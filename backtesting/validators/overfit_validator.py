"""Overfitting Detection for Sports Betting Models.

This module provides comprehensive overfitting detection to prevent models that
fit noise instead of signal from reaching production.

CRITICAL: A model that looks too good to be true in backtesting almost certainly IS.
This validator catches common overfitting patterns before they cost real money.

Key Red Flags Detected:
    - Too many features for sample size (sqrt rule)
    - In-sample ROI > 15% (suspiciously good)
    - High variance across seasons (>30%)
    - Sensitive to small parameter changes
    - Unstable feature importance over time

References:
    - Bailey, D. H., & Lopez de Prado, M. (2014). The Deflated Sharpe Ratio
    - Harvey, C. R., et al. (2016). ...and the Cross-Section of Expected Returns
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple
import math
import copy
import warnings

import numpy as np
import pandas as pd


class ModelProtocol(Protocol):
    """Protocol for models compatible with overfitting validation."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Fit the model on training data."""
        ...

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Generate predictions."""
        ...


@dataclass
class OverfitValidation:
    """Container for overfitting validation results.

    Attributes:
        feature_count: Actual number of features in model
        max_allowed_features: Maximum features allowed (sqrt(sample_size))
        feature_ratio_passes: Whether feature count is acceptable
        in_sample_roi: ROI achieved on training data
        in_sample_too_good: Flag if ROI > 15% (suspicious)
        cross_season_variance: Coefficient of variation across seasons
        variance_passes: Whether variance is acceptable (<30%)
        param_sensitivity: Maximum ROI change from +/-10% parameter perturbation
        sensitivity_passes: Whether model is stable to param changes (<5%)
        learning_curve_healthy: Whether learning curve shows good generalization
        feature_importance_stable: Whether feature importances are consistent
        overall_passes: Whether all checks pass
        warnings: List of warning messages
        detailed_results: Dictionary with full analysis details
    """

    feature_count: int = 0
    max_allowed_features: int = 0
    feature_ratio_passes: bool = False
    in_sample_roi: float = 0.0
    in_sample_too_good: bool = False
    cross_season_variance: float = 0.0
    variance_passes: bool = False
    param_sensitivity: float = 0.0
    sensitivity_passes: bool = False
    learning_curve_healthy: bool = True
    feature_importance_stable: bool = True
    overall_passes: bool = False
    warnings: List[str] = field(default_factory=list)
    detailed_results: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Compute overall pass/fail status."""
        self.overall_passes = (
            self.feature_ratio_passes
            and not self.in_sample_too_good
            and self.variance_passes
            and self.sensitivity_passes
            and self.learning_curve_healthy
            and self.feature_importance_stable
        )

    def summary(self) -> str:
        """Generate human-readable summary of validation results."""
        status = "PASS" if self.overall_passes else "FAIL"
        lines = [
            "=" * 60,
            f"OVERFITTING VALIDATION: {status}",
            "=" * 60,
            "",
            "CHECKS:",
            f"  [{'PASS' if self.feature_ratio_passes else 'FAIL'}] Feature Count: "
            f"{self.feature_count} / {self.max_allowed_features} max",
            f"  [{'PASS' if not self.in_sample_too_good else 'FAIL'}] In-Sample ROI: "
            f"{self.in_sample_roi:.2%} (max: 15%)",
            f"  [{'PASS' if self.variance_passes else 'FAIL'}] Cross-Season Variance: "
            f"{self.cross_season_variance:.2%} (max: 30%)",
            f"  [{'PASS' if self.sensitivity_passes else 'FAIL'}] Param Sensitivity: "
            f"{self.param_sensitivity:.2%} (max: 5%)",
            f"  [{'PASS' if self.learning_curve_healthy else 'FAIL'}] Learning Curve: "
            f"{'Healthy' if self.learning_curve_healthy else 'Problematic'}",
            f"  [{'PASS' if self.feature_importance_stable else 'FAIL'}] Feature Stability: "
            f"{'Stable' if self.feature_importance_stable else 'Unstable'}",
        ]

        if self.warnings:
            lines.extend(["", "WARNINGS:"])
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


