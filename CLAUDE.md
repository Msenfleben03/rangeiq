# Project: Sports Betting Model Development

## Overview

Build profitable projection models for NCAA Football, NCAA Basketball, NFL, and MLB
achieving positive ROI through systematic Closing Line Value (CLV) capture with zero startup costs.

## Quick Navigation

| Section | Content |
|---------|---------|
| [Tech Stack](#tech-stack) | Python libs, DBs, testing, linting |
| [Backtesting Validation Framework](#backtesting-validation-framework) | 5-dimension validator, Gatekeeper, blocking checks |
| [Project Structure](#project-structure) | File tree with descriptions |
| [Current Phase & Timeline](#current-phase--timeline) | Active tasks only |
| [Domain Knowledge](#domain-knowledge---critical-context) | CLV, formulas, market priorities |
| [Bankroll & Risk Management](#bankroll--risk-management) | Kelly sizing, risk limits |
| [Quick Start Commands](#quick-start-commands) | Daily pipeline, backtest, backup |
| [Notes for Claude Code](#notes-for-claude-code) | Approach, dead ends |

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

### Usage

See `backtesting/validators/gatekeeper.py` and `scripts/run_gatekeeper_validation.py`.
Key classes: `Gatekeeper`, `TemporalValidator`, `StatisticalValidator`, `OverfitValidator`, `BettingValidator`.

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
├── config/          # settings.py (DB paths, API keys), constants.py (thresholds)
├── data/
│   ├── ncaab_betting.db      # NCAAB: bets, odds, bankroll, predictions, barttorvik_ratings
│   ├── mlb_data.db           # MLB: games, pitchers, lineups, bets, odds (key: game_pk)
│   ├── raw/                  # Parquet files (ncaab_games_YYYY.parquet, mlb/)
│   ├── processed/            # Backtest results, dashboard JSON
│   └── external/             # Barttorvik scraped snapshots
├── models/
│   ├── elo.py                # Elo rating system
│   └── sport_specific/
│       ├── ncaab/team_ratings.py      # Elo + Barttorvik ensemble
│       └── mlb/poisson_model.py       # Poisson → ML/RL/totals/F5 (pitcher adj + Platt)
├── features/sport_specific/
│   ├── ncaab/advanced_features.py     # NCAABFeatureEngine
│   └── mlb/                           # pitcher, lineup, bullpen, weather, park, umpire
├── betting/
│   └── odds_converter.py     # devig_prob(), KellySizer, CLV, American↔decimal
├── backtesting/
│   ├── walk_forward.py       # Walk-forward validation engine
│   └── validators/           # 5-Dimension Framework: temporal, statistical, overfit, betting, gatekeeper
├── pipelines/                # ESPN fetchers, Barttorvik, MLB Stats API, odds providers, Kalshi/Polymarket
├── tracking/                 # BettingDatabase, logger, reports, ForecastingDatabase
├── scripts/                  # daily_run.py, mlb_daily_run.py, backtest, train, backup/restore, collect_closing_odds
├── tests/                    # 47 files, ~987 tests (test_logger: 8 known failures)
├── dashboards/ncaab_dashboard.html
└── docs/
    ├── DECISIONS.md           # 20+ cross-sport ADRs
    ├── DATA_DICTIONARY.md     # Full DB schema
    ├── RUNBOOK.md             # Daily/weekly/monthly ops
    ├── mlb/                   # DECISIONS.md, MODEL_ARCHITECTURE.md, PIPELINE_DESIGN.md, research/
    ├── plans/                 # Implementation plans (dated, per-feature)
    ├── user-how-to/           # PIPELINE_GUIDE.md (daily pipeline reference)
    └── CODEMAPS/              # Module-level architecture docs
```

---

## Current Phase & Timeline

### Status Dashboard

| Phase | Dates | Focus | Status |
|-------|-------|-------|--------|
| 1-2 | Jan 24 - Feb 6 | NCAAB foundation | Complete |
| 3-4 | Feb 7 - Feb 20 | NCAAB paper betting + automation | Complete |
| 5-6 | Feb 21 - Mar 6 | March Madness prep + MLB skeleton | Complete |
| 7-8 | Mar 7 - Mar 20 | Live testing (small stakes) + MLB data | In Progress |
| 9-10 | Mar 21 - Apr 3 | MLB model v1 + paper betting | Upcoming |

### Current Sprint Focus

**Completed milestones**: NCAAB Elo model (OOS flat ROI +27.09% pooled, p=0.0001, 5 seasons), 5-dim validator (198 tests),
historical odds backfill (91.6% coverage 2020-2025), Barttorvik integration, paper betting pipeline,
CLV collection system, Dynamic Kelly + Platt calibration, Task Scheduler automation, ESPN predictor
cross-check, MLB skeleton (47 files), MLB Poisson v1 (56.1% acc), F5 market, de-vig CLV fix,
per-sport DB split (ncaab_betting.db + mlb_data.db), GFS backup system,
K=32 tournament fix, closing odds collector, `.claude/` untracked from git,
MLB F5 Platt calibration, all seasons re-fetched with tournament data (2020-2025).

**Active tasks:**

- [ ] Begin live paper betting tracking (daily_run.py)
- [ ] Backfill 2026 odds (0% coverage currently)
- [ ] Schema overhaul Tasks 2-8 — `docs/plans/2026-03-05-schema-overhaul.md`
- [ ] NCAAB: K=32 tournament fix for March Madness (bracket drops Mar 15-16)

### Injury/Divergence System Overhaul

- [ ] Phase 1: Backtest ESPN divergence (2023-2025, ~18K games) — plan: `docs/plans/2026-02-28-injury-divergence-system.md`
- [ ] Phase 2: Graduated sizing (replace binary kill switch with data-driven curve)
- [ ] Phase 3: Injury data enrichment (ESPN injuries API + cross-reference sources)

### Prediction Markets Integration

- [x] Polymarket + Kalshi fetchers, forecasting schema (7 tables)
- [ ] Open Kalshi account (CFTC-regulated)
- [ ] Paper trade 50+ positions
- [ ] Achieve Brier score < 0.125

---

## Prediction Markets Module

Focus: Political/economic markets (3-10% CLV). Sports markets avoided — inferior to sportsbooks.

| Platform | Use Case | Fees |
|----------|----------|------|
| **Kalshi** | Primary (US legal, CFTC-regulated) | 1.2% |
| **Polymarket** | Data source | 0.01% |
| **PredictIt** | Benchmark only | 16% |

Targets: Brier score < 0.125, CLV > 3%, calibration error < 5%.
Superforecasting: outside view first, granular estimates (65% not "likely"), Bayesian updating with tracked revisions.
See `pipelines/kalshi_fetcher.py`, `pipelines/polymarket_fetcher.py`, `tracking/forecasting_db.py`.

---

## Domain Knowledge - CRITICAL CONTEXT

### Core Principle: CLV > Win Rate

**Closing Line Value is the PRIMARY success metric.** A bettor who consistently gets better odds
than closing lines WILL profit long-term, even through losing streaks. Track CLV religiously.

### Key Formulas

All implemented in `betting/odds_converter.py`: `american_to_implied_prob()`, `calculate_clv()`,
`devig_prob()`, `fractional_kelly()`, `KellySizer`. Elo formulas in `models/elo.py`.

**De-vig**: `fair_prob = raw_implied / (raw_home + raw_away)` — always apply before comparing to model prob.
**CLV**: `(prob_closing - prob_placed) / prob_placed` — positive = beat the market.
**Kelly**: `(b * p - q) / b * fraction` — use 0.25 fraction; full Kelly is too aggressive.

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

Full schema in `docs/DATA_DICTIONARY.md`. Key tables:

- **ncaab_betting.db**: `bets`, `bankroll_log`, `predictions`, `team_ratings`, `odds_snapshots`, `barttorvik_ratings`
- **mlb_data.db**: `games`, `game_pitchers`, `pitcher_stats`, `lineups`, `odds_snapshots`,
  `bets`, `predictions`, `park_factors` (primary key: `game_pk`)

Schema rebuilt via `BettingDatabase()` constructor in `tracking/database.py`. No `sport` column — file name identifies sport.

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
sqlite3 data/ncaab_betting.db  # NCAAB: bets, odds, bankroll, predictions, barttorvik_ratings
sqlite3 data/mlb_data.db       # MLB: games, pitchers, lineups, bets, predictions, odds (game_pk key)

# ===============================================================
# BACKUP & RESTORE
# ===============================================================
python scripts/backup_db.py              # GFS backup: both DBs → C:\Users\msenf\sports-betting-backups\
python scripts/backup_db.py --list       # List available backups
python scripts/backup_db.py --verify     # Verify latest backup integrity
python scripts/restore_db.py             # Restore all DBs from latest backup
python scripts/restore_db.py --date 2026-03-04  # Restore from specific date
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

### Known Dead Ends (do not revisit)

| Item | Reason |
|------|--------|
| `sportsipy` library | BROKEN since 2025 — use ESPN API |
| KenPom via cbbdata | Auth BLOCKED (upstream issue #14) — use kenpompy |
| `breadwinner.py` metric | DISABLED — no ROI correlation found |
| KenPom year-end as feature | 98.9% redundant with Barttorvik (session 9) |
| Hurst exponent / Jensen's alpha | Sample size too small / circular (session 7) |
| Barttorvik 2026 history before Feb 17 | Unrecoverable — scraping forward from Feb 17 |
| ECC Continuous Learning v2 | INCOMPATIBLE with Windows (session 8) |
| `test_logger.py` 8 failures | Pre-existing SQLite schema mismatch — known, not a blocker |
