"""Backtesting Validators Module - 5-Dimension Validation Framework.

This module provides a comprehensive validation framework ensuring no sports betting
model reaches production without rigorous testing. The framework catches data leakage,
insufficient evidence, overfitting, and unrealistic betting assumptions.

Validation Pipeline:
    Raw Model -> [TEMPORAL] -> [STATISTICAL] -> [OVERFIT] -> [BETTING] -> [GATEKEEPER] -> PASS/QUARANTINE

The 5 Validators:
    - TemporalValidator (26 tests): Prevents look-ahead bias (THE MOST CRITICAL CHECK)
    - StatisticalValidator (49 tests): Sample size, Sharpe ratio, significance testing
    - OverfitValidator (42 tests): Detects overfitting patterns that inflate results
    - BettingValidator (52 tests): Domain-specific CLV, vig, Kelly, line availability
    - Gatekeeper (29 tests): FINAL VALIDATION GATE - Aggregates all checks, makes decision

Total: 198 tests

Blocking Check Thresholds (ALL must pass for deployment):
    - temporal_no_leakage: 0 leaky features detected
    - statistical_sample_size: >= 200 bets
    - statistical_sharpe: >= 0.5
    - overfit_in_sample_roi: <= 15%
    - betting_clv_threshold: >= 1.5%
    - betting_ruin_probability: <= 5%

Gate Decisions:
    - PASS: All blocking checks pass - model approved for deployment
    - QUARANTINE: Any blocking check fails - model needs review/fixes
    - NEEDS_REVIEW: All pass but multiple warnings or edge cases

Key Principles:
    1. CLV > Win Rate: Closing Line Value is the PRIMARY success metric
    2. Lines must exist: Cannot bet lines that were not available
    3. Vig is real: -110 baseline must be modeled
    4. Kelly limits: Bet sizing must respect bankroll rules (max 3%)
    5. No model reaches production without passing the Gatekeeper

Quick Start:
    ```python
    # THE MAIN ENTRY POINT - Gatekeeper runs all validators
    from backtesting.validators import Gatekeeper, GateDecision

    gatekeeper = Gatekeeper()
    gatekeeper.load_validators()

    report = gatekeeper.generate_report(
        model_name="ncaab_elo_v1",
        backtest_results={
            "profit_loss": [...],
            "stake": [...],
            "clv_values": [...],
            "game_date": [...]
        },
        model_metadata={
            "n_features": 10,
            "n_samples": 500,
            "in_sample_roi": 0.06
        }
    )

    if report.decision == GateDecision.PASS:
        print("Model approved for deployment!")
    elif report.decision == GateDecision.QUARANTINE:
        print(f"Model quarantined: {report.blocking_failures}")
        gatekeeper.quarantine_model("ncaab_elo_v1", report)
        print(gatekeeper.explain_failure(report))
    ```

Individual Validator Usage:
    ```python
    # Temporal validation - check for data leakage
    from backtesting.validators import TemporalValidator
    temporal = TemporalValidator()
    result = temporal.full_validation(df, feature_cols, target_col, date_col)

    # Statistical validation - check sample size and significance
    from backtesting.validators import StatisticalValidator
    statistical = StatisticalValidator(min_sample_size=200, min_sharpe=0.5)
    result = statistical.validate(backtest_df, model_metadata)

    # Overfit validation - check for overfitting red flags
    from backtesting.validators import OverfitValidator, quick_overfit_check
    passes, warnings = quick_overfit_check(n_features=10, n_samples=500, in_sample_roi=0.08)

    # Betting validation - check CLV, vig, Kelly limits
    from backtesting.validators import BettingValidator
    betting = BettingValidator(min_clv=0.015)
    result = betting.full_validation(backtest_results)
    ```

See Also:
    - backtesting/validators/README.md for full documentation
    - CLAUDE.md for project context and usage examples
    - tests/test_*_validator.py for test examples
"""

from backtesting.validators.temporal_validator import (
    TemporalValidator,
    TemporalValidationResult,
    LeakageType,
    FeatureLeakageInfo,
    WalkForwardValidationResult,
)

from backtesting.validators.overfit_validator import (
    OverfitValidation,
    OverfitValidator,
    quick_overfit_check,
)

from backtesting.validators.betting_validator import (
    BettingValidator,
    BettingValidation,
    VigAnalysis,
    LineAvailabilityResult,
    ValidationSeverity,
    ValidationIssue,
    format_validation_report,
)

from backtesting.validators.statistical_validator import (
    StatisticalValidator,
    StatisticalValidation,
    StatisticalValidationResult,
    DrawdownAnalysis,
    MonteCarloRuinResult,
)

from backtesting.validators.gatekeeper import (
    Gatekeeper,
    GateDecision,
    GateReport,
    ValidationResult,
)

__all__ = [
    # Temporal validation (26 tests)
    "TemporalValidator",
    "TemporalValidationResult",
    "LeakageType",
    "FeatureLeakageInfo",
    "WalkForwardValidationResult",
    # Overfit validation (42 tests)
    "OverfitValidation",
    "OverfitValidator",
    "quick_overfit_check",
    # Betting validation (52 tests)
    "BettingValidator",
    "BettingValidation",
    "VigAnalysis",
    "LineAvailabilityResult",
    "ValidationSeverity",
    "ValidationIssue",
    "format_validation_report",
    # Statistical validation (49 tests)
    "StatisticalValidator",
    "StatisticalValidation",
    "StatisticalValidationResult",
    "DrawdownAnalysis",
    "MonteCarloRuinResult",
    # Gatekeeper - Final validation gate (29 tests)
    "Gatekeeper",
    "GateDecision",
    "GateReport",
    "ValidationResult",
]
