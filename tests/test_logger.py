"""Tests for the paper bet logging utilities."""

from __future__ import annotations

import pytest

from tracking.database import BettingDatabase
from tracking.logger import (
    get_bets_by_date,
    get_pending_bets,
    log_multiple_bets,
    log_paper_bet,
    validate_bet_limits,
)


@pytest.fixture
def db(tmp_path):
    """Create a temporary BettingDatabase."""
    return BettingDatabase(str(tmp_path / "test.db"))


@pytest.fixture
def sample_bet():
    return {
        "sport": "ncaab",
        "game_date": "2026-02-15",
        "game_id": "DUKE_UNC",
        "bet_type": "moneyline",
        "selection": "home",
        "odds_placed": -220,
        "stake": 100.0,
        "sportsbook": "draftkings",
    }


class TestLogPaperBet:
    def test_inserts_bet(self, db, sample_bet):
        bet_id = log_paper_bet(db, sample_bet)
        assert bet_id > 0

    def test_sets_is_live_false(self, db, sample_bet):
        log_paper_bet(db, sample_bet)
        rows = db.execute_query("SELECT is_live FROM bets WHERE game_id = 'DUKE_UNC'")
        assert rows[0]["is_live"] == 0  # FALSE

    def test_missing_required_fields_raises(self, db):
        with pytest.raises(ValueError, match="Missing required"):
            log_paper_bet(db, {"sport": "ncaab"})


class TestLogMultipleBets:
    def test_batch_insert(self, db, sample_bet):
        bet2 = dict(sample_bet)
        bet2["game_id"] = "KANSAS_BAYLOR"
        bet2["selection"] = "away"

        ids = log_multiple_bets(db, [sample_bet, bet2])
        assert len(ids) == 2

    def test_skips_invalid_bets(self, db, sample_bet):
        invalid = {"sport": "ncaab"}  # Missing required
        ids = log_multiple_bets(db, [sample_bet, invalid])
        assert len(ids) == 1


class TestGetPendingBets:
    def test_returns_unsettled(self, db, sample_bet):
        log_paper_bet(db, sample_bet)
        pending = get_pending_bets(db, sport="ncaab")
        assert len(pending) == 1

    def test_excludes_settled(self, db, sample_bet):
        bet_id = log_paper_bet(db, sample_bet)
        db.update_bet_result(bet_id, "win", 90.91)
        pending = get_pending_bets(db, sport="ncaab")
        assert len(pending) == 0


class TestGetBetsByDate:
    def test_filters_by_date(self, db, sample_bet):
        log_paper_bet(db, sample_bet)
        bets = get_bets_by_date(db, "2026-02-15")
        assert len(bets) == 1

    def test_no_results_for_different_date(self, db, sample_bet):
        log_paper_bet(db, sample_bet)
        bets = get_bets_by_date(db, "2026-02-16")
        assert len(bets) == 0


class TestValidateBetLimits:
    def test_within_limits(self, db):
        result = validate_bet_limits(100.0, db)
        assert result["allowed"] is True

    def test_exceeds_max_bet(self, db):
        result = validate_bet_limits(500.0, db)  # 10% of $5000
        assert result["allowed"] is False
        assert "exceeds max bet" in result["reason"]
