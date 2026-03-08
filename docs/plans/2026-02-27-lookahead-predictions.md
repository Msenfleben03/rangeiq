# Lookahead Predictions & Position Building Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove single-day prediction caps so the pipeline fetches odds and generates predictions for all games with available odds (up to 7 days out), with position-building bet sizing that scales up as gameday approaches.

**Architecture:** Add `position_entry` column to the bets table and drop the UNIQUE constraint that blocks multiple bets per game. Introduce a days-out Kelly multiplier in `PaperBettingConfig` so early bets are sized smaller. Refactor `daily_run.py` to loop over a configurable lookahead window, calling `run_predictions()` per date. Update `auto_record_bets_from_predictions()` to query existing position size before recording and only add when there's room under the Kelly cap.

**Tech Stack:** Python 3.11+, SQLite, pandas, pytest

---

### Task 1: Schema Migration — Add `position_entry` and Drop UNIQUE Constraint

**Files:**
- Modify: `tracking/database.py:70-103` (CREATE TABLE + migration block)
- Test: `tests/test_lookahead.py` (new file)

**Step 1: Write the failing test**

```python
# tests/test_lookahead.py
"""Tests for lookahead predictions and position-building."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tracking.database import BettingDatabase


@pytest.fixture
def db(tmp_path):
    """Fresh database for each test."""
    db_path = tmp_path / "test_betting.db"
    return BettingDatabase(str(db_path))


class TestPositionEntrySchema:
    """Test that bets table supports multiple entries per game."""

    def test_position_entry_column_exists(self, db):
        """position_entry column should exist in bets table."""
        rows = db.execute_query("PRAGMA table_info(bets)")
        columns = {r["name"] for r in rows}
        assert "position_entry" in columns

    def test_multiple_bets_same_game_allowed(self, db):
        """Should allow multiple bets on same game+side+sportsbook."""
        base = {
            "sport": "ncaab",
            "game_date": "2026-03-01",
            "game_id": "401720001",
            "bet_type": "moneyline",
            "selection": "Duke Blue Devils ML",
            "odds_placed": 150,
            "stake": 70.0,
            "sportsbook": "paper",
            "position_entry": 1,
        }
        id1 = db.insert_bet(base)
        assert id1 > 0

        entry2 = {**base, "position_entry": 2, "odds_placed": 140, "stake": 50.0}
        id2 = db.insert_bet(entry2)
        assert id2 > 0
        assert id2 != id1

    def test_duplicate_position_entry_rejected(self, db):
        """Same game+side+sportsbook+position_entry should be rejected."""
        base = {
            "sport": "ncaab",
            "game_date": "2026-03-01",
            "game_id": "401720001",
            "bet_type": "moneyline",
            "selection": "Duke Blue Devils ML",
            "odds_placed": 150,
            "stake": 70.0,
            "sportsbook": "paper",
            "position_entry": 1,
        }
        db.insert_bet(base)
        dup_id = db.insert_bet(base)
        assert dup_id == -1  # Duplicate rejected
```

**Step 2: Run test to verify it fails**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py::TestPositionEntrySchema -v`
Expected: FAIL — `position_entry` column doesn't exist, second insert silently rejected by old UNIQUE constraint.

**Step 3: Write the migration**

In `tracking/database.py`, in the `_create_tables` method, after the existing `snapshot_type` migration block, add:

```python
# Migration: position_entry column + updated UNIQUE constraint
try:
    cursor.execute(
        "ALTER TABLE bets ADD COLUMN position_entry INTEGER DEFAULT 1"
    )
    logger.info("Added position_entry column to bets")
except sqlite3.OperationalError:
    pass  # Column already exists

# Rebuild UNIQUE constraint (SQLite requires table rebuild)
# Check if old constraint still exists by attempting a known-duplicate insert
try:
    cursor.execute("SELECT sql FROM sqlite_master WHERE name='bets'")
    create_sql = cursor.fetchone()[0]
    if "UNIQUE(game_id, bet_type, selection, sportsbook)" in create_sql and \
       "position_entry" not in create_sql.split("UNIQUE")[1]:
        # Old constraint — rebuild table
        cursor.execute("""
            CREATE TABLE bets_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sport TEXT NOT NULL,
                league TEXT,
                game_date DATE NOT NULL,
                game_id TEXT,
                bet_type TEXT NOT NULL,
                selection TEXT NOT NULL,
                line REAL,
                odds_placed INTEGER NOT NULL,
                odds_closing INTEGER,
                model_probability REAL,
                model_edge REAL,
                stake REAL NOT NULL,
                sportsbook TEXT NOT NULL,
                result TEXT,
                profit_loss REAL,
                actual_profit_loss REAL,
                clv REAL,
                notes TEXT,
                is_live BOOLEAN DEFAULT FALSE,
                is_settled BOOLEAN DEFAULT FALSE,
                settled_at TIMESTAMP,
                bet_uuid TEXT,
                placed_at TIMESTAMP,
                position_entry INTEGER DEFAULT 1,
                UNIQUE(game_id, bet_type, selection, sportsbook, position_entry)
            )
        """)
        cursor.execute("INSERT INTO bets_new SELECT *, 1 FROM bets WHERE 1=0")
        # Copy existing data — handle column mismatch gracefully
        existing_cols = [
            r[1] for r in cursor.execute("PRAGMA table_info(bets)").fetchall()
        ]
        new_cols = [
            r[1] for r in cursor.execute("PRAGMA table_info(bets_new)").fetchall()
        ]
        shared = [c for c in new_cols if c in existing_cols]
        cols_str = ", ".join(shared)
        cursor.execute(
            f"INSERT OR IGNORE INTO bets_new ({cols_str}) "
            f"SELECT {cols_str} FROM bets"
        )
        cursor.execute("DROP TABLE bets")
        cursor.execute("ALTER TABLE bets_new RENAME TO bets")
        logger.info("Rebuilt bets table with position_entry UNIQUE constraint")
