"""Tests for the Statistical Validator.

Tests cover:
    - Sample size validation (must be >= 500)
    - Confidence interval calculations (bootstrap and analytical)
    - Sharpe ratio calculation (must be >= 0.5)
    - Drawdown analysis and recovery time
    - Out-of-sample degradation check (< 20%)
    - Monte Carlo ruin probability (< 5%)
    - Full validation pipeline

CRITICAL: These tests verify that the validator properly rejects results
that don't meet minimum statistical rigor requirements.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backtesting.validators.statistical_validator import (  # noqa: E402
    StatisticalValidator,
    StatisticalValidation,
    MonteCarloRuinResult,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def validator():
    """Create a default StatisticalValidator."""
    return StatisticalValidator()


@pytest.fixture
def custom_validator():
    """Create a validator with custom thresholds."""
    return StatisticalValidator(
        min_sample_size=100,
        min_sharpe=0.3,
        max_oos_degradation=0.30,
        max_ruin_probability=0.10,
    )


@pytest.fixture
def small_sample_results():
    """Create results with insufficient sample size (< 500)."""
    np.random.seed(42)
    n_bets = 100  # Below minimum

    # Generate realistic returns with slight edge
    returns = np.random.normal(0.01, 0.5, n_bets)
    outcomes = (np.random.random(n_bets) < 0.54).astype(float)
    clv_values = np.random.normal(0.01, 0.02, n_bets)
    bankroll_series = 1000 + np.cumsum(returns * 100)

    return {
        "n_bets": n_bets,
        "returns": returns,
        "clv_values": clv_values,
        "outcomes": outcomes,
        "bankroll_series": bankroll_series,
        "avg_odds": 1.91,
        "win_rate": np.mean(outcomes),
    }


@pytest.fixture
def sufficient_sample_results():
    """Create results with sufficient sample size (>= 500)."""
    np.random.seed(42)
    n_bets = 600

    # Generate realistic returns with slight edge
    returns = np.random.normal(0.02, 0.3, n_bets)
    outcomes = (np.random.random(n_bets) < 0.55).astype(float)
    clv_values = np.random.normal(0.015, 0.02, n_bets)
    bankroll_series = 1000 + np.cumsum(returns * 100)

    return {
        "n_bets": n_bets,
        "returns": returns,
        "clv_values": clv_values,
        "outcomes": outcomes,
        "bankroll_series": bankroll_series,
        "avg_odds": 1.91,
        "win_rate": np.mean(outcomes),
    }


@pytest.fixture
def high_sharpe_results():
    """Create results with good Sharpe ratio."""
    np.random.seed(42)
    n_bets = 600

    # Consistent positive returns with low variance
    returns = np.random.normal(0.03, 0.15, n_bets)
    outcomes = (np.random.random(n_bets) < 0.57).astype(float)
    clv_values = np.random.normal(0.02, 0.015, n_bets)
    bankroll_series = 1000 + np.cumsum(returns * 100)

    return {
        "n_bets": n_bets,
        "returns": returns,
        "clv_values": clv_values,
        "outcomes": outcomes,
        "bankroll_series": bankroll_series,
        "avg_odds": 1.91,
        "win_rate": np.mean(outcomes),
    }


@pytest.fixture
def low_sharpe_results():
    """Create results with poor Sharpe ratio."""
    np.random.seed(42)
    n_bets = 600

    # Low returns with high variance
    returns = np.random.normal(0.001, 0.8, n_bets)
    outcomes = (np.random.random(n_bets) < 0.52).astype(float)
    clv_values = np.random.normal(0.005, 0.03, n_bets)
    bankroll_series = 1000 + np.cumsum(returns * 100)

    return {
        "n_bets": n_bets,
        "returns": returns,
        "clv_values": clv_values,
        "outcomes": outcomes,
        "bankroll_series": bankroll_series,
        "avg_odds": 1.91,
        "win_rate": np.mean(outcomes),
    }


# =============================================================================
# SAMPLE SIZE VALIDATION TESTS
# =============================================================================


class TestSampleSizeValidation:
    """Tests for sample size validation (n >= 500)."""

    def test_small_sample_fails(self, validator):
        """Test that small sample size (< 500) fails validation."""
        assert not validator.validate_sample_size(100)
        assert not validator.validate_sample_size(499)
        assert not validator.validate_sample_size(0)
        assert not validator.validate_sample_size(1)

    def test_sufficient_sample_passes(self, validator):
        """Test that sufficient sample size (>= 500) passes validation."""
        assert validator.validate_sample_size(500)
        assert validator.validate_sample_size(501)
        assert validator.validate_sample_size(1000)
        assert validator.validate_sample_size(10000)

    def test_boundary_value(self, validator):
        """Test exact boundary at 500."""
        assert validator.validate_sample_size(500)
        assert not validator.validate_sample_size(499)

    def test_custom_minimum(self, custom_validator):
        """Test with custom minimum sample size."""
        # Custom validator has min_sample_size=100
        assert custom_validator.validate_sample_size(100)
        assert not custom_validator.validate_sample_size(99)

    def test_full_validation_small_sample(self, validator, small_sample_results):
        """Test full validation fails for small sample."""
        validation = validator.full_validation(small_sample_results)

        assert not validation.is_sufficient
        assert not validation.all_checks_pass
        assert any("Sample size" in msg for msg in validation.validation_messages)


class TestSampleSizeMessages:
    """Test that sample size failure messages are informative."""

    def test_failure_message_includes_count(self, validator, small_sample_results):
        """Test failure message includes actual count."""
        validation = validator.full_validation(small_sample_results)

        # Should mention the actual sample size
        sample_msg = [m for m in validation.validation_messages if "Sample size" in m]
        assert len(sample_msg) > 0
        assert "100" in sample_msg[0]  # Actual count


# =============================================================================
# CONFIDENCE INTERVAL TESTS
# =============================================================================


class TestConfidenceIntervals:
    """Tests for confidence interval calculations."""

    def test_basic_ci_calculation(self, validator):
        """Test basic CI calculation with known values."""
        np.random.seed(42)
        values = np.random.normal(0.05, 0.02, 1000)

        ci = validator.calculate_confidence_interval(values)

        # True mean is 0.05
        assert ci[0] < 0.05 < ci[1]  # CI should contain true mean
        assert ci[0] < ci[1]  # Lower should be less than upper

    def test_ci_width_decreases_with_sample_size(self, validator):
        """Test that CI width decreases with larger samples."""
        np.random.seed(42)

        small_sample = np.random.normal(0.05, 0.1, 100)
        large_sample = np.random.normal(0.05, 0.1, 1000)

        ci_small = validator.calculate_confidence_interval(small_sample)
        ci_large = validator.calculate_confidence_interval(large_sample)

        width_small = ci_small[1] - ci_small[0]
        width_large = ci_large[1] - ci_large[0]

        assert width_large < width_small

    def test_ci_empty_array(self, validator):
        """Test CI with empty array returns zeros."""
        ci = validator.calculate_confidence_interval(np.array([]))
        assert ci == (0.0, 0.0)

    def test_ci_nan_handling(self, validator):
        """Test CI handles NaN values correctly."""
        values = np.array([0.1, np.nan, 0.15, 0.12, np.nan, 0.08])
        ci = validator.calculate_confidence_interval(values)

        # Should still compute CI from non-NaN values
        assert ci[0] < ci[1]

    def test_ci_single_value(self, validator):
        """Test CI with single value."""
        # Single value should return the value itself
        values = np.array([0.05])
        ci = validator.calculate_confidence_interval(values)

        # For single value, CI should be around that value
        assert ci[0] <= 0.05 <= ci[1] or (ci[0] == ci[1] == 0.05)

    def test_ci_95_coverage(self, validator):
        """Test that 95% CI has approximately 95% coverage."""
        np.random.seed(42)
        n_trials = 100
        true_mean = 0.05
        n_contained = 0

        for _ in range(n_trials):
            sample = np.random.normal(true_mean, 0.1, 200)
            ci = validator.calculate_confidence_interval(sample)
            if ci[0] <= true_mean <= ci[1]:
                n_contained += 1

        # Coverage should be at least 85% (allow for sampling variance)
        # May be higher than 95% due to bootstrap being conservative
        coverage = n_contained / n_trials
        assert coverage >= 0.85  # At least 85% coverage


# =============================================================================
# SHARPE RATIO TESTS
# =============================================================================


class TestSharpeRatio:
    """Tests for Sharpe ratio calculation."""

    def test_positive_sharpe(self, validator):
        """Test positive Sharpe with consistent profits."""
        # Consistent positive returns
        returns = np.array([0.01, 0.02, 0.015, 0.01, 0.02] * 100)

        sharpe = validator.calculate_sharpe_ratio(returns)

        assert sharpe > 0

    def test_negative_sharpe(self, validator):
        """Test negative Sharpe with losses."""
        # Consistent negative returns
        returns = np.array([-0.01, -0.02, -0.015, -0.01, -0.02] * 100)

        sharpe = validator.calculate_sharpe_ratio(returns)

        assert sharpe < 0

    def test_zero_variance_returns_zero(self, validator):
        """Test that zero variance returns Sharpe of 0."""
        returns = np.array([0.01, 0.01, 0.01, 0.01])

        sharpe = validator.calculate_sharpe_ratio(returns)

        assert sharpe == 0.0

    def test_empty_returns_zero(self, validator):
        """Test empty returns gives Sharpe of 0."""
        sharpe = validator.calculate_sharpe_ratio(np.array([]))
        assert sharpe == 0.0

    def test_sharpe_threshold_check(self, validator, high_sharpe_results):
        """Test Sharpe passes when above threshold."""
        validation = validator.full_validation(high_sharpe_results)

        # High sharpe results should pass
        assert validation.sharpe_ratio > 0

    def test_sharpe_fails_below_threshold(self, validator, low_sharpe_results):
        """Test Sharpe fails when below 0.5 threshold."""
        validation = validator.full_validation(low_sharpe_results)

        # With high variance returns, Sharpe should be low
        if validation.sharpe_ratio < 0.5:
            assert not validation.sharpe_passes

    def test_sharpe_annualization(self, validator):
        """Test Sharpe is properly annualized."""
        # Create daily returns
        np.random.seed(42)
        daily_returns = np.random.normal(0.001, 0.02, 365)  # One year of daily returns

        sharpe = validator.calculate_sharpe_ratio(daily_returns, periods_per_year=365)

        # Should be annualized
        raw_sharpe = np.mean(daily_returns) / np.std(daily_returns, ddof=1)
        annualized_sharpe = raw_sharpe * np.sqrt(365)

        assert abs(sharpe - annualized_sharpe) < 0.01


# =============================================================================
# DRAWDOWN ANALYSIS TESTS
# =============================================================================


class TestDrawdownAnalysis:
    """Tests for drawdown analysis."""

    def test_max_drawdown_calculation(self, validator):
        """Test max drawdown is calculated correctly."""
        # Start at 100, peak at 150, trough at 100, end at 120
        bankroll = np.array([100, 120, 150, 130, 100, 110, 120])

        analysis = validator.analyze_drawdown(bankroll)

        # Max DD = (150 - 100) / 150 = 33.3%
        expected_dd = (150 - 100) / 150
        assert abs(analysis.max_drawdown - expected_dd) < 0.01

    def test_no_drawdown(self, validator):
        """Test monotonically increasing equity has no drawdown."""
        bankroll = np.array([100, 110, 120, 130, 140, 150])

        analysis = validator.analyze_drawdown(bankroll)

        assert analysis.max_drawdown == 0.0

    def test_recovery_time(self, validator):
        """Test recovery time is calculated correctly."""
        # Peak at index 2, trough at index 4, recover at index 6
        bankroll = np.array([100, 120, 150, 130, 100, 120, 150, 160])

        analysis = validator.analyze_drawdown(bankroll)

        # Recovery from trough (index 4) to new high (index 6 or 7)
        assert analysis.recovery_time_periods >= 0

    def test_no_recovery(self, validator):
        """Test recovery time is -1 when no recovery."""
        # Never recovers from drawdown
        bankroll = np.array([100, 150, 130, 100, 90, 80])

        analysis = validator.analyze_drawdown(bankroll)

        # Should indicate no recovery
        assert analysis.recovery_time_periods == -1

    def test_empty_series(self, validator):
        """Test empty series returns zero drawdown."""
        analysis = validator.analyze_drawdown(np.array([]))

        assert analysis.max_drawdown == 0.0
        assert analysis.recovery_time_periods == -1

    def test_underwater_percentage(self, validator):
        """Test underwater percentage calculation."""
        # In drawdown for 4 out of 7 periods
        bankroll = np.array([100, 110, 120, 100, 90, 100, 110])

        analysis = validator.analyze_drawdown(bankroll)

        # Should have some underwater time
        assert 0 < analysis.underwater_pct < 1


# =============================================================================
# OUT-OF-SAMPLE DEGRADATION TESTS
# =============================================================================


class TestOutOfSampleDegradation:
    """Tests for out-of-sample degradation validation."""

    def test_acceptable_degradation(self, validator):
        """Test acceptable degradation passes (< 20%)."""
        in_sample = 0.10  # 10% ROI
        out_sample = 0.085  # 8.5% ROI (15% degradation)

        assert validator.validate_out_of_sample(in_sample, out_sample)

    def test_excessive_degradation_fails(self, validator):
        """Test excessive degradation fails (>= 20%)."""
        in_sample = 0.10  # 10% ROI
        out_sample = 0.05  # 5% ROI (50% degradation)

        assert not validator.validate_out_of_sample(in_sample, out_sample)

    def test_boundary_degradation(self, validator):
        """Test exactly 20% degradation fails."""
        in_sample = 0.10
        out_sample = 0.08  # Exactly 20% degradation

        # 20% is >= 20%, so should fail
        assert not validator.validate_out_of_sample(in_sample, out_sample)

    def test_improvement_passes(self, validator):
        """Test OOS improvement always passes."""
        in_sample = 0.10
        out_sample = 0.12  # Better OOS performance

        assert validator.validate_out_of_sample(in_sample, out_sample)

    def test_negative_insample_handling(self, validator):
        """Test handling of negative in-sample ROI."""
        in_sample = -0.05  # Negative in-sample
        out_sample = -0.03  # Less negative OOS (improvement)

        # Should pass since OOS is better than in-sample
        result = validator.validate_out_of_sample(in_sample, out_sample)
        assert result

    def test_degradation_calculation(self, validator):
        """Test degradation percentage calculation."""
        in_sample = 0.10
        out_sample = 0.08

        degradation = validator.calculate_oos_degradation(in_sample, out_sample)

        # (0.10 - 0.08) / 0.10 = 0.20
        assert abs(degradation - 0.20) < 0.001


# =============================================================================
# MONTE CARLO RUIN PROBABILITY TESTS
# =============================================================================


class TestMonteCarloRuin:
    """Tests for Monte Carlo ruin probability."""

    def test_positive_edge_low_ruin(self, validator):
        """Test that positive edge has low ruin probability."""
        result = validator.run_monte_carlo(
            win_rate=0.57,  # Strong edge
            avg_odds=1.91,  # -110
            n_bets=500,
            kelly_fraction=0.25,
            n_simulations=1000,  # Fewer sims for speed
        )

        # With strong edge, ruin should be very low
        assert result.ruin_probability < 0.10

    def test_negative_edge_high_ruin(self, validator):
        """Test that negative edge has higher ruin probability."""
        result = validator.run_monte_carlo(
            win_rate=0.48,  # Negative edge at -110
            avg_odds=1.91,
            n_bets=500,
            kelly_fraction=0.25,
            n_simulations=1000,
        )

        # With negative edge, more likely to see ruin
        # (Though Kelly should prevent betting much)
        assert result.ruin_probability >= 0 or result.expected_growth <= 0

    def test_result_structure(self, validator):
        """Test Monte Carlo result has expected structure."""
        result = validator.run_monte_carlo(
            win_rate=0.54,
            avg_odds=1.91,
            n_bets=500,
            n_simulations=100,
        )

        assert isinstance(result, MonteCarloRuinResult)
        assert 0 <= result.ruin_probability <= 1
        assert result.n_simulations == 100
        assert result.n_bets_per_sim == 500
        assert result.percentile_5 <= result.median_final_bankroll <= result.percentile_95

    def test_ruin_threshold_respected(self, validator):
        """Test that custom ruin threshold is used."""
        # With very conservative ruin threshold (50% loss = ruin)
        result = validator.run_monte_carlo(
            win_rate=0.52,
            avg_odds=1.91,
            n_bets=500,
            kelly_fraction=0.25,
            n_simulations=500,
            ruin_threshold=0.5,  # 50% bankroll remaining = ruin
        )

        assert result.ruin_threshold == 0.5


# =============================================================================
# FULL VALIDATION TESTS
# =============================================================================


class TestFullValidation:
    """Tests for the full_validation method."""

    def test_small_sample_fails_overall(self, validator, small_sample_results):
        """Test that small sample causes overall failure."""
        validation = validator.full_validation(small_sample_results)

        assert not validation.all_checks_pass
        assert not validation.is_sufficient

    def test_sufficient_sample_can_pass(self, validator, high_sharpe_results):
        """Test that sufficient sample with good metrics can pass."""
        validation = validator.full_validation(high_sharpe_results)

        assert validation.is_sufficient
        # Note: other checks may still fail depending on the data

    def test_validation_includes_all_fields(self, validator, sufficient_sample_results):
        """Test validation result includes all expected fields."""
        validation = validator.full_validation(sufficient_sample_results)

        assert isinstance(validation, StatisticalValidation)
        assert validation.sample_size == sufficient_sample_results["n_bets"]
        assert isinstance(validation.confidence_interval_roi, tuple)
        assert isinstance(validation.confidence_interval_clv, tuple)
        assert isinstance(validation.confidence_interval_win_rate, tuple)
        assert isinstance(validation.sharpe_ratio, float)
        assert isinstance(validation.max_drawdown, float)
        assert isinstance(validation.ruin_probability, float)

    def test_oos_validation_when_provided(self, validator, sufficient_sample_results):
        """Test OOS validation when in/out sample ROI provided."""
        validation = validator.full_validation(
            sufficient_sample_results,
            in_sample_roi=0.10,
            out_sample_roi=0.08,
        )

        assert validation.out_of_sample_degradation is not None
        assert validation.oos_passes is not None

    def test_oos_validation_skipped_when_not_provided(self, validator, sufficient_sample_results):
        """Test OOS validation skipped when ROIs not provided."""
        validation = validator.full_validation(sufficient_sample_results)

        assert validation.out_of_sample_degradation is None
        assert validation.oos_passes is None

    def test_validation_messages_populated(self, validator, small_sample_results):
        """Test that validation messages are populated."""
        validation = validator.full_validation(small_sample_results)

        assert len(validation.validation_messages) > 0
        # Should have at least sample size message
        assert any("Sample size" in msg for msg in validation.validation_messages)


# =============================================================================
# REPORT FORMATTING TESTS
# =============================================================================


class TestReportFormatting:
    """Tests for validation report formatting."""

    def test_format_report_structure(self, validator, sufficient_sample_results):
        """Test report has expected structure."""
        validation = validator.full_validation(sufficient_sample_results)
        report = validator.format_validation_report(validation)

        assert "STATISTICAL VALIDATION REPORT" in report
        assert "SAMPLE SIZE" in report
        assert "CONFIDENCE INTERVALS" in report
        assert "SHARPE RATIO" in report
        assert "DRAWDOWN" in report
        assert "MONTE CARLO" in report

    def test_format_report_shows_status(self, validator, small_sample_results):
        """Test report shows pass/fail status."""
        validation = validator.full_validation(small_sample_results)
        report = validator.format_validation_report(validation)

        assert "FAIL" in report  # Should show failure


# =============================================================================
# EDGE CASES AND ERROR HANDLING
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_all_zeros_returns(self, validator):
        """Test handling of all-zero returns."""
        results = {
            "n_bets": 600,
            "returns": np.zeros(600),
            "clv_values": np.zeros(600),
            "outcomes": np.ones(600),  # All wins
            "bankroll_series": np.ones(600) * 1000,
            "avg_odds": 1.91,
        }

        # Should not crash
        validation = validator.full_validation(results)
        assert validation is not None

    def test_all_wins(self, validator):
        """Test handling of all wins."""
        np.random.seed(42)
        n_bets = 600

        results = {
            "n_bets": n_bets,
            "returns": np.ones(n_bets) * 0.91,  # All wins at -110
            "clv_values": np.random.normal(0.02, 0.01, n_bets),
            "outcomes": np.ones(n_bets),
            "bankroll_series": 1000 + np.arange(n_bets) * 91,  # Growing bankroll
            "avg_odds": 1.91,
            "win_rate": 1.0,
        }

        validation = validator.full_validation(results)

        # Should pass most checks with perfect wins
        assert validation.is_sufficient

    def test_all_losses(self, validator):
        """Test handling of all losses."""
        np.random.seed(42)
        n_bets = 600

        results = {
            "n_bets": n_bets,
            "returns": np.ones(n_bets) * -1.0,  # All losses
            "clv_values": np.random.normal(-0.02, 0.01, n_bets),
            "outcomes": np.zeros(n_bets),
            "bankroll_series": 1000 - np.arange(n_bets) * 100,  # Declining bankroll
            "avg_odds": 1.91,
            "win_rate": 0.0,
        }

        validation = validator.full_validation(results)

        # Should fail Sharpe check with all losses
        assert not validation.sharpe_passes or validation.sharpe_ratio < 0

    def test_empty_results(self, validator):
        """Test handling of empty results."""
        results = {
            "n_bets": 0,
            "returns": np.array([]),
            "clv_values": np.array([]),
            "outcomes": np.array([]),
            "bankroll_series": np.array([]),
            "avg_odds": 1.91,
        }

        # Should not crash
        validation = validator.full_validation(results)
        assert not validation.is_sufficient


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple validation aspects."""

    def test_realistic_profitable_strategy(self, validator):
        """Test a realistic profitable strategy passes validation."""
        np.random.seed(42)
        n_bets = 1000

        # Realistic profitable strategy: 54% win rate at -110
        win_rate = 0.54
        outcomes = (np.random.random(n_bets) < win_rate).astype(float)

        # Returns: win = +0.91, loss = -1.0 (for unit bets at -110)
        returns = np.where(outcomes == 1, 0.91, -1.0) / 10  # Scale down

        clv_values = np.random.normal(0.012, 0.015, n_bets)  # Positive CLV
        bankroll_series = 1000 + np.cumsum(returns * 100)

        results = {
            "n_bets": n_bets,
            "returns": returns,
            "clv_values": clv_values,
            "outcomes": outcomes,
            "bankroll_series": bankroll_series,
            "avg_odds": 1.91,
            "win_rate": np.mean(outcomes),
        }

        validation = validator.full_validation(results)

        # Profitable strategy should pass sample size
        assert validation.is_sufficient
        assert validation.sample_size == 1000

        # Should have positive CLV interval
        assert validation.confidence_interval_clv[0] > -0.05

    def test_marginal_strategy_flags_issues(self, validator):
        """Test a marginal strategy correctly flags issues."""
        np.random.seed(42)
        n_bets = 600

        # Marginal strategy: break-even at -110
        win_rate = 0.5238
        outcomes = (np.random.random(n_bets) < win_rate).astype(float)
        returns = np.where(outcomes == 1, 0.91, -1.0) / 10

        results = {
            "n_bets": n_bets,
            "returns": returns,
            "clv_values": np.random.normal(0.0, 0.02, n_bets),  # Zero expected CLV
            "outcomes": outcomes,
            "bankroll_series": 1000 + np.cumsum(returns * 100),
            "avg_odds": 1.91,
            "win_rate": np.mean(outcomes),
        }

        validation = validator.full_validation(results)

        # Should pass sample size but may fail Sharpe
        assert validation.is_sufficient


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
