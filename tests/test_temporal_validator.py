"""Comprehensive Tests for Temporal Validator.

These tests validate the temporal integrity validator, which is the FIRST LINE
OF DEFENSE against the most dangerous bias in sports betting backtests.

Test Categories:
1. Clean datasets that should PASS validation
2. Known-leaky datasets that should FAIL validation
3. Edge cases: same-day games, timezone issues
4. Integration with walk-forward validation

CRITICAL: If these tests fail, your backtest results cannot be trusted.
"""

from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from backtesting.validators.temporal_validator import (
    LeakageType,
    TemporalValidationResult,
    TemporalValidator,
)


# =============================================================================
# FIXTURES - Test Data Generators
# =============================================================================


@pytest.fixture
def clean_dataset():
    """Generate a clean dataset with no temporal leakage.

    Features are properly lagged with .shift(1) applied.
    """
    np.random.seed(42)
    n_samples = 200

    # Generate dates (sorted chronologically)
    dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="D")

    # Generate clean features (no leakage)
    df = pd.DataFrame(
        {
            "game_date": dates,
            "team_id": np.tile(["team_a", "team_b", "team_c", "team_d"], n_samples // 4),
            # Feature 1: Properly lagged rolling average (shift applied)
            "elo_rating": np.random.normal(1500, 100, n_samples),
            # Feature 2: Static team strength
            "team_strength": np.random.uniform(0.4, 0.6, n_samples),
            # Feature 3: Home court advantage
            "is_home": np.random.choice([0, 1], n_samples),
            # Target: Binary outcome
            "target": np.random.choice([0, 1], n_samples),
        }
    )

    # Add properly lagged rolling feature
    df = df.sort_values("game_date").reset_index(drop=True)
    df["rolling_avg"] = df["elo_rating"].rolling(5).mean().shift(1)

    return df


@pytest.fixture
def leaky_dataset_correlation():
    """Generate a dataset with correlation leakage.

    A feature correlates suspiciously high with target (>0.95).
    """
    np.random.seed(42)
    n_samples = 200

    dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="D")
    target = np.random.choice([0, 1], n_samples)

    df = pd.DataFrame(
        {
            "game_date": dates,
            "target": target,
            # LEAKY: Feature derived from target with small noise
            "leaky_feature": target + np.random.normal(0, 0.05, n_samples),
            # Clean feature
            "clean_feature": np.random.normal(0, 1, n_samples),
        }
    )

    return df


@pytest.fixture
def leaky_dataset_no_shift():
    """Generate a dataset with rolling calculation leakage.

    Rolling average is NOT shifted, so it includes current observation.
    The feature has values from position 0 after forward fill.
    """
    np.random.seed(42)
    n_samples = 200

    dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="D")

    df = pd.DataFrame(
        {
            "game_date": dates,
            "score": np.random.randint(60, 100, n_samples),
            "target": np.random.choice([0, 1], n_samples),
        }
    )

    # LEAKY: Rolling average WITHOUT shift AND forward filled (no NaN at start)
    # This simulates a common mistake where NaN are filled instead of keeping proper lag
    df["rolling_avg_score"] = (
        df["score"].rolling(5, min_periods=1).mean()
    )  # min_periods=1 means value at row 0

    return df


@pytest.fixture
def leaky_dataset_train_test_overlap():
    """Generate train/test indices with overlap."""
    n_samples = 200
    dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="D")

    df = pd.DataFrame(
        {
            "game_date": dates,
            "feature": np.random.normal(0, 1, n_samples),
            "target": np.random.choice([0, 1], n_samples),
        }
    )

    # LEAKY: Overlapping indices
    train_indices = np.arange(0, 150)  # 0-149
    test_indices = np.arange(100, 200)  # 100-199 (overlaps with 100-149!)

    return df, train_indices, test_indices


@pytest.fixture
def leaky_dataset_future_dates():
    """Generate dataset where test data precedes training data."""
    n_samples = 200
    dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="D")

    df = pd.DataFrame(
        {
            "game_date": dates,
            "feature": np.random.normal(0, 1, n_samples),
            "target": np.random.choice([0, 1], n_samples),
        }
    )

    # LEAKY: Test data is BEFORE training data!
    train_indices = np.arange(100, 200)  # Later dates for training
    test_indices = np.arange(0, 50)  # Earlier dates for testing!

    return df, train_indices, test_indices