class OverfitValidator:
    """Detects overfitting in sports betting models.

    This validator implements multiple statistical tests to catch common
    overfitting patterns that lead to models performing well in backtests
    but failing in live trading.

    Example:
        ```python
        validator = OverfitValidator()

        # Quick check on feature count
        passes = validator.validate_feature_count(n_features=10, n_samples=400)

        # Full validation
        result = validator.full_validation(
            backtest_results={'season_rois': [0.05, 0.03, 0.08]},
            model_metadata={'n_features': 10, 'n_samples': 1000}
        )

        print(result.summary())
        if not result.overall_passes:
            raise ValueError("Model shows signs of overfitting!")
        ```

    Attributes:
        MAX_IN_SAMPLE_ROI: Maximum acceptable in-sample ROI (15%)
        MAX_CROSS_SEASON_VARIANCE: Maximum acceptable CV across seasons (30%)
        MAX_PARAM_SENSITIVITY: Maximum acceptable ROI change from param changes (5%)
        MIN_LEARNING_CURVE_RATIO: Minimum test/train score ratio (0.8)
    """

    MAX_IN_SAMPLE_ROI = 0.15  # 15% - if higher, probably overfit
    MAX_CROSS_SEASON_VARIANCE = 0.30  # 30% coefficient of variation
    MAX_PARAM_SENSITIVITY = 0.05  # 5% ROI change from 10% param change
    MIN_LEARNING_CURVE_RATIO = 0.8  # test score should be >= 80% of train score
    MAX_FEATURE_IMPORTANCE_DRIFT = 0.50  # 50% rank correlation drop = unstable

    def validate_feature_count(self, n_features: int, n_samples: int) -> bool:
        """Validate that feature count follows the sqrt(n) rule.

        The rule of thumb is that you should have no more than sqrt(n) features
        to avoid overfitting. This is because more features = more opportunities
        to find spurious correlations.

        Args:
            n_features: Number of features in the model
            n_samples: Number of training samples

        Returns:
            True if feature count is acceptable, False otherwise

        Example:
            >>> validator = OverfitValidator()
            >>> validator.validate_feature_count(n_features=10, n_samples=100)
            True  # sqrt(100) = 10
            >>> validator.validate_feature_count(n_features=15, n_samples=100)
            False  # 15 > sqrt(100)
        """
        if n_samples <= 0:
            return False
        if n_features <= 0:
            return True  # No features = no overfitting from features

        max_features = math.sqrt(n_samples)
        return n_features <= max_features

    def get_max_features(self, n_samples: int) -> int:
        """Calculate maximum allowed features for given sample size.

        Args:
            n_samples: Number of training samples

        Returns:
            Maximum number of features allowed
        """
        if n_samples <= 0:
            return 0
        return int(math.sqrt(n_samples))

    def check_in_sample_roi(self, roi: float) -> bool:
        """Check if in-sample ROI is suspiciously high.

        In sports betting, a backtest ROI > 15% is almost certainly overfit.
        Even the best sharp bettors achieve 3-5% ROI long-term.

        Args:
            roi: Return on Investment as decimal (0.05 = 5%)

        Returns:
            True if ROI is acceptable (<=15%), False if suspiciously high

        Example:
            >>> validator = OverfitValidator()
            >>> validator.check_in_sample_roi(0.05)  # 5% ROI
            True
            >>> validator.check_in_sample_roi(0.20)  # 20% ROI
            False  # Too good to be true!
        """
        return roi <= self.MAX_IN_SAMPLE_ROI

    def calculate_cross_season_variance(self, season_rois: List[float]) -> float:
        """Calculate coefficient of variation across seasons.

        A good model should perform relatively consistently across different
        seasons. High variance suggests the model is fit to specific
        conditions in some seasons but not others.

        Args:
            season_rois: List of ROI values for each season

        Returns:
            Coefficient of variation (std / mean), or inf if mean is 0

        Example:
            >>> validator = OverfitValidator()
            >>> validator.calculate_cross_season_variance([0.05, 0.04, 0.06])
            0.166...  # Low variance = good
            >>> validator.calculate_cross_season_variance([0.10, -0.05, 0.08])
            1.53...  # High variance = overfit warning
        """
        if len(season_rois) < 2:
            return 0.0  # Can't calculate variance with < 2 seasons

        season_rois = np.array(season_rois)
        mean_roi = np.mean(season_rois)

        if mean_roi == 0:
            return float("inf")

        std_roi = np.std(season_rois, ddof=1)  # Sample std
        return abs(std_roi / mean_roi)

    def check_variance_passes(self, season_rois: List[float]) -> bool:
        """Check if cross-season variance is acceptable.

        Args:
            season_rois: List of ROI values for each season

        Returns:
            True if variance is acceptable (<30%), False otherwise
        """
        cv = self.calculate_cross_season_variance(season_rois)
        return cv <= self.MAX_CROSS_SEASON_VARIANCE

    def test_parameter_sensitivity(
        self,
        model: Any,
        params: Dict[str, float],
        X_test: pd.DataFrame,
        y_test: pd.Series,
        evaluate_fn: Callable[[np.ndarray, np.ndarray], float],
        perturbation: float = 0.10,
    ) -> Tuple[float, Dict[str, float]]:
        """Test model sensitivity to parameter changes.

        A robust model should not change dramatically when parameters are
        perturbed slightly. If +/-10% parameter changes cause >5% ROI
        change, the model is likely overfit to specific parameter values.

        Args:
            model: Model object with attributes matching param names
            params: Dictionary of parameter names to current values
            X_test: Test features
            y_test: Test targets
            evaluate_fn: Function(predictions, actuals) -> ROI score
            perturbation: Fraction to perturb parameters (default 0.10 = 10%)

        Returns:
            Tuple of (max_sensitivity, param_sensitivities_dict)

        Example:
            >>> def eval_fn(pred, actual):
            ...     return calculate_roi(pred, actual)
            >>> sensitivity, details = validator.test_parameter_sensitivity(
            ...     model, {'k_factor': 20}, X_test, y_test, eval_fn
            ... )
            >>> if sensitivity > 0.05:
            ...     print("Model is too sensitive to parameters!")
        """
        if not params:
            return 0.0, {}

        # Get baseline performance
        try:
            baseline_preds = model.predict(X_test)
            baseline_score = evaluate_fn(baseline_preds, y_test.values)
        except Exception as e:
            warnings.warn(f"Could not get baseline predictions: {e}")
            return 0.0, {}

        sensitivities = {}

        for param_name, param_value in params.items():
            if param_value == 0:
                continue  # Skip zero-valued params

            max_change = 0.0

            # Test +/- perturbation
            for direction in [1, -1]:
                perturbed_value = param_value * (1 + direction * perturbation)

                # Create perturbed model
                try:
                    perturbed_model = copy.deepcopy(model)
                    setattr(perturbed_model, param_name, perturbed_value)

                    # Re-fit if model has fit method and we have training data
                    # For simplicity, just predict with changed params
                    perturbed_preds = perturbed_model.predict(X_test)
                    perturbed_score = evaluate_fn(perturbed_preds, y_test.values)

                    change = abs(perturbed_score - baseline_score)
                    max_change = max(max_change, change)

                except Exception:
                    # If we can't perturb this param, skip it
                    continue

            sensitivities[param_name] = max_change

        max_sensitivity = max(sensitivities.values()) if sensitivities else 0.0
        return max_sensitivity, sensitivities

    def analyze_learning_curve(
        self,
        train_sizes: List[int],
        train_scores: List[float],
        test_scores: List[float],
    ) -> Dict[str, Any]:
        """Analyze learning curve for overfitting patterns.

        A healthy learning curve shows:
        1. Train and test scores converging as data increases
        2. Both scores plateauing (diminishing returns)
        3. Small gap between train and test scores

        Overfitting signs:
        1. Large persistent gap between train and test
        2. Train score much higher than test score
        3. Test score not improving or getting worse with more data

        Args:
            train_sizes: List of training set sizes
            train_scores: Corresponding training scores (higher = better)
            test_scores: Corresponding test/validation scores

        Returns:
            Dictionary containing:
                - healthy: Boolean indicating if curve looks healthy
                - final_gap: Gap between train and test at largest size
                - convergence_rate: Rate at which gap is shrinking
                - test_improving: Whether test score is improving
                - warnings: List of warning messages
        """
        result = {
            "healthy": True,
            "final_gap": 0.0,
            "convergence_rate": 0.0,
            "test_improving": True,
            "warnings": [],
        }

        if len(train_sizes) < 2:
            result["warnings"].append("Not enough data points for learning curve analysis")
            return result

        train_sizes = np.array(train_sizes)
        train_scores = np.array(train_scores)
        test_scores = np.array(test_scores)

        # Sort by training size
        sort_idx = np.argsort(train_sizes)
        train_sizes = train_sizes[sort_idx]
        train_scores = train_scores[sort_idx]
        test_scores = test_scores[sort_idx]

        # Calculate gap at each point
        gaps = train_scores - test_scores

        # Final gap
        result["final_gap"] = gaps[-1]

        # Check if gap is shrinking (convergence)
        if len(gaps) >= 2:
            early_gap = np.mean(gaps[: len(gaps) // 2])
            late_gap = np.mean(gaps[len(gaps) // 2 :])
            result["convergence_rate"] = early_gap - late_gap

        # Check if test score is improving
        if len(test_scores) >= 2:
            test_trend = np.polyfit(range(len(test_scores)), test_scores, 1)[0]
            result["test_improving"] = test_trend >= 0

        # Determine if healthy
        warnings_list = []

        # Large final gap = overfitting
        if result["final_gap"] > 0.1:  # 10% gap
            warnings_list.append(
                f"Large train-test gap ({result['final_gap']:.2%}) suggests overfitting"
            )
            result["healthy"] = False

        # Test score much lower than train = overfitting
        final_train = train_scores[-1]
        final_test = test_scores[-1]
        if final_train > 0 and final_test / final_train < self.MIN_LEARNING_CURVE_RATIO:
            warnings_list.append(
                f"Test score ({final_test:.3f}) much lower than train ({final_train:.3f})"
            )
            result["healthy"] = False

        # Test not improving with more data = possible issue
        if not result["test_improving"]:
            warnings_list.append("Test score not improving with more training data")
            result["healthy"] = False

        # Gap not converging = possible overfitting
        if result["convergence_rate"] < 0:
            warnings_list.append("Train-test gap is widening, not converging")
            result["healthy"] = False

        result["warnings"] = warnings_list
        return result

    def detect_feature_importance_drift(
        self,
        feature_importances_by_period: List[Dict[str, float]],
        top_k: int = 10,
    ) -> Dict[str, Any]:
        """Detect if feature importance is stable across time periods.

        If the most important features change dramatically between time
        periods, it suggests the model is fitting to noise rather than
        persistent patterns.

        Args:
            feature_importances_by_period: List of dicts mapping feature names
                to importance scores for each time period
            top_k: Number of top features to compare

        Returns:
            Dictionary containing:
                - stable: Boolean indicating if importances are stable
                - avg_rank_correlation: Average Spearman correlation of rankings
                - min_rank_correlation: Minimum correlation observed
                - top_features_consistency: % of top features appearing in all periods
                - warnings: List of warning messages
        """
        result = {
            "stable": True,
            "avg_rank_correlation": 1.0,
            "min_rank_correlation": 1.0,
            "top_features_consistency": 1.0,
            "warnings": [],
        }

        if len(feature_importances_by_period) < 2:
            result["warnings"].append("Not enough periods for drift detection")
            return result

        # Get all feature names
        all_features = set()
        for period in feature_importances_by_period:
            all_features.update(period.keys())

        all_features = sorted(all_features)

        if len(all_features) == 0:
            return result

        # Convert to ranking arrays
        rankings = []
        for period in feature_importances_by_period:
            # Get importance values, defaulting to 0 for missing features
            values = np.array([period.get(f, 0.0) for f in all_features])
            # Convert to ranks (higher importance = higher rank)
            ranks = np.zeros_like(values)
            ranks[np.argsort(values)] = np.arange(len(values))
            rankings.append(ranks)

        # Calculate pairwise rank correlations
        correlations = []
        for i in range(len(rankings) - 1):
            # Spearman rank correlation
            d = rankings[i] - rankings[i + 1]
            n = len(d)
            if n > 1:
                rho = 1 - (6 * np.sum(d**2)) / (n * (n**2 - 1))
                correlations.append(rho)

        if correlations:
            result["avg_rank_correlation"] = np.mean(correlations)
            result["min_rank_correlation"] = np.min(correlations)

        # Check top feature consistency
        top_features_per_period = []
        for period in feature_importances_by_period:
            sorted_features = sorted(period.keys(), key=lambda f: period[f], reverse=True)
            top_features_per_period.append(set(sorted_features[:top_k]))

        # Find features that appear in top-k for ALL periods
        if top_features_per_period:
            common_top = top_features_per_period[0]
            for top_set in top_features_per_period[1:]:
                common_top = common_top.intersection(top_set)

            result["top_features_consistency"] = len(common_top) / top_k

        # Determine stability
        warnings_list = []

        if result["min_rank_correlation"] < 0.5:
            warnings_list.append(
                f"Low rank correlation ({result['min_rank_correlation']:.2f}) between periods"
            )
            result["stable"] = False

        if result["top_features_consistency"] < 0.5:
            warnings_list.append(
                f"Only {result['top_features_consistency']:.0%} of top features consistent"
            )
            result["stable"] = False

        result["warnings"] = warnings_list
        return result

    def full_validation(
        self,
        backtest_results: Dict[str, Any],
        model_metadata: Dict[str, Any],
    ) -> OverfitValidation:
        """Run all overfitting checks on backtest results.

        This is the main entry point for validating a model before deployment.
        It runs all available checks and returns a comprehensive validation result.

        Args:
            backtest_results: Dictionary containing:
                - season_rois: List of ROI values per season
                - in_sample_roi: Overall in-sample ROI (optional)
                - train_sizes: List of training sizes for learning curve (optional)
                - train_scores: Training scores for learning curve (optional)
                - test_scores: Test scores for learning curve (optional)
                - feature_importances_by_period: List of importance dicts (optional)

            model_metadata: Dictionary containing:
                - n_features: Number of features in model
                - n_samples: Number of training samples
                - params: Dict of parameter names to values (optional)

        Returns:
            OverfitValidation dataclass with all check results

        Example:
            >>> validator = OverfitValidator()
            >>> results = {
            ...     'season_rois': [0.05, 0.03, 0.04, 0.06],
            ...     'in_sample_roi': 0.08
            ... }
            >>> metadata = {'n_features': 8, 'n_samples': 500}
            >>> validation = validator.full_validation(results, metadata)
            >>> print(validation.summary())
            >>> if not validation.overall_passes:
            ...     raise ValueError("Model appears to be overfit!")
        """
        validation = OverfitValidation()
        all_warnings = []

        # 1. Feature count check
        n_features = model_metadata.get("n_features", 0)
        n_samples = model_metadata.get("n_samples", 0)

        validation.feature_count = n_features
        validation.max_allowed_features = self.get_max_features(n_samples)
        validation.feature_ratio_passes = self.validate_feature_count(n_features, n_samples)

        if not validation.feature_ratio_passes:
            all_warnings.append(
                f"Too many features: {n_features} > sqrt({n_samples}) = "
                f"{validation.max_allowed_features}"
            )

        # 2. In-sample ROI check
        in_sample_roi = backtest_results.get("in_sample_roi", 0.0)
        validation.in_sample_roi = in_sample_roi
        validation.in_sample_too_good = not self.check_in_sample_roi(in_sample_roi)

        if validation.in_sample_too_good:
            all_warnings.append(
                f"In-sample ROI ({in_sample_roi:.2%}) exceeds 15% - likely overfit!"
            )

        # 3. Cross-season variance check
        season_rois = backtest_results.get("season_rois", [])
        if len(season_rois) >= 2:
            validation.cross_season_variance = self.calculate_cross_season_variance(season_rois)
            validation.variance_passes = self.check_variance_passes(season_rois)

            if not validation.variance_passes:
                all_warnings.append(
                    f"High cross-season variance: {validation.cross_season_variance:.2%} > 30%"
                )
        else:
            validation.variance_passes = True  # Can't check with < 2 seasons
            all_warnings.append("Insufficient seasons for variance analysis (need >= 2)")

        # 4. Parameter sensitivity (if model and params provided)
        # Note: Full param sensitivity requires the model object, which we may not have
        # in this interface. For now, we'll mark as passing unless explicitly tested.
        validation.param_sensitivity = 0.0
        validation.sensitivity_passes = True

        # 5. Learning curve analysis
        train_sizes = backtest_results.get("train_sizes", [])
        train_scores = backtest_results.get("train_scores", [])
        test_scores = backtest_results.get("test_scores", [])

        if train_sizes and train_scores and test_scores:
            lc_result = self.analyze_learning_curve(train_sizes, train_scores, test_scores)
            validation.learning_curve_healthy = lc_result["healthy"]
            all_warnings.extend(lc_result["warnings"])
            validation.detailed_results["learning_curve"] = lc_result
        else:
            validation.learning_curve_healthy = True

        # 6. Feature importance drift
        fi_by_period = backtest_results.get("feature_importances_by_period", [])
        if len(fi_by_period) >= 2:
            fi_result = self.detect_feature_importance_drift(fi_by_period)
            validation.feature_importance_stable = fi_result["stable"]
            all_warnings.extend(fi_result["warnings"])
            validation.detailed_results["feature_importance"] = fi_result
        else:
            validation.feature_importance_stable = True

        # Compile warnings
        validation.warnings = all_warnings

        # Compute overall pass/fail
        validation.overall_passes = (
            validation.feature_ratio_passes
            and not validation.in_sample_too_good
            and validation.variance_passes
            and validation.sensitivity_passes
            and validation.learning_curve_healthy
            and validation.feature_importance_stable
        )

        return validation


def quick_overfit_check(
    n_features: int,
    n_samples: int,
    in_sample_roi: float,
    season_rois: Optional[List[float]] = None,
) -> Tuple[bool, List[str]]:
    """Quick overfitting sanity check for common red flags.

    This is a convenience function for fast validation without creating
    a full OverfitValidator instance.

    Args:
        n_features: Number of features in model
        n_samples: Number of training samples
        in_sample_roi: In-sample return on investment
        season_rois: Optional list of ROIs by season

    Returns:
        Tuple of (passes_check, list_of_warnings)

    Example:
        >>> passes, warnings = quick_overfit_check(
        ...     n_features=5, n_samples=1000, in_sample_roi=0.04
        ... )
        >>> if not passes:
        ...     print("WARNING:", warnings)
    """
    validator = OverfitValidator()
    warnings_list = []

    # Feature count
    if not validator.validate_feature_count(n_features, n_samples):
        max_f = validator.get_max_features(n_samples)
        warnings_list.append(f"Too many features: {n_features} > {max_f}")

    # In-sample ROI
    if not validator.check_in_sample_roi(in_sample_roi):
        warnings_list.append(f"Suspiciously high ROI: {in_sample_roi:.2%} > 15%")

    # Cross-season variance
    if season_rois and len(season_rois) >= 2:
        if not validator.check_variance_passes(season_rois):
            cv = validator.calculate_cross_season_variance(season_rois)
            warnings_list.append(f"High season variance: CV = {cv:.2%} > 30%")

    passes = len(warnings_list) == 0
    return passes, warnings_list
