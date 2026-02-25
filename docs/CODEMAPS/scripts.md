# Scripts Module Codemap

**Last Updated:** 2026-02-25

## Architecture

```text
scripts/
  # === Phase 1: Data & Training ===
  fetch_historical_data.py       # Download 6 seasons of NCAAB data via ESPN API
  fetch_season_data.py           # Unified scores + odds CLI (incremental/nightly modes)
  train_ncaab_elo.py             # Train Elo model on historical parquet data
  # === Phase 2: Odds Backfill ===
  backfill_historical_odds.py    # ESPN Core API odds backfill (checkpoint/resume)
  # === Phase 2b: Barttorvik Ratings ===
  fetch_barttorvik_data.py     # Fetch Barttorvik T-Rank ratings (cbbdata API, all seasons)
  # === Phase 2c: Barttorvik Tuning ===
  tune_barttorvik_weights.py     # Grid search for Barttorvik coefficients (80 combos)
  # === Phase 3: Backtesting & Validation ===
  backtest_ncaab_elo.py          # Walk-forward backtest with simulated odds + Kelly + feature wrapper
  ab_compare_features.py         # A/B comparison framework (paired t-test on common games)
  incremental_backtest.py        # Walk-forward: train [2020..N-1], test N (5-fold)
  run_gatekeeper_validation.py   # Full 5-dimension Gatekeeper validation
  # === Phase 3b: Opening Odds ===
  fetch_opening_odds.py          # Nightly: fetch opening odds for tomorrow's games (ESPN Core API)
  # === Phase 4: Daily Predictions ===
  daily_predictions.py           # Morning: predict + fetch odds + recommend bets
  daily_run.py                   # Paper betting orchestrator (predict→record→settle→report+CLV)
  # === Phase 5: Paper Betting ===
  record_paper_bets.py           # Record bet decisions (interactive + CSV import)
  settle_paper_bets.py           # Settle completed games, compute P/L and CLV
  # === Phase 6: Reporting ===
  generate_report.py             # CLI for daily/weekly/CLV/health reports
  # === Phase 7: Dashboard ===
  generate_dashboard_data.py     # Merge Elo + Barttorvik + stats → dashboard JSON bundle
  # === Utilities ===
  validate_ncaab_elo.py          # Run NCAAB Elo through Gatekeeper (legacy)
  verify_schema.py               # Verify SQLite schema matches expected structure
  reset_closing_odds.py          # Reset/repair closing odds data
  fix_docstrings.py              # Automated docstring formatting
```

## Phase 1: Data & Training

### fetch_historical_data.py

Downloads 6 seasons (2020-2025) of NCAAB game data via ESPN API with checkpoint/resume support.

**Usage:**

```bash
python scripts/fetch_historical_data.py
python scripts/fetch_historical_data.py --start 2022 --end 2025
python scripts/fetch_historical_data.py --force  # Re-download all
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `get_existing_seasons(output_dir)` | Find cached parquet files (checkpoint resume) |
| `validate_season_data(df, season)` | Validate game count, columns, null scores |
| `fetch_all_seasons(start, end, force, delay)` | Main entry: fetch with rate limiting |

**Outputs:** `data/raw/ncaab/ncaab_games_{year}.parquet`
**Dependencies:** pandas, pipelines.espn_ncaab_fetcher (ESPNDataFetcher), config.settings

### fetch_season_data.py

CLI entry point for the unified fetcher — scores + odds in a single pass.
Supports incremental updates, nightly mode, and scores-only mode.

**Usage:**

```bash
python scripts/fetch_season_data.py --season 2025
python scripts/fetch_season_data.py --season 2025 --incremental
python scripts/fetch_season_data.py --nightly
python scripts/fetch_season_data.py --season 2025 --no-odds
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `main()` | CLI argument parsing and fetcher invocation |

**Outputs:** Enriched parquet (scores + odds) + raw odds parquet
**Dependencies:** pipelines.unified_fetcher (UnifiedNCAABFetcher)