except Exception as e:
    logger.debug("Bets table constraint check: %s", e)
```

Also update the CREATE TABLE in `_create_tables` to include `position_entry` and the new UNIQUE constraint for fresh databases:

```python
"""CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sport TEXT NOT NULL,
    league TEXT,
    game_date DATE NOT NULL,
    game_id TEXT,
    bet_type TEXT NOT NULL,
    selection TEXT NOT NULL,
    line REAL,
    odds_placed INTEGER NOT NULL,
    odds_closing INTEGER,
    model_probability REAL,
    model_edge REAL,
    stake REAL NOT NULL,
    sportsbook TEXT NOT NULL,
    result TEXT,
    profit_loss REAL,
    actual_profit_loss REAL,
    clv REAL,
    notes TEXT,
    is_live BOOLEAN DEFAULT FALSE,
    is_settled BOOLEAN DEFAULT FALSE,
    settled_at TIMESTAMP,
    bet_uuid TEXT,
    placed_at TIMESTAMP,
    position_entry INTEGER DEFAULT 1,
    UNIQUE(game_id, bet_type, selection, sportsbook, position_entry)
)
"""
```

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py::TestPositionEntrySchema -v`
Expected: 3 PASS

**Step 5: Commit**

```bash
git add tracking/database.py tests/test_lookahead.py
git commit -m "feat: add position_entry column to bets table for multi-entry positions"
```

---

### Task 2: Days-Out Kelly Multiplier Config & Sizing Logic

**Files:**
- Modify: `config/constants.py` (add to `PaperBettingConfig`)
- Modify: `betting/odds_converter.py` (add helper function)
- Test: `tests/test_lookahead.py` (append new test class)

**Step 1: Write the failing tests**

Append to `tests/test_lookahead.py`:

```python
from betting.odds_converter import get_days_out_multiplier


class TestDaysOutMultiplier:
    """Test speculative sizing based on days until gameday."""

    def test_gameday_full_multiplier(self):
        assert get_days_out_multiplier(0) == 1.0

    def test_one_day_out(self):
        assert get_days_out_multiplier(1) == 0.85

    def test_two_days_out(self):
        assert get_days_out_multiplier(2) == 0.65

    def test_three_days_out(self):
        assert get_days_out_multiplier(3) == 0.50

    def test_five_days_out(self):
        assert get_days_out_multiplier(5) == 0.35

    def test_seven_days_out(self):
        assert get_days_out_multiplier(7) == 0.35

    def test_beyond_window_clamps(self):
        """Days beyond max should use the lowest multiplier."""
        assert get_days_out_multiplier(14) == 0.35

    def test_negative_days_treated_as_gameday(self):
        """Games already started (negative days) use full multiplier."""
        assert get_days_out_multiplier(-1) == 1.0
```

**Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py::TestDaysOutMultiplier -v`
Expected: FAIL — `get_days_out_multiplier` not found.

**Step 3: Add config constants**

In `config/constants.py`, add to `PaperBettingConfig`:

```python
    # Lookahead window
    LOOKAHEAD_DAYS: int = 7  # Scan today through today+7

    # Days-out Kelly multipliers (speculative sizing)
    # Key = days until gameday, Value = fraction of full Kelly allocation
    DAYS_OUT_MULTIPLIERS: Dict[int, float] = None  # Use default in __post_init__

    # Position building
    EDGE_ADD_THRESHOLD: float = 0.02  # 2pp minimum edge increase to add to position
    MIN_BET_DOLLARS: float = 10.0  # Below this, skip the entry

    def __post_init__(self):
        if self.DAYS_OUT_MULTIPLIERS is None:
            self.DAYS_OUT_MULTIPLIERS = {
                0: 1.0,    # Gameday — full conviction
                1: 0.85,   # Near-complete info
                2: 0.65,   # Good info, some uncertainty
                3: 0.50,   # Moderate speculation
                4: 0.50,
                5: 0.35,   # High speculation
                6: 0.35,
                7: 0.35,
            }
```

**Step 4: Implement the helper function**

In `betting/odds_converter.py`, add:

```python
def get_days_out_multiplier(days_out: int) -> float:
    """Get Kelly multiplier based on days until gameday.

    Early bets are sized smaller (speculative). Gameday bets get full
    Kelly allocation. Total position across all entries for a game is
    capped at the Kelly-optimal amount for the current edge.

    Args:
        days_out: Days until game starts. 0 = gameday, negative = started.

    Returns:
        Multiplier to apply to Kelly fraction (0.0 to 1.0).
    """
    from config.constants import PAPER_BETTING

    if days_out <= 0:
        return 1.0

    multipliers = PAPER_BETTING.DAYS_OUT_MULTIPLIERS
    if days_out in multipliers:
        return multipliers[days_out]

    # Beyond max configured day — use smallest multiplier
    return min(multipliers.values())
```

**Step 5: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py::TestDaysOutMultiplier -v`
Expected: 8 PASS

