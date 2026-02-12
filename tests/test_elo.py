"""
Tests for ELO rating system implementation.

This module tests the base ELO rating system and NCAAB-specific extensions.
Following TDD approach - tests written before implementation.
"""

from datetime import date

import pytest

from models.elo import (
    EloRatingSystem,
    elo_expected,
    elo_update,
    elo_to_spread,
    spread_to_elo,
    regress_to_mean,
    mov_multiplier,
)
from models.sport_specific.ncaab.team_ratings import NCAABEloModel


# =============================================================================
# PURE FUNCTION TESTS
# =============================================================================


class TestEloExpected:
    """Tests for the elo_expected function."""

    def test_equal_ratings_returns_50_percent(self):
        """Equal ratings should give 50% win probability."""
        assert elo_expected(1500, 1500) == pytest.approx(0.5, abs=1e-6)

    def test_higher_rating_favored(self):
        """Higher rated team should have > 50% probability."""
        prob = elo_expected(1600, 1500)
        assert prob > 0.5

    def test_lower_rating_underdog(self):
        """Lower rated team should have < 50% probability."""
        prob = elo_expected(1400, 1500)
        assert prob < 0.5

    def test_100_point_difference(self):
        """100 Elo point difference should give ~64% probability."""
        prob = elo_expected(1600, 1500)
        assert prob == pytest.approx(0.64, abs=0.01)

    def test_400_point_difference(self):
        """400 Elo point difference should give ~91% probability."""
        prob = elo_expected(1900, 1500)
        assert prob == pytest.approx(0.909, abs=0.01)

    def test_symmetry(self):
        """Probabilities should sum to 1 for two teams."""
        prob_a = elo_expected(1600, 1500)
        prob_b = elo_expected(1500, 1600)
        assert prob_a + prob_b == pytest.approx(1.0, abs=1e-6)

    def test_negative_rating_difference(self):
        """Function should work with negative differences."""
        prob = elo_expected(1400, 1600)
        assert 0 < prob < 0.5


class TestEloUpdate:
    """Tests for the elo_update function."""

    def test_win_increases_rating(self):
        """Winning should increase rating."""
        expected = elo_expected(1500, 1500)
        new_rating = elo_update(1500, expected, actual=1.0, k=20)
        assert new_rating > 1500

    def test_loss_decreases_rating(self):
        """Losing should decrease rating."""
        expected = elo_expected(1500, 1500)
        new_rating = elo_update(1500, expected, actual=0.0, k=20)
        assert new_rating < 1500

    def test_upset_win_larger_gain(self):
        """Upset win should give larger rating gain."""
        expected_underdog = elo_expected(1400, 1600)
        expected_favorite = elo_expected(1600, 1400)

        gain_underdog = elo_update(1400, expected_underdog, 1.0, k=20) - 1400
        gain_favorite = elo_update(1600, expected_favorite, 1.0, k=20) - 1600

        assert gain_underdog > gain_favorite

    def test_k_factor_scales_update(self):
        """Larger K factor should produce larger updates."""
        expected = elo_expected(1500, 1500)
        update_k20 = abs(elo_update(1500, expected, 1.0, k=20) - 1500)
        update_k40 = abs(elo_update(1500, expected, 1.0, k=40) - 1500)

        assert update_k40 == pytest.approx(update_k20 * 2, abs=1e-6)

    def test_zero_sum(self):
        """In a match, rating changes should be zero-sum (with same K)."""
        expected_a = elo_expected(1500, 1500)
        expected_b = elo_expected(1500, 1500)

        # Team A wins
        change_a = elo_update(1500, expected_a, 1.0, k=20) - 1500
        change_b = elo_update(1500, expected_b, 0.0, k=20) - 1500

        assert change_a + change_b == pytest.approx(0.0, abs=1e-6)


class TestEloToSpread:
    """Tests for Elo-to-spread conversion."""

    def test_equal_ratings_zero_spread(self):
        """Equal ratings should produce zero spread."""
        assert elo_to_spread(0) == pytest.approx(0.0)

    def test_positive_diff_negative_spread(self):
        """Higher home rating means home is favored (negative spread)."""
        spread = elo_to_spread(100, points_per_elo=25)
        assert spread == pytest.approx(4.0)

    def test_100_elo_equals_4_points(self):
        """100 Elo points should equal ~4 point spread at default."""
        spread = elo_to_spread(100)
        assert spread == pytest.approx(4.0)

    def test_custom_points_per_elo(self):
        """Should work with custom points_per_elo."""
        spread = elo_to_spread(100, points_per_elo=50)
        assert spread == pytest.approx(2.0)


