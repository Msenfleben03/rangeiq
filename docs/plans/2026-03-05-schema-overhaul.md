# Schema Overhaul — Per-Sport DBs + Data Enrichment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split the monolithic `betting.db` into per-sport databases, add MLB betting/tracking tables to `mlb_data.db`, store Barttorvik four-factor data that is currently fetched but discarded, add MLB umpire-game linkage and linescore tables, and add F5-aware odds storage.

**Architecture:** Each sport gets its own SQLite file — `ncaab_betting.db` and `mlb_data.db`. No `sport` column needed in any table. `mlb_data.db` becomes the single source of truth for all MLB data (feature store + bet tracking). `ncaab_betting.db` holds NCAAB ratings, bets, predictions, odds, and Barttorvik four factors. `config/settings.py` exports sport-specific paths used by all consumers.

**Tech Stack:** Python 3.11+, SQLite (raw, no ORM), pandas (parquet ingestion), pytest

---

## Overview of Changes

| Component | Change |
|-----------|--------|
| `config/settings.py` | Add `NCAAB_DATABASE_PATH`, `MLB_DATABASE_PATH`; keep `DATABASE_PATH` as alias |
| `tracking/database.py` | Rebuild ncaab_betting.db schema: drop `sport`, drop `actual_profit_loss`, add CLV components, add `market_type` to odds_snapshots, add `barttorvik_ratings` wide table, add `prop_bets`, add `schema_version` |
| `scripts/mlb_init_db.py` | Add `bets`, `prop_bets`, `odds_snapshots` (with `market_type`), `game_umpire`, `linescore` tables; bump SCHEMA_VERSION to 2 |
| `pipelines/barttorvik_scraper.py` | Scrape four-factor columns (efg_o/d, tov_o/d, orb, drb, ftr_o/d) from HTML table |
| NCAAB consumer scripts | Replace `DATABASE_PATH` with `NCAAB_DATABASE_PATH` |
| MLB consumer scripts | Replace `DATABASE_PATH` with `MLB_DATABASE_PATH` |

---

## Task 1: Update `config/settings.py` — Sport-Specific DB Paths

**Files:**
- Modify: `config/settings.py:19`

**Step 1: Replace the single DATABASE_PATH with sport-specific paths**

```python
# Before (line 19):
DATABASE_PATH = DATA_DIR / "betting.db"

# After:
NCAAB_DATABASE_PATH = DATA_DIR / "ncaab_betting.db"
MLB_DATABASE_PATH   = DATA_DIR / "mlb_data.db"
DATABASE_PATH       = NCAAB_DATABASE_PATH  # backwards-compat alias; NCAAB consumers use this
```

**Step 2: Run existing tests to verify nothing broke**

```bash
cd C:\Users\msenf\sports-betting
venv/Scripts/python.exe -m pytest tests/test_setup.py tests/test_model_persistence.py -v
```