**Step 6: Commit**

```bash
git add config/constants.py betting/odds_converter.py tests/test_lookahead.py
git commit -m "feat: add days-out Kelly multiplier for speculative position sizing"
```

---

### Task 3: Position Query Helper & Sizing Logic

**Files:**
- Modify: `tracking/logger.py` (add `get_position_summary` and `calculate_entry_stake`)
- Test: `tests/test_lookahead.py` (append new test class)

**Step 1: Write the failing tests**

Append to `tests/test_lookahead.py`:

```python
from tracking.logger import get_position_summary, calculate_entry_stake


class TestPositionSummary:
    """Test querying existing position for a game."""

    def test_no_existing_position(self, db):
        summary = get_position_summary(db, "401720001", "Duke Blue Devils ML")
        assert summary["total_staked"] == 0.0
        assert summary["entry_count"] == 0
        assert summary["max_entry"] == 0

    def test_single_entry_position(self, db):
        db.insert_bet({
            "sport": "ncaab", "game_date": "2026-03-01",
            "game_id": "401720001", "bet_type": "moneyline",
            "selection": "Duke Blue Devils ML", "odds_placed": 150,
            "stake": 70.0, "sportsbook": "paper", "position_entry": 1,
        })
        summary = get_position_summary(db, "401720001", "Duke Blue Devils ML")
        assert summary["total_staked"] == 70.0
        assert summary["entry_count"] == 1
        assert summary["max_entry"] == 1

    def test_multi_entry_position(self, db):
        for i, (odds, stake) in enumerate([(150, 70), (140, 50), (130, 80)], 1):
            db.insert_bet({
                "sport": "ncaab", "game_date": "2026-03-01",
                "game_id": "401720001", "bet_type": "moneyline",
                "selection": "Duke Blue Devils ML", "odds_placed": odds,
                "stake": float(stake), "sportsbook": "paper",
                "position_entry": i,
            })
        summary = get_position_summary(db, "401720001", "Duke Blue Devils ML")
        assert summary["total_staked"] == 200.0
        assert summary["entry_count"] == 3
        assert summary["max_entry"] == 3


class TestCalculateEntryStake:
    """Test position-aware stake calculation."""

    def test_new_position_uses_multiplier(self):
        """First entry on day-5 game should apply 0.35x multiplier."""
        stake = calculate_entry_stake(
            kelly_optimal=200.0,
            existing_staked=0.0,
            days_out=5,
            min_bet=10.0,
        )
        assert stake == pytest.approx(70.0)  # 200 * 0.35

    def test_gameday_fills_remaining(self):
        """Gameday entry should fill up to full Kelly."""
        stake = calculate_entry_stake(
            kelly_optimal=200.0,
            existing_staked=70.0,
            days_out=0,
            min_bet=10.0,
        )
        assert stake == pytest.approx(130.0)  # 200 - 70

    def test_position_already_full(self):
        """Should return 0 if already at or above Kelly cap."""
        stake = calculate_entry_stake(
            kelly_optimal=200.0,
            existing_staked=200.0,
            days_out=0,
            min_bet=10.0,
        )
        assert stake == 0.0

    def test_over_positioned_returns_zero(self):
        """If existing > Kelly optimal (line moved), return 0."""
        stake = calculate_entry_stake(
            kelly_optimal=60.0,
            existing_staked=70.0,
            days_out=0,
            min_bet=10.0,
        )
        assert stake == 0.0

    def test_below_min_bet_returns_zero(self):
        """If remaining room is below min bet, skip."""
        stake = calculate_entry_stake(
            kelly_optimal=200.0,
            existing_staked=195.0,
            days_out=0,
            min_bet=10.0,
        )
        assert stake == 0.0  # Only $5 room, below $10 min

    def test_mid_week_partial_fill(self):
        """Day-2 with existing position should fill to day-2 cap."""
        stake = calculate_entry_stake(
            kelly_optimal=200.0,
            existing_staked=70.0,
            days_out=2,
            min_bet=10.0,
        )
        # Day-2 multiplier = 0.65, allowed = 200 * 0.65 = 130
        # Room = 130 - 70 = 60
        assert stake == pytest.approx(60.0)
```

**Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py::TestPositionSummary tests/test_lookahead.py::TestCalculateEntryStake -v`
Expected: FAIL — functions don't exist.

**Step 3: Implement the functions**

In `tracking/logger.py`, add:

```python
from betting.odds_converter import get_days_out_multiplier


def get_position_summary(
    db: BettingDatabase,
    game_id: str,
    selection: str,
) -> dict[str, Any]:
    """Query the current position for a game+side.

    Args:
        db: BettingDatabase instance.
        game_id: ESPN game ID.
        selection: Bet selection string (e.g. "Duke Blue Devils ML").

    Returns:
        Dict with total_staked, entry_count, max_entry.
    """
    rows = db.execute_query(
        """SELECT
            COALESCE(SUM(stake), 0) as total_staked,
            COUNT(*) as entry_count,
            COALESCE(MAX(position_entry), 0) as max_entry
        FROM bets
        WHERE game_id = ? AND selection = ? AND result IS NULL""",
        (game_id, selection),
    )
    if rows:
        return {
            "total_staked": float(rows[0]["total_staked"]),
            "entry_count": int(rows[0]["entry_count"]),
            "max_entry": int(rows[0]["max_entry"]),
        }
    return {"total_staked": 0.0, "entry_count": 0, "max_entry": 0}


