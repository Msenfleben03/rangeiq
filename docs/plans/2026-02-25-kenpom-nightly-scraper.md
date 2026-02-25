# KenPom Nightly Scraper + Pipeline Merge Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Record daily KenPom rating snapshots to SQLite for future backtesting, and merge the nightly/morning pipelines into a single 7 AM job.

**Architecture:** The existing `pipelines/kenpom_fetcher.py` already scrapes kenpom.com via `kenpompy` and caches to parquet. We add a parallel SQLite storage path (new `kenpom_ratings` table in `betting.db`) and a thin DB-write function. The `fetch_kenpom_data.py --daily-only` CLI already orchestrates the scrape. We add a `--store-db` flag so the nightly pipeline writes to both parquet (for backtesting lookups) and SQLite (for historical tracking). Then we merge `nightly-refresh.ps1` + `morning-betting.ps1` into a single `daily-pipeline.ps1` running at 7 AM.

**Tech Stack:** Python 3.11+, kenpompy, SQLite, PowerShell, Windows Task Scheduler

---

## Task 1: Environment Setup (Credentials + Dependency)

**Files:**
- Modify: `requirements.txt`
- Create credentials entry (user will handle `.env` manually for security)

**Step 1: Add kenpompy to requirements.txt**

In `requirements.txt`, add under the "SPORTS DATA SOURCES" section:

```
# KenPom efficiency ratings (scrapes kenpom.com, requires subscription)
kenpompy>=0.9.0
```

**Step 2: Install kenpompy**

Run: `venv/Scripts/pip.exe install kenpompy`
Expected: Successfully installed kenpompy

**Step 3: Verify kenpompy import works**

Run: `venv/Scripts/python.exe -c "import kenpompy; print('kenpompy OK')"`
Expected: `kenpompy OK`

**Step 4: Add credentials to .env**

The user will add these lines to `.env` (DO NOT commit .env):
```
KENPOM_EMAIL=msenfleben03@gmail.com
KENPOM_PASSWORD=Insights3$ixty
```

Verify settings.py reads them:
Run: `venv/Scripts/python.exe -c "from config.settings import KENPOM_EMAIL, KENPOM_PASSWORD; print(f'Email: {KENPOM_EMAIL[:5]}..., Pass: {\"set\" if KENPOM_PASSWORD else \"missing\"}')"`
Expected: `Email: msenf..., Pass: set`

**Step 5: Commit**

```bash
git add requirements.txt
git commit -m "chore: add kenpompy dependency for KenPom nightly scraping"
```

---

## Task 2: Database Schema (kenpom_ratings table)

**Files:**
- Modify: `tracking/database.py` (add table creation in `_initialize_schema`)
- Test: `tests/test_kenpom_scraper_db.py` (new file)

**Step 1: Write the failing test**

Create `tests/test_kenpom_scraper_db.py`:

```python
"""Tests for KenPom SQLite storage (kenpom_ratings table)."""

from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from tracking.database import BettingDatabase


@pytest.fixture()
def db(tmp_path):
    """Fresh database in temp directory."""
    db_path = tmp_path / "test_betting.db"
    return BettingDatabase(str(db_path))


class TestKenpomRatingsTable:
    """Test kenpom_ratings table creation and constraints."""

    def test_table_exists(self, db):
        """kenpom_ratings table is created on init."""
        rows = db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='kenpom_ratings'"
        )
        assert len(rows) == 1

    def test_insert_rating(self, db):
        """Can insert a KenPom rating row."""
        with db.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO kenpom_ratings
                   (team, conf, season, snapshot_date, rank, adj_em, adj_o, adj_d, adj_t,
                    luck, sos_adj_em, sos_opp_o, sos_opp_d, ncsos_adj_em, w_l, seed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("Houston", "B12", 2026, "2026-02-25", 1, 36.0, 126.0, 90.0, 63.0,
                 0.03, 8.5, 108.5, 100.0, 5.0, "25-1", "1"),
            )
        rows = db.execute_query("SELECT * FROM kenpom_ratings WHERE team = 'Houston'")
        assert len(rows) == 1
        assert rows[0]["adj_em"] == pytest.approx(36.0)

    def test_unique_constraint_prevents_duplicates(self, db):
        """Duplicate (team, season, snapshot_date) raises IntegrityError."""
        insert_sql = """INSERT INTO kenpom_ratings
            (team, conf, season, snapshot_date, rank, adj_em, adj_o, adj_d, adj_t)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        params = ("Houston", "B12", 2026, "2026-02-25", 1, 36.0, 126.0, 90.0, 63.0)
        with db.get_cursor() as cursor:
            cursor.execute(insert_sql, params)
        with pytest.raises(Exception):
            with db.get_cursor() as cursor:
                cursor.execute(insert_sql, params)

    def test_different_dates_allowed(self, db):
        """Same team on different dates inserts as separate rows."""
        insert_sql = """INSERT INTO kenpom_ratings
            (team, conf, season, snapshot_date, rank, adj_em, adj_o, adj_d, adj_t)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        with db.get_cursor() as cursor:
            cursor.execute(insert_sql, ("Houston", "B12", 2026, "2026-02-25", 1, 36.0, 126.0, 90.0, 63.0))
        with db.get_cursor() as cursor:
            cursor.execute(insert_sql, ("Houston", "B12", 2026, "2026-02-26", 1, 36.5, 126.5, 89.5, 63.0))
        rows = db.execute_query("SELECT * FROM kenpom_ratings WHERE team = 'Houston'")
        assert len(rows) == 2
```

**Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_kenpom_scraper_db.py -v`
Expected: FAIL (table `kenpom_ratings` does not exist)

**Step 3: Add kenpom_ratings table to database.py**

In `tracking/database.py`, inside `_initialize_schema()`, after the `odds_snapshots` table creation and migration block (after line ~194), add:

```python
            # KenPom daily ratings snapshots
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS kenpom_ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team TEXT NOT NULL,
                    conf TEXT,
                    season INTEGER NOT NULL,
                    snapshot_date DATE NOT NULL,
                    rank INTEGER,
                    adj_em REAL,
                    adj_o REAL,
                    adj_o_rk INTEGER,
                    adj_d REAL,
                    adj_d_rk INTEGER,
                    adj_t REAL,
                    adj_t_rk INTEGER,
                    luck REAL,
                    luck_rk INTEGER,
                    sos_adj_em REAL,
                    sos_adj_em_rk INTEGER,
                    sos_opp_o REAL,
                    sos_opp_o_rk INTEGER,
                    sos_opp_d REAL,
                    sos_opp_d_rk INTEGER,
                    ncsos_adj_em REAL,
                    ncsos_adj_em_rk INTEGER,
                    w_l TEXT,
                    seed TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE(team, season, snapshot_date)
                )
            """
            )
```

**Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_kenpom_scraper_db.py -v`
Expected: 4 passed

**Step 5: Run existing database tests to check for regressions**

Run: `venv/Scripts/python.exe -m pytest tests/ -k "test_daily_run or test_forecasting_db" -v --timeout=30`
Expected: No new failures

**Step 6: Commit**

```bash
git add tracking/database.py tests/test_kenpom_scraper_db.py
git commit -m "feat: add kenpom_ratings table to SQLite schema"
```

---

## Task 3: DB Storage Function

**Files:**
- Modify: `pipelines/kenpom_fetcher.py` (add `store_snapshot_to_db` function)
- Modify: `scripts/fetch_kenpom_data.py` (add `--store-db` flag)
- Test: `tests/test_kenpom_scraper_db.py` (add tests)

**Step 1: Write the failing test**

Add to `tests/test_kenpom_scraper_db.py`:

```python
import pandas as pd
from pipelines.kenpom_fetcher import store_snapshot_to_db


class TestStoreSnapshotToDb:
    """Test store_snapshot_to_db function."""

    def _make_snapshot_df(self, date_str="2026-02-25"):
        """Create a minimal KenPom snapshot DataFrame matching normalize output."""
        return pd.DataFrame({
            "rank": pd.array([1, 2, 3], dtype="Int64"),
            "team": ["Houston", "Duke", "Arizona"],
            "conf": ["B12", "ACC", "B12"],
            "w_l": ["25-1", "24-2", "23-2"],
            "adj_em": [36.0, 34.0, 33.0],
            "adj_o": [126.0, 125.0, 124.0],
            "adj_o_rk": pd.array([1, 2, 3], dtype="Int64"),
            "adj_d": [90.0, 91.0, 91.5],
            "adj_d_rk": pd.array([1, 2, 3], dtype="Int64"),
            "adj_t": [63.0, 66.0, 70.0],
            "adj_t_rk": pd.array([10, 250, 26], dtype="Int64"),
            "luck": [0.042, -0.015, 0.028],
            "luck_rk": pd.array([50, 200, 100], dtype="Int64"),
            "sos_adj_em": [8.50, 9.10, 7.80],
            "sos_adj_em_rk": pd.array([10, 5, 15], dtype="Int64"),
            "sos_opp_o": [108.5, 109.1, 107.8],
            "sos_opp_o_rk": pd.array([10, 5, 15], dtype="Int64"),
            "sos_opp_d": [100.0, 100.0, 100.0],
            "sos_opp_d_rk": pd.array([10, 5, 15], dtype="Int64"),
            "ncsos_adj_em": [5.0, 4.5, 6.2],
            "ncsos_adj_em_rk": pd.array([20, 30, 10], dtype="Int64"),
            "seed": ["1", "1", "2"],
            "year": [2026, 2026, 2026],
            "date": pd.to_datetime([date_str] * 3),
        })

    def test_stores_all_teams(self, db):
        """All teams from snapshot are stored in DB."""
        df = self._make_snapshot_df()
        count = store_snapshot_to_db(df, 2026, str(db.db_path))
        assert count == 3

    def test_data_matches(self, db):
        """Stored values match input DataFrame."""
        df = self._make_snapshot_df()
        store_snapshot_to_db(df, 2026, str(db.db_path))
        rows = db.execute_query(
            "SELECT * FROM kenpom_ratings WHERE team = 'Houston'"
        )
        assert len(rows) == 1
        assert rows[0]["adj_em"] == pytest.approx(36.0)
        assert rows[0]["adj_o"] == pytest.approx(126.0)
        assert rows[0]["snapshot_date"] == "2026-02-25"
        assert rows[0]["season"] == 2026

    def test_idempotent_upsert(self, db):
        """Running twice on same date doesn't create duplicates."""
        df = self._make_snapshot_df()
        store_snapshot_to_db(df, 2026, str(db.db_path))
        count = store_snapshot_to_db(df, 2026, str(db.db_path))
        assert count == 3  # 3 upserted (replaced), not 6
        rows = db.execute_query("SELECT COUNT(*) as n FROM kenpom_ratings")
        assert rows[0]["n"] == 3

    def test_different_dates_accumulate(self, db):
        """Snapshots from different dates accumulate."""
        df1 = self._make_snapshot_df("2026-02-25")
        df2 = self._make_snapshot_df("2026-02-26")
        store_snapshot_to_db(df1, 2026, str(db.db_path))
        store_snapshot_to_db(df2, 2026, str(db.db_path))
        rows = db.execute_query("SELECT COUNT(*) as n FROM kenpom_ratings")
        assert rows[0]["n"] == 6  # 3 teams x 2 dates

    def test_empty_df_returns_zero(self, db):
        """Empty DataFrame stores nothing, returns 0."""
        df = pd.DataFrame()
        count = store_snapshot_to_db(df, 2026, str(db.db_path))
        assert count == 0
