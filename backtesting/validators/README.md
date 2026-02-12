# Backtesting Validators

A 5-dimension validation framework ensuring no sports betting model reaches production without rigorous testing. This framework catches data leakage, insufficient evidence, overfitting, and unrealistic betting assumptions.

## Overview

**Total Tests: 198**

The validation pipeline runs each validator in sequence, where each must pass before proceeding:

```
Raw Model -> [TEMPORAL] -> [STATISTICAL] -> [OVERFIT] -> [BETTING] -> [GATEKEEPER] -> PASS/QUARANTINE
```

## Quick Start

```python
from backtesting.validators import Gatekeeper, GateDecision

# Initialize the Gatekeeper (loads all validators)
gatekeeper = Gatekeeper()
gatekeeper.load_validators()

# Run full validation
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

# Check result
if report.decision == GateDecision.PASS:
    print("Model approved!")
elif report.decision == GateDecision.QUARANTINE:
    print(f"Blocked: {report.blocking_failures}")
    print(gatekeeper.explain_failure(report))
```

## The 5 Validators

### 1. TemporalValidator (26 tests)

**Purpose:** Prevents look-ahead bias - THE MOST CRITICAL check.

Temporal leakage is the #1 cause of inflated backtest performance. A model should NEVER have access to information unavailable at bet placement time.

**Checks:**

- Walk-forward structure validation
- Train/test contamination detection
- Rolling calculation shift verification (`.shift(1)` after rolling)
- Closing line timing validation
- Feature timestamp auditing
- Suspicious correlation detection

**Usage:**

```python
from backtesting.validators import TemporalValidator

validator = TemporalValidator()
result = validator.full_validation(
    df=betting_data,
    feature_cols=['elo_rating', 'rolling_avg_pts'],
    target_col='result',
    date_col='game_date',
    train_indices=train_idx,
    test_indices=test_idx
)

if not result.passed:
    for leak in result.leaky_features:
        print(f"LEAKAGE: {leak.feature_name} - {leak.leakage_type.value}")
        print(f"  Fix: {leak.recommendation}")
```

### 2. StatisticalValidator (49 tests)

**Purpose:** Enforces statistical rigor - no metric claims without uncertainty bounds.

**Thresholds:**

- Minimum sample size: 200 bets (500 recommended)
- Minimum Sharpe ratio: 0.5
- Maximum out-of-sample degradation: 20%
- Maximum ruin probability: 5%

**Checks:**

- Sample size adequacy
- Confidence intervals (95% CI via bootstrap)
- Sharpe ratio calculation
- Drawdown analysis
- Monte Carlo ruin probability
- Significance testing

**Usage:**

```python
from backtesting.validators import StatisticalValidator

validator = StatisticalValidator(min_sample_size=200, min_sharpe=0.5)

# Quick check
if not validator.validate_sample_size(n_bets=150):
    print("INSUFFICIENT SAMPLE SIZE")

# Full validation
result = validator.full_validation({
    'n_bets': 600,
    'returns': returns_array,
    'clv_values': clv_array,
    'outcomes': win_loss_array,
    'bankroll_series': cumulative_bankroll,
    'avg_odds': 1.91
})

print(validator.format_validation_report(result))
```

### 3. OverfitValidator (42 tests)

**Purpose:** Detects overfitting patterns that inflate backtest results.

A model that looks too good to be true almost certainly is.

**Thresholds:**

- Maximum in-sample ROI: 15% (higher = suspicious)
- Maximum cross-season variance: 30% CV
- Maximum parameter sensitivity: 5% ROI change from 10% param change
- Feature count: sqrt(n_samples) rule

**Checks:**

- Feature count vs sample size
- In-sample ROI sanity check
- Cross-season variance
- Parameter sensitivity analysis
- Learning curve health
- Feature importance stability

**Usage:**

```python
from backtesting.validators import OverfitValidator, quick_overfit_check

# Quick check
passes, warnings = quick_overfit_check(
    n_features=10,
    n_samples=500,
    in_sample_roi=0.08,
    season_rois=[0.05, 0.03, 0.04]
)

# Full validation
validator = OverfitValidator()
result = validator.full_validation(
    backtest_results={
        'season_rois': [0.05, 0.03, 0.04, 0.06],
        'in_sample_roi': 0.08
    },
    model_metadata={
        'n_features': 10,
        'n_samples': 500
    }
)

print(result.summary())
```

### 4. BettingValidator (52 tests)

**Purpose:** Domain-specific validation accounting for market realities.

Theory means nothing if the lines were not actually bettable.

**Thresholds:**

- Minimum CLV: 1.5% sustained over 3+ seasons
- Realistic vig: -110 baseline (at minimum -105)
- Maximum bet size: 3% of bankroll
- Maximum Kelly fraction: 25%

**Checks:**

- CLV threshold validation (PRIMARY METRIC)
- Realistic vig modeling
- Line availability verification
- Kelly sizing limits
- Book-specific slippage
- No look-ahead on closing lines

**Usage:**