def calculate_entry_stake(
    kelly_optimal: float,
    existing_staked: float,
    days_out: int,
    min_bet: float = 10.0,
) -> float:
    """Calculate stake for a new position entry.

    Uses the days-out multiplier to cap how much of the full Kelly
    allocation is allowed at this point in time. Only the remaining
    room (allowed minus already staked) is returned.

    Args:
        kelly_optimal: Full Kelly-optimal stake at current odds/edge.
        existing_staked: Total already staked on this position.
        days_out: Days until gameday (0 = gameday).
        min_bet: Minimum bet size — below this returns 0.

    Returns:
        Stake for this entry, or 0.0 if position is full or below min.
    """
    multiplier = get_days_out_multiplier(days_out)
    allowed_total = kelly_optimal * multiplier
    remaining = allowed_total - existing_staked

    if remaining < min_bet:
        return 0.0

    return round(remaining, 2)
```

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py::TestPositionSummary tests/test_lookahead.py::TestCalculateEntryStake -v`
Expected: 9 PASS

**Step 5: Commit**

```bash
git add tracking/logger.py tests/test_lookahead.py
git commit -m "feat: add position query and entry stake calculation for position building"
```

---

### Task 4: Update `auto_record_bets_from_predictions()` for Position Building

**Files:**
- Modify: `tracking/logger.py:177-305` (`auto_record_bets_from_predictions`)
- Test: `tests/test_lookahead.py` (append new test class)

**Step 1: Write the failing tests**

Append to `tests/test_lookahead.py`:

```python
class TestAutoRecordPositionBuilding:
    """Test that auto_record handles multi-entry positions correctly."""

    def _make_predictions_df(self, games):
        """Build a predictions DataFrame from game dicts."""
        return pd.DataFrame(games)

    def test_first_entry_recorded_with_position_entry_1(self, db):
        """First bet on a game should get position_entry=1."""
        preds = self._make_predictions_df([{
            "game_id": "401720001", "home": "DUKE", "away": "UNC",
            "home_name": "Duke Blue Devils", "away_name": "North Carolina Tar Heels",
            "home_prob": 0.65, "away_prob": 0.35,
            "predicted_spread": -5.0, "bart_adj": 0.01,
            "rec_side": "HOME", "rec_odds": 150, "rec_kelly": 0.04,
            "rec_stake": 200.0,
            "home_edge": 0.10, "away_edge": -0.05,
        }])
        recorded = auto_record_bets_from_predictions(
            db, preds, "2026-03-05", days_out=5,
        )
        assert len(recorded) == 1
        # Check DB
        bets = db.execute_query(
            "SELECT position_entry, stake FROM bets WHERE game_id='401720001'"
        )
        assert len(bets) == 1
        assert bets[0]["position_entry"] == 1

    def test_second_entry_gets_position_entry_2(self, db):
        """Adding to a position should increment position_entry."""
        # Entry 1
        db.insert_bet({
            "sport": "ncaab", "game_date": "2026-03-05",
            "game_id": "401720001", "bet_type": "moneyline",
            "selection": "Duke Blue Devils ML", "odds_placed": 150,
            "stake": 70.0, "sportsbook": "paper", "position_entry": 1,
        })
        # Entry 2 via auto_record
        preds = self._make_predictions_df([{
            "game_id": "401720001", "home": "DUKE", "away": "UNC",
            "home_name": "Duke Blue Devils", "away_name": "North Carolina Tar Heels",
            "home_prob": 0.65, "away_prob": 0.35,
            "predicted_spread": -5.0, "bart_adj": 0.01,
            "rec_side": "HOME", "rec_odds": 140, "rec_kelly": 0.04,
            "rec_stake": 200.0,
            "home_edge": 0.12, "away_edge": -0.05,
        }])
        recorded = auto_record_bets_from_predictions(
            db, preds, "2026-03-05", days_out=3,
        )
        assert len(recorded) == 1
        bets = db.execute_query(
            "SELECT position_entry FROM bets WHERE game_id='401720001' "
            "ORDER BY position_entry"
        )
        assert len(bets) == 2
        assert bets[1]["position_entry"] == 2

    def test_position_full_skips_recording(self, db):
        """Should skip if existing position already meets Kelly cap."""
        db.insert_bet({
            "sport": "ncaab", "game_date": "2026-03-05",
            "game_id": "401720001", "bet_type": "moneyline",
            "selection": "Duke Blue Devils ML", "odds_placed": 150,
            "stake": 250.0, "sportsbook": "paper", "position_entry": 1,
        })
        preds = self._make_predictions_df([{
            "game_id": "401720001", "home": "DUKE", "away": "UNC",
            "home_name": "Duke Blue Devils", "away_name": "North Carolina Tar Heels",
            "home_prob": 0.65, "away_prob": 0.35,
            "predicted_spread": -5.0, "bart_adj": 0.01,
            "rec_side": "HOME", "rec_odds": 140, "rec_kelly": 0.04,
            "rec_stake": 200.0,
            "home_edge": 0.10, "away_edge": -0.05,
        }])
        recorded = auto_record_bets_from_predictions(
            db, preds, "2026-03-05", days_out=0,
        )
        assert len(recorded) == 0
```

**Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py::TestAutoRecordPositionBuilding -v`
Expected: FAIL — `auto_record_bets_from_predictions` doesn't accept `days_out` param.

**Step 3: Update `auto_record_bets_from_predictions`**

In `tracking/logger.py`, modify the function signature and body:

```python
def auto_record_bets_from_predictions(
    db: BettingDatabase,
    predictions_df: "pd.DataFrame",
    game_date: str,
    dry_run: bool = False,
    max_bets: int = 10,
    days_out: int = 0,
) -> list[dict]:
    """Automatically record paper bets from prediction DataFrame.

    Supports position building: queries existing entries for each game
    and only adds a new entry if there's room under the Kelly cap
    (adjusted by the days-out multiplier).

    Args:
        db: BettingDatabase instance.
        predictions_df: DataFrame from generate_predictions() with rec_side.
        game_date: Date string in YYYY-MM-DD format.
        dry_run: If True, return bets without inserting into database.
        max_bets: Maximum number of NEW entries to record per run.
        days_out: Days until gameday (0 = gameday). Controls Kelly multiplier.

    Returns:
        List of bet dicts that were recorded (or would be in dry_run mode).
    """
    import pandas as pd

    if predictions_df.empty:
        return []

    # Filter to recommendations only
    has_rec = (
        predictions_df["rec_side"].notna()
        if "rec_side" in predictions_df.columns
        else pd.Series(False, index=predictions_df.index)
    )
    recs = predictions_df[has_rec].copy()

    if recs.empty:
        logger.info("No bet recommendations to record")
        return []

    # Sort by edge (best first) and limit
    if "home_edge" in recs.columns and "away_edge" in recs.columns:
        recs["best_edge"] = recs.apply(
            lambda r: r["home_edge"] if r.get("rec_side") == "HOME" else r.get("away_edge", 0),
            axis=1,
        )
        recs = recs.sort_values("best_edge", ascending=False)

    recs = recs.head(max_bets)

    # Skip injury-flagged rows
    if "injury_flag" in recs.columns:
        flagged_count = recs["injury_flag"].sum()
        if flagged_count > 0:
            logger.info(
                "Skipping %d injury-flagged bets (already suppressed)",
                int(flagged_count),
            )
        recs = recs[recs["injury_flag"] != True]  # noqa: E712

    recorded: list[dict] = []
    for _, row in recs.iterrows():
        side = row["rec_side"]
        team = row["home"] if side == "HOME" else row["away"]
        team_name = row.get("home_name", team) if side == "HOME" else row.get("away_name", team)
        selection = f"{team_name} ML"
        game_id = str(row.get("game_id", ""))

        # Position building: check existing entries
        position = get_position_summary(db, game_id, selection)
        kelly_optimal = float(row.get("rec_stake", 0))

        entry_stake = calculate_entry_stake(
            kelly_optimal=kelly_optimal,
            existing_staked=position["total_staked"],
            days_out=days_out,
            min_bet=PAPER_BETTING.MIN_BET_DOLLARS,
        )

        if entry_stake <= 0:
            logger.info(
                "Position full for %s (staked=$%.0f, kelly=$%.0f, days_out=%d) — skipping",
                selection, position["total_staked"], kelly_optimal, days_out,
            )
            continue

        next_entry = position["max_entry"] + 1

        # Build notes with ESPN context if available
        notes_parts = [
            f"Auto-recorded paper bet. Bart adj: {row.get('bart_adj', 0):.4f}",
            f"Position entry #{next_entry}, days_out={days_out}",
        ]
        espn_prob = row.get("espn_prob")
        if pd.notna(espn_prob):
            div_val = row.get("prob_divergence", 0) or 0
            notes_parts.append(f"ESPN prob: {espn_prob:.0%}, divergence: {div_val:+.0%}")

        bet_data = {
            "sport": "ncaab",
            "game_date": game_date,
            "game_id": game_id,
            "bet_type": "moneyline",
            "selection": selection,
            "odds_placed": int(row.get("rec_odds", 0)),
            "stake": entry_stake,
            "sportsbook": "paper",
            "model_probability": float(
                row["home_prob"] if side == "HOME" else row["away_prob"]
            ),
            "model_edge": float(
                row.get("home_edge", 0) if side == "HOME" else row.get("away_edge", 0)
            ),
            "notes": ". ".join(notes_parts),
            "position_entry": next_entry,
        }

        if dry_run:
            logger.info(
                "[DRY RUN] Would record: %s entry #%d @ %+d "
                "(edge: %.1f%%, stake: $%.0f, days_out: %d)",
                bet_data["selection"], next_entry,
                bet_data["odds_placed"],
                bet_data["model_edge"] * 100,
                entry_stake, days_out,
            )
        else:
            limits = validate_bet_limits(bet_data["stake"], db)
            if not limits["allowed"]:
                logger.warning(
                    "Bet rejected: %s — %s", bet_data["selection"], limits["reason"]
                )
                continue

            try:
                bet_id = log_paper_bet(db, bet_data)
                bet_data["bet_id"] = bet_id
                logger.info(
                    "Recorded bet #%d: %s entry #%d @ %+d (edge: %.1f%%, stake: $%.0f)",
                    bet_id, bet_data["selection"], next_entry,
                    bet_data["odds_placed"],
                    bet_data["model_edge"] * 100, entry_stake,
                )
            except Exception as e:
                logger.error("Failed to record bet: %s — %s", bet_data["selection"], e)
                continue

        recorded.append(bet_data)

    logger.info(
        "%s %d/%d paper bets for %s (days_out=%d)",
        "Would record" if dry_run else "Recorded",
        len(recorded), len(recs), game_date, days_out,
    )
    return recorded