@pytest.fixture
def dataset_with_closing_line_issues():
    """Generate dataset with closing line timing violations."""
    n_samples = 100
    game_times = pd.date_range(start="2024-01-01 19:00:00", periods=n_samples, freq="D")

    # Generate capture times - some before (-1 hour) and some after (+2 hours) game time
    np.random.seed(42)
    hour_offsets = np.random.choice([-1, 2], n_samples)

    df = pd.DataFrame(
        {
            "game_time": game_times,
            "closing_line": np.random.uniform(-5, 5, n_samples),
            # LEAKY: Some closing lines captured AFTER game start
            "closing_captured_at": [
                gt + timedelta(hours=int(offset))  # Convert to int for timedelta
                for gt, offset in zip(game_times, hour_offsets)
            ],
        }
    )

    return df


@pytest.fixture
def validator():
    """Create a TemporalValidator instance."""
    return TemporalValidator(
        correlation_threshold=0.95,
        min_train_test_gap_days=1,
        strict_mode=False,
    )


# =============================================================================
# TESTS - Clean Dataset (Should PASS)
# =============================================================================


class TestCleanDataset:
    """Tests that verify clean datasets pass validation."""

    def test_clean_dataset_passes_full_validation(self, validator, clean_dataset):
        """A properly constructed dataset should pass all validations."""
        df = clean_dataset
        feature_cols = ["elo_rating", "team_strength", "is_home", "rolling_avg"]

        # Create valid train/test split
        train_indices = np.arange(0, 150)
        test_indices = np.arange(155, 200)  # Gap of 5 days

        result = validator.full_validation(
            df=df,
            feature_cols=feature_cols,
            target_col="target",
            date_col="game_date",
            train_indices=train_indices,
            test_indices=test_indices,
        )

        assert result.passed, f"Clean dataset should pass. Report:\n{result.report_summary}"
        assert result.walk_forward_valid
        assert result.n_issues_found == 0

    def test_clean_walk_forward_structure(self, validator, clean_dataset):
        """Walk-forward validation with proper split should pass."""
        df = clean_dataset

        train_indices = np.arange(0, 100)
        test_indices = np.arange(105, 150)

        result = validator.validate_walk_forward(
            df=df,
            date_col="game_date",
            train_size=100,
            test_size=45,
            train_indices=train_indices,
            test_indices=test_indices,
        )

        assert result.is_valid
        assert len(result.issues) == 0 or all("WARNING" not in i for i in result.issues)
        assert len(result.fold_details) == 1
        assert result.fold_details[0]["gap_days"] >= 1

    def test_no_leakage_in_clean_features(self, validator, clean_dataset):
        """Clean features should not trigger leakage detection."""
        df = clean_dataset
        feature_cols = ["elo_rating", "team_strength", "is_home"]

        leaky = validator.detect_leakage(
            df=df,
            feature_cols=feature_cols,
            target_col="target",
            date_col="game_date",
        )

        assert (
            len(leaky) == 0
        ), f"Should find no leakage. Found: {[leak.feature_name for leak in leaky]}"


# =============================================================================
# TESTS - Leaky Dataset (Should FAIL)
# =============================================================================


class TestLeakyDataset:
    """Tests that verify leaky datasets are caught."""

    def test_detects_correlation_leakage(self, validator, leaky_dataset_correlation):
        """Should detect features with suspiciously high correlation."""
        df = leaky_dataset_correlation
        feature_cols = ["leaky_feature", "clean_feature"]

        leaky = validator.detect_leakage(
            df=df,
            feature_cols=feature_cols,
            target_col="target",
            date_col="game_date",
        )

        # Should detect the leaky feature
        leaky_names = [leak.feature_name for leak in leaky]
        assert "leaky_feature" in leaky_names, "Should detect correlation leakage"

        # Check it's flagged as correlation spike
        leaky_feature_info = next(leak for leak in leaky if leak.feature_name == "leaky_feature")
        assert leaky_feature_info.leakage_type == LeakageType.CORRELATION_SPIKE
        assert leaky_feature_info.severity == "high"

    def test_detects_rolling_without_shift(self, validator, leaky_dataset_no_shift):
        """Should detect rolling calculations without proper .shift(1)."""
        df = leaky_dataset_no_shift
        feature_cols = ["rolling_avg_score"]

        leaky = validator.detect_leakage(
            df=df,
            feature_cols=feature_cols,
            target_col="target",
            date_col="game_date",
        )

        # Should detect the unshifted rolling feature
        leaky_names = [leak.feature_name for leak in leaky]
        assert "rolling_avg_score" in leaky_names, "Should detect unshifted rolling"

        leaky_feature_info = next(
            leak for leak in leaky if leak.feature_name == "rolling_avg_score"
        )
        assert leaky_feature_info.leakage_type == LeakageType.ROLLING_NO_SHIFT

    def test_detects_train_test_overlap(self, validator, leaky_dataset_train_test_overlap):
        """Should detect when train and test sets overlap."""
        df, train_indices, test_indices = leaky_dataset_train_test_overlap

        result = validator.validate_walk_forward(
            df=df,
            date_col="game_date",
            train_size=150,
            test_size=100,
            train_indices=train_indices,
            test_indices=test_indices,
        )

        assert not result.is_valid, "Should fail due to overlap"
        assert any("CRITICAL" in issue for issue in result.issues)
        assert any("overlap" in issue.lower() for issue in result.issues)

    def test_detects_temporal_ordering_violation(self, validator, leaky_dataset_future_dates):
        """Should detect when test data precedes training data."""
        df, train_indices, test_indices = leaky_dataset_future_dates

        result = validator.validate_walk_forward(
            df=df,
            date_col="game_date",
            train_size=100,
            test_size=50,
            train_indices=train_indices,
            test_indices=test_indices,
        )

        assert not result.is_valid, "Should fail: test before train"
        assert any("CRITICAL" in issue for issue in result.issues)

    def test_detects_closing_line_timing_issues(self, validator, dataset_with_closing_line_issues):
        """Should detect closing lines captured after game start."""
        df = dataset_with_closing_line_issues

        is_valid, issues = validator.validate_closing_line_timing(
            bets_df=df,
            closing_line_col="closing_line",
            game_time_col="game_time",
            closing_captured_at_col="closing_captured_at",
        )

        assert not is_valid, "Should fail: some closing lines captured after game"
        assert any("CRITICAL" in issue for issue in issues)


