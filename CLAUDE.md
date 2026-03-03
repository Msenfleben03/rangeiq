# Project: Sports Betting Model Development

## Overview

Build profitable projection models for NCAA Football, NCAA Basketball, NFL, and MLB
achieving positive ROI through systematic Closing Line Value (CLV) capture with zero startup costs.

## Tech Stack

- Language: Python 3.11+
- Framework: pandas, scikit-learn, statsmodels
- Database: SQLite (local), potential PostgreSQL migration
- Testing: pytest

---

## Backtesting Validation Framework

### Overview

A comprehensive 5-dimension validation framework ensures no model reaches production without
rigorous testing. The framework catches data leakage, insufficient evidence, overfitting,
and unrealistic betting assumptions.

### Validation Pipeline

```text
Raw Model -> [TEMPORAL] -> [STATISTICAL] -> [OVERFIT] -> [BETTING] -> [GATEKEEPER] -> PASS/QUARANTINE
```

### The 5 Validators

| Validator | Tests | Purpose |
|-----------|-------|---------|
| **TEMPORAL** | 26 | Prevents look-ahead bias (THE MOST CRITICAL) |
| **STATISTICAL** | 49 | Enforces sample size, Sharpe, significance |
| **OVERFIT** | 42 | Detects overfitting patterns |
| **BETTING** | 52 | Domain-specific checks (CLV, vig, Kelly) |
| **GATEKEEPER** | 29 | Final gate - aggregates all decisions |
| **TOTAL** | **198** | Complete validation suite |

### Blocking Check Thresholds

| Check | Threshold | Dimension |
|-------|-----------|-----------|
| `temporal_no_leakage` | 0 leaky features | TEMPORAL |
| `statistical_sample_size` | >= 200 bets | STATISTICAL |
| `statistical_sharpe` | >= 0.5 | STATISTICAL |
| `overfit_in_sample_roi` | <= 15% | OVERFIT |
| `betting_clv_threshold` | >= 1.5% | BETTING |
| `betting_ruin_probability` | <= 5% | BETTING |

### Gate Decisions

- **PASS**: All blocking checks pass - model approved for deployment
- **QUARANTINE**: Any blocking check fails - model needs fixes
- **NEEDS_REVIEW**: Passes but has warnings or edge cases

### Usage Example

```python
from backtesting.validators import Gatekeeper, GateDecision

# Initialize and load all validators
gatekeeper = Gatekeeper()
gatekeeper.load_validators()

# Run full validation pipeline
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

# Check decision
if report.decision == GateDecision.PASS:
    print("Model approved for deployment!")
    print(report.summary())
elif report.decision == GateDecision.QUARANTINE:
    print(f"Model quarantined: {report.blocking_failures}")
    gatekeeper.quarantine_model("ncaab_elo_v1", report)
    print(gatekeeper.explain_failure(report))
```

### Individual Validator Usage

```python
from backtesting.validators import (
    TemporalValidator,
    StatisticalValidator,
    OverfitValidator,
    BettingValidator,
)

# Temporal: Check for data leakage
temporal = TemporalValidator()
result = temporal.full_validation(
    df=betting_data,
    feature_cols=features,
    target_col='result',
    date_col='game_date'
)
if not result.passed:
    print(f"Leakage detected: {[f.feature_name for f in result.leaky_features]}")

# Statistical: Verify sample size and significance
statistical = StatisticalValidator(min_sample_size=200, min_sharpe=0.5)
result = statistical.validate(backtest_df, model_metadata)
if not result.sample_size_adequate:
    print("Insufficient sample size for statistical conclusions")

# Overfit: Check for overfitting red flags
overfit = OverfitValidator()
result = overfit.full_validation(
    {'season_rois': [0.05, 0.03, 0.04], 'in_sample_roi': 0.08},
    {'n_features': 10, 'n_samples': 500}
)
if result.in_sample_too_good:
    print("WARNING: In-sample ROI suspiciously high!")

# Betting: Validate CLV and realistic assumptions
betting = BettingValidator(min_clv=0.015)
result = betting.full_validation({
    'clv_values': [0.02, 0.015, 0.018],
    'config': {'assumed_vig': -110},
    'bet_sizes': [100, 150, 100],
    'bankroll': 5000
})
print(f"CLV passes: {result.clv_passes}")
```

---

## Workflows

### Model Validation Workflow

```bash
# Run full validation before deployment
python -c "
from backtesting.validators import Gatekeeper
gk = Gatekeeper()
gk.load_validators()
report = gk.generate_report('model_name', results, metadata)
print(report.summary())
"

# Run validator tests
pytest tests/test_temporal_validator.py -v
pytest tests/test_gatekeeper.py -v
pytest tests/ -k "validator" -v  # All validator tests
```

---

## Project Structure