```

**Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_kenpom_scraper_db.py::TestStoreSnapshotToDb -v`
Expected: FAIL (ImportError — `store_snapshot_to_db` does not exist)

**Step 3: Implement store_snapshot_to_db in kenpom_fetcher.py**

Add to `pipelines/kenpom_fetcher.py`, after the `append_to_cache` function (before the `KenPomFetcher` class):

```python
# ---------------------------------------------------------------------------
# SQLite Storage
# ---------------------------------------------------------------------------


def store_snapshot_to_db(
    df: pd.DataFrame,
    season: int,
    db_path: str = "data/betting.db",
) -> int:
    """Store a KenPom ratings snapshot to the kenpom_ratings SQLite table.

    Uses INSERT OR REPLACE for idempotent daily writes. The UNIQUE constraint
    on (team, season, snapshot_date) prevents duplicates.

    Args:
        df: Normalized KenPom ratings DataFrame (from normalize_kenpom_df).
        season: Season year.
        db_path: Path to SQLite database.

    Returns:
        Number of rows stored.
    """
    if df.empty:
        return 0

    import sqlite3

    snapshot_date = date.today().isoformat()
    if "date" in df.columns:
        first_date = pd.to_datetime(df["date"].iloc[0])
        snapshot_date = first_date.strftime("%Y-%m-%d")

    # Column mapping from DataFrame columns to DB columns
    db_columns = [
        "team", "conf", "season", "snapshot_date", "rank",
        "adj_em", "adj_o", "adj_o_rk", "adj_d", "adj_d_rk",
        "adj_t", "adj_t_rk", "luck", "luck_rk",
        "sos_adj_em", "sos_adj_em_rk", "sos_opp_o", "sos_opp_o_rk",
        "sos_opp_d", "sos_opp_d_rk", "ncsos_adj_em", "ncsos_adj_em_rk",
        "w_l", "seed",
    ]
    placeholders = ", ".join(["?"] * len(db_columns))
    col_names = ", ".join(db_columns)
    sql = f"INSERT OR REPLACE INTO kenpom_ratings ({col_names}) VALUES ({placeholders})"  # nosec B608

    conn = sqlite3.connect(db_path)
    count = 0
    try:
        cursor = conn.cursor()
        for _, row in df.iterrows():
            values = (
                row.get("team"),
                row.get("conf"),
                season,
                snapshot_date,
                _to_py(row.get("rank")),
                _to_py(row.get("adj_em")),
                _to_py(row.get("adj_o")),
                _to_py(row.get("adj_o_rk")),
                _to_py(row.get("adj_d")),
                _to_py(row.get("adj_d_rk")),
                _to_py(row.get("adj_t")),
                _to_py(row.get("adj_t_rk")),
                _to_py(row.get("luck")),
                _to_py(row.get("luck_rk")),
                _to_py(row.get("sos_adj_em")),
                _to_py(row.get("sos_adj_em_rk")),
                _to_py(row.get("sos_opp_o")),
                _to_py(row.get("sos_opp_o_rk")),
                _to_py(row.get("sos_opp_d")),
                _to_py(row.get("sos_opp_d_rk")),
                _to_py(row.get("ncsos_adj_em")),
                _to_py(row.get("ncsos_adj_em_rk")),
                row.get("w_l"),
                row.get("seed"),
            )
            cursor.execute(sql, values)
            count += 1
        conn.commit()
    finally:
        conn.close()

    logger.info("Stored %d KenPom ratings to DB for season %d (%s)", count, season, snapshot_date)
    return count


def _to_py(val: Any) -> Any:
    """Convert pandas/numpy scalar to Python native type for SQLite."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if hasattr(val, "item"):
        return val.item()
    return val
```

**Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_kenpom_scraper_db.py -v`
Expected: 9 passed (4 from Task 2 + 5 new)

**Step 5: Add --store-db flag to fetch_kenpom_data.py**

In `scripts/fetch_kenpom_data.py`, add argument after `--verbose`:

```python
    parser.add_argument(
        "--store-db",
        action="store_true",
        help="Also store snapshot to SQLite kenpom_ratings table",
    )
```

And in the `args.daily_only` block (around line 98-105), after the existing `_print_summary` call, add:

```python
    if args.daily_only:
        print("Fetching today's KenPom snapshot...")
        df = fetcher.fetch_current_snapshot()
        if df.empty:
            print("FAILED: No data retrieved.")
            return 1
        _print_summary(df, "Current")
        if args.store_db:
            from pipelines.kenpom_fetcher import store_snapshot_to_db
            season = df["year"].iloc[0] if "year" in df.columns else date.today().year
            count = store_snapshot_to_db(df, int(season))
            print(f"Stored {count} ratings to SQLite (kenpom_ratings table)")
        return 0
```

**Step 6: Run ruff check**

Run: `venv/Scripts/python.exe -m ruff check pipelines/kenpom_fetcher.py scripts/fetch_kenpom_data.py`
Expected: No errors (or fix any that appear)

**Step 7: Commit**

```bash
git add pipelines/kenpom_fetcher.py scripts/fetch_kenpom_data.py tests/test_kenpom_scraper_db.py
git commit -m "feat: add KenPom SQLite storage with store_snapshot_to_db"
```

---

## Task 4: Add KenPom Step to Nightly Pipeline

**Files:**
- Modify: `scripts/nightly-refresh.ps1` (add scrape_kenpom step)

**Step 1: Add scrape_kenpom step to nightly-refresh.ps1**

In `scripts/nightly-refresh.ps1`, in the `$steps` ordered dictionary (around line 60-103), add a new step after `scrape_barttorvik` and before `fetch_opening_odds`:

```powershell
    scrape_kenpom = @{
        script    = "fetch_kenpom_data.py"
        args      = @("--daily-only", "--store-db")
        critical  = $false
        timeout   = 120
    }
