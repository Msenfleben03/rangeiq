"""Standalone Game Log Manager.

Insert games, settle results, or export the game log.

Usage:
    python scripts/generate_game_log.py --date 2026-03-11
    python scripts/generate_game_log.py --settle
    python scripts/generate_game_log.py --export csv
    python scripts/generate_game_log.py --export json
    python scripts/generate_game_log.py --stats
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import NCAAB_DATABASE_PATH
from scripts.daily_predictions import fetch_espn_scoreboard
from scripts.collect_closing_odds import fetch_completed_games, fetch_espn_closing_odds
from tracking.game_log import insert_game_log_entries, settle_game_log_entries

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def export_game_log(db_path: Path, fmt: str = "csv") -> str:
    """Export game_log table to CSV or JSON.

    Args:
        db_path: Path to database.
        fmt: "csv" or "json".

    Returns:
        Path to exported file.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM game_log ORDER BY game_date DESC, home").fetchall()
    conn.close()

    out_dir = PROJECT_ROOT / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    if fmt == "csv":
        out_path = out_dir / "ncaab_game_log.csv"
        if rows:
            keys = rows[0].keys()
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for row in rows:
                    writer.writerow(dict(row))
        else:
            out_path.write_text("No data\n", encoding="utf-8")
    elif fmt == "json":
        out_path = out_dir / "ncaab_game_log.json"
        data = [dict(row) for row in rows]
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
    else:
        raise ValueError(f"Unknown format: {fmt}")

    print(f"Exported {len(rows)} games to {out_path}")
    return str(out_path)


def show_stats(db_path: Path) -> None:
    """Print game log summary statistics."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) as n FROM game_log").fetchone()["n"]
    settled = conn.execute(
        "SELECT COUNT(*) as n FROM game_log WHERE result IS NOT NULL"
    ).fetchone()["n"]
    bet_count = conn.execute("SELECT COUNT(*) as n FROM game_log WHERE bet_placed = 1").fetchone()[
        "n"
    ]
    with_odds = conn.execute(
        "SELECT COUNT(*) as n FROM game_log WHERE odds_opening_home IS NOT NULL"
    ).fetchone()["n"]
    with_closing = conn.execute(
        "SELECT COUNT(*) as n FROM game_log WHERE odds_closing_home IS NOT NULL"
    ).fetchone()["n"]
    dates = conn.execute(
        "SELECT MIN(game_date) as first, MAX(game_date) as last FROM game_log"
    ).fetchone()
    conn.close()

    print(f"\n{'=' * 50}")
    print("NCAAB Game Log Statistics")
    print(f"{'=' * 50}")
    print(f"Total games:          {total}")
    print(f"Settled:              {settled}")
    print(f"Pending:              {total - settled}")
    print(f"Games with bets:      {bet_count}")
    print(f"With opening odds:    {with_odds}")
    print(f"With closing odds:    {with_closing}")
    print(f"Date range:           {dates['first']} to {dates['last']}")


def main() -> None:
    """Parse arguments and execute the requested action."""
    parser = argparse.ArgumentParser(description="NCAAB Game Log Manager")
    parser.add_argument("--date", help="Insert games for date (YYYY-MM-DD)")
    parser.add_argument("--settle", action="store_true", help="Settle unsettled games")
    parser.add_argument("--settle-date", help="Settle games for specific date (YYYY-MM-DD)")
    parser.add_argument("--export", choices=["csv", "json"], help="Export game log")
    parser.add_argument("--stats", action="store_true", help="Show game log statistics")
    parser.add_argument("--db", type=Path, default=NCAAB_DATABASE_PATH, help="Database path")
    args = parser.parse_args()

    if args.stats:
        show_stats(args.db)
        return

    if args.export:
        export_game_log(args.db, args.export)
        return

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d")
        games = fetch_espn_scoreboard(target)
        print(f"Found {len(games)} games for {args.date}")

        inserted = insert_game_log_entries(
            str(args.db),
            args.date,
            games,
            {},
            {},
        )
        print(f"Inserted {inserted} new games into game_log")

    if args.settle:
        settle_date = args.settle_date
        if not settle_date:
            settle_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        completed = fetch_completed_games(settle_date)
        if not completed:
            print(f"No completed games found for {settle_date}")
            return

        game_ids = [g["game_id"] for g in completed]
        espn_results = fetch_espn_closing_odds(game_ids)

        closing_odds: dict[str, dict] = {}
        for gid, snapshot in espn_results.items():
            closing_odds[gid] = {
                "home": snapshot.home_ml_close or snapshot.home_moneyline,
                "away": snapshot.away_ml_close or snapshot.away_moneyline,
            }

        settled = settle_game_log_entries(str(args.db), completed, closing_odds)
        print(f"Settled {settled} games for {settle_date}")


if __name__ == "__main__":
    main()
