# Backtesting Module Codemap

**Last Updated:** 2026-02-12
**Entry Point:** `backtesting/__init__.py`
**Test Coverage:** `tests/test_backtesting.py`, `tests/test_temporal_validator.py`,
`tests/test_statistical_validator.py`, `tests/test_overfit_validator.py`,
`tests/test_betting_validator.py`, `tests/test_gatekeeper.py`

## Architecture

```text
backtesting/
  __init__.py              # Re-exports all public APIs from submodules
  walk_forward.py          # Time-series cross-validation (prevents look-ahead bias)
  metrics.py               # CLV, ROI, Brier score, Sharpe ratio, drawdown
  simulation.py            # Monte Carlo bankroll projections, risk of ruin
  validators/
    __init__.py            # Re-exports all 5 dimension validators
    temporal_validator.py  # Dimension 1: Look-ahead bias detection (26 tests)
    statistical_validator.py  # Dimension 2: Sample size, significance (49 tests)
    overfit_validator.py   # Dimension 3: Overfitting detection (42 tests)
    betting_validator.py   # Dimension 4: CLV, vig, Kelly validation (52 tests)
    gatekeeper.py          # Dimension 5: Final gate - PASS/QUARANTINE (29 tests)
```

## Validation Pipeline

```text
Raw Model -> [TEMPORAL] -> [STATISTICAL] -> [OVERFIT] -> [BETTING] -> [GATEKEEPER]
                 |               |              |             |             |
             0 leaky         >= 200 bets    <= 15% IS    >= 1.5% CLV    PASS or
             features        >= 0.5 Sharpe     ROI        <= 5% ruin    QUARANTINE
```

## Key Modules

### walk_forward.py

| Export | Type | Purpose |
|--------|------|---------|
| `WalkForwardValidator` | class | Time-series CV with configurable windows (train/test/step days) |
| `SeasonalWalkForwardValidator` | class | Season-boundary-aware CV (extends WalkForwardValidator) |
| `WalkForwardWindow` | dataclass | Single train/test window (fold_id, dates, indices) |
| `WalkForwardResult` | dataclass | Results from one fold (predictions, probabilities, actuals, metrics) |
| `create_lagged_features()` | function | Adds `.shift(n)` lag columns to prevent leakage |
| `detect_data_leakage()` | function | Flags features with suspiciously high target correlation |
| `verify_temporal_integrity()` | function | Checks rolling features for proper shifting |

**Dependencies:** numpy, pandas

**Key Design Decisions:**

- `BaseModel` protocol requires `fit()`, `predict()`, optional `predict_proba()`
- `WalkForwardWindow.__post_init__()` raises ValueError if train_end >= test_start
- `gap_days` parameter defaults to 1 to prevent same-day leakage

### metrics.py

| Export | Type | Purpose |
|--------|------|---------|
| `BettingMetrics` | dataclass | Container for all computed metrics (17 fields) |
| `calculate_roi()` | function | Total Profit / Total Wagered |
| `calculate_clv_metrics()` | function | Average, weighted, median CLV + positive rate |
| `calculate_brier_score()` | function | Probability calibration: mean((p - outcome)^2) |
| `calculate_log_loss()` | function | Cross-entropy loss for probability predictions |
| `calculate_calibration_error()` | function | Binned calibration error with DataFrame output |
| `calculate_sharpe_ratio()` | function | Annualized risk-adjusted returns |
| `calculate_drawdown_metrics()` | function | Max/avg drawdown, duration, current drawdown |
| `calculate_streak_metrics()` | function | Longest win/loss streaks, current streak |
| `calculate_win_rate_by_confidence()` | function | Performance segmented by model confidence |
| `compute_all_metrics()` | function | Main entry point: DataFrame -> BettingMetrics |
| `format_metrics_report()` | function | Human-readable performance report string |

**Dependencies:** numpy, pandas, betting.odds_converter

### simulation.py

| Export | Type | Purpose |
|--------|------|---------|
| `SimulationConfig` | dataclass | Configuration (n_sims, n_bets, bankroll, kelly, stop_loss) |
| `SimulationResult` | dataclass | Results (final_bankrolls, drawdowns, percentiles, ROI distribution) |
| `MonteCarloSimulator` | class | Bankroll path simulation with Kelly sizing |
| `run_drawdown_analysis()` | function | Drawdown distribution analysis convenience wrapper |
| `calculate_risk_of_ruin()` | function | P(losing X% of bankroll) over N bets |
| `validate_kelly_fraction()` | function | Compare different Kelly fractions in simulation |
| `calculate_confidence_intervals()` | function | CI bounds for final bankroll |
| `simulate_from_backtest()` | function | Bootstrap simulation from actual backtest results |
| `format_simulation_report()` | function | Human-readable simulation report string |

**Dependencies:** numpy, pandas, betting.odds_converter (american_to_decimal, fractional_kelly), scipy.stats (optional)

### validators/temporal_validator.py

| Export | Type | Purpose |
|--------|------|---------|
| `TemporalValidator` | class | Main validator for look-ahead bias detection |
| `TemporalValidationResult` | dataclass | Complete validation result (passed, leaky_features, summaries) |
| `LeakageType` | enum | 10 types of temporal leakage (ROLLING_NO_SHIFT, CORRELATION_SPIKE, etc.) |
| `FeatureLeakageInfo` | dataclass | Info about a leaky feature (name, type, severity, evidence, recommendation) |
| `WalkForwardValidationResult` | dataclass | Walk-forward structure validation (is_valid, n_folds, issues) |