```python
from backtesting.validators import BettingValidator

validator = BettingValidator(min_clv=0.015)

# Calculate CLV
clv = validator.calculate_clv(odds_placed=-105, odds_closing=-110)
print(f"CLV: {clv:.2%}")  # Positive = good

# Full validation
result = validator.full_validation({
    'clv_values': [0.02, 0.015, 0.018, 0.025],
    'config': {'assumed_vig': -110},
    'bet_sizes': [100, 150, 100, 200],
    'bankroll': 5000
})

print(result.summary())
```

### 5. Gatekeeper (29 tests)

**Purpose:** Final validation gate - aggregates all dimension checks and makes PASS/QUARANTINE decision.

No model reaches production without passing the Gatekeeper.

**Blocking Checks (ALL must pass):**

- `temporal_no_leakage` - No data leakage detected
- `statistical_sample_size` - >= 200 bets
- `statistical_sharpe` - >= 0.5
- `overfit_in_sample_roi` - <= 15%
- `betting_clv_threshold` - >= 1.5%
- `betting_ruin_probability` - <= 5%

**Gate Decisions:**

- **PASS**: All blocking checks pass, model approved for deployment
- **QUARANTINE**: Any blocking check fails, model needs review/fixes
- **NEEDS_REVIEW**: All pass but multiple warnings or edge cases

**Usage:**

```python
from backtesting.validators import Gatekeeper, GateDecision

gatekeeper = Gatekeeper()
gatekeeper.load_validators()

report = gatekeeper.generate_report(
    model_name="ncaab_elo_v1",
    backtest_results=results_dict,
    model_metadata=metadata_dict
)

# Print summary
print(report.summary())

# Handle decision
if report.decision == GateDecision.PASS:
    print("APPROVED for deployment")
    gatekeeper.persist_to_memory(report)

elif report.decision == GateDecision.QUARANTINE:
    print("QUARANTINED")
    gatekeeper.quarantine_model("ncaab_elo_v1", report)
    print(gatekeeper.explain_failure(report))

elif report.decision == GateDecision.NEEDS_REVIEW:
    print("NEEDS HUMAN REVIEW")
    print(f"Warnings: {report.warnings}")
```

## Example Validation Workflow

```python
"""Complete model validation workflow."""
import pandas as pd
from backtesting.validators import (
    Gatekeeper,
    GateDecision,
    TemporalValidator,
    BettingValidator,
)

# 1. Load backtest results
backtest_df = pd.read_csv("backtest_results.csv")

# 2. Quick temporal check first (most critical)
temporal = TemporalValidator()
temporal_result = temporal.full_validation(
    df=backtest_df,
    feature_cols=['elo_diff', 'rolling_avg'],
    target_col='result',
    date_col='game_date'
)

if not temporal_result.passed:
    print("STOP: Fix temporal leakage before continuing")
    for leak in temporal_result.leaky_features:
        print(f"  - {leak.feature_name}: {leak.recommendation}")
    exit(1)

# 3. Quick CLV check
betting = BettingValidator()
clv_passes, clv_details = betting.validate_clv_threshold(
    clv_values=backtest_df['clv'].tolist()
)

if not clv_passes:
    print(f"WARNING: CLV {clv_details['mean_clv']:.2%} below threshold")

# 4. Full Gatekeeper validation
gatekeeper = Gatekeeper()
gatekeeper.load_validators()

report = gatekeeper.generate_report(
    model_name="my_model_v1",
    backtest_results=backtest_df.to_dict(),
    model_metadata={
        'n_features': 8,
        'n_samples': len(backtest_df),
        'in_sample_roi': 0.05
    }
)

# 5. Handle result
print(report.summary())

if report.decision == GateDecision.PASS:
    print("\nModel APPROVED for paper betting phase")
    gatekeeper.persist_to_memory(report)
else:
    print("\nModel REJECTED")
    print(gatekeeper.explain_failure(report))
    gatekeeper.quarantine_model("my_model_v1", report)
```

## Running Tests

```bash
# All validator tests (198 total)
pytest tests/ -k "validator" -v

# Individual validators
pytest tests/test_temporal_validator.py -v    # 26 tests
pytest tests/test_statistical_validator.py -v # 49 tests
pytest tests/test_overfit_validator.py -v     # 42 tests
pytest tests/test_betting_validator.py -v     # 52 tests
pytest tests/test_gatekeeper.py -v            # 29 tests

# Quick smoke test
python -c "from backtesting.validators import Gatekeeper; print('OK')"
```

## Key Principles

1. **CLV > Win Rate**: Closing Line Value is the PRIMARY success metric
2. **No leakage tolerance**: Any temporal leakage = automatic QUARANTINE
3. **Sample size matters**: 200 minimum, 500+ recommended
4. **If it looks too good, it probably is**: >15% ROI = likely overfit
5. **Lines must exist**: Cannot bet lines that were not available
6. **Vig is real**: Model -110 baseline, not +100

## References

- Bailey, D. H., & Lopez de Prado, M. (2014). The Deflated Sharpe Ratio
- Harvey, C. R., et al. (2016). ...and the Cross-Section of Expected Returns
- Tetlock, P. E. (2015). Superforecasting
