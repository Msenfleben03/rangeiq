"""Walk-forward backtesting for MLB Poisson model.

Usage:
    python scripts/mlb_backtest.py                    # Train 2023-2024, test 2025
    python scripts/mlb_backtest.py --test-season 2024 # Train 2023, test 2024
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.sport_specific.mlb.poisson_model import PoissonModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "mlb_data.db"


def load_games(db_path: Path) -> pd.DataFrame:
    """Load all final games from the database."""
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql_query(
        "SELECT game_pk, game_date, season, home_team_id, away_team_id, "
        "home_score, away_score FROM games WHERE status = 'final'",
        conn,
    )
    conn.close()
    return df


def run_backtest(games: pd.DataFrame, test_season: int) -> pd.DataFrame:
    """Run walk-forward: train on seasons < test_season, predict test_season."""
    train = games[games["season"] < test_season]
    test = games[games["season"] == test_season].copy()

    if len(train) == 0:
        logger.error("No training data for test season %d", test_season)
        return pd.DataFrame()

    if len(test) == 0:
        logger.error("No test data for season %d", test_season)
        return pd.DataFrame()

    logger.info(
        "Training on %d games (seasons %s), testing on %d (%d)",
        len(train),
        sorted(train["season"].unique()),
        len(test),
        test_season,
    )

    model = PoissonModel()
    model.fit(train)

    results = []
    skipped_ties = 0
    skipped_unknown = 0
    for _, row in test.iterrows():
        if row["home_score"] == row["away_score"]:
            skipped_ties += 1
            continue

        home_id = int(row["home_team_id"])
        away_id = int(row["away_team_id"])

        # Skip games with teams not seen in training data
        if home_id not in model.team_ratings or away_id not in model.team_ratings:
            skipped_unknown += 1
            continue

        pred = model.predict(home_id, away_id)
        home_won = row["home_score"] > row["away_score"]

        results.append(
            {
                "game_pk": row["game_pk"],
                "game_date": row["game_date"],
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_score": row["home_score"],
                "away_score": row["away_score"],
                "pred_home_prob": pred["moneyline_home"],
                "pred_lambda_home": pred["lambda_home"],
                "pred_lambda_away": pred["lambda_away"],
                "home_won": home_won,
                "correct": (pred["moneyline_home"] > 0.5) == home_won,
            }
        )

    if skipped_ties > 0:
        logger.info("Skipped %d tied games", skipped_ties)
    if skipped_unknown > 0:
        logger.warning("Skipped %d games with unknown teams", skipped_unknown)

    return pd.DataFrame(results)


def print_report(results: pd.DataFrame, test_season: int) -> None:
    """Print backtest summary."""
    if results.empty:
        print(f"No results for season {test_season}")
        return

    n = len(results)
    correct = results["correct"].sum()
    accuracy = correct / n

    # Log loss
    eps = 1e-10
    probs = results["pred_home_prob"].clip(eps, 1 - eps)
    actuals = results["home_won"].astype(float)
    log_loss = -(actuals * np.log(probs) + (1 - actuals) * np.log(1 - probs)).mean()

    # Calibration
    results = results.copy()
    results["prob_bin"] = pd.cut(results["pred_home_prob"], bins=10)
    cal = results.groupby("prob_bin", observed=True).agg(
        pred_avg=("pred_home_prob", "mean"),
        actual_avg=("home_won", "mean"),
        count=("home_won", "count"),
    )

    print(f"\n{'=' * 60}")
    print(f"MLB Poisson Model v1 -- Backtest {test_season}")
    print(f"{'=' * 60}")
    print(f"Games:      {n}")
    print(f"Accuracy:   {accuracy:.1%} ({correct}/{n})")
    print(f"Log Loss:   {log_loss:.4f}")
    print("\nCalibration:")
    print(f"{'Predicted':>12} {'Actual':>10} {'Count':>8}")
    print(f"{'-' * 32}")
    for _, row in cal.iterrows():
        print(f"{row['pred_avg']:>12.1%} {row['actual_avg']:>10.1%} {int(row['count']):>8}")
    print(f"{'=' * 60}")


def main() -> None:
    """CLI entry point for MLB walk-forward backtest."""
    parser = argparse.ArgumentParser(description="MLB Poisson model walk-forward backtest")
    parser.add_argument(
        "--test-season",
        type=int,
        default=2025,
        help="Season to test on (trains on all prior)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(DB_PATH),
        help="Path to mlb_data.db",
    )
    args = parser.parse_args()

    games = load_games(Path(args.db_path))
    logger.info(
        "Loaded %d games across seasons %s",
        len(games),
        sorted(games["season"].unique()),
    )

    results = run_backtest(games, args.test_season)
    print_report(results, args.test_season)

    # Save results
    out_dir = PROJECT_ROOT / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"mlb_backtest_{args.test_season}.parquet"
    results.to_parquet(out_path, index=False)
    logger.info("Saved results to %s", out_path)


if __name__ == "__main__":
    main()