### train_ncaab_elo.py

Loads raw parquet data, processes games chronologically with season regression, outputs a trained model.

**Usage:**

```bash
python scripts/train_ncaab_elo.py
python scripts/train_ncaab_elo.py --start 2020 --end 2025
python scripts/train_ncaab_elo.py --validate  # Print top 25 + sanity checks
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `load_season_data(season)` | Load parquet for a single season |
| `prepare_games_for_elo(df)` | Deduplicate, parse home/away, sort chronologically |
| `extract_conferences(df)` | Build team_id -> conference mapping |
| `train_model(start_season, end_season)` | Main: process seasons with regression between years |
| `validate_model(model)` | Sanity checks: team count, rating bounds, mean |

**Outputs:**

- `data/processed/ncaab_elo_model.pkl` (pickled model + metadata)
- `data/processed/ncaab_elo_ratings_current.csv` (human-readable)
- `team_ratings` table entries via database

**Dependencies:** pandas, config.constants (ELO), models.model_persistence,
models.sport_specific.ncaab.team_ratings, tracking.database

## Phase 2: Odds Backfill

### backfill_historical_odds.py

Backfills historical odds data from ESPN Core API with checkpoint/resume support.
Processes events in batches with configurable delays.

**Usage:**

```bash
python scripts/backfill_historical_odds.py --season 2025
python scripts/backfill_historical_odds.py --season 2025 --resume
python scripts/backfill_historical_odds.py --season 2025 --batch-size 100
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `backfill_season(season, resume, batch_size)` | Main entry: process events with checkpointing |
| `save_checkpoint(state)` | Persist progress for resume |
| `load_checkpoint(season)` | Resume from last checkpoint |

**Outputs:** Odds data saved to `data/odds/` directory
**Dependencies:** pipelines.espn_core_odds_provider (ESPNCoreOddsFetcher)

## Phase 2b: Barttorvik Ratings & Tuning

### fetch_barttorvik_data.py

Downloads daily point-in-time Barttorvik T-Rank efficiency ratings from the free
cbbdata.com API and caches as parquet files.

**Usage:**

```bash
python scripts/fetch_barttorvik_data.py
python scripts/fetch_barttorvik_data.py --seasons 2025
python scripts/fetch_barttorvik_data.py --force  # re-download even if cached
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `main()` | CLI argument parsing, fetcher invocation, summary display |

**Outputs:** `data/external/barttorvik/barttorvik_ratings_{year}.parquet` (347K ratings total)
**Dependencies:** pipelines.barttorvik_fetcher (BarttovikFetcher), config.settings (CBBDATA_API_KEY)

### tune_barttorvik_weights.py

Grid search over barttorvik_weight, net_diff_coeff, and barthag_diff_coeff
to find the combination that maximizes flat-stake ROI while maintaining significance.

**Usage:**

```bash
python scripts/tune_barttorvik_weights.py --quick                          # 12 combos, 2 seasons
python scripts/tune_barttorvik_weights.py --seasons 2020 2021 2022 2023 2024 2025  # Full grid
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `run_grid_search(seasons, quick)` | Main: iterate combos, collect results, rank |
| `GridResult` | Dataclass: combo params + ROI + Sharpe + p-value |

**Grid:** 5 weights x 4 net_coeffs x 4 barthag_coeffs = 80 combos (full), 12 (quick)
**Best Result:** w=1.5, nc=0.005, bc=0.20 → ROI +24.0%, Sharpe 1.89, p=2.5e-6
**Outputs:** `data/backtests/barttorvik_grid_summary.json`, `data/backtests/barttorvik_grid_results.csv`
**Dependencies:** scipy.stats, scripts.backtest_ncaab_elo (BarttovikCoeffs, run_backtest_with_features)
**Tests:** 14 tests in `tests/test_tune_barttorvik.py`

## Phase 3: Backtesting & Validation

### backtest_ncaab_elo.py