```

Also add the import at top of file:

```python
from config.constants import BANKROLL, PAPER_BETTING
```

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py::TestAutoRecordPositionBuilding -v`
Expected: 3 PASS

**Step 5: Commit**

```bash
git add tracking/logger.py tests/test_lookahead.py
git commit -m "feat: update auto_record to support position building with days-out sizing"
```

---

### Task 5: Multi-Day Lookahead in `daily_run.py`

**Files:**
- Modify: `scripts/daily_run.py:316-481` (`run_predictions` and `main`)
- Test: `tests/test_lookahead.py` (append integration test class)

**Step 1: Write the failing tests**

Append to `tests/test_lookahead.py`:

```python
from unittest.mock import patch, MagicMock
from scripts.daily_run import run_lookahead_predictions


class TestRunLookaheadPredictions:
    """Test multi-day lookahead prediction loop."""

    @patch("scripts.daily_run.run_predictions")
    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_scans_multiple_days(self, mock_fetch, mock_run, db):
        """Should call fetch_espn_scoreboard for each day in window."""
        mock_fetch.return_value = []  # No games
        mock_run.return_value = pd.DataFrame()

        today = datetime(2026, 3, 1)
        run_lookahead_predictions(today, db, dry_run=True, lookahead_days=3)

        # Should scan today + 3 future days = 4 calls
        assert mock_fetch.call_count == 4

    @patch("scripts.daily_run.run_predictions")
    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_skips_days_with_no_games(self, mock_fetch, mock_run, db):
        """Should not call run_predictions for days with no games."""
        mock_fetch.side_effect = [
            [{"game_id": "1", "status": "STATUS_SCHEDULED"}],  # today
            [],  # tomorrow
            [{"game_id": "2", "status": "STATUS_SCHEDULED"}],  # day+2
        ]
        mock_run.return_value = pd.DataFrame()

        today = datetime(2026, 3, 1)
        run_lookahead_predictions(today, db, dry_run=True, lookahead_days=2)

        assert mock_run.call_count == 2  # today and day+2, not tomorrow

    @patch("scripts.daily_run.run_predictions")
    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_passes_correct_days_out(self, mock_fetch, mock_run, db):
        """Should pass days_out=0 for today, days_out=3 for day+3."""
        mock_fetch.return_value = [
            {"game_id": "1", "status": "STATUS_SCHEDULED"},
        ]
        mock_run.return_value = pd.DataFrame()

        today = datetime(2026, 3, 1)
        run_lookahead_predictions(today, db, dry_run=True, lookahead_days=3)

        # Check days_out kwarg for each call
        days_out_values = [
            call.kwargs.get("days_out", call.args[3] if len(call.args) > 3 else None)
            for call in mock_run.call_args_list
        ]
        assert days_out_values == [0, 1, 2, 3]
```

**Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py::TestRunLookaheadPredictions -v`
Expected: FAIL — `run_lookahead_predictions` doesn't exist.

**Step 3: Implement `run_lookahead_predictions`**

In `scripts/daily_run.py`, add a new function and update `run_predictions` signature:

```python
def run_predictions(
    target_date: datetime,
    db: BettingDatabase,
    dry_run: bool = False,
    days_out: int = 0,
) -> pd.DataFrame:
```

Update the `auto_record_bets_from_predictions` call inside `run_predictions` to pass `days_out`:

```python
    recorded = auto_record_bets_from_predictions(
        db=db,
        predictions_df=predictions,
        game_date=game_date_str,
        dry_run=dry_run,
        max_bets=PAPER_BETTING.MAX_BETS_PER_DAY,
        days_out=days_out,
    )
```

Add the new lookahead function:

```python
def run_lookahead_predictions(
    today: datetime,
    db: BettingDatabase,
    dry_run: bool = False,
    lookahead_days: int | None = None,
) -> dict[str, pd.DataFrame]:
    """Run predictions for today and all future dates with available games.

    Scans ESPN Scoreboard for each day in the lookahead window. For each
    day with games, runs the full prediction pipeline with days-out
    adjusted Kelly sizing.

    Args:
        today: The current date (day 0).
        db: BettingDatabase instance.
        dry_run: If True, preview bets without recording.
        lookahead_days: Days to scan ahead. Default from config.

    Returns:
        Dict mapping date string to predictions DataFrame.
    """
    if lookahead_days is None:
        lookahead_days = PAPER_BETTING.LOOKAHEAD_DAYS

    all_predictions: dict[str, pd.DataFrame] = {}

    for offset in range(lookahead_days + 1):
        target_date = today + timedelta(days=offset)
        date_str = target_date.strftime("%Y-%m-%d")

        # Discover games for this date
        games = fetch_espn_scoreboard(target_date)
        pre_game = [
            g for g in games
            if g["status"] in ("STATUS_SCHEDULED", "STATUS_PREGAME", "")
        ]

        if not pre_game:
            if offset == 0 and games:
                logger.info("Day+%d (%s): %d games, all started/completed", offset, date_str, len(games))
            elif not games:
                logger.debug("Day+%d (%s): no games found", offset, date_str)
            continue

        logger.info(
            "Day+%d (%s): %d pre-game / %d total",
            offset, date_str, len(pre_game), len(games),
        )

        predictions = run_predictions(
            target_date=target_date,
            db=db,
            dry_run=dry_run,
            days_out=offset,
        )
        all_predictions[date_str] = predictions

    return all_predictions
