"""Reset Closing Odds Data.

Clears synthetic/test closing odds data to prepare for real data collection.

This script:
1. Removes all odds_snapshots entries where is_closing=1
2. Resets odds_closing field in bets table to NULL
3. Resets clv field in bets table to NULL (needs recalculation)
4. Creates backup before deletion

Usage:
    python scripts/reset_closing_odds.py --db data/betting.db

Author: Zero-cost data retrieval implementation
Date: 2026-01-26
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
import argparse
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@contextmanager
def get_db(db_path: str):
    """Context manager for database connections."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def backup_database(db_path: str) -> str:
    """Create backup of database before modifications.

    Returns:
        Path to backup file.
    """
    db_path = Path(db_path)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}.db"

    shutil.copy2(db_path, backup_path)
    logger.info(f"Created backup: {backup_path}")

    return str(backup_path)


def get_current_stats(db_path: str) -> dict:
    """Get current statistics before reset."""
    with get_db(db_path) as conn:
        stats = {}

        # Count closing odds snapshots
        result = conn.execute(
            "SELECT COUNT(*) as count FROM odds_snapshots WHERE is_closing = 1"
        ).fetchone()
        stats["closing_snapshots"] = result["count"] if result else 0

        # Count total odds snapshots
        result = conn.execute("SELECT COUNT(*) as count FROM odds_snapshots").fetchone()
        stats["total_snapshots"] = result["count"] if result else 0

        # Count bets with odds_closing
        result = conn.execute(
            "SELECT COUNT(*) as count FROM bets WHERE odds_closing IS NOT NULL"
        ).fetchone()
        stats["bets_with_closing_odds"] = result["count"] if result else 0

        # Count bets with CLV
        result = conn.execute("SELECT COUNT(*) as count FROM bets WHERE clv IS NOT NULL").fetchone()
        stats["bets_with_clv"] = result["count"] if result else 0

        return stats