Walk-forward backtest: loads trained model, holds out test season,
simulates bet selection with edge filtering, Kelly sizing, and CLV.

**Usage:**

```bash
python scripts/backtest_ncaab_elo.py
python scripts/backtest_ncaab_elo.py --test-season 2025 --min-edge 0.02
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `load_test_season(season)` | Load raw parquet for test season |
| `prepare_test_games(df)` | Convert to game dicts, deduplicate |
| `simulate_market_odds(win_prob, vig)` | Synthetic American odds with vig + noise |
| `simulate_closing_odds(opening_odds)` | Synthetic line movement (1-3 pts) |
| `run_backtest(model, games, ...)` | Walk-forward: predict -> odds -> edge -> Kelly -> P/L |
| `run_backtest_with_features(model, games, feature_engine, ...)` | Walk-forward with feature-adjusted probabilities |
| `summarize_backtest(df)` | Summary stats: ROI, Sharpe, drawdown, CLV |

**Outputs:** `data/backtests/ncaab_elo_backtest_{season}.parquet`
**Dependencies:** numpy, pandas, betting.odds_converter, models.model_persistence, config.constants,
features.sport_specific.ncaab.advanced_features

### ab_compare_features.py

A/B comparison framework using paired t-tests on per-bet returns for the same games.
Compares Elo-only baseline against Elo + advanced features.

**Usage:**

```bash
python scripts/ab_compare_features.py --seasons 2025 --min-edge 0.075
python scripts/ab_compare_features.py --seasons 2020 2021 2022 2023 2024 2025
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `run_ab_comparison(model, games, odds_lookup, seasons, ...)` | Run both configs on same games, paired t-test |
| `print_comparison_table(results)` | Pretty-print per-season and pooled results |

**Dependencies:** copy (deepcopy), scipy.stats (ttest_rel), features.sport_specific.ncaab.advanced_features

### incremental_backtest.py

Walk-forward incremental retraining: for each test season N, trains on [2020..N-1]
and tests on N. Prevents data leakage from training on future seasons.

**Usage:**

```bash
python scripts/incremental_backtest.py
python scripts/incremental_backtest.py --barttorvik
python scripts/incremental_backtest.py --test-seasons 2024 2025 --save-models
python scripts/incremental_backtest.py --compare-alldata
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `run_incremental_backtest(test_seasons, barttorvik, save_models)` | Main: retrain per fold, collect results |
| `compare_to_alldata(incremental_results, alldata_results)` | Compare incremental vs all-data model |

**Folds:** 5 (test seasons 2021-2025), pooled ROI +17.86%, p<0.0001
**Outputs:** Console summary + optional saved models per fold
**Dependencies:** scripts.train_ncaab_elo (train_model), scripts.backtest_ncaab_elo

### run_gatekeeper_validation.py

Runs the full 5-dimension Gatekeeper validation on backtest results.
Falls back to simplified validation if full Gatekeeper unavailable.

**Usage:**

```bash
python scripts/run_gatekeeper_validation.py
python scripts/run_gatekeeper_validation.py --backtest data/backtests/ncaab_elo_backtest_2025.parquet
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `load_backtest(path)` | Load backtest parquet |
| `prepare_gatekeeper_inputs(df)` | Convert DataFrame to Gatekeeper input format |
| `run_validation(backtest_path, model_name)` | Full or simplified validation |
| `_simplified_validation(df, model_name)` | Fallback: checks 4 key blocking thresholds |

**Outputs:** `data/validation/{model_name}_gatekeeper_report.json`
**Dependencies:** pandas, backtesting.validators.gatekeeper (optional), config.settings

## Phase 3b: Opening Odds

### fetch_opening_odds.py

Nightly step: fetches opening/early odds for tomorrow's NCAAB games via ESPN Core API.
Stores snapshots with `snapshot_type='opening'` in `odds_snapshots` table.
Runs as part of `nightly-refresh.ps1` after Barttorvik scraping.

**Usage:**

