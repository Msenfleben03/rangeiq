"""Analyze divergence between model and ESPN pre-game probabilities.

Joins backtest results with ESPN pre-game probabilities, computes divergence
metrics, and produces bucketed performance analysis to inform whether
high-divergence bets should be suppressed or down-weighted.

Usage:
    python scripts/analyze_divergence.py
    python scripts/analyze_divergence.py --save-enriched
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Paths ───────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BACKTESTS_DIR = DATA_DIR / "backtests"
ESPN_PATH = DATA_DIR / "espn_divergence" / "espn_pregame_probs.parquet"
ENRICHED_PATH = DATA_DIR / "espn_divergence" / "backtest_with_divergence.parquet"

BUCKET_ORDER = ["0-5pp", "5-10pp", "10-15pp", "15-20pp", "20pp+"]


# ── Core functions ──────────────────────────────────────────────────


def compute_divergence(row: dict, espn_home_prob: float | None) -> dict:
    """Compute divergence between model and ESPN home win probability.

    Args:
        row: Dict with bet_side and model_prob (P(bet side wins)).
        espn_home_prob: ESPN's pre-game home win probability.

    Returns:
        Dict with home_prob, divergence, abs_divergence, direction.
    """
    # Reconstruct home probability from bet perspective
    if row["bet_side"] == "home":
        home_prob = row["model_prob"]
    else:
        home_prob = 1.0 - row["model_prob"]

    if espn_home_prob is None or np.isnan(espn_home_prob):
        return {
            "home_prob": home_prob,
            "divergence": np.nan,
            "abs_divergence": np.nan,
            "direction": None,
        }

    divergence = home_prob - espn_home_prob
    abs_divergence = abs(divergence)
    direction = "model_higher" if divergence > 0 else "model_lower"

    return {
        "home_prob": home_prob,
        "divergence": divergence,
        "abs_divergence": abs_divergence,
        "direction": direction,
    }


def assign_bucket(abs_div: float) -> str:
    """Assign a divergence bucket based on absolute divergence.

    Boundaries: [0,5pp), [5pp,10pp), [10pp,15pp), [15pp,20pp), [20pp,+inf).

    Args:
        abs_div: Absolute divergence as a proportion (e.g. 0.05 = 5pp).

    Returns:
        Bucket label string.
    """
    if abs_div < 0.05:
        return "0-5pp"
    if abs_div < 0.10:
        return "5-10pp"
    if abs_div < 0.15:
        return "10-15pp"
    if abs_div < 0.20:
        return "15-20pp"
    return "20pp+"


def load_and_merge(
    backtests_dir: Path,
    espn_path: Path,
    seasons: list[int],
) -> pd.DataFrame:
    """Load backtest results and join with ESPN probabilities.

    Args:
        backtests_dir: Directory with ncaab_elo_backtest_{season}.parquet.
        espn_path: Path to espn_pregame_probs.parquet.
        seasons: List of season years to load.

    Returns:
        Merged DataFrame with divergence columns added.
    """
    dfs = []
    for season in seasons:
        path = backtests_dir / f"ncaab_elo_backtest_{season}.parquet"
        if path.exists():
            df = pd.read_parquet(path)
            df["season"] = season
            dfs.append(df)
        else:
            logger.warning("Missing backtest: %s", path)

    if not dfs:
        raise FileNotFoundError("No backtest files found")

    backtest = pd.concat(dfs, ignore_index=True)
    backtest["game_id"] = backtest["game_id"].astype(str)

    espn = pd.read_parquet(espn_path)
    espn["game_id"] = espn["game_id"].astype(str)
    espn_lookup = espn.set_index("game_id")["espn_home_prob"].to_dict()

    # Compute divergence for each bet
    div_records = []
    for _, row in backtest.iterrows():
        espn_prob = espn_lookup.get(str(row["game_id"]))
        div_result = compute_divergence(row.to_dict(), espn_prob)
        div_records.append(div_result)

    div_df = pd.DataFrame(div_records)
    merged = pd.concat([backtest.reset_index(drop=True), div_df], axis=1)

    # Assign buckets
    merged["divergence_bucket"] = merged["abs_divergence"].apply(
        lambda x: assign_bucket(x) if not np.isnan(x) else None
    )

    return merged


def analyze_buckets(df: pd.DataFrame) -> pd.DataFrame:
    """Compute performance metrics grouped by divergence bucket.

    Args:
        df: DataFrame with result, profit_loss, stake, clv, edge,
            abs_divergence, divergence_bucket columns.

    Returns:
        DataFrame with one row per bucket: N, win_rate, roi, mean_clv,
        median_clv, mean_edge.
    """
    rows = []
    for bucket in BUCKET_ORDER:
        subset = df[df["divergence_bucket"] == bucket]
        if len(subset) == 0:
            continue

        n = len(subset)
        wins = (subset["result"] == "win").sum()
        total_pnl = subset["profit_loss"].sum()
        total_stake = subset["stake"].sum()

        rows.append(
            {
                "bucket": bucket,
                "n": n,
                "win_rate": wins / n,
                "roi": total_pnl / total_stake if total_stake > 0 else 0,
                "mean_clv": subset["clv"].mean(),
                "median_clv": subset["clv"].median(),
                "mean_edge": subset["edge"].mean(),
            }
        )

    return pd.DataFrame(rows)


def analyze_direction(df: pd.DataFrame) -> pd.DataFrame:
    """Compute performance metrics grouped by direction and bucket.

    Args:
        df: Merged DataFrame with direction and divergence_bucket columns.

    Returns:
        DataFrame with metrics per direction+bucket combination.
    """
    valid = df.dropna(subset=["direction"])
    rows = []

    for direction in ["model_higher", "model_lower"]:
        for bucket in BUCKET_ORDER:
            subset = valid[
                (valid["direction"] == direction) & (valid["divergence_bucket"] == bucket)
            ]
            if len(subset) == 0:
                continue

            n = len(subset)
            wins = (subset["result"] == "win").sum()
            total_pnl = subset["profit_loss"].sum()
            total_stake = subset["stake"].sum()

            rows.append(
                {
                    "direction": direction,
                    "bucket": bucket,
                    "n": n,
                    "win_rate": wins / n,
                    "roi": total_pnl / total_stake if total_stake > 0 else 0,
                    "mean_clv": subset["clv"].mean(),
                }
            )

    return pd.DataFrame(rows)


def threshold_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze ROI at different suppression thresholds.

    For each threshold, computes what ROI would result from keeping only
    bets with abs_divergence below that threshold.

    Args:
        df: Merged DataFrame with abs_divergence, profit_loss, stake columns.

    Returns:
        DataFrame with threshold, n, roi, mean_clv columns.
    """
    valid = df.dropna(subset=["abs_divergence"])
    thresholds = [1.0, 0.20, 0.15, 0.10, 0.05]  # 1.0 = keep all
    rows = []

    for thresh in thresholds:
        subset = valid[valid["abs_divergence"] < thresh] if thresh < 1.0 else valid
        if len(subset) == 0:
            continue

        total_pnl = subset["profit_loss"].sum()
        total_stake = subset["stake"].sum()
        label = "Keep all" if thresh >= 1.0 else f"Drop >{int(thresh * 100)}pp"

        rows.append(
            {
                "threshold": label,
                "n": len(subset),
                "roi": total_pnl / total_stake if total_stake > 0 else 0,
                "mean_clv": subset["clv"].mean(),
                "win_rate": (subset["result"] == "win").mean(),
            }
        )

    return pd.DataFrame(rows)


