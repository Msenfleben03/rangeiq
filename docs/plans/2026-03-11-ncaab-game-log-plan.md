# NCAAB Game Log Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an append-only game log that captures every D1 NCAAB game with model predictions, opening/closing odds, and final scores.

**Architecture:** New `game_log` table in `ncaab_betting.db`, populated at two pipeline touch points (prediction insert + settlement update). New `tracking/game_log.py` module owns all logic. Standalone script + dashboard page for consumption.

**Tech Stack:** Python 3.11+, SQLite, pandas, HTML/JS (dashboard)

**Design doc:** `docs/plans/2026-03-11-ncaab-game-log-design.md`

---

### Task 0: Prerequisite — Fix `groups=50` in ESPN Scoreboard Fetch

The `fetch_espn_scoreboard()` in `scripts/daily_predictions.py:79` uses `PAPER_BETTING.ESPN_SCOREBOARD_URL` with `limit=200` but does NOT pass `groups=50`. Without it, ESPN silently returns only featured games (~1-5/day) instead of all D1 games (~20-30/day). The game log requires ALL games.

Similarly, `scripts/collect_closing_odds.py:112` builds the URL without `groups=50`.

**Files:**
- Modify: `scripts/daily_predictions.py:79-80`
- Modify: `scripts/collect_closing_odds.py:112`

**Step 1: Add `groups=50` to `fetch_espn_scoreboard`**

In `scripts/daily_predictions.py`, line 80:

```python
# Before:
params = {"dates": date_str, "limit": 200}

# After:
params = {"dates": date_str, "limit": 500, "groups": 50}
```

**Step 2: Add `groups=50` to `collect_closing_odds.py`**

In `scripts/collect_closing_odds.py`, line 112:

```python
# Before:
url = f"{NCAAB_SCOREBOARD}?dates={date_compact}&limit=500"

# After:
url = f"{NCAAB_SCOREBOARD}?dates={date_compact}&limit=500&groups=50"
```

**Step 3: Verify existing tests still pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py -v -p no:examples -x -q 2>&1 | head -30`

**Step 4: Commit**

```bash
git add scripts/daily_predictions.py scripts/collect_closing_odds.py
git commit -m "fix: add groups=50 to ESPN scoreboard fetches for all D1 games"
```

---

### Task 1: Add `game_log` Table to Database Schema

**Files:**
- Modify: `tracking/database.py:65-316` (inside `_initialize_schema`)
- Test: `tests/test_game_log.py` (new file)

**Step 1: Write the failing test**

Create `tests/test_game_log.py`:

```python
"""Tests for game_log table and tracking/game_log.py module."""

import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database with game_log table."""
    return str(tmp_path / "test_ncaab.db")


@pytest.fixture
def db(db_path):
    """Create a BettingDatabase with game_log table."""
    from tracking.database import BettingDatabase
    return BettingDatabase(db_path)


class TestGameLogSchema:
    """Test game_log table creation and constraints."""

    def test_game_log_table_exists(self, db, db_path):
        """game_log table should be created during schema init."""
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='game_log'"
        )
        assert cursor.fetchone() is not None
        conn.close()

    def test_game_log_columns(self, db, db_path):
        """game_log table should have the expected columns."""
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(game_log)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()

        expected = {
            "id", "game_date", "game_id", "home", "away",
            "home_score", "away_score", "model_prob_home", "edge",
            "odds_opening_home", "odds_opening_away",
            "odds_closing_home", "odds_closing_away",
            "bet_placed", "bet_side", "result", "settled_at", "created_at",
        }
        assert expected.issubset(columns)

    def test_game_log_unique_constraint(self, db, db_path):
        """Inserting duplicate game_id should raise IntegrityError."""
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO game_log (game_date, game_id, home, away) "
            "VALUES ('2026-03-11', '401720001', 'DUKE', 'UNC')"
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO game_log (game_date, game_id, home, away) "
                "VALUES ('2026-03-11', '401720001', 'DUKE', 'UNC')"
            )
        conn.close()
```

**Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_game_log.py::TestGameLogSchema -v -p no:examples`
Expected: FAIL — `game_log` table doesn't exist yet.

**Step 3: Add game_log table to `_initialize_schema`**

In `tracking/database.py`, after the `schema_version` table creation (~line 313), add:

```python
            # Game log — tracks every D1 game with model predictions and odds
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS game_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_date DATE NOT NULL,
                    game_id TEXT NOT NULL,
                    home TEXT NOT NULL,
                    away TEXT NOT NULL,
                    home_score INTEGER,
                    away_score INTEGER,
                    model_prob_home REAL,
                    edge REAL,
                    odds_opening_home INTEGER,
                    odds_opening_away INTEGER,
                    odds_closing_home INTEGER,
                    odds_closing_away INTEGER,
                    bet_placed BOOLEAN DEFAULT 0,
                    bet_side TEXT,
                    result TEXT,
                    settled_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(game_id)
                )
            """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_game_log_date "
                "ON game_log(game_date)"
            )