```bash
python scripts/fetch_opening_odds.py                    # Tomorrow (default)
python scripts/fetch_opening_odds.py --date 2026-02-25  # Specific date
python scripts/fetch_opening_odds.py --dry-run           # Preview games only
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `fetch_opening_odds(db, target_date)` | Discover games, skip existing, fetch odds via ESPN Core API |
| `store_opening_snapshot(db, snapshot)` | Store OddsSnapshot as `snapshot_type='opening'` |

**Dependencies:** pipelines.espn_core_odds_provider (ESPNCoreOddsFetcher),
scripts.daily_predictions (fetch_espn_scoreboard), tracking.database
**Tests:** 5 tests in `tests/test_fetch_opening_odds.py`

## Phase 4: Daily Predictions

### daily_predictions.py

Morning workflow: loads trained model, fetches today's games,
predicts outcomes, retrieves odds, calculates edges, outputs recs.

**Usage:**

```bash
python scripts/daily_predictions.py --date today
python scripts/daily_predictions.py --date 2026-02-15 --mode api
python scripts/daily_predictions.py --date today --mode manual --odds-file odds.csv
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `parse_date(date_str)` | Parse "today", "tomorrow", or YYYY-MM-DD |
| `fetch_todays_games(target_date)` | Fetch games via ESPN API |
| `generate_predictions(model, games, orchestrator, ...)` | Predictions + odds + edge + Kelly recommendations |
| `display_predictions(df)` | Pretty-print prediction table with bet recs |

**Dependencies:** pandas, betting.odds_converter, config.constants,
models.model_persistence, pipelines.odds_orchestrator, tracking.database

### daily_run.py

End-to-end paper betting orchestrator: fetch games → predict → record bets → settle → report.
Single entry point for all daily operations.

**Usage:**

```bash
python scripts/daily_run.py                    # Full run
python scripts/daily_run.py --dry-run          # Preview without recording
python scripts/daily_run.py --settle-only      # Only settle yesterday's bets
python scripts/daily_run.py --report-only      # Only generate weekly report
python scripts/daily_run.py --date 2026-02-15  # Specific date
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `run_full_pipeline(date, dry_run)` | Main: orchestrate all phases |
| `settle_yesterdays_bets(db, settle_date)` | Pass 1: settle win/loss; Pass 2: fetch closing odds + CLV |
| `_get_closing_ml_for_bet(selection, game, snapshot)` | Match bet side to closing moneyline |
| `_store_closing_snapshot(db, snapshot)` | Store closing odds as `snapshot_type='closing'` |
| `generate_weekly_report(db)` | Aggregate weekly stats |

**Dependencies:** scripts.daily_predictions (fetch_espn_scoreboard, generate_predictions),
pipelines.espn_core_odds_provider (ESPNCoreOddsFetcher), betting.odds_converter (calculate_clv),
tracking.logger (auto_record_bets_from_predictions), tracking.reports (daily_report, weekly_report)
**Tests:** 29 tests in `tests/test_daily_run.py`

## Phase 5: Paper Betting

### record_paper_bets.py

Records paper bet decisions via interactive prompt or CSV import. Validates exposure limits before confirming.

**Usage:**

```bash
python scripts/record_paper_bets.py --date today       # Interactive mode
python scripts/record_paper_bets.py --import-csv bets.csv
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `import_from_csv(csv_path, db)` | Bulk import bets from CSV with validation |
| `interactive_mode(target_date, db)` | Interactive bet entry with limit checks |

**Dependencies:** tracking.database, tracking.logger (log_paper_bet, validate_bet_limits)

### settle_paper_bets.py

Evening workflow: fetches game results, determines outcomes, calculates P/L
and CLV, updates database, refreshes model ratings.

**Usage:**

