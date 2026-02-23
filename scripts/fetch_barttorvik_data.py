"""Fetch and cache Barttorvik T-Rank ratings for all seasons.

Downloads daily point-in-time efficiency ratings from the cbbdata.com API
and caches them as parquet files in data/external/barttorvik/.

For in-progress seasons (e.g. 2026), the cbbdata archive endpoint returns
empty. Use --scrape to fetch today's snapshot directly from barttorvik.com
and append it to the cache (building daily history over time).

Requires CBBDATA_API_KEY in .env or environment (for completed seasons).

Usage:
    python scripts/fetch_barttorvik_data.py                    # Completed seasons via API
    python scripts/fetch_barttorvik_data.py --seasons 2025
    python scripts/fetch_barttorvik_data.py --seasons 2026 --scrape  # Current season
    python scripts/fetch_barttorvik_data.py --force            # Re-download even if cached
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from config.settings import CBBDATA_API_KEY  # noqa: E402
from pipelines.barttorvik_fetcher import BarttovikFetcher  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Barttorvik T-Rank ratings")
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=[2020, 2021, 2022, 2023, 2024, 2025],
        help="Seasons to fetch (default: 2020-2025)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if cache exists",
    )
    parser.add_argument(
        "--scrape",
        action="store_true",
        help="Use barttorvik.com scraper for current season (cbbdata archive "
        "returns empty for in-progress seasons)",
    )
    args = parser.parse_args()

    # Scrape mode: use barttorvik_scraper for in-progress seasons
    if args.scrape:
        from pipelines.barttorvik_scraper import scrape_and_cache

        for season in args.seasons:
            logger.info("Scraping barttorvik.com for season %d...", season)
            df = scrape_and_cache(season, force=args.force)
            if df.empty:
                logger.error("Scrape failed for season %d", season)
            else:
                import pandas as pd

                df["date"] = pd.to_datetime(df["date"])
                n_dates = df["date"].nunique()
                n_teams = df["team"].nunique()
                date_min = df["date"].min().strftime("%Y-%m-%d")
                date_max = df["date"].max().strftime("%Y-%m-%d")
                print(
                    f"  Season {season}: {len(df):>6,} ratings, "
                    f"{n_teams:>3} teams, {n_dates:>3} dates "
                    f"({date_min} to {date_max})"
                )
        return

    # API mode: use cbbdata API for completed seasons
    if not CBBDATA_API_KEY:
        logger.error(
            "CBBDATA_API_KEY not found. Set it in .env or environment. "
            "Register free at https://www.cbbdata.com"
        )
        sys.exit(1)

    fetcher = BarttovikFetcher(api_key=CBBDATA_API_KEY)

    try:
        combined = fetcher.fetch_all_seasons(
            seasons=args.seasons,
            use_cache=not args.force,
        )

        if combined.empty:
            logger.error("No data fetched. Check your API key.")
            sys.exit(1)

        # Print summary
        print(f"\n{'=' * 60}")
        print("BARTTORVIK DATA SUMMARY")
        print(f"{'=' * 60}")
        for season in args.seasons:
            season_df = combined[combined["year"] == season]
            if not season_df.empty:
                date_min = season_df["date"].min().strftime("%Y-%m-%d")
                date_max = season_df["date"].max().strftime("%Y-%m-%d")
                print(
                    f"  Season {season}: {len(season_df):>6,} ratings, "
                    f"{season_df['team'].nunique():>3} teams, "
                    f"{season_df['date'].nunique():>3} dates "
                    f"({date_min} to {date_max})"
                )
        print(f"\n  Total: {len(combined):,} ratings")
        print("  Cache: data/external/barttorvik/")
    finally:
        fetcher.close()


if __name__ == "__main__":
    main()
