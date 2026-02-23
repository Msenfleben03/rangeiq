"""Daily Ratings Snapshot Collector.

Fetches today's Barttorvik and KenPom ratings and appends them to the
season cache files. Each run adds one date's worth of data (~365 teams)
to build up point-in-time history for backtesting.

Run this DAILY to accumulate PIT snapshots. Idempotent — running
multiple times on the same day deduplicates by (team, date).

Usage:
    python scripts/daily_snapshot.py                # Both sources
    python scripts/daily_snapshot.py --barttorvik    # Barttorvik only
    python scripts/daily_snapshot.py --kenpom        # KenPom only
    python scripts/daily_snapshot.py --season 2026   # Specific season
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from config.settings import (
    CBBDATA_API_KEY,
    KENPOM_EMAIL,
    KENPOM_PASSWORD,
)
from pipelines.barttorvik_fetcher import (
    BarttovikFetcher,
    load_cached_season,
)
from pipelines.kenpom_fetcher import (
    KenPomFetcher,
    load_cached_season as load_kenpom_cached,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_current_season() -> int:
    """Determine the current NCAAB season year.

    NCAAB season spans Nov-March. The season year is the calendar year
    of the spring portion (e.g., 2025-26 season = 2026).
    """
    today = date.today()
    return today.year if today.month >= 10 else today.year


def fetch_barttorvik_snapshot(season: int) -> dict:
    """Fetch and append today's Barttorvik snapshot.

    Returns:
        Dict with status info.
    """
    api_key = CBBDATA_API_KEY or os.environ.get("CBBDATA_API_KEY", "")
    if not api_key:
        return {"source": "barttorvik", "status": "skipped", "reason": "no API key"}

    try:
        fetcher = BarttovikFetcher(api_key=api_key)
        df = fetcher.fetch_daily_snapshot(season)
        fetcher.close()

        if df.empty:
            return {"source": "barttorvik", "status": "empty", "teams": 0}

        # Report cache state
        cached = load_cached_season(season)
        n_dates = cached["date"].nunique() if cached is not None else 0

        return {
            "source": "barttorvik",
            "status": "ok",
            "teams": len(df),
            "snapshot_date": df["date"].max().strftime("%Y-%m-%d"),
            "cache_total_rows": len(cached) if cached is not None else 0,
            "cache_total_dates": n_dates,
        }
    except Exception as exc:
        logger.error("Barttorvik snapshot failed: %s", exc)
        return {"source": "barttorvik", "status": "error", "error": str(exc)}


def fetch_kenpom_snapshot(season: int) -> dict:
    """Fetch and append today's KenPom snapshot.

    Returns:
        Dict with status info.
    """
    email = KENPOM_EMAIL or os.environ.get("KENPOM_EMAIL", "")
    password = KENPOM_PASSWORD or os.environ.get("KENPOM_PASSWORD", "")
    if not email or not password:
        return {"source": "kenpom", "status": "skipped", "reason": "no credentials"}

    try:
        fetcher = KenPomFetcher(email=email, password=password)
        df = fetcher.fetch_current_snapshot()

        if df.empty:
            return {"source": "kenpom", "status": "empty", "teams": 0}

        # Report cache state
        cached = load_kenpom_cached(season)
        n_dates = 0
        if cached is not None and "date" in cached.columns:
            import pandas as pd

            cached["date"] = pd.to_datetime(cached["date"])
            n_dates = cached["date"].nunique()

        return {
            "source": "kenpom",
            "status": "ok",
            "teams": len(df),
            "snapshot_date": date.today().strftime("%Y-%m-%d"),
            "cache_total_rows": len(cached) if cached is not None else 0,
            "cache_total_dates": n_dates,
        }
    except Exception as exc:
        logger.error("KenPom snapshot failed: %s", exc)
        return {"source": "kenpom", "status": "error", "error": str(exc)}


def main() -> int:
    """Run daily ratings snapshot collection for Barttorvik and KenPom."""
    parser = argparse.ArgumentParser(
        description="Daily ratings snapshot collector (Barttorvik + KenPom)"
    )
    parser.add_argument(
        "--season",
        type=int,
        default=None,
        help="Season year (default: auto-detect current season)",
    )
    parser.add_argument(
        "--barttorvik",
        action="store_true",
        help="Fetch Barttorvik only",
    )
    parser.add_argument(
        "--kenpom",
        action="store_true",
        help="Fetch KenPom only",
    )
    args = parser.parse_args()

    season = args.season or get_current_season()
    # If neither flag is set, fetch both
    fetch_bart = args.barttorvik or (not args.barttorvik and not args.kenpom)
    fetch_kp = args.kenpom or (not args.barttorvik and not args.kenpom)

    print(f"Daily Snapshot — Season {season} ({date.today().strftime('%Y-%m-%d')})")
    print(f"Sources: {'Barttorvik' if fetch_bart else ''} {'KenPom' if fetch_kp else ''}")
    print()

    results = []
    errors = 0

    if fetch_bart:
        print("--- Barttorvik ---")
        result = fetch_barttorvik_snapshot(season)
        results.append(result)
        if result["status"] == "ok":
            print(f"  Snapshot: {result['teams']} teams ({result['snapshot_date']})")
            print(
                f"  Cache:    {result['cache_total_rows']} rows, {result['cache_total_dates']} dates"
            )
        elif result["status"] == "skipped":
            print(f"  Skipped:  {result['reason']}")
        elif result["status"] == "error":
            print(f"  ERROR:    {result['error']}")
            errors += 1
        else:
            print("  Empty response")
            errors += 1

    if fetch_kp:
        print("--- KenPom ---")
        result = fetch_kenpom_snapshot(season)
        results.append(result)
        if result["status"] == "ok":
            print(f"  Snapshot: {result['teams']} teams ({result['snapshot_date']})")
            print(
                f"  Cache:    {result['cache_total_rows']} rows, {result['cache_total_dates']} dates"
            )
        elif result["status"] == "skipped":
            print(f"  Skipped:  {result['reason']}")
        elif result["status"] == "error":
            print(f"  ERROR:    {result['error']}")
            errors += 1
        else:
            print("  Empty response")
            errors += 1

    print()
    ok_count = sum(1 for r in results if r["status"] == "ok")
    print(f"Done: {ok_count}/{len(results)} sources updated successfully")

    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