```

**Step 4: Run test to verify it passes**

Run: `venv/Scripts/python.exe -m pytest tests/test_game_log.py::TestGameLogSchema -v -p no:examples`
Expected: 3 PASS

**Step 5: Commit**

```bash
git add tracking/database.py tests/test_game_log.py
git commit -m "feat: add game_log table to ncaab_betting.db schema"
```

---

### Task 2: Build `tracking/game_log.py` — Insert Logic

**Files:**
- Create: `tracking/game_log.py`
- Test: `tests/test_game_log.py` (extend)

**Step 1: Write the failing tests**

Append to `tests/test_game_log.py`:

```python
class TestGameLogInsert:
    """Test inserting games into game_log."""

    def test_insert_game_with_odds(self, db, db_path):
        """Insert a game with model predictions and opening odds."""
        from tracking.game_log import insert_game_log_entries

        games = [
            {
                "game_id": "401720001",
                "home": "DUKE",
                "away": "UNC",
                "home_name": "Duke Blue Devils",
                "away_name": "North Carolina Tar Heels",
            }
        ]
        predictions = {
            "401720001": {
                "model_prob_home": 0.65,
                "edge": 0.12,
                "odds_opening_home": -180,
                "odds_opening_away": 150,
            }
        }
        bets = {"401720001": "home"}

        inserted = insert_game_log_entries(db_path, "2026-03-11", games, predictions, bets)
        assert inserted == 1

        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM game_log WHERE game_id = '401720001'").fetchone()
        conn.close()

        assert row["home"] == "DUKE"
        assert row["away"] == "UNC"
        assert row["model_prob_home"] == pytest.approx(0.65)
        assert row["edge"] == pytest.approx(0.12)
        assert row["odds_opening_home"] == -180
        assert row["odds_opening_away"] == 150
        assert row["bet_placed"] == 1
        assert row["bet_side"] == "home"

    def test_insert_game_without_odds(self, db, db_path):
        """Insert a game with no odds available (small conference)."""
        from tracking.game_log import insert_game_log_entries

        games = [
            {
                "game_id": "401720002",
                "home": "TEAM_A",
                "away": "TEAM_B",
                "home_name": "Team A",
                "away_name": "Team B",
            }
        ]
        predictions = {
            "401720002": {
                "model_prob_home": 0.55,
                "edge": None,
                "odds_opening_home": None,
                "odds_opening_away": None,
            }
        }

        inserted = insert_game_log_entries(db_path, "2026-03-11", games, predictions, {})
        assert inserted == 1

        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM game_log WHERE game_id = '401720002'").fetchone()
        conn.close()

        assert row["odds_opening_home"] is None
        assert row["edge"] is None
        assert row["bet_placed"] == 0
        assert row["bet_side"] is None

    def test_insert_duplicate_skipped(self, db, db_path):
        """Re-inserting same game_id should be skipped (no error)."""
        from tracking.game_log import insert_game_log_entries

        games = [{"game_id": "401720003", "home": "UK", "away": "FLA",
                   "home_name": "Kentucky", "away_name": "Florida"}]
        predictions = {"401720003": {"model_prob_home": 0.50, "edge": None,
                                      "odds_opening_home": None, "odds_opening_away": None}}

        assert insert_game_log_entries(db_path, "2026-03-11", games, predictions, {}) == 1
        assert insert_game_log_entries(db_path, "2026-03-11", games, predictions, {}) == 0

    def test_insert_game_not_in_predictions(self, db, db_path):
        """Games without predictions should still be inserted (model_prob=None)."""
        from tracking.game_log import insert_game_log_entries

        games = [{"game_id": "401720004", "home": "GONZ", "away": "SMC",
                   "home_name": "Gonzaga", "away_name": "Saint Mary's"}]
        predictions = {}  # No prediction for this game

        inserted = insert_game_log_entries(db_path, "2026-03-11", games, predictions, {})
        assert inserted == 1

        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM game_log WHERE game_id = '401720004'").fetchone()
        conn.close()

        assert row["model_prob_home"] is None
        assert row["bet_placed"] == 0