```text
sports_betting/
├── CLAUDE.md                 # This file - Claude Code context
├── README.md                 # Project overview
├── AGENTS.md                 # Agent personas
├── requirements.txt          # Python dependencies
├── .env                      # API keys (gitignored)
├── .gitignore
│
├── config/
│   ├── settings.py           # Global configuration (paths, API keys, DB)
│   └── constants.py          # Thresholds, InjuryCheckConfig, OddsConfig
│
├── data/
│   ├── raw/ncaab/            # Parquet game files per season (ncaab_games_YYYY.parquet)
│   ├── raw/mlb/              # MLB raw data
│   ├── mlb_data.db           # MLB-specific database (14 tables, game_pk key)
│   ├── projections/mlb/      # MLB preseason projections cache
│   ├── processed/            # Backtest results, Barttorvik ratings, odds, dashboard JSON
│   ├── odds/                 # Historical odds snapshots
│   └── external/             # Barttorvik scraped snapshots
│
├── models/
│   ├── elo.py                # Elo rating system (K-factor, HCA, regression)
│   ├── model_persistence.py  # Save/load models with ModelMetadata
│   └── sport_specific/
│       ├── ncaab/
│       │   └── team_ratings.py  # NCAABTeamRatings (Elo + Barttorvik ensemble)
│       ├── mlb/
│       │   ├── poisson_model.py     # Poisson run distribution → ML/RL/totals/F5
│       │   ├── pitcher_model.py     # Pitcher evaluation and projection
│       │   ├── lineup_model.py      # Lineup strength with platoon splits
│       │   └── projection_blender.py # ZiPS/Steamer blending with observed data
│       └── nfl/, ncaaf/             # Placeholder __init__.py only
│
├── features/
│   ├── engineering.py        # Safe rolling, decay, opponent-quality, rest days
│   └── sport_specific/
│       ├── ncaab/
│       │   ├── advanced_features.py  # NCAABFeatureEngine (vol, OQ-margin, rest, decay)
│       │   └── breadwinner.py        # Breadwinner metric (DISABLED - no ROI correlation)
│       └── mlb/
│           ├── pitcher_features.py   # K-BB%, SIERA, xFIP, Stuff+, rolling stats
│           ├── lineup_features.py    # Aggregate wRC+, platoon splits, xwOBA
│           ├── bullpen_features.py   # Fatigue tracking, availability, TTOP
│           ├── weather_features.py   # Wind direction/speed, temp, dome detection
│           ├── park_features.py      # Event-specific park factors by handedness
│           └── umpire_features.py    # Zone size, K/BB rates, run impact
│
├── betting/
│   ├── odds_converter.py     # American/decimal/implied prob, CLV calc, Kelly, devig_prob()
│   └── arb_detector.py       # Cross-book arbitrage detection
│
├── tracking/
│   ├── database.py           # BettingDatabase SQLite interface
│   ├── models.py             # Database schema/ORM definitions
│   ├── logger.py             # Bet logging (skips injury-flagged bets)
│   ├── reports.py            # Performance reporting
│   ├── forecasting_db.py     # ForecastingDatabase for prediction markets
│   ├── cost_tracker.py       # API cost tracking
│   └── doc_metrics.py        # Documentation metrics
│
├── backtesting/
│   ├── walk_forward.py       # Walk-forward validation engine
│   ├── metrics.py            # Evaluation metrics (ROI, Sharpe, CLV)
│   ├── simulation.py         # Monte Carlo simulations
│   └── validators/           # 5-Dimension Validation Framework (198 tests)
│       ├── temporal_validator.py    # Look-ahead bias detection
│       ├── statistical_validator.py # Sample size, Sharpe, significance
│       ├── overfit_validator.py     # Overfitting detection
│       ├── betting_validator.py     # CLV, vig, Kelly validation
│       └── gatekeeper.py           # Final validation gate
│
├── pipelines/
│   ├── espn_ncaab_fetcher.py      # ESPN Site API fetcher (primary NCAAB scores)
│   ├── ncaab_data_fetcher.py      # Legacy sportsipy wrapper (BROKEN - use ESPN API)
│   ├── espn_core_odds_provider.py # ESPN Core API odds (free, historical)
│   ├── unified_fetcher.py         # Scores + odds in one pass
│   ├── barttorvik_fetcher.py      # Barttorvik T-Rank ratings (cbbdata API, Parquet)
│   ├── barttorvik_scraper.py      # Daily Barttorvik web scraper (for in-progress seasons)
│   ├── kenpom_fetcher.py          # KenPom fetcher (auth BLOCKED - cbbdata issue #14)
│   ├── team_name_mapping.py       # ESPN <-> Barttorvik team name mapping (359 teams)
│   ├── injury_checker.py          # ESPN predictor cross-check (injury/divergence detection)
│   ├── odds_providers.py          # Odds retrieval (4 providers)
│   ├── odds_orchestrator.py       # Odds fallback: API -> ESPN Core -> ESPN -> Cache
│   ├── closing_odds_collector.py  # Closing odds collection
│   ├── batch_fetcher.py           # Batch data fetching utility
│   ├── player_stats_fetcher.py    # Player statistics fetcher
│   ├── polymarket_fetcher.py      # Polymarket API client
│   ├── kalshi_fetcher.py          # Kalshi API client (CFTC-regulated)
│   ├── arb_scanner.py             # Cross-book arbitrage detection
│   │   # === MLB Pipelines ===
│   ├── mlb_stats_api.py           # MLB Stats API client (schedules, lineups, rosters)
│   ├── mlb_pybaseball_fetcher.py  # pybaseball wrapper (Statcast, FanGraphs)
│   ├── mlb_weather_fetcher.py     # Open-Meteo client (forecast + historical)
│   ├── mlb_projections_fetcher.py # ZiPS/Steamer from FanGraphs
│   ├── mlb_odds_provider.py       # MLB odds (ESPN Core API + others)
│   ├── mlb_lineup_monitor.py      # Lineup confirmation polling / event-driven
│   └── mlb_park_factors.py        # Park factor ingestion + computation
│
├── dashboards/
│   └── ncaab_dashboard.html       # Unified NCAAB dashboard (9 tabs)
│
├── tests/                         # 36 test files, ~635 tests + 35 planned MLB
│   ├── conftest.py                # Shared fixtures
│   ├── test_elo.py                # Elo model tests
│   ├── test_odds_converter.py     # 6 tests for devig_prob() + odds utilities
│   ├── test_daily_run.py          # 29 tests for paper betting pipeline (incl. CLV)
│   ├── test_fetch_opening_odds.py # 5 tests for opening odds fetcher
│   ├── test_feature_engineering.py   # 30 tests for feature engine
│   ├── test_barttorvik_fetcher.py    # 18 tests for Barttorvik pipeline
│   ├── test_barttorvik_scraper.py
│   ├── test_team_name_mapping.py     # 11 tests for ESPN<->Barttorvik mapping
│   ├── test_espn_core_odds_provider.py
│   ├── test_unified_fetcher.py
│   ├── test_odds_providers.py
│   ├── test_temporal_validator.py
│   ├── test_statistical_validator.py
│   ├── test_overfit_validator.py
│   ├── test_betting_validator.py
│   ├── test_gatekeeper.py
│   ├── test_tune_barttorvik.py       # 14 tests for weight tuning grid search
│   ├── test_logger.py               # 8 failures (schema mismatch - known issue)
│   ├── test_settlement.py
│   ├── test_reports.py
│   ├── test_model_persistence.py
│   ├── test_forecasting_db.py
│   ├── test_backtesting.py
│   ├── test_breadwinner_metric.py
│   ├── test_daily_snapshot.py
│   ├── test_kelly_sizer.py          # 15 tests for KellySizer + calibration
│   ├── test_kenpom_fetcher.py
│   ├── test_tune_kenpom.py
│   ├── test_player_stats_fetcher.py
│   ├── test_setup.py
│   │   # === MLB Tests ===
│   ├── test_mlb_poisson_model.py    # Poisson run distribution tests
│   ├── test_mlb_pitcher_model.py    # Pitcher evaluation tests
│   ├── test_mlb_stats_api.py        # MLB Stats API client tests
│   ├── test_mlb_weather_fetcher.py  # Open-Meteo weather tests
│   ├── test_mlb_daily_run.py        # MLB daily pipeline tests
│   ├── test_mlb_backfill_starters.py # Starter ID backfill tests (23 tests)
│   └── test_mlb_backfill_odds.py     # MLB odds backfill tests (7 tests)
│
├── scripts/
│   │   # === Core Pipeline ===
│   ├── daily_run.py                   # Paper betting orchestrator (predict->record->settle->report+CLV)
│   ├── daily_predictions.py           # ESPN Scoreboard API + Barttorvik predictions + ESPN% display
│   ├── record_paper_bets.py           # Log paper bet decisions
│   ├── settle_paper_bets.py           # Settle completed bets
│   ├── generate_report.py             # Performance reports
│   │   # === Data Fetching ===
│   ├── fetch_opening_odds.py          # Nightly: fetch opening odds for tomorrow's games (ESPN Core)
│   ├── fetch_season_data.py           # Unified scores + odds fetcher CLI
│   ├── fetch_historical_data.py       # Fetch NCAAB seasons (ESPN API)
│   ├── fetch_barttorvik_data.py       # Fetch Barttorvik T-Rank ratings (all seasons)
│   ├── fetch_barttorvik_2026.py       # 2026-specific Barttorvik fetch
│   ├── fetch_kenpom_data.py           # KenPom data fetch
│   ├── backfill_historical_odds.py    # ESPN Core API odds backfill (checkpoint/resume)
│   ├── daily_snapshot.py              # Daily ratings snapshot
│   │   # === Training & Backtesting ===
│   ├── train_ncaab_elo.py             # Train Elo model on historical data
│   ├── backtest_ncaab_elo.py          # Walk-forward backtest + feature wrapper
│   ├── incremental_backtest.py        # Walk-forward: train [2020..N-1], test N
│   ├── validate_ncaab_elo.py          # Model validation
│   ├── run_gatekeeper_validation.py   # 5-dim validation pipeline
│   │   # === Tuning & A/B Testing ===
│   ├── tune_barttorvik_weights.py     # Grid search for Barttorvik coefficients
│   ├── tune_kenpom_weights.py         # KenPom weight tuning
│   ├── tune_breadwinner_weights.py    # Breadwinner tuning (DISABLED)
│   ├── ab_compare_features.py         # A/B comparison framework (paired t-test)
│   │   # === Dashboard & Infrastructure ===
│   ├── generate_dashboard_data.py     # Merge Elo + Barttorvik + stats -> dashboard JSON
│   ├── deploy_dashboard.py            # Deploy dashboard to Vercel
│   ├── pipeline_health_check.py       # Pre-flight health check (venv, DB, APIs)
│   ├── verify_schema.py              # Database schema verification
│   ├── reset_closing_odds.py          # Reset/fix closing odds data
│   ├── fix_docstrings.py             # Docstring formatting utility
│   │   # === MLB Scripts ===
│   ├── mlb_daily_run.py               # MLB daily pipeline orchestrator (event-driven)
│   ├── mlb_fetch_historical.py        # Bulk fetch 2023-2025 data
│   ├── mlb_backtest.py                # Walk-forward backtesting
│   ├── mlb_train_model.py             # Model training
│   ├── mlb_fetch_projections.py       # Preseason projections pull
│   ├── mlb_init_db.py                 # Initialize mlb_data.db schema
│   ├── mlb_backfill_starters.py       # Backfill starter IDs from boxscore API
│   ├── mlb_backfill_odds.py           # Backfill 2023-2025 ML odds from ESPN Core API
│   │   # === Exploratory ===
│   └── test_cbbdata_api.py            # CBBData API exploratory testing
│
├── scripts/                           # PowerShell orchestrators
│   ├── daily-pipeline.ps1             # Unified daily pipeline (7 AM: scores→Elo→Barttorvik→KenPom→settle→predict→dashboard)
│   ├── nightly-refresh.ps1            # Legacy (replaced by daily-pipeline.ps1)
│   ├── morning-betting.ps1            # Legacy (replaced by daily-pipeline.ps1)
│   ├── pipeline-common.ps1            # Shared PS functions (lock, log, checkpoint)
│   └── setup-scheduled-tasks.ps1      # Register/unregister Task Scheduler tasks
│
└── docs/
    ├── DATA_DICTIONARY.md             # Field definitions
    ├── DECISIONS.md                   # Architecture decisions (20 cross-sport + NCAAB ADRs; MLB → docs/mlb/DECISIONS.md)
    ├── ARCHITECTURE.md                # System architecture overview
    ├── DATA_SOURCES.md                # Master data source reference
    ├── RUNBOOK.md                     # Daily/weekly/monthly operations
    ├── QUICKSTART.md                  # Setup checklist
    ├── CONTRIB.md                     # Contribution guidelines
    ├── ADVANCED_FEATURES_RESEARCH.md  # Feature research report
    ├── CBBDATA_API_RESEARCH.md        # CBBData REST API research
    ├── CBBDATA_QUICKSTART.md          # CBBData API quick start guide
    ├── BARTTORVIK_SUMMARY.md          # Barttorvik integration summary
    ├── ESPN_BPI_API_RESEARCH.md       # ESPN BPI API research
    ├── KENPOM_EFFICIENCY_RESEARCH.md  # KenPom/Barttorvik data options
    ├── reports/                       # Generated analysis reports
    ├── plans/                         # Design documents
    │   ├── 2026-02-25-mlb-expansion-design.md  # MLB expansion design
    │   ├── 2026-02-26-poisson-model-v1.md      # Poisson model v1 design
    │   ├── 2026-02-27-lookahead-predictions.md  # Lookahead predictions design
    │   ├── 2026-02-28-injury-divergence-system.md # Injury/divergence overhaul (3 phases)
    │   ├── 2026-03-02-mlb-measurement-fix-design.md  # CLV/edge de-vig design
    │   └── 2026-03-02-mlb-measurement-fix-impl.md    # CLV/edge de-vig implementation plan
    ├── mlb/                           # MLB-specific documentation
    │   ├── README.md                  # MLB model overview + NCAAB comparison
    │   ├── DECISIONS.md               # MLB ADRs (11 decisions: Poisson, de-vig, F5, etc.)
    │   ├── DATA_SOURCES.md            # MLB Stats API, pybaseball, Open-Meteo
    │   ├── DATA_DICTIONARY.md         # mlb_data.db schema (14 tables)
    │   ├── MODEL_ARCHITECTURE.md      # Poisson model design, feature hierarchy
    │   ├── PIPELINE_DESIGN.md         # Event-driven pipeline architecture
    │   ├── 4-cell-diagnostic-2024.md  # De-vigged CLV/ROI by cell (home/away × fav/dog)
    │   ├── 4-cell-diagnostic-2025.md  # De-vigged CLV/ROI by cell (home/away × fav/dog)
    │   └── research/                  # MLB research by topic
    │       ├── pitching-metrics.md    # SIERA, K-BB%, Stuff+, stabilization
    │       ├── bullpen-fatigue.md     # Fatigue modeling, availability tracking
    │       ├── weather-effects.md     # Wind, temperature, humidity
    │       ├── park-factors.md        # Event-specific park effects
    │       ├── platoon-splits.md      # L/R matchup advantages
    │       ├── umpire-zones.md        # Strike zone analysis
    │       ├── market-strategies.md   # F5, totals, K props, contrarian
    │       └── projection-systems.md  # ZiPS, Steamer, blending weights
    └── CODEMAPS/                      # Module-level architecture docs
        ├── CODEMAP.md                 # Index / overview
        ├── backtesting.md
        ├── betting.md
        ├── config.md
        ├── features.md
        ├── models.md
        ├── pipelines.md
        ├── scripts.md
        ├── tests.md
        └── tracking.md
```

