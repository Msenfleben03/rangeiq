"""Fetch Historical NCAAB Data.

Downloads 5 seasons (2020-2025) of NCAAB game data via sportsipy.
Supports checkpoint/resume — skips seasons where parquet already exists.

Usage:
    python scripts/fetch_historical_data.py
    python scripts/fetch_historical_data.py --start 2022 --end 2025
    python scripts/fetch_historical_data.py --force  # Re-download all
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from config.settings import RAW_DATA_DIR, NCAAB_SEASONS_START, NCAAB_SEASONS_END
from pipelines.ncaab_data_fetcher import NCAABDataFetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Expected game counts per season (approximate, for validation)
EXPECTED_GAMES_MIN = 4000
EXPECTED_GAMES_MAX = 8000


def get_existing_seasons(output_dir: Path) -> set[int]:
    """Find seasons that already have parquet files on disk.

    Args:
        output_dir: Directory containing parquet files.

    Returns:
        Set of season years already downloaded.
    """
    existing = set()
    for f in output_dir.glob("ncaab_games_*.parquet"):
        name = f.stem  # ncaab_games_2024
        parts = name.split("_")
        if len(parts) == 3 and parts[2].isdigit():
            year = int(parts[2])
            # Validate the file isn't empty/corrupt
            try:
                df = pd.read_parquet(f)
                if len(df) >= EXPECTED_GAMES_MIN:
                    existing.add(year)
                    logger.info("Found valid cached data for %d (%d games)", year, len(df))
                else:
                    logger.warning(
                        "Cached %d has only %d games (expected >= %d), will re-fetch",
                        year,
                        len(df),
                        EXPECTED_GAMES_MIN,
                    )
            except Exception as e:
                logger.warning("Corrupt parquet for %d: %s", year, e)
    return existing


def validate_season_data(df: pd.DataFrame, season: int) -> bool:
    """Validate that fetched season data looks reasonable.

    Args:
        df: DataFrame of game results.
        season: Season year.

    Returns:
        True if data passes validation checks.
    """
    if df.empty:
        logger.error("Season %d: No data returned", season)
        return False

    n_games = len(df)
    if n_games < EXPECTED_GAMES_MIN:
        logger.warning(
            "Season %d: Only %d games (expected >= %d)",
            season,
            n_games,
            EXPECTED_GAMES_MIN,
        )
        return False

    if n_games > EXPECTED_GAMES_MAX:
        logger.warning(
            "Season %d: %d games seems high (expected <= %d)",
            season,
            n_games,
            EXPECTED_GAMES_MAX,
        )

    # Check for required columns
    required_cols = {"game_id", "team_id", "opponent_id", "points_for", "points_against"}
    missing = required_cols - set(df.columns)
    if missing:
        logger.error("Season %d: Missing columns: %s", season, missing)
        return False

    # Check for null scores
    null_scores = df["points_for"].isna().sum() + df["points_against"].isna().sum()
    if null_scores > 0:
        logger.warning("Season %d: %d null score values", season, null_scores)

    logger.info("Season %d: Validated OK (%d games)", season, n_games)
    return True


def fetch_all_seasons(
    start: int,
    end: int,
    force: bool = False,
    delay: float = 1.0,
) -> dict[int, int]:
    """Fetch multiple seasons with checkpoint/resume support.

    Args:
        start: First season year.
        end: Last season year (inclusive).
        force: If True, re-download even if parquet exists.
        delay: Seconds between requests for rate limiting.

    Returns:
        Dictionary mapping season year to game count.
    """
    output_dir = RAW_DATA_DIR / "ncaab"
    output_dir.mkdir(parents=True, exist_ok=True)

    fetcher = NCAABDataFetcher(output_dir=str(output_dir))

    # Check for existing data (checkpoint/resume)
    if force:
        existing = set()
        logger.info("Force mode: will re-download all seasons")
    else:
        existing = get_existing_seasons(output_dir)

    results: dict[int, int] = {}
    seasons = list(range(start, end + 1))
    skipped = [s for s in seasons if s in existing]
    to_fetch = [s for s in seasons if s not in existing]

    if skipped:
        logger.info("Skipping cached seasons: %s", skipped)
        for s in skipped:
            df = pd.read_parquet(output_dir / f"ncaab_games_{s}.parquet")
            results[s] = len(df)

    if not to_fetch:
        logger.info("All seasons already cached. Use --force to re-download.")
        return results

    logger.info("Fetching seasons: %s", to_fetch)
    total_start = time.time()

    for i, season in enumerate(to_fetch):
        season_start = time.time()
        logger.info(
            "\n%s\nFetching season %d (%d/%d)\n%s",
            "=" * 60,
            season,
            i + 1,
            len(to_fetch),
            "=" * 60,
        )

        try:
            df = fetcher.fetch_season_data(season, delay=delay)

            if validate_season_data(df, season):
                results[season] = len(df)
                logger.info(
                    "Season %d complete: %d games (%.1f min)",
                    season,
                    len(df),
                    (time.time() - season_start) / 60,
                )
            else:
                results[season] = 0
                logger.error("Season %d failed validation", season)

        except KeyboardInterrupt:
            logger.info("Interrupted. Progress saved for completed seasons.")
            break
        except Exception as e:
            logger.error("Season %d failed: %s", season, e)
            results[season] = 0

    total_time = (time.time() - total_start) / 60
    logger.info(
        "\nFetch complete in %.1f minutes. Results: %s",
        total_time,
        {k: f"{v} games" for k, v in sorted(results.items())},
    )
    return results


def main() -> None:
    """Entry point for historical data fetching."""
    parser = argparse.ArgumentParser(description="Fetch historical NCAAB data")
    parser.add_argument(
        "--start",
        type=int,
        default=NCAAB_SEASONS_START,
        help=f"First season year (default: {NCAAB_SEASONS_START})",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=NCAAB_SEASONS_END,
        help=f"Last season year (default: {NCAAB_SEASONS_END})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if parquet files exist",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.0,
        help="Seconds between requests (default: 1.0)",
    )
    args = parser.parse_args()

    logger.info(
        "Fetching NCAAB data: seasons %d-%d (delay=%.1fs, force=%s)",
        args.start,
        args.end,
        args.delay,
        args.force,
    )

    results = fetch_all_seasons(
        start=args.start,
        end=args.end,
        force=args.force,
        delay=args.delay,
    )

    # Summary
    total_games = sum(results.values())
    successful = sum(1 for v in results.values() if v > 0)
    failed = sum(1 for v in results.values() if v == 0)

    print(f"\n{'=' * 60}")
    print("FETCH SUMMARY")
    print(f"{'=' * 60}")
    print(f"Seasons requested: {args.start}-{args.end}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Total games: {total_games:,}")
    for season in sorted(results):
        status = f"{results[season]:,} games" if results[season] > 0 else "FAILED"
        print(f"  {season}: {status}")


if __name__ == "__main__":
    main()
