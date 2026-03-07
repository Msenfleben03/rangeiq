"""Tests for the NCAAB betting database schema (v2).

Verifies that tracking/database.py creates the expected tables and columns
after the per-sport split and CLV component overhaul.
"""

import sqlite3
import tempfile
from pathlib import Path


def test_bets_has_clv_components():
    """bets table must have CLV component columns and must NOT have removed columns."""
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase

        BettingDatabase(str(Path(tmp) / "test.db"))
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bets)").fetchall()]
        conn.close()
        assert "devig_prob_placed" in cols
        assert "devig_prob_closing" in cols
        assert "opening_odds" in cols
        assert "actual_profit_loss" not in cols
        assert "sport" not in cols


def test_odds_snapshots_has_market_type():
    """odds_snapshots table must have market_type column."""
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase

        BettingDatabase(str(Path(tmp) / "test.db"))
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(odds_snapshots)").fetchall()]
        conn.close()
        assert "market_type" in cols


def test_barttorvik_ratings_table_exists():
    """barttorvik_ratings, prop_bets, and schema_version tables must exist."""
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase

        BettingDatabase(str(Path(tmp) / "test.db"))
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        tables = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        conn.close()
        assert "barttorvik_ratings" in tables
        assert "prop_bets" in tables
        assert "schema_version" in tables


def test_barttorvik_ratings_has_four_factors():
    """barttorvik_ratings table must have all four-factor columns."""
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase

        BettingDatabase(str(Path(tmp) / "test.db"))
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(barttorvik_ratings)").fetchall()]
        conn.close()
        four_factors = ["efg_o", "efg_d", "tov_o", "tov_d", "orb", "drb", "ftr_o", "ftr_d"]
        for col in four_factors:
            assert col in cols, f"Missing four-factor column: {col}"


def test_predictions_has_no_sport_column():
    """predictions table must NOT have a sport column (per-sport DB split)."""
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase

        BettingDatabase(str(Path(tmp) / "test.db"))
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(predictions)").fetchall()]
        conn.close()
        assert "sport" not in cols


def test_schema_version_inserted():
    """schema_version table must contain version 2 row."""
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase

        BettingDatabase(str(Path(tmp) / "test.db"))
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        row = conn.execute("SELECT version FROM schema_version WHERE version=2").fetchone()
        conn.close()
        assert row is not None


def test_prop_bets_insert():
    """insert_prop_bet must insert a row into prop_bets."""
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase

        db = BettingDatabase(str(Path(tmp) / "test.db"))
        db.insert_prop_bet(
            {
                "game_id": "abc123",
                "game_date": "2026-03-05",
                "player_name": "Test Player",
                "prop_type": "points",
                "line": 22.5,
                "selection": "over",
                "odds_placed": -115,
                "sportsbook": "DraftKings",
            }
        )
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        count = conn.execute("SELECT COUNT(*) FROM prop_bets").fetchone()[0]
        conn.close()
        assert count == 1


def test_prop_bets_duplicate_skipped():
    """insert_prop_bet returns -1 on duplicate and does not raise."""
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase

        db = BettingDatabase(str(Path(tmp) / "test.db"))
        data = {
            "game_id": "abc123",
            "game_date": "2026-03-05",
            "player_name": "Test Player",
            "prop_type": "points",
            "line": 22.5,
            "selection": "over",
            "odds_placed": -115,
            "sportsbook": "DraftKings",
        }
        db.insert_prop_bet(data)
        result = db.insert_prop_bet(data)
        assert result == -1


def test_bets_unique_constraint_includes_position_entry():
    """bets UNIQUE constraint must include position_entry."""
    with tempfile.TemporaryDirectory() as tmp:
        from tracking.database import BettingDatabase

        BettingDatabase(str(Path(tmp) / "test.db"))
        conn = sqlite3.connect(str(Path(tmp) / "test.db"))
        create_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='bets'"
        ).fetchone()[0]
        conn.close()
        assert "position_entry" in create_sql
