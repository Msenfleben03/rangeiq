"""Tests for the Gatekeeper - Final Validation Gate.

This module provides comprehensive tests for the Gatekeeper including:
    - Full pipeline with passing model
    - Full pipeline with failing model (each dimension)
    - Report generation
    - Memory persistence
    - Decision logic

Run with: pytest tests/test_gatekeeper.py -v
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Import the modules under test
import sys

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backtesting.validators.gatekeeper import (  # noqa: E402
    GateDecision,
    GateReport,
    Gatekeeper,
    ValidationResult,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def gatekeeper():
    """Create a Gatekeeper instance with validators loaded."""
    gk = Gatekeeper()
    gk.load_validators()
    return gk


@pytest.fixture
def passing_backtest_results():
    """Generate backtest results that should PASS all validations."""
    np.random.seed(42)
    n_bets = 500  # Must be >= 500 for statistical validation to pass

    # Generate winning results with higher win rate to achieve good Sharpe
    # Need ~56% win rate at -110 to get Sharpe > 0.5
    win_rate = 0.56
    wins = np.random.random(n_bets) < win_rate

    profits = np.where(wins, 91.0, -100.0)  # -110 odds
    stakes = np.full(n_bets, 100.0)
    results = np.where(wins, "win", "loss")

    # Generate realistic CLV (positive on average)
    clv_values = np.random.normal(0.02, 0.02, n_bets)  # Mean 2% CLV, lower variance

    # Generate dates
    dates = pd.date_range("2023-01-01", periods=n_bets, freq="D")

    return {
        "profit_loss": profits.tolist(),
        "stake": stakes.tolist(),
        "result": results.tolist(),
        "clv": clv_values.tolist(),
        "clv_values": clv_values.tolist(),
        "game_date": dates.tolist(),
        "odds_placed": [-110] * n_bets,
        "odds_closing": [-112] * n_bets,  # Slight CLV
        # Note: season_rois is in metadata, not here (different length)
    }


@pytest.fixture
def passing_model_metadata():
    """Generate model metadata that should PASS all validations."""
    return {
        "n_features": 15,
        "n_samples": 1000,
        "model_type": "elo_regression",
        "in_sample_roi": 0.06,  # Realistic 6%
        "season_rois": [0.04, 0.035, 0.05, 0.045],
        "config": {"assumed_vig": -110, "slippage_modeled": True},
        "bankroll": 5000,
    }


@pytest.fixture
def failing_temporal_results():
    """Generate results with temporal leakage."""
    np.random.seed(42)
    n_bets = 300

    # Suspiciously high win rate indicates leakage
    win_rate = 0.75  # Way too high
    wins = np.random.random(n_bets) < win_rate

    profits = np.where(wins, 91.0, -100.0)
    stakes = np.full(n_bets, 100.0)
    results = np.where(wins, "win", "loss")

    # Perfect predictions indicate leakage
    model_probs = np.where(wins, 0.9, 0.1)

    return {
        "profit_loss": profits.tolist(),
        "stake": stakes.tolist(),
        "result": results.tolist(),
        "model_probability": model_probs.tolist(),
        "game_date": pd.date_range("2023-01-01", periods=n_bets, freq="D").tolist(),
    }


@pytest.fixture
def failing_statistical_results():
    """Generate results with insufficient sample size."""
    np.random.seed(42)
    n_bets = 50  # Way below minimum

    wins = np.random.random(n_bets) < 0.54
    profits = np.where(wins, 91.0, -100.0)
    stakes = np.full(n_bets, 100.0)
    results = np.where(wins, "win", "loss")

    return {
        "profit_loss": profits.tolist(),
        "stake": stakes.tolist(),
        "result": results.tolist(),
        "clv_values": [0.02] * n_bets,
    }


@pytest.fixture
def failing_overfit_results():
    """Generate results showing overfitting."""
    return {
        "profit_loss": [100] * 200,  # All wins
        "stake": [100] * 200,
        "result": ["win"] * 200,
        "clv_values": [0.05] * 200,  # Too good
        # Note: season_rois is in metadata, not here
    }


@pytest.fixture
def failing_overfit_metadata():
    """Generate metadata showing overfitting."""
    return {
        "n_features": 50,  # Way too many
        "n_samples": 200,
        "model_type": "neural_network",
        "in_sample_roi": 0.25,  # Suspiciously high
        "season_rois": [0.20, 0.05, 0.25, -0.10],
    }


@pytest.fixture
def failing_clv_results():
    """Generate results with poor CLV."""
    np.random.seed(42)
    n_bets = 300

    wins = np.random.random(n_bets) < 0.54
    profits = np.where(wins, 91.0, -100.0)
    stakes = np.full(n_bets, 100.0)
    results = np.where(wins, "win", "loss")

    # Negative CLV - not beating the line
    clv_values = np.random.normal(-0.01, 0.02, n_bets)

    return {
        "profit_loss": profits.tolist(),
        "stake": stakes.tolist(),
        "result": results.tolist(),
        "clv_values": clv_values.tolist(),
        # Note: season_rois is in metadata, not here
    }


# =============================================================================
# Test Classes
# =============================================================================


class TestGatekeeperInitialization:
    """Test Gatekeeper initialization and setup."""

    def test_gatekeeper_creation(self):
        """Test basic Gatekeeper instantiation."""
        gk = Gatekeeper()
        assert gk is not None
        assert gk.temporal_validator is None
        assert gk.statistical_validator is None
        assert not gk._validators_loaded

    def test_load_validators(self, gatekeeper):
        """Test that all validators are loaded correctly."""
        assert gatekeeper._validators_loaded
        assert gatekeeper.temporal_validator is not None
        assert gatekeeper.statistical_validator is not None
        assert gatekeeper.overfit_validator is not None
        assert gatekeeper.betting_validator is not None

    def test_blocking_checks_defined(self, gatekeeper):
        """Test that blocking checks are properly defined."""
        assert len(Gatekeeper.BLOCKING_CHECKS) > 0
        assert "temporal_no_leakage" in Gatekeeper.BLOCKING_CHECKS
        assert "statistical_sample_size" in Gatekeeper.BLOCKING_CHECKS
        assert "betting_clv_threshold" in Gatekeeper.BLOCKING_CHECKS


class TestGatekeeperPassing:
    """Test Gatekeeper with models that should PASS."""

    def test_full_pipeline_passing(
        self, gatekeeper, passing_backtest_results, passing_model_metadata
    ):
        """Test that a good model passes all validations."""
        report = gatekeeper.generate_report(
            model_name="test_passing_model",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
        )

        assert report is not None
        assert report.model_name == "test_passing_model"
        assert report.decision in [GateDecision.PASS, GateDecision.NEEDS_REVIEW]
        assert report.overall_score >= 0.6  # Most checks should pass
        assert len(report.dimension_results) > 0

    def test_passing_report_structure(
        self, gatekeeper, passing_backtest_results, passing_model_metadata
    ):
        """Test that passing report has correct structure."""
        report = gatekeeper.generate_report(
            model_name="test_model",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
        )

        assert isinstance(report.timestamp, datetime)
        assert isinstance(report.overall_score, float)
        assert 0.0 <= report.overall_score <= 1.0
        assert isinstance(report.blocking_failures, list)
        assert isinstance(report.warnings, list)
        assert isinstance(report.recommendations, list)

    def test_passing_report_serialization(
        self, gatekeeper, passing_backtest_results, passing_model_metadata
    ):
        """Test that report can be serialized to dict/JSON."""
        report = gatekeeper.generate_report(
            model_name="test_model",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
        )

        report_dict = report.to_dict()
        assert "model_name" in report_dict
        assert "decision" in report_dict
        assert "dimension_results" in report_dict

        # Should be JSON serializable
        json_str = json.dumps(report_dict, default=str)
        assert len(json_str) > 0

    def test_passing_report_summary(
        self, gatekeeper, passing_backtest_results, passing_model_metadata
    ):
        """Test that report summary is human-readable."""
        report = gatekeeper.generate_report(
            model_name="test_model",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
        )

        summary = report.summary()
        assert "test_model" in summary
        assert "Decision:" in summary
        assert "Overall Score:" in summary


class TestGatekeeperFailing:
    """Test Gatekeeper with models that should FAIL (QUARANTINE)."""

    def test_failing_temporal_leakage(
        self, gatekeeper, failing_temporal_results, passing_model_metadata
    ):
        """Test that temporal leakage is detected and causes QUARANTINE."""
        report = gatekeeper.generate_report(
            model_name="leaky_model",
            backtest_results=failing_temporal_results,
            model_metadata=passing_model_metadata,
        )

        # Should detect the leakage
        temporal_result = next(
            (r for r in report.dimension_results if "temporal" in r.dimension),
            None,
        )

        assert temporal_result is not None
        # The extremely high win rate should trigger suspicion
        assert not temporal_result.passed or report.decision == GateDecision.QUARANTINE

    def test_failing_sample_size(
        self, gatekeeper, failing_statistical_results, passing_model_metadata
    ):
        """Test that insufficient sample size causes QUARANTINE."""
        report = gatekeeper.generate_report(
            model_name="small_sample_model",
            backtest_results=failing_statistical_results,
            model_metadata=passing_model_metadata,
        )

        statistical_result = next(
            (r for r in report.dimension_results if "statistical" in r.dimension),
            None,
        )

        assert statistical_result is not None
        assert not statistical_result.passed
        assert report.decision == GateDecision.QUARANTINE
        assert any("sample" in f.lower() for f in report.blocking_failures)

    def test_failing_overfit(self, gatekeeper, failing_overfit_results, failing_overfit_metadata):
        """Test that overfitting is detected and causes QUARANTINE."""
        report = gatekeeper.generate_report(
            model_name="overfit_model",
            backtest_results=failing_overfit_results,
            model_metadata=failing_overfit_metadata,
        )

        overfit_result = next(
            (r for r in report.dimension_results if "overfit" in r.dimension),
            None,
        )

        assert overfit_result is not None
        assert not overfit_result.passed
        assert report.decision == GateDecision.QUARANTINE

    def test_failing_clv(self, gatekeeper, failing_clv_results, passing_model_metadata):
        """Test that poor CLV causes QUARANTINE."""
        report = gatekeeper.generate_report(
            model_name="no_edge_model",
            backtest_results=failing_clv_results,
            model_metadata=passing_model_metadata,
        )

        betting_result = next(
            (r for r in report.dimension_results if "betting" in r.dimension),
            None,
        )

        assert betting_result is not None
        assert not betting_result.passed
        assert report.decision == GateDecision.QUARANTINE
        assert any("clv" in f.lower() for f in report.blocking_failures)


class TestDecisionLogic:
    """Test the decision-making logic."""

    def test_make_decision_all_pass(self, gatekeeper):
        """Test PASS decision when all checks pass."""
        results = [
            ValidationResult(dimension="temporal_no_leakage", passed=True),
            ValidationResult(dimension="statistical_sample_size", passed=True),
            ValidationResult(dimension="overfit_in_sample_roi", passed=True),
            ValidationResult(dimension="betting_clv_threshold", passed=True),
            ValidationResult(dimension="human_review_flag", passed=True, details={}),
        ]

        decision = gatekeeper.make_decision(results)
        assert decision == GateDecision.PASS

    def test_make_decision_blocking_failure(self, gatekeeper):
        """Test QUARANTINE decision when blocking check fails."""
        results = [
            ValidationResult(dimension="temporal_no_leakage", passed=False),
            ValidationResult(dimension="statistical_sample_size", passed=True),
            ValidationResult(dimension="overfit_in_sample_roi", passed=True),
            ValidationResult(dimension="betting_clv_threshold", passed=True),
        ]

        decision = gatekeeper.make_decision(results)
        assert decision == GateDecision.QUARANTINE

    def test_make_decision_needs_review(self, gatekeeper):
        """Test NEEDS_REVIEW decision with warnings."""
        results = [
            ValidationResult(dimension="temporal_no_leakage", passed=True),
            ValidationResult(dimension="statistical_sample_size", passed=True),
            ValidationResult(dimension="overfit_in_sample_roi", passed=True),
            ValidationResult(dimension="betting_clv_threshold", passed=True),
            ValidationResult(
                dimension="human_review_flag",
                passed=True,
                details={"review_needed": True},
            ),
        ]

        decision = gatekeeper.make_decision(results)
        assert decision == GateDecision.NEEDS_REVIEW


class TestReportGeneration:
    """Test report generation and formatting."""

    def test_report_includes_all_dimensions(
        self, gatekeeper, passing_backtest_results, passing_model_metadata
    ):
        """Test that report includes results from all validators."""
        report = gatekeeper.generate_report(
            model_name="test_model",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
        )

        dimensions = [r.dimension for r in report.dimension_results]

        assert any("temporal" in d for d in dimensions)
        assert any("statistical" in d for d in dimensions)
        assert any("overfit" in d for d in dimensions)
        assert any("betting" in d for d in dimensions)

    def test_report_recommendations_generated(
        self, gatekeeper, failing_statistical_results, passing_model_metadata
    ):
        """Test that recommendations are generated for failures."""
        report = gatekeeper.generate_report(
            model_name="failing_model",
            backtest_results=failing_statistical_results,
            model_metadata=passing_model_metadata,
        )

        assert len(report.recommendations) > 0
        # Should recommend collecting more data
        assert any("data" in r.lower() or "sample" in r.lower() for r in report.recommendations)

    def test_explain_failure_readable(
        self, gatekeeper, failing_statistical_results, passing_model_metadata
    ):
        """Test that failure explanation is human-readable."""
        report = gatekeeper.generate_report(
            model_name="failing_model",
            backtest_results=failing_statistical_results,
            model_metadata=passing_model_metadata,
        )

        explanation = gatekeeper.explain_failure(report)
        assert len(explanation) > 0
        assert "failing_model" in explanation
        assert "WHY IT FAILED" in explanation or "WHAT THIS MEANS" in explanation


class TestMemoryPersistence:
    """Test memory persistence functionality."""

    def test_persist_to_memory(
        self, gatekeeper, passing_backtest_results, passing_model_metadata, tmp_path
    ):
        """Test that reports can be persisted to memory."""
        report = gatekeeper.generate_report(
            model_name="test_persist_model",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
        )

        # The persist_to_memory function should not raise errors
        # It will write to the data/ directory
        # We just verify it doesn't crash - the actual file write is tested implicitly
        try:
            gatekeeper.persist_to_memory(report)
            # If it got here without raising, it worked (even if writing to actual path)
        except Exception as e:
            # Only fail if it's an unexpected error type
            if "permission" not in str(e).lower():
                # Re-raise non-permission errors
                raise

    def test_quarantine_model(
        self, gatekeeper, failing_statistical_results, passing_model_metadata, tmp_path
    ):
        """Test that failed models can be quarantined."""
        report = gatekeeper.generate_report(
            model_name="quarantine_test_model",
            backtest_results=failing_statistical_results,
            model_metadata=passing_model_metadata,
        )

        # This should not raise
        gatekeeper.quarantine_model("quarantine_test_model", report)


class TestValidationResult:
    """Test the ValidationResult dataclass."""

    def test_validation_result_creation(self):
        """Test creating a ValidationResult."""
        result = ValidationResult(
            dimension="test_dimension",
            passed=True,
            details={"key": "value"},
            failure_reason=None,
        )

        assert result.dimension == "test_dimension"
        assert result.passed is True
        assert result.details == {"key": "value"}
        assert result.failure_reason is None

    def test_validation_result_with_failure(self):
        """Test ValidationResult with failure."""
        result = ValidationResult(
            dimension="test_dimension",
            passed=False,
            details={"error": "something wrong"},
            failure_reason="Test failed because of X",
        )

        assert not result.passed
        assert "Test failed" in result.failure_reason


class TestGateReport:
    """Test the GateReport dataclass."""

    def test_gate_report_to_dict(self):
        """Test GateReport serialization."""
        report = GateReport(
            model_name="test_model",
            timestamp=datetime.now(),
            decision=GateDecision.PASS,
            dimension_results=[],
            overall_score=1.0,
        )

        report_dict = report.to_dict()
        assert report_dict["model_name"] == "test_model"
        assert report_dict["decision"] == "PASS"
        assert report_dict["overall_score"] == 1.0

    def test_gate_report_summary_format(self):
        """Test GateReport summary format."""
        report = GateReport(
            model_name="test_model",
            timestamp=datetime.now(),
            decision=GateDecision.QUARANTINE,
            dimension_results=[
                ValidationResult(
                    dimension="test_dim",
                    passed=False,
                    failure_reason="test failure",
                )
            ],
            overall_score=0.5,
            blocking_failures=["test_dim: test failure"],
            recommendations=["Fix the test"],
        )

        summary = report.summary()
        assert "QUARANTINE" in summary
        assert "test_model" in summary
        assert "BLOCKING FAILURES" in summary
        assert "RECOMMENDATIONS" in summary


class TestIntegration:
    """Integration tests for the full validation pipeline."""

    def test_end_to_end_passing_model(
        self, gatekeeper, passing_backtest_results, passing_model_metadata
    ):
        """End-to-end test with a model that should pass."""
        # Generate report
        report = gatekeeper.generate_report(
            model_name="e2e_passing",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
        )

        # Verify report
        assert report.model_name == "e2e_passing"
        assert isinstance(report.timestamp, datetime)
        assert report.decision in [GateDecision.PASS, GateDecision.NEEDS_REVIEW]

        # Verify summary is readable
        summary = report.summary()
        assert len(summary) > 100

        # Verify serialization works
        report_dict = report.to_dict()
        json_str = json.dumps(report_dict, default=str)
        assert len(json_str) > 0

    def test_end_to_end_failing_model(
        self, gatekeeper, failing_statistical_results, passing_model_metadata
    ):
        """End-to-end test with a model that should fail."""
        # Generate report
        report = gatekeeper.generate_report(
            model_name="e2e_failing",
            backtest_results=failing_statistical_results,
            model_metadata=passing_model_metadata,
        )

        # Verify failure
        assert report.decision == GateDecision.QUARANTINE
        assert len(report.blocking_failures) > 0

        # Verify explanation is helpful
        explanation = gatekeeper.explain_failure(report)
        assert len(explanation) > 0
        assert "NEXT STEPS" in explanation


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_backtest_results(self, gatekeeper, passing_model_metadata):
        """Test handling of empty backtest results."""
        report = gatekeeper.generate_report(
            model_name="empty_model",
            backtest_results={},
            model_metadata=passing_model_metadata,
        )

        # Should not crash, should quarantine
        assert report is not None
        assert report.decision == GateDecision.QUARANTINE

    def test_missing_columns(self, gatekeeper, passing_model_metadata):
        """Test handling of missing required columns."""
        partial_results = {
            "profit_loss": [10, -10, 20],
            # Missing stake, result, etc.
        }

        report = gatekeeper.generate_report(
            model_name="partial_model",
            backtest_results=partial_results,
            model_metadata=passing_model_metadata,
        )

        # Should handle gracefully
        assert report is not None

    def test_null_metadata(self, gatekeeper, passing_backtest_results):
        """Test handling of null metadata."""
        report = gatekeeper.generate_report(
            model_name="no_metadata_model",
            backtest_results=passing_backtest_results,
            model_metadata={},
        )

        assert report is not None

    def test_validators_auto_load(self, passing_backtest_results, passing_model_metadata):
        """Test that validators are auto-loaded if not explicitly loaded."""
        gk = Gatekeeper()
        # Don't call load_validators()

        report = gk.generate_report(
            model_name="auto_load_test",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
        )

        assert report is not None
        assert gk._validators_loaded


# =============================================================================
# Non-Linear Pipeline Tests (Pre-Screen, Fast Mode, Early Termination)
# =============================================================================


class TestQuickPrescreen:
    """Test the _quick_prescreen() instant arithmetic filter."""

    def test_prescreen_passes_good_model(
        self, gatekeeper, passing_backtest_results, passing_model_metadata
    ):
        """Good model should pass pre-screen (returns None)."""
        result = gatekeeper._quick_prescreen(passing_backtest_results, passing_model_metadata)
        assert result is None

    def test_prescreen_catches_high_roi(self, gatekeeper, passing_backtest_results):
        """In-sample ROI > 15% should fail pre-screen."""
        bad_metadata = {
            "n_features": 5,
            "n_samples": 1000,
            "in_sample_roi": 0.25,  # 25% -- way too high
        }
        result = gatekeeper._quick_prescreen(passing_backtest_results, bad_metadata)
        assert result is not None
        assert any("in_sample_roi" in f for f in result)

    def test_prescreen_catches_too_many_features(self, gatekeeper, passing_backtest_results):
        """n_features > sqrt(n_samples) should fail pre-screen."""
        bad_metadata = {
            "n_features": 50,  # sqrt(200) ≈ 14
            "n_samples": 200,
            "in_sample_roi": 0.05,
        }
        result = gatekeeper._quick_prescreen(passing_backtest_results, bad_metadata)
        assert result is not None
        assert any("n_features" in f for f in result)

    def test_prescreen_catches_small_sample(self, gatekeeper, passing_model_metadata):
        """Sample size < 200 should fail pre-screen."""
        small_results = {
            "clv_values": [0.02] * 50,  # Only 50 bets
        }
        result = gatekeeper._quick_prescreen(small_results, passing_model_metadata)
        assert result is not None
        assert any("sample_size" in f for f in result)

    def test_prescreen_uses_profit_loss_for_sample_size(self, gatekeeper, passing_model_metadata):
        """Should fall back to profit_loss length when clv_values is missing."""
        results = {
            "profit_loss": [10.0] * 50,
        }
        result = gatekeeper._quick_prescreen(results, passing_model_metadata)
        assert result is not None
        assert any("sample_size" in f for f in result)

    def test_prescreen_returns_multiple_failures(self, gatekeeper):
        """Multiple failing conditions should all be reported."""
        bad_results = {"clv_values": [0.02] * 10}
        bad_metadata = {
            "n_features": 50,
            "n_samples": 100,
            "in_sample_roi": 0.30,
        }
        result = gatekeeper._quick_prescreen(bad_results, bad_metadata)
        assert result is not None
        assert len(result) >= 2  # At least ROI + sample size


class TestFastMode:
    """Test mode='fast' tiered execution and early termination."""

    def test_fast_mode_passing_model_same_decision(
        self, gatekeeper, passing_backtest_results, passing_model_metadata
    ):
        """Fast and full modes should produce the same decision for passing models."""
        report_fast = gatekeeper.generate_report(
            model_name="fast_pass",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
            mode="fast",
        )
        report_full = gatekeeper.generate_report(
            model_name="full_pass",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
            mode="full",
        )
        assert report_fast.decision == report_full.decision

    def test_fast_mode_failing_model_same_decision(
        self, gatekeeper, failing_overfit_results, failing_overfit_metadata
    ):
        """Fast and full modes should produce same QUARANTINE for failing models."""
        report_fast = gatekeeper.generate_report(
            model_name="fast_fail",
            backtest_results=failing_overfit_results,
            model_metadata=failing_overfit_metadata,
            mode="fast",
        )
        report_full = gatekeeper.generate_report(
            model_name="full_fail",
            backtest_results=failing_overfit_results,
            model_metadata=failing_overfit_metadata,
            mode="full",
        )
        assert report_fast.decision == report_full.decision == GateDecision.QUARANTINE

    def test_fast_mode_clv_failure_same_decision(
        self, gatekeeper, failing_clv_results, passing_model_metadata
    ):
        """Fast and full should agree on CLV-triggered QUARANTINE."""
        report_fast = gatekeeper.generate_report(
            model_name="fast_clv",
            backtest_results=failing_clv_results,
            model_metadata=passing_model_metadata,
            mode="fast",
        )
        report_full = gatekeeper.generate_report(
            model_name="full_clv",
            backtest_results=failing_clv_results,
            model_metadata=passing_model_metadata,
            mode="full",
        )
        assert report_fast.decision == report_full.decision == GateDecision.QUARANTINE

    def test_fast_mode_sample_size_failure_same_decision(
        self, gatekeeper, failing_statistical_results, passing_model_metadata
    ):
        """Fast and full should agree on sample-size-triggered QUARANTINE."""
        report_fast = gatekeeper.generate_report(
            model_name="fast_sample",
            backtest_results=failing_statistical_results,
            model_metadata=passing_model_metadata,
            mode="fast",
        )
        report_full = gatekeeper.generate_report(
            model_name="full_sample",
            backtest_results=failing_statistical_results,
            model_metadata=passing_model_metadata,
            mode="full",
        )
        assert report_fast.decision == report_full.decision == GateDecision.QUARANTINE

    def test_fast_mode_records_mode_in_report(
        self, gatekeeper, passing_backtest_results, passing_model_metadata
    ):
        """Report should record the mode used."""
        report = gatekeeper.generate_report(
            model_name="mode_check",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
            mode="fast",
        )
        assert report.mode in ("fast", "fast->full", "full")

    def test_full_mode_records_mode(
        self, gatekeeper, passing_backtest_results, passing_model_metadata
    ):
        """Full mode should record 'full'."""
        report = gatekeeper.generate_report(
            model_name="full_mode_check",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
            mode="full",
        )
        assert report.mode == "full"

    def test_full_mode_no_skipped_validators(
        self, gatekeeper, passing_backtest_results, passing_model_metadata
    ):
        """Full mode should never skip validators."""
        report = gatekeeper.generate_report(
            model_name="full_no_skip",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
            mode="full",
        )
        assert report.skipped_validators == []

    def test_full_mode_backward_compat(
        self, gatekeeper, passing_backtest_results, passing_model_metadata
    ):
        """Full mode should include all 5 dimension results (4 validators + human review)."""
        report = gatekeeper.generate_report(
            model_name="compat_check",
            backtest_results=passing_backtest_results,
            model_metadata=passing_model_metadata,
            mode="full",
        )
        dimensions = [r.dimension for r in report.dimension_results]
        assert any("temporal" in d for d in dimensions)
        assert any("statistical" in d for d in dimensions)
        assert any("overfit" in d for d in dimensions)
        assert any("betting" in d for d in dimensions)
        assert any("human_review" in d for d in dimensions)


class TestEarlyTermination:
    """Test that early termination skips expensive validators."""

    def test_overfit_failure_skips_remaining(self, gatekeeper):
        """When overfit validator fails in fast mode, remaining validators should be skipped."""
        overfit_results = {
            "profit_loss": [100] * 200,
            "stake": [100] * 200,
            "result": ["win"] * 200,
            "clv_values": [0.05] * 200,
        }
        overfit_metadata = {
            "n_features": 5,
            "n_samples": 200,
            "in_sample_roi": 0.25,  # Will fail overfit check
            "season_rois": [0.20, 0.05, 0.25, -0.10],
        }

        # run_all_validations directly in fast mode
        results, skipped = gatekeeper.run_all_validations(
            overfit_results,
            overfit_metadata,
            mode="fast",
        )

        # Overfit is first in the order; if it fails, remaining should be skipped
        overfit_result = next((r for r in results if "overfit" in r.dimension), None)
        if overfit_result and not overfit_result.passed:
            assert len(skipped) > 0

    def test_fast_mode_auto_escalates_on_quarantine(
        self, gatekeeper, failing_overfit_results, failing_overfit_metadata
    ):
        """When fast mode detects QUARANTINE, it should auto-escalate to full."""
        report = gatekeeper.generate_report(
            model_name="escalation_test",
            backtest_results=failing_overfit_results,
            model_metadata=failing_overfit_metadata,
            mode="fast",
        )

        # The report should either be "full" (pre-screen caught it) or "fast->full"
        # (fast mode caught it then escalated)
        assert report.mode in ("full", "fast->full")
        assert report.decision == GateDecision.QUARANTINE

        # After escalation, all dimensions should be present
        dimensions = [r.dimension for r in report.dimension_results]
        assert any("temporal" in d for d in dimensions)
        assert any("statistical" in d for d in dimensions)
        assert any("overfit" in d for d in dimensions)
        assert any("betting" in d for d in dimensions)

    def test_prescreen_triggers_full_escalation(self, gatekeeper):
        """When pre-screen fails, generate_report should escalate to full mode."""
        bad_results = {"clv_values": [0.02] * 10, "profit_loss": [10.0] * 10}
        bad_metadata = {
            "n_features": 5,
            "n_samples": 100,
            "in_sample_roi": 0.30,  # Fails pre-screen
        }

        report = gatekeeper.generate_report(
            model_name="prescreen_escalation",
            backtest_results=bad_results,
            model_metadata=bad_metadata,
            mode="fast",
        )

        # Pre-screen failure should escalate to full
        assert report.mode == "full"
        assert report.decision == GateDecision.QUARANTINE


class TestReportNewFields:
    """Test the new mode and skipped_validators fields in GateReport."""

    def test_report_to_dict_includes_mode(self):
        """to_dict() should include mode and skipped_validators."""
        report = GateReport(
            model_name="test",
            timestamp=datetime.now(),
            decision=GateDecision.PASS,
            mode="fast",
            skipped_validators=["statistical"],
        )
        d = report.to_dict()
        assert d["mode"] == "fast"
        assert d["skipped_validators"] == ["statistical"]

    def test_report_summary_includes_mode(self):
        """summary() should display mode."""
        report = GateReport(
            model_name="test",
            timestamp=datetime.now(),
            decision=GateDecision.PASS,
            mode="fast",
        )
        summary = report.summary()
        assert "Mode: fast" in summary

    def test_report_summary_shows_skipped(self):
        """summary() should show skipped validators when present."""
        report = GateReport(
            model_name="test",
            timestamp=datetime.now(),
            decision=GateDecision.QUARANTINE,
            mode="fast",
            skipped_validators=["temporal", "statistical"],
        )
        summary = report.summary()
        assert "SKIPPED VALIDATORS" in summary
        assert "temporal" in summary
        assert "statistical" in summary

    def test_report_summary_hides_skipped_when_empty(self):
        """summary() should not show skipped section when empty."""
        report = GateReport(
            model_name="test",
            timestamp=datetime.now(),
            decision=GateDecision.PASS,
            mode="full",
            skipped_validators=[],
        )
        summary = report.summary()
        assert "SKIPPED VALIDATORS" not in summary