---

## Current Phase & Timeline

### Status Dashboard

| Phase | Dates | Focus | Status |
|-------|-------|-------|--------|
| 1-2 | Jan 24 - Feb 6 | NCAAB foundation | Complete |
| 3-4 | Feb 7 - Feb 20 | NCAAB paper betting + automation | Complete |
| 5-6 | Feb 21 - Mar 6 | March Madness prep + MLB skeleton | In Progress |
| 7-8 | Mar 7 - Mar 20 | Live testing (small stakes) + MLB data | Upcoming |
| 9-10 | Mar 21 - Apr 3 | MLB model v1 + paper betting | Upcoming |

### Current Sprint Focus

- [x] Set up project structure and environment
- [x] Implement NCAAB data pipeline (ESPN API — sportsipy broken)
- [x] Build baseline NCAAB Elo model (models/elo.py, models/sport_specific/ncaab/team_ratings.py)
- [x] Create SQLite database with schema (22 tables)
- [x] Build 5-dimension validation framework (198 tests)
- [x] Fetch 6 seasons of historical data (2020-2025, 35,719 games)
- [x] Train Elo model (1,061 teams rated)
- [x] Run walk-forward backtest (2025 season)
- [x] Run Gatekeeper validation (QUARANTINE — needs real odds, conference data)
- [x] Build ESPN Core API odds fetcher (free, historical, ~85% coverage)
- [x] Build unified scores + odds fetcher (single-pass pipeline)
- [x] Build interactive Elo ratings dashboard (5-tab HTML)
- [x] Complete historical odds backfill (2020-2025, 91.6% coverage, 318K records)
- [x] Re-backtest with real odds data (6 seasons, pooled p=0.0002, ROI 6.54%)
- [x] Advanced feature research (5 features evaluated, 4 implemented)
- [x] A/B test advanced features (5/6 seasons improved, one-sided p=0.064)
- [x] Research KenPom alternatives (Barttorvik cbbdata API — free, daily ratings)
- [x] Build Barttorvik fetcher pipeline (347K ratings cached, 6 seasons)
- [x] Build ESPN <-> Barttorvik team name mapping (359 teams)
- [x] Integrate Barttorvik efficiency ratings into backtest
- [x] Grid search Barttorvik weights (quick: 12 combos, best w=1.5/nc=0.003/bc=0.15, ROI +24.2%)
- [x] Incremental retraining (5-fold walk-forward, pooled ROI +17.86%, p<0.0001)
- [x] Build paper betting system (daily_run.py orchestrator, ESPN Scoreboard API)
- [x] Full grid search (80 combos, 6 seasons, best w=1.5/nc=0.005/bc=0.20, ROI +24.0%, p=2.5e-6)
- [x] Fixed stale Elo ratings (retrained with 2026 data, 5,039 games)
- [x] Fixed DB schema mismatches (game_date, profit_loss, confidence columns)
- [x] Built NCAAB dashboard (7-tab HTML, Elo + Barttorvik + game stats)
- [x] Built dashboard data pipeline (generate_dashboard_data.py → JSON bundle)
- [x] Dry-run paper betting verified (5 picks, 7.9-13.4% edges)
- [x] Implement CLV collection system (opening odds + closing odds + CLV calc)
- [x] Implement Dynamic Kelly sizing (KellySizer + Platt calibration)
- [x] Implement KenPom nightly scraping (kenpompy → parquet + SQLite)
- [x] Unify pipeline automation (daily-pipeline.ps1, Task Scheduler 7 AM)
- [x] Implement ESPN predictor cross-check (injury/divergence detection)
- [x] Design MLB expansion (15 architectural decisions documented)
- [x] Create MLB skeleton (47 files: models, features, pipelines, scripts, tests, docs)
- [ ] Begin live paper betting tracking (daily_run.py)
- [ ] Backfill 2026 odds (0% coverage currently)
- [x] MLB Phase 1a: init_db — mlb_data.db schema (13 tables, 30 teams, 360 park factors)
- [x] MLB Phase 1b: historical data — 7,511 games + 2,193 pitcher stat rows (2023-2025)
- [x] MLB Phase 1c: Poisson model v1 — 54.1% accuracy, log loss 0.697 (2025 test)
- [x] MLB Phase 1d: Starter backfill + pitcher adjustment (backfill running, parser fixed)
- [x] MLB measurement fix: de-vig CLV + edge (`devig_prob()` in `betting/odds_converter.py`)
  (2025 results: -3.0% ROI, -1.74% de-vigged CLV)

