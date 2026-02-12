"""
Test file to verify environment setup and basic functionality.
Run with: pytest tests/test_setup.py -v
"""

import pytest


class TestEnvironmentSetup:
    """Verify that the development environment is correctly configured."""

    def test_pandas_import(self):
        """Verify pandas is installed and importable."""
        import pandas as pd

        assert pd.__version__ >= "2.0.0"

    def test_numpy_import(self):
        """Verify numpy is installed and importable."""
        import numpy as np

        assert np.__version__ >= "1.24.0"

    def test_sklearn_import(self):
        """Verify scikit-learn is installed and importable."""
        import sklearn

        assert sklearn.__version__ >= "1.3.0"

    def test_statsmodels_import(self):
        """Verify statsmodels is installed and importable."""
        import statsmodels

        assert statsmodels.__version__ >= "0.14.0"

    @pytest.mark.slow
    def test_sportsipy_import(self):
        """Verify sportsipy is installed (used for NCAAB data)."""
        try:
            from sportsipy.ncaab.teams import Teams  # noqa: F401

            assert True
        except ImportError:
            pytest.skip("sportsipy not installed - needed for NCAAB")

    @pytest.mark.slow
    def test_pybaseball_import(self):
        """Verify pybaseball is installed (used for MLB data)."""
        try:
            import pybaseball  # noqa: F401

            assert True
        except ImportError:
            pytest.skip("pybaseball not installed - needed for MLB")

    @pytest.mark.slow
    def test_nfl_data_import(self):
        """Verify nfl_data_py is installed (used for NFL data)."""
        try:
            import nfl_data_py  # noqa: F401

            assert True
        except ImportError:
            pytest.skip("nfl_data_py not installed - needed for NFL")


class TestOddsConversions:
    """Test basic odds conversion functions."""

    def test_american_to_decimal_favorite(self):
        """Test American to decimal conversion for favorites."""
        # -110 should equal 1.909...
        american = -110
        expected_decimal = 1.909

        if american > 0:
            decimal = (american / 100) + 1
        else:
            decimal = (100 / abs(american)) + 1

        assert abs(decimal - expected_decimal) < 0.01

    def test_american_to_decimal_underdog(self):
        """Test American to decimal conversion for underdogs."""
        # +150 should equal 2.5
        american = 150
        expected_decimal = 2.5

        if american > 0:
            decimal = (american / 100) + 1
        else:
            decimal = (100 / abs(american)) + 1

        assert decimal == expected_decimal

    def test_american_to_implied_prob_favorite(self):
        """Test American to implied probability for favorites."""
        # -110 should be ~52.38%
        american = -110
        expected_prob = 0.5238

        if american > 0:
            prob = 100 / (american + 100)
        else:
            prob = abs(american) / (abs(american) + 100)

        assert abs(prob - expected_prob) < 0.01

    def test_american_to_implied_prob_underdog(self):
        """Test American to implied probability for underdogs."""
        # +200 should be ~33.33%
        american = 200
        expected_prob = 0.3333

        if american > 0:
            prob = 100 / (american + 100)
        else:
            prob = abs(american) / (abs(american) + 100)

        assert abs(prob - expected_prob) < 0.01


class TestKellyCriterion:
    """Test Kelly criterion calculations."""

    def test_kelly_positive_edge(self):
        """Test Kelly sizing with positive edge."""
        prob = 0.55  # Our estimated probability
        decimal_odds = 2.0  # Even money (+100)

        # Kelly formula: (bp - q) / b
        # where b = decimal odds - 1, p = win prob, q = 1 - p
        b = decimal_odds - 1
        p = prob
        q = 1 - p

        kelly = (b * p - q) / b

        assert kelly > 0  # Should be positive with edge
        assert kelly < 1  # Should be less than 100%
        assert abs(kelly - 0.10) < 0.01  # ~10% Kelly

    def test_kelly_no_edge(self):
        """Test Kelly sizing with no edge (fair odds)."""
        prob = 0.50  # Fair coin
        decimal_odds = 2.0  # Fair odds

        b = decimal_odds - 1
        p = prob
        q = 1 - p

        kelly = (b * p - q) / b

        assert abs(kelly) < 0.001  # Should be ~0

    def test_kelly_negative_edge(self):
        """Test Kelly sizing with negative edge (should not bet)."""
        prob = 0.45  # Less than implied
        decimal_odds = 2.0  # Implies 50%

        b = decimal_odds - 1
        p = prob
        q = 1 - p

        kelly = (b * p - q) / b

        assert kelly < 0  # Negative = don't bet


class TestEloCalculations:
    """Test Elo rating system calculations."""

    def test_elo_expected_equal_ratings(self):
        """Test expected score with equal ratings."""
        rating_a = 1500
        rating_b = 1500

        expected = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

        assert abs(expected - 0.5) < 0.001  # Should be 50%

    def test_elo_expected_higher_rating(self):
        """Test expected score with higher rating."""
        rating_a = 1600  # Better team
        rating_b = 1400  # Worse team

        expected = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

        assert expected > 0.5  # Should favor team A
        assert abs(expected - 0.76) < 0.01  # ~76%

    def test_elo_update_win(self):
        """Test Elo rating update after a win."""
        rating = 1500
        expected = 0.5
        actual = 1.0  # Win
        k = 20

        new_rating = rating + k * (actual - expected)

        assert new_rating > rating  # Should increase after win
        assert new_rating == 1510  # 1500 + 20 * (1 - 0.5)

    def test_elo_update_loss(self):
        """Test Elo rating update after a loss."""
        rating = 1500
        expected = 0.5
        actual = 0.0  # Loss
        k = 20

        new_rating = rating + k * (actual - expected)

        assert new_rating < rating  # Should decrease after loss
        assert new_rating == 1490  # 1500 + 20 * (0 - 0.5)

    def test_elo_to_spread(self):
        """Test converting Elo difference to point spread."""
        elo_diff = 100  # Team A is 100 Elo better
        points_per_elo = 25  # Standard conversion

        spread = elo_diff / points_per_elo

        assert spread == 4.0  # Should be 4-point favorite


class TestDatabaseSchema:
    """Test database can be created from schema."""

    def test_database_creation(self, test_db):
        """Test that database can be initialized from schema."""
        import sqlite3

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        # Check that key tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}

        expected_tables = {"bets", "games", "teams", "predictions", "team_ratings"}

        for table in expected_tables:
            assert table in tables, f"Table {table} not found in database"

        conn.close()

    def test_database_views(self, test_db):
        """Test that database views are created."""
        import sqlite3

        conn = sqlite3.connect(test_db)
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = {row[0] for row in cursor.fetchall()}

        expected_views = {"v_active_bets", "v_model_performance", "v_daily_pnl"}

        for view in expected_views:
            assert view in views, f"View {view} not found in database"

        conn.close()


class TestFixtures:
    """Test that pytest fixtures work correctly."""

    def test_sample_game_fixture(self, sample_game):
        """Test sample game fixture."""
        assert sample_game["sport"] == "NCAAB"
        assert sample_game["home_score"] > 0
        assert sample_game["is_final"] is True

    def test_sample_bet_fixture(self, sample_bet):
        """Test sample bet fixture."""
        assert sample_bet["bet_type"] == "spread"
        assert sample_bet["stake"] > 0
        assert sample_bet["result"] in ["win", "loss", "push"]

    def test_elo_config_fixture(self, elo_config):
        """Test Elo configuration fixture."""
        assert elo_config["k_factor"] > 0
        assert elo_config["initial_rating"] == 1500
        assert 0 < elo_config["regression_factor"] < 1