class TestSpreadToElo:
    """Tests for spread-to-Elo conversion."""

    def test_zero_spread_zero_elo(self):
        """Zero spread should give zero Elo difference."""
        assert spread_to_elo(0) == pytest.approx(0.0)

    def test_4_point_spread_100_elo(self):
        """4 point spread should equal ~100 Elo at default."""
        elo_diff = spread_to_elo(4)
        assert elo_diff == pytest.approx(100.0)

    def test_roundtrip(self):
        """Converting back and forth should preserve value."""
        original_diff = 150
        spread = elo_to_spread(original_diff)
        recovered = spread_to_elo(spread)
        assert recovered == pytest.approx(original_diff)


class TestRegressToMean:
    """Tests for season regression."""

    def test_regression_moves_toward_mean(self):
        """High rating should regress toward mean."""
        regressed = regress_to_mean(1700, mean=1500, factor=0.33)
        assert 1500 < regressed < 1700

    def test_regression_factor(self):
        """33% regression should move 1/3 of the way to mean."""
        rating = 1700
        mean = 1500
        diff = rating - mean
        expected = rating - (diff * 0.33)
        actual = regress_to_mean(rating, mean=mean, factor=0.33)
        assert actual == pytest.approx(expected)

    def test_mean_rating_unchanged(self):
        """Rating at mean should not change."""
        regressed = regress_to_mean(1500, mean=1500, factor=0.33)
        assert regressed == pytest.approx(1500)

    def test_below_mean_regression(self):
        """Below-mean ratings should regress upward."""
        regressed = regress_to_mean(1300, mean=1500, factor=0.33)
        assert 1300 < regressed < 1500


class TestMOVMultiplier:
    """Tests for margin of victory multiplier."""

    def test_close_game_low_multiplier(self):
        """Close game should have relatively low multiplier."""
        mult = mov_multiplier(1, elo_diff=0)
        # Log(2) * autocorr_adj = ~0.69 for margin=1
        # Close games have lower multiplier than blowouts
        assert mult > 0
        assert mult < 1.5

    def test_blowout_higher_multiplier(self):
        """Blowout should have higher multiplier."""
        mult_close = mov_multiplier(3, elo_diff=0)
        mult_blowout = mov_multiplier(20, elo_diff=0)
        assert mult_blowout > mult_close

    def test_cap_applied(self):
        """Multiplier should be capped to prevent extreme values."""
        mult_extreme = mov_multiplier(50, elo_diff=0, mov_cap=25)
        mult_capped = mov_multiplier(25, elo_diff=0, mov_cap=25)
        # Both should use capped MOV
        assert mult_extreme == mult_capped

    def test_elo_diff_autocorrelation_adjustment(self):
        """Larger Elo diff should reduce multiplier (expected blowouts)."""
        # When favorite wins by 20, multiplier should be lower than
        # when underdog wins by 20
        mult_favorite = mov_multiplier(20, elo_diff=200)  # Favorite won
        mult_underdog = mov_multiplier(20, elo_diff=-200)  # Underdog won
        assert mult_underdog > mult_favorite


# =============================================================================
# ELO RATING SYSTEM CLASS TESTS
# =============================================================================


