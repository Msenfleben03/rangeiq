"""Backtesting Framework for Sports Betting Models.

This module provides tools for rigorous evaluation of betting models:

- Walk-Forward Validation: Time-series aware cross-validation that prevents
  look-ahead bias (the #1 cause of inflated backtest performance)

- Metrics: Comprehensive metrics including CLV (the PRIMARY success indicator),
  ROI, Brier score for calibration, and risk-adjusted returns

- Simulation: Monte Carlo simulation for bankroll projections, drawdown analysis,
  and Kelly criterion validation

Example Usage:
    ```python
    from backtesting import (
        WalkForwardValidator,
        SeasonalWalkForwardValidator,
        compute_all_metrics,
        MonteCarloSimulator,
        SimulationConfig,
    )

    # Walk-forward validation
    validator = WalkForwardValidator(
        train_window_days=180,
        test_window_days=30,
        step_days=30
    )

    for window in validator.split(df, date_column='game_date'):
        train = df.iloc[window.train_indices]
        test = df.iloc[window.test_indices]
        # Train and evaluate...

    # Compute metrics from backtest results
    metrics = compute_all_metrics(results_df)
    print(f"CLV: {metrics.avg_clv:.2%}")  # THE key metric
    print(f"ROI: {metrics.roi:.2%}")

    # Monte Carlo simulation
    simulator = MonteCarloSimulator(
        win_probability=0.54,
        avg_odds=-110,
        config=SimulationConfig(n_simulations=10000)
    )
    sim_results = simulator.run()
    print(f"Expected ROI: {sim_results.expected_value / 5000 - 1:.1%}")
    ```

Key Principles:
    1. CLV > Win Rate: Closing Line Value is the primary success metric
    2. No Look-Ahead: Always use .shift(1) after rolling calculations
    3. Time-Series CV: Never use random k-fold for betting data
    4. Understand Variance: Use Monte Carlo to set realistic expectations
"""

from backtesting.walk_forward import (
    WalkForwardValidator,
    WalkForwardWindow,
    WalkForwardResult,
    SeasonalWalkForwardValidator,
    create_lagged_features,
    detect_data_leakage,
    verify_temporal_integrity,
)

from backtesting.metrics import (
    BettingMetrics,
    calculate_roi,
    calculate_clv_metrics,
    calculate_brier_score,
    calculate_log_loss,
    calculate_calibration_error,
    calculate_sharpe_ratio,
    calculate_drawdown_metrics,
    calculate_streak_metrics,
    calculate_win_rate_by_confidence,
    compute_all_metrics,
    format_metrics_report,
)

from backtesting.simulation import (
    SimulationConfig,
    SimulationResult,
    MonteCarloSimulator,
    run_drawdown_analysis,
    calculate_risk_of_ruin,
    validate_kelly_fraction,
    calculate_confidence_intervals,
    simulate_from_backtest,
    format_simulation_report,
)

# Validators - CRITICAL for preventing leakage, overfitting, and betting-specific issues
from backtesting.validators import (
    # Temporal validation
    TemporalValidator,
    TemporalValidationResult,
    LeakageType,
    FeatureLeakageInfo,
    WalkForwardValidationResult,
    # Overfitting detection
    OverfitValidator,
    OverfitValidation,
    quick_overfit_check,
    # Betting-specific validation (CLV, vig, line availability)
    BettingValidator,
    BettingValidation,
    VigAnalysis,
    LineAvailabilityResult,
    ValidationSeverity,
    ValidationIssue,
    format_validation_report,
    # Statistical validation (anti-noise enforcement)
    StatisticalValidator,
    StatisticalValidation,
    StatisticalValidationResult,
    DrawdownAnalysis,
    MonteCarloRuinResult,
    # Gatekeeper - FINAL VALIDATION GATE (Master pipeline)
    Gatekeeper,
    GateDecision,
    GateReport,
    ValidationResult,
)


__all__ = [
    # Walk-forward validation
    "WalkForwardValidator",
    "WalkForwardWindow",
    "WalkForwardResult",
    "SeasonalWalkForwardValidator",
    "create_lagged_features",
    "detect_data_leakage",
    "verify_temporal_integrity",
    # Metrics
    "BettingMetrics",
    "calculate_roi",
    "calculate_clv_metrics",
    "calculate_brier_score",
    "calculate_log_loss",
    "calculate_calibration_error",
    "calculate_sharpe_ratio",
    "calculate_drawdown_metrics",
    "calculate_streak_metrics",
    "calculate_win_rate_by_confidence",
    "compute_all_metrics",
    "format_metrics_report",
    # Simulation
    "SimulationConfig",
    "SimulationResult",
    "MonteCarloSimulator",
    "run_drawdown_analysis",
    "calculate_risk_of_ruin",
    "validate_kelly_fraction",
    "calculate_confidence_intervals",
    "simulate_from_backtest",
    "format_simulation_report",
    # Validators - Temporal
    "TemporalValidator",
    "TemporalValidationResult",
    # Validators - Overfitting
    "OverfitValidator",
    "OverfitValidation",
    "quick_overfit_check",
    # Validators - Betting-specific (THE KEY VALIDATOR)
    "BettingValidator",
    "BettingValidation",
    "VigAnalysis",
    "LineAvailabilityResult",
    "ValidationSeverity",
    "ValidationIssue",
    "format_validation_report",
    # Statistical validation
    "StatisticalValidator",
    "StatisticalValidation",
    "StatisticalValidationResult",
    "DrawdownAnalysis",
    "MonteCarloRuinResult",
    # Gatekeeper - FINAL VALIDATION GATE (Master pipeline)
    "Gatekeeper",
    "GateDecision",
    "GateReport",
    "ValidationResult",
    # Additional temporal validation types
    "LeakageType",
    "FeatureLeakageInfo",
    "WalkForwardValidationResult",
]
