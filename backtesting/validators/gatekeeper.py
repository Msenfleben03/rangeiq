"""Gatekeeper - Final Validation Gate for Model Deployment.

This module implements the final validation gate that aggregates all dimension
checks and makes the PASS/QUARANTINE decision. No model reaches production
without passing the gatekeeper.

The Gatekeeper is the LAST LINE OF DEFENSE against:
    - Data leakage (temporal validator)
    - Insufficient statistical evidence (statistical validator)
    - Overfitting (overfit validator)
    - Unrealistic betting assumptions (betting validator)

Decision Logic:
    - PASS: All blocking checks pass, model is ready for deployment
    - QUARANTINE: Any blocking check fails, model needs review/fixes
    - NEEDS_REVIEW: No blocking failures but multiple warnings

Example:
    ```python
    from backtesting.validators import Gatekeeper, GateDecision

    gatekeeper = Gatekeeper()
    gatekeeper.load_validators()

    report = gatekeeper.generate_report(
        model_name="ncaab_elo_v1",
        backtest_results=results_df.to_dict(),
        model_metadata=metadata
    )

    if report.decision == GateDecision.PASS:
        print("Model approved for deployment!")
    else:
        print(f"Model quarantined: {report.blocking_failures}")
        gatekeeper.quarantine_model("ncaab_elo_v1", report)
    ```
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import json
import math

import pandas as pd


class GateDecision(Enum):
    """Final gate decision for model deployment."""

    PASS = "PASS"
    QUARANTINE = "QUARANTINE"
    NEEDS_REVIEW = "NEEDS_REVIEW"


@dataclass
class ValidationResult:
    """Result from a single dimension validation.

    Attributes:
        dimension: Name of the validation dimension
        passed: Whether this dimension's checks passed
        details: Detailed results from the validator
        failure_reason: Human-readable failure explanation
    """

    dimension: str
    passed: bool
    details: Dict[str, Any] = field(default_factory=dict)
    failure_reason: Optional[str] = None


@dataclass
class GateReport:
    """Complete gate validation report.

    This is the final output documenting why a model was approved or rejected.

    Attributes:
        model_name: Name/identifier of the model being validated
        timestamp: When the validation was performed
        decision: Final PASS/QUARANTINE/NEEDS_REVIEW decision
        dimension_results: Results from each validation dimension
        overall_score: Percentage of checks passed (0-1)
        blocking_failures: List of blocking checks that failed
        warnings: List of non-blocking warnings
        recommendations: Suggested actions based on results
        human_review_required: Whether manual review is needed
    """

    model_name: str
    timestamp: datetime
    decision: GateDecision
    dimension_results: List[ValidationResult] = field(default_factory=list)
    overall_score: float = 0.0
    blocking_failures: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    human_review_required: bool = False
    mode: str = "full"
    skipped_validators: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "model_name": self.model_name,
            "timestamp": self.timestamp.isoformat(),
            "decision": self.decision.value,
            "overall_score": self.overall_score,
            "blocking_failures": self.blocking_failures,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "human_review_required": self.human_review_required,
            "mode": self.mode,
            "skipped_validators": self.skipped_validators,
            "dimension_results": [
                {
                    "dimension": r.dimension,
                    "passed": r.passed,
                    "failure_reason": r.failure_reason,
                    "details": r.details,
                }
                for r in self.dimension_results
            ],
        }

    def summary(self) -> str:
        """Generate human-readable summary of the gate report."""
        lines = [
            "=" * 70,
            f"GATE VALIDATION REPORT: {self.model_name}",
            "=" * 70,
            "",
            f"Decision: {self.decision.value}",
            f"Mode: {self.mode}",
            f"Timestamp: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Overall Score: {self.overall_score:.1%}",
            f"Human Review Required: {'Yes' if self.human_review_required else 'No'}",
            "",
            "DIMENSION RESULTS:",
            "-" * 40,
        ]

        for result in self.dimension_results:
            status = "PASS" if result.passed else "FAIL"
            lines.append(f"  [{status}] {result.dimension}")
            if result.failure_reason:
                lines.append(f"        Reason: {result.failure_reason}")

        if self.blocking_failures:
            lines.extend(["", "BLOCKING FAILURES:", "-" * 40])
            for failure in self.blocking_failures:
                lines.append(f"  - {failure}")

        if self.warnings:
            lines.extend(["", "WARNINGS:", "-" * 40])
            for warning in self.warnings:
                lines.append(f"  - {warning}")

        if self.recommendations:
            lines.extend(["", "RECOMMENDATIONS:", "-" * 40])
            for rec in self.recommendations:
                lines.append(f"  - {rec}")

        if self.skipped_validators:
            lines.extend(["", "SKIPPED VALIDATORS (early termination):", "-" * 40])
            for skipped in self.skipped_validators:
                lines.append(f"  - {skipped}")

        lines.append("")
        lines.append("=" * 70)

        return "\n".join(lines)


class Gatekeeper:
    """Final validation gate - aggregates all dimension checks.

    The Gatekeeper is responsible for:
    1. Loading and coordinating all dimension validators
    2. Running comprehensive validation across all dimensions
    3. Making the final PASS/QUARANTINE decision
    4. Generating detailed reports for audit trail
    5. Persisting decisions to memory for future reference

    BLOCKING_CHECKS must ALL pass for deployment approval.
    Any single blocking failure results in QUARANTINE.

    Example:
        ```python
        gatekeeper = Gatekeeper()
        gatekeeper.load_validators()

        # Run full validation
        report = gatekeeper.generate_report(
            model_name="ncaab_elo_v1",
            backtest_results={"profit_loss": [...], "stake": [...]},
            model_metadata={"n_features": 10, "n_samples": 500}
        )

        print(report.summary())

        if report.decision == GateDecision.QUARANTINE:
            gatekeeper.quarantine_model("ncaab_elo_v1", report)
        ```
    """

    # ALL must pass for deployment - these are non-negotiable
    BLOCKING_CHECKS = [
        "temporal_no_leakage",
        "statistical_sample_size",
        "statistical_sharpe",
        "overfit_in_sample_roi",
        "betting_clv_threshold",
        "betting_ruin_probability",
    ]

    # Thresholds for blocking checks
    THRESHOLDS = {
        "min_sample_size": 200,
        "min_sharpe": 0.5,
        "max_in_sample_roi": 0.15,
        "min_clv": 0.015,
        "max_ruin_probability": 0.05,
    }

    def __init__(self):
        """Initialize the Gatekeeper with null validators."""
        self.temporal_validator = None
        self.statistical_validator = None
        self.overfit_validator = None
        self.betting_validator = None
        self._validators_loaded = False

    def load_validators(self):
        """Import and initialize all dimension validators.

        Call this before running validations to ensure all validators
        are available.
        """
        from backtesting.validators.temporal_validator import TemporalValidator
        from backtesting.validators.statistical_validator import StatisticalValidator
        from backtesting.validators.overfit_validator import OverfitValidator
        from backtesting.validators.betting_validator import BettingValidator

        self.temporal_validator = TemporalValidator()
        self.statistical_validator = StatisticalValidator(
            min_sample_size=self.THRESHOLDS["min_sample_size"],
            min_sharpe=self.THRESHOLDS["min_sharpe"],
        )
        self.overfit_validator = OverfitValidator()
        self.betting_validator = BettingValidator(
            min_clv=self.THRESHOLDS["min_clv"],
        )

        self._validators_loaded = True

    def _ensure_validators_loaded(self):
        """Ensure validators are loaded before use."""
        if not self._validators_loaded:
            self.load_validators()

    def _quick_prescreen(
        self,
        backtest_results: Dict[str, Any],
        model_metadata: Dict[str, Any],
    ) -> Optional[List[str]]:
        """Run instant arithmetic pre-screen before any validator.

        Checks 3 cheap conditions that catch ~40% of bad models immediately:
        1. in_sample_roi <= 15% (overfit threshold)
        2. n_features <= sqrt(n_samples) (feature count rule)
        3. Sample size >= 200 bets (minimum for statistical validity)

        Args:
            backtest_results: Dictionary with backtest data.
            model_metadata: Dictionary with model information.

        Returns:
            None if pre-screen passes, or a list of failure reasons if it fails.
        """
        failures = []

        in_sample_roi = model_metadata.get("in_sample_roi", 0.0)
        if in_sample_roi > self.THRESHOLDS["max_in_sample_roi"]:
            failures.append(
                f"Pre-screen: in_sample_roi {in_sample_roi:.1%} > "
                f"{self.THRESHOLDS['max_in_sample_roi']:.1%} threshold"
            )

        n_features = model_metadata.get("n_features", 0)
        n_samples = model_metadata.get("n_samples", 0)
        if n_samples > 0 and n_features > math.sqrt(n_samples):
            max_features = int(math.sqrt(n_samples))
            failures.append(
                f"Pre-screen: n_features {n_features} > sqrt({n_samples}) = {max_features}"
            )

        clv_values = backtest_results.get("clv_values", [])
        if not clv_values and "clv" in backtest_results:
            clv_values = (
                backtest_results["clv"]
                if isinstance(backtest_results["clv"], list)
                else list(backtest_results["clv"])
            )
        sample_size = (
            len(clv_values) if clv_values else len(backtest_results.get("profit_loss", []))
        )
        if sample_size < self.THRESHOLDS["min_sample_size"]:
            failures.append(
                f"Pre-screen: sample_size {sample_size} < "
                f"{self.THRESHOLDS['min_sample_size']} minimum"
            )

        return failures if failures else None

    # Validators ordered by execution cost (cheapest first) for fast mode
    _VALIDATOR_ORDER_FAST = ["overfit", "betting", "temporal", "statistical"]

    def run_all_validations(
        self,
        backtest_results: Dict[str, Any],
        model_metadata: Dict[str, Any],
        mode: str = "full",
    ) -> Tuple[List[ValidationResult], List[str]]:
        """Execute all dimension validations.

        Args:
            backtest_results: Dictionary with backtest data including:
                - profit_loss: List/array of profit/loss per bet
                - stake: List/array of stake amounts
                - result: List of 'win'/'loss'/'push' strings
                - odds_placed: List of odds when bets placed
                - odds_closing: List of closing odds
                - clv_values: List of CLV values
                - game_date: List of game dates
            model_metadata: Dictionary with model info including:
                - n_features: Number of features
                - n_samples: Number of training samples
                - season_rois: List of ROI per season
                - in_sample_roi: In-sample ROI
            mode: "fast" for tiered early-termination, "full" for all
                validators regardless (default: "full").

        Returns:
            Tuple of (list of ValidationResult, list of skipped validator names)
        """
        self._ensure_validators_loaded()

        results = []
        skipped = []

        # Convert dict to DataFrame if needed for some validators
        df = None
        if isinstance(backtest_results, dict) and "profit_loss" in backtest_results:
            df = pd.DataFrame(backtest_results)
        elif isinstance(backtest_results, pd.DataFrame):
            df = backtest_results

        if mode == "full":
            # Original sequential order -- run everything unconditionally
            results.append(self._validate_temporal(df, model_metadata))
            results.append(self._validate_statistical(df, model_metadata))
            results.append(self._validate_overfit(backtest_results, model_metadata))
            results.append(self._validate_betting(backtest_results, model_metadata))
        else:
            # Fast mode: cheapest validators first, early termination
            validator_dispatch = {
                "overfit": lambda: self._validate_overfit(backtest_results, model_metadata),
                "betting": lambda: self._validate_betting(backtest_results, model_metadata),
                "temporal": lambda: self._validate_temporal(df, model_metadata),
                "statistical": lambda: self._validate_statistical(df, model_metadata),
            }

            for i, name in enumerate(self._VALIDATOR_ORDER_FAST):
                result = validator_dispatch[name]()
                results.append(result)

                # Early termination: if a blocking check failed, skip remaining validators
                if not result.passed and any(bc in result.dimension for bc in self.BLOCKING_CHECKS):
                    skipped.extend(self._VALIDATOR_ORDER_FAST[i + 1 :])
                    break

        # Dimension 5: Human Review Flag (always runs -- depends on prior results)
        review_result = self._check_human_review_needed(results, model_metadata)
        results.append(review_result)

        return results, skipped

    def _validate_temporal(
        self,
        df: Optional[pd.DataFrame],
        metadata: Dict[str, Any],
    ) -> ValidationResult:
        """Run temporal validation checks."""
        if df is None or len(df) == 0:
            return ValidationResult(
                dimension="temporal_no_leakage",
                passed=True,
                details={"note": "No data provided for temporal validation"},
            )

        try:
            result = self.temporal_validator.validate(df, metadata)
            # Check if any critical leakage was found
            has_leakage = len(result.leaky_features) > 0
            passed = result.passed and not has_leakage
            failure_reason = None

            if not passed:
                # Get failure reasons from leaky features
                reasons = [f.recommendation for f in result.leaky_features[:3]]
                if not reasons:
                    reasons = [result.report_summary[:200]]
                failure_reason = "; ".join(reasons)

            return ValidationResult(
                dimension="temporal_no_leakage",
                passed=passed,
                details={
                    "n_issues_found": result.n_issues_found,
                    "walk_forward_valid": result.walk_forward_valid,
                    "closing_line_valid": result.closing_line_valid,
                    "leaky_features": [f.feature_name for f in result.leaky_features],
                },
                failure_reason=failure_reason,
            )
        except Exception as e:
            return ValidationResult(
                dimension="temporal_no_leakage",
                passed=False,
                details={"error": str(e)},
                failure_reason=f"Temporal validation error: {str(e)}",
            )

    def _validate_statistical(
        self,
        df: Optional[pd.DataFrame],
        metadata: Dict[str, Any],
    ) -> ValidationResult:
        """Run statistical validation checks."""
        if df is None or len(df) == 0:
            return ValidationResult(
                dimension="statistical_sample_size",
                passed=False,
                details={"note": "No data provided"},
                failure_reason="No backtest data provided for statistical validation",
            )

        try:
            result = self.statistical_validator.validate(df, metadata)

            # We check both sample size AND sharpe as blocking
            sample_ok = result.sample_size_adequate
            sharpe_ok = result.sharpe_adequate

            passed = sample_ok and sharpe_ok
            failure_reasons = []

            if not sample_ok:
                failure_reasons.append(
                    f"Sample size {result.details.get('sample_size', {}).get('n_bets', 0)} "
                    f"< {self.THRESHOLDS['min_sample_size']}"
                )
            if not sharpe_ok:
                sharpe_val = result.details.get("sharpe", {}).get("sharpe", 0)
                failure_reasons.append(
                    f"Sharpe ratio {sharpe_val:.2f} < {self.THRESHOLDS['min_sharpe']}"
                )

            return ValidationResult(
                dimension="statistical_sample_size",
                passed=passed,
                details=result.details,
                failure_reason="; ".join(failure_reasons) if failure_reasons else None,
            )
        except Exception as e:
            return ValidationResult(
                dimension="statistical_sample_size",
                passed=False,
                details={"error": str(e)},
                failure_reason=f"Statistical validation error: {str(e)}",
            )

    def _validate_overfit(
        self,
        backtest_results: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> ValidationResult:
        """Run overfitting validation checks."""
        try:
            # Prepare data for overfit validator
            overfit_data = {
                "in_sample_roi": metadata.get("in_sample_roi", 0.0),
                "season_rois": backtest_results.get("season_rois", metadata.get("season_rois", [])),
            }

            result = self.overfit_validator.full_validation(overfit_data, metadata)

            # Blocking check: in-sample ROI must not be suspiciously high
            passed = not result.in_sample_too_good and result.variance_passes

            failure_reasons = []
            if result.in_sample_too_good:
                failure_reasons.append(
                    f"In-sample ROI {result.in_sample_roi:.1%} exceeds "
                    f"{self.THRESHOLDS['max_in_sample_roi']:.1%} threshold (suspicious)"
                )
            if not result.variance_passes:
                failure_reasons.append(
                    f"Cross-season variance {result.cross_season_variance:.1%} too high"
                )

            return ValidationResult(
                dimension="overfit_in_sample_roi",
                passed=passed,
                details={
                    "in_sample_roi": result.in_sample_roi,
                    "in_sample_too_good": result.in_sample_too_good,
                    "cross_season_variance": result.cross_season_variance,
                    "feature_count": result.feature_count,
                    "max_features": result.max_allowed_features,
                    "overall_passes": result.overall_passes,
                },
                failure_reason="; ".join(failure_reasons) if failure_reasons else None,
            )
        except Exception as e:
            return ValidationResult(
                dimension="overfit_in_sample_roi",
                passed=False,
                details={"error": str(e)},
                failure_reason=f"Overfit validation error: {str(e)}",
            )

    def _validate_betting(
        self,
        backtest_results: Dict[str, Any],
        metadata: Dict[str, Any],
    ) -> ValidationResult:
        """Run betting-specific validation checks."""
        try:
            # Prepare data for betting validator
            clv_values = backtest_results.get("clv_values", [])
            if not clv_values and "clv" in backtest_results:
                clv_values = (
                    backtest_results["clv"]
                    if isinstance(backtest_results["clv"], list)
                    else backtest_results["clv"].tolist()
                )

            betting_data = {
                "clv_values": clv_values,
                "season_labels": backtest_results.get("season_labels"),
                "config": metadata.get("config", {"assumed_vig": -110}),
                "bet_sizes": backtest_results.get("stake", []),
                "bankroll": metadata.get("bankroll", 5000),
            }

            result = self.betting_validator.full_validation(betting_data)

            # Blocking checks: CLV threshold and realistic vig
            passed = result.clv_passes and result.realistic_vig

            failure_reasons = []
            if not result.clv_passes:
                failure_reasons.append(
                    f"CLV {result.clv_mean:.2%} below {self.THRESHOLDS['min_clv']:.2%} threshold"
                )
            if not result.realistic_vig:
                failure_reasons.append("Unrealistic vig assumptions in backtest")

            # Also check ruin probability from betting details
            ruin_prob = result.details.get("ruin_probability", 0.0)
            if ruin_prob > self.THRESHOLDS["max_ruin_probability"]:
                passed = False
                failure_reasons.append(
                    f"Ruin probability {ruin_prob:.1%} exceeds "
                    f"{self.THRESHOLDS['max_ruin_probability']:.1%}"
                )

            return ValidationResult(
                dimension="betting_clv_threshold",
                passed=passed,
                details={
                    "clv_mean": result.clv_mean,
                    "clv_passes": result.clv_passes,
                    "realistic_vig": result.realistic_vig,
                    "lines_available": result.lines_were_available,
                    "kelly_limits_ok": result.kelly_respects_limits,
                    "overall_valid": result.overall_valid,
                },
                failure_reason="; ".join(failure_reasons) if failure_reasons else None,
            )
        except Exception as e:
            return ValidationResult(
                dimension="betting_clv_threshold",
                passed=False,
                details={"error": str(e)},
                failure_reason=f"Betting validation error: {str(e)}",
            )

    def _check_human_review_needed(
        self,
        validation_results: List[ValidationResult],
        metadata: Dict[str, Any],
    ) -> ValidationResult:
        """Determine if human review is required based on results and context."""
        warnings = []
        review_needed = False

        # Count warnings (passed but with concerns)
        warning_count = sum(
            1 for r in validation_results if r.passed and r.details.get("warning", False)
        )

        if warning_count >= 2:
            review_needed = True
            warnings.append(f"{warning_count} dimensions have warnings")

        # Check for edge cases that need human judgment
        for result in validation_results:
            # Near-threshold values
            if "sharpe" in result.details:
                sharpe = result.details.get("sharpe", {}).get("sharpe", 0)
                if sharpe and 0.4 < sharpe < 0.6:
                    review_needed = True
                    warnings.append(f"Sharpe ratio {sharpe:.2f} near threshold")

            if "clv_mean" in result.details:
                clv = result.details.get("clv_mean", 0)
                if 0.01 < clv < 0.02:
                    review_needed = True
                    warnings.append(f"CLV {clv:.2%} near threshold")

        # Novel model types always need review
        model_type = metadata.get("model_type", "")
        if "new" in model_type.lower() or "experimental" in model_type.lower():
            review_needed = True
            warnings.append("Experimental/new model type requires review")

        return ValidationResult(
            dimension="human_review_flag",
            passed=True,  # This dimension doesn't block
            details={
                "review_needed": review_needed,
                "warning_count": warning_count,
                "review_reasons": warnings,
            },
            failure_reason=None,
        )

    def make_decision(self, validation_results: List[ValidationResult]) -> GateDecision:
        """PASS only if ALL blocking checks pass.

        Decision logic:
        - QUARANTINE: Any blocking check fails
        - NEEDS_REVIEW: All pass but multiple warnings or edge cases
        - PASS: All blocking checks pass, no major concerns

        Args:
            validation_results: List of ValidationResult from all dimensions

        Returns:
            GateDecision enum value
        """
        # Check for any blocking failures
        blocking_failures = []
        for result in validation_results:
            if not result.passed:
                # Check if this is a blocking dimension
                for blocking_check in self.BLOCKING_CHECKS:
                    if blocking_check in result.dimension.lower():
                        blocking_failures.append(result.dimension)
                        break

        if blocking_failures:
            return GateDecision.QUARANTINE

        # Check if human review is flagged
        for result in validation_results:
            if result.dimension == "human_review_flag":
                if result.details.get("review_needed", False):
                    return GateDecision.NEEDS_REVIEW

        # Count warnings across all dimensions
        total_warnings = sum(
            len(r.details.get("warnings", []))
            for r in validation_results
            if isinstance(r.details.get("warnings"), list)
        )

        if total_warnings >= 3:
            return GateDecision.NEEDS_REVIEW

        return GateDecision.PASS

    def generate_report(
        self,
        model_name: str,
        backtest_results: Dict[str, Any],
        model_metadata: Dict[str, Any],
        mode: str = "fast",
    ) -> GateReport:
        """Full validation pipeline with comprehensive report.

        This is the main entry point for validating a model before deployment.
        It runs all dimension validations, makes the final decision, and
        generates a detailed report.

        Args:
            model_name: Identifier for the model being validated
            backtest_results: Dictionary with backtest data
            model_metadata: Dictionary with model information
            mode: "fast" for tiered early-termination (default), "full" to
                run every validator regardless. On QUARANTINE in fast mode,
                auto-escalates to full to capture all failures.

        Returns:
            GateReport with complete validation results and decision
        """
        self._ensure_validators_loaded()

        effective_mode = mode
        skipped: List[str] = []

        if mode == "fast":
            # Pre-screen: instant arithmetic checks before any validator
            prescreen_failures = self._quick_prescreen(backtest_results, model_metadata)
            if prescreen_failures is not None:
                # Obvious failure -- build a minimal QUARANTINE report, then
                # auto-escalate to full mode for complete diagnostics.
                effective_mode = "full"
                dimension_results, skipped = self.run_all_validations(
                    backtest_results,
                    model_metadata,
                    mode="full",
                )
            else:
                # Pre-screen passed -- run tiered validators with early exit
                dimension_results, skipped = self.run_all_validations(
                    backtest_results,
                    model_metadata,
                    mode="fast",
                )

                # Auto-escalate: if fast mode quarantines, re-run full to
                # capture ALL failures for the quarantine report.
                preliminary_decision = self.make_decision(dimension_results)
                if preliminary_decision == GateDecision.QUARANTINE and skipped:
                    dimension_results, skipped = self.run_all_validations(
                        backtest_results,
                        model_metadata,
                        mode="full",
                    )
                    effective_mode = "fast->full"
        else:
            dimension_results, skipped = self.run_all_validations(
                backtest_results,
                model_metadata,
                mode="full",
            )

        # Make decision
        decision = self.make_decision(dimension_results)

        # Calculate overall score (% of checks passed)
        total_checks = len(dimension_results)
        passed_checks = sum(1 for r in dimension_results if r.passed)
        overall_score = passed_checks / total_checks if total_checks > 0 else 0.0

        # Collect blocking failures
        blocking_failures = [
            f"{r.dimension}: {r.failure_reason}"
            for r in dimension_results
            if not r.passed and any(bc in r.dimension for bc in self.BLOCKING_CHECKS)
        ]

        # Collect warnings
        warnings = []
        for result in dimension_results:
            if result.passed and result.details.get("warnings"):
                warnings.extend(result.details["warnings"])
            elif result.passed and result.failure_reason:
                warnings.append(result.failure_reason)

        # Generate recommendations
        recommendations = self._generate_recommendations(
            dimension_results, decision, model_metadata
        )

        # Check if human review required
        human_review = decision == GateDecision.NEEDS_REVIEW or any(
            r.dimension == "human_review_flag" and r.details.get("review_needed")
            for r in dimension_results
        )

        report = GateReport(
            model_name=model_name,
            timestamp=datetime.now(),
            decision=decision,
            dimension_results=dimension_results,
            overall_score=overall_score,
            blocking_failures=blocking_failures,
            warnings=warnings,
            recommendations=recommendations,
            human_review_required=human_review,
            mode=effective_mode,
            skipped_validators=skipped,
        )

        return report

    def _generate_recommendations(
        self,
        results: List[ValidationResult],
        decision: GateDecision,
        metadata: Dict[str, Any],
    ) -> List[str]:
        """Generate actionable recommendations based on validation results."""
        recommendations = []

        if decision == GateDecision.PASS:
            recommendations.append(
                "Model approved for deployment. Monitor live performance closely "
                "for first 100 bets."
            )
            return recommendations

        # Recommendations for each failed dimension
        for result in results:
            if not result.passed:
                if "temporal" in result.dimension:
                    recommendations.append(
                        "Review feature engineering for data leakage. "
                        "Ensure .shift(1) is applied after all rolling calculations."
                    )
                elif "statistical" in result.dimension:
                    if "sample" in result.failure_reason.lower():
                        recommendations.append(
                            f"Collect more data. Current sample is insufficient. "
                            f"Target: {self.THRESHOLDS['min_sample_size']} bets minimum."
                        )
                    if "sharpe" in result.failure_reason.lower():
                        recommendations.append(
                            "Improve risk-adjusted returns. Consider: "
                            "(1) Better bet selection, (2) Kelly sizing, "
                            "(3) Removing high-variance plays."
                        )
                elif "overfit" in result.dimension:
                    recommendations.append(
                        "Model shows signs of overfitting. Consider: "
                        "(1) Reduce features to sqrt(n) rule, "
                        "(2) Add regularization, (3) Use cross-validation."
                    )
                elif "betting" in result.dimension:
                    if "clv" in result.failure_reason.lower():
                        recommendations.append(
                            "CLV is below threshold. Focus on finding edges that "
                            "beat the closing line. CLV > Win Rate for long-term success."
                        )

        if decision == GateDecision.NEEDS_REVIEW:
            recommendations.append("Schedule review with senior analyst before deployment.")

        return recommendations

    def persist_to_memory(
        self,
        report: GateReport,
    ):
        """Store gate decision for audit trail.

        Persists the report to a local JSON file for future
        reference and audit purposes.

        Args:
            report: GateReport to persist
        """
        try:
            from pathlib import Path

            data_dir = Path(__file__).parent.parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)

            scorecard_file = data_dir / "model-scorecards.json"

            # Load existing or create new
            if scorecard_file.exists():
                with open(scorecard_file, "r", encoding="utf-8") as f:
                    scorecards = json.load(f)
            else:
                scorecards = {}

            scorecards[report.model_name] = report.to_dict()

            with open(scorecard_file, "w", encoding="utf-8") as f:
                json.dump(scorecards, f, indent=2, default=str)

            print(f"Report persisted to {scorecard_file}")

        except Exception as e:
            print(f"Warning: Could not persist report to memory: {e}")

    def quarantine_model(self, model_name: str, report: GateReport):
        """Move failed model to quarantine with root cause analysis.

        Quarantined models are stored with their failure details for
        future reference and to prevent accidental deployment.

        Args:
            model_name: Name of the model to quarantine
            report: GateReport with failure details
        """
        try:
            # Store in bias-registry for future reference
            quarantine_record = {
                "model_name": model_name,
                "quarantine_time": datetime.now().isoformat(),
                "decision": report.decision.value,
                "blocking_failures": report.blocking_failures,
                "root_causes": self._analyze_root_causes(report),
                "recommendations": report.recommendations,
            }

            # Persist to local file
            from pathlib import Path

            quarantine_dir = Path(__file__).parent.parent.parent / "data"
            quarantine_dir.mkdir(parents=True, exist_ok=True)

            quarantine_file = quarantine_dir / "quarantined-models.json"

            if quarantine_file.exists():
                with open(quarantine_file, "r", encoding="utf-8") as f:
                    quarantined = json.load(f)
            else:
                quarantined = {}

            quarantined[model_name] = quarantine_record

            with open(quarantine_file, "w", encoding="utf-8") as f:
                json.dump(quarantined, f, indent=2, default=str)

            print(f"Model '{model_name}' quarantined. Review failures before retry.")

        except Exception as e:
            print(f"Warning: Could not quarantine model: {e}")

    def _analyze_root_causes(self, report: GateReport) -> List[str]:
        """Analyze root causes of model failure."""
        root_causes = []

        for failure in report.blocking_failures:
            if "leakage" in failure.lower():
                root_causes.append("DATA_LEAKAGE: Future information is being used in predictions")
            elif "sample" in failure.lower():
                root_causes.append(
                    "INSUFFICIENT_DATA: Not enough bets to draw reliable conclusions"
                )
            elif "sharpe" in failure.lower():
                root_causes.append(
                    "POOR_RISK_ADJUSTED_RETURNS: Returns don't justify the risk taken"
                )
            elif "in_sample" in failure.lower() or "overfit" in failure.lower():
                root_causes.append(
                    "OVERFITTING: Model performs too well in-sample, likely won't generalize"
                )
            elif "clv" in failure.lower():
                root_causes.append("NO_EDGE: Model doesn't consistently beat the closing line")
            elif "vig" in failure.lower():
                root_causes.append(
                    "UNREALISTIC_ASSUMPTIONS: Backtest assumes better odds than available"
                )

        return root_causes if root_causes else ["UNKNOWN: Review detailed report"]

    def explain_failure(self, report: GateReport) -> str:
        """Generate human-readable explanation of why model failed.

        Args:
            report: GateReport with failure details

        Returns:
            Detailed explanation suitable for non-technical stakeholders
        """
        if report.decision == GateDecision.PASS:
            return "Model passed all validation checks and is approved for deployment."

        lines = [
            f"Model '{report.model_name}' was {report.decision.value}.",
            "",
            "WHY IT FAILED:",
            "-" * 40,
        ]

        root_causes = self._analyze_root_causes(report)
        for cause in root_causes:
            lines.append(f"  - {cause}")

        lines.extend(
            [
                "",
                "WHAT THIS MEANS:",
                "-" * 40,
            ]
        )

        if "DATA_LEAKAGE" in str(root_causes):
            lines.append(
                "  The model is using information that wouldn't be available at bet time. "
                "This creates artificially good results that won't hold up in live betting."
            )
        if "INSUFFICIENT_DATA" in str(root_causes):
            lines.append(
                "  We don't have enough bets to be confident the results aren't just luck. "
                "More data is needed before we can trust this model."
            )
        if "OVERFITTING" in str(root_causes):
            lines.append(
                "  The model has memorized the training data rather than learning patterns. "
                "It will likely fail when encountering new situations."
            )
        if "NO_EDGE" in str(root_causes):
            lines.append(
                "  The model isn't consistently beating the market's closing line. "
                "Without positive CLV, long-term profitability is unlikely."
            )

        lines.extend(
            [
                "",
                "NEXT STEPS:",
                "-" * 40,
            ]
        )
        for rec in report.recommendations:
            lines.append(f"  - {rec}")

        return "\n".join(lines)