### Injury/Divergence System Overhaul

- [ ] Phase 1: Backtest ESPN divergence (2023-2025, ~18K games) — plan: `docs/plans/2026-02-28-injury-divergence-system.md`
- [ ] Phase 2: Graduated sizing (replace binary kill switch with data-driven curve)
- [ ] Phase 3: Injury data enrichment (ESPN injuries API + cross-reference sources)

### Prediction Markets Integration

- [x] Research prediction market platforms (Polymarket, Kalshi, PredictIt)
- [x] Research Superforecasting methodology (Tetlock/GJP)
- [x] Design forecasting schema (7 tables)
- [x] Build Polymarket data fetcher
- [x] Build Kalshi data fetcher (CFTC-regulated)
- [ ] Open Kalshi account (CFTC-regulated)
- [ ] Paper trade 50+ positions
- [ ] Achieve Brier score < 0.125

---

## Prediction Markets Module

### Strategic Focus

| Category | Priority | Expected CLV |
|----------|----------|--------------|
| Political/Economic | HIGH | 3-10% |
| Sports | AVOID | Inferior to sportsbooks |

### Platform Hierarchy

| Platform | Use Case | Risk | Fees |
|----------|----------|------|------|
| **Kalshi** | Primary trading (US legal) | Low | 1.2% |
| **Polymarket** | Data source + US launch Mar 2026 | Medium | 0.01% |
| **PredictIt** | Accuracy benchmark only | High | 16% |

