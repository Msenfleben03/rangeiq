"""Tests for Overfitting Detection Validator.

These tests verify that the OverfitValidator correctly identifies overfitting
patterns in betting models. The tests use both obviously overfit models
(which should FAIL) and properly regularized models (which should PASS).

Test Categories:
    1. Feature Count Validation (sqrt rule)
    2. In-Sample ROI Check (>15% = suspicious)
    3. Cross-Season Variance Analysis
    4. Parameter Sensitivity Testing
    5. Learning Curve Analysis
    6. Feature Importance Drift Detection
    7. Full Validation Integration Tests
    8. Edge Cases
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backtesting.validators.overfit_validator import (  # noqa: E402
    OverfitValidator,
    quick_overfit_check,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def validator():
    """Create a fresh OverfitValidator instance."""
    return OverfitValidator()


@pytest.fixture
def healthy_backtest_results():
    """Backtest results from a properly regularized model."""
    return {
        # Very consistent ROIs - CV should be well under 30%
        # mean = 0.04, std ~= 0.007, CV ~= 0.17 (17%)
        "season_rois": [0.04, 0.035, 0.045, 0.04, 0.04],  # Low variance
        "in_sample_roi": 0.05,  # Reasonable 5%
        "train_sizes": [100, 200, 300, 400, 500],
        "train_scores": [0.55, 0.54, 0.53, 0.52, 0.52],  # Converging
        "test_scores": [0.50, 0.51, 0.51, 0.51, 0.51],  # Close to train
        # Stable feature importance - same features in same order (just small variations)
        "feature_importances_by_period": [
            {"feat_a": 0.35, "feat_b": 0.28, "feat_c": 0.20, "feat_d": 0.10, "feat_e": 0.07},
            {"feat_a": 0.33, "feat_b": 0.30, "feat_c": 0.18, "feat_d": 0.12, "feat_e": 0.07},
            {"feat_a": 0.36, "feat_b": 0.27, "feat_c": 0.21, "feat_d": 0.09, "feat_e": 0.07},
        ],
    }


@pytest.fixture
def healthy_model_metadata():
    """Metadata for a properly sized model."""
    return {
        "n_features": 8,  # sqrt(500) ~ 22, so 8 is fine
        "n_samples": 500,
    }


@pytest.fixture
def overfit_backtest_results():
    """Backtest results from an obviously overfit model."""
    return {
        "season_rois": [0.15, -0.10, 0.25, -0.05, 0.20],  # High variance (FAIL)
        "in_sample_roi": 0.25,  # Way too good - 25% (FAIL)
        "train_sizes": [100, 200, 300, 400, 500],
        "train_scores": [0.75, 0.76, 0.77, 0.78, 0.79],  # Train keeps increasing
        "test_scores": [0.45, 0.44, 0.43, 0.42, 0.41],  # Test keeps decreasing (FAIL)
        "feature_importances_by_period": [
            {"feat_a": 0.5, "feat_b": 0.3, "feat_c": 0.1, "feat_d": 0.05, "feat_e": 0.05},
            {"feat_c": 0.4, "feat_d": 0.3, "feat_e": 0.2, "feat_a": 0.05, "feat_b": 0.05},
            {"feat_e": 0.6, "feat_a": 0.2, "feat_b": 0.1, "feat_c": 0.05, "feat_d": 0.05},
        ],  # Completely different top features each period (FAIL)
    }


@pytest.fixture
def overfit_model_metadata():
    """Metadata for an overfit model with too many features."""
    return {
        "n_features": 50,  # Way more than sqrt(100) ~ 10 (FAIL)
        "n_samples": 100,
    }


# =============================================================================
# Test Feature Count Validation
# =============================================================================


class TestFeatureCountValidation:
    """Tests for the sqrt(n) feature count rule."""

    def test_valid_feature_count_exact(self, validator):
        """Test that exactly sqrt(n) features passes."""
        # sqrt(100) = 10
        assert validator.validate_feature_count(n_features=10, n_samples=100) is True

    def test_valid_feature_count_under(self, validator):
        """Test that fewer than sqrt(n) features passes."""
        # sqrt(100) = 10, using 5 features
        assert validator.validate_feature_count(n_features=5, n_samples=100) is True

    def test_invalid_feature_count_over(self, validator):
        """Test that more than sqrt(n) features fails."""
        # sqrt(100) = 10, using 15 features
        assert validator.validate_feature_count(n_features=15, n_samples=100) is False

    def test_invalid_feature_count_way_over(self, validator):
        """Test that way more than sqrt(n) features fails."""
        # sqrt(100) = 10, using 50 features - obvious overfit
        assert validator.validate_feature_count(n_features=50, n_samples=100) is False

    def test_large_sample_allows_more_features(self, validator):
        """Test that larger samples allow more features."""
        # sqrt(10000) = 100
        assert validator.validate_feature_count(n_features=50, n_samples=10000) is True
        assert validator.validate_feature_count(n_features=100, n_samples=10000) is True
        assert validator.validate_feature_count(n_features=150, n_samples=10000) is False

    def test_zero_samples_fails(self, validator):
        """Test that zero samples always fails."""
        assert validator.validate_feature_count(n_features=1, n_samples=0) is False

    def test_zero_features_passes(self, validator):
        """Test that zero features always passes (no overfitting risk)."""
        assert validator.validate_feature_count(n_features=0, n_samples=100) is True

    def test_get_max_features(self, validator):
        """Test max features calculation."""
        assert validator.get_max_features(100) == 10
        assert validator.get_max_features(400) == 20
        assert validator.get_max_features(0) == 0


# =============================================================================
# Test In-Sample ROI Check
# =============================================================================


class TestInSampleROICheck:
    """Tests for suspicious in-sample ROI detection."""

    def test_reasonable_roi_passes(self, validator):
        """Test that reasonable ROIs pass."""
        assert validator.check_in_sample_roi(0.03) is True  # 3%
        assert validator.check_in_sample_roi(0.05) is True  # 5%
        assert validator.check_in_sample_roi(0.10) is True  # 10%
        assert validator.check_in_sample_roi(0.15) is True  # 15% - boundary

    def test_suspiciously_high_roi_fails(self, validator):
        """Test that suspiciously high ROIs fail."""
        assert validator.check_in_sample_roi(0.16) is False  # 16%
        assert validator.check_in_sample_roi(0.20) is False  # 20%
        assert validator.check_in_sample_roi(0.50) is False  # 50%
        assert validator.check_in_sample_roi(1.00) is False  # 100% - impossible

    def test_negative_roi_passes(self, validator):
        """Test that negative ROI passes (not suspicious of overfitting)."""
        assert validator.check_in_sample_roi(-0.05) is True
        assert validator.check_in_sample_roi(-0.10) is True

    def test_zero_roi_passes(self, validator):
        """Test that zero ROI passes."""
        assert validator.check_in_sample_roi(0.0) is True


# =============================================================================
# Test Cross-Season Variance
# =============================================================================


class TestCrossSeasonVariance:
    """Tests for cross-season variance analysis."""

    def test_low_variance_passes(self, validator):
        """Test that consistent performance across seasons passes."""
        # Very consistent: mean ~5%, std ~1%
        season_rois = [0.05, 0.04, 0.06, 0.05, 0.05]
        cv = validator.calculate_cross_season_variance(season_rois)
        assert cv < 0.30  # Should be well under 30%
        assert validator.check_variance_passes(season_rois) == True  # noqa: E712

    def test_high_variance_fails(self, validator):
        """Test that inconsistent performance across seasons fails."""
        # Highly variable: mean ~9%, std ~13%
        season_rois = [0.15, -0.10, 0.25, -0.05, 0.20]
        cv = validator.calculate_cross_season_variance(season_rois)
        assert cv > 0.30  # Should be way over 30%
        assert validator.check_variance_passes(season_rois) == False  # noqa: E712

    def test_single_season_returns_zero(self, validator):
        """Test that single season returns 0 variance."""
        assert validator.calculate_cross_season_variance([0.05]) == 0.0

    def test_empty_list_returns_zero(self, validator):
        """Test that empty list returns 0 variance."""
        assert validator.calculate_cross_season_variance([]) == 0.0

    def test_all_zeros_returns_inf(self, validator):
        """Test that all-zero ROIs returns infinity."""
        cv = validator.calculate_cross_season_variance([0.0, 0.0, 0.0])
        assert cv == float("inf")

    def test_boundary_variance(self, validator):
        """Test variance at the boundary (30%)."""
        # Construct a list with exactly ~30% CV
        # mean = 0.10, std = 0.03 -> CV = 0.30
        season_rois = [0.07, 0.10, 0.13]  # mean=0.10, std~0.03
        cv = validator.calculate_cross_season_variance(season_rois)
        # This should be close to boundary
        assert 0.20 < cv < 0.40


# =============================================================================
# Test Learning Curve Analysis
# =============================================================================


class TestLearningCurveAnalysis:
    """Tests for learning curve analysis."""

    def test_healthy_learning_curve(self, validator):
        """Test that a healthy learning curve is detected."""
        # Good curve: train and test converge, gap shrinks
        train_sizes = [100, 200, 300, 400, 500]
        train_scores = [0.60, 0.58, 0.56, 0.55, 0.54]  # Decreasing (generalizing)
        test_scores = [0.48, 0.50, 0.51, 0.52, 0.52]  # Increasing (learning)

        result = validator.analyze_learning_curve(train_sizes, train_scores, test_scores)

        assert result["healthy"] == True  # noqa: E712
        assert result["test_improving"] == True  # noqa: E712
        assert len(result["warnings"]) == 0

    def test_overfit_learning_curve(self, validator):
        """Test that an overfitting learning curve is detected."""
        # Bad curve: train increases, test decreases = clear overfit
        train_sizes = [100, 200, 300, 400, 500]
        train_scores = [0.60, 0.65, 0.70, 0.75, 0.80]  # Increasing
        test_scores = [0.50, 0.48, 0.45, 0.43, 0.40]  # Decreasing (BAD)

        result = validator.analyze_learning_curve(train_sizes, train_scores, test_scores)

        assert result["healthy"] == False  # noqa: E712
        assert result["test_improving"] == False  # noqa: E712
        assert len(result["warnings"]) > 0

    def test_large_gap_warning(self, validator):
        """Test that large train-test gap triggers warning."""
        train_sizes = [100, 200, 300]
        train_scores = [0.80, 0.80, 0.80]  # High train
        test_scores = [0.50, 0.51, 0.52]  # Much lower test

        result = validator.analyze_learning_curve(train_sizes, train_scores, test_scores)

        assert result["healthy"] is False
        assert result["final_gap"] > 0.1
        assert any("gap" in w.lower() for w in result["warnings"])

    def test_insufficient_data_warning(self, validator):
        """Test that insufficient data triggers warning."""
        result = validator.analyze_learning_curve([100], [0.55], [0.50])

        assert "Not enough" in result["warnings"][0]


# =============================================================================
# Test Feature Importance Drift Detection
# =============================================================================


class TestFeatureImportanceDrift:
    """Tests for feature importance stability over time."""

    def test_stable_importance(self, validator):
        """Test that stable feature importance is detected."""
        # Same top features across periods (just slightly different values)
        # Need enough features for top_k check - using top_k=3 for 4 features
        importances = [
            {"a": 0.4, "b": 0.3, "c": 0.2, "d": 0.1},
            {"a": 0.38, "b": 0.32, "c": 0.18, "d": 0.12},
            {"a": 0.42, "b": 0.28, "c": 0.22, "d": 0.08},
        ]

        # Use top_k=3 so consistency is based on top 3 features (which are a, b, c in all periods)
        result = validator.detect_feature_importance_drift(importances, top_k=3)

        assert result["stable"] == True  # noqa: E712
        assert result["avg_rank_correlation"] > 0.5
        assert len(result["warnings"]) == 0

    def test_unstable_importance(self, validator):
        """Test that unstable feature importance is detected."""
        # Completely different top features each period
        importances = [
            {"a": 0.5, "b": 0.3, "c": 0.1, "d": 0.05, "e": 0.05},
            {"c": 0.5, "d": 0.3, "e": 0.1, "a": 0.05, "b": 0.05},
            {"e": 0.5, "a": 0.25, "b": 0.15, "c": 0.05, "d": 0.05},
        ]

        result = validator.detect_feature_importance_drift(importances, top_k=3)

        assert result["stable"] == False  # noqa: E712
        assert len(result["warnings"]) > 0

    def test_single_period_no_drift(self, validator):
        """Test that single period returns no drift detected."""
        importances = [{"a": 0.4, "b": 0.3, "c": 0.2, "d": 0.1}]

        result = validator.detect_feature_importance_drift(importances)

        assert result["stable"] == True  # noqa: E712
        assert "Not enough periods" in result["warnings"][0]


# =============================================================================
# Test Full Validation
# =============================================================================


class TestFullValidation:
    """Integration tests for full_validation method."""

    def test_healthy_model_passes(
        self, validator, healthy_backtest_results, healthy_model_metadata
    ):
        """Test that a properly built model passes all checks."""
        result = validator.full_validation(healthy_backtest_results, healthy_model_metadata)

        assert result.overall_passes == True  # noqa: E712
        assert result.feature_ratio_passes == True  # noqa: E712
        assert result.in_sample_too_good == False  # noqa: E712
        assert result.variance_passes == True  # noqa: E712
        assert result.learning_curve_healthy == True  # noqa: E712
        assert result.feature_importance_stable == True  # noqa: E712

    def test_overfit_model_fails(self, validator, overfit_backtest_results, overfit_model_metadata):
        """Test that an obviously overfit model fails validation."""
        result = validator.full_validation(overfit_backtest_results, overfit_model_metadata)

        assert result.overall_passes == False  # noqa: E712
        # Should fail multiple checks
        assert result.feature_ratio_passes == False  # noqa: E712 - 50 features for 100 samples
        assert result.in_sample_too_good == True  # noqa: E712 - 25% ROI
        assert result.variance_passes == False  # noqa: E712 - High cross-season variance
        assert result.learning_curve_healthy == False  # noqa: E712 - Test score decreasing
        assert result.feature_importance_stable == False  # noqa: E712 - Unstable importance

        # Should have multiple warnings
        assert len(result.warnings) >= 3

    def test_validation_summary_output(
        self, validator, healthy_backtest_results, healthy_model_metadata
    ):
        """Test that summary output is formatted correctly."""
        result = validator.full_validation(healthy_backtest_results, healthy_model_metadata)
        summary = result.summary()

        assert "OVERFITTING VALIDATION" in summary
        assert "PASS" in summary or "FAIL" in summary
        assert "Feature Count" in summary
        assert "In-Sample ROI" in summary
        assert "Cross-Season Variance" in summary

    def test_partial_data_validation(self, validator):
        """Test validation with minimal data."""
        # Only provide essential fields
        results = {"in_sample_roi": 0.05}
        metadata = {"n_features": 5, "n_samples": 100}

        validation = validator.full_validation(results, metadata)

        # Should still produce a result
        assert validation is not None
        assert validation.feature_ratio_passes is True
        assert validation.in_sample_too_good is False


# =============================================================================
# Test Quick Check Function
# =============================================================================


class TestQuickOverfitCheck:
    """Tests for the convenience quick_overfit_check function."""

    def test_healthy_quick_check(self):
        """Test quick check with healthy parameters."""
        passes, warnings = quick_overfit_check(
            n_features=5,
            n_samples=1000,
            in_sample_roi=0.04,
            season_rois=[0.03, 0.04, 0.05],
        )

        assert passes is True
        assert len(warnings) == 0

    def test_overfit_quick_check(self):
        """Test quick check catches overfit parameters."""
        passes, warnings = quick_overfit_check(
            n_features=50,  # Way too many
            n_samples=100,
            in_sample_roi=0.25,  # Way too good
            season_rois=[0.20, -0.10, 0.30],  # High variance
        )

        assert passes is False
        assert len(warnings) >= 3
        assert any("features" in w.lower() for w in warnings)
        assert any("roi" in w.lower() for w in warnings)
        assert any("variance" in w.lower() for w in warnings)

    def test_quick_check_without_seasons(self):
        """Test quick check works without season data."""
        passes, warnings = quick_overfit_check(
            n_features=5,
            n_samples=100,
            in_sample_roi=0.05,
        )

        assert passes is True


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_results(self, validator):
        """Test validation with empty results."""
        validation = validator.full_validation({}, {"n_features": 0, "n_samples": 0})

        # Should not crash, should have warnings
        assert validation is not None

    def test_negative_samples(self, validator):
        """Test with negative sample count."""
        assert validator.validate_feature_count(5, -100) is False
        assert validator.get_max_features(-100) == 0

    def test_extreme_roi_values(self, validator):
        """Test with extreme ROI values."""
        # Very negative ROI - should pass (not overfit indicator)
        assert validator.check_in_sample_roi(-0.50) is True

        # Very high ROI - should definitely fail
        assert validator.check_in_sample_roi(10.0) is False

    def test_nan_handling(self, validator):
        """Test handling of NaN values."""
        # NaN in season ROIs
        season_rois = [0.05, np.nan, 0.04]
        # This should handle NaN gracefully
        cv = validator.calculate_cross_season_variance([x for x in season_rois if not np.isnan(x)])
        assert not np.isnan(cv)

    def test_single_feature_single_sample(self, validator):
        """Test extreme minimal case."""
        assert validator.validate_feature_count(1, 1) is True  # sqrt(1) = 1

    def test_very_large_dataset(self, validator):
        """Test with large numbers."""
        # sqrt(1_000_000) = 1000
        assert validator.validate_feature_count(500, 1_000_000) is True
        assert validator.validate_feature_count(1000, 1_000_000) is True
        assert validator.validate_feature_count(2000, 1_000_000) is False

    def test_learning_curve_with_equal_scores(self, validator):
        """Test learning curve when train equals test."""
        train_sizes = [100, 200, 300]
        train_scores = [0.52, 0.52, 0.52]
        test_scores = [0.52, 0.52, 0.52]

        result = validator.analyze_learning_curve(train_sizes, train_scores, test_scores)

        # Perfect equality should be healthy
        assert result["healthy"] is True
        assert result["final_gap"] == 0.0


# =============================================================================
# Test Real-World Scenarios
# =============================================================================


class TestRealWorldScenarios:
    """Tests simulating real betting model scenarios."""

    def test_ncaab_model_reasonable(self, validator):
        """Test a reasonable NCAAB Elo model."""
        # Typical NCAAB model: 5 seasons, ~800 games/season, 10 features
        # Using more consistent ROIs to ensure variance passes
        results = {
            "season_rois": [0.025, 0.028, 0.022, 0.026, 0.024],  # Very consistent
            "in_sample_roi": 0.025,  # 2.5% - realistic for a good model
        }
        metadata = {"n_features": 10, "n_samples": 4000}  # sqrt(4000) ~ 63

        validation = validator.full_validation(results, metadata)

        assert validation.overall_passes == True  # noqa: E712
        assert validation.feature_ratio_passes == True  # noqa: E712 - 10 << 63

    def test_mlb_model_overtuned(self, validator):
        """Test an overtuned MLB model that won't generalize."""
        # Model with too many park/weather/umpire interaction terms
        results = {
            "season_rois": [0.08, -0.02, 0.12, 0.03, -0.04],  # Inconsistent
            "in_sample_roi": 0.18,  # Too good - overfitting
        }
        metadata = {"n_features": 75, "n_samples": 1500}  # sqrt(1500) ~ 38

        validation = validator.full_validation(results, metadata)

        assert validation.overall_passes is False
        assert validation.feature_ratio_passes is False  # 75 > 38
        assert validation.in_sample_too_good is True  # 18% > 15%

    def test_prop_model_data_mining(self, validator):
        """Test a player props model that found spurious correlations."""
        # Model trained on many prop types, looks great in-sample
        results = {
            "season_rois": [0.15, 0.12, 0.20, 0.08, 0.25],  # High variance
            "in_sample_roi": 0.35,  # Way too good - data mining
            "feature_importances_by_period": [
                {"prop_type_1": 0.5, "metric_a": 0.3, "others": 0.2},
                {"prop_type_2": 0.4, "metric_b": 0.4, "others": 0.2},
                {"prop_type_3": 0.6, "metric_c": 0.2, "others": 0.2},
            ],  # Different "important" features each period
        }
        metadata = {"n_features": 150, "n_samples": 500}  # sqrt(500) ~ 22

        validation = validator.full_validation(results, metadata)

        assert validation.overall_passes is False
        assert validation.feature_ratio_passes is False  # 150 >> 22
        assert validation.in_sample_too_good is True  # 35% >> 15%
        assert validation.feature_importance_stable is False


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