```

**Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_game_log.py::TestGameLogInsert -v -p no:examples`
Expected: FAIL — `tracking.game_log` module doesn't exist.

**Step 3: Write `tracking/game_log.py` — insert function**

```python
"""Game Log Tracking — records every D1 NCAAB game with predictions and odds.

Append-only log: each daily pipeline run inserts all games for the target date.
Settlement run updates scores, closing odds, and results the next day.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def insert_game_log_entries(
    db_path: str | Path,
    game_date: str,
    games: list[dict],
    predictions: dict[str, dict],
    bets: dict[str, str],
) -> int:
    """Insert games into game_log table.

    Args:
        db_path: Path to ncaab_betting.db.
        game_date: Date string (YYYY-MM-DD).
        games: List of game dicts from ESPN Scoreboard (must have game_id, home, away).
        predictions: Dict mapping game_id -> {model_prob_home, edge,
            odds_opening_home, odds_opening_away}.
        bets: Dict mapping game_id -> bet_side ("home" or "away") for games we bet.

    Returns:
        Number of rows inserted (skips duplicates).
    """
    conn = sqlite3.connect(str(db_path))
    inserted = 0

    try:
        for game in games:
            game_id = game.get("game_id", "")
            if not game_id:
                continue

            pred = predictions.get(game_id, {})
            bet_side = bets.get(game_id)

            try:
                conn.execute(
                    """INSERT OR IGNORE INTO game_log
                        (game_date, game_id, home, away,
                         model_prob_home, edge,
                         odds_opening_home, odds_opening_away,
                         bet_placed, bet_side, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        game_date,
                        game_id,
                        game.get("home", ""),
                        game.get("away", ""),
                        pred.get("model_prob_home"),
                        pred.get("edge"),
                        pred.get("odds_opening_home"),
                        pred.get("odds_opening_away"),
                        1 if bet_side else 0,
                        bet_side,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                if conn.total_changes > inserted:
                    inserted = conn.total_changes
            except sqlite3.Error as e:
                logger.warning("Failed to insert game %s: %s", game_id, e)

        conn.commit()
    finally:
        conn.close()

    logger.info("Game log: inserted %d games for %s", inserted, game_date)
    return inserted
```

Wait — `conn.total_changes` tracks cumulative changes across the connection, not per-statement. Let me fix the counting logic:

```python
def insert_game_log_entries(
    db_path: str | Path,
    game_date: str,
    games: list[dict],
    predictions: dict[str, dict],
    bets: dict[str, str],
) -> int:
    conn = sqlite3.connect(str(db_path))
    inserted = 0

    try:
        for game in games:
            game_id = game.get("game_id", "")
            if not game_id:
                continue

            pred = predictions.get(game_id, {})
            bet_side = bets.get(game_id)

            try:
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO game_log
                        (game_date, game_id, home, away,
                         model_prob_home, edge,
                         odds_opening_home, odds_opening_away,
                         bet_placed, bet_side, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        game_date,
                        game_id,
                        game.get("home", ""),
                        game.get("away", ""),
                        pred.get("model_prob_home"),
                        pred.get("edge"),
                        pred.get("odds_opening_home"),
                        pred.get("odds_opening_away"),
                        1 if bet_side else 0,
                        bet_side,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                if cursor.rowcount > 0:
                    inserted += 1
            except sqlite3.Error as e:
                logger.warning("Failed to insert game %s: %s", game_id, e)

        conn.commit()
    finally:
        conn.close()

    logger.info("Game log: inserted %d games for %s", inserted, game_date)
    return inserted
```

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_game_log.py::TestGameLogInsert -v -p no:examples`
Expected: 4 PASS

**Step 5: Commit**

```bash
git add tracking/game_log.py tests/test_game_log.py
git commit -m "feat: add game_log insert logic (tracking/game_log.py)"
```

---

### Task 3: Build `tracking/game_log.py` — Settlement Logic

**Files:**
- Modify: `tracking/game_log.py`
- Test: `tests/test_game_log.py` (extend)

**Step 1: Write the failing tests**

Append to `tests/test_game_log.py`:

```python
class TestGameLogSettle:
    """Test settling games in game_log (scores + closing odds + result)."""

    def _seed_game(self, db_path, game_id="401720010", home="DUKE", away="UNC"):
        """Insert a pending game into game_log."""
        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO game_log (game_date, game_id, home, away, model_prob_home) "
            "VALUES ('2026-03-10', ?, ?, ?, 0.60)",
            (game_id, home, away),
        )
        conn.commit()
        conn.close()

    def test_settle_updates_score_and_result(self, db, db_path):
        """Settling a game should update scores, result, and settled_at."""
        self._seed_game(db_path)
        from tracking.game_log import settle_game_log_entries

        completed_games = [
            {
                "game_id": "401720010",
                "home": "DUKE",
                "away": "UNC",
                "home_score": 78,
                "away_score": 72,
            }
        ]
        closing_odds = {
            "401720010": {"home": -200, "away": 170},
        }

        settled = settle_game_log_entries(db_path, completed_games, closing_odds)
        assert settled == 1

        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM game_log WHERE game_id = '401720010'").fetchone()
        conn.close()

        assert row["home_score"] == 78
        assert row["away_score"] == 72
        assert row["result"] == "home"
        assert row["odds_closing_home"] == -200
        assert row["odds_closing_away"] == 170
        assert row["settled_at"] is not None

    def test_settle_away_win(self, db, db_path):
        """Away team winning should set result='away'."""
        self._seed_game(db_path, game_id="401720011")
        from tracking.game_log import settle_game_log_entries

        completed = [{"game_id": "401720011", "home": "DUKE", "away": "UNC",
                       "home_score": 65, "away_score": 70}]
        settled = settle_game_log_entries(db_path, completed, {})
        assert settled == 1

        import sqlite3
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM game_log WHERE game_id = '401720011'").fetchone()
        conn.close()

        assert row["result"] == "away"
        assert row["odds_closing_home"] is None  # No closing odds provided

    def test_settle_already_settled_skipped(self, db, db_path):
        """Games already settled should not be re-settled."""
        self._seed_game(db_path, game_id="401720012")
        from tracking.game_log import settle_game_log_entries

        completed = [{"game_id": "401720012", "home": "DUKE", "away": "UNC",
                       "home_score": 80, "away_score": 75}]

        assert settle_game_log_entries(db_path, completed, {}) == 1
        assert settle_game_log_entries(db_path, completed, {}) == 0  # Already settled

    def test_settle_game_not_in_log_skipped(self, db, db_path):
        """Games not in game_log should be skipped (no error)."""
        from tracking.game_log import settle_game_log_entries

        completed = [{"game_id": "999999999", "home": "X", "away": "Y",
                       "home_score": 80, "away_score": 75}]
        assert settle_game_log_entries(db_path, completed, {}) == 0
```

**Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_game_log.py::TestGameLogSettle -v -p no:examples`
Expected: FAIL — `settle_game_log_entries` not defined.

**Step 3: Implement `settle_game_log_entries` in `tracking/game_log.py`**

Add to `tracking/game_log.py`:

```python
def settle_game_log_entries(
    db_path: str | Path,
    completed_games: list[dict],
    closing_odds: dict[str, dict],
) -> int:
    """Update game_log with final scores, closing odds, and results.

    Args:
        db_path: Path to ncaab_betting.db.
        completed_games: List of game dicts with game_id, home_score, away_score.
        closing_odds: Dict mapping game_id -> {"home": int, "away": int} closing MLs.
            Games not in this dict get NULL closing odds.

    Returns:
        Number of games settled.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    settled = 0

    try:
        for game in completed_games:
            game_id = game.get("game_id", "")
            if not game_id:
                continue

            # Check if game exists and is unsettled
            row = conn.execute(
                "SELECT id, result FROM game_log WHERE game_id = ?",
                (game_id,),
            ).fetchone()

            if row is None:
                logger.debug("Game %s not in game_log, skipping", game_id)
                continue

            if row["result"] is not None:
                logger.debug("Game %s already settled, skipping", game_id)
                continue

            home_score = game.get("home_score", 0)
            away_score = game.get("away_score", 0)
            result = "home" if home_score > away_score else "away"

            odds = closing_odds.get(game_id, {})
            closing_home = odds.get("home")
            closing_away = odds.get("away")

            conn.execute(
                """UPDATE game_log
                   SET home_score = ?, away_score = ?, result = ?,
                       odds_closing_home = ?, odds_closing_away = ?,
                       settled_at = ?
                   WHERE game_id = ?""",
                (
                    home_score,
                    away_score,
                    result,
                    closing_home,
                    closing_away,
                    datetime.now(timezone.utc).isoformat(),
                    game_id,
                ),
            )
            settled += 1

        conn.commit()
    finally:
        conn.close()

    logger.info("Game log: settled %d games", settled)
    return settled
```

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_game_log.py::TestGameLogSettle -v -p no:examples`
Expected: 4 PASS

**Step 5: Run ALL game_log tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_game_log.py -v -p no:examples`
Expected: 7 PASS (3 schema + 4 insert + 4 settle... wait, 3 + 4 + 4 = 11 total)