### Key Metrics

| Metric | Target | Benchmark |
|--------|--------|-----------|
| Brier Score | < 0.125 | Superforecasters: 0.10 |
| Calibration Error | < 5% | Per probability bin |
| CLV | > 3% | Political/economic markets |

### Superforecasting Principles

1. **Fermi Decomposition** - Break complex questions into sub-questions
2. **Outside View First** - Start with base rates
3. **Granular Estimates** - 65% beats "likely"
4. **Bayesian Updating** - Many small revisions
5. **Track Every Revision** - With reasoning

### Quick Start

```python
# Polymarket data fetching
from pipelines.polymarket_fetcher import PolymarketFetcher
fetcher = PolymarketFetcher()
markets = fetcher.fetch_political_markets()

# Kalshi data fetching (CFTC-regulated, US legal)
from pipelines.kalshi_fetcher import KalshiFetcher
kalshi = KalshiFetcher(api_key="your_key")  # or from .env
political = kalshi.fetch_political_markets()
economic = kalshi.fetch_economic_markets()

# Forecasting with belief tracking
from tracking.forecasting_db import ForecastingDatabase
db = ForecastingDatabase("data/betting.db")
fc_id = db.create_forecast(
    question_text="Will X happen?",
    platform="kalshi",
    initial_probability=0.35
)
db.record_revision(fc_id, new_probability=0.42,
                   revision_trigger="news_event")
```

