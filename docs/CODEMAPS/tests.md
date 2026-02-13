# Tests Module Codemap

**Last Updated:** 2026-02-12
**Framework:** pytest
**Entry Point:** `tests/conftest.py` (shared fixtures)

## Architecture

```text
tests/
  __init__.py                      # Package marker
  conftest.py                      # Shared fixtures (project_root, test_data_dir, sample data)
  test_backtesting.py              # Walk-forward validator, metrics, simulation tests
  test_elo.py                      # Base Elo + NCAAB Elo model tests
  test_temporal_validator.py       # Temporal integrity validation (26 tests)
  test_statistical_validator.py    # Statistical robustness validation (49 tests)
  test_overfit_validator.py        # Overfitting detection (42 tests)
  test_betting_validator.py        # Betting-specific validation (52 tests)
  test_gatekeeper.py               # Final gate validation (29 tests)
  test_forecasting_db.py           # Forecasting database interface tests
  test_setup.py                    # Environment and dependency verification
```

## Test Distribution

| Test File | Target Module | Test Count | Focus |
|-----------|---------------|------------|-------|
| `test_temporal_validator.py` | validators/temporal_validator.py | 26 | Look-ahead bias, walk-forward structure, leakage detection |
| `test_statistical_validator.py` | validators/statistical_validator.py | 49 | Sample size, Sharpe ratio, confidence intervals |
| `test_overfit_validator.py` | validators/overfit_validator.py | 42 | Feature count rules, in-sample ROI, cross-season variance |
| `test_betting_validator.py` | validators/betting_validator.py | 52 | CLV threshold, vig modeling, Kelly limits, line availability |
| `test_gatekeeper.py` | validators/gatekeeper.py | 29 | Full pipeline, PASS/QUARANTINE decisions, report generation |
| `test_backtesting.py` | backtesting/ (metrics, simulation, walk_forward) | varies | Metrics calculation, simulation config, walk-forward splits |
| `test_elo.py` | models/elo.py, ncaab/team_ratings.py | varies | Elo math, rating updates, spread prediction, regression |
| `test_forecasting_db.py` | tracking/forecasting_db.py | varies | Forecast CRUD, revisions, calibration, Brier scores |
| `test_setup.py` | environment | varies | Package imports, database connectivity |
| **TOTAL** | | **198+** | Full 5-dimension validation framework |

## Shared Fixtures (conftest.py)

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `project_root` | session | Returns Path to project root directory |
| `test_data_dir` | session | Returns `tests/data/` (creates if needed) |
| `sample_backtest_df` | function | DataFrame with realistic backtest data |
| `sample_model_metadata` | function | Dict with n_features, n_samples, in_sample_roi |
| `temp_database` | function | Temporary SQLite database for isolation |

## Running Tests

```bash
# All tests
pytest tests/ -v

# Validator tests only
pytest tests/ -k "validator" -v

# Specific validator
pytest tests/test_gatekeeper.py -v
pytest tests/test_temporal_validator.py -v

# With coverage
pytest tests/ --cov=backtesting --cov=betting --cov=models -v

# Quick smoke test
pytest tests/test_setup.py -v
```

## Test Patterns

1. **Fixtures provide realistic data** - conftest.py generates DataFrames resembling actual backtest outputs
2. **Boundary testing** - Each validator tested at threshold boundaries (e.g., exactly 200 samples, exactly 0.5 Sharpe)
3. **Failure path testing** - QUARANTINE decisions tested with specific blocking check failures
4. **Integration testing** - Gatekeeper tests exercise the full pipeline across all 4 validators
5. **Isolation** - Each test uses fresh validator instances and temp databases

## Related Areas

- [backtesting.md](backtesting.md) - The 5 validators being tested (198 tests total)
- [models.md](models.md) - Elo model tests in test_elo.py
- [tracking.md](tracking.md) - Forecasting DB tests in test_forecasting_db.py
