"""Tests for lookahead predictions and position-building."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from betting.odds_converter import get_days_out_multiplier
from scripts.daily_run import run_lookahead_predictions
from tracking.database import BettingDatabase
from tracking.logger import (
    auto_record_bets_from_predictions,
    calculate_entry_stake,
    get_position_summary,
)


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


class TestAutoRecordPositionBuilding:
    """Test that auto_record handles multi-entry positions correctly."""

    def _make_predictions_df(self, games):
        """Build a predictions DataFrame from game dicts."""

        return pd.DataFrame(games)

    def test_first_entry_recorded_with_position_entry_1(self, db):
        """First bet on a game should get position_entry=1."""
        preds = self._make_predictions_df(
            [
                {
                    "game_id": "401720001",
                    "home": "DUKE",
                    "away": "UNC",
                    "home_name": "Duke Blue Devils",
                    "away_name": "North Carolina Tar Heels",
                    "home_prob": 0.65,
                    "away_prob": 0.35,
                    "predicted_spread": -5.0,
                    "bart_adj": 0.01,
                    "rec_side": "HOME",
                    "rec_odds": 150,
                    "rec_kelly": 0.04,
                    "rec_stake": 200.0,
                    "home_edge": 0.10,
                    "away_edge": -0.05,
                }
            ]
        )
        recorded = auto_record_bets_from_predictions(
            db,
            preds,
            "2026-03-05",
            days_out=5,
        )
        assert len(recorded) == 1
        # Check DB has position_entry=1
        bets = db.execute_query("SELECT position_entry, stake FROM bets WHERE game_id='401720001'")
        assert len(bets) == 1
        assert bets[0]["position_entry"] == 1
        # Stake should be speculative (200 * 0.35 = 70)
        assert bets[0]["stake"] == pytest.approx(70.0)

    def test_second_entry_gets_position_entry_2(self, db):
        """Adding to a position should increment position_entry."""
        # Pre-existing entry 1
        db.insert_bet(
            {
                "sport": "ncaab",
                "game_date": "2026-03-05",
                "game_id": "401720001",
                "bet_type": "moneyline",
                "selection": "Duke Blue Devils ML",
                "odds_placed": 150,
                "stake": 70.0,
                "sportsbook": "paper",
                "position_entry": 1,
            }
        )
        # Entry 2 via auto_record at day-3
        preds = self._make_predictions_df(
            [
                {
                    "game_id": "401720001",
                    "home": "DUKE",
                    "away": "UNC",
                    "home_name": "Duke Blue Devils",
                    "away_name": "North Carolina Tar Heels",
                    "home_prob": 0.65,
                    "away_prob": 0.35,
                    "predicted_spread": -5.0,
                    "bart_adj": 0.01,
                    "rec_side": "HOME",
                    "rec_odds": 140,
                    "rec_kelly": 0.04,
                    "rec_stake": 200.0,
                    "home_edge": 0.12,
                    "away_edge": -0.05,
                }
            ]
        )
        recorded = auto_record_bets_from_predictions(
            db,
            preds,
            "2026-03-05",
            days_out=3,
        )
        assert len(recorded) == 1
        bets = db.execute_query(
            "SELECT position_entry, stake FROM bets WHERE game_id='401720001' "
            "ORDER BY position_entry"
        )
        assert len(bets) == 2
        assert bets[1]["position_entry"] == 2
        # Day-3 multiplier=0.50, allowed=100, existing=70, add=30
        assert bets[1]["stake"] == pytest.approx(30.0)

    def test_position_full_skips_recording(self, db):
        """Should skip if existing position already meets Kelly cap."""
        db.insert_bet(
            {
                "sport": "ncaab",
                "game_date": "2026-03-05",
                "game_id": "401720001",
                "bet_type": "moneyline",
                "selection": "Duke Blue Devils ML",
                "odds_placed": 150,
                "stake": 250.0,
                "sportsbook": "paper",
                "position_entry": 1,
            }
        )
        preds = self._make_predictions_df(
            [
                {
                    "game_id": "401720001",
                    "home": "DUKE",
                    "away": "UNC",
                    "home_name": "Duke Blue Devils",
                    "away_name": "North Carolina Tar Heels",
                    "home_prob": 0.65,
                    "away_prob": 0.35,
                    "predicted_spread": -5.0,
                    "bart_adj": 0.01,
                    "rec_side": "HOME",
                    "rec_odds": 140,
                    "rec_kelly": 0.04,
                    "rec_stake": 200.0,
                    "home_edge": 0.10,
                    "away_edge": -0.05,
                }
            ]
        )
        recorded = auto_record_bets_from_predictions(
            db,
            preds,
            "2026-03-05",
            days_out=0,
        )
        assert len(recorded) == 0


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
        """Should not call run_predictions for days with no pre-game events."""
        mock_fetch.side_effect = [
            [{"game_id": "1", "status": "STATUS_SCHEDULED"}],  # today
            [],  # tomorrow - no games
            [{"game_id": "2", "status": "STATUS_SCHEDULED"}],  # day+2
        ]
        mock_run.return_value = pd.DataFrame()

        today = datetime(2026, 3, 1)
        run_lookahead_predictions(today, db, dry_run=True, lookahead_days=2)

        assert mock_run.call_count == 2  # today and day+2, not tomorrow

    @patch("scripts.daily_run.run_predictions")
    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_passes_correct_days_out(self, mock_fetch, mock_run, db):
        """Should pass days_out=0 for today, increasing for future days."""
        mock_fetch.return_value = [
            {"game_id": "1", "status": "STATUS_SCHEDULED"},
        ]
        mock_run.return_value = pd.DataFrame()

        today = datetime(2026, 3, 1)
        run_lookahead_predictions(today, db, dry_run=True, lookahead_days=3)

        # Check days_out kwarg for each call
        assert mock_run.call_count == 4
        for i, call in enumerate(mock_run.call_args_list):
            assert call.kwargs.get("days_out") == i


class TestFetchOpeningOddsLookahead:
    """Test multi-day opening odds fetch."""

    @patch("scripts.fetch_opening_odds.fetch_espn_scoreboard")
    @patch("scripts.fetch_opening_odds.ESPNCoreOddsFetcher")
    def test_scans_full_window(self, mock_fetcher_cls, mock_scoreboard, db):
        """Should scan all days in lookahead window."""
        from scripts.fetch_opening_odds import fetch_opening_odds_lookahead

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
        from scripts.fetch_opening_odds import fetch_opening_odds_lookahead

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