# =============================================================================
# TESTS - Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_same_day_games_with_gap(self, validator):
        """Same-day games should pass if ordered correctly within the day."""
        n_samples = 20
        # Multiple games on same day, but ordered by time
        dates = pd.to_datetime(
            ["2024-01-01 12:00", "2024-01-01 15:00", "2024-01-01 19:00"] * 6
            + ["2024-01-02 12:00", "2024-01-02 19:00"]
        )[:n_samples]

        df = (
            pd.DataFrame(
                {
                    "game_date": dates,
                    "feature": np.random.normal(0, 1, n_samples),
                    "target": np.random.choice([0, 1], n_samples),
                }
            )
            .sort_values("game_date")
            .reset_index(drop=True)
        )

        train_indices = np.arange(0, 12)
        test_indices = np.arange(14, 20)

        result = validator.validate_walk_forward(
            df=df,
            date_col="game_date",
            train_size=12,
            test_size=6,
            train_indices=train_indices,
            test_indices=test_indices,
        )

        assert result.is_valid

    def test_empty_dataframe(self, validator):
        """Should handle empty DataFrames gracefully."""
        df = pd.DataFrame(columns=["game_date", "feature", "target"])

        result = validator.validate_walk_forward(
            df=df,
            date_col="game_date",
            train_size=10,
            test_size=5,
        )

        # Empty dataframe has no data to validate
        assert result.is_valid  # No violations found in empty data

    def test_single_sample_per_set(self, validator):
        """Should handle minimal sample sizes."""
        dates = pd.date_range(start="2024-01-01", periods=10, freq="D")
        df = pd.DataFrame(
            {
                "game_date": dates,
                "feature": np.random.normal(0, 1, 10),
                "target": np.random.choice([0, 1], 10),
            }
        )

        train_indices = np.array([0, 1, 2])
        test_indices = np.array([5, 6, 7])

        result = validator.validate_walk_forward(
            df=df,
            date_col="game_date",
            train_size=3,
            test_size=3,
            train_indices=train_indices,
            test_indices=test_indices,
        )

        assert result.is_valid

    def test_feature_with_future_in_name(self, validator):
        """Should flag features with suspicious naming patterns."""
        n_samples = 50
        dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="D")

        df = pd.DataFrame(
            {
                "game_date": dates,
                "final_score": np.random.randint(60, 100, n_samples),
                "actual_margin": np.random.uniform(-10, 10, n_samples),
                "outcome_indicator": np.random.choice([0, 1], n_samples),
                "target": np.random.choice([0, 1], n_samples),
            }
        )

        feature_cols = ["final_score", "actual_margin", "outcome_indicator"]

        leaky = validator.detect_leakage(
            df=df,
            feature_cols=feature_cols,
            target_col="target",
            date_col="game_date",
        )

        leaky_names = [leak.feature_name for leak in leaky]

        # All these should be flagged due to suspicious naming
        assert "final_score" in leaky_names
        assert "actual_margin" in leaky_names
        assert "outcome_indicator" in leaky_names

    def test_gap_exactly_at_threshold(self, validator):
        """Should pass when gap equals exactly the minimum threshold."""
        validator_strict = TemporalValidator(min_train_test_gap_days=1)

        dates = pd.date_range(start="2024-01-01", periods=20, freq="D")
        df = pd.DataFrame(
            {
                "game_date": dates,
                "feature": np.random.normal(0, 1, 20),
                "target": np.random.choice([0, 1], 20),
            }
        )

        # Exactly 1 day gap
        train_indices = np.arange(0, 10)  # Days 0-9
        test_indices = np.arange(11, 20)  # Days 11-19 (gap of 1 day)

        result = validator_strict.validate_walk_forward(
            df=df,
            date_col="game_date",
            train_size=10,
            test_size=9,
            train_indices=train_indices,
            test_indices=test_indices,
        )

        assert result.is_valid


