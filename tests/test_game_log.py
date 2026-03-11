"""Tests for game_log table schema and basic operations."""

import sqlite3
import tempfile
import os
import pytest

from tracking.database import BettingDatabase


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        yield BettingDatabase(db_path=db_path)


class TestGameLogSchema:
    """Test game_log table exists with correct schema."""

    def test_game_log_table_exists(self, db):
        rows = db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='game_log'"
        )
        assert len(rows) == 1

    def test_game_log_columns(self, db):
        rows = db.execute_query("PRAGMA table_info(game_log)")
        col_names = [r["name"] for r in rows]
        expected = [
            "id",
            "game_date",
            "game_id",
            "home",
            "away",
            "home_score",
            "away_score",
            "model_prob_home",
            "edge",
            "odds_opening_home",
            "odds_opening_away",
            "odds_closing_home",
            "odds_closing_away",
            "bet_placed",
            "bet_side",
            "result",
            "settled_at",
            "created_at",
        ]
        assert col_names == expected

    def test_game_id_unique_constraint(self, db):
        with db.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO game_log (game_date, game_id, home, away) "
                "VALUES ('2026-03-11', '401000001', 'DUKE', 'UNC')"
            )
        # Second insert with same game_id should raise IntegrityError
        with pytest.raises(sqlite3.IntegrityError):
            with db.get_cursor() as cursor:
                cursor.execute(
                    "INSERT INTO game_log (game_date, game_id, home, away) "
                    "VALUES ('2026-03-11', '401000001', 'DUKE', 'UNC')"
                )

    def test_schema_version_3(self, db):
        rows = db.execute_query("SELECT * FROM schema_version WHERE version = 3")
        assert len(rows) == 1
        assert "game_log" in rows[0]["description"]
