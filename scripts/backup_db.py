"""Database backup script with GFS rotation.

Backs up ncaab_betting.db + mlb_data.db to C:\\Users\\msenf\\sports-betting-backups\\
Retention: 7 daily + 4 weekly backups.

Usage:
    python scripts/backup_db.py              # backup all DBs
    python scripts/backup_db.py --list       # show existing backups
    python scripts/backup_db.py --verify     # verify latest backup integrity
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BACKUP_ROOT = Path(r"C:\Users\msenf\sports-betting-backups")

DATABASES = {
    "ncaab_betting.db": PROJECT_ROOT / "data" / "ncaab_betting.db",
    "mlb_data.db": PROJECT_ROOT / "data" / "mlb_data.db",
}

KEEP_DAILY = 7
KEEP_WEEKLY = 4


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def today_str() -> str:
    """Return today's date as YYYY-MM-DD string."""
    return datetime.now().strftime("%Y-%m-%d")


def is_weekly_backup_day() -> bool:
    """Sunday = weekly backup day."""
    return datetime.now().weekday() == 6


def backup_dir(tier: str) -> Path:
    """Return the backup directory for the given tier (daily/weekly)."""
    d = BACKUP_ROOT / tier
    d.mkdir(parents=True, exist_ok=True)
    return d


def verify_sqlite(path: Path) -> bool:
    """Return True if the file is a valid, non-empty SQLite database."""
    if not path.exists() or path.stat().st_size == 0:
        return False
    try:
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA integrity_check")
        conn.close()
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Core backup logic
# ──────────────────────────────────────────────────────────────────────────────


def backup_one(db_name: str, src: Path, tier: str, label: str) -> bool:
    """Copy src to backup directory. Returns True on success."""
    if not src.exists():
        print(f"  SKIP  {db_name}: source file does not exist")
        return False
    if src.stat().st_size == 0:
        print(f"  SKIP  {db_name}: source file is 0 bytes — skipping corrupt DB")
        return False

    dest_filename = f"{db_name}_{label}.bak"
    dest = backup_dir(tier) / dest_filename
    try:
        shutil.copy2(str(src), str(dest))
        size_kb = dest.stat().st_size // 1024
        print(f"  OK    {db_name} -> {dest.name} ({size_kb} KB)")
        return True
    except Exception as e:
        print(f"  ERROR {db_name}: {e}")
        return False


def rotate(tier: str, keep: int) -> None:
    """Delete oldest backups in a tier, keeping `keep` per DB name."""
    d = backup_dir(tier)
    # Group files by db_name prefix (e.g. "ncaab_betting.db", "mlb_data.db")
    by_db: dict[str, list[Path]] = {}
    for f in d.glob("*.bak"):
        # Filename format: {db_name}_{YYYY-MM-DD}.bak
        # db_name can contain dots, so split from the right on underscore+date
        stem = f.stem  # e.g. "ncaab_betting.db_2026-03-05"
        parts = stem.rsplit("_", 1)
        db_key = parts[0] if len(parts) == 2 else stem
        by_db.setdefault(db_key, []).append(f)

    for db_key, files in by_db.items():
        files_sorted = sorted(files, key=lambda x: x.stat().st_mtime)
        excess = len(files_sorted) - keep
        for old in files_sorted[:excess]:
            old.unlink()
            print(f"  PURGE {old.name}")


def run_backup() -> int:
    """Run a full backup. Returns exit code (0=success, 1=partial/total failure)."""
    label = today_str()
    print(f"\nBackup -- {label}")
    print("=" * 50)

    results = []
    for db_name, src in DATABASES.items():
        ok = backup_one(db_name, src, "daily", label)
        results.append(ok)
        if ok and is_weekly_backup_day():
            backup_one(db_name, src, "weekly", label)

    print("\nRotating old backups...")
    rotate("daily", KEEP_DAILY)
    rotate("weekly", KEEP_WEEKLY)

    success_count = sum(results)
    total = len(results)
    print(f"\n{success_count}/{total} databases backed up successfully.")

    if success_count == 0:
        print("CRITICAL: No databases were backed up.")
        return 1
    return 0


# ──────────────────────────────────────────────────────────────────────────────
# List / verify commands
# ──────────────────────────────────────────────────────────────────────────────


def list_backups() -> None:
    """Print all existing backup files."""
    print("\nExisting backups:")
    print("=" * 60)
    for tier in ("daily", "weekly"):
        d = backup_dir(tier)
        files = sorted(d.glob("*.bak"))
        if not files:
            print(f"  [{tier}] (empty)")
            continue
        print(f"  [{tier}]")
        for f in files:
            size_kb = f.stat().st_size // 1024
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"    {f.name:<44} {size_kb:>6} KB  {mtime}")


def verify_latest() -> int:
    """Verify the most recent backup of each DB in the daily tier."""
    print("\nVerifying latest backups...")
    print("=" * 50)
    d = backup_dir("daily")
    ok_count = 0
    for db_name in DATABASES:
        candidates = sorted(d.glob(f"{db_name}_*.bak"), key=lambda x: x.stat().st_mtime)
        if not candidates:
            print(f"  MISSING  {db_name}: no daily backup found")
            continue
        latest = candidates[-1]
        if verify_sqlite(latest):
            size_kb = latest.stat().st_size // 1024
            print(f"  OK       {latest.name} ({size_kb} KB)")
            ok_count += 1
        else:
            print(f"  CORRUPT  {latest.name}: integrity check failed")
    return 0 if ok_count == len(DATABASES) else 1


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────


def main() -> int:
    """Run backup, list, or verify command."""
    parser = argparse.ArgumentParser(description="Backup sports-betting databases")
    parser.add_argument("--list", action="store_true", help="List existing backups")
    parser.add_argument("--verify", action="store_true", help="Verify latest backup integrity")
    args = parser.parse_args()

    if args.list:
        list_backups()
        return 0
    if args.verify:
        return verify_latest()
    return run_backup()


if __name__ == "__main__":
    sys.exit(main())
