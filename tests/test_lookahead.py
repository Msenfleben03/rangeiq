"""Tests for lookahead predictions and position-building."""

from __future__ import annotations

import pytest

from betting.odds_converter import get_days_out_multiplier
from tracking.database import BettingDatabase
from tracking.logger import calculate_entry_stake, get_position_summary


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


class TestPositionSummary:
    """Test querying existing position for a game."""

    def test_no_existing_position(self, db):
        summary = get_position_summary(db, "401720001", "Duke Blue Devils ML")
        assert summary["total_staked"] == 0.0
        assert summary["entry_count"] == 0
        assert summary["max_entry"] == 0

    def test_single_entry_position(self, db):
        db.insert_bet(
            {
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
        )
        summary = get_position_summary(db, "401720001", "Duke Blue Devils ML")
        assert summary["total_staked"] == 70.0
        assert summary["entry_count"] == 1
        assert summary["max_entry"] == 1

    def test_multi_entry_position(self, db):
        for i, (odds, stake) in enumerate([(150, 70), (140, 50), (130, 80)], 1):
            db.insert_bet(
                {
                    "sport": "ncaab",
                    "game_date": "2026-03-01",
                    "game_id": "401720001",
                    "bet_type": "moneyline",
                    "selection": "Duke Blue Devils ML",
                    "odds_placed": odds,
                    "stake": float(stake),
                    "sportsbook": "paper",
                    "position_entry": i,
                }
            )
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