def print_report(
    bucket_df: pd.DataFrame,
    direction_df: pd.DataFrame,
    threshold_df: pd.DataFrame,
    total_bets: int,
    matched_bets: int,
) -> None:
    """Print formatted divergence analysis report.

    Args:
        bucket_df: Bucket analysis results.
        direction_df: Direction analysis results.
        threshold_df: Threshold analysis results.
        total_bets: Total backtest bets.
        matched_bets: Bets with ESPN data.
    """
    print("=" * 68)
    print("DIVERGENCE ANALYSIS — NCAAB Backtests (2023-2025)")
    print("=" * 68)
    print(
        f"Total bets: {total_bets:,} | With ESPN data: {matched_bets:,} "
        f"| Coverage: {matched_bets / total_bets:.1%}"
    )
    print()

    print("PERFORMANCE BY DIVERGENCE BUCKET")
    print("-" * 68)
    print(f"{'Bucket':<13} {'N':>5} {'Win%':>7} {'ROI':>8} {'Avg CLV':>9} {'Avg Edge':>9}")
    for _, row in bucket_df.iterrows():
        print(
            f"{row['bucket']:<13} {row['n']:>5} "
            f"{row['win_rate']:>6.1%} {row['roi']:>+7.1%} "
            f"{row['mean_clv']:>+8.2%} {row['mean_edge']:>8.1%}"
        )
    print()

    print("DIRECTION SPLIT")
    print("-" * 68)
    print(f"{'Direction':<14} {'Bucket':<10} {'N':>5} {'Win%':>7} {'ROI':>8} {'Avg CLV':>9}")
    for _, row in direction_df.iterrows():
        print(
            f"{row['direction']:<14} {row['bucket']:<10} {row['n']:>5} "
            f"{row['win_rate']:>6.1%} {row['roi']:>+7.1%} "
            f"{row['mean_clv']:>+8.2%}"
        )
    print()

    print("THRESHOLD ANALYSIS")
    print("-" * 68)
    print(f"{'Action':<18} {'N':>6} {'Win%':>7} {'ROI':>8} {'Avg CLV':>9}")
    for _, row in threshold_df.iterrows():
        print(
            f"{row['threshold']:<18} {row['n']:>6} "
            f"{row['win_rate']:>6.1%} {row['roi']:>+7.1%} "
            f"{row['mean_clv']:>+8.2%}"
        )
    print()


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Analyze divergence between model and ESPN probabilities"
    )
    parser.add_argument(
        "--save-enriched",
        action="store_true",
        help="Save enriched backtest+divergence parquet",
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=[2023, 2024, 2025],
        help="Seasons to analyze (default: 2023 2024 2025)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if not ESPN_PATH.exists():
        logger.error("ESPN data not found: %s", ESPN_PATH)
        logger.error("Run scripts/fetch_espn_divergence.py first")
        return

    merged = load_and_merge(BACKTESTS_DIR, ESPN_PATH, args.seasons)
    valid = merged.dropna(subset=["divergence"])

    bucket_df = analyze_buckets(valid)
    direction_df = analyze_direction(valid)
    threshold_df = threshold_analysis(valid)

    print_report(
        bucket_df=bucket_df,
        direction_df=direction_df,
        threshold_df=threshold_df,
        total_bets=len(merged),
        matched_bets=len(valid),
    )

    if args.save_enriched:
        ENRICHED_PATH.parent.mkdir(parents=True, exist_ok=True)
        merged.to_parquet(ENRICHED_PATH, index=False)
        logger.info("Saved enriched data: %s (%d rows)", ENRICHED_PATH, len(merged))


if __name__ == "__main__":
    main()
