"""Daily NCAAB Predictions with Integrated Odds.

Loads trained model, fetches today's games, predicts outcomes,
retrieves odds via OddsOrchestrator, calculates edges, and
outputs bet recommendations.

Usage:
    python scripts/daily_predictions.py --date today
    python scripts/daily_predictions.py --date 2026-02-15 --mode api
    python scripts/daily_predictions.py --date today --mode manual --odds-file odds.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from betting.odds_converter import (
    american_to_decimal,
    calculate_edge,
    fractional_kelly,
)
from config.constants import BANKROLL, ODDS_CONFIG, THRESHOLDS
from config.settings import DATABASE_PATH, ODDS_API_KEY, PROCESSED_DATA_DIR
from models.model_persistence import load_model
from pipelines.odds_orchestrator import OddsOrchestrator
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
        from datetime import timedelta

        return datetime.now() + timedelta(days=1)
    return datetime.strptime(date_str, "%Y-%m-%d")


def fetch_todays_games(target_date: datetime) -> list[dict]:
    """Fetch games for the target date via sportsipy.

    Falls back to an empty list if sportsipy is unavailable.
    """
    try:
        from pipelines.ncaab_data_fetcher import NCAABDataFetcher

        fetcher = NCAABDataFetcher()
        games = fetcher.fetch_games_by_date(target_date)
        logger.info("Fetched %d games for %s", len(games), target_date.strftime("%Y-%m-%d"))
        return games
    except Exception as e:
        logger.error("Failed to fetch games: %s", e)
        return []


def generate_predictions(
    model,
    games: list[dict],
    orchestrator: OddsOrchestrator,
    mode: str = "auto",
    min_edge: float = 0.02,
) -> pd.DataFrame:
    """Generate predictions + odds + edge calculations for each game.

    Args:
        model: Trained NCAABEloModel.
        games: List of game dicts from sportsipy.
        orchestrator: OddsOrchestrator for fetching odds.
        mode: Odds retrieval mode.
        min_edge: Minimum edge for bet recommendations.

    Returns:
        DataFrame of predictions with bet recommendations.
    """
    predictions = []

    for game in games:
        home = game.get("home_abbr", game.get("home_team", ""))
        away = game.get("away_abbr", game.get("away_team", ""))
        game_id = game.get("game_id", f"{home}_{away}")

        # Model prediction
        home_prob = model.predict_win_probability(home, away)
        spread = model.predict_spread(home, away)
        fair_home_ml = _prob_to_american(home_prob)
        fair_away_ml = _prob_to_american(1 - home_prob)

        pred = {
            "game_id": game_id,
            "home": home,
            "away": away,
            "home_prob": home_prob,
            "away_prob": 1 - home_prob,
            "predicted_spread": spread,
            "fair_home_ml": fair_home_ml,
            "fair_away_ml": fair_away_ml,
        }

        # Fetch market odds
        odds = orchestrator.fetch_odds(
            sport="ncaab",
            home=game.get("home_team", home),
            away=game.get("away_team", away),
            game_id=game_id,
            mode=mode,
        )

        if odds is not None:
            pred["sportsbook"] = odds.sportsbook
            pred["market_spread"] = odds.spread_home
            pred["spread_odds"] = odds.spread_home_odds
            pred["market_total"] = odds.total
            pred["home_ml"] = odds.moneyline_home
            pred["away_ml"] = odds.moneyline_away

            # Edge calculation on moneyline
            if odds.moneyline_home is not None:
                home_edge = calculate_edge(home_prob, odds.moneyline_home)
                away_edge = (
                    calculate_edge(1 - home_prob, odds.moneyline_away) if odds.moneyline_away else 0
                )

                pred["home_edge"] = home_edge
                pred["away_edge"] = away_edge

                # Bet recommendation
                if home_edge >= min_edge:
                    decimal_odds = american_to_decimal(odds.moneyline_home)
                    kelly = fractional_kelly(home_prob, decimal_odds)
                    stake = BANKROLL.TOTAL_BANKROLL * kelly
                    pred["rec_side"] = "HOME"
                    pred["rec_odds"] = odds.moneyline_home
                    pred["rec_kelly"] = kelly
                    pred["rec_stake"] = stake
                elif away_edge >= min_edge:
                    decimal_odds = american_to_decimal(odds.moneyline_away)
                    kelly = fractional_kelly(1 - home_prob, decimal_odds)
                    stake = BANKROLL.TOTAL_BANKROLL * kelly
                    pred["rec_side"] = "AWAY"
                    pred["rec_odds"] = odds.moneyline_away
                    pred["rec_kelly"] = kelly
                    pred["rec_stake"] = stake
        else:
            pred["sportsbook"] = None
            pred["market_spread"] = None
            pred["home_ml"] = None
            pred["away_ml"] = None

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
    print(f"\n{'=' * 90}")
    print("DAILY PREDICTIONS — NCAAB")
    print(f"{'=' * 90}")

    if df.empty:
        print("No games found for today.")
        return

    # All games
    print(f"\n{'Game':<30s} {'Spread':>7s} {'Home%':>6s} {'HML':>6s} {'AML':>6s} {'Edge':>6s}")
    print("-" * 70)
    for _, row in df.iterrows():
        matchup = f"{row['away']} @ {row['home']}"
        spread = f"{row['predicted_spread']:+.1f}" if row.get("predicted_spread") else "?"
        home_pct = f"{row['home_prob']:.0%}"
        hml = str(row.get("home_ml", "?"))
        aml = str(row.get("away_ml", "?"))
        edge = ""
        if "home_edge" in row and pd.notna(row.get("home_edge")):
            best_edge = max(row.get("home_edge", 0), row.get("away_edge", 0))
            edge = f"{best_edge:+.1%}"
        print(f"{matchup:<30s} {spread:>7s} {home_pct:>6s} {hml:>6s} {aml:>6s} {edge:>6s}")

    # Bet recommendations
    recs = df[df.get("rec_side", pd.Series(dtype=str)).notna()].copy()
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
    parser.add_argument("--min-edge", type=float, default=THRESHOLDS.MIN_EDGE_SPREAD)
    args = parser.parse_args()

    target_date = parse_date(args.date)
    logger.info(
        "Generating predictions for %s (mode=%s)", target_date.strftime("%Y-%m-%d"), args.mode
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

    # Fetch games
    games = fetch_todays_games(target_date)
    if not games:
        print("No games found. Try a different date or check sportsipy connectivity.")
        return

    # Generate predictions
    predictions = generate_predictions(
        model=model,
        games=games,
        orchestrator=orchestrator,
        mode=args.mode,
        min_edge=args.min_edge,
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