```bash
python scripts/settle_paper_bets.py --date today
python scripts/settle_paper_bets.py --date yesterday
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `fetch_game_results(target_date)` | Get scores via ESPN API |
| `determine_bet_outcome(bet, game_result)` | Win/loss/push for moneyline, spread, total |
| `settle_bets(db, date, orchestrator, model)` | Main: settle pending bets + update ratings |

**Dependencies:** betting.odds_converter, models.model_persistence,
pipelines.odds_orchestrator, tracking.database, tracking.logger

## Phase 6: Reporting

### generate_report.py

CLI wrapper for all report types from tracking.reports.

**Usage:**

```bash
python scripts/generate_report.py --daily
python scripts/generate_report.py --weekly --clv
python scripts/generate_report.py --health --odds-health
python scripts/generate_report.py --all
```

**Report Types:**

| Flag | Function | Purpose |
|------|----------|---------|
| `--daily` | `print_daily()` | Today's bets, P/L, CLV |
| `--weekly` | `print_weekly()` | Rolling week: ROI, Sharpe, CLV trend |
| `--clv` | `print_clv()` | 30-day CLV distribution by bet type |
| `--health` | `print_health()` | Model drift alerts (CRITICAL/WARNING) |
| `--odds-health` | `print_odds_health()` | Provider success rates, stale data |
| `--all` | all of above | Full dashboard |

**Dependencies:** tracking.database, tracking.reports

## Phase 7: Dashboard

### generate_dashboard_data.py

Merges three data sources into a single JSON bundle for the NCAAB dashboard:
Elo ratings (current), Barttorvik T-Rank (latest snapshot), and game stats (2026 W-L, PPG).

**Usage:**

```bash
python scripts/generate_dashboard_data.py
python scripts/generate_dashboard_data.py --season 2026
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `main()` | CLI parsing + merge pipeline |
| `load_elo_ratings()` | Load trained model ratings |
| `load_barttorvik_snapshot()` | Load latest Barttorvik snapshot |
| `merge_data_sources(elo, barttorvik, games)` | Merge on team + add conference metadata |

**Outputs:** `data/processed/ncaab_dashboard_bundle.json` (360 teams, 31 conferences)
**Dependencies:** pipelines.team_name_mapping (build_espn_barttorvik_mapping), pandas
**Consumed by:** `dashboards/ncaab_dashboard.html` (Plotly.js, 7 tabs)

## Utility Scripts

### validate_ncaab_elo.py

Runs the NCAAB Elo model through the full 5-dimension validation pipeline
(legacy — superseded by `run_gatekeeper_validation.py`).

**Dependencies:** backtesting.validators (Gatekeeper), models.sport_specific.ncaab.team_ratings

### verify_schema.py

Validates SQLite database schema matches expected structure.

**Dependencies:** sqlite3, tracking.database

### reset_closing_odds.py

Utility to reset or repair closing odds data in the bets table.

**Dependencies:** sqlite3

### fix_docstrings.py

Automated docstring formatting and repair tool for consistent Google-style docstrings.

**Dependencies:** ast (Python AST parsing)

## Daily Workflow

```text
OPTION A — Automated (recommended):
  1. daily_run.py --dry-run                       # Preview picks
  2. daily_run.py                                 # Full: predict → record → settle → report

OPTION B — Manual steps:
  MORNING:
    1. daily_predictions.py --date today           # Predict + odds + recommendations
    2. record_paper_bets.py --date today            # Record bet decisions
  EVENING:
    3. settle_paper_bets.py --date today            # Settle completed games
    4. generate_report.py --daily --odds-health     # Performance check

WEEKLY:
  5. generate_report.py --weekly --clv            # Full review
  6. generate_dashboard_data.py                   # Refresh dashboard data
```

## Related Areas

- [models.md](models.md) - model_persistence.py used by train/backtest/settle scripts
- [pipelines.md](pipelines.md) - odds_orchestrator.py used by daily_predictions and settle
- [tracking.md](tracking.md) - logger.py and reports.py used by record/settle/generate scripts
- [backtesting.md](backtesting.md) - Gatekeeper used by run_gatekeeper_validation.py
- [config.md](config.md) - ODDS_CONFIG, BANKROLL, THRESHOLDS consumed by all scripts