```

Update `main()` to use `run_lookahead_predictions` instead of the single `run_predictions` call:

```python
    # Step 2: Generate predictions across lookahead window
    print("\n--- Generating predictions (lookahead window) ---")
    all_predictions = run_lookahead_predictions(
        today=target_date,
        db=db,
        dry_run=args.dry_run,
    )

    if not all_predictions and not args.dry_run:
        logger.warning("No predictions generated across lookahead window")
```

Remove the old `sys.exit(1)` on empty predictions — with lookahead, some days having no games is normal.

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py::TestRunLookaheadPredictions -v`
Expected: 3 PASS

**Step 5: Run existing daily_run tests to verify no regressions**

Run: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py -v`
Expected: 31 PASS (same as before)

**Step 6: Commit**

```bash
git add scripts/daily_run.py tests/test_lookahead.py
git commit -m "feat: add multi-day lookahead prediction loop with days-out sizing"
```

---

### Task 6: Update `fetch_opening_odds.py` for Lookahead Window

**Files:**
- Modify: `scripts/fetch_opening_odds.py:75-176` (`fetch_opening_odds` and `main`)
- Test: `tests/test_lookahead.py` (append test class)

**Step 1: Write the failing tests**

Append to `tests/test_lookahead.py`:

```python
from scripts.fetch_opening_odds import fetch_opening_odds_lookahead


class TestFetchOpeningOddsLookahead:
    """Test multi-day opening odds fetch."""

    @patch("scripts.fetch_opening_odds.fetch_espn_scoreboard")
    @patch("scripts.fetch_opening_odds.ESPNCoreOddsFetcher")
    def test_scans_full_window(self, mock_fetcher_cls, mock_scoreboard, db):
        """Should scan all days in lookahead window."""
        mock_scoreboard.return_value = []

        today = datetime(2026, 3, 1)
        result = fetch_opening_odds_lookahead(db, today, lookahead_days=3)

        # today + 3 = 4 calls
        assert mock_scoreboard.call_count == 4
        assert len(result) == 4  # One result dict per day

    @patch("scripts.fetch_opening_odds.fetch_espn_scoreboard")
    @patch("scripts.fetch_opening_odds.ESPNCoreOddsFetcher")
    def test_aggregates_stats(self, mock_fetcher_cls, mock_scoreboard, db):
        """Should return per-day stats."""
        mock_scoreboard.side_effect = [
            [{"game_id": "1", "away_name": "A", "home_name": "B", "away": "A", "home": "B"}],
            [],
        ]
        mock_instance = MagicMock()
        mock_instance.fetch_game_odds.return_value = []
        mock_fetcher_cls.return_value = mock_instance

        today = datetime(2026, 3, 1)
        results = fetch_opening_odds_lookahead(db, today, lookahead_days=1)

        assert results[0]["games_found"] == 1
        assert results[1]["games_found"] == 0
```

**Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py::TestFetchOpeningOddsLookahead -v`
Expected: FAIL — function doesn't exist.

**Step 3: Implement `fetch_opening_odds_lookahead`**

In `scripts/fetch_opening_odds.py`, add:

```python
def fetch_opening_odds_lookahead(
    db: BettingDatabase,
    today: datetime,
    lookahead_days: int | None = None,
) -> list[dict]:
    """Fetch opening odds for all games in the lookahead window.

    Args:
        db: BettingDatabase instance.
        today: Current date (start of window).
        lookahead_days: Days to scan. Default from config.

    Returns:
        List of result dicts, one per day scanned.
    """
    from config.constants import PAPER_BETTING

    if lookahead_days is None:
        lookahead_days = PAPER_BETTING.LOOKAHEAD_DAYS

    results = []
    for offset in range(lookahead_days + 1):
        target = today + timedelta(days=offset)
        result = fetch_opening_odds(db, target)
        results.append(result)

    return results
```

Update `main()` to use the lookahead version:

```python
def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch opening odds for NCAAB games across lookahead window"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD). Default: today.",
    )
    parser.add_argument(
        "--lookahead-days",
        type=int,
        default=None,
        help="Days to scan ahead. Default from config.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview games without fetching odds.",
    )
    args = parser.parse_args()

    if args.date:
        today = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        today = datetime.now()

    if args.dry_run:
        from config.constants import PAPER_BETTING
        lookahead = args.lookahead_days or PAPER_BETTING.LOOKAHEAD_DAYS
        for offset in range(lookahead + 1):
            target = today + timedelta(days=offset)
            games = fetch_espn_scoreboard(target)
            date_str = target.strftime("%Y-%m-%d")
            print(f"Day+{offset} ({date_str}): {len(games)} games")
            for g in games:
                print(f"  {g['away_name']} @ {g['home_name']} ({g['game_id']})")
        return

    db = BettingDatabase(str(DATABASE_PATH))
    results = fetch_opening_odds_lookahead(db, today, args.lookahead_days)

    print(f"\n{'=' * 60}")
    print(f"Opening Odds Fetch -- Lookahead Window")
    print(f"{'=' * 60}")
    total_fetched = 0
    total_failed = 0
    for r in results:
        total_fetched += r["odds_fetched"]
        total_failed += r["odds_failed"]
        if r["games_found"] > 0:
            print(
                f"  {r['date']}: {r['games_found']} games, "
                f"{r['odds_fetched']} fetched, "
                f"{r['skipped_existing']} existing, "
                f"{r['odds_failed']} failed"
            )
    print(f"\nTotal: {total_fetched} fetched, {total_failed} failed")
```

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py::TestFetchOpeningOddsLookahead -v`
Expected: 2 PASS

**Step 5: Run existing opening odds tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_fetch_opening_odds.py -v`
Expected: 5 PASS