```

**Step 2: Verify the step definition is valid (dry run)**

Run: `pwsh -File scripts/nightly-refresh.ps1 -DryRun`
Expected: Output shows `scrape_kenpom` step listed between `scrape_barttorvik` and `fetch_opening_odds` with `[DRY RUN]` prefix

**Step 3: Commit**

```bash
git add scripts/nightly-refresh.ps1
git commit -m "feat: add KenPom scraping step to nightly pipeline"
```

---

## Task 5: Merge Nightly + Morning into Single Daily Pipeline

**Files:**
- Create: `scripts/daily-pipeline.ps1` (merged pipeline)
- Modify: `scripts/nightly-refresh.ps1` (add deprecation notice)
- Modify: `scripts/morning-betting.ps1` (add deprecation notice)

**Step 1: Create daily-pipeline.ps1**

Create `scripts/daily-pipeline.ps1` with the merged pipeline. The step order at 7 AM:

1. `health_check` - pre-flight validation (CRITICAL)
2. `fetch_scores` - fetch yesterday's final scores (CRITICAL)
3. `train_elo` - retrain with new results (CRITICAL)
4. `scrape_barttorvik` - today's Barttorvik ratings (non-critical)
5. `scrape_kenpom` - today's KenPom ratings (non-critical)
6. `settle_bets` - settle yesterday's paper bets (non-critical)
7. `predictions` - generate today's predictions + record bets (non-critical)
8. `fetch_opening_odds` - opening odds for today's games (non-critical)
9. `generate_dashboard` - rebuild dashboard data (non-critical)
10. `deploy_dashboard` - push to Vercel (non-critical)

```powershell
<#
.SYNOPSIS
    Unified daily pipeline -- refresh data, settle, predict, dashboard.

.DESCRIPTION
    Single pipeline replacing nightly-refresh.ps1 + morning-betting.ps1.
    Runs all steps in sequence at 7:00 AM ET:
    1. Health check (pre-flight validation)
    2. Fetch latest scores (ESPN API, incremental)
    3. Retrain Elo model with new data
    4. Scrape Barttorvik daily snapshot
    5. Scrape KenPom daily snapshot (store to SQLite)
    6. Settle yesterday's paper bets
    7. Generate today's predictions and record paper bets
    8. Fetch opening odds for today's games
    9. Generate dashboard data bundle
    10. Deploy dashboard to Vercel

    Supports checkpointing, retry, and notification on failure.
    Designed to run via Windows Task Scheduler at 7:00 AM ET daily.

.PARAMETER Force
    Skip checkpoint resume -- run all steps from scratch.

.PARAMETER DryRun
    Preview all steps without executing any Python scripts.

.PARAMETER SkipHealthCheck
    Skip the pre-flight health check step.

.PARAMETER SettleOnly
    Only settle yesterday's bets, skip everything else.

.PARAMETER SkipSettle
    Skip settlement step.

.PARAMETER SkipPredict
    Skip prediction step.

.PARAMETER MaxRetries
    Maximum retry attempts per step (default: 1).

.EXAMPLE
    .\scripts\daily-pipeline.ps1
    .\scripts\daily-pipeline.ps1 -DryRun
    .\scripts\daily-pipeline.ps1 -Force -MaxRetries 2
    .\scripts\daily-pipeline.ps1 -SettleOnly
#>

[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$DryRun,
    [switch]$SkipHealthCheck,
    [switch]$SettleOnly,
    [switch]$SkipSettle,
    [switch]$SkipPredict,
    [int]$MaxRetries = 1
)

$ErrorActionPreference = "Stop"

# Load shared functions
. "$PSScriptRoot\pipeline-common.ps1"

# Load environment variables
Import-DotEnv

# Initialize logging
$logFile = Initialize-PipelineLog -PipelineType "daily"
Write-Log "INFO" "Daily pipeline starting (DryRun=$DryRun, Force=$Force, SettleOnly=$SettleOnly)"

