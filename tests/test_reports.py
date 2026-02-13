"""Tests for performance reporting."""

from __future__ import annotations

import pytest

from tracking.database import BettingDatabase
from tracking.reports import (
    clv_analysis,
    daily_report,
    model_health_check,
    odds_system_health,
    weekly_report,
)


@pytest.fixture
def db(tmp_path):
    """Create a temporary BettingDatabase with sample data."""
    db = BettingDatabase(str(tmp_path / "test.db"))

    # Insert sample bets
    sample_bets = [
        {
            "sport": "ncaab",
            "game_date": "2026-02-12",
            "game_id": "GAME001",
            "bet_type": "moneyline",
            "selection": "home",
            "odds_placed": -110,
            "stake": 100.0,
            "sportsbook": "draftkings",
            "result": "win",
            "profit_loss": 90.91,
            "clv": 0.02,
        },
        {
            "sport": "ncaab",
            "game_date": "2026-02-12",
            "game_id": "GAME002",
            "bet_type": "spread",
            "selection": "away",
            "odds_placed": -110,
            "stake": 80.0,
            "sportsbook": "fanduel",
            "result": "loss",
            "profit_loss": -80.0,
            "clv": -0.01,
        },
        {
            "sport": "ncaab",
            "game_date": "2026-02-12",
            "game_id": "GAME003",
            "bet_type": "moneyline",
            "selection": "home",
            "odds_placed": +150,
            "stake": 50.0,
            "sportsbook": "betmgm",
        },
    ]

    for bet in sample_bets:
        db.insert_bet(bet)

    return db


class TestDailyReport:
    def test_returns_correct_date(self, db):
        report = daily_report(db, "2026-02-12")
        assert report["date"] == "2026-02-12"

    def test_counts_bets(self, db):
        report = daily_report(db, "2026-02-12")
        assert report["total_bets"] == 3
        assert report["settled"] == 2
        assert report["pending"] == 1

    def test_win_loss_counts(self, db):
        report = daily_report(db, "2026-02-12")
        assert report["wins"] == 1
        assert report["losses"] == 1

    def test_pnl_calculation(self, db):
        report = daily_report(db, "2026-02-12")
        assert abs(report["total_pnl"] - 10.91) < 0.01

    def test_empty_date(self, db):
        report = daily_report(db, "2026-01-01")
        assert report["total_bets"] == 0


class TestWeeklyReport:
    def test_returns_period(self, db):
        report = weekly_report(db)
        assert "period" in report


class TestCLVAnalysis:
    def test_calculates_avg_clv(self, db):
        report = clv_analysis(db, days=30)
        if report["bets_with_clv"] > 0:
            assert "avg_clv" in report


class TestModelHealthCheck:
    def test_returns_status(self, db):
        report = model_health_check(db)
        assert report["status"] in ("HEALTHY", "WARNING", "CRITICAL")

    def test_no_alerts_for_healthy(self, db):
        report = model_health_check(db)
        # With only 2 settled bets, should be healthy
        assert report["status"] == "HEALTHY"


class TestOddsSystemHealth:
    def test_returns_providers(self, db):
        report = odds_system_health(db)
        assert "providers" in report
        assert "total_snapshots" in report
