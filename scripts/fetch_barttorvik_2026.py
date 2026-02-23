#!/usr/bin/env python3
"""Fetch current-season Barttorvik T-Rank ratings via web scraping.

Designed to run daily as part of the nightly refresh workflow.
Falls back through: cbbdata API → curl_cffi → SeleniumBase.

Usage:
    python scripts/fetch_barttorvik_2026.py
    python scripts/fetch_barttorvik_2026.py --force         # Re-scrape even if today cached
    python scripts/fetch_barttorvik_2026.py --method curl    # Force curl_cffi only
    python scripts/fetch_barttorvik_2026.py --method browser # Force SeleniumBase
    python scripts/fetch_barttorvik_2026.py --year 2025      # Different season
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.settings import BARTTORVIK_DATA_DIR
from pipelines.barttorvik_scraper import scrape_and_cache


def main() -> int:
    """Run the Barttorvik scraper CLI."""
    parser = argparse.ArgumentParser(description="Fetch Barttorvik T-Rank ratings via scraping")
    parser.add_argument(
        "--year",
        type=int,
        default=2026,
        help="Season year (default: 2026)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape even if today's data is already cached",
    )
    parser.add_argument(
        "--method",
        choices=["api", "curl", "browser"],
        default=None,
        help="Force a specific scraping method (default: try all)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=BARTTORVIK_DATA_DIR,
        help="Cache directory (default: data/external/barttorvik)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print(f"Fetching Barttorvik ratings for season {args.year}...")
    print(f"Cache directory: {args.cache_dir}")
    if args.force:
        print("Force mode: will re-scrape even if today is cached")
    if args.method:
        print(f"Method override: {args.method}")

    df = scrape_and_cache(
        year=args.year,
        cache_dir=args.cache_dir,
        force=args.force,
        method=args.method,
    )

    if df.empty:
        print("\nFAILED: No data retrieved. Check logs for details.")
        return 1

    # Summary stats
    n_teams = df["team"].nunique() if "team" in df.columns else 0
    n_dates = df["date"].nunique() if "date" in df.columns else 0

    print("\nSuccess!")
    print(f"  Teams: {n_teams}")
    print(f"  Date snapshots: {n_dates}")
    print(f"  Total rows: {len(df)}")

    # Show top 10
    if "rank" in df.columns and "team" in df.columns:
        latest_date = df["date"].max()
        latest = df[df["date"] == latest_date].nsmallest(10, "rank")
        print(
            f"\nTop 10 teams (as of {latest_date.date() if hasattr(latest_date, 'date') else latest_date}):"
        )
        print("-" * 70)
        for _, row in latest.iterrows():
            print(
                f"  {int(row['rank']):3d}. {row['team']:<25s} "
                f"AdjO={row['adj_o']:6.1f}  AdjD={row['adj_d']:5.1f}  "
                f"Barthag={row['barthag']:.4f}"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