**Key Methods on TemporalValidator:**

- `validate_walk_forward()` - Verifies chronological ordering, no overlap, sufficient gap
- `detect_leakage()` - Scans features for correlation spikes, rolling without shift, future references
- `audit_feature_timestamps()` - Verifies features available at t-1
- `validate_closing_line_timing()` - Ensures closing line captured before game start
- `detect_train_test_contamination()` - Checks for index overlap
- `full_validation()` - Runs entire temporal validation pipeline
- `validate()` - Legacy compatibility method
- `detect_data_leakage()` - Legacy compatibility method

**Suspicious Patterns Detected:** rolling, moving_avg, ewm, cumsum, cumulative,
lag, shift, pct_change, diff, mean_last, avg_last, sum_last

### validators/statistical_validator.py

| Export | Type | Purpose |
|--------|------|---------|
| `StatisticalValidator` | class | Enforces sample size, Sharpe, significance |
| `StatisticalValidation` | dataclass | Validation container (sample_size_adequate, sharpe_adequate, etc.) |
| `StatisticalValidationResult` | dataclass | Full result with details dict |
| `DrawdownAnalysis` | dataclass | Max drawdown, recovery time, underwater percentage |
| `MonteCarloRuinResult` | dataclass | Ruin probability from simulation |

**Configurable Thresholds:** min_sample_size (200), min_sharpe (0.5)

### validators/overfit_validator.py

| Export | Type | Purpose |
|--------|------|---------|
| `OverfitValidator` | class | Detects overfitting red flags |
| `OverfitValidation` | dataclass | Results (feature_ratio_passes, in_sample_too_good, variance_passes, etc.) |
| `quick_overfit_check()` | function | Fast check: n_features, n_samples, in_sample_roi |

**Key Checks:**

- Feature count <= sqrt(sample_size) rule
- In-sample ROI <= 15% (suspiciously good threshold)
- Cross-season variance <= 30% (coefficient of variation)
- Parameter sensitivity (model stability under perturbation)
- Learning curve health (generalization vs memorization)

### validators/betting_validator.py

| Export | Type | Purpose |
|--------|------|---------|
| `BettingValidator` | class | Domain-specific CLV, vig, line, Kelly validation |
| `BettingValidation` | dataclass | Results (clv_passes, realistic_vig, lines_were_available, kelly_respects_limits) |
| `VigAnalysis` | dataclass | Vig/juice analysis (assumed baseline, effective break-even) |
| `LineAvailabilityResult` | dataclass | Line availability validation |
| `ValidationSeverity` | enum | INFO, WARNING, ERROR, CRITICAL |
| `ValidationIssue` | dataclass | Individual issue (severity, category, message, details) |
| `format_validation_report()` | function | Human-readable validation report |

**Dependencies:** betting.odds_converter (american_to_implied_prob)

### validators/gatekeeper.py

| Export | Type | Purpose |
|--------|------|---------|
| `Gatekeeper` | class | Final validation gate aggregating all dimensions |
| `GateDecision` | enum | PASS, QUARANTINE, NEEDS_REVIEW |
| `GateReport` | dataclass | Complete report (decision, dimension_results, score, failures, recommendations) |
| `ValidationResult` | dataclass | Single dimension result (dimension, passed, details, failure_reason) |

**Blocking Checks (ALL must pass):**

- `temporal_no_leakage` - 0 leaky features
- `statistical_sample_size` - >= 200 bets
- `statistical_sharpe` - >= 0.5
- `overfit_in_sample_roi` - <= 15%
- `betting_clv_threshold` - >= 1.5% CLV
- `betting_ruin_probability` - <= 5%

**Key Methods on Gatekeeper:**

- `load_validators()` - Initializes all 4 dimension validators
- `_quick_prescreen()` - Instant arithmetic checks (catches ~40% of bad models)
- `run_all_validations()` - Execute all dimensions (full or fast mode with early termination)
- `make_decision()` - PASS/QUARANTINE/NEEDS_REVIEW logic
- `generate_report()` - Main entry point: returns GateReport
- `persist_to_memory()` - Saves report to data/model-scorecards.json
- `quarantine_model()` - Saves failure to data/quarantined-models.json
- `explain_failure()` - Human-readable explanation of why model failed

**Fast Mode:** Validators ordered by cost
(overfit -> betting -> temporal -> statistical).
Early termination on first blocking failure,
then auto-escalates to full mode for complete diagnostics.

## External Dependencies

| Package | Used In | Purpose |
|---------|---------|---------|
| numpy | All modules | Array operations, statistics |
| pandas | All modules | DataFrames, date handling |
| scipy.stats | simulation.py, statistical_validator.py | Optional: advanced statistics |
| betting.odds_converter | metrics.py, simulation.py, betting_validator.py | CLV, odds conversion, Kelly |

## Related Areas

- [betting.md](betting.md) - Core odds/EV/CLV calculations used by metrics and validators
- [models.md](models.md) - Models that must pass the Gatekeeper before deployment
- [config.md](config.md) - BacktestConfig constants used by validators
- [tests.md](tests.md) - 219 tests across 5 validator test files covering all validators
