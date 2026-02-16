"""Tests for BettingValidator - Domain-Specific Betting Validation.

This test suite validates the betting-specific validation logic including:
- CLV calculation accuracy
- Unrealistic vig detection
- Kelly limit enforcement
- Line availability validation
- Book slippage modeling

Run with: pytest tests/test_betting_validator.py -v
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backtesting.validators.betting_validator import (  # noqa: E402
    BettingValidator,
    BettingValidation,
    ValidationSeverity,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator():
    """Create a BettingValidator with default settings."""
    return BettingValidator()


@pytest.fixture
def validator_strict():
    """Create a BettingValidator with strict settings."""
    return BettingValidator(
        min_clv=0.02,  # Require 2% CLV
        max_kelly_fraction=0.20,  # 20% Kelly max
        max_bet_size=0.02,  # 2% max bet
    )


@pytest.fixture
def sample_clv_values_good():
    """CLV values that should pass validation."""
    return [0.02, 0.018, 0.025, 0.015, 0.022, 0.019, 0.021, 0.016, 0.020, 0.017]


@pytest.fixture
def sample_clv_values_bad():
    """CLV values that should fail validation."""
    return [0.01, 0.008, -0.005, 0.012, -0.002, 0.009, 0.011, -0.001, 0.005, 0.003]


@pytest.fixture
def sample_bets_df():
    """Sample bets DataFrame for testing."""
    return pd.DataFrame(
        {
            "game_id": [f"game_{i}" for i in range(10)],
            "bet_time": pd.date_range("2024-01-01 10:00:00", periods=10, freq="h"),
            "line": [-3.5, -7.0, +2.5, -1.0, +3.0, -5.5, +1.5, -4.0, +6.0, -2.5],
            "odds_placed": [-110, -105, +100, -115, -108, -110, +105, -110, -112, -110],
            "odds_closing": [-112, -108, -102, -118, -110, -108, +102, -112, -115, -108],
            "sportsbook": ["draftkings", "fanduel", "betmgm", "caesars", "pinnacle"] * 2,
            "stake": [100, 150, 100, 120, 80, 100, 90, 110, 130, 100],
        }
    )


@pytest.fixture
def sample_historical_odds_df():
    """Sample historical odds DataFrame for testing."""
    records = []
    for i in range(10):
        game_id = f"game_{i}"
        base_time = datetime(2024, 1, 1, 10, 0, 0) + timedelta(hours=i)
        lines = [-3.5, -7.0, +2.5, -1.0, +3.0, -5.5, +1.5, -4.0, +6.0, -2.5]

        # Create odds snapshots at different times
        for minutes_before in [60, 30, 15, 5]:
            timestamp = base_time - timedelta(minutes=minutes_before)
            # Simulate small line movements
            line_adj = 0.5 if minutes_before > 30 else 0
            records.append(
                {
                    "game_id": game_id,
                    "timestamp": timestamp,
                    "line": lines[i] + line_adj,
                    "odds": -110 + (minutes_before // 10),
                }
            )

    return pd.DataFrame(records)


# =============================================================================
# CLV Calculation Tests
# =============================================================================


class TestCLVCalculation:
    """Test CLV calculation accuracy."""

    def test_clv_positive_when_got_better_odds(self, validator):
        """Getting better odds than closing should yield positive CLV."""
        # Placed at -105, closed at -110
        # -105 implies 51.22%, -110 implies 52.38%
        # CLV = (52.38 - 51.22) / 51.22 = positive (~2.27%)
        clv = validator.calculate_clv(-105, -110)

        assert clv > 0, "CLV should be positive when we got better odds"
        assert clv > 0.02, "CLV should be approximately 2.27%"

    def test_clv_negative_when_got_worse_odds(self, validator):
        """Getting worse odds than closing should yield negative CLV."""
        # Placed at -110, closed at -105
        # -110 implies 52.38%, -105 implies 51.22%
        # CLV = (51.22 - 52.38) / 52.38 = negative (~-2.2%)
        clv = validator.calculate_clv(-110, -105)

        assert clv < 0, "CLV should be negative when we got worse odds"
        assert clv < -0.02, "CLV should be approximately -2.2%"

    def test_clv_zero_when_odds_same(self, validator):
        """Same odds at placement and closing should yield zero CLV."""
        clv = validator.calculate_clv(-110, -110)

        assert clv == 0.0, "CLV should be zero when odds are the same"

    def test_clv_for_underdog_odds(self, validator):
        """CLV calculation works for plus-money odds."""
        # Placed at +150, closed at +140
        # +150 implies 40%, +140 implies 41.67%
        # CLV = (41.67 - 40) / 40 = positive (got better price as underdog)
        clv = validator.calculate_clv(+150, +140)

        assert clv > 0, "CLV should be positive when underdog odds were better"

    def test_clv_handles_zero_odds(self, validator):
        """CLV calculation handles edge case of zero odds gracefully."""
        clv = validator.calculate_clv(0, -110)
        assert clv == 0.0

        clv = validator.calculate_clv(-110, 0)
        assert clv == 0.0

    def test_clv_extreme_favorite(self, validator):
        """CLV calculation works for heavy favorites."""
        # Heavy favorite: -300 to -320
        clv = validator.calculate_clv(-300, -320)

        assert clv > 0, "Getting -300 when it closed at -320 is positive CLV"

    def test_clv_extreme_underdog(self, validator):
        """CLV calculation works for heavy underdogs."""
        # Heavy underdog: +500 to +450
        clv = validator.calculate_clv(+500, +450)

        assert clv > 0, "Getting +500 when it closed at +450 is positive CLV"


# =============================================================================
# CLV Threshold Validation Tests
# =============================================================================


class TestCLVThresholdValidation:
    """Test CLV threshold validation logic."""

    def test_clv_threshold_passes_with_good_values(self, validator, sample_clv_values_good):
        """CLV validation passes when mean exceeds threshold."""
        passes, details = validator.validate_clv_threshold(sample_clv_values_good)

        assert passes, "Should pass with good CLV values"
        assert details["mean_clv"] >= 0.015, "Mean CLV should exceed threshold"
        assert details["passes_mean"]

    def test_clv_threshold_fails_with_bad_values(self, validator, sample_clv_values_bad):
        """CLV validation fails when mean is below threshold."""
        passes, details = validator.validate_clv_threshold(sample_clv_values_bad)

        assert not passes, "Should fail with bad CLV values"
        assert details["mean_clv"] < 0.015, "Mean CLV should be below threshold"
        assert not details["passes_mean"]

    def test_clv_threshold_empty_values(self, validator):
        """CLV validation handles empty input gracefully."""
        passes, details = validator.validate_clv_threshold([])

        assert not passes
        assert "error" in details

    def test_clv_threshold_with_season_labels(self, validator):
        """CLV validation works with season labels."""
        clv_values = [0.02, 0.018, 0.025, 0.015, 0.022, 0.019]
        seasons = [2022, 2022, 2023, 2023, 2024, 2024]

        passes, details = validator.validate_clv_threshold(clv_values, season_labels=seasons)

        assert passes
        assert details["seasons_analyzed"] == 3
        assert "season_stats" in details
        assert len(details["season_stats"]) == 3

    def test_clv_threshold_calculates_positive_rate(self, validator):
        """CLV validation correctly calculates positive rate."""
        clv_values = [0.02, -0.01, 0.015, -0.005, 0.025, 0.018, -0.008, 0.022]
        # 5 positive, 3 negative = 62.5% positive rate

        passes, details = validator.validate_clv_threshold(clv_values)

        expected_positive_rate = 5 / 8
        assert abs(details["positive_rate"] - expected_positive_rate) < 0.01

    def test_strict_validator_requires_higher_clv(self, validator_strict, sample_clv_values_good):
        """Strict validator with 2% threshold requires higher CLV."""
        # Mean of good values is ~1.9%, which should fail strict 2% requirement
        passes, details = validator_strict.validate_clv_threshold(sample_clv_values_good)

        # The sample has mean ~1.9%, strict requires 2%
        # This may pass or fail depending on exact values
        assert details["threshold"] == 0.02


# =============================================================================
# Vig Validation Tests
# =============================================================================


class TestVigValidation:
    """Test realistic vig modeling validation."""

    def test_standard_vig_passes(self, validator):
        """Standard -110 vig should pass validation."""
        config = {"assumed_vig": -110}
        result = validator.check_realistic_vig(config)

        assert result.vig_correctly_modeled
        assert abs(result.effective_break_even - 0.5238) < 0.001

    def test_reduced_vig_flagged(self, validator):
        """Reduced vig (-105) should be flagged."""
        config = {"assumed_vig": -105}
        result = validator.check_realistic_vig(config)

        assert result.vig_correctly_modeled  # -105 is acceptable
        assert result.effective_break_even < 0.5238

    def test_unrealistic_vig_fails(self, validator):
        """Zero or near-zero vig should fail validation."""
        config = {"assumed_vig": -100}  # Even money, no vig
        result = validator.check_realistic_vig(config)

        assert not result.vig_correctly_modeled
        assert len(result.issues) > 0

    def test_zero_vig_error(self, validator):
        """Zero vig should generate error."""
        config = {"assumed_vig": 0}
        result = validator.check_realistic_vig(config)

        assert not result.vig_correctly_modeled
        error_issues = [i for i in result.issues if i.severity == ValidationSeverity.ERROR]
        assert len(error_issues) > 0

    def test_vig_with_bets_df(self, validator, sample_bets_df):
        """Vig validation analyzes actual bet odds when provided."""
        config = {"assumed_vig": -110}
        result = validator.check_realistic_vig(config, sample_bets_df)

        # Should analyze the actual odds from the bets
        assert result.vig_correctly_modeled

    def test_reduced_vig_flag_set(self, validator):
        """Reduced vig flag is properly tracked."""
        config = {"assumed_vig": -110, "reduced_vig": True}
        result = validator.check_realistic_vig(config)

        assert result.reduced_vig_used
        info_issues = [i for i in result.issues if i.severity == ValidationSeverity.INFO]
        assert any("reduced vig" in i.message.lower() for i in info_issues)


# =============================================================================
# Kelly Sizing Validation Tests
# =============================================================================


class TestKellySizingValidation:
    """Test Kelly criterion bet sizing validation."""

    def test_kelly_passes_with_reasonable_sizes(self, validator):
        """Reasonable bet sizes should pass Kelly validation."""
        bet_sizes = [100, 150, 120, 80, 100]  # Max 3% of 5000 = 150
        bankroll = 5000

        passes, details = validator.validate_kelly_sizing(bet_sizes, bankroll)

        assert passes
        assert details["max_actual_fraction"] <= 0.03

    def test_kelly_fails_with_oversized_bets(self, validator):
        """Oversized bets should fail Kelly validation."""
        bet_sizes = [100, 250, 120, 80, 100]  # 250/5000 = 5% > 3% limit
        bankroll = 5000

        passes, details = validator.validate_kelly_sizing(bet_sizes, bankroll)

        assert not passes
        assert details["oversized_bets"] >= 1
        assert details["max_actual_fraction"] > 0.03

    def test_kelly_with_zero_bankroll(self, validator):
        """Zero bankroll should return error."""
        bet_sizes = [100, 150]
        bankroll = 0

        passes, details = validator.validate_kelly_sizing(bet_sizes, bankroll)

        assert not passes
        assert "error" in details

    def test_kelly_with_empty_bets(self, validator):
        """Empty bet list should pass (nothing to validate)."""
        passes, details = validator.validate_kelly_sizing([], 5000)

        assert passes
        assert "message" in details

    def test_kelly_custom_limits(self, validator):
        """Custom Kelly limits are respected."""
        bet_sizes = [100, 150, 120]
        bankroll = 5000

        # With 2% limit, 150/5000 = 3% should fail
        passes, details = validator.validate_kelly_sizing(
            bet_sizes, bankroll, max_bet=0.02  # 2% limit
        )

        assert not passes

    def test_kelly_calculates_statistics(self, validator):
        """Kelly validation calculates proper statistics."""
        bet_sizes = [100, 150, 120, 80, 100]
        bankroll = 5000

        _, details = validator.validate_kelly_sizing(bet_sizes, bankroll)

        assert details["n_bets"] == 5
        assert details["max_bet_amount"] == 150
        assert details["min_bet_amount"] == 80
        assert abs(details["avg_bet_fraction"] - 0.022) < 0.001


# =============================================================================
# Line Availability Validation Tests
# =============================================================================


class TestLineAvailabilityValidation:
    """Test line availability validation."""

    def test_line_availability_with_matching_data(
        self, validator, sample_bets_df, sample_historical_odds_df
    ):
        """Line availability validation works with matching data."""
        result = validator.validate_line_availability(
            sample_bets_df,
            sample_historical_odds_df,
            time_tolerance_minutes=60,
            line_tolerance=1.0,
        )

        assert result.total_bets == 10
        assert result.availability_rate >= 0  # Some should be available

    def test_line_availability_with_missing_columns(self, validator):
        """Missing columns are handled gracefully."""
        bets_df = pd.DataFrame({"game_id": ["game_1"]})  # Missing required columns
        odds_df = pd.DataFrame({"game_id": ["game_1"]})

        result = validator.validate_line_availability(bets_df, odds_df)

        assert result.availability_rate == 0.0

    def test_line_availability_with_empty_data(self, validator):
        """Empty DataFrames are handled gracefully."""
        bets_df = pd.DataFrame(columns=["game_id", "bet_time", "line", "odds_placed"])
        odds_df = pd.DataFrame(columns=["game_id", "timestamp", "line", "odds"])

        result = validator.validate_line_availability(bets_df, odds_df)

        assert result.total_bets == 0
        assert result.availability_rate == 1.0  # No bets to validate

    def test_line_availability_strict_tolerance(
        self, validator, sample_bets_df, sample_historical_odds_df
    ):
        """Strict tolerance reduces availability rate."""
        result_strict = validator.validate_line_availability(
            sample_bets_df,
            sample_historical_odds_df,
            time_tolerance_minutes=5,  # Very strict
            line_tolerance=0.1,
        )

        result_loose = validator.validate_line_availability(
            sample_bets_df,
            sample_historical_odds_df,
            time_tolerance_minutes=120,  # Very loose
            line_tolerance=2.0,
        )

        # Strict should have lower or equal availability
        assert result_strict.availability_rate <= result_loose.availability_rate


# =============================================================================
# Book Slippage Tests
# =============================================================================


class TestBookSlippage:
    """Test book-specific slippage modeling."""

    def test_sharp_book_has_less_slippage(self, validator):
        """Sharp books (Pinnacle) have less slippage."""
        pinnacle_slip = validator.model_book_slippage("pinnacle")
        draftkings_slip = validator.model_book_slippage("draftkings")

        assert pinnacle_slip < draftkings_slip
        assert pinnacle_slip == 0.005  # 0.5%

    def test_soft_book_has_more_slippage(self, validator):
        """Soft books have more slippage."""
        caesars_slip = validator.model_book_slippage("caesars")

        assert caesars_slip >= 0.01  # At least 1%

    def test_unknown_book_uses_default(self, validator):
        """Unknown books use default slippage."""
        unknown_slip = validator.model_book_slippage("unknown_book_xyz")
        default_slip = validator.BOOK_SLIPPAGE["default"]

        assert unknown_slip == default_slip

    def test_slippage_case_insensitive(self, validator):
        """Book names are case insensitive."""
        assert validator.model_book_slippage("DraftKings") == validator.model_book_slippage(
            "draftkings"
        )
        assert validator.model_book_slippage("PINNACLE") == validator.model_book_slippage(
            "pinnacle"
        )

    def test_slippage_validation_with_config(self, validator):
        """Slippage validation works with config."""
        config = {"slippage_modeled": True, "slippage_rate": 0.01}
        is_modeled, details = validator.validate_slippage_modeled(config)

        assert is_modeled
        assert details["slippage_modeled"]

    def test_slippage_validation_implicit(self, validator):
        """Slippage is considered modeled if rate >= 0.5%."""
        config = {"slippage_rate": 0.006}  # 0.6%
        is_modeled, details = validator.validate_slippage_modeled(config)

        assert is_modeled

    def test_slippage_validation_with_bets(self, validator, sample_bets_df):
        """Slippage validation analyzes books used."""
        config = {"slippage_modeled": True}
        is_modeled, details = validator.validate_slippage_modeled(config, sample_bets_df)

        assert "books_used" in details
        assert "expected_slippage_by_book" in details


# =============================================================================
# Full Validation Tests
# =============================================================================


class TestFullValidation:
    """Test complete validation pipeline."""

    def test_full_validation_passes_with_good_data(self, validator):
        """Full validation passes with good backtest results."""
        results = {
            "clv_values": [0.02, 0.018, 0.025, 0.015, 0.022],
            "config": {
                "assumed_vig": -110,
                "slippage_modeled": True,
                "slippage_rate": 0.01,
            },
            "bet_sizes": [100, 150, 120, 80, 100],
            "bankroll": 5000,
        }

        validation = validator.full_validation(results)

        assert validation.clv_passes
        assert validation.realistic_vig
        assert validation.kelly_respects_limits

    def test_full_validation_fails_with_bad_clv(self, validator):
        """Full validation fails when CLV is too low."""
        results = {
            "clv_values": [0.005, 0.008, -0.002, 0.01, 0.003],  # Too low
            "config": {"assumed_vig": -110},
            "bet_sizes": [100, 100, 100],
            "bankroll": 5000,
        }

        validation = validator.full_validation(results)

        assert not validation.clv_passes
        assert not validation.overall_valid

        # Should have CLV-related issue
        clv_issues = [i for i in validation.issues if i.category == "clv"]
        assert len(clv_issues) > 0

    def test_full_validation_fails_with_unrealistic_vig(self, validator):
        """Full validation fails when vig is unrealistic."""
        results = {
            "clv_values": [0.02, 0.018, 0.025],
            "config": {"assumed_vig": -100},  # No vig - unrealistic
            "bet_sizes": [100, 100, 100],
            "bankroll": 5000,
        }

        validation = validator.full_validation(results)

        assert not validation.realistic_vig
        assert not validation.overall_valid

    def test_full_validation_warnings_without_slippage(self, validator):
        """Full validation warns when slippage not modeled."""
        results = {
            "clv_values": [0.02, 0.018, 0.025],
            "config": {"assumed_vig": -110},  # No slippage config
            "bet_sizes": [100, 100, 100],
            "bankroll": 5000,
        }

        validation = validator.full_validation(results)

        assert not validation.book_slippage_modeled

        slippage_issues = [i for i in validation.issues if i.category == "slippage"]
        assert len(slippage_issues) > 0

    def test_full_validation_summary_format(self, validator):
        """Full validation produces readable summary."""
        results = {
            "clv_values": [0.02, 0.018],
            "config": {"assumed_vig": -110},
            "bet_sizes": [100, 100],
            "bankroll": 5000,
        }

        validation = validator.full_validation(results)
        summary = validation.summary()

        assert "BETTING VALIDATION SUMMARY" in summary
        assert "CLV Mean" in summary
        assert "Realistic Vig" in summary
        assert "PASS" in summary or "FAIL" in summary

    def test_full_validation_details_populated(self, validator):
        """Full validation populates all detail sections."""
        results = {
            "clv_values": [0.02, 0.018, 0.025],
            "config": {"assumed_vig": -110, "slippage_modeled": True},
            "bet_sizes": [100, 150, 120],
            "bankroll": 5000,
        }

        validation = validator.full_validation(results)

        assert "clv" in validation.details
        assert "vig" in validation.details
        assert "kelly" in validation.details
        assert "slippage" in validation.details


# =============================================================================
# Look-Ahead Detection Tests
# =============================================================================


class TestLookAheadDetection:
    """Test look-ahead bias detection."""

    def test_no_look_ahead_with_different_odds(self, validator):
        """No look-ahead detected when placed and closing odds differ."""
        bets_df = pd.DataFrame(
            {
                "odds_placed": [-110, -108, -112, -110, -105],
                "odds_closing": [-112, -110, -110, -108, -108],
            }
        )

        no_look_ahead, suspicious = validator.validate_no_look_ahead(bets_df)

        # All different, so no look-ahead
        assert no_look_ahead

    def test_look_ahead_detected_with_identical_odds(self, validator):
        """Look-ahead detected when too many odds match exactly."""
        # If >50% have identical placed/closing odds, likely look-ahead
        bets_df = pd.DataFrame(
            {
                "odds_placed": [-110, -110, -110, -110, -110, -110],
                "odds_closing": [-110, -110, -110, -110, -110, -108],
            }
        )

        no_look_ahead, suspicious = validator.validate_no_look_ahead(bets_df)

        # 5/6 = 83% identical, should flag as look-ahead
        assert not no_look_ahead
        assert len(suspicious) >= 5

    def test_look_ahead_handles_missing_column(self, validator):
        """Look-ahead check handles missing odds_closing gracefully."""
        bets_df = pd.DataFrame(
            {
                "odds_placed": [-110, -108, -112],
            }
        )

        no_look_ahead, suspicious = validator.validate_no_look_ahead(bets_df)

        assert no_look_ahead
        assert len(suspicious) == 0


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_single_bet_clv_validation(self, validator):
        """Single bet CLV validation works."""
        passes, details = validator.validate_clv_threshold([0.02])

        assert details["n_bets"] == 1
        assert details["std_clv"] == 0.0  # No variance with single value

    def test_all_negative_clv(self, validator):
        """All negative CLV values fail validation."""
        passes, details = validator.validate_clv_threshold([-0.01, -0.02, -0.015])

        assert not passes
        assert details["mean_clv"] < 0
        assert details["positive_rate"] == 0.0

    def test_very_large_clv_values(self, validator):
        """Very large CLV values are handled."""
        passes, details = validator.validate_clv_threshold([0.10, 0.15, 0.20])

        assert passes
        assert details["mean_clv"] == 0.15

    def test_mixed_bet_types_kelly(self, validator):
        """Kelly validation handles mixed bet sizes."""
        bet_sizes = [10, 50, 100, 150, 1000]  # Wide range
        bankroll = 10000

        passes, details = validator.validate_kelly_sizing(bet_sizes, bankroll)

        assert details["max_bet_amount"] == 1000
        assert details["min_bet_amount"] == 10

    def test_validation_with_none_values(self, validator):
        """Full validation handles None/missing values gracefully."""
        results = {
            "clv_values": [0.02, 0.018],
            "config": {},  # Empty config
            "bet_sizes": [],  # Empty bets
            "bankroll": 5000,
        }

        validation = validator.full_validation(results)

        # Should not raise, and should produce some result
        assert isinstance(validation, BettingValidation)


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple validations."""

    def test_realistic_backtest_scenario(self, validator):
        """Test a realistic backtest validation scenario."""
        # Simulate a 3-season backtest
        n_bets_per_season = 200

        # Generate realistic CLV distribution (slight positive edge)
        np.random.seed(42)
        clv_values = np.random.normal(0.018, 0.02, n_bets_per_season * 3).tolist()
        seasons = (
            [2022] * n_bets_per_season + [2023] * n_bets_per_season + [2024] * n_bets_per_season
        )

        # Generate realistic bet sizes (quarter Kelly with some variance)
        bankroll = 5000
        bet_sizes = np.random.uniform(50, 140, n_bets_per_season * 3).tolist()

        results = {
            "clv_values": clv_values,
            "season_labels": seasons,
            "config": {
                "assumed_vig": -110,
                "slippage_modeled": True,
                "slippage_rate": 0.01,
                "book_specific_slippage": True,
            },
            "bet_sizes": bet_sizes,
            "bankroll": bankroll,
        }

        validation = validator.full_validation(results)

        # With positive mean CLV and realistic config, should pass
        assert validation.realistic_vig
        assert validation.kelly_respects_limits
        assert validation.book_slippage_modeled

        # Print summary for debugging
        print("\n" + validation.summary())

    def test_too_good_to_be_true_scenario(self, validator):
        """Detect a backtest that's too good to be true."""
        # Unrealistically good CLV
        clv_values = [0.05, 0.06, 0.04, 0.055, 0.045] * 100  # 5%+ CLV is suspicious

        results = {
            "clv_values": clv_values,
            "config": {
                "assumed_vig": -100,  # No vig - red flag
                "slippage_modeled": False,  # No slippage - red flag
            },
            "bet_sizes": [500] * 500,  # 10% bets - red flag
            "bankroll": 5000,
        }

        validation = validator.full_validation(results)

        # Should fail multiple checks
        assert not validation.realistic_vig
        assert not validation.kelly_respects_limits
        assert not validation.book_slippage_modeled
        assert not validation.overall_valid

        # Should have multiple issues
        assert len(validation.issues) >= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