**Step 6: Commit**

```bash
git add tracking/game_log.py tests/test_game_log.py
git commit -m "feat: add game_log settlement logic with closing odds"
```

---

### Task 4: Integrate Game Log into `daily_run.py`

**Files:**
- Modify: `scripts/daily_run.py`

**Step 1: Add import**

At the top of `scripts/daily_run.py`, after the existing imports (~line 49):

```python
from tracking.game_log import insert_game_log_entries, settle_game_log_entries
```

**Step 2: Add game log insert after predictions (in `run_predictions`)**

In `scripts/daily_run.py`, inside `run_predictions()`, after `display_predictions(predictions)` (line 474) and before the `return predictions` (line 483), add:

```python
    # --- Game Log: record ALL games (bet or not) ---
    game_date_str_log = target_date.strftime("%Y-%m-%d")
    pred_lookup = {}
    bet_lookup = {}
    for _, row in predictions.iterrows():
        gid = row.get("game_id", "")
        if not gid:
            continue
        # Best edge: signed (+home, -away)
        home_edge = row.get("home_edge")
        away_edge = row.get("away_edge")
        if home_edge is not None and away_edge is not None:
            best_edge = home_edge if home_edge >= away_edge else -away_edge
        elif home_edge is not None:
            best_edge = home_edge
        elif away_edge is not None:
            best_edge = -away_edge
        else:
            best_edge = None

        pred_lookup[gid] = {
            "model_prob_home": row.get("home_prob"),
            "edge": best_edge,
            "odds_opening_home": row.get("home_ml"),
            "odds_opening_away": row.get("away_ml"),
        }
        rec_side = row.get("rec_side")
        if rec_side:
            bet_lookup[gid] = rec_side.lower()

    # Use ALL games (not just pre-game) so we log the full slate
    all_games_for_log = fetch_espn_scoreboard(target_date)
    log_count = insert_game_log_entries(
        str(DATABASE_PATH), game_date_str_log, all_games_for_log, pred_lookup, bet_lookup,
    )
    if log_count > 0:
        logger.info("Game log: recorded %d games for %s", log_count, game_date_str_log)
```

**Step 3: Add game log settlement in `settle_yesterdays_bets`**

In `scripts/daily_run.py`, inside `settle_yesterdays_bets()`, after the existing CLV pass (~line 303, before the `return` statement), add:

```python
    # --- Game Log: settle ALL completed games (not just bets) ---
    all_completed = [g for g in games if g["status"] in ("STATUS_FINAL", "STATUS_FINAL_OT")]
    if all_completed:
        # Build closing odds lookup from the ESPN Core fetcher results
        gl_closing_odds: dict[str, dict] = {}
        if settled_game_ids and closing_odds:
            for gid, snapshot in closing_odds.items():
                gl_closing_odds[gid] = {
                    "home": snapshot.home_ml_close or snapshot.home_moneyline,
                    "away": snapshot.away_ml_close or snapshot.away_moneyline,
                }

        # Also fetch closing odds for non-bet games
        non_bet_game_ids = [
            g["game_id"] for g in all_completed if g["game_id"] not in settled_game_ids
        ]
        if non_bet_game_ids:
            try:
                nb_fetcher = ESPNCoreOddsFetcher(sport="ncaab")
                for gid in non_bet_game_ids:
                    try:
                        snapshots = nb_fetcher.fetch_game_odds(gid)
                        if snapshots:
                            pre_game = [s for s in snapshots if s.provider_id != 59]
                            best = pre_game[0] if pre_game else snapshots[0]
                            gl_closing_odds[gid] = {
                                "home": best.home_ml_close or best.home_moneyline,
                                "away": best.away_ml_close or best.away_moneyline,
                            }
                            # Also store to odds_snapshots for the proprietary DB
                            _store_closing_snapshot(db, best)
                    except Exception as e:
                        logger.debug("Closing odds failed for non-bet game %s: %s", gid, e)
                nb_fetcher.close()
            except Exception as e:
                logger.warning("Non-bet closing odds fetch failed: %s", e)

        gl_settled = settle_game_log_entries(
            str(DATABASE_PATH), all_completed, gl_closing_odds,
        )
        logger.info("Game log: settled %d/%d completed games", gl_settled, len(all_completed))
```

