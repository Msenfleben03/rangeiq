"""Unified Season Data Fetcher — Scores + Odds in One Pass.

Replaces the two-step workflow of:
    1. fetch_historical_data.py   (scores only)
    2. backfill_historical_odds.py (odds only, hours later)

With a single pipeline that fetches both simultaneously.

Usage:
    # Fetch full season with odds
    python scripts/fetch_season_data.py --season 2025

    # Fetch all seasons
    python scripts/fetch_season_data.py

    # Incremental update (only new games)
    python scripts/fetch_season_data.py --season 2025 --incremental

    # Scores only (no odds, fast)
    python scripts/fetch_season_data.py --season 2025 --no-odds

    # Nightly cron mode (incremental + current season)
    python scripts/fetch_season_data.py --nightly

    # Force re-fetch everything
    python scripts/fetch_season_data.py --season 2025 --force
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Allow imports from project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import NCAAB_SEASONS_START, NCAAB_SEASONS_END  # noqa: E402
from pipelines.unified_fetcher import UnifiedNCAABFetcher  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def current_ncaab_season() -> int:
    """Determine the current NCAAB season year.

    NCAAB season spans Nov-Apr. The "2025 season" runs Nov 2024 - Apr 2025.
    Before November, the current season is the calendar year.
    From November onward, it's calendar year + 1.

    Returns:
        Current season year.
    """
    now = datetime.now()
    if now.month >= 11:
        return now.year + 1
    return now.year


def main() -> None:
    """Run unified season data fetch."""
    parser = argparse.ArgumentParser(
        description="Fetch NCAAB scores + odds in a single pass",
    )
    parser.add_argument(
        "--season",
        type=int,
        default=None,
        help="Specific season to fetch (default: all configured seasons)",
    )
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
        "--incremental",
        action="store_true",
        help="Only fetch new games not already in parquet",
    )
    parser.add_argument(
        "--nightly",
        action="store_true",
        help="Nightly mode: incremental fetch of current season only",
    )
    parser.add_argument(
        "--no-odds",
        action="store_true",
        help="Skip odds fetching (scores only, fast)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-fetch everything, ignoring cache",
    )
    parser.add_argument(
        "--no-skip-list",
        action="store_true",
        help="Ignore skip list (re-try games that previously had no odds)",
    )
    parser.add_argument(
        "--odds-rate",
        type=float,
        default=2.0,
        help="Odds API requests per second (default: 2.0)",
    )
    parser.add_argument(
        "--score-delay",
        type=float,
        default=0.3,
        help="Delay between score requests in seconds (default: 0.3)",
    )

    args = parser.parse_args()

    # Determine seasons to fetch
    if args.nightly:
        seasons = [current_ncaab_season()]
        incremental = True
        logger.info("Nightly mode: fetching current season %d", seasons[0])
    elif args.season:
        seasons = [args.season]
        incremental = args.incremental
    else:
        seasons = list(range(args.start, args.end + 1))
        incremental = args.incremental

    with_odds = not args.no_odds
    use_skip_list = not args.no_skip_list

    fetcher = UnifiedNCAABFetcher(
        score_delay=args.score_delay,
        odds_rate=args.odds_rate,
    )

    total_start = time.time()
    results: dict[int, dict] = {}

    try:
        for season in seasons:
            logger.info("=" * 60)
            logger.info("Season %d — %s", season, "incremental" if incremental else "full")
            logger.info("=" * 60)

            season_start = time.time()
            df = fetcher.fetch_season(
                season,
                with_odds=with_odds,
                incremental=incremental,
                force=args.force,
                use_skip_list=use_skip_list,
            )

            elapsed = time.time() - season_start
            n_games = len(df)
            n_with_odds = (
                df["home_moneyline"].notna().sum() if "home_moneyline" in df.columns else 0
            )

            results[season] = {
                "games": n_games,
                "with_odds": int(n_with_odds),
                "elapsed": elapsed,
            }

            logger.info(
                "Season %d: %d games, %d with odds (%.1f min)",
                season,
                n_games,
                n_with_odds,
                elapsed / 60,
            )

    except KeyboardInterrupt:
        logger.warning("Interrupted! Completed seasons are saved.")
    finally:
        fetcher.close()

    # Summary
    total_elapsed = time.time() - total_start
    print(f"\n{'=' * 60}")
    print("UNIFIED FETCH SUMMARY")
    print(f"{'=' * 60}")
    print(f"Mode: {'incremental' if incremental else 'full'} | Odds: {with_odds}")
    print(f"Total time: {total_elapsed / 60:.1f} minutes\n")

    total_games = 0
    total_odds = 0
    for season in sorted(results):
        r = results[season]
        coverage = 100 * r["with_odds"] / r["games"] if r["games"] > 0 else 0
        print(
            f"  {season}: {r['games']:,} games | "
            f"{r['with_odds']:,} with odds ({coverage:.0f}%) | "
            f"{r['elapsed'] / 60:.1f} min"
        )
        total_games += r["games"]
        total_odds += r["with_odds"]

    if total_games > 0:
        overall_coverage = 100 * total_odds / total_games
        print(
            f"\n  Total: {total_games:,} games, {total_odds:,} with odds ({overall_coverage:.0f}%)"
        )
    elif not results:
        logger.error("No games fetched across all seasons")
        sys.exit(1)


if __name__ == "__main__":
    main()