def reset_closing_odds(db_path: str, dry_run: bool = False) -> dict:
    """Reset all synthetic closing odds data.

    Args:
        db_path: Path to SQLite database.
        dry_run: If True, show what would be done without making changes.

    Returns:
        Summary of operations performed.
    """
    results = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "operations": [],
    }

    # Get current stats
    before_stats = get_current_stats(db_path)
    results["before"] = before_stats
    logger.info(f"Before reset: {json.dumps(before_stats, indent=2)}")

    if dry_run:
        logger.info("DRY RUN - No changes will be made")
        results["operations"].append("DRY RUN - No changes made")
        return results

    # Create backup first
    backup_path = backup_database(db_path)
    results["backup_path"] = backup_path

    with get_db(db_path) as conn:
        # 1. Archive closing odds before deletion (for audit trail)
        logger.info("Archiving closing odds data before deletion...")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS odds_snapshots_archive_synthetic (
                id INTEGER,
                game_id TEXT,
                sportsbook TEXT,
                captured_at TEXT,
                spread_home REAL,
                spread_home_odds INTEGER,
                spread_away_odds INTEGER,
                total REAL,
                over_odds INTEGER,
                under_odds INTEGER,
                moneyline_home INTEGER,
                moneyline_away INTEGER,
                is_closing BOOLEAN,
                archived_at TEXT DEFAULT CURRENT_TIMESTAMP,
                archive_reason TEXT DEFAULT 'synthetic_data_reset'
            )
        """
        )

        cursor = conn.execute(
            """
            INSERT INTO odds_snapshots_archive_synthetic
            SELECT *, CURRENT_TIMESTAMP, 'synthetic_data_reset'
            FROM odds_snapshots
            WHERE is_closing = 1
        """
        )
        archived_count = cursor.rowcount
        results["operations"].append(f"Archived {archived_count} closing odds records")
        logger.info(f"Archived {archived_count} closing odds records")

        # 2. Delete closing odds snapshots
        logger.info("Deleting closing odds snapshots...")
        cursor = conn.execute("DELETE FROM odds_snapshots WHERE is_closing = 1")
        deleted_snapshots = cursor.rowcount
        results["operations"].append(f"Deleted {deleted_snapshots} closing odds snapshots")
        logger.info(f"Deleted {deleted_snapshots} closing odds snapshots")

        # 3. Reset odds_closing in bets table
        logger.info("Resetting odds_closing in bets table...")
        cursor = conn.execute("UPDATE bets SET odds_closing = NULL WHERE odds_closing IS NOT NULL")
        reset_bets_odds = cursor.rowcount
        results["operations"].append(f"Reset odds_closing for {reset_bets_odds} bets")
        logger.info(f"Reset odds_closing for {reset_bets_odds} bets")

        # 4. Reset CLV in bets table (needs recalculation with real closing odds)
        logger.info("Resetting CLV in bets table...")
        cursor = conn.execute("UPDATE bets SET clv = NULL WHERE clv IS NOT NULL")
        reset_bets_clv = cursor.rowcount
        results["operations"].append(f"Reset CLV for {reset_bets_clv} bets")
        logger.info(f"Reset CLV for {reset_bets_clv} bets")

    # Get stats after reset
    after_stats = get_current_stats(db_path)
    results["after"] = after_stats
    logger.info(f"After reset: {json.dumps(after_stats, indent=2)}")

    return results


def verify_reset(db_path: str) -> bool:
    """Verify that reset was successful.

    Returns:
        True if reset verified, False otherwise.
    """
    stats = get_current_stats(db_path)

    if stats["closing_snapshots"] > 0:
        logger.error(f"VERIFICATION FAILED: {stats['closing_snapshots']} closing snapshots remain")
        return False

    if stats["bets_with_closing_odds"] > 0:
        logger.error(
            f"VERIFICATION FAILED: {stats['bets_with_closing_odds']} bets still have odds_closing"
        )
        return False

    if stats["bets_with_clv"] > 0:
        logger.error(f"VERIFICATION FAILED: {stats['bets_with_clv']} bets still have CLV")
        return False

    logger.info("VERIFICATION PASSED: All synthetic closing data has been reset")
    return True


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Reset synthetic closing odds data to prepare for real data collection"
    )
    parser.add_argument("--db", default="data/betting.db", help="Path to SQLite database")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--no-backup", action="store_true", help="Skip creating backup (not recommended)"
    )
    parser.add_argument(
        "--verify", action="store_true", help="Only verify current state, don't reset"
    )

    args = parser.parse_args()

    db_path = Path(args.db)

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return 1

    if args.verify:
        # Just verify current state
        stats = get_current_stats(str(db_path))
        print("\n=== Current Closing Odds Status ===")
        print(json.dumps(stats, indent=2))
        return 0

    # Confirm before proceeding
    if not args.dry_run:
        print("\n=== WARNING ===")
        print("This will DELETE all synthetic closing odds data:")
        stats = get_current_stats(str(db_path))
        print(f"  - {stats['closing_snapshots']} closing odds snapshots")
        print(f"  - {stats['bets_with_closing_odds']} bets with odds_closing")
        print(f"  - {stats['bets_with_clv']} bets with CLV")
        print("\nA backup will be created before deletion.")

        confirm = input("\nType 'yes' to proceed: ")
        if confirm.lower() != "yes":
            print("Aborted.")
            return 0

    # Perform reset
    results = reset_closing_odds(str(db_path), dry_run=args.dry_run)

    print("\n=== Reset Results ===")
    print(json.dumps(results, indent=2))

    # Verify if not dry run
    if not args.dry_run:
        print("\n=== Verification ===")
        if verify_reset(str(db_path)):
            print("SUCCESS: Ready for real closing odds collection")
            return 0
        else:
            print("ERROR: Reset verification failed")
            return 1

    return 0


if __name__ == "__main__":
    exit(main())