**Note:** The `closing_odds` variable (dict of game_id -> OddsSnapshot) is already populated in the existing Pass 2 code for settled bets. We reuse it and extend with non-bet games.

**Step 4: Verify the pipeline runs in dry-run mode**

Run: `venv/Scripts/python.exe scripts/daily_run.py --dry-run --skip-settle`
Expected: Pipeline runs, game log insert logged. No DB writes in dry-run.

Wait — the game log insert is NOT guarded by dry_run. We need to consider: should dry-run skip game log writes? The game log is append-only and non-destructive, but `--dry-run` semantics should skip ALL DB writes.

Add this guard in the game log insert block:

```python
    if not dry_run:
        log_count = insert_game_log_entries(...)
```

Hmm, but `run_predictions` already has `dry_run` as a parameter. We should pass it through. This requires wrapping the game log insert with `if not dry_run:`.

**Step 5: Commit**

```bash
git add scripts/daily_run.py
git commit -m "feat: integrate game_log into daily pipeline (insert + settle)"
```

---

### Task 5: Build Standalone Script `scripts/generate_game_log.py`

**Files:**
- Create: `scripts/generate_game_log.py`

**Step 1: Write the script**

```python
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
    rows = conn.execute(
        "SELECT * FROM game_log ORDER BY game_date DESC, home"
    ).fetchall()
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
    bet_count = conn.execute(
        "SELECT COUNT(*) as n FROM game_log WHERE bet_placed = 1"
    ).fetchone()["n"]
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
    parser = argparse.ArgumentParser(description="NCAAB Game Log Manager")
    parser.add_argument("--date", help="Insert games for date (YYYY-MM-DD)")
    parser.add_argument("--settle", action="store_true", help="Settle unsettled games")
    parser.add_argument("--settle-date", help="Settle games for specific date (YYYY-MM-DD)")
    parser.add_argument("--export", choices=["csv", "json"], help="Export game log")
    parser.add_argument("--stats", action="store_true", help="Show game log statistics")
    parser.add_argument(
        "--db", type=Path, default=NCAAB_DATABASE_PATH, help="Database path"
    )
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

        # No predictions in standalone mode — just log games with nulls
        inserted = insert_game_log_entries(
            str(args.db), args.date, games, {}, {},
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

        # Fetch closing odds for all completed games
        game_ids = [g["game_id"] for g in completed]
        espn_results = fetch_espn_closing_odds(game_ids)

        closing_odds = {}
        for gid, snapshot in espn_results.items():
            closing_odds[gid] = {
                "home": snapshot.home_ml_close or snapshot.home_moneyline,
                "away": snapshot.away_ml_close or snapshot.away_moneyline,
            }

        settled = settle_game_log_entries(str(args.db), completed, closing_odds)
        print(f"Settled {settled} games for {settle_date}")


if __name__ == "__main__":
    main()
```

**Step 2: Test manually**

Run: `venv/Scripts/python.exe scripts/generate_game_log.py --stats`
Expected: Shows 0 total games (empty table).

**Step 3: Commit**

```bash
git add scripts/generate_game_log.py
git commit -m "feat: add standalone game log manager script"
```

---

### Task 6: Extend Dashboard Data Export

**Files:**
- Modify: `scripts/generate_dashboard_data.py`

**Step 1: Add game log export to `generate_bundle()`**

In `scripts/generate_dashboard_data.py`, after `all_teams = load_all_team_ratings()` (~line 525), add:

```python
    # Load game log for dashboard
    game_log_data = _load_game_log(NCAAB_DATABASE_PATH)
```

Add this helper function before `generate_bundle()`:

```python
def _load_game_log(db_path: Path) -> list[dict]:
    """Load game_log table for dashboard export."""
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM game_log ORDER BY game_date DESC, home"
        ).fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        logger.warning("game_log table not found — run daily pipeline first")
        return []
    finally:
        conn.close()
```

Add `import sqlite3` at the top of the file (after existing imports).

Add to the `bundle` dict (before the `return bundle` line):

```python
        "game_log": game_log_data,
```

And in the `meta` dict:

```python
            "game_log_count": len(game_log_data),
```

**Step 2: Add import for NCAAB_DATABASE_PATH**

At the top of `generate_dashboard_data.py`, add:

```python
from config.settings import NCAAB_DATABASE_PATH
```

**Step 3: Verify**

Run: `venv/Scripts/python.exe scripts/generate_dashboard_data.py`
Expected: Generates bundle with `game_log: []` (empty until pipeline runs).

**Step 4: Commit**

```bash
git add scripts/generate_dashboard_data.py
git commit -m "feat: include game_log in dashboard data bundle"
```

---

### Task 7: Build Dashboard Page `dashboards/ncaab_game_log.html`

**Files:**
- Create: `dashboards/ncaab_game_log.html`
- Modify: `dashboards/ncaab_dashboard.html` (add nav link)

**Step 1: Create the game log dashboard page**

This is a self-contained HTML page that loads `ncaab_dashboard_bundle.json` and renders the `game_log` array as a sortable, filterable table. Match the existing dark theme from `ncaab_dashboard.html` (CSS variables, font, colors).

Key features:
- Load data from `../data/processed/ncaab_dashboard_bundle.json`
- Sortable columns (click header to sort)
- Filter: date range picker, bet/no-bet toggle, text search
- Color: green row highlight for `bet_placed=1`
- Summary bar: total games, games with bets, settled count
- Link back to main dashboard