---

## Domain Knowledge - CRITICAL CONTEXT

### Core Principle: CLV > Win Rate

**Closing Line Value is the PRIMARY success metric.** A bettor who consistently gets better odds
than closing lines WILL profit long-term, even through losing streaks. Track CLV religiously.

### Key Formulas

```python
# ===============================================================
# ODDS CONVERSIONS
# ===============================================================

def american_to_decimal(american: int) -> float:
    """Convert American odds to decimal odds"""
    if american > 0:
        return (american / 100) + 1
    return (100 / abs(american)) + 1

def american_to_implied_prob(american: int) -> float:
    """Convert American odds to implied probability"""
    if american > 0:
        return 100 / (american + 100)
    return abs(american) / (abs(american) + 100)

def decimal_to_american(decimal: float) -> int:
    """Convert decimal odds to American odds"""
    if decimal >= 2.0:
        return int((decimal - 1) * 100)
    return int(-100 / (decimal - 1))

# ===============================================================
# EXPECTED VALUE
# ===============================================================

def expected_value(win_prob: float, profit_if_win: float, stake: float) -> float:
    """
    Calculate expected value of a bet
    EV = (p * profit) - (q * stake)
    """
    return (win_prob * profit_if_win) - ((1 - win_prob) * stake)

def calculate_edge(model_prob: float, american_odds: int) -> float:
    """Calculate edge: model probability minus implied probability"""
    implied = american_to_implied_prob(american_odds)
    return model_prob - implied

# ===============================================================
# CLOSING LINE VALUE
# ===============================================================

def calculate_clv(odds_placed: int, odds_closing: int) -> float:
    """
    Calculate Closing Line Value
    Positive CLV = got better odds than market closed at
    THIS IS THE KEY PREDICTOR OF LONG-TERM PROFITABILITY
    """
    prob_placed = american_to_implied_prob(odds_placed)
    prob_closing = american_to_implied_prob(odds_closing)
    return (prob_closing - prob_placed) / prob_placed

# ===============================================================
# KELLY CRITERION
# ===============================================================

def fractional_kelly(
    win_prob: float,
    decimal_odds: float,
    fraction: float = 0.25,  # Quarter Kelly default
    max_bet: float = 0.03    # 3% max
) -> float:
    """
    Conservative fractional Kelly bet sizing
    ALWAYS use fractional Kelly - full Kelly is too aggressive
    """
    b = decimal_odds - 1
    q = 1 - win_prob

    if b <= 0:
        return 0.0

    kelly = (b * win_prob - q) / b
    recommended = max(0, kelly * fraction)
    return min(recommended, max_bet)

# ===============================================================
# ELO RATING SYSTEM
# ===============================================================

def elo_expected(rating_a: float, rating_b: float) -> float:
    """Calculate expected win probability for team A"""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

def elo_update(
    rating: float,
    expected: float,
    actual: float,  # 1=win, 0.5=tie, 0=loss
    k: int = 20
) -> float:
    """Update Elo rating after game result"""
    return rating + k * (actual - expected)

def elo_to_spread(elo_diff: float, points_per_elo: float = 25) -> float:
    """Convert Elo difference to predicted point spread"""
    return elo_diff / points_per_elo

def regress_to_mean(rating: float, mean: float = 1500, factor: float = 0.33) -> float:
    """Apply offseason regression to mean"""
    return mean + (rating - mean) * (1 - factor)
```

