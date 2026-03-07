"""Database restore script.

Restores ncaab_betting.db and/or mlb_data.db from a backup created by backup_db.py.

Usage:
    python scripts/restore_db.py --list              # Show available backup points
    python scripts/restore_db.py                     # Restore all DBs from latest daily backup
    python scripts/restore_db.py --date 2026-03-04   # Restore from specific date
    python scripts/restore_db.py --db ncaab_betting.db  # Restore one DB only
    python scripts/restore_db.py --weekly            # Use weekly backups instead of daily
    python scripts/restore_db.py --verify-only       # Check latest backup without restoring

Exit codes:
    0 = success
    1 = partial / no backup found
    2 = critical failure
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKUP_ROOT = Path(r"C:\Users\msenf\sports-betting-backups")

DATABASES = {
    "ncaab_betting.db": PROJECT_ROOT / "data" / "ncaab_betting.db",
    "mlb_data.db": PROJECT_ROOT / "data" / "mlb_data.db",
}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def verify_sqlite(path: Path) -> bool:
    """Return True if path is a valid, non-empty SQLite database."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA integrity_check")
        conn.close()
        return True
    except Exception:
        return False


def find_latest_backup(db_name: str, tier: str) -> Path | None:
    """Find the most recent backup file for db_name in the given tier."""
    d = BACKUP_ROOT / tier
    if not d.exists():
        return None
    candidates = sorted(d.glob(f"{db_name}_*.bak"), key=lambda x: x.stat().st_mtime)
    return candidates[-1] if candidates else None


def find_backup_by_date(db_name: str, tier: str, date_str: str) -> Path | None:
    """Find backup file matching a specific date label (YYYY-MM-DD)."""
    d = BACKUP_ROOT / tier
    if not d.exists():
        return None
    target = d / f"{db_name}_{date_str}.bak"
    return target if target.exists() else None


def list_backups() -> None:
    """Print all available backup files."""
    print("\nAvailable backups:")
    print("=" * 60)
    for tier in ("daily", "weekly"):
        d = BACKUP_ROOT / tier
        files = sorted(d.glob("*.bak")) if d.exists() else []
        if not files:
            print(f"  [{tier}] (empty)")
            continue
        print(f"  [{tier}]")
        for f in files:
            size_kb = f.stat().st_size // 1024
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            valid = "OK" if verify_sqlite(f) else "CORRUPT"
            print(f"    {f.name:<44} {size_kb:>6} KB  {mtime}  [{valid}]")


# ──────────────────────────────────────────────────────────────────────────────
# Restore logic
# ──────────────────────────────────────────────────────────────────────────────


def restore_one(db_name: str, backup_file: Path, destination: Path, force: bool) -> bool:
    """Restore a single DB from backup. Returns True on success."""
    if not verify_sqlite(backup_file):
        print(f"  ERROR  {backup_file.name}: backup file is missing or corrupt")
        return False

    # Safety: if destination is healthy and force not set, confirm
    if destination.exists() and destination.stat().st_size > 0 and not force:
        resp = (
            input(f"  WARNING: {destination} already exists and appears healthy. Overwrite? [y/N] ")
            .strip()
            .lower()
        )
        if resp != "y":
            print(f"  SKIP   {db_name}: user declined overwrite")
            return False

    # Create parent dir if needed
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(str(backup_file), str(destination))
        size_kb = destination.stat().st_size // 1024
        print(f"  OK     {db_name} restored from {backup_file.name} ({size_kb} KB)")
        return True
    except OSError as e:
        print(f"  ERROR  {db_name}: copy failed -- {e}")
        return False


def run_restore(
    db_filter: str | None,
    date_str: str | None,
    tier: str,
    force: bool,
) -> int:
    """Run restore operation. Returns exit code."""
    targets = {db_filter: DATABASES[db_filter]} if db_filter else dict(DATABASES)

    if not (BACKUP_ROOT / tier).exists():
        print(f"ERROR: Backup tier '{tier}' not found at {BACKUP_ROOT / tier}")
        print("Run backup_db.py first to create backups.")
        return 2

    label = date_str or "latest"
    print(f"\nRestore ({tier} / {label})")
    print("=" * 50)

    results = []
    for db_name, dest in targets.items():
        if date_str:
            backup_file = find_backup_by_date(db_name, tier, date_str)
            if not backup_file:
                print(f"  MISSING  {db_name}: no backup found for {date_str} in [{tier}]")
                results.append(False)
                continue
        else:
            backup_file = find_latest_backup(db_name, tier)
            if not backup_file:
                print(f"  MISSING  {db_name}: no backups found in [{tier}]")
                results.append(False)
                continue

        ok = restore_one(db_name, backup_file, dest, force)
        results.append(ok)

    success = sum(results)
    total = len(results)
    print(f"\n{success}/{total} databases restored.")

    if success == 0:
        return 2
    if success < total:
        return 1
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# Auto-restore (called by health check)
# ──────────────────────────────────────────────────────────────────────────────


def auto_restore_if_corrupt(db_name: str) -> bool:
    """Silently restore db_name if it is missing or 0-byte. Returns True if restored."""
    dest = DATABASES.get(db_name)
    if not dest:
        return False

    needs_restore = (not dest.exists()) or (dest.stat().st_size == 0)
    if not needs_restore:
        return False

    print(f"[auto-restore] {db_name} is missing/corrupt -- attempting restore...")
    backup = find_latest_backup(db_name, "daily")
    if not backup:
        backup = find_latest_backup(db_name, "weekly")
    if not backup:
        print(f"[auto-restore] No backup found for {db_name}")
        return False

    return restore_one(db_name, backup, dest, force=True)


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────


def main() -> int:
    """Restore one or more databases from backup."""
    parser = argparse.ArgumentParser(description="Restore sports-betting databases from backup")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--date", metavar="YYYY-MM-DD", help="Restore from specific date")
    parser.add_argument(
        "--db",
        choices=list(DATABASES.keys()),
        help="Restore only this database",
    )
    parser.add_argument(
        "--weekly",
        action="store_true",
        help="Use weekly backup tier instead of daily",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation when overwriting healthy database",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify latest backup integrity without restoring",
    )
    args = parser.parse_args()

    if args.list:
        list_backups()
        return 0

    if args.verify_only:
        list_backups()
        return 0

    tier = "weekly" if args.weekly else "daily"
    return run_restore(
        db_filter=args.db,
        date_str=args.date,
        tier=tier,
        force=args.force,
    )


if __name__ == "__main__":
    sys.exit(main())
