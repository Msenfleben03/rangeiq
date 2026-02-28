"""Fetch ESPN pre-game win probabilities for backtest divergence analysis.

Reads game IDs from backtest parquet files (2023-2025), fetches ESPN's
pre-game homeWinPercentage from the summary API's winprobability array,
and saves results to a parquet file with checkpoint/resume support.

Usage:
    python scripts/fetch_espn_divergence.py --dry-run
    python scripts/fetch_espn_divergence.py --seasons 2023 2024 2025
    python scripts/fetch_espn_divergence.py --reset
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ── Paths ───────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BACKTESTS_DIR = DATA_DIR / "backtests"
OUTPUT_DIR = DATA_DIR / "espn_divergence"
CHECKPOINT_PATH = OUTPUT_DIR / "checkpoint.txt"
OUTPUT_PATH = OUTPUT_DIR / "espn_pregame_probs.parquet"

ESPN_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary"
)


# ── Core functions ──────────────────────────────────────────────────


def fetch_single_game_prob(game_id: str) -> dict:
    """Fetch ESPN pre-game home win probability for a single game.

    Uses the summary API's winprobability[0].homeWinPercentage field,
    which is the pre-game probability and remains available for completed games.

    Args:
        game_id: ESPN event ID.

    Returns:
        Dict with game_id, espn_home_prob (float or None), fetch_success (bool).
    """
    result = {"game_id": game_id, "espn_home_prob": None, "fetch_success": False}

    try:
        resp = requests.get(
            ESPN_SUMMARY_URL,
            params={"event": game_id},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        result["fetch_success"] = True

        wp = data.get("winprobability", [])
        if wp and "homeWinPercentage" in wp[0]:
            result["espn_home_prob"] = wp[0]["homeWinPercentage"]

    except requests.RequestException as exc:
        logger.warning("API error for game %s: %s", game_id, exc)

    return result


def load_checkpoint(path: Path) -> set[str]:
    """Load previously fetched game IDs from checkpoint file.

    Args:
        path: Path to checkpoint text file.

    Returns:
        Set of already-fetched game IDs.
    """
    if not path.exists():
        return set()

    with open(path, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def save_checkpoint(path: Path, ids: set[str]) -> None:
    """Save checkpoint of fetched game IDs.

    Args:
        path: Path to checkpoint text file.
        ids: Set of fetched game IDs.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        for gid in sorted(ids):
            f.write(f"{gid}\n")


def load_backtest_game_ids(backtests_dir: Path, seasons: list[int]) -> list[dict]:
    """Load unique game IDs from backtest parquet files.

    Args:
        backtests_dir: Directory containing ncaab_elo_backtest_{season}.parquet.
        seasons: List of season years to load.

    Returns:
        List of dicts with game_id and season, deduplicated by game_id.
    """
    if not backtests_dir.exists():
        return []

    seen = set()
    results = []

    for season in seasons:
        path = backtests_dir / f"ncaab_elo_backtest_{season}.parquet"
        if not path.exists():
            logger.warning("Backtest file not found: %s", path)
            continue

        df = pd.read_parquet(path, columns=["game_id"])
        for gid in df["game_id"].unique():
            gid_str = str(gid)
            if gid_str not in seen:
                seen.add(gid_str)
                results.append({"game_id": gid_str, "season": season})

    return results


def fetch_all(
    backtests_dir: Path,
    seasons: list[int],
    output_path: Path,
    checkpoint_path: Path,
    delay: float = 0.5,
    dry_run: bool = False,
) -> pd.DataFrame | None:
    """Fetch ESPN pre-game probabilities for all backtest games.

    Args:
        backtests_dir: Directory containing backtest parquets.
        seasons: Season years to process.
        output_path: Path for output parquet.
        checkpoint_path: Path for checkpoint file.
        delay: Seconds between API calls.
        dry_run: If True, only print counts without fetching.

    Returns:
        DataFrame with results, or None if dry_run.
    """
    game_records = load_backtest_game_ids(backtests_dir, seasons)
    if not game_records:
        logger.error("No backtest game IDs found")
        return None

    done = load_checkpoint(checkpoint_path)
    remaining = [r for r in game_records if r["game_id"] not in done]

    logger.info(
        "Total games: %d | Already fetched: %d | Remaining: %d",
        len(game_records),
        len(done),
        len(remaining),
    )

    if dry_run:
        print(f"Would fetch {len(remaining)} games ({len(done)} already checkpointed)")
        return None

    # Load existing results if resuming
    all_results = []
    if output_path.exists():
        existing = pd.read_parquet(output_path)
        all_results = existing.to_dict("records")
        logger.info("Loaded %d existing results from parquet", len(all_results))

    try:
        for i, record in enumerate(remaining):
            result = fetch_single_game_prob(record["game_id"])
            result["season"] = record["season"]
            all_results.append(result)
            done.add(record["game_id"])

            # Progress + checkpoint every 50 games
            if (i + 1) % 50 == 0 or (i + 1) == len(remaining):
                save_checkpoint(checkpoint_path, done)
                df = pd.DataFrame(all_results)
                df.to_parquet(output_path, index=False)
                success_count = df["fetch_success"].sum()
                logger.info(
                    "Progress: %d/%d fetched | %d successful | saved",
                    i + 1,
                    len(remaining),
                    success_count,
                )

            if i < len(remaining) - 1:
                time.sleep(delay)

    except KeyboardInterrupt:
        logger.info("Interrupted — saving checkpoint")
        save_checkpoint(checkpoint_path, done)
        if all_results:
            df = pd.DataFrame(all_results)
            df.to_parquet(output_path, index=False)
            logger.info("Saved %d results before exit", len(df))
        sys.exit(1)

    df = pd.DataFrame(all_results)
    df.to_parquet(output_path, index=False)
    success_rate = df["fetch_success"].mean() if len(df) > 0 else 0
    wp_rate = df["espn_home_prob"].notna().mean() if len(df) > 0 else 0
    logger.info(
        "Done: %d games | fetch success: %.1f%% | ESPN prob coverage: %.1f%%",
        len(df),
        success_rate * 100,
        wp_rate * 100,
    )
    return df


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch ESPN pre-game probabilities for divergence analysis"
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=[2023, 2024, 2025],
        help="Seasons to fetch (default: 2023 2024 2025)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print counts without fetching",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset checkpoint and start fresh",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds between API calls (default: 0.5)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.reset and CHECKPOINT_PATH.exists():
        CHECKPOINT_PATH.unlink()
        logger.info("Checkpoint reset")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fetch_all(
        backtests_dir=BACKTESTS_DIR,
        seasons=args.seasons,
        output_path=OUTPUT_PATH,
        checkpoint_path=CHECKPOINT_PATH,
        delay=args.delay,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