class TestEloRatingSystem:
    """Tests for the EloRatingSystem class."""

    @pytest.fixture
    def elo_system(self):
        """Create a default Elo system."""
        return EloRatingSystem(
            k_factor=20,
            initial_rating=1500,
            home_advantage=100,
            mov_cap=25,
            regression_factor=0.33,
        )

    def test_initialization(self, elo_system):
        """System should initialize with correct parameters."""
        assert elo_system.k_factor == 20
        assert elo_system.initial_rating == 1500
        assert elo_system.home_advantage == 100

    def test_get_rating_new_team(self, elo_system):
        """New team should get initial rating."""
        rating = elo_system.get_rating("new_team")
        assert rating == 1500

    def test_set_and_get_rating(self, elo_system):
        """Should be able to set and retrieve rating."""
        elo_system.set_rating("duke", 1650)
        assert elo_system.get_rating("duke") == 1650

    def test_update_after_game(self, elo_system):
        """Update should modify ratings correctly after a game."""
        elo_system.set_rating("duke", 1600)
        elo_system.set_rating("unc", 1550)

        # Duke wins at home by 10
        elo_system.update_game(
            home_team="duke",
            away_team="unc",
            home_score=80,
            away_score=70,
        )

        # Duke should gain, UNC should lose
        assert elo_system.get_rating("duke") > 1600
        assert elo_system.get_rating("unc") < 1550

    def test_home_advantage_applied(self, elo_system):
        """Home advantage should be factored into prediction."""
        elo_system.set_rating("home_team", 1500)
        elo_system.set_rating("away_team", 1500)

        prob = elo_system.predict_win_probability("home_team", "away_team")

        # Home team should be favored even with equal ratings
        assert prob > 0.5

    def test_predict_spread(self, elo_system):
        """Should predict point spread correctly."""
        elo_system.set_rating("duke", 1600)
        elo_system.set_rating("unc", 1500)

        spread = elo_system.predict_spread("duke", "unc")

        # Duke at home (100 advantage) + 100 rating diff = 200 Elo advantage
        # 200 / 25 = 8 points
        assert spread == pytest.approx(-8.0, abs=0.5)

    def test_season_regression(self, elo_system):
        """Should regress all ratings between seasons."""
        elo_system.set_rating("duke", 1700)
        elo_system.set_rating("unc", 1600)
        elo_system.set_rating("nc_state", 1300)

        elo_system.apply_season_regression()

        # All should move toward 1500
        assert 1500 < elo_system.get_rating("duke") < 1700
        assert 1500 < elo_system.get_rating("unc") < 1600
        assert 1300 < elo_system.get_rating("nc_state") < 1500

    def test_rating_bounds(self, elo_system):
        """Ratings should stay within bounds."""
        elo_system.min_rating = 1000
        elo_system.max_rating = 2000

        elo_system.set_rating("weak_team", 900)  # Below min
        elo_system.set_rating("strong_team", 2100)  # Above max

        assert elo_system.get_rating("weak_team") >= 1000
        assert elo_system.get_rating("strong_team") <= 2000

    def test_get_all_ratings(self, elo_system):
        """Should return all team ratings."""
        elo_system.set_rating("duke", 1650)
        elo_system.set_rating("unc", 1620)

        ratings = elo_system.get_all_ratings()

        assert "duke" in ratings
        assert "unc" in ratings
        assert ratings["duke"] == 1650

    def test_process_multiple_games(self, elo_system):
        """Should process a sequence of games correctly."""
        games = [
            {"home": "duke", "away": "unc", "home_score": 80, "away_score": 70},
            {"home": "unc", "away": "duke", "home_score": 75, "away_score": 72},
            {"home": "duke", "away": "unc", "home_score": 85, "away_score": 80},
        ]

        for game in games:
            elo_system.update_game(
                home_team=game["home"],
                away_team=game["away"],
                home_score=game["home_score"],
                away_score=game["away_score"],
            )

        # Duke won 2, lost 1 - should be higher rated
        assert elo_system.get_rating("duke") > elo_system.get_rating("unc")


# =============================================================================
# NCAAB ELO MODEL TESTS
# =============================================================================