**Step 6: Commit**

```bash
git add scripts/fetch_opening_odds.py tests/test_lookahead.py
git commit -m "feat: extend opening odds fetch to scan full lookahead window"
```

---

### Task 7: Update Pipeline Orchestrator (`daily-pipeline.ps1`)

**Files:**
- Modify: `scripts/daily-pipeline.ps1:74-135` (step definitions)

**Step 1: No tests needed** — PowerShell orchestrator is validated by dry-run.

**Step 2: Update step definitions**

The `predictions` step already calls `daily_run.py --skip-settle`, which will now use the lookahead loop internally. No arg changes needed.

The `fetch_opening_odds` step should drop the implicit "tomorrow only" behavior. Update:

```powershell
    fetch_opening_odds = @{
        script    = "fetch_opening_odds.py"
        args      = @()  # Now scans full lookahead window by default
        critical  = $false
        timeout   = 300  # Increased: scanning 7 days of odds takes longer
    }
```

**Step 3: Verify with dry-run**

Run: `powershell -File scripts/daily-pipeline.ps1 -DryRun`
Expected: All 10 steps listed, no errors.

**Step 4: Commit**

```bash
git add scripts/daily-pipeline.ps1
git commit -m "feat: update pipeline timeout for multi-day odds fetch"
```

---

### Task 8: Full Integration Test & Regression Check

**Files:**
- Test: `tests/test_lookahead.py` (final integration test)
- Run: full test suite

**Step 1: Write end-to-end integration test**

Append to `tests/test_lookahead.py`:

```python
class TestEndToEndPositionBuilding:
    """Integration test: simulate 3-day position build-up."""

    def test_position_builds_over_multiple_days(self, db):
        """Simulate day-3, day-1, and gameday entries for same game."""
        game_id = "401720001"
        selection = "Duke Blue Devils ML"

        # Day-3 entry (speculative)
        db.insert_bet({
            "sport": "ncaab", "game_date": "2026-03-05",
            "game_id": game_id, "bet_type": "moneyline",
            "selection": selection, "odds_placed": 160,
            "stake": 50.0, "sportsbook": "paper", "position_entry": 1,
        })

        pos = get_position_summary(db, game_id, selection)
        assert pos["total_staked"] == 50.0
        assert pos["entry_count"] == 1

        # Day-1 add (kelly_optimal=200, multiplier=0.85, allowed=170)
        entry_stake = calculate_entry_stake(200.0, 50.0, days_out=1)
        assert entry_stake == pytest.approx(120.0)  # 170 - 50

        db.insert_bet({
            "sport": "ncaab", "game_date": "2026-03-05",
            "game_id": game_id, "bet_type": "moneyline",
            "selection": selection, "odds_placed": 140,
            "stake": entry_stake, "sportsbook": "paper", "position_entry": 2,
        })

        pos = get_position_summary(db, game_id, selection)
        assert pos["total_staked"] == 170.0
        assert pos["entry_count"] == 2

        # Gameday fill (kelly_optimal=200, multiplier=1.0, allowed=200)
        entry_stake = calculate_entry_stake(200.0, 170.0, days_out=0)
        assert entry_stake == pytest.approx(30.0)  # 200 - 170

        db.insert_bet({
            "sport": "ncaab", "game_date": "2026-03-05",
            "game_id": game_id, "bet_type": "moneyline",
            "selection": selection, "odds_placed": 130,
            "stake": entry_stake, "sportsbook": "paper", "position_entry": 3,
        })

        pos = get_position_summary(db, game_id, selection)
        assert pos["total_staked"] == 200.0
        assert pos["entry_count"] == 3
        assert pos["max_entry"] == 3

        # Verify CLV can be calculated per entry later
        bets = db.execute_query(
            "SELECT odds_placed, stake, position_entry FROM bets "
            "WHERE game_id=? ORDER BY position_entry",
            (game_id,),
        )
        assert [(b["odds_placed"], b["stake"]) for b in bets] == [
            (160, 50.0), (140, 120.0), (130, 30.0),
        ]
```

**Step 2: Run all lookahead tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_lookahead.py -v`
Expected: All tests PASS

**Step 3: Run full test suite for regressions**

Run: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py tests/test_fetch_opening_odds.py tests/test_kelly_sizer.py -v`
Expected: 31 + 5 + 15 = 51 PASS (same as baseline)

**Step 4: Commit**

```bash
git add tests/test_lookahead.py
git commit -m "test: add end-to-end position building integration test"
```

---

## Summary

| Task | What | New Tests |
|------|------|-----------|
| 1 | Schema migration: `position_entry` + new UNIQUE | 3 |
| 2 | Days-out Kelly multiplier config + helper | 8 |
| 3 | Position query + entry stake calculation | 9 |
| 4 | Update `auto_record` for position building | 3 |
| 5 | Multi-day lookahead loop in `daily_run.py` | 3 |
| 6 | Extend `fetch_opening_odds` to full window | 2 |
| 7 | Pipeline orchestrator timeout update | 0 (dry-run) |
| 8 | Integration test + regression check | 1 |
| **Total** | **8 tasks, 8 commits** | **29 new tests** |
