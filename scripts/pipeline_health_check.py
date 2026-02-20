"""Pipeline Health Check — Pre-flight validation for automated runs.

Validates that all prerequisites are met before running the nightly
or morning betting pipeline. Checks cover environment, data, model,
and system resources.

Usage:
    python scripts/pipeline_health_check.py            # Human-readable
    python scripts/pipeline_health_check.py --json     # Machine-readable

Exit codes:
    0 = healthy (all checks pass)
    1 = warnings (non-critical issues, pipeline can proceed)
    2 = critical (pipeline should not run)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import (  # noqa: E402
    BARTTORVIK_DATA_DIR,
    DATABASE_PATH,
    PROCESSED_DATA_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Thresholds
MIN_DISK_SPACE_MB = 500
DATA_FRESHNESS_HOURS = 48
LOCK_STALE_MINUTES = 60

LOCK_FILE = PROJECT_ROOT / "logs" / "pipeline.lock"


class CheckResult:
    """Result of a single health check."""

    def __init__(self, name: str, passed: bool, level: str, message: str):
        self.name = name
        self.passed = passed
        self.level = level  # "ok", "warning", "critical"
        self.message = message

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "level": self.level,
            "message": self.message,
        }


def check_venv() -> CheckResult:
    """Verify virtual environment exists and has key packages."""
    venv_python = PROJECT_ROOT / "venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        return CheckResult("venv", False, "critical", f"venv not found: {venv_python}")

    # Check a key dependency is importable
    try:
        import pandas  # noqa: F401

        return CheckResult("venv", True, "ok", "venv active and pandas importable")
    except ImportError:
        return CheckResult("venv", False, "critical", "pandas not importable — venv may be broken")


def check_database() -> CheckResult:
    """Verify SQLite database is accessible."""
    if not DATABASE_PATH.exists():
        return CheckResult("database", False, "critical", f"DB not found: {DATABASE_PATH}")

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        required = {"bets", "predictions", "team_ratings"}
        missing = required - set(tables)
        if missing:
            return CheckResult(
                "database", False, "critical", f"Missing tables: {', '.join(missing)}"
            )

        return CheckResult("database", True, "ok", f"DB OK — {len(tables)} tables")
    except sqlite3.Error as e:
        return CheckResult("database", False, "critical", f"DB error: {e}")


def check_api_keys() -> CheckResult:
    """Verify required API keys are present in environment."""
    # Load .env if not already in environment
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        _load_env_file(env_path)

    cbbdata_key = os.environ.get("CBBDATA_API_KEY", "")
    odds_key = os.environ.get("ODDS_API_KEY", "")

    issues = []
    if not cbbdata_key:
        issues.append("CBBDATA_API_KEY missing (Barttorvik scraping will fail)")
    if not odds_key:
        issues.append("ODDS_API_KEY missing (odds fetching limited)")

    if not cbbdata_key:
        return CheckResult("api_keys", False, "warning", "; ".join(issues))

    if issues:
        return CheckResult("api_keys", True, "warning", "; ".join(issues))

    return CheckResult("api_keys", True, "ok", "API keys present")


def check_model_file() -> CheckResult:
    """Verify trained model file exists."""
    model_path = PROCESSED_DATA_DIR / "ncaab_elo_model.pkl"
    if not model_path.exists():
        return CheckResult(
            "model_file",
            False,
            "critical",
            "No trained model — run train_ncaab_elo.py first",
        )

    age_hours = (time.time() - model_path.stat().st_mtime) / 3600
    if age_hours > 48:
        return CheckResult(
            "model_file",
            True,
            "warning",
            f"Model is {age_hours:.0f}h old — consider retraining",
        )

    return CheckResult("model_file", True, "ok", f"Model exists ({age_hours:.1f}h old)")


def check_data_freshness() -> CheckResult:
    """Check that game data is recent enough."""
    games_dir = PROJECT_ROOT / "data" / "raw" / "ncaab"
    season_file = games_dir / "ncaab_games_2026.parquet"

    if not season_file.exists():
        return CheckResult(
            "data_freshness",
            False,
            "critical",
            "No 2026 game data — run fetch_season_data.py first",
        )

    age_hours = (time.time() - season_file.stat().st_mtime) / 3600
    if age_hours > DATA_FRESHNESS_HOURS:
        return CheckResult(
            "data_freshness",
            True,
            "warning",
            f"Game data is {age_hours:.0f}h old (>{DATA_FRESHNESS_HOURS}h threshold)",
        )

    return CheckResult("data_freshness", True, "ok", f"Game data is {age_hours:.1f}h old")


def check_barttorvik_cache() -> CheckResult:
    """Verify Barttorvik ratings cache exists."""
    if not BARTTORVIK_DATA_DIR.exists():
        return CheckResult(
            "barttorvik_cache",
            False,
            "warning",
            "Barttorvik cache directory missing",
        )

    files = list(BARTTORVIK_DATA_DIR.glob("barttorvik_ratings_*.parquet"))
    if not files:
        return CheckResult(
            "barttorvik_cache",
            False,
            "warning",
            "No Barttorvik parquet files cached",
        )

    newest = max(files, key=lambda f: f.stat().st_mtime)
    age_hours = (time.time() - newest.stat().st_mtime) / 3600

    return CheckResult(
        "barttorvik_cache",
        True,
        "ok",
        f"{len(files)} files cached, newest: {newest.name} ({age_hours:.1f}h old)",
    )


def check_disk_space() -> CheckResult:
    """Verify sufficient disk space."""
    usage = shutil.disk_usage(PROJECT_ROOT)
    free_mb = usage.free / (1024 * 1024)

    if free_mb < MIN_DISK_SPACE_MB:
        return CheckResult(
            "disk_space",
            False,
            "critical",
            f"Only {free_mb:.0f}MB free (<{MIN_DISK_SPACE_MB}MB minimum)",
        )

    return CheckResult("disk_space", True, "ok", f"{free_mb:.0f}MB free")


def check_stale_lock() -> CheckResult:
    """Check for stale pipeline lock file."""
    if not LOCK_FILE.exists():
        return CheckResult("stale_lock", True, "ok", "No lock file")

    age_minutes = (time.time() - LOCK_FILE.stat().st_mtime) / 60

    if age_minutes > LOCK_STALE_MINUTES:
        return CheckResult(
            "stale_lock",
            False,
            "warning",
            f"Stale lock file ({age_minutes:.0f}min old) — previous run may have crashed. "
            f"Delete {LOCK_FILE} to clear.",
        )

    return CheckResult(
        "stale_lock",
        False,
        "critical",
        f"Pipeline lock active ({age_minutes:.0f}min old) — another run in progress?",
    )


def check_elo_ratings_csv() -> CheckResult:
    """Verify Elo ratings CSV exists for dashboard generation."""
    csv_path = PROCESSED_DATA_DIR / "ncaab_elo_ratings_current.csv"
    if not csv_path.exists():
        return CheckResult(
            "elo_ratings_csv",
            True,
            "warning",
            "Elo ratings CSV missing — dashboard generation will fail",
        )

    return CheckResult("elo_ratings_csv", True, "ok", "Elo ratings CSV exists")


def _load_env_file(env_path: Path) -> None:
    """Load .env file into os.environ (simple key=value parser)."""
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip("'\"")
                    if key and key not in os.environ:
                        os.environ[key] = value
    except OSError:
        pass


def run_all_checks() -> list[CheckResult]:
    """Run all health checks and return results."""
    checks = [
        check_venv,
        check_database,
        check_api_keys,
        check_model_file,
        check_data_freshness,
        check_barttorvik_cache,
        check_disk_space,
        check_stale_lock,
        check_elo_ratings_csv,
    ]

    results = []
    for check_fn in checks:
        try:
            result = check_fn()
        except Exception as e:
            result = CheckResult(check_fn.__name__, False, "critical", f"Check crashed: {e}")
        results.append(result)

    return results


def determine_exit_code(results: list[CheckResult]) -> int:
    """Determine overall exit code from check results.

    Returns:
        0 = healthy, 1 = warnings, 2 = critical
    """
    has_critical = any(r.level == "critical" and not r.passed for r in results)
    has_warning = any(r.level == "warning" and not r.passed for r in results)

    if has_critical:
        return 2
    if has_warning:
        return 1
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline pre-flight health check")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    args = parser.parse_args()

    results = run_all_checks()
    exit_code = determine_exit_code(results)

    if args.json:
        output = {
            "timestamp": datetime.now().isoformat(),
            "exit_code": exit_code,
            "status": {0: "healthy", 1: "warnings", 2: "critical"}[exit_code],
            "checks": [r.to_dict() for r in results],
        }
        print(json.dumps(output, indent=2))
    else:
        status_label = {0: "HEALTHY", 1: "WARNINGS", 2: "CRITICAL"}[exit_code]
        print(f"\nPipeline Health Check — {status_label}")
        print("=" * 50)

        for r in results:
            icon = "OK" if r.passed else r.level.upper()
            print(f"  [{icon:>8}] {r.name}: {r.message}")

        passed = sum(1 for r in results if r.passed)
        print(f"\n{passed}/{len(results)} checks passed")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