The HTML file should be ~300-400 lines (self-contained JS, reuse CSS variables from the existing dashboard's `:root`).

I won't write the full HTML in this plan — the implementing engineer should reference `dashboards/ncaab_dashboard.html` for the exact CSS variables, table styling, and dark theme. The structure is:

```
<header> with title + link to main dashboard
<controls> with date filter, bet filter, search
<summary bar> with stats
<table> with all game_log columns, sortable headers
<script> that fetches JSON, renders table, handles sort/filter
```

**Step 2: Add nav link to existing dashboard**

In `dashboards/ncaab_dashboard.html`, in the `.header` div, add a link:

```html
<a href="ncaab_game_log.html" style="...">Game Log</a>
```

**Step 3: Test locally**

Run: `cd dashboards && python -m http.server 8765`
Open `http://localhost:8765/ncaab_game_log.html` — should show empty table with "No games recorded yet."

**Step 4: Commit**

```bash
git add dashboards/ncaab_game_log.html dashboards/ncaab_dashboard.html
git commit -m "feat: add game log dashboard page with sort/filter"
```

---

### Task 8: Integration Test

**Files:**
- Create: `tests/test_game_log_integration.py`

**Step 1: Write the integration test**

```python
"""Integration test for the full game log lifecycle:
insert -> settle -> export -> verify.
"""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database."""
    from tracking.database import BettingDatabase
    path = str(tmp_path / "test_integration.db")
    BettingDatabase(path)
    return path


# Synthetic games resembling ESPN Scoreboard output
SAMPLE_GAMES = [
    {"game_id": "401720100", "home": "DUKE", "away": "UNC",
     "home_name": "Duke", "away_name": "North Carolina",
     "home_score": 0, "away_score": 0, "status": "STATUS_SCHEDULED"},
    {"game_id": "401720101", "home": "UK", "away": "FLA",
     "home_name": "Kentucky", "away_name": "Florida",
     "home_score": 0, "away_score": 0, "status": "STATUS_SCHEDULED"},
    {"game_id": "401720102", "home": "GONZ", "away": "SMC",
     "home_name": "Gonzaga", "away_name": "Saint Mary's",
     "home_score": 0, "away_score": 0, "status": "STATUS_SCHEDULED"},
]

SAMPLE_PREDICTIONS = {
    "401720100": {"model_prob_home": 0.65, "edge": 0.12,
                   "odds_opening_home": -180, "odds_opening_away": 150},
    "401720101": {"model_prob_home": 0.55, "edge": 0.08,
                   "odds_opening_home": -130, "odds_opening_away": 110},
    # 401720102 deliberately missing — no odds available
}

SAMPLE_BETS = {"401720100": "home"}  # Only bet on Duke


class TestGameLogIntegration:
    """Full lifecycle: insert -> settle -> export."""

    def test_full_lifecycle(self, db_path, tmp_path):
        from tracking.game_log import insert_game_log_entries, settle_game_log_entries

        # Phase 1: Insert
        inserted = insert_game_log_entries(
            db_path, "2026-03-11", SAMPLE_GAMES, SAMPLE_PREDICTIONS, SAMPLE_BETS,
        )
        assert inserted == 3

        # Verify state
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM game_log ORDER BY game_id").fetchall()
        assert len(rows) == 3
        assert rows[0]["bet_placed"] == 1  # Duke game
        assert rows[0]["bet_side"] == "home"
        assert rows[1]["bet_placed"] == 0  # Kentucky game
        assert rows[2]["model_prob_home"] is None  # Gonzaga — no prediction

        # Phase 2: Settle
        completed = [
            {"game_id": "401720100", "home": "DUKE", "away": "UNC",
             "home_score": 78, "away_score": 72},
            {"game_id": "401720101", "home": "UK", "away": "FLA",
             "home_score": 65, "away_score": 70},
            # 401720102 not completed yet
        ]
        closing = {
            "401720100": {"home": -200, "away": 170},
            "401720101": {"home": -120, "away": 100},
        }

        settled = settle_game_log_entries(db_path, completed, closing)
        assert settled == 2

        # Verify settled state
        rows = conn.execute("SELECT * FROM game_log ORDER BY game_id").fetchall()
        assert rows[0]["result"] == "home"  # Duke won
        assert rows[0]["home_score"] == 78
        assert rows[0]["odds_closing_home"] == -200
        assert rows[1]["result"] == "away"  # Florida won
        assert rows[2]["result"] is None    # Gonzaga not settled

        conn.close()

        # Phase 3: Export JSON
        from scripts.generate_game_log import export_game_log
        out = export_game_log(Path(db_path), fmt="json")
        data = json.loads(Path(out).read_text(encoding="utf-8"))
        assert len(data) == 3
        assert data[0]["result"] is not None or data[1]["result"] is not None
```

**Step 2: Run integration test**

Run: `venv/Scripts/python.exe -m pytest tests/test_game_log_integration.py -v -p no:examples`
Expected: PASS

**Step 3: Run full test suite to check for regressions**

Run: `venv/Scripts/python.exe -m pytest tests/test_game_log.py tests/test_game_log_integration.py -v -p no:examples`
Expected: All PASS

**Step 4: Commit**

```bash
git add tests/test_game_log_integration.py
git commit -m "test: add game_log integration test (insert -> settle -> export)"
```

---

### Task 9: Lint, Format, Final Verification

**Step 1: Run ruff**

```bash
venv/Scripts/python.exe -m ruff check tracking/game_log.py scripts/generate_game_log.py scripts/daily_run.py scripts/generate_dashboard_data.py --fix
venv/Scripts/python.exe -m ruff format tracking/game_log.py scripts/generate_game_log.py scripts/daily_run.py scripts/generate_dashboard_data.py
```

**Step 2: Run all game_log tests**

```bash
venv/Scripts/python.exe -m pytest tests/test_game_log.py tests/test_game_log_integration.py -v -p no:examples
```

**Step 3: Run existing daily_run tests to verify no regressions**

```bash
venv/Scripts/python.exe -m pytest tests/test_daily_run.py -v -p no:examples -x -q 2>&1 | head -40
```

**Step 4: Manual smoke test — dry run**

```bash
venv/Scripts/python.exe scripts/daily_run.py --dry-run --skip-settle
venv/Scripts/python.exe scripts/generate_game_log.py --stats
```

**Step 5: Commit any lint fixes**

```bash
git add -A
git commit -m "chore: lint and format game_log implementation"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 0 | Fix `groups=50` missing from scoreboard fetches | `daily_predictions.py`, `collect_closing_odds.py` |
| 1 | Add `game_log` table to schema | `tracking/database.py`, `tests/test_game_log.py` |
| 2 | Insert logic (`tracking/game_log.py`) | `tracking/game_log.py`, `tests/test_game_log.py` |
| 3 | Settlement logic | `tracking/game_log.py`, `tests/test_game_log.py` |
| 4 | Integrate into `daily_run.py` | `scripts/daily_run.py` |
| 5 | Standalone script | `scripts/generate_game_log.py` |
| 6 | Dashboard data export | `scripts/generate_dashboard_data.py` |
| 7 | Dashboard HTML page | `dashboards/ncaab_game_log.html`, `dashboards/ncaab_dashboard.html` |
| 8 | Integration test | `tests/test_game_log_integration.py` |
| 9 | Lint + final verification | All modified files |

**Estimated commits:** 9
**Test coverage:** 11+ unit tests + 1 integration test
