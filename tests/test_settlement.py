"""Tests for bet settlement logic."""

from __future__ import annotations


from scripts.settle_paper_bets import determine_bet_outcome


class TestDetermineBetOutcome:
    """Test the outcome determination logic."""

    def test_moneyline_home_win(self):
        bet = {
            "bet_type": "moneyline",
            "selection": "home",
            "odds_placed": -110,
            "stake": 100.0,
            "line": None,
        }
        game = {"home_score": 80, "away_score": 70}
        result, pnl = determine_bet_outcome(bet, game)
        assert result == "win"
        assert pnl > 0

    def test_moneyline_home_loss(self):
        bet = {
            "bet_type": "moneyline",
            "selection": "home",
            "odds_placed": -110,
            "stake": 100.0,
            "line": None,
        }
        game = {"home_score": 65, "away_score": 70}
        result, pnl = determine_bet_outcome(bet, game)
        assert result == "loss"
        assert pnl == -100.0

    def test_moneyline_away_win(self):
        bet = {
            "bet_type": "moneyline",
            "selection": "away",
            "odds_placed": 150,
            "stake": 100.0,
            "line": None,
        }
        game = {"home_score": 65, "away_score": 70}
        result, pnl = determine_bet_outcome(bet, game)
        assert result == "win"
        assert pnl == 150.0

    def test_spread_home_cover(self):
        bet = {
            "bet_type": "spread",
            "selection": "home",
            "odds_placed": -110,
            "stake": 100.0,
            "line": -5.5,
        }
        game = {"home_score": 80, "away_score": 70}
        result, pnl = determine_bet_outcome(bet, game)
        # margin=10, line=-5.5 -> adjusted=10+(-5.5)=4.5 > 0 -> win
        assert result == "win"
        assert pnl > 0

    def test_spread_home_fail(self):
        bet = {
            "bet_type": "spread",
            "selection": "home",
            "odds_placed": -110,
            "stake": 100.0,
            "line": -5.5,
        }
        game = {"home_score": 73, "away_score": 70}
        result, pnl = determine_bet_outcome(bet, game)
        # margin=3, line=-5.5 -> adjusted=3+(-5.5)=-2.5 < 0 -> loss
        assert result == "loss"

    def test_spread_push(self):
        bet = {
            "bet_type": "spread",
            "selection": "home",
            "odds_placed": -110,
            "stake": 100.0,
            "line": -10.0,
        }
        game = {"home_score": 80, "away_score": 70}
        result, pnl = determine_bet_outcome(bet, game)
        # margin=10, line=-10 -> adjusted=0 -> push
        assert result == "push"
        assert pnl == 0.0

    def test_total_over_win(self):
        bet = {
            "bet_type": "total",
            "selection": "over",
            "odds_placed": -110,
            "stake": 100.0,
            "line": 145.5,
        }
        game = {"home_score": 80, "away_score": 70}
        result, pnl = determine_bet_outcome(bet, game)
        # total=150, line=145.5 -> over wins
        assert result == "win"

    def test_total_under_win(self):
        bet = {
            "bet_type": "total",
            "selection": "under",
            "odds_placed": -110,
            "stake": 100.0,
            "line": 155.5,
        }
        game = {"home_score": 80, "away_score": 70}
        result, pnl = determine_bet_outcome(bet, game)
        # total=150, line=155.5 -> under wins
        assert result == "win"

    def test_total_over_loss(self):
        bet = {
            "bet_type": "total",
            "selection": "over",
            "odds_placed": -110,
            "stake": 100.0,
            "line": 155.5,
        }
        game = {"home_score": 80, "away_score": 70}
        result, pnl = determine_bet_outcome(bet, game)
        # total=150, line=155.5 -> over loses
        assert result == "loss"