### Break-Even Win Rates

| American Odds | Implied Prob | Break-Even |
|---------------|--------------|------------|
| -110 | 52.38% | 52.38% |
| -105 | 51.22% | 51.22% |
| +100 | 50.00% | 50.00% |
| +150 | 40.00% | 40.00% |
| -200 | 66.67% | 66.67% |

### Market Inefficiency Priorities

| Priority | Market | Why |
|----------|--------|-----|
| 1 | Player props (all sports) | Highest inefficiency, lowest book limits |
| 2 | Small conference games (NCAAB/NCAAF) | Reduced coverage |
| 3 | Derivative markets (team totals, F5 lines) | Less sharp action |
| 4 | Main spreads/totals | Highly efficient, benchmark only |

---

## Bankroll & Risk Management

### Current Allocation

| Category | Amount | Notes |
|----------|--------|-------|
| **Total Bankroll** | $5,000 | |
| Active Capital | $4,000 | Distributed across sportsbooks |
| Reserve | $1,000 | Never touch |

### Sportsbook Distribution

| Book | Allocation | Purpose |
|------|------------|---------|
| DraftKings | $1,000 | Primary volume, props |
| FanDuel | $1,000 | Line shopping |
| BetMGM | $750 | Soft lines |
| Caesars | $750 | Line shopping |
| ESPN BET | $500 | Backup |

### Bet Sizing Rules (Dynamic Kelly)

Bets are sized using `KellySizer` (in `betting/odds_converter.py`) with Platt-calibrated
win probabilities. The calibrator fits a logistic regression on historical backtest
(edge, win/loss) data to correct ~10pp model overconfidence before feeding into Kelly.

| Parameter | Value | Notes |
|-----------|-------|-------|
| Kelly Fraction | 0.25 (Quarter) | Default; 0.33 for high confidence |
| Max Bet | 5% ($250) | Hard cap per bet |
| Min Bet | $10 | Below this, bet is skipped |
| Bankroll | $5,000 | Static paper bankroll |

```python
from betting.odds_converter import KellySizer, build_calibration_data
sizer = KellySizer(kelly_fraction=0.25, max_bet_fraction=0.05, bankroll=5000)
edges, outcomes = build_calibration_data("data/backtests")
sizer.calibrate(edges, outcomes)
stake = sizer.size_bet(model_prob=0.60, edge=0.15, american_odds=+180)
```

### Risk Limits

| Limit Type | Threshold | Action |
|------------|-----------|--------|
| Daily exposure | 20% ($1,000) | No new bets |
| Weekly loss | 25% ($1,250) | Reduce sizing 50% |
| Monthly loss | 40% ($2,000) | Pause, full review |

---

## Database Schema

```sql
-- Core bet tracking
CREATE TABLE bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sport TEXT NOT NULL,
    league TEXT,
    game_date DATE NOT NULL,
    game_id TEXT,

    -- Bet details
    bet_type TEXT NOT NULL,
    selection TEXT NOT NULL,
    line REAL,
    odds_placed INTEGER NOT NULL,
    odds_closing INTEGER,

    -- Model data
    model_probability REAL,
    model_edge REAL,

    -- Execution
    stake REAL NOT NULL,
    sportsbook TEXT NOT NULL,

    -- Results
    result TEXT,
    profit_loss REAL,
    clv REAL,

    -- Metadata
    notes TEXT,
    is_live BOOLEAN DEFAULT FALSE,

    UNIQUE(game_id, bet_type, selection, sportsbook)
);

-- Bankroll tracking
CREATE TABLE bankroll_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL UNIQUE,
    starting_balance REAL,
    ending_balance REAL,
    daily_pnl REAL,
    bets_placed INTEGER,
    bets_won INTEGER,
    bets_lost INTEGER,
    avg_clv REAL
);

-- Model predictions
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sport TEXT NOT NULL,
    game_id TEXT NOT NULL,
    game_date DATE NOT NULL,
    model_name TEXT NOT NULL,
    prediction_type TEXT,
    predicted_value REAL,
    market_value REAL,
    closing_value REAL,
    actual_value REAL,

    UNIQUE(game_id, model_name, prediction_type)
);

-- Team ratings
CREATE TABLE team_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    sport TEXT NOT NULL,
    season INTEGER NOT NULL,
    rating_type TEXT NOT NULL,
    rating_value REAL NOT NULL,
    as_of_date DATE NOT NULL,
    as_of_game_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(team_id, season, rating_type, as_of_date)
);
```