# Define pipeline steps
$steps = [ordered]@{
    health_check = @{
        script    = "pipeline_health_check.py"
        args      = @("--json")
        critical  = $true
        timeout   = 30
    }
    fetch_scores = @{
        script    = "fetch_season_data.py"
        args      = @("--season", "2026", "--incremental", "--no-odds")
        critical  = $true
        timeout   = 300
    }
    train_elo = @{
        script    = "train_ncaab_elo.py"
        args      = @("--end", "2026")
        critical  = $true
        timeout   = 180
    }
    scrape_barttorvik = @{
        script    = "fetch_barttorvik_data.py"
        args      = @("--seasons", "2026", "--scrape")
        critical  = $false
        timeout   = 120
    }
    scrape_kenpom = @{
        script    = "fetch_kenpom_data.py"
        args      = @("--daily-only", "--store-db")
        critical  = $false
        timeout   = 120
    }
    settle_bets = @{
        script    = "daily_run.py"
        args      = @("--settle-only")
        critical  = $false
        timeout   = 120
    }
    predictions = @{
        script    = "daily_run.py"
        args      = @("--skip-settle")
        critical  = $false
        timeout   = 300
    }
    fetch_opening_odds = @{
        script    = "fetch_opening_odds.py"
        args      = @()
        critical  = $false
        timeout   = 180
    }
    generate_dashboard = @{
        script    = "generate_dashboard_data.py"
        args      = @()
        critical  = $false
        timeout   = 60
    }
    deploy_dashboard = @{
        script    = "deploy_dashboard.py"
        args      = @()
        critical  = $false
        timeout   = 90
    }
}

# Apply flags to skip steps
if ($SkipHealthCheck) {
    $steps.Remove("health_check")
    Write-Log "INFO" "Health check skipped (-SkipHealthCheck)"

    if (-not $DryRun) {
        $locked = Acquire-PipelineLock
        if (-not $locked) {
            Write-Log "ERROR" "Cannot acquire pipeline lock -- exiting"
            exit 2
        }
    }
}

if ($SettleOnly) {
    # Only keep health_check and settle_bets
    $keepSteps = @("health_check", "settle_bets")
    $removeSteps = @($steps.Keys | Where-Object { $_ -notin $keepSteps })
    foreach ($s in $removeSteps) { $steps.Remove($s) }
    Write-Log "INFO" "Settle-only mode: running health_check + settle_bets only"
}

if ($SkipSettle) {
    $steps.Remove("settle_bets")
    Write-Log "INFO" "Settlement skipped (-SkipSettle)"
}

if ($SkipPredict) {
    $steps.Remove("predictions")
    Write-Log "INFO" "Predictions skipped (-SkipPredict)"
}

# Check for checkpoint to resume
$checkpoint = $null
if (-not $Force -and -not $DryRun) {
    $checkpoint = Load-Checkpoint -PipelineType "daily"
    if ($checkpoint) {
        Write-Log "INFO" "Resuming from checkpoint (started at $($checkpoint.started_at))"
    }
}

# Initialize state
$today = Get-Date -Format "yyyy-MM-dd"
$state = @{
    date           = $today
    pipeline       = "daily"
    started_at     = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
    steps          = @{}
    overall_status = "running"
}

# Merge checkpoint steps if resuming
if ($checkpoint) {
    foreach ($prop in $checkpoint.steps.PSObject.Properties) {
        $state.steps[$prop.Name] = @{
            status    = $prop.Value.status
            exit_code = $prop.Value.exit_code
            attempt   = $prop.Value.attempt
            error     = $prop.Value.error
        }
    }
}

$hasCriticalFailure = $false
$hasAnyFailure = $false