# =============================================================================
# TESTS - Timestamp Auditing
# =============================================================================


class TestTimestampAuditing:
    """Tests for feature timestamp auditing."""

    def test_audit_passes_for_pregame_features(self, validator):
        """Features available before game should pass."""
        metadata = {
            "elo_rating": {
                "available_at": "pre_game",
                "source": "database",
                "lag_applied": False,
            },
            "team_strength": {
                "available_at": "season_start",
                "source": "calculated",
                "lag_applied": True,
            },
        }

        violations = validator.audit_feature_timestamps(metadata)
        assert len(violations) == 0

    def test_audit_fails_for_postgame_features(self, validator):
        """Features available only after game should fail without lag."""
        metadata = {
            "final_score": {
                "available_at": "game_end",
                "source": "game_log",
                "lag_applied": False,  # Not lagged!
            },
            "result_binary": {
                "available_at": "postgame",
                "source": "calculated",
                "lag_applied": False,
            },
        }

        violations = validator.audit_feature_timestamps(metadata)

        assert len(violations) == 2
        violation_names = [v.feature_name for v in violations]
        assert "final_score" in violation_names
        assert "result_binary" in violation_names

    def test_audit_passes_for_lagged_postgame_features(self, validator):
        """Postgame features should pass if properly lagged."""
        metadata = {
            "last_game_score": {
                "available_at": "game_end",
                "source": "game_log",
                "lag_applied": True,  # Properly lagged!
            },
        }

        violations = validator.audit_feature_timestamps(metadata)
        assert len(violations) == 0


# =============================================================================
# TESTS - Train/Test Contamination
# =============================================================================


class TestTrainTestContamination:
    """Tests for train/test contamination detection."""

    def test_detects_index_overlap(self, validator):
        """Should detect overlapping indices."""
        df = pd.DataFrame(
            {
                "game_date": pd.date_range(start="2024-01-01", periods=100, freq="D"),
                "feature": np.random.normal(0, 1, 100),
            }
        )

        train_indices = np.arange(0, 60)
        test_indices = np.arange(50, 80)  # Overlaps 50-59

        is_valid, issues = validator.detect_train_test_contamination(
            df, train_indices, test_indices
        )

        assert not is_valid
        assert any("10 indices" in issue for issue in issues)

    def test_passes_disjoint_sets(self, validator):
        """Should pass for non-overlapping indices."""
        df = pd.DataFrame(
            {
                "game_date": pd.date_range(start="2024-01-01", periods=100, freq="D"),
                "feature": np.random.normal(0, 1, 100),
            }
        )

        train_indices = np.arange(0, 50)
        test_indices = np.arange(60, 100)  # No overlap

        is_valid, issues = validator.detect_train_test_contamination(
            df, train_indices, test_indices
        )

        assert is_valid


# =============================================================================
# TESTS - Report Generation
# =============================================================================


class TestReportGeneration:
    """Tests for report generation functionality."""

    def test_report_includes_all_issues(self, validator, leaky_dataset_correlation):
        """Report should include all detected issues."""
        df = leaky_dataset_correlation

        validator.detect_leakage(
            df=df,
            feature_cols=["leaky_feature"],
            target_col="target",
            date_col="game_date",
        )

        report = validator.generate_leakage_report()

        assert report["n_issues"] > 0
        assert len(report["features_flagged"]) > 0
        assert len(report["recommendations"]) > 0
        assert "leaky_feature" in report["features_flagged"]

    def test_full_validation_report_summary(self, validator, leaky_dataset_correlation):
        """Full validation should produce readable summary."""
        df = leaky_dataset_correlation
        train_indices = np.arange(0, 100)
        test_indices = np.arange(110, 200)

        result = validator.full_validation(
            df=df,
            feature_cols=["leaky_feature", "clean_feature"],
            target_col="target",
            date_col="game_date",
            train_indices=train_indices,
            test_indices=test_indices,
        )

        assert "TEMPORAL INTEGRITY VALIDATION REPORT" in result.report_summary
        assert "FAILED" in result.report_summary or "PASSED" in result.report_summary


