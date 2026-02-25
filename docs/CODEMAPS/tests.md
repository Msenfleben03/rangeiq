# Tests Module Codemap

**Last Updated:** 2026-02-25
**Framework:** pytest
**Entry Point:** `tests/conftest.py` (shared fixtures)

## Architecture

```text
tests/
  __init__.py                      # Package marker
  conftest.py                      # Shared fixtures (project_root, test_data_dir, sample data)
  # === Validator Tests (219 tests) ===
  test_temporal_validator.py       # Temporal integrity validation (26 tests)
  test_statistical_validator.py    # Statistical robustness validation (49 tests)
  test_overfit_validator.py        # Overfitting detection (42 tests)
  test_betting_validator.py        # Betting-specific validation (52 tests)
  test_gatekeeper.py               # Final gate validation (50 tests)
  # === Feature Tests ===
  test_feature_engineering.py      # Feature engine + utilities (30 tests)
  # === Model Tests ===
  test_elo.py                      # Base Elo + NCAAB Elo model tests
  test_model_persistence.py        # Save/load/export model persistence tests
  # === Tracking Tests ===
  test_logger.py                   # Paper bet logging and validation tests
  test_reports.py                  # Performance reporting tests
  test_settlement.py               # Bet settlement logic tests
  # === Pipeline Tests ===
  test_odds_providers.py           # Odds provider strategy pattern tests (46 tests)
  test_espn_core_odds_provider.py  # ESPN Core API odds provider tests (54 tests)
  test_unified_fetcher.py          # Unified scores+odds fetcher tests (21 tests)
  test_barttorvik_fetcher.py       # Barttorvik T-Rank fetcher tests (18 tests)
  test_team_name_mapping.py        # ESPN<->Barttorvik name mapping tests (11 tests)
  test_tune_barttorvik.py          # Barttorvik grid search tuning tests (14 tests)
  test_daily_run.py                # Paper betting orchestrator tests (29 tests, incl. CLV)
  test_fetch_opening_odds.py       # Opening odds fetcher tests (5 tests)
  # === Integration Tests ===
  test_backtesting.py              # Walk-forward validator, metrics, simulation tests
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
| `test_gatekeeper.py` | validators/gatekeeper.py | 50 | Full pipeline, PASS/QUARANTINE decisions, report generation |
| `test_elo.py` | models/elo.py, ncaab/team_ratings.py | 53 | Elo math, rating updates, spread prediction, regression |
| `test_model_persistence.py` | models/model_persistence.py | 15 | Save/load roundtrip, CSV export, DB export, metadata sidecar |
| `test_logger.py` | tracking/logger.py | 11 | log_paper_bet, batch insert, validate_bet_limits, get_pending |
| `test_reports.py` | tracking/reports.py | 10 | daily_report, weekly_report, clv_analysis, model_health_check |
| `test_settlement.py` | scripts/settle_paper_bets.py | 9 | determine_bet_outcome for ML/spread/total, CLV calc, P/L |
| `test_odds_providers.py` | pipelines/odds_providers.py | 46 | ManualOddsProvider, TheOddsAPIProvider, ESPNOddsProvider mocking |
| `test_espn_core_odds_provider.py` | pipelines/espn_core_odds_provider.py | 54 | ESPN Core API odds fetcher, OddsSnapshot, provider integration |
| `test_unified_fetcher.py` | pipelines/unified_fetcher.py | 21 | Unified fetcher modes, skip lists, enriched parquet output |
| `test_backtesting.py` | backtesting/ (metrics, simulation, walk_forward) | 51 | Metrics calculation, simulation config, walk-forward splits |
| `test_forecasting_db.py` | tracking/forecasting_db.py | 20 | Forecast CRUD, revisions, calibration, Brier scores |
| `test_feature_engineering.py` | features/engineering.py, ncaab/advanced_features.py | 30 | safe_rolling, OQ-weight, rest days, feature engine, leakage check |
| `test_barttorvik_fetcher.py` | pipelines/barttorvik_fetcher.py | 18 | Parquet parsing, PIT lookup, cache, differentials, fetcher class |
| `test_team_name_mapping.py` | pipelines/team_name_mapping.py | 11 | Mascot stripping, manual overrides, full mapping coverage |
| `test_tune_barttorvik.py` | scripts/tune_barttorvik_weights.py | 14 | Grid search combos, result ranking, CSV/JSON output |
| `test_daily_run.py` | scripts/daily_run.py | 26 | Pipeline orchestration, dry-run, settle, report modes |
| `test_setup.py` | environment | 24 | Package imports, database connectivity |
| **TOTAL** | | **629** | Full validation + features + paper betting + models + pipelines + Barttorvik + tuning + integration |

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

# Validator tests only (219 tests)
pytest tests/ -k "validator" -v

# Paper betting pipeline tests (91 tests)
pytest tests/test_logger.py tests/test_reports.py tests/test_settlement.py tests/test_odds_providers.py tests/test_model_persistence.py -v

# Specific validator
pytest tests/test_gatekeeper.py -v
pytest tests/test_temporal_validator.py -v

# With coverage
pytest tests/ --cov=backtesting --cov=betting --cov=models --cov=tracking --cov=pipelines -v

# Quick smoke test
pytest tests/test_setup.py -v
```

## Test Patterns

1. **Fixtures provide realistic data** - conftest.py generates DataFrames resembling actual backtest outputs
2. **Boundary testing** - Each validator tested at threshold boundaries (e.g., exactly 200 samples, exactly 0.5 Sharpe)
3. **Failure path testing** - QUARANTINE decisions tested with specific blocking check failures
4. **Integration testing** - Gatekeeper tests exercise the full pipeline across all 4 validators
5. **Isolation** - Each test uses fresh validator instances and temp databases
6. **Mocking** - Odds provider tests mock HTTP responses to avoid real API calls

## Related Areas

- [backtesting.md](backtesting.md) - The 5 validators being tested (219 tests total)
- [models.md](models.md) - Elo model tests in test_elo.py, persistence in test_model_persistence.py
- [tracking.md](tracking.md) - Logger/reports tests in test_logger.py, test_reports.py, test_settlement.py
- [pipelines.md](pipelines.md) - Odds provider tests in test_odds_providers.py
