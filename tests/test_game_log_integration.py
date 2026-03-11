"""Integration test for the full game log lifecycle:
insert -> settle -> export -> verify.
"""


import pytest

from tracking.database import BettingDatabase


@pytest.fixture
def db(tmp_path):
    """Create a temporary database."""
    path = str(tmp_path / "test_integration.db")
    return BettingDatabase(path)


SAMPLE_GAMES = [
    {
        "game_id": "401720100",
        "home": "DUKE",
        "away": "UNC",
        "home_name": "Duke",
        "away_name": "North Carolina",
        "home_score": 0,
        "away_score": 0,
        "status": "STATUS_SCHEDULED",
    },
    {
        "game_id": "401720101",
        "home": "UK",
        "away": "FLA",
        "home_name": "Kentucky",
        "away_name": "Florida",
        "home_score": 0,
        "away_score": 0,
        "status": "STATUS_SCHEDULED",
    },
    {
        "game_id": "401720102",
        "home": "GONZ",
        "away": "SMC",
        "home_name": "Gonzaga",
        "away_name": "Saint Mary's",
        "home_score": 0,
        "away_score": 0,
        "status": "STATUS_SCHEDULED",
    },
]

SAMPLE_PREDICTIONS = {
    "401720100": {
        "model_prob_home": 0.65,
        "edge": 0.12,
        "odds_opening_home": -180,
        "odds_opening_away": 150,
    },
    "401720101": {
        "model_prob_home": 0.55,
        "edge": 0.08,
        "odds_opening_home": -130,
        "odds_opening_away": 110,
    },
    # 401720102 deliberately missing — no odds available
}

SAMPLE_BETS = {"401720100": "home"}  # Only bet on Duke


class TestGameLogIntegration:
    """Full lifecycle: insert -> settle -> export."""

    def test_full_lifecycle(self, db, tmp_path):
        from tracking.game_log import insert_game_log_entries, settle_game_log_entries

        db_path = str(db.db_path)

        # Phase 1: Insert
        inserted = insert_game_log_entries(
            db_path,
            "2026-03-11",
            SAMPLE_GAMES,
            SAMPLE_PREDICTIONS,
            SAMPLE_BETS,
        )
        assert inserted == 3

        # Verify state
        rows = db.execute_query("SELECT * FROM game_log ORDER BY game_id")
        assert len(rows) == 3
        assert rows[0]["bet_placed"] == 1  # Duke game
        assert rows[0]["bet_side"] == "home"
        assert rows[1]["bet_placed"] == 0  # Kentucky game
        assert rows[2]["model_prob_home"] is None  # Gonzaga — no prediction

        # Phase 2: Settle
        completed = [
            {
                "game_id": "401720100",
                "home": "DUKE",
                "away": "UNC",
                "home_score": 78,
                "away_score": 72,
            },
            {
                "game_id": "401720101",
                "home": "UK",
                "away": "FLA",
                "home_score": 65,
                "away_score": 70,
            },
            # 401720102 not completed yet
        ]
        closing = {
            "401720100": {"home": -200, "away": 170},
            "401720101": {"home": -120, "away": 100},
        }

        settled = settle_game_log_entries(db_path, completed, closing)
        assert settled == 2

        # Verify settled state
        rows = db.execute_query("SELECT * FROM game_log ORDER BY game_id")
        assert rows[0]["result"] == "home"  # Duke won
        assert rows[0]["home_score"] == 78
        assert rows[0]["odds_closing_home"] == -200
        assert rows[1]["result"] == "away"  # Florida won
        assert rows[2]["result"] is None  # Gonzaga not settled

    def test_idempotent_insert(self, db):
        from tracking.game_log import insert_game_log_entries

        db_path = str(db.db_path)

        # First insert
        assert (
            insert_game_log_entries(
                db_path, "2026-03-11", SAMPLE_GAMES, SAMPLE_PREDICTIONS, SAMPLE_BETS
            )
            == 3
        )
        # Second insert — should skip all duplicates
        assert (
            insert_game_log_entries(
                db_path, "2026-03-11", SAMPLE_GAMES, SAMPLE_PREDICTIONS, SAMPLE_BETS
            )
            == 0
        )

    def test_idempotent_settle(self, db):
        from tracking.game_log import insert_game_log_entries, settle_game_log_entries

        db_path = str(db.db_path)

        insert_game_log_entries(
            db_path, "2026-03-11", SAMPLE_GAMES, SAMPLE_PREDICTIONS, SAMPLE_BETS
        )

        completed = [
            {
                "game_id": "401720100",
                "home": "DUKE",
                "away": "UNC",
                "home_score": 78,
                "away_score": 72,
            },
        ]

        assert settle_game_log_entries(db_path, completed, {}) == 1
        assert settle_game_log_entries(db_path, completed, {}) == 0  # Already settled
