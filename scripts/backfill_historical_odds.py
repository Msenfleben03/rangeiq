"""Backfill Historical Odds from ESPN Core API.

Reads existing season parquet files, extracts ESPN event IDs, fetches
odds from the Core API (open/close/current), and saves to parquet.

Supports:
    - Resume from last checkpoint (skips already-fetched events)
    - Per-season output files
    - Progress tracking with ETA
    - Configurable rate limiting

Usage:
    # Backfill all seasons
    python scripts/backfill_historical_odds.py

    # Backfill specific season
    python scripts/backfill_historical_odds.py --season 2025

    # Resume interrupted backfill
    python scripts/backfill_historical_odds.py --season 2025 --resume

    # Dry run (show what would be fetched)
    python scripts/backfill_historical_odds.py --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from pipelines.espn_core_odds_provider import (  # noqa: E402
    ESPNCoreOddsFetcher,
    OddsSnapshot,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RAW_DATA_DIR = Path("data/raw/ncaab")
ODDS_OUTPUT_DIR = Path("data/odds")
CHECKPOINT_DIR = Path("data/odds/checkpoints")

SEASONS = [2020, 2021, 2022, 2023, 2024, 2025]
REQUESTS_PER_SECOND = 2.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_event_ids(season: int) -> list[str]:
    """Load unique event IDs from a season parquet file.

    Args:
        season: Season year.

    Returns:
        Sorted list of unique event IDs.
    """
    parquet_path = RAW_DATA_DIR / f"ncaab_games_{season}.parquet"
    if not parquet_path.exists():
        logger.warning("Season file not found: %s", parquet_path)
        return []

    df = pd.read_parquet(parquet_path)
    ids = sorted(df["game_id"].unique().tolist())
    logger.info("Season %d: %d unique event IDs", season, len(ids))
    return ids


def load_checkpoint(season: int) -> set[str]:
    """Load previously fetched event IDs from checkpoint.

    Args:
        season: Season year.

    Returns:
        Set of already-fetched event IDs.
    """
    checkpoint_path = CHECKPOINT_DIR / f"odds_checkpoint_{season}.txt"
    if not checkpoint_path.exists():
        return set()

    with open(checkpoint_path, encoding="utf-8") as f:
        ids = {line.strip() for line in f if line.strip()}

    logger.info("Checkpoint: %d events already fetched for %d", len(ids), season)
    return ids


def save_checkpoint(season: int, event_ids: set[str]) -> None:
    """Save checkpoint of fetched event IDs.

    Args:
        season: Season year.
        event_ids: Set of fetched event IDs.
    """
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_path = CHECKPOINT_DIR / f"odds_checkpoint_{season}.txt"

    with open(checkpoint_path, "w", encoding="utf-8") as f:
        for eid in sorted(event_ids):
            f.write(f"{eid}\n")


def snapshots_to_dataframe(
    results: dict[str, list[OddsSnapshot]],
) -> pd.DataFrame:
    """Convert batch results to a flat DataFrame.

    Args:
        results: Dict mapping event_id to list of OddsSnapshot.

    Returns:
        DataFrame with one row per (event_id, provider).
    """
    rows = []
    for snapshots in results.values():
        for snap in snapshots:
            rows.append(snap.to_dict())

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def save_odds_parquet(
    df: pd.DataFrame,
    season: int,
    append: bool = True,
) -> Path:
    """Save odds DataFrame to parquet, optionally appending to existing.

    Args:
        df: Odds DataFrame.
        season: Season year.
        append: If True, merge with existing file.

    Returns:
        Path to saved file.
    """
    ODDS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ODDS_OUTPUT_DIR / f"ncaab_odds_{season}.parquet"

    if append and output_path.exists():
        existing = pd.read_parquet(output_path)
        df = pd.concat([existing, df], ignore_index=True)
        df = df.drop_duplicates(
            subset=["game_id", "provider_id"],
            keep="last",
        )

    df.to_parquet(output_path, index=False)
    logger.info("Saved %d odds records to %s", len(df), output_path)
    return output_path


# ---------------------------------------------------------------------------
# Main backfill logic
# ---------------------------------------------------------------------------


def backfill_season(
    season: int,
    resume: bool = True,
    batch_size: int = 50,
    requests_per_second: float = REQUESTS_PER_SECOND,
) -> pd.DataFrame:
    """Backfill odds for an entire season.

    Args:
        season: Season year.
        resume: If True, skip already-fetched events.
        batch_size: Save checkpoint every N events.

    Returns:
        DataFrame of all fetched odds.
    """
    event_ids = load_event_ids(season)
    if not event_ids:
        return pd.DataFrame()

    # Resume support
    fetched_ids: set[str] = set()
    if resume:
        fetched_ids = load_checkpoint(season)

    remaining = [eid for eid in event_ids if eid not in fetched_ids]
    logger.info(
        "Season %d: %d total events, %d already fetched, %d remaining",
        season,
        len(event_ids),
        len(fetched_ids),
        len(remaining),
    )

    if not remaining:
        logger.info("Season %d: all events already fetched!", season)
        output_path = ODDS_OUTPUT_DIR / f"ncaab_odds_{season}.parquet"
        if output_path.exists():
            return pd.read_parquet(output_path)
        return pd.DataFrame()

    fetcher = ESPNCoreOddsFetcher(
        sport="ncaab",
        requests_per_second=requests_per_second,
    )

    all_results: dict[str, list[OddsSnapshot]] = {}
    start_time = time.time()
    games_with_odds = 0
    games_without_odds = 0

    try:
        for idx, eid in enumerate(remaining):
            snapshots = fetcher.fetch_game_odds(eid)
            fetched_ids.add(eid)

            if snapshots:
                all_results[eid] = snapshots
                games_with_odds += 1
            else:
                games_without_odds += 1

            # Progress
            done = idx + 1
            if done % 25 == 0 or done == len(remaining):
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                eta = (len(remaining) - done) / rate if rate > 0 else 0
                logger.info(
                    "Season %d: %d/%d (%.0f%%) | "
                    "odds: %d | empty: %d | "
                    "%.1f evt/s | ETA: %.0fs",
                    season,
                    done,
                    len(remaining),
                    100 * done / len(remaining),
                    games_with_odds,
                    games_without_odds,
                    rate,
                    eta,
                )

            # Periodic checkpoint + save
            if done % batch_size == 0:
                save_checkpoint(season, fetched_ids)
                if all_results:
                    df_batch = snapshots_to_dataframe(all_results)
                    save_odds_parquet(df_batch, season, append=True)

    except KeyboardInterrupt:
        logger.warning("Interrupted! Saving progress...")
    finally:
        fetcher.close()
        save_checkpoint(season, fetched_ids)

    # Final save
    if all_results:
        df = snapshots_to_dataframe(all_results)
        output_path = save_odds_parquet(df, season, append=True)
        final_df = pd.read_parquet(output_path)
    else:
        output_path = ODDS_OUTPUT_DIR / f"ncaab_odds_{season}.parquet"
        final_df = pd.read_parquet(output_path) if output_path.exists() else pd.DataFrame()

    # Summary
    elapsed = time.time() - start_time
    logger.info(
        "Season %d complete: %d with odds, %d empty, %.1f seconds",
        season,
        games_with_odds,
        games_without_odds,
        elapsed,
    )

    return final_df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the historical odds backfill."""
    parser = argparse.ArgumentParser(
        description="Backfill historical NCAAB odds from ESPN Core API",
    )
    parser.add_argument(
        "--season",
        type=int,
        default=None,
        help="Specific season to backfill (default: all)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Resume from last checkpoint (default: True)",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Start fresh, ignoring checkpoints",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Save checkpoint every N events (default: 50)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be fetched without making API calls",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=REQUESTS_PER_SECOND,
        help="Requests per second (default: 2.0)",
    )

    args = parser.parse_args()
    rate = args.rate

    seasons = [args.season] if args.season else SEASONS
    resume = not args.no_resume

    if args.dry_run:
        for season in seasons:
            event_ids = load_event_ids(season)
            fetched = load_checkpoint(season) if resume else set()
            remaining = len(event_ids) - len(fetched)
            est_requests = remaining * 3  # ~3 requests per event
            est_time = est_requests / rate
            print(
                f"Season {season}: {len(event_ids)} events, "
                f"{len(fetched)} done, {remaining} remaining, "
                f"~{est_requests} requests, ~{est_time:.0f}s"
            )
        return

    total_with_odds = 0
    total_games = 0

    for season in seasons:
        logger.info("=" * 60)
        logger.info("Starting backfill for season %d", season)
        logger.info("=" * 60)

        df = backfill_season(
            season,
            resume=resume,
            batch_size=args.batch_size,
            requests_per_second=rate,
        )

        if not df.empty:
            n_games = df["game_id"].nunique()
            n_records = len(df)
            total_with_odds += n_games
            total_games += len(load_event_ids(season))
            logger.info(
                "Season %d: %d games with odds, %d total records",
                season,
                n_games,
                n_records,
            )

    logger.info("=" * 60)
    logger.info(
        "Backfill complete: %d/%d games with odds across %d seasons",
        total_with_odds,
        total_games,
        len(seasons),
    )
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