---

## Coding Standards

### Style

- Follow PEP 8
- Use type hints for all function signatures
- Docstrings for all public functions (Google style)
- Maximum line length: 100 characters

### Naming

- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Files: `snake_case.py`

### Testing Requirements

- All model calculations must have unit tests
- Backtest results must be reproducible (set random seeds)
- Test with edge cases: missing data, extreme odds, zero probabilities
- **All models must pass the Gatekeeper before deployment**

### Error Handling Pattern

```python
try:
    data = fetch_game_data(game_id)
except DataNotFoundError:
    logger.warning(f"Game {game_id} not found, skipping")
    return None
except APIRateLimitError:
    logger.error("API rate limit hit, waiting 60s")
    time.sleep(60)
    return fetch_game_data(game_id)
```

---

## Quick Start Commands

```bash
# ===============================================================
# ENVIRONMENT SETUP
# ===============================================================
cd ~/sports_betting
source venv/Scripts/activate  # Windows: venv\Scripts\activate

# ===============================================================
# DAILY WORKFLOW (Paper Betting)
# ===============================================================
python scripts/daily_run.py --dry-run       # Preview picks (no DB writes)
python scripts/daily_run.py                  # Full run: predict → record → settle → report
python scripts/daily_run.py --settle-only    # Settle yesterday's bets only
python scripts/daily_run.py --report-only    # Weekly performance report

# ===============================================================
# NIGHTLY REFRESH
# ===============================================================
python scripts/fetch_season_data.py --season 2026 --incremental --no-odds
python scripts/train_ncaab_elo.py --end 2026
python scripts/daily_run.py

# ===============================================================
# RUN BACKTESTS
# ===============================================================
python scripts/backtest_ncaab_elo.py --barttorvik --test-season 2025
python scripts/backtest_ncaab_elo.py --barttorvik --test-season 2025 --calibrated-kelly
python scripts/incremental_backtest.py --barttorvik

# ===============================================================
# VALIDATE MODEL BEFORE DEPLOYMENT
# ===============================================================
pytest tests/test_gatekeeper.py -v
python -c "from backtesting.validators import Gatekeeper; print('Validators loaded OK')"

# ===============================================================
# PERFORMANCE REPORT
# ===============================================================
python -c "from tracking.reports import weekly_report; weekly_report()"

# ===============================================================
# DASHBOARD
# ===============================================================
python scripts/generate_dashboard_data.py    # Regenerate data bundle
python -m http.server 8765                   # Serve at localhost:8765

# ===============================================================
# MLB PIPELINE (planned — skeleton files exist, implementation pending)
# ===============================================================
python scripts/mlb_init_db.py --seed-teams          # Create mlb_data.db + 30 teams
python scripts/mlb_fetch_historical.py --seasons 2023 2024 2025  # Bulk data
python scripts/mlb_fetch_projections.py --season 2026            # ZiPS + Steamer
python scripts/mlb_train_model.py --end-season 2025              # Poisson model
python scripts/mlb_backtest.py --test-season 2025                # Walk-forward
python scripts/mlb_daily_run.py --dry-run                        # Preview picks

# ===============================================================
# DATABASE ACCESS
# ===============================================================
sqlite3 data/betting.db      # Shared: bets, odds, bankroll, predictions
sqlite3 data/mlb_data.db     # MLB-specific: 14 tables, game_pk key
```

---

## Notes for Claude Code

### Personality & Approach

- Prefer clean, modular code over clever one-liners
- Always explain the "why" behind model choices
- Proactively flag potential overfitting or data leakage risks
- Suggest tests for any new functionality
- **Run Gatekeeper validation before approving any model for deployment**

### Domain Expertise Expected

- Understand sports betting fundamentals (odds, EV, CLV)
- Know the difference between sharp and soft books
- Recognize common modeling pitfalls (look-ahead bias, leakage)
- Understand walk-forward validation vs random cross-validation
- Know the 5-dimension validation framework and blocking checks

### When In Doubt

- Ask clarifying questions rather than assume
- Default to simpler implementations first
- Prioritize correctness over performance initially
- Always consider: "Could this leak future information?"
- **When model looks too good: Run the Gatekeeper**