class TestNCAABEloModel:
    """Tests for NCAAB-specific Elo model."""

    @pytest.fixture
    def ncaab_model(self):
        """Create NCAAB Elo model."""
        return NCAABEloModel()

    def test_initialization_with_ncaab_defaults(self, ncaab_model):
        """Should use NCAAB-specific default values."""
        assert ncaab_model.k_factor == 20
        assert ncaab_model.home_advantage == 100
        assert ncaab_model.mov_cap == 25
        assert ncaab_model.regression_factor == 0.50

    def test_tournament_k_factor(self, ncaab_model):
        """Tournament games should use different K factor."""
        # Regular season game
        regular_k = ncaab_model.get_k_factor(is_tournament=False)

        # Tournament game
        tournament_k = ncaab_model.get_k_factor(is_tournament=True)

        # Tournament games typically have higher K factor
        assert tournament_k >= regular_k

    def test_conference_strength_adjustment(self, ncaab_model):
        """Should adjust for conference strength."""
        # Power conference team
        power_adj = ncaab_model.get_conference_adjustment("Big Ten")

        # Mid-major conference
        mid_adj = ncaab_model.get_conference_adjustment("A-10")

        # Low-major conference
        low_adj = ncaab_model.get_conference_adjustment("SWAC")

        # Power > Mid > Low
        assert power_adj > mid_adj > low_adj

    def test_neutral_site_no_home_advantage(self, ncaab_model):
        """Neutral site games should have no home advantage."""
        ncaab_model.set_rating("duke", 1600)
        ncaab_model.set_rating("kansas", 1600)

        # Regular game with home advantage
        home_prob = ncaab_model.predict_win_probability("duke", "kansas")

        # Neutral site
        neutral_prob = ncaab_model.predict_win_probability("duke", "kansas", neutral_site=True)

        assert home_prob > neutral_prob
        assert neutral_prob == pytest.approx(0.5, abs=0.01)

    def test_tournament_seeding_correlation(self, ncaab_model):
        """Higher seeds should correlate with higher Elo."""
        # Set up teams with known seeds
        seed_elo_mapping = ncaab_model.seed_to_elo_estimate(1)
        seed_16_elo = ncaab_model.seed_to_elo_estimate(16)

        assert seed_elo_mapping > seed_16_elo

    def test_historical_matchup_data(self, ncaab_model):
        """Should track historical matchup data."""
        ncaab_model.set_rating("duke", 1600)
        ncaab_model.set_rating("unc", 1580)

        # Play a few games
        ncaab_model.update_game("duke", "unc", 80, 75)
        ncaab_model.update_game("unc", "duke", 82, 78)

        history = ncaab_model.get_matchup_history("duke", "unc")

        assert history["total_games"] == 2
        assert history["duke_wins"] == 1
        assert history["unc_wins"] == 1

    def test_early_season_adjustment(self, ncaab_model):
        """Early season games should have reduced impact."""
        # First 5 games of season
        early_k = ncaab_model.get_k_factor(games_played=3)

        # Mid season
        mid_k = ncaab_model.get_k_factor(games_played=15)

        # Early season typically has lower K to account for uncertainty
        assert early_k <= mid_k

    def test_process_season(self, ncaab_model):
        """Should process an entire season of games."""
        games = [
            {
                "date": date(2024, 11, 15),
                "home": "duke",
                "away": "unc",
                "home_score": 80,
                "away_score": 70,
            },
            {
                "date": date(2024, 11, 20),
                "home": "kansas",
                "away": "kentucky",
                "home_score": 75,
                "away_score": 72,
            },
            {
                "date": date(2024, 11, 25),
                "home": "unc",
                "away": "kansas",
                "home_score": 68,
                "away_score": 65,
            },
        ]

        ncaab_model.process_games(games)

        # All teams should have ratings
        assert ncaab_model.get_rating("duke") != 1500
        assert ncaab_model.get_rating("unc") != 1500
        assert ncaab_model.get_rating("kansas") != 1500
        assert ncaab_model.get_rating("kentucky") != 1500

    def test_export_ratings_dataframe(self, ncaab_model):
        """Should export ratings as DataFrame."""
        ncaab_model.set_rating("duke", 1650)
        ncaab_model.set_rating("unc", 1620)
        ncaab_model.set_rating("kansas", 1680)

        df = ncaab_model.to_dataframe()

        assert len(df) == 3
        assert "team_id" in df.columns
        assert "elo_rating" in df.columns
        assert df[df["team_id"] == "kansas"]["elo_rating"].values[0] == 1680


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_elo_expected_extreme_difference(self):
        """Should handle extreme rating differences."""
        prob = elo_expected(2000, 1000)
        assert 0.99 < prob < 1.0

    def test_elo_expected_negative_ratings(self):
        """Should handle unusual (but valid) rating values."""
        # Ratings below normal range
        prob = elo_expected(1100, 1000)
        assert 0 < prob < 1

    def test_mov_multiplier_zero_margin(self):
        """Should handle ties (rare in basketball)."""
        mult = mov_multiplier(0, elo_diff=0)
        assert mult >= 0

    def test_empty_system_regression(self):
        """Regression on empty system should not error."""
        elo_system = EloRatingSystem()
        elo_system.apply_season_regression()  # Should not raise

    def test_same_team_matchup(self):
        """Predicting same team vs itself should handle gracefully."""
        elo_system = EloRatingSystem()
        elo_system.set_rating("duke", 1600)

        # At neutral site, same team vs itself should return 0.5
        prob = elo_system.predict_win_probability("duke", "duke", neutral_site=True)
        assert prob == pytest.approx(0.5)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_full_season_simulation(self):
        """Simulate a mini-season and verify consistency."""
        model = NCAABEloModel()

        # Teams
        teams = ["duke", "unc", "kansas", "kentucky", "villanova"]

        # Simulate 50 games
        import random

        random.seed(42)

        for _ in range(50):
            home = random.choice(teams)
            away = random.choice([t for t in teams if t != home])

            home_score = random.randint(60, 90)
            away_score = random.randint(60, 90)

            model.update_game(home, away, home_score, away_score)

        # Ratings should diverge from initial
        ratings = model.get_all_ratings()
        rating_values = list(ratings.values())

        # Should have variance
        assert max(rating_values) > 1500
        assert min(rating_values) < 1500

        # Should sum close to initial (zero-sum property)
        avg_rating = sum(rating_values) / len(rating_values)
        assert avg_rating == pytest.approx(1500, abs=10)

    def test_clv_tracking_integration(self):
        """Test that Elo predictions can be compared to closing lines."""
        model = NCAABEloModel()
        model.set_rating("duke", 1650)
        model.set_rating("unc", 1550)

        # Model predicts spread
        predicted_spread = model.predict_spread("duke", "unc")

        # Market spread (from hypothetical sportsbook)
        market_spread = -5.5

        # CLV calculation (if we bet at -5.5 and model says -7)
        clv = predicted_spread - market_spread

        # Should be negative (we're getting value betting Duke)
        assert clv < 0  # Means we like Duke more than market
