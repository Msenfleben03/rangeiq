"""Tests for lookahead predictions and position-building."""

from __future__ import annotations


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
