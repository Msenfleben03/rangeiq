"""Walk-forward backtesting for MLB Poisson model.

Usage:
    python scripts/mlb_backtest.py                          # Train 2023-2024, test 2025
    python scripts/mlb_backtest.py --test-season 2024       # Train 2023, test 2024
    python scripts/mlb_backtest.py --pitcher-adj            # With pitcher adjustment
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

from config.constants import MLB_MODEL
from models.sport_specific.mlb.poisson_model import PoissonModel, compute_pitcher_adj

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "mlb_data.db"


def load_games(db_path: Path) -> pd.DataFrame:
    """Load all final games with starter IDs from the database."""
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql_query(
        "SELECT game_pk, game_date, season, home_team_id, away_team_id, "
        "home_score, away_score, home_starter_id, away_starter_id "
        "FROM games WHERE status = 'final'",
        conn,
    )
    conn.close()
    return df


def load_pitcher_stats(db_path: Path) -> dict[tuple[int, int], dict]:
    """Load pitcher season stats keyed by (player_id, season).

    Returns:
        Dict mapping (player_id, season) to {xfip, ip, games_started}.
    """
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT player_id, season, xfip, ip, games_started "
        "FROM pitcher_season_stats WHERE xfip IS NOT NULL"
    ).fetchall()
    conn.close()

    stats: dict[tuple[int, int], dict] = {}
    for player_id, season, xfip, ip, gs in rows:
        stats[(player_id, season)] = {
            "xfip": xfip,
            "ip": ip or 0.0,
            "games_started": gs or 0,
        }
    return stats


def compute_league_avg_xfip(
    pitcher_stats: dict[tuple[int, int], dict],
    season: int,
    min_gs: int = 5,
) -> float:
    """Compute IP-weighted league-average xFIP for a season.

    Args:
        pitcher_stats: Dict from load_pitcher_stats().
        season: The season to compute for.
        min_gs: Minimum games started to include in the average.

    Returns:
        Weighted average xFIP. Falls back to 4.2 if no data.
    """
    total_weighted = 0.0
    total_ip = 0.0
    for (_, s), val in pitcher_stats.items():
        if s != season:
            continue
        if val["games_started"] < min_gs:
            continue
        ip = val["ip"]
        total_weighted += val["xfip"] * ip
        total_ip += ip

    if total_ip == 0:
        return 4.2  # reasonable default
    return total_weighted / total_ip


def run_backtest(
    games: pd.DataFrame,
    test_season: int,
    pitcher_adj: bool = False,
    pitcher_stats: dict[tuple[int, int], dict] | None = None,
) -> pd.DataFrame:
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

    # Pre-compute league avg xFIP from prior season (temporal safety)
    prior_season = test_season - 1
    league_avg_xfip = 4.2
    if pitcher_adj and pitcher_stats:
        league_avg_xfip = compute_league_avg_xfip(
            pitcher_stats, prior_season, min_gs=MLB_MODEL.PITCHER_MIN_GS_FOR_LEAGUE_AVG
        )
        logger.info(
            "Pitcher adj ON: prior season %d, league avg xFIP = %.3f",
            prior_season,
            league_avg_xfip,
        )

    results = []
    skipped_ties = 0
    skipped_unknown = 0
    pitcher_found = 0
    pitcher_missing = 0

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

        # Compute pitcher adjustments
        home_padj = 1.0
        away_padj = 1.0
        game_pitcher_found = False

        if pitcher_adj and pitcher_stats:
            home_starter = row.get("home_starter_id")
            away_starter = row.get("away_starter_id")

            if home_starter and not pd.isna(home_starter):
                home_key = (int(home_starter), prior_season)
                home_ps = pitcher_stats.get(home_key)
                if home_ps:
                    home_padj = compute_pitcher_adj(
                        xfip=home_ps["xfip"],
                        league_avg_xfip=league_avg_xfip,
                        ip=home_ps["ip"],
                        stabilization_ip=MLB_MODEL.PITCHER_XFIP_STABILIZATION_IP,
                        clamp_low=MLB_MODEL.PITCHER_XFIP_CLAMP_LOW,
                        clamp_high=MLB_MODEL.PITCHER_XFIP_CLAMP_HIGH,
                    )
                    game_pitcher_found = True

            if away_starter and not pd.isna(away_starter):
                away_key = (int(away_starter), prior_season)
                away_ps = pitcher_stats.get(away_key)
                if away_ps:
                    away_padj = compute_pitcher_adj(
                        xfip=away_ps["xfip"],
                        league_avg_xfip=league_avg_xfip,
                        ip=away_ps["ip"],
                        stabilization_ip=MLB_MODEL.PITCHER_XFIP_STABILIZATION_IP,
                        clamp_low=MLB_MODEL.PITCHER_XFIP_CLAMP_LOW,
                        clamp_high=MLB_MODEL.PITCHER_XFIP_CLAMP_HIGH,
                    )
                    game_pitcher_found = True

        if game_pitcher_found:
            pitcher_found += 1
        elif pitcher_adj:
            pitcher_missing += 1

        pred = model.predict(
            home_id,
            away_id,
            home_pitcher_adj=home_padj,
            away_pitcher_adj=away_padj,
        )
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
                "home_pitcher_adj": home_padj,
                "away_pitcher_adj": away_padj,
            }
        )

    if skipped_ties > 0:
        logger.info("Skipped %d tied games", skipped_ties)
    if skipped_unknown > 0:
        logger.warning("Skipped %d games with unknown teams", skipped_unknown)
    if pitcher_adj:
        total_games = pitcher_found + pitcher_missing
        coverage = pitcher_found / total_games * 100 if total_games > 0 else 0
        logger.info("Pitcher coverage: %d/%d (%.1f%%)", pitcher_found, total_games, coverage)

    return pd.DataFrame(results)


def print_report(results: pd.DataFrame, test_season: int, pitcher_adj: bool = False) -> None:
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

    model_label = "v1+pitcher" if pitcher_adj else "v1"
    print(f"\n{'=' * 60}")
    print(f"MLB Poisson Model {model_label} -- Backtest {test_season}")
    print(f"{'=' * 60}")
    print(f"Games:      {n}")
    print(f"Accuracy:   {accuracy:.1%} ({correct}/{n})")
    print(f"Log Loss:   {log_loss:.4f}")

    # Pitcher coverage stats
    if pitcher_adj and "home_pitcher_adj" in results.columns:
        has_adj = (results["home_pitcher_adj"] != 1.0) | (results["away_pitcher_adj"] != 1.0)
        n_adj = has_adj.sum()
        print(f"\nPitcher Adj: {n_adj}/{n} games ({n_adj / n:.1%} coverage)")
        if n_adj > 0:
            adj_vals = pd.concat([results["home_pitcher_adj"], results["away_pitcher_adj"]])
            adj_vals = adj_vals[adj_vals != 1.0]
            print(
                f"  Adj range: [{adj_vals.min():.3f}, {adj_vals.max():.3f}], "
                f"mean={adj_vals.mean():.3f}"
            )

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
    parser.add_argument(
        "--pitcher-adj",
        action="store_true",
        default=False,
        help="Enable starting pitcher xFIP adjustment",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    games = load_games(db_path)
    logger.info(
        "Loaded %d games across seasons %s",
        len(games),
        sorted(games["season"].unique()),
    )

    # Load pitcher stats if needed
    pitcher_stats = None
    if args.pitcher_adj:
        pitcher_stats = load_pitcher_stats(db_path)
        logger.info("Loaded %d pitcher-season stat rows", len(pitcher_stats))

    results = run_backtest(
        games,
        args.test_season,
        pitcher_adj=args.pitcher_adj,
        pitcher_stats=pitcher_stats,
    )
    print_report(results, args.test_season, pitcher_adj=args.pitcher_adj)

    # Save results
    out_dir = PROJECT_ROOT / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = "_pitcher" if args.pitcher_adj else ""
    out_path = out_dir / f"mlb_backtest_{args.test_season}{suffix}.parquet"
    results.to_parquet(out_path, index=False)
    logger.info("Saved results to %s", out_path)


if __name__ == "__main__":
    main()
