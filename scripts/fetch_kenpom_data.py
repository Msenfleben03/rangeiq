#!/usr/bin/env python3
"""Fetch KenPom efficiency ratings and cache as parquet.

Requires a KenPom subscription ($25/year) with credentials in .env:
  KENPOM_EMAIL=your_email
  KENPOM_PASSWORD=your_password

Usage:
    # Fetch all historical seasons (2020-2026)
    python scripts/fetch_kenpom_data.py --seasons 2020 2021 2022 2023 2024 2025 2026

    # Fetch just current season
    python scripts/fetch_kenpom_data.py --daily-only

    # Fetch specific seasons
    python scripts/fetch_kenpom_data.py --seasons 2025 2026

    # Force re-fetch (ignore cache)
    python scripts/fetch_kenpom_data.py --seasons 2026 --force
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from config.settings import KENPOM_DATA_DIR, KENPOM_EMAIL, KENPOM_PASSWORD
from pipelines.kenpom_fetcher import KenPomFetcher


def main() -> int:
    """Run the KenPom data fetcher CLI."""
    parser = argparse.ArgumentParser(description="Fetch KenPom efficiency ratings")
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=None,
        help="Season years to fetch (default: 2020-2026)",
    )
    parser.add_argument(
        "--daily-only",
        action="store_true",
        help="Only fetch today's snapshot for current season",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even if cache exists",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=KENPOM_DATA_DIR,
        help="Cache directory (default: data/external/kenpom)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--store-db",
        action="store_true",
        help="Also store snapshot to SQLite kenpom_ratings table",
    )
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Get credentials
    email = KENPOM_EMAIL or os.environ.get("KENPOM_EMAIL", "")
    password = KENPOM_PASSWORD or os.environ.get("KENPOM_PASSWORD", "")

    if not email or not password:
        print("ERROR: KenPom credentials not found.")
        print("Set KENPOM_EMAIL and KENPOM_PASSWORD in .env or environment.")
        return 1

    try:
        fetcher = KenPomFetcher(
            email=email,
            password=password,
            cache_dir=args.cache_dir,
        )
    except Exception as exc:
        print(f"ERROR: Failed to initialize KenPom fetcher: {exc}")
        return 1

    if args.daily_only:
        print("Fetching today's KenPom snapshot...")
        df = fetcher.fetch_current_snapshot()
        if df.empty:
            print("FAILED: No data retrieved.")
            return 1
        _print_summary(df, "Current")
        if args.store_db:
            from datetime import date

            from pipelines.kenpom_fetcher import store_snapshot_to_db

            season = int(df["year"].iloc[0]) if "year" in df.columns else date.today().year
            count = store_snapshot_to_db(df, season)
            print(f"Stored {count} ratings to SQLite (kenpom_ratings table)")
        return 0

    # Fetch specified seasons
    seasons = args.seasons or list(range(2020, 2027))
    print(f"Fetching KenPom ratings for seasons: {seasons}")
    print(f"Cache directory: {args.cache_dir}")

    total_teams = 0
    for season in seasons:
        print(f"\n--- Season {season} ---")
        use_cache = not args.force
        df = fetcher.fetch_season_ratings(season, use_cache=use_cache)

        if df.empty:
            print(f"  No data for season {season}")
            continue

        n_teams = df["team"].nunique()
        total_teams += n_teams
        print(f"  Teams: {n_teams}")
        _print_top5(df, season)

    print(f"\nTotal: {total_teams} team-season ratings cached")
    return 0


def _print_summary(df, label: str) -> None:
    """Print a summary of fetched data."""
    n_teams = df["team"].nunique() if "team" in df.columns else 0
    print(f"\n{label}: {n_teams} teams")
    _print_top5(df, label)


def _print_top5(df, season) -> None:
    """Print top 5 teams from a ratings DataFrame."""
    if "rank" in df.columns and "team" in df.columns:
        top5 = df.nsmallest(5, "rank")
        for _, row in top5.iterrows():
            adj_em = row.get("adj_em", 0)
            adj_o = row.get("adj_o", 0)
            adj_d = row.get("adj_d", 0)
            print(
                f"  {int(row['rank']):3d}. {row['team']:<25s} "
                f"AdjEM={adj_em:+6.1f}  AdjO={adj_o:6.1f}  AdjD={adj_d:5.1f}"
            )


if __name__ == "__main__":
    sys.exit(main())
