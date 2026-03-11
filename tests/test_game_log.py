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


class TestGameLogInsert:
    """Test inserting games into game_log."""

    def test_insert_game_with_odds(self, db):
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

        inserted = insert_game_log_entries(db.db_path, "2026-03-11", games, predictions, bets)
        assert inserted == 1

        rows = db.execute_query("SELECT * FROM game_log WHERE game_id = '401720001'")
        row = rows[0]

        assert row["home"] == "DUKE"
        assert row["away"] == "UNC"
        assert row["model_prob_home"] == pytest.approx(0.65)
        assert row["edge"] == pytest.approx(0.12)
        assert row["odds_opening_home"] == -180
        assert row["odds_opening_away"] == 150
        assert row["bet_placed"] == 1
        assert row["bet_side"] == "home"

    def test_insert_game_without_odds(self, db):
        from tracking.game_log import insert_game_log_entries

        games = [
            {
                "game_id": "401720002",
                "home": "TEAM_A",
                "away": "TEAM_B",
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

        inserted = insert_game_log_entries(db.db_path, "2026-03-11", games, predictions, {})
        assert inserted == 1

        rows = db.execute_query("SELECT * FROM game_log WHERE game_id = '401720002'")
        row = rows[0]
        assert row["odds_opening_home"] is None
        assert row["edge"] is None
        assert row["bet_placed"] == 0
        assert row["bet_side"] is None

    def test_insert_duplicate_skipped(self, db):
        from tracking.game_log import insert_game_log_entries

        games = [{"game_id": "401720003", "home": "UK", "away": "FLA"}]
        predictions = {
            "401720003": {
                "model_prob_home": 0.50,
                "edge": None,
                "odds_opening_home": None,
                "odds_opening_away": None,
            }
        }

        assert insert_game_log_entries(db.db_path, "2026-03-11", games, predictions, {}) == 1
        assert insert_game_log_entries(db.db_path, "2026-03-11", games, predictions, {}) == 0

    def test_insert_game_not_in_predictions(self, db):
        from tracking.game_log import insert_game_log_entries

        games = [{"game_id": "401720004", "home": "GONZ", "away": "SMC"}]
        predictions = {}

        inserted = insert_game_log_entries(db.db_path, "2026-03-11", games, predictions, {})
        assert inserted == 1

        rows = db.execute_query("SELECT * FROM game_log WHERE game_id = '401720004'")
        row = rows[0]
        assert row["model_prob_home"] is None
        assert row["bet_placed"] == 0


class TestGameLogSettle:
    """Test settling games in game_log."""

    def _seed_game(self, db, game_id="401720010", home="DUKE", away="UNC"):
        with db.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO game_log (game_date, game_id, home, away, model_prob_home) "
                "VALUES ('2026-03-10', ?, ?, ?, 0.60)",
                (game_id, home, away),
            )

    def test_settle_updates_score_and_result(self, db):
        self._seed_game(db)
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

        settled = settle_game_log_entries(db.db_path, completed_games, closing_odds)
        assert settled == 1

        rows = db.execute_query("SELECT * FROM game_log WHERE game_id = '401720010'")
        row = rows[0]
        assert row["home_score"] == 78
        assert row["away_score"] == 72
        assert row["result"] == "home"
        assert row["odds_closing_home"] == -200
        assert row["odds_closing_away"] == 170
        assert row["settled_at"] is not None

    def test_settle_away_win(self, db):
        self._seed_game(db, game_id="401720011")
        from tracking.game_log import settle_game_log_entries

        completed = [
            {
                "game_id": "401720011",
                "home": "DUKE",
                "away": "UNC",
                "home_score": 65,
                "away_score": 70,
            }
        ]
        settled = settle_game_log_entries(db.db_path, completed, {})
        assert settled == 1

        rows = db.execute_query("SELECT * FROM game_log WHERE game_id = '401720011'")
        row = rows[0]
        assert row["result"] == "away"
        assert row["odds_closing_home"] is None

    def test_settle_already_settled_skipped(self, db):
        self._seed_game(db, game_id="401720012")
        from tracking.game_log import settle_game_log_entries

        completed = [
            {
                "game_id": "401720012",
                "home": "DUKE",
                "away": "UNC",
                "home_score": 80,
                "away_score": 75,
            }
        ]

        assert settle_game_log_entries(db.db_path, completed, {}) == 1
        assert settle_game_log_entries(db.db_path, completed, {}) == 0

    def test_settle_game_not_in_log_skipped(self, db):
        from tracking.game_log import settle_game_log_entries

        completed = [
            {
                "game_id": "999999999",
                "home": "X",
                "away": "Y",
                "home_score": 80,
                "away_score": 75,
            }
        ]
        assert settle_game_log_entries(db.db_path, completed, {}) == 0
