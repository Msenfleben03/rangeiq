"""Walk-Forward Backtest for NCAAB Elo Model.

Loads a trained model, holds out the most recent season for testing,
and runs a walk-forward backtest: for each game date, predict -> evaluate
-> update ratings.

Uses real ESPN odds data when available (default), or simulated odds
with --simulate flag.

Usage:
    python scripts/backtest_ncaab_elo.py
    python scripts/backtest_ncaab_elo.py --test-season 2025 --min-edge 0.02
    python scripts/backtest_ncaab_elo.py --simulate  # Use simulated odds (legacy)
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from betting.odds_converter import (
    american_to_decimal,
    american_to_implied_prob,
    calculate_clv,
    calculate_edge,
    fractional_kelly,
)
from config.constants import BANKROLL, THRESHOLDS
from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR
from models.model_persistence import load_model
from models.sport_specific.ncaab.team_ratings import NCAABEloModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_test_season(season: int) -> pd.DataFrame:
    """Load raw data for the test season."""
    path = RAW_DATA_DIR / "ncaab" / f"ncaab_games_{season}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No data for test season {season}: {path}")
    df = pd.read_parquet(path)
    logger.info("Loaded test season %d: %d rows", season, len(df))
    return df


def prepare_test_games(df: pd.DataFrame) -> list[dict]:
    """Convert raw data to game dicts, deduplicating by game_id."""
    games = []
    seen: set[str] = set()

    for _, row in df.iterrows():
        game_id = row.get("game_id", "")
        if not game_id or game_id in seen:
            continue
        seen.add(game_id)

        location = str(row.get("location", "")).strip().lower()
        team_id = str(row.get("team_id", ""))
        opponent_id = str(row.get("opponent_id", ""))
        points_for = row.get("points_for")
        points_against = row.get("points_against")

        if pd.isna(points_for) or pd.isna(points_against):
            continue

        game_date = row.get("date")
        if isinstance(game_date, str):
            try:
                game_date = pd.to_datetime(game_date)
            except (ValueError, TypeError):
                continue

        if location == "home":
            home, away = team_id, opponent_id
            home_score, away_score = int(points_for), int(points_against)
            neutral = False
        elif location == "away":
            home, away = opponent_id, team_id
            home_score, away_score = int(points_against), int(points_for)
            neutral = False
        else:
            home, away = team_id, opponent_id
            home_score, away_score = int(points_for), int(points_against)
            neutral = True

        games.append(
            {
                "game_id": game_id,
                "date": game_date,
                "home": home,
                "away": away,
                "home_score": home_score,
                "away_score": away_score,
                "neutral_site": neutral,
            }
        )

    games.sort(key=lambda g: g["date"])
    return games


def load_odds_data(season: int, provider_id: int = 58) -> dict[str, dict]:
    """Load real odds data and index by game_id.

    Args:
        season: Season year (e.g. 2025).
        provider_id: ESPN provider ID (58=ESPN BET, 100=DraftKings).

    Returns:
        Dict mapping game_id -> odds dict with opening/closing lines.
    """
    odds_path = Path("data/odds") / f"ncaab_odds_{season}.parquet"
    if not odds_path.exists():
        logger.warning("No odds file found at %s", odds_path)
        return {}

    df = pd.read_parquet(odds_path)
    provider_df = df[df["provider_id"] == provider_id]

    if provider_df.empty:
        # Try any available provider
        logger.warning("Provider %d not found, using first available", provider_id)
        provider_df = df.drop_duplicates(subset=["game_id"], keep="first")

    odds_lookup: dict[str, dict] = {}
    for _, row in provider_df.iterrows():
        game_id = str(row["game_id"])
        odds_lookup[game_id] = {
            "home_ml_open": row.get("home_ml_open"),
            "away_ml_open": row.get("away_ml_open"),
            "home_ml_close": row.get("home_ml_close"),
            "away_ml_close": row.get("away_ml_close"),
            "home_moneyline": row.get("home_moneyline"),
            "away_moneyline": row.get("away_moneyline"),
            "spread": row.get("spread"),
            "home_spread_close": row.get("home_spread_close"),
        }

    logger.info(
        "Loaded %d games with real odds (provider %d) for season %d",
        len(odds_lookup),
        provider_id,
        season,
    )
    return odds_lookup


def _get_real_odds(
    odds_lookup: dict[str, dict], game_id: str
) -> tuple[int | None, int | None, int | None, int | None]:
    """Extract opening and closing moneylines for a game.

    Returns:
        (home_ml_open, away_ml_open, home_ml_close, away_ml_close)
        Any value may be None if not available.
    """
    entry = odds_lookup.get(str(game_id))
    if entry is None:
        return None, None, None, None

    home_open = entry["home_ml_open"]
    away_open = entry["away_ml_open"]
    home_close = entry["home_ml_close"]
    away_close = entry["away_ml_close"]

    # Fall back to current moneyline if open/close missing
    if pd.isna(home_open):
        home_open = entry["home_moneyline"]
    if pd.isna(away_open):
        away_open = entry["away_moneyline"]
    if pd.isna(home_close):
        home_close = entry["home_moneyline"]
    if pd.isna(away_close):
        away_close = entry["away_moneyline"]

    # Convert to int if valid (0 is invalid for American odds)
    def _to_int(v: float | None) -> int | None:
        if v is None or pd.isna(v):
            return None
        val = int(v)
        if val == 0:
            return None
        return val

    return _to_int(home_open), _to_int(away_open), _to_int(home_close), _to_int(away_close)


def simulate_market_odds(win_prob: float, vig: float = 0.05) -> int:
    """Simulate realistic American market odds from a true probability.

    Adds vig and random noise to create a synthetic market line.

    Args:
        win_prob: True win probability.
        vig: Vig/juice to add (default 5%).

    Returns:
        Simulated American odds.
    """
    # Add vig to implied probability
    implied = win_prob + vig / 2
    implied = max(0.05, min(0.95, implied))

    # Add small random noise (market inefficiency)
    noise = np.random.normal(0, 0.015)
    implied = max(0.05, min(0.95, implied + noise))

    # Convert to American
    if implied >= 0.5:
        return int(-100 * implied / (1 - implied))
    else:
        return int(100 * (1 - implied) / implied)


def simulate_closing_odds(opening_odds: int) -> int:
    """Simulate closing odds from opening odds.

    Lines typically move 1-3 points toward the sharp side.

    Args:
        opening_odds: Opening American odds.

    Returns:
        Simulated closing American odds.
    """
    # Small random movement
    move = np.random.normal(0, 3)
    prob = american_to_implied_prob(opening_odds)
    closing_prob = max(0.05, min(0.95, prob + move / 100))

    if closing_prob >= 0.5:
        return int(-100 * closing_prob / (1 - closing_prob))
    else:
        return int(100 * (1 - closing_prob) / closing_prob)


def run_backtest(
    model: NCAABEloModel,
    games: list[dict],
    min_edge: float = 0.02,
    kelly_fraction: float = 0.25,
    max_bet: float = 0.03,
    bankroll: float = 5000.0,
    odds_lookup: dict[str, dict] | None = None,
    use_simulated: bool = False,
) -> pd.DataFrame:
    """Run walk-forward backtest.

    For each game: predict -> get odds -> check edge -> size bet ->
    record -> update model.

    Args:
        model: Trained NCAABEloModel.
        games: Chronologically sorted game list.
        min_edge: Minimum edge to place a bet.
        kelly_fraction: Kelly fraction for sizing.
        max_bet: Maximum bet as fraction of bankroll.
        bankroll: Starting bankroll.
        odds_lookup: Dict mapping game_id -> odds dict (real odds).
        use_simulated: If True, use simulated odds instead of real.

    Returns:
        DataFrame of backtest results.
    """
    np.random.seed(42)  # Reproducibility
    results = []
    current_bankroll = bankroll
    skipped_no_odds = 0

    for game in games:
        home = game["home"]
        away = game["away"]
        home_score = game["home_score"]
        away_score = game["away_score"]
        neutral = game["neutral_site"]
        game_id = game["game_id"]

        # 1. PREDICT (before seeing result)
        home_win_prob = model.predict_win_probability(home, away, neutral)
        predicted_spread = model.predict_spread(home, away, neutral)

        # 2. GET ODDS (real or simulated)
        if use_simulated or odds_lookup is None:
            market_odds_home = simulate_market_odds(home_win_prob)
            market_odds_away = simulate_market_odds(1 - home_win_prob)
            closing_odds_home = simulate_closing_odds(market_odds_home)
            closing_odds_away = simulate_closing_odds(market_odds_away)
        else:
            home_open, away_open, home_close, away_close = _get_real_odds(odds_lookup, game_id)
            if home_open is None or away_open is None:
                # No odds for this game — still update model, skip betting
                model.update_game(home, away, home_score, away_score, neutral)
                skipped_no_odds += 1
                continue
            market_odds_home = home_open
            market_odds_away = away_open
            closing_odds_home = home_close if home_close is not None else home_open
            closing_odds_away = away_close if away_close is not None else away_open

        # 3. CALCULATE EDGE (both sides)
        home_edge = calculate_edge(home_win_prob, market_odds_home)
        away_edge = calculate_edge(1 - home_win_prob, market_odds_away)

        # 4. PICK BEST SIDE (if either qualifies)
        if abs(home_edge) >= min_edge or abs(away_edge) >= min_edge:
            if home_edge > away_edge and home_edge >= min_edge:
                bet_side = "home"
                bet_prob = home_win_prob
                bet_odds = market_odds_home
                closing_odds = closing_odds_home
                won = home_score > away_score
            elif away_edge >= min_edge:
                bet_side = "away"
                bet_prob = 1 - home_win_prob
                bet_odds = market_odds_away
                closing_odds = closing_odds_away
                won = away_score > home_score
            else:
                # Home edge is negative but above threshold on abs, skip
                model.update_game(home, away, home_score, away_score, neutral)
                continue

            # 5. SIZE BET (Kelly)
            decimal_odds = american_to_decimal(bet_odds)
            bet_fraction = fractional_kelly(bet_prob, decimal_odds, kelly_fraction, max_bet)
            stake = current_bankroll * bet_fraction

            if stake > 0:
                # 6. CALCULATE P/L
                if won:
                    profit = stake * (decimal_odds - 1)
                    result_str = "win"
                else:
                    profit = -stake
                    result_str = "loss"

                # 7. CLV
                clv = calculate_clv(bet_odds, closing_odds)

                current_bankroll += profit

                results.append(
                    {
                        "game_id": game_id,
                        "date": game["date"],
                        "home": home,
                        "away": away,
                        "home_score": home_score,
                        "away_score": away_score,
                        "bet_side": bet_side,
                        "model_prob": bet_prob,
                        "edge": max(home_edge, away_edge),
                        "odds_placed": bet_odds,
                        "odds_closing": closing_odds,
                        "stake": stake,
                        "result": result_str,
                        "profit_loss": profit,
                        "clv": clv,
                        "bankroll": current_bankroll,
                        "predicted_spread": predicted_spread,
                    }
                )

        # 8. UPDATE MODEL (always, regardless of bet)
        model.update_game(home, away, home_score, away_score, neutral)

    if skipped_no_odds > 0:
        logger.info("Skipped %d games with no odds data", skipped_no_odds)

    df = pd.DataFrame(results)
    return df


def summarize_backtest(df: pd.DataFrame, initial_bankroll: float = 5000.0) -> dict:
    """Calculate summary statistics from backtest results."""
    if df.empty:
        return {"error": "No bets placed"}

    total_bets = len(df)
    wins = (df["result"] == "win").sum()
    losses = (df["result"] == "loss").sum()
    total_pnl = df["profit_loss"].sum()
    total_staked = df["stake"].sum()
    avg_clv = df["clv"].mean()
    win_rate = wins / total_bets

    # ROI
    roi = total_pnl / total_staked if total_staked > 0 else 0

    # Sharpe ratio (annualized, ~150 betting days)
    daily_pnl = df.groupby(df["date"].dt.date)["profit_loss"].sum()
    if len(daily_pnl) > 1 and daily_pnl.std() > 0:
        sharpe = (daily_pnl.mean() / daily_pnl.std()) * np.sqrt(150)
    else:
        sharpe = 0.0

    # Max drawdown
    cumulative = df["profit_loss"].cumsum()
    running_max = cumulative.cummax()
    drawdown = cumulative - running_max
    max_drawdown = drawdown.min()

    return {
        "total_bets": total_bets,
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "total_staked": total_staked,
        "roi": roi,
        "avg_clv": avg_clv,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "final_bankroll": df["bankroll"].iloc[-1] if not df.empty else initial_bankroll,
        "avg_edge": df["edge"].mean(),
        "avg_stake": df["stake"].mean(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward backtest for NCAAB Elo")
    parser.add_argument("--test-season", type=int, default=2025)
    parser.add_argument("--min-edge", type=float, default=THRESHOLDS.MIN_EDGE_SPREAD)
    parser.add_argument("--kelly", type=float, default=BANKROLL.KELLY_FRACTION_DEFAULT)
    parser.add_argument("--max-bet", type=float, default=BANKROLL.MAX_BET_FRACTION)
    parser.add_argument("--bankroll", type=float, default=BANKROLL.TOTAL_BANKROLL)
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Use simulated odds instead of real ESPN data (legacy mode)",
    )
    args = parser.parse_args()

    # Load trained model
    model_path = PROCESSED_DATA_DIR / "ncaab_elo_model.pkl"
    if not model_path.exists():
        logger.error("No trained model found. Run train_ncaab_elo.py first.")
        sys.exit(1)

    saved = load_model(model_path)
    model = saved.model
    logger.info("Loaded model with %d teams", len(model.ratings))

    # Apply regression before test season
    model.apply_season_regression()

    # Load test season
    df_raw = load_test_season(args.test_season)
    games = prepare_test_games(df_raw)
    logger.info("Prepared %d test games for season %d", len(games), args.test_season)

    # Load real odds (unless --simulate)
    odds_lookup = None
    if not args.simulate:
        odds_lookup = load_odds_data(args.test_season)
        if not odds_lookup:
            logger.warning(
                "No real odds data for season %d. Falling back to simulated odds.",
                args.test_season,
            )
    else:
        logger.info("Using simulated odds (--simulate flag)")

    odds_mode = "simulated" if args.simulate or not odds_lookup else "real"

    # Run backtest
    results = run_backtest(
        model=model,
        games=games,
        min_edge=args.min_edge,
        kelly_fraction=args.kelly,
        max_bet=args.max_bet,
        bankroll=args.bankroll,
        odds_lookup=odds_lookup,
        use_simulated=args.simulate,
    )

    # Save results
    output_dir = Path("data/backtests")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"ncaab_elo_backtest_{args.test_season}.parquet"
    results.to_parquet(output_path, index=False)
    logger.info("Saved backtest results to %s", output_path)

    # Summary
    summary = summarize_backtest(results, args.bankroll)

    print(f"\n{'=' * 60}")
    print(f"BACKTEST RESULTS — NCAAB Elo ({args.test_season} season)")
    print(f"Odds source: {odds_mode.upper()}")
    if odds_mode == "real" and odds_lookup:
        games_with_odds = sum(1 for g in games if str(g["game_id"]) in odds_lookup)
        print(f"Games with odds: {games_with_odds}/{len(games)}")
    print(f"{'=' * 60}")
    print(f"Total bets:     {summary['total_bets']}")
    print(f"Win rate:        {summary['win_rate']:.1%}")
    print(f"Total P/L:      ${summary['total_pnl']:+.2f}")
    print(f"ROI:             {summary['roi']:.2%}")
    print(f"Avg CLV:         {summary['avg_clv']:.3%}")
    print(f"Sharpe ratio:    {summary['sharpe']:.2f}")
    print(f"Max drawdown:   ${summary['max_drawdown']:.2f}")
    print(f"Final bankroll: ${summary['final_bankroll']:.2f}")
    print(f"Avg edge:        {summary['avg_edge']:.2%}")
    print(f"Avg stake:      ${summary['avg_stake']:.2f}")

    # Check Gatekeeper-relevant thresholds
    print(f"\n{'=' * 60}")
    print("GATEKEEPER CHECK PREVIEW")
    print(f"{'=' * 60}")
    checks = {
        "Sample size >= 200": summary["total_bets"] >= 200,
        "Sharpe >= 0.5": summary["sharpe"] >= 0.5,
        "In-sample ROI <= 15%": summary["roi"] <= 0.15,
        "Avg CLV >= 1.5%": summary["avg_clv"] >= 0.015,
    }
    for check, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {check}")


if __name__ == "__main__":
    main()
