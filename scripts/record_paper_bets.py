"""Record Paper Bets.

Interactive and CSV-import modes for recording paper bet decisions.
Validates exposure limits before confirming.

Usage:
    python scripts/record_paper_bets.py --date today
    python scripts/record_paper_bets.py --import-csv bets.csv
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DATABASE_PATH
from tracking.database import BettingDatabase
from tracking.logger import (
    get_bets_by_date,
    log_multiple_bets,
    log_paper_bet,
    validate_bet_limits,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def import_from_csv(csv_path: Path, db: BettingDatabase) -> int:
    """Import paper bets from a CSV file.

    CSV columns: sport, game_date, game_id, bet_type, selection, line,
                 odds_placed, stake, sportsbook, model_probability, model_edge, notes

    Args:
        csv_path: Path to CSV file.
        db: BettingDatabase instance.

    Returns:
        Number of bets successfully imported.
    """
    if not csv_path.exists():
        logger.error("CSV file not found: %s", csv_path)
        return 0

    bets = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bet = {
                "sport": row.get("sport", "ncaab"),
                "game_date": row["game_date"],
                "game_id": row.get("game_id", ""),
                "bet_type": row["bet_type"],
                "selection": row["selection"],
                "odds_placed": int(row["odds_placed"]),
                "stake": float(row["stake"]),
                "sportsbook": row.get("sportsbook", "draftkings"),
            }
            # Optional fields
            if row.get("line"):
                bet["line"] = float(row["line"])
            if row.get("model_probability"):
                bet["model_probability"] = float(row["model_probability"])
            if row.get("model_edge"):
                bet["model_edge"] = float(row["model_edge"])
            if row.get("notes"):
                bet["notes"] = row["notes"]

            # Validate limits
            check = validate_bet_limits(bet["stake"], db)
            if not check["allowed"]:
                logger.warning("Bet rejected: %s — %s", bet.get("game_id"), check["reason"])
                continue

            bets.append(bet)

    ids = log_multiple_bets(db, bets)
    return len(ids)


def interactive_mode(target_date: str, db: BettingDatabase) -> None:
    """Interactive bet recording."""
    print(f"\n{'=' * 60}")
    print(f"PAPER BET RECORDING — {target_date}")
    print(f"{'=' * 60}")

    # Show existing bets for today
    existing = get_bets_by_date(db, target_date, sport="ncaab")
    if existing:
        print(f"\nExisting bets for {target_date}: {len(existing)}")
        for bet in existing:
            print(
                f"  {bet['game_id']}: {bet['bet_type']} {bet['selection']} @ {bet['odds_placed']}"
            )

    print("\nEnter bets (type 'done' to finish):")
    print("Format: game_id, bet_type, selection, odds, stake, sportsbook")
    print("Example: DUKE_UNC, moneyline, home, -220, 100, draftkings\n")

    while True:
        try:
            line = input("Bet> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if line.lower() in ("done", "quit", "exit", ""):
            break

        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            print("  Need: game_id, bet_type, selection, odds, stake, sportsbook")
            continue

        try:
            bet = {
                "sport": "ncaab",
                "game_date": target_date,
                "game_id": parts[0],
                "bet_type": parts[1],
                "selection": parts[2],
                "odds_placed": int(parts[3]),
                "stake": float(parts[4]),
                "sportsbook": parts[5],
            }

            check = validate_bet_limits(bet["stake"], db)
            if not check["allowed"]:
                print(f"  REJECTED: {check['reason']}")
                continue

            bet_id = log_paper_bet(db, bet)
            print(f"  Recorded bet #{bet_id}: {bet['selection']} @ {bet['odds_placed']}")

        except (ValueError, IndexError) as e:
            print(f"  Error: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Record paper bets")
    parser.add_argument("--date", type=str, default="today")
    parser.add_argument("--import-csv", type=str, default=None)
    args = parser.parse_args()

    db = BettingDatabase(str(DATABASE_PATH))

    if args.import_csv:
        count = import_from_csv(Path(args.import_csv), db)
        print(f"Imported {count} bets from {args.import_csv}")
    else:
        if args.date.lower() == "today":
            target_date = datetime.now().strftime("%Y-%m-%d")
        else:
            target_date = args.date
        interactive_mode(target_date, db)


if __name__ == "__main__":
    main()
