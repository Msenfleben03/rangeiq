"""Daily NCAAB Predictions with Integrated Odds.

Loads trained model, fetches today's games via ESPN Scoreboard API,
predicts outcomes, retrieves live odds, calculates edges, and
outputs bet recommendations. Optionally applies Barttorvik adjustments.

Usage:
    python scripts/daily_predictions.py --date today
    python scripts/daily_predictions.py --date 2026-02-15 --barttorvik
    python scripts/daily_predictions.py --date today --mode manual --odds-file odds.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import requests

from betting.odds_converter import (
    american_to_decimal,
    calculate_edge,
    fractional_kelly,
)
from config.constants import BREADWINNER, ODDS_CONFIG, PAPER_BETTING
from features.sport_specific.ncaab.breadwinner import (
    BreadwinnerScores,
    get_breadwinner_adjustment,
)
from config.settings import NCAAB_DATABASE_PATH as DATABASE_PATH, ODDS_API_KEY, PROCESSED_DATA_DIR
from models.model_persistence import load_model
from pipelines.barttorvik_fetcher import compute_barttorvik_differentials, load_cached_season
from pipelines.kenpom_fetcher import (
    compute_kenpom_differentials,
    load_cached_season as load_kenpom_cached,
)
from pipelines.injury_checker import GameContext, check_divergence
from pipelines.odds_orchestrator import OddsOrchestrator
from pipelines.team_name_mapping import espn_id_to_barttorvik, espn_id_to_kenpom
from scripts.backtest_ncaab_elo import BarttovikCoeffs, KenPomCoeffs
from tracking.database import BettingDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> datetime:
    """Parse date argument."""
    if date_str.lower() in ("today", "now"):
        return datetime.now()
    if date_str.lower() == "tomorrow":
        return datetime.now() + timedelta(days=1)
    return datetime.strptime(date_str, "%Y-%m-%d")


def fetch_espn_scoreboard(target_date: datetime) -> list[dict]:
    """Fetch today's NCAAB games from ESPN Scoreboard API.

    Uses ESPN's public JSON API instead of broken sportsipy.

    Args:
        target_date: Date to fetch games for.

    Returns:
        List of game dicts with keys: game_id, home, away, home_name,
        away_name, game_time, status, home_score, away_score.
    """
    date_str = target_date.strftime("%Y%m%d")
    url = PAPER_BETTING.ESPN_SCOREBOARD_URL
    params = {"dates": date_str, "limit": 500, "groups": 50}

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.error("ESPN Scoreboard API error: %s", e)
        return []

    events = data.get("events", [])
    games = []

    for event in events:
        competitions = event.get("competitions", [])
        if not competitions:
            continue

        comp = competitions[0]
        competitors = comp.get("competitors", [])
        if len(competitors) != 2:
            continue

        home_team = None
        away_team = None
        for team_data in competitors:
            team_info = team_data.get("team", {})
            entry = {
                "id": team_info.get("id", ""),
                "abbr": team_info.get("abbreviation", ""),
                "name": team_info.get("displayName", ""),
                "score": team_data.get("score", "0"),
            }
            if team_data.get("homeAway") == "home":
                home_team = entry
            else:
                away_team = entry

        if not home_team or not away_team:
            continue

        neutral = comp.get("neutralSite", False)
        status_type = comp.get("status", {}).get("type", {}).get("name", "")

        games.append(
            {
                "game_id": str(event.get("id", "")),
                "home": home_team["abbr"],
                "away": away_team["abbr"],
                "home_id": home_team["id"],
                "away_id": away_team["id"],
                "home_name": home_team["name"],
                "away_name": away_team["name"],
                "home_score": int(home_team["score"]) if home_team["score"] else 0,
                "away_score": int(away_team["score"]) if away_team["score"] else 0,
                "neutral_site": neutral,
                "status": status_type,
                "game_time": event.get("date", ""),
            }
        )

    logger.info(
        "Fetched %d games from ESPN Scoreboard for %s",
        len(games),
        target_date.strftime("%Y-%m-%d"),
    )
    return games


def generate_predictions(
    model,
    games: list[dict],
    orchestrator: OddsOrchestrator | None = None,
    mode: str = "auto",
    min_edge: float = 0.05,
    use_barttorvik: bool = False,
    barttorvik_df: pd.DataFrame | None = None,
    bart_coeffs: BarttovikCoeffs | None = None,
    barttorvik_weight: float = 1.0,
    use_kenpom: bool = False,
    kenpom_df: pd.DataFrame | None = None,
    kenpom_coeffs: KenPomCoeffs | None = None,
    kenpom_weight: float = 1.0,
    breadwinner_lookup: dict[str, BreadwinnerScores] | None = None,
    breadwinner_coeff: float = BREADWINNER.BREADWINNER_COEFF,
    breadwinner_variant: str = BREADWINNER.BREADWINNER_VARIANT,
    breadwinner_include_centers: bool = BREADWINNER.INCLUDE_CENTERS,
    target_date: datetime | None = None,
    game_context: dict[str, GameContext] | None = None,
    kelly_sizer=None,
) -> pd.DataFrame:
    """Generate predictions + odds + edge calculations for each game.

    Args:
        model: Trained NCAABEloModel.
        games: List of game dicts from ESPN Scoreboard.
        orchestrator: OddsOrchestrator for fetching odds (optional).
        mode: Odds retrieval mode.
        min_edge: Minimum edge for bet recommendations.
        use_barttorvik: Whether to apply Barttorvik adjustments.
        barttorvik_df: Barttorvik ratings DataFrame.
        bart_coeffs: Barttorvik coefficients.
        barttorvik_weight: Weight for Barttorvik adjustment.
        breadwinner_lookup: Dict mapping team -> BreadwinnerScores.
        breadwinner_coeff: Variance compression coefficient.
        breadwinner_variant: "top1", "top2", or "hhi".
        breadwinner_include_centers: If False, skip center breadwinners.
        target_date: Game date for Barttorvik PIT lookup.
        game_context: Dict of game_id -> GameContext from ESPN summary API.
            Used to cross-check model probabilities against ESPN predictor
            and scan news for injury keywords.
        kelly_sizer: Optional KellySizer instance for calibrated bet sizing.
            When None, falls back to raw fractional_kelly with model probs.

    Returns:
        DataFrame of predictions with bet recommendations.
    """
    predictions = []

    for game in games:
        home = game.get("home", "")
        away = game.get("away", "")
        game_id = game.get("game_id", f"{home}_{away}")
        neutral = game.get("neutral_site", False)

        # Model prediction (Elo baseline)
        home_prob = model.predict_win_probability(home, away, neutral)
        spread = model.predict_spread(home, away, neutral)

        # Barttorvik adjustment
        bart_adj = 0.0
        if use_barttorvik and barttorvik_df is not None:
            home_bart = espn_id_to_barttorvik(home)
            away_bart = espn_id_to_barttorvik(away)
            if home_bart and away_bart:
                lookup_date = target_date.date() if target_date else datetime.now().date()
                diffs = compute_barttorvik_differentials(
                    barttorvik_df,
                    home_bart,
                    away_bart,
                    lookup_date,
                )
                if diffs:
                    coeffs = bart_coeffs or BarttovikCoeffs()
                    net_diff = diffs.get("net_rating_diff", 0)
                    barthag_diff = diffs.get("barthag_diff", 0)
                    bart_adj = (
                        net_diff * coeffs.net_diff_coeff + barthag_diff * coeffs.barthag_diff_coeff
                    )
                    home_prob = max(0.01, min(0.99, home_prob + barttorvik_weight * bart_adj))

        # KenPom adjustment
        kp_adj = 0.0
        if use_kenpom and kenpom_df is not None:
            home_kp = espn_id_to_kenpom(home)
            away_kp = espn_id_to_kenpom(away)
            if home_kp and away_kp:
                lookup_date = target_date.date() if target_date else datetime.now().date()
                kp_diffs = compute_kenpom_differentials(
                    kenpom_df,
                    home_kp,
                    away_kp,
                    lookup_date,
                )
                if kp_diffs:
                    kp_c = kenpom_coeffs or KenPomCoeffs()
                    adj_em_diff = kp_diffs.get("adj_em_diff", 0)
                    sos_diff = kp_diffs.get("sos_adj_em_diff", 0)
                    kp_adj = adj_em_diff * kp_c.net_diff_coeff + sos_diff * kp_c.sos_coeff
                    home_prob = max(0.01, min(0.99, home_prob + kenpom_weight * kp_adj))

        # Breadwinner adjustment
        bw_adj = 0.0
        if breadwinner_lookup:
            home_bw = espn_id_to_barttorvik(home)
            away_bw = espn_id_to_barttorvik(away)
            if home_bw and away_bw:
                bw_adj = get_breadwinner_adjustment(
                    home=home_bw,
                    away=away_bw,
                    home_prob=home_prob,
                    lookup=breadwinner_lookup,
                    coeff=breadwinner_coeff,
                    variant=breadwinner_variant,
                    include_centers=breadwinner_include_centers,
                )
                home_prob = max(0.01, min(0.99, home_prob + bw_adj))

        fair_home_ml = _prob_to_american(home_prob)
        fair_away_ml = _prob_to_american(1 - home_prob)

        pred = {
            "game_id": game_id,
            "home": home,
            "away": away,
            "home_name": game.get("home_name", home),
            "away_name": game.get("away_name", away),
            "home_prob": home_prob,
            "away_prob": 1 - home_prob,
            "predicted_spread": spread,
            "fair_home_ml": fair_home_ml,
            "fair_away_ml": fair_away_ml,
            "bart_adj": bart_adj,
            "bw_adj": bw_adj,
            "neutral_site": neutral,
            "status": game.get("status", ""),
        }

        # Fetch market odds (if orchestrator available)
        if orchestrator is not None:
            try:
                odds = orchestrator.fetch_odds(
                    sport="ncaab",
                    home=game.get("home_name", home),
                    away=game.get("away_name", away),
                    game_id=game_id,
                    mode=mode,
                )
            except Exception as e:
                logger.debug("Odds fetch failed for %s: %s", game_id, e)
                odds = None

            if odds is not None:
                pred["sportsbook"] = odds.sportsbook
                pred["market_spread"] = odds.spread_home
                pred["home_ml"] = odds.moneyline_home
                pred["away_ml"] = odds.moneyline_away

                if odds.moneyline_home is not None:
                    home_edge = calculate_edge(home_prob, odds.moneyline_home)
                    away_edge = (
                        calculate_edge(1 - home_prob, odds.moneyline_away)
                        if odds.moneyline_away
                        else 0
                    )
                    pred["home_edge"] = home_edge
                    pred["away_edge"] = away_edge

                    # Bet recommendation
                    if home_edge >= min_edge:
                        if kelly_sizer is not None:
                            stake = kelly_sizer.size_bet(
                                model_prob=home_prob,
                                edge=home_edge,
                                american_odds=odds.moneyline_home,
                            )
                        else:
                            decimal_odds = american_to_decimal(odds.moneyline_home)
                            kelly = fractional_kelly(home_prob, decimal_odds)
                            stake = PAPER_BETTING.PAPER_BANKROLL * kelly
                        if stake > 0:
                            pred["rec_side"] = "HOME"
                            pred["rec_odds"] = odds.moneyline_home
                            pred["rec_kelly"] = stake / PAPER_BETTING.PAPER_BANKROLL
                            pred["rec_stake"] = stake
                    elif away_edge >= min_edge:
                        if kelly_sizer is not None:
                            stake = kelly_sizer.size_bet(
                                model_prob=1 - home_prob,
                                edge=away_edge,
                                american_odds=odds.moneyline_away,
                            )
                        else:
                            decimal_odds = american_to_decimal(odds.moneyline_away)
                            kelly = fractional_kelly(1 - home_prob, decimal_odds)
                            stake = PAPER_BETTING.PAPER_BANKROLL * kelly
                        if stake > 0:
                            pred["rec_side"] = "AWAY"
                            pred["rec_odds"] = odds.moneyline_away
                            pred["rec_kelly"] = stake / PAPER_BETTING.PAPER_BANKROLL
                            pred["rec_stake"] = stake

        # ESPN predictor cross-check (injury/divergence detection)
        if game_context and game_id in game_context:
            ctx = game_context[game_id]
            if ctx.fetch_success:
                pred["espn_prob"] = ctx.espn_home_prob
                pred["espn_spread"] = ctx.espn_spread

                div_result = check_divergence(home_prob, ctx.espn_home_prob)
                pred["prob_divergence"] = div_result["divergence"]

                # Block on divergence threshold only — keywords are informational
                # (ESPN news is often general NCAAB news, not game-specific)
                injury_flag = div_result["is_blocked"]
                pred["injury_flag"] = injury_flag
                pred["injury_details"] = (
                    "; ".join(ctx.news_headlines[:3]) if ctx.news_headlines else ""
                )
                pred["injury_keywords"] = ", ".join(ctx.injury_keywords_found)
                pred["divergence_warning"] = div_result["is_warning"]

                # Suppress bet recommendation if divergence exceeds block threshold
                if injury_flag and "rec_side" in pred:
                    logger.warning(
                        "Bet suppressed for %s @ %s: divergence=%.0fpp, keywords=%s",
                        away,
                        home,
                        (div_result["divergence"] or 0) * 100,
                        ctx.injury_keywords_found,
                    )
                    pred["rec_side"] = None
                    pred["rec_odds"] = None
                    pred["rec_kelly"] = None
                    pred["rec_stake"] = None

        predictions.append(pred)

    return pd.DataFrame(predictions)


def _prob_to_american(prob: float) -> int:
    """Convert probability to American odds."""
    if prob <= 0 or prob >= 1:
        return 0
    if prob >= 0.5:
        return int(-100 * prob / (1 - prob))
    return int(100 * (1 - prob) / prob)


def display_predictions(df: pd.DataFrame) -> None:
    """Pretty-print prediction table."""
    has_espn = "espn_prob" in df.columns if not df.empty else False

    print(f"\n{'=' * 100}")
    print("DAILY PREDICTIONS -- NCAAB")
    print(f"{'=' * 100}")

    if df.empty:
        print("No games found for today.")
        return

    if has_espn:
        print(
            f"\n{'Game':<30s} {'Spread':>7s} {'Home%':>6s} {'ESPN%':>6s} "
            f"{'Div':>6s} {'HML':>6s} {'AML':>6s} {'Edge':>6s}"
        )
        print("-" * 85)
    else:
        print(f"\n{'Game':<30s} {'Spread':>7s} {'Home%':>6s} {'HML':>6s} {'AML':>6s} {'Edge':>6s}")
        print("-" * 70)

    for _, row in df.iterrows():
        matchup = f"{row['away']} @ {row['home']}"
        spread = f"{row['predicted_spread']:+.1f}" if pd.notna(row.get("predicted_spread")) else "?"
        home_pct = f"{row['home_prob']:.0%}"
        hml = str(row.get("home_ml", "?"))
        aml = str(row.get("away_ml", "?"))
        edge = ""
        if "home_edge" in row and pd.notna(row.get("home_edge")):
            best_edge = max(row.get("home_edge", 0), row.get("away_edge", 0))
            edge = f"{best_edge:+.1%}"

        if has_espn:
            espn_pct = f"{row['espn_prob']:.0%}" if pd.notna(row.get("espn_prob")) else "N/A"
            div_val = row.get("prob_divergence")
            div_str = f"{div_val:+.0%}" if pd.notna(div_val) else "N/A"
            print(
                f"{matchup:<30s} {spread:>7s} {home_pct:>6s} {espn_pct:>6s} "
                f"{div_str:>6s} {hml:>6s} {aml:>6s} {edge:>6s}"
            )
        else:
            print(f"{matchup:<30s} {spread:>7s} {home_pct:>6s} {hml:>6s} {aml:>6s} {edge:>6s}")

    # Injury/divergence warnings
    if "injury_flag" in df.columns:
        flagged = df[df["injury_flag"] == True]  # noqa: E712
        if not flagged.empty:
            print(f"\n{'!' * 3} INJURY/DIVERGENCE WARNINGS {'!' * 3}")
            print("-" * 85)
            for _, row in flagged.iterrows():
                matchup = f"{row['away']} @ {row['home']}"
                model_pct = f"{row['home_prob']:.0%}"
                espn_pct = f"{row['espn_prob']:.0%}" if pd.notna(row.get("espn_prob")) else "N/A"
                div_val = row.get("prob_divergence")
                div_pp = f"{abs(div_val) * 100:.0f}pp" if pd.notna(div_val) else "?"

                print(f"  {matchup}: Model {model_pct} vs ESPN {espn_pct} -- DIVERGENCE {div_pp}")

                keywords = row.get("injury_keywords", "")
                if keywords:
                    print(f"    Keywords: {keywords}")

                details = row.get("injury_details", "")
                if details:
                    # Truncate long headlines
                    if len(details) > 120:
                        details = details[:117] + "..."
                    print(f"    Headlines: {details}")

                print("    Bet SUPPRESSED -- verify injuries before manual override")

    # Bet recommendations
    if "rec_side" in df.columns:
        recs = df[df["rec_side"].notna()].copy()
    else:
        recs = df.iloc[0:0].copy()
    if not recs.empty:
        print(f"\n{'=' * 90}")
        print("BET RECOMMENDATIONS (edge >= threshold)")
        print(f"{'=' * 90}")
        print(f"{'Game':<25s} {'Side':>5s} {'Odds':>6s} {'Edge':>6s} {'Kelly':>6s} {'Stake':>8s}")
        print("-" * 65)
        for _, row in recs.iterrows():
            matchup = f"{row['away']} @ {row['home']}"
            side = row.get("rec_side", "")
            odds = str(row.get("rec_odds", ""))
            edge_val = row.get("home_edge", 0) if side == "HOME" else row.get("away_edge", 0)
            kelly = f"{row.get('rec_kelly', 0):.1%}"
            stake = f"${row.get('rec_stake', 0):.0f}"
            print(f"{matchup:<25s} {side:>5s} {odds:>6s} {edge_val:>+5.1%} {kelly:>6s} {stake:>8s}")
    else:
        print("\nNo bets qualify (no edges above threshold).")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily NCAAB predictions")
    parser.add_argument("--date", type=str, default="today")
    parser.add_argument("--mode", type=str, default=ODDS_CONFIG.DEFAULT_MODE)
    parser.add_argument("--odds-file", type=str, default=None)
    parser.add_argument("--min-edge", type=float, default=PAPER_BETTING.MIN_EDGE)
    parser.add_argument(
        "--barttorvik",
        action="store_true",
        help="Apply Barttorvik efficiency adjustments",
    )
    parser.add_argument(
        "--barttorvik-weight",
        type=float,
        default=PAPER_BETTING.BARTTORVIK_WEIGHT,
    )
    parser.add_argument(
        "--kenpom",
        action="store_true",
        help="Apply KenPom efficiency adjustments",
    )
    parser.add_argument(
        "--kenpom-weight",
        type=float,
        default=1.0,
    )
    args = parser.parse_args()

    target_date = parse_date(args.date)
    logger.info(
        "Generating predictions for %s (mode=%s)",
        target_date.strftime("%Y-%m-%d"),
        args.mode,
    )

    # Load model
    model_path = PROCESSED_DATA_DIR / "ncaab_elo_model.pkl"
    if not model_path.exists():
        logger.error("No trained model. Run train_ncaab_elo.py first.")
        sys.exit(1)

    saved = load_model(model_path)
    model = saved.model
    logger.info("Model loaded: %d teams", len(model.ratings))

    # Set up orchestrator
    db = BettingDatabase(str(DATABASE_PATH))
    orchestrator = OddsOrchestrator(
        db=db,
        cache_ttl=ODDS_CONFIG.CACHE_TTL_SECONDS,
        monthly_credit_limit=ODDS_CONFIG.API_CREDIT_MONTHLY_LIMIT,
    )
    orchestrator.register_default_providers(
        api_key=ODDS_API_KEY,
        csv_path=args.odds_file,
    )

    # Fetch games via ESPN Scoreboard API
    games = fetch_espn_scoreboard(target_date)
    if not games:
        print("No games found. Try a different date.")
        return

    # Filter to pre-game only
    pre_game = [g for g in games if g["status"] in ("STATUS_SCHEDULED", "STATUS_PREGAME", "")]
    logger.info("%d pre-game / %d total games", len(pre_game), len(games))

    # Barttorvik data
    barttorvik_df = None
    bart_coeffs = None
    if args.barttorvik:
        season = target_date.year if target_date.month >= 10 else target_date.year
        barttorvik_df = load_cached_season(season)
        bart_coeffs = BarttovikCoeffs(
            net_diff_coeff=PAPER_BETTING.BARTTORVIK_NET_DIFF_COEFF,
            barthag_diff_coeff=PAPER_BETTING.BARTTORVIK_BARTHAG_DIFF_COEFF,
        )
        if barttorvik_df is not None:
            logger.info("Barttorvik data: %d rows for season %d", len(barttorvik_df), season)
        else:
            logger.warning("No Barttorvik data for season %d", season)

    # KenPom data
    kenpom_df = None
    kenpom_coeffs = None
    if args.kenpom:
        from config.constants import KENPOM

        season = target_date.year if target_date.month >= 10 else target_date.year
        kenpom_df = load_kenpom_cached(season)
        kenpom_coeffs = KenPomCoeffs(
            net_diff_coeff=KENPOM.KENPOM_NET_DIFF_COEFF,
            sos_coeff=KENPOM.KENPOM_SOS_COEFF,
        )
        if kenpom_df is not None:
            logger.info("KenPom data: %d rows for season %d", len(kenpom_df), season)
        else:
            logger.warning("No KenPom data for season %d", season)

    # Generate predictions
    predictions = generate_predictions(
        model=model,
        games=pre_game if pre_game else games,
        orchestrator=orchestrator,
        mode=args.mode,
        min_edge=args.min_edge,
        use_barttorvik=args.barttorvik,
        barttorvik_df=barttorvik_df,
        bart_coeffs=bart_coeffs,
        barttorvik_weight=args.barttorvik_weight,
        use_kenpom=args.kenpom,
        kenpom_df=kenpom_df,
        kenpom_coeffs=kenpom_coeffs,
        kenpom_weight=args.kenpom_weight,
        target_date=target_date,
    )

    # Store predictions in database
    for _, row in predictions.iterrows():
        try:
            db.execute_query(
                """INSERT OR REPLACE INTO predictions
                    (sport, game_id, game_date, model_name, prediction_type,
                     predicted_value, market_value)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    "ncaab",
                    row["game_id"],
                    target_date.strftime("%Y-%m-%d"),
                    "ncaab_elo_v1",
                    "home_win_prob",
                    row["home_prob"],
                    row.get("home_ml"),
                ),
            )
        except Exception as e:
            logger.debug("Prediction storage skipped: %s", e)

    # Display
    display_predictions(predictions)

    # Credit budget check
    budget = orchestrator.get_credit_budget()
    if budget.get("is_warning"):
        print(f"\nWARNING: Odds API at {budget['pct_used']:.0%} of monthly credits!")


if __name__ == "__main__":
    main()