# =============================================================================
# TESTS - Statistical Leakage Detection
# =============================================================================


class TestStatisticalLeakage:
    """Tests for statistical leakage detection."""

    def test_detects_unrealistic_win_rate(self, validator):
        """Should flag unrealistically high win rates."""
        n_samples = 100
        dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="D")

        df = pd.DataFrame(
            {
                "game_date": dates,
                "result": ["win"] * 85 + ["loss"] * 15,  # 85% win rate - suspicious!
            }
        )

        passed, issues = validator._statistical_leakage_check(df)

        assert not passed
        assert any("85" in issue or "unrealistically" in issue.lower() for issue in issues)

    def test_accepts_realistic_win_rate(self, validator):
        """Should accept realistic win rates."""
        n_samples = 100
        dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="D")

        df = pd.DataFrame(
            {
                "game_date": dates,
                "result": ["win"] * 55 + ["loss"] * 45,  # 55% - realistic
            }
        )

        passed, issues = validator._statistical_leakage_check(df)

        assert passed


# =============================================================================
# TESTS - Legacy Compatibility
# =============================================================================


class TestLegacyCompatibility:
    """Tests for legacy method compatibility."""

    def test_legacy_validate_method(self, validator):
        """Legacy validate() method should still work."""
        n_samples = 100
        dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="D")

        df = pd.DataFrame(
            {
                "game_date": dates,
                "prediction_date": dates - timedelta(days=1),  # Predictions before game
                "result": np.random.choice(["win", "loss"], n_samples),
            }
        )

        result = validator.validate(df)

        assert isinstance(result, TemporalValidationResult)
        assert hasattr(result, "passed")
        assert hasattr(result, "report_summary")

    def test_legacy_detect_data_leakage(self, validator):
        """Legacy detect_data_leakage() method should still work."""
        n_samples = 50
        df = pd.DataFrame(
            {
                "feature1": np.random.normal(0, 1, n_samples),
                "feature2": np.zeros(n_samples),  # Zero variance
                "result": np.random.choice([0, 1], n_samples),
            }
        )

        indicators = validator.detect_data_leakage(df, target_col="result")

        assert "zero_variance_features" in indicators
        assert "feature2" in indicators["zero_variance_features"]


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests with realistic scenarios."""

    def test_full_backtest_workflow(self, validator, clean_dataset):
        """Simulate a complete backtest validation workflow."""
        df = clean_dataset

        # Define multiple folds
        folds = [
            (np.arange(0, 50), np.arange(55, 80)),
            (np.arange(25, 80), np.arange(85, 110)),
            (np.arange(50, 110), np.arange(115, 150)),
        ]

        feature_cols = ["elo_rating", "team_strength", "is_home", "rolling_avg"]

        all_valid = True
        for train_idx, test_idx in folds:
            result = validator.full_validation(
                df=df,
                feature_cols=feature_cols,
                target_col="target",
                date_col="game_date",
                train_indices=train_idx,
                test_indices=test_idx,
            )
            if not result.passed:
                all_valid = False
                break

        assert all_valid, "All folds should pass validation"

    def test_catches_subtle_leakage(self, validator):
        """Test detection of subtle leakage patterns."""
        np.random.seed(42)
        n_samples = 200

        dates = pd.date_range(start="2024-01-01", periods=n_samples, freq="D")
        target = np.random.choice([0, 1], n_samples)

        df = pd.DataFrame(
            {
                "game_date": dates,
                "target": target,
                # Subtle leakage: feature slightly correlates with target
                "subtle_leak": target * 0.8 + np.random.normal(0, 0.3, n_samples),
                # Very subtle leakage: 0.85 correlation
                "very_subtle": target * 0.7 + np.random.normal(0, 0.4, n_samples),
            }
        )

        # With default threshold (0.95), very_subtle might not be caught
        # But subtle_leak should be closer to detection

        validator.detect_leakage(
            df=df,
            feature_cols=["subtle_leak", "very_subtle"],
            target_col="target",
            date_col="game_date",
        )

        # At least one should be flagged with lower threshold
        validator_sensitive = TemporalValidator(correlation_threshold=0.7)
        leaky_sensitive = validator_sensitive.detect_leakage(
            df=df,
            feature_cols=["subtle_leak", "very_subtle"],
            target_col="target",
            date_col="game_date",
        )

        assert len(leaky_sensitive) >= 1, "Sensitive validator should catch subtle leakage"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