Expected: all pass (these tests don't depend on DB path).

**Step 3: Commit**

```bash
git add config/settings.py
git commit -m "feat(db): add NCAAB_DATABASE_PATH and MLB_DATABASE_PATH to settings"
```

---

## Task 2: Rebuild `ncaab_betting.db` Schema

**Files:**
- Modify: `tracking/database.py`

### What changes in the schema

**`bets` table:**
- Remove `sport` column (no longer needed — file name tells you the sport)
- Remove `actual_profit_loss` (duplicate — keep `profit_loss`)
- Add `devig_prob_placed REAL` — fair win prob at bet time (post de-vig)
- Add `devig_prob_closing REAL` — fair win prob at close (post de-vig)
- Add `opening_odds INTEGER` — market open odds (may differ from odds_placed)
- UNIQUE constraint stays: `(game_id, bet_type, selection, sportsbook, position_entry)`

**`odds_snapshots` table:**
- Add `market_type TEXT NOT NULL DEFAULT 'full_game'` — values: `full_game`, `f5`, `first_half`, `team_total`
- Update UNIQUE to: `UNIQUE(game_id, sportsbook, snapshot_type, market_type)`

**`predictions` table:**
- Remove `sport` column

**New `barttorvik_ratings` table** (wide, replaces EAV rows for Barttorvik data):
```sql
CREATE TABLE IF NOT EXISTS barttorvik_ratings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    team        TEXT NOT NULL,
    conf        TEXT,
    season      INTEGER NOT NULL,
    rating_date DATE NOT NULL,
    -- Summary
    rank        INTEGER,
    barthag     REAL,
    wab         REAL,
    -- Efficiency
    adj_o       REAL,
    adj_d       REAL,
    adj_tempo   REAL,
    -- Four factors (offense)
    efg_o       REAL,   -- effective FG% offense
    tov_o       REAL,   -- turnover rate offense
    orb         REAL,   -- offensive rebound rate
    ftr_o       REAL,   -- free throw rate offense
    -- Four factors (defense)
    efg_d       REAL,   -- effective FG% defense allowed
    tov_d       REAL,   -- turnover rate defense
    drb         REAL,   -- defensive rebound rate
    ftr_d       REAL,   -- free throw rate defense allowed
    -- Shooting breakdown
    two_pt_o    REAL,
    three_pt_o  REAL,
    three_pt_rate_o REAL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team, season, rating_date)
);
CREATE INDEX IF NOT EXISTS idx_bart_team_date
    ON barttorvik_ratings(team, season, rating_date);
```

**New `prop_bets` table:**
```sql
CREATE TABLE IF NOT EXISTS prop_bets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL,
    game_date       DATE NOT NULL,
    player_name     TEXT NOT NULL,
    player_team     TEXT,
    prop_type       TEXT NOT NULL,  -- 'strikeouts', 'points', 'assists', etc.
    line            REAL NOT NULL,
    selection       TEXT NOT NULL,  -- 'over' or 'under'
    odds_placed     INTEGER NOT NULL,
    odds_closing    INTEGER,
    model_prediction REAL,
    model_prob      REAL,
    model_edge      REAL,
    stake           REAL,
    sportsbook      TEXT,
    result          TEXT,           -- 'win', 'loss', 'push', 'void'
    actual_value    REAL,           -- what the player actually did
    profit_loss     REAL,
    clv             REAL,
    is_settled      BOOLEAN DEFAULT FALSE,
    settled_at      TIMESTAMP,
    is_live         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, player_name, prop_type, line, selection, sportsbook)
);
```

**New `schema_version` table:**
```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);
```
Insert `(2, CURRENT_TIMESTAMP, 'per-sport split + CLV components + barttorvik four factors')` on init.

**Step 1: Write the failing test**

```python
# tests/test_ncaab_schema.py
import sqlite3
import tempfile
from pathlib import Path

def test_bets_has_clv_components():
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase
        db = BettingDatabase(str(Path(tmp) / "test.db"))
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bets)").fetchall()]
        conn.close()
        assert "devig_prob_placed" in cols
        assert "devig_prob_closing" in cols
        assert "opening_odds" in cols
        assert "actual_profit_loss" not in cols
        assert "sport" not in cols

def test_odds_snapshots_has_market_type():
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase
        db = BettingDatabase(str(Path(tmp) / "test.db"))
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(odds_snapshots)").fetchall()]
        conn.close()
        assert "market_type" in cols

def test_barttorvik_ratings_table_exists():
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase
        db = BettingDatabase(str(Path(tmp) / "test.db"))
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()
        assert "barttorvik_ratings" in tables
        assert "prop_bets" in tables
        assert "schema_version" in tables

def test_prop_bets_insert():
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase
        db = BettingDatabase(str(Path(tmp) / "test.db"))
        db.insert_prop_bet({
            "game_id": "abc123",
            "game_date": "2026-03-05",
            "player_name": "Test Player",
            "prop_type": "points",
            "line": 22.5,
            "selection": "over",
            "odds_placed": -115,
            "sportsbook": "DraftKings",
        })
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        count = conn.execute("SELECT COUNT(*) FROM prop_bets").fetchone()[0]
        conn.close()
        assert count == 1
```

**Step 2: Run test — expect FAIL**

```bash
venv/Scripts/python.exe -m pytest tests/test_ncaab_schema.py -v
```

Expected: `FAILED` — columns/tables don't exist yet.

**Step 3: Implement in `tracking/database.py`**

Replace the `_initialize_schema` method with the updated DDL (see overview above). Key changes:

- `bets` CREATE TABLE: remove `sport`, remove `actual_profit_loss`, add `devig_prob_placed REAL`, `devig_prob_closing REAL`, `opening_odds INTEGER`
- `odds_snapshots` CREATE TABLE: add `market_type TEXT NOT NULL DEFAULT 'full_game'`
- `predictions` CREATE TABLE: remove `sport`
- Add `barttorvik_ratings` CREATE TABLE block
- Add `prop_bets` CREATE TABLE block
- Add `schema_version` CREATE TABLE block + `INSERT OR IGNORE INTO schema_version VALUES (2, ...)`
- Remove all `ALTER TABLE` migration blocks (fresh schema, no migrations needed)
- Add `insert_prop_bet(self, data: dict) -> int` method (same pattern as `insert_bet`)

**Step 4: Run tests — expect PASS**

```bash
venv/Scripts/python.exe -m pytest tests/test_ncaab_schema.py -v
```

**Step 5: Verify existing tests still pass**

```bash
venv/Scripts/python.exe -m pytest tests/test_daily_run.py tests/test_settlement.py -v
```

**Step 6: Commit**

```bash
git add tracking/database.py tests/test_ncaab_schema.py
git commit -m "feat(db): rebuild ncaab_betting schema - CLV components, market_type, barttorvik wide table, prop_bets"
```

---

## Task 3: Add Betting + Missing Data Tables to `mlb_data.db`

**Files:**
- Modify: `scripts/mlb_init_db.py`

### New tables to add to SCHEMA_SQL

**`bets` — MLB-specific bet tracking:**
```sql
CREATE TABLE IF NOT EXISTS bets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_pk         INTEGER REFERENCES games(game_pk),
    game_date       DATE NOT NULL,
    bet_type        TEXT NOT NULL,      -- 'moneyline', 'f5', 'total', 'spread'
    market_type     TEXT NOT NULL DEFAULT 'full_game',  -- 'full_game', 'f5'
    selection       TEXT NOT NULL,      -- 'home', 'away', 'over', 'under'
    line            REAL,
    odds_placed     INTEGER NOT NULL,
    odds_closing    INTEGER,
    opening_odds    INTEGER,
    model_probability   REAL,
    model_edge          REAL,
    devig_prob_placed   REAL,
    devig_prob_closing  REAL,
    pitcher_adj_home    REAL,           -- MLB-specific: pitcher lambda adjustment
    pitcher_adj_away    REAL,
    stake           REAL NOT NULL,
    sportsbook      TEXT NOT NULL,
    result          TEXT,               -- 'win', 'loss', 'push', 'void'
    profit_loss     REAL,
    clv             REAL,
    is_settled      BOOLEAN NOT NULL DEFAULT 0,
    settled_at      TIMESTAMP,
    is_live         BOOLEAN NOT NULL DEFAULT 0,
    notes           TEXT,
    bet_uuid        TEXT,
    placed_at       TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_pk, bet_type, market_type, selection, sportsbook)
);
CREATE INDEX IF NOT EXISTS idx_mlb_bets_game ON bets(game_pk);
CREATE INDEX IF NOT EXISTS idx_mlb_bets_date ON bets(game_date);
```

**`prop_bets` — MLB player props:**
```sql
CREATE TABLE IF NOT EXISTS prop_bets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_pk         INTEGER REFERENCES games(game_pk),
    game_date       DATE NOT NULL,
    player_id       INTEGER REFERENCES players(player_id),
    player_name     TEXT NOT NULL,
    player_team     INTEGER REFERENCES teams(team_id),
    prop_type       TEXT NOT NULL,  -- 'strikeouts', 'hits', 'total_bases', etc.
    line            REAL NOT NULL,
    selection       TEXT NOT NULL,
    odds_placed     INTEGER NOT NULL,
    odds_closing    INTEGER,
    model_prediction REAL,
    model_prob       REAL,
    model_edge       REAL,
    stake            REAL,
    sportsbook       TEXT,
    result           TEXT,
    actual_value     REAL,
    profit_loss      REAL,
    clv              REAL,
    is_settled       BOOLEAN NOT NULL DEFAULT 0,
    settled_at       TIMESTAMP,
    is_live          BOOLEAN NOT NULL DEFAULT 0,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_pk, player_id, prop_type, line, selection, sportsbook)
);
```

**`odds_snapshots` — multi-book, multi-market:**
```sql
CREATE TABLE IF NOT EXISTS odds_snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_pk         INTEGER NOT NULL REFERENCES games(game_pk),
    provider        TEXT NOT NULL,
    market_type     TEXT NOT NULL DEFAULT 'full_game',  -- 'full_game', 'f5'
    snapshot_type   TEXT NOT NULL DEFAULT 'current',    -- 'opening', 'current', 'closing'
    captured_at     TIMESTAMP NOT NULL,
    spread_home     REAL,
    spread_home_odds INTEGER,
    spread_away_odds INTEGER,
    total           REAL,
    over_odds       INTEGER,
    under_odds      INTEGER,
    moneyline_home  INTEGER,
    moneyline_away  INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_pk, provider, market_type, snapshot_type)
);
CREATE INDEX IF NOT EXISTS idx_mlb_odds_game ON odds_snapshots(game_pk);
```

**`game_umpire` — links umpire to specific game (missing link!):**
```sql
CREATE TABLE IF NOT EXISTS game_umpire (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_pk         INTEGER NOT NULL REFERENCES games(game_pk),
    umpire_name     TEXT NOT NULL,
    position        TEXT NOT NULL DEFAULT 'HP',  -- HP, 1B, 2B, 3B
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_pk, position)
);
CREATE INDEX IF NOT EXISTS idx_game_umpire_name ON game_umpire(umpire_name);
CREATE INDEX IF NOT EXISTS idx_game_umpire_game ON game_umpire(game_pk);
```

**`linescore` — inning-by-inning runs (needed for F5 research):**
```sql
CREATE TABLE IF NOT EXISTS linescore (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_pk         INTEGER NOT NULL REFERENCES games(game_pk),
    inning          INTEGER NOT NULL,  -- 1-9 (or extra innings)
    home_runs       INTEGER NOT NULL DEFAULT 0,
    away_runs       INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_pk, inning)
);
CREATE INDEX IF NOT EXISTS idx_linescore_game ON linescore(game_pk);
```

Also bump `SCHEMA_VERSION = 2` and add a description to the `schema_version` insert.

**Step 1: Write failing test**

```python
# tests/test_mlb_schema_v2.py
import sqlite3, tempfile
from pathlib import Path

def _init_db(tmp):
    from scripts.mlb_init_db import init_schema
    db_path = Path(tmp) / "mlb_test.db"
    init_schema(db_path)
    return db_path

def test_new_tables_exist():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _init_db(tmp)
        conn = sqlite3.connect(str(db_path))
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert "bets" in tables
        assert "prop_bets" in tables
        assert "odds_snapshots" in tables
        assert "game_umpire" in tables
        assert "linescore" in tables

def test_odds_snapshots_has_market_type():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _init_db(tmp)
        conn = sqlite3.connect(str(db_path))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(odds_snapshots)").fetchall()]
        conn.close()
        assert "market_type" in cols
        assert "snapshot_type" in cols

def test_bets_has_mlb_specific_columns():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _init_db(tmp)
        conn = sqlite3.connect(str(db_path))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bets)").fetchall()]
        conn.close()
        assert "pitcher_adj_home" in cols
        assert "devig_prob_placed" in cols
        assert "market_type" in cols

def test_schema_version_is_2():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _init_db(tmp)
        conn = sqlite3.connect(str(db_path))
        version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        conn.close()
        assert version == 2
```

**Step 2: Run — expect FAIL**

```bash
venv/Scripts/python.exe -m pytest tests/test_mlb_schema_v2.py -v
```

**Step 3: Implement** — add the 5 new DDL blocks to `SCHEMA_SQL` in `mlb_init_db.py`, bump `SCHEMA_VERSION = 2`, update `verify_schema()` to include the new tables.

**Step 4: Run — expect PASS**

```bash
venv/Scripts/python.exe -m pytest tests/test_mlb_schema_v2.py -v
```

**Step 5: Verify existing MLB tests still pass**

```bash
venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py tests/test_mlb_stats_api.py -v
```

**Step 6: Run migration on live mlb_data.db** (idempotent — CREATE IF NOT EXISTS)

```bash
venv/Scripts/python.exe scripts/mlb_init_db.py --verify
```

Expected output includes `bets`, `prop_bets`, `odds_snapshots`, `game_umpire`, `linescore` in the table list.

**Step 7: Commit**

```bash
git add scripts/mlb_init_db.py tests/test_mlb_schema_v2.py
git commit -m "feat(db): add bets/odds/umpire/linescore tables to mlb_data.db (schema v2)"
```

---

## Task 4: Barttorvik Scraper — Add Four-Factor Columns

**Background:** The barttorvik.com HTML table has four-factor columns. The scraper currently only extracts 8 columns (rank, team, conf, adj_o, adj_d, barthag, adj_tempo, wab). The column indices from the actual page:

```
Rk(0), Team(1), Conf(2), G(3), Rec(4), AdjOE(5), AdjDE(6), Barthag(7),
EFG%(8), EFGD%(9), TOR(10), TORD(11), ORB(12), DRB(13), FTR(14), FTRD(15),
2P%(16), 2P%D(17), 3P%(18), 3P%D(19), 3PR(20), 3PRD(21), Adj T.(22), WAB(23)
```

**Files:**
- Modify: `pipelines/barttorvik_scraper.py`

**Step 1: Write failing test**

```python
# In tests/test_barttorvik_scraper.py — add to existing file:

def test_scraper_output_has_four_factors():
    """Verify OUTPUT_COLUMNS includes four-factor columns."""
    from pipelines.barttorvik_scraper import OUTPUT_COLUMNS
    four_factors = ["efg_o", "efg_d", "tov_o", "tov_d", "orb", "drb", "ftr_o", "ftr_d"]
    for col in four_factors:
        assert col in OUTPUT_COLUMNS, f"Missing four-factor column: {col}"

def test_parse_row_extracts_four_factors(mock_trank_html):
    """Verify HTML row parsing extracts four-factor values."""
    from pipelines.barttorvik_scraper import parse_ratings_table
    df = parse_ratings_table(mock_trank_html, season=2026)
    assert not df.empty
    assert "efg_o" in df.columns
    assert df["efg_o"].notna().any()
```

**Step 2: Run — expect FAIL**

```bash
venv/Scripts/python.exe -m pytest tests/test_barttorvik_scraper.py::test_scraper_output_has_four_factors -v
```

**Step 3: Implement in `barttorvik_scraper.py`**

Update `COLUMN_INDICES`:
```python
COLUMN_INDICES = {
    "rank":       0,
    "team":       1,
    "conf":       2,
    "adj_o":      5,
    "adj_d":      6,
    "barthag":    7,
    "efg_o":      8,   # Effective FG% offense
    "efg_d":      9,   # Effective FG% defense
    "tov_o":      10,  # Turnover rate offense
    "tov_d":      11,  # Turnover rate defense
    "orb":        12,  # Offensive rebound rate
    "drb":        13,  # Defensive rebound rate
    "ftr_o":      14,  # Free throw rate offense
    "ftr_d":      15,  # Free throw rate defense
    "two_pt_o":   16,
    "three_pt_o": 18,
    "three_pt_rate_o": 20,
    "adj_tempo":  22,
    "wab":        23,
}
```

Update `OUTPUT_COLUMNS` to include the new keys.

In the row-parsing loop, add `_safe_float()` calls for each new column (same pattern as adj_o/adj_d).

Update the coercion loop at the end of parse function to coerce new numeric columns.

**Step 4: Run — expect PASS**

```bash
venv/Scripts/python.exe -m pytest tests/test_barttorvik_scraper.py -v
```

**Step 5: Commit**

```bash
git add pipelines/barttorvik_scraper.py tests/test_barttorvik_scraper.py
git commit -m "feat(barttorvik): scrape four-factor columns (efg, tov, orb, drb, ftr)"
```

---

## Task 5: Ingest Barttorvik Four Factors into `barttorvik_ratings` Table

**Files:**
- Modify: `pipelines/barttorvik_fetcher.py` (add `store_to_db()` function)
- Modify: `scripts/fetch_barttorvik_data.py` (call store_to_db after fetch)

**Step 1: Add `store_ratings_to_db()` to `barttorvik_fetcher.py`**

```python
def store_ratings_to_db(df: pd.DataFrame, db_path: Path) -> int:
    """Insert/replace Barttorvik ratings into barttorvik_ratings table.

    Maps DataFrame columns to DB columns. Silently skips columns not in
    the DB schema. Returns number of rows inserted.
    """
    import sqlite3

    COLUMN_MAP = {
        "team": "team", "conf": "conf", "year": "season",
        "date": "rating_date", "rank": "rank", "barthag": "barthag",
        "wab": "wab", "adj_o": "adj_o", "adj_d": "adj_d",
        "adj_tempo": "adj_tempo", "efg_o": "efg_o", "tov_o": "tov_o",
        "orb": "orb", "ftr_o": "ftr_o", "efg_d": "efg_d",
        "tov_d": "tov_d", "drb": "drb", "ftr_d": "ftr_d",
        "two_pt_o": "two_pt_o", "three_pt_o": "three_pt_o",
        "three_pt_rate_o": "three_pt_rate_o",
    }

    rows = []
    for _, row in df.iterrows():
        record = {}
        for src_col, dst_col in COLUMN_MAP.items():
            val = row.get(src_col)
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                record[dst_col] = val
        if "team" in record and "season" in record and "rating_date" in record:
            # Normalize date
            if hasattr(record["rating_date"], "strftime"):
                record["rating_date"] = record["rating_date"].strftime("%Y-%m-%d")
            rows.append(record)

    if not rows:
        return 0

    cols = list(rows[0].keys())
    placeholders = ",".join("?" for _ in cols)
    col_str = ",".join(cols)
    sql = f"INSERT OR REPLACE INTO barttorvik_ratings ({col_str}) VALUES ({placeholders})"

    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
        conn.commit()
    finally:
        conn.close()

    return len(rows)
```

**Step 2: Write test**

```python
# tests/test_barttorvik_fetcher.py — add:

def test_store_ratings_to_db(tmp_path):
    import pandas as pd
    from pathlib import Path
    from tracking.database import BettingDatabase
    from pipelines.barttorvik_fetcher import store_ratings_to_db

    db_path = tmp_path / "ncaab.db"
    BettingDatabase(str(db_path))  # init schema

    df = pd.DataFrame([{
        "team": "Duke", "conf": "ACC", "year": 2026,
        "date": pd.Timestamp("2026-03-01"),
        "rank": 5, "barthag": 0.95, "wab": 8.2,
        "adj_o": 120.1, "adj_d": 95.3, "adj_tempo": 68.5,
        "efg_o": 0.551, "tov_o": 14.2, "orb": 32.1, "ftr_o": 0.31,
        "efg_d": 0.481, "tov_d": 18.7, "drb": 71.3, "ftr_d": 0.28,
    }])

    count = store_ratings_to_db(df, db_path)
    assert count == 1

    import sqlite3
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT efg_o, tov_o, orb FROM barttorvik_ratings WHERE team='Duke'").fetchone()
    conn.close()
    assert row is not None
    assert abs(row[0] - 0.551) < 0.001
```

**Step 3: Run — expect FAIL, implement, run again — expect PASS**

```bash
venv/Scripts/python.exe -m pytest tests/test_barttorvik_fetcher.py::test_store_ratings_to_db -v
```

**Step 4: Wire into `scripts/fetch_barttorvik_data.py`**

After the fetch loop that saves to parquet, add:

```python
from config.settings import NCAAB_DATABASE_PATH
from pipelines.barttorvik_fetcher import store_ratings_to_db

# After df is fetched and cached:
stored = store_ratings_to_db(df, NCAAB_DATABASE_PATH)
logger.info("Stored %d Barttorvik rows to ncaab_betting.db", stored)
```

**Step 5: Commit**

```bash
git add pipelines/barttorvik_fetcher.py scripts/fetch_barttorvik_data.py tests/test_barttorvik_fetcher.py
git commit -m "feat(barttorvik): store four-factor ratings to barttorvik_ratings table in ncaab_betting.db"
```

---

## Task 6: Update Consumer Scripts — NCAAB_DATABASE_PATH

**Files to update** (replace `DATABASE_PATH` import with `NCAAB_DATABASE_PATH`):

| Script | Change |
|--------|--------|
| `scripts/daily_run.py` | `DATABASE_PATH` → `NCAAB_DATABASE_PATH` |
| `scripts/backtest_ncaab_elo.py` | same |
| `scripts/incremental_backtest.py` | same |
| `scripts/generate_report.py` | same |
| `scripts/settle_paper_bets.py` | same |
| `scripts/record_paper_bets.py` | same |
| `tracking/logger.py` | same |
| `tracking/reports.py` | same |

**Step 1: Find all references**

```bash
cd C:\Users\msenf\sports-betting
grep -rn "from config.settings import.*DATABASE_PATH\|DATABASE_PATH" scripts/ tracking/ --include="*.py" | grep -v "NCAAB\|MLB" | grep -v ".pyc"
```

**Step 2: For each file found**, change:
```python
from config.settings import DATABASE_PATH
```
to:
```python
from config.settings import NCAAB_DATABASE_PATH as DATABASE_PATH
```
This one-line change is backwards compatible — all existing code using `DATABASE_PATH` continues to work.

**Step 3: Run NCAAB tests**

```bash
venv/Scripts/python.exe -m pytest tests/test_daily_run.py tests/test_settlement.py tests/test_reports.py -v
```

**Step 4: Commit**

```bash
git add scripts/ tracking/
git commit -m "feat(db): NCAAB consumer scripts use NCAAB_DATABASE_PATH"
```

---

## Task 7: Update MLB Consumer Scripts — MLB_DATABASE_PATH

**Files to update:**

| Script | Change |
|--------|--------|
| `scripts/mlb_daily_run.py` | Import `MLB_DATABASE_PATH`, use for all DB operations |
| `scripts/mlb_backtest.py` | same |
| `scripts/mlb_backfill_odds.py` | same |
| `scripts/mlb_backfill_starters.py` | same |

These scripts currently do NOT use `BettingDatabase` — they use raw sqlite3 with `DEFAULT_DB_PATH` from `mlb_init_db.py`. The change is simply:

```python
# Before:
from scripts.mlb_init_db import DEFAULT_DB_PATH
# or
DB_PATH = BASE_DIR / "data" / "mlb_data.db"

# After:
from config.settings import MLB_DATABASE_PATH as DB_PATH
```

**Step 1: Find all hardcoded `mlb_data.db` references**

```bash
grep -rn "mlb_data.db\|DEFAULT_DB_PATH" scripts/ pipelines/ --include="*.py"
```

**Step 2: Update each file** to use `MLB_DATABASE_PATH`.

**Step 3: Run MLB tests**

```bash
venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py tests/test_mlb_backfill_starters.py tests/test_mlb_backfill_odds.py -v
```

**Step 4: Commit**

```bash
git add scripts/ pipelines/
git commit -m "feat(db): MLB consumer scripts use MLB_DATABASE_PATH from settings"
```

---

## Task 8: Rename betting.db → ncaab_betting.db

Now that all code points to `NCAAB_DATABASE_PATH`, rename the actual file.

**Step 1: Rename the file**

```bash
cd C:\Users\msenf\sports-betting
mv data/betting.db data/ncaab_betting.db
```

**Step 2: Update `.gitignore`**

```
# Before:
!data/betting.db

# After:
!data/ncaab_betting.db
```

**Step 3: Update `scripts/backup_db.py`**

```python
DATABASES = {
    "ncaab_betting.db": PROJECT_ROOT / "data" / "ncaab_betting.db",
    "mlb_data.db":      PROJECT_ROOT / "data" / "mlb_data.db",
}
```

**Step 4: Update `scripts/restore_db.py`** — same DATABASES dict change.

**Step 5: Update `scripts/pipeline_health_check.py`** — the auto-restore check references `db_name = DATABASE_PATH.name`; since `DATABASE_PATH` now points to `ncaab_betting.db` via alias, this works automatically.

**Step 6: Run full test suite**

```bash
venv/Scripts/python.exe -m pytest tests/ -v --ignore=tests/test_logger.py -x
```
(test_logger.py has known pre-existing failures — skip it)

**Step 7: Run backup to verify new filename**

```bash
venv/Scripts/python.exe scripts/backup_db.py
venv/Scripts/python.exe scripts/backup_db.py --list
```

Expected: `ncaab_betting.db_2026-03-05.bak` and `mlb_data.db_2026-03-05.bak`

**Step 8: Final commit**

```bash
git add data/ncaab_betting.db .gitignore scripts/backup_db.py scripts/restore_db.py
git commit -m "feat(db): rename betting.db -> ncaab_betting.db, update backup scripts"
```

---

## Validation Checklist

After all tasks complete, verify:

```bash
# Both DBs exist with correct size
ls -la data/ncaab_betting.db data/mlb_data.db

# NCAAB schema has all new tables/columns
venv/Scripts/python.exe -c "
import sqlite3
conn = sqlite3.connect('data/ncaab_betting.db')
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('NCAAB tables:', tables)
cols = [r[1] for r in conn.execute('PRAGMA table_info(bets)').fetchall()]
print('bets cols:', cols)
"

# MLB schema v2
venv/Scripts/python.exe scripts/mlb_init_db.py --verify

# Full test suite
venv/Scripts/python.exe -m pytest tests/ -v --ignore=tests/test_logger.py

# Backup works for both DBs
venv/Scripts/python.exe scripts/backup_db.py --verify
```

---

## Notes

- **Barttorvik four-factor column indices** are based on the current barttorvik.com HTML table structure (verified March 2026). If the site changes column order, update `COLUMN_INDICES` in `barttorvik_scraper.py`.
- **cbbdata API** (historical seasons) already returns four-factor columns in the parquet — `store_ratings_to_db()` handles both sources since it reads from the DataFrame regardless of origin.
- **`actual_profit_loss`** is deliberately removed. Any existing code writing to it will fail loudly (preferred over silent data loss). Search for `actual_profit_loss` in code and replace with `profit_loss`.
- **`sport` column removal** affects `predictions` and `bets` in ncaab_betting.db only. Since each DB is sport-specific, the column is redundant.
- **mlb_data.db `odds` table** (existing, wide open/close columns) is left intact. The new `odds_snapshots` table replaces it for going-forward use — backfilled data stays in `odds`, new pipeline writes to `odds_snapshots`.