foreach ($stepName in $steps.Keys) {
    $stepConfig = $steps[$stepName]

    # Skip completed steps (checkpoint resume)
    if ($state.steps.ContainsKey($stepName)) {
        $existing = $state.steps[$stepName]
        if ($existing.status -eq "completed") {
            Write-Log "INFO" "Step [$stepName] already completed (checkpoint) -- skipping"
            continue
        }
    }

    # Skip remaining steps if a critical step failed
    if ($hasCriticalFailure) {
        Write-Log "WARN" "Skipping [$stepName] -- critical failure in earlier step"
        $state.steps[$stepName] = @{
            status    = "skipped"
            exit_code = -1
            attempt   = 0
            error     = "Skipped due to earlier critical failure"
        }
        continue
    }

    Write-Log "INFO" "========== Step: $stepName =========="

    $result = Invoke-PipelineStep `
        -StepName $stepName `
        -Script $stepConfig.script `
        -Arguments $stepConfig.args `
        -TimeoutSeconds $stepConfig.timeout `
        -MaxRetries $MaxRetries `
        -DryRun:$DryRun

    if ($result.exit_code -eq 0) {
        $state.steps[$stepName] = @{
            status    = "completed"
            exit_code = 0
            attempt   = $result.attempt
            duration  = $result.duration
        }

        # Acquire lock AFTER health_check passes (avoids self-deadlock)
        if ($stepName -eq "health_check" -and -not $DryRun) {
            $locked = Acquire-PipelineLock
            if (-not $locked) {
                Write-Log "ERROR" "Cannot acquire pipeline lock -- exiting"
                Release-PipelineLock
                exit 2
            }
        }
    } else {
        $errorMsg = if ($result.stderr) {
            $result.stderr.Substring(0, [Math]::Min(200, $result.stderr.Length))
        } else {
            "Exit code $($result.exit_code)"
        }

        $state.steps[$stepName] = @{
            status    = "failed"
            exit_code = $result.exit_code
            attempt   = $result.attempt
            error     = $errorMsg
        }

        $hasAnyFailure = $true

        if ($stepConfig.critical) {
            $hasCriticalFailure = $true
            Write-Log "ERROR" "CRITICAL step [$stepName] failed -- aborting pipeline"
            Send-PipelineNotification `
                -Title "Daily Pipeline FAILED" `
                -Message "Critical step '$stepName' failed: $errorMsg" `
                -Level "error"
        } else {
            Write-Log "WARN" "Non-critical step [$stepName] failed -- continuing"
        }
    }

    # Save checkpoint after each step
    if (-not $DryRun) {
        Save-Checkpoint -State $state
    }
}

# Determine overall status
if ($hasCriticalFailure) {
    $state.overall_status = "critical_failure"
    $exitCode = 2
} elseif ($hasAnyFailure) {
    $state.overall_status = "partial_failure"
    $exitCode = 1
} else {
    $state.overall_status = "completed"
    $exitCode = 0
}

$state.completed_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")

# Save final state
if (-not $DryRun) {
    Save-Checkpoint -State $state
    Release-PipelineLock
}

# Summary
Write-Log "INFO" "========================================"
Write-Log "INFO" "Daily pipeline: $($state.overall_status.ToUpper())"
Write-Log "INFO" "========================================"

foreach ($stepName in $steps.Keys) {
    if ($state.steps.ContainsKey($stepName)) {
        $s = $state.steps[$stepName]
        $icon = switch ($s.status) {
            "completed" { "OK" }
            "failed"    { "FAIL" }
            "skipped"   { "SKIP" }
            default     { "?" }
        }
        Write-Log "INFO" "  [$icon] $stepName (exit=$($s.exit_code), attempt=$($s.attempt))"
    }
}

if ($exitCode -eq 0) {
    Send-PipelineNotification `
        -Title "Daily Pipeline Success" `
        -Message "All steps completed for $today" `
        -Level "success"
}

Write-Log "INFO" "Log file: $logFile"
exit $exitCode
```

**Step 2: Verify dry run works**

Run: `pwsh -File scripts/daily-pipeline.ps1 -DryRun`
Expected: All 10 steps listed with `[DRY RUN]` prefix, exits with code 0

**Step 3: Add deprecation notices to old scripts**

Add as the first line after `$ErrorActionPreference = "Stop"` in both `nightly-refresh.ps1` and `morning-betting.ps1`:

```powershell
Write-Warning "DEPRECATED: Use daily-pipeline.ps1 instead. This script will be removed in a future version."
```

**Step 4: Commit**

```bash
git add scripts/daily-pipeline.ps1 scripts/nightly-refresh.ps1 scripts/morning-betting.ps1
git commit -m "feat: merge nightly + morning into unified daily-pipeline.ps1"
```

---

## Task 6: Update Task Scheduler

**Files:**
- Modify: `scripts/setup-scheduled-tasks.ps1`

**Step 1: Update task definitions**

Replace the `$Tasks` array in `scripts/setup-scheduled-tasks.ps1` (lines 33-48) with:

```powershell
$Tasks = @(
    @{
        Name        = "SportsBetting-Daily"
        Description = "Daily pipeline: fetch scores, retrain Elo, scrape Barttorvik + KenPom, settle bets, predict, dashboard"
        Script      = Join-Path $ScriptsDir "daily-pipeline.ps1"
        TriggerTime = "07:00"  # 7:00 AM
        Arguments   = "-ExecutionPolicy Bypass -File `"$(Join-Path $ScriptsDir 'daily-pipeline.ps1')`""
    }
)
```

Also update the `.DESCRIPTION` comment (lines 7-9) to:

```powershell
#    Manages one scheduled task:
#    - SportsBetting-Daily     (7:00 AM ET) -- full daily pipeline
```

**Step 2: Verify status output**

Run: `pwsh -File scripts/setup-scheduled-tasks.ps1 -Action status`
Expected: Shows `SportsBetting-Daily` (may show NOT REGISTERED until registered)

**Step 3: Commit**

```bash
git add scripts/setup-scheduled-tasks.ps1
git commit -m "feat: update Task Scheduler for single 7 AM daily pipeline"
```

---

## Task 7: Smoke Test (End-to-End Verification)

**Files:** None (verification only)

**Step 1: Run all new tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_kenpom_scraper_db.py tests/test_kenpom_fetcher.py -v`
Expected: All tests pass (9 new + existing kenpom tests)

**Step 2: Run existing test suite to check for regressions**

Run: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py tests/test_fetch_opening_odds.py -v`
Expected: 34/34 pass (no regressions)

**Step 3: Test the KenPom scrape + DB store end-to-end (manual)**

Run: `venv/Scripts/python.exe scripts/fetch_kenpom_data.py --daily-only --store-db -v`
Expected:
- Prints "Fetching today's KenPom snapshot..."
- Prints team count and top 5
- Prints "Stored N ratings to SQLite (kenpom_ratings table)"

**Step 4: Verify DB has data**

Run: `venv/Scripts/python.exe -c "import sqlite3; conn = sqlite3.connect('data/betting.db'); print(conn.execute('SELECT COUNT(*), snapshot_date FROM kenpom_ratings GROUP BY snapshot_date').fetchall()); conn.close()"`
Expected: Shows today's date with ~360 team ratings

**Step 5: Dry run the merged pipeline**

Run: `pwsh -File scripts/daily-pipeline.ps1 -DryRun`
Expected: All 10 steps listed, exits 0

**Step 6: Run ruff on all modified files**

Run: `venv/Scripts/python.exe -m ruff check pipelines/kenpom_fetcher.py scripts/fetch_kenpom_data.py tracking/database.py tests/test_kenpom_scraper_db.py`
Expected: No errors

**Step 7: Final commit (if any fixups needed)**

```bash
git add -A
git commit -m "test: verify KenPom nightly scraper end-to-end"
```

---

## Summary of Changes

| File | Action | Purpose |
|------|--------|---------|
| `requirements.txt` | Modify | Add kenpompy dependency |
| `.env` | Modify | Add KENPOM_EMAIL + KENPOM_PASSWORD (not committed) |
| `tracking/database.py` | Modify | Add `kenpom_ratings` table to schema |
| `pipelines/kenpom_fetcher.py` | Modify | Add `store_snapshot_to_db()` + `_to_py()` helper |
| `scripts/fetch_kenpom_data.py` | Modify | Add `--store-db` flag |
| `scripts/daily-pipeline.ps1` | Create | Merged nightly + morning pipeline |
| `scripts/nightly-refresh.ps1` | Modify | Add deprecation warning |
| `scripts/morning-betting.ps1` | Modify | Add deprecation warning |
| `scripts/setup-scheduled-tasks.ps1` | Modify | Single 7 AM task definition |
| `tests/test_kenpom_scraper_db.py` | Create | 9 tests for DB storage |

## Post-Implementation

After registering the new task (`.\scripts\setup-scheduled-tasks.ps1 -Action register`):
- **Old tasks**: Manually unregister `SportsBetting-Nightly` and `SportsBetting-Morning` via Task Scheduler or by running the old setup script's unregister first
- **Monitor first run**: Check `logs/pipeline-daily-*.log` after first 7 AM execution
- **Verify accumulation**: After a few days, check `SELECT snapshot_date, COUNT(*) FROM kenpom_ratings GROUP BY snapshot_date` to confirm daily snapshots are accumulating
