# Tracking Module Codemap

**Last Updated:** 2026-03-11
**Entry Point:** `tracking/__init__.py` (empty)
**Test Coverage:** `tests/test_forecasting_db.py`, `tests/test_game_log.py`,
`tests/test_game_log_integration.py`, `tests/test_logger.py`, `tests/test_reports.py`,
`tests/test_settlement.py`

## Architecture

```text
tracking/
  __init__.py           # Empty package marker
  database.py           # SQLite connection management, schema creation (BettingDatabase)
  game_log.py           # Game log insert/settlement for all D1 games
  models.py             # SQLAlchemy ORM models (Team, Game, Bet, Prediction, etc.)
  logger.py             # Paper bet logging, validation, and batch operations
  reports.py            # Performance reports: daily, weekly, CLV, health, odds system
  forecasting_db.py     # Superforecasting prediction market DB interface
  cost_tracker.py       # Zero-cost enforcement and opportunity cost tracking
  doc_metrics.py        # Documentation health metrics and reporting
```

## Key Modules

### database.py

SQLite database management for the core betting tracking system.

| Export | Type | Purpose |
|--------|------|---------|
| `BettingDatabase` | class | Connection pooling, schema creation, context manager for transactions |

**Key Methods:**

- `__init__(db_path)` - Initialize and create schema if needed
- `get_cursor()` - Context manager yielding cursor with auto-commit/rollback
- `execute_query(sql, params)` - Execute query and return list of dicts
- `insert_bet(bet_data)` - Insert a bet record
- `update_bet_result(bet_id, result, profit_loss, clv)` - Update settled bet
- `insert_bankroll_entry(entry)` - Insert daily bankroll log
- `_initialize_schema()` - Creates all tables on first run

**Database:** `data/betting.db` (SQLite)

**Core Tables Created:**

- `bets` - Individual bet records (odds, stake, result, CLV, model_probability)
- `bankroll_log` - Daily balance tracking (starting/ending balance, daily PnL)
- `predictions` - Model prediction records (predicted vs actual values)
- `team_ratings` - Elo ratings by team, sport, season
- `games` - Game schedule and results
- `odds_snapshots` - Historical odds from multiple sportsbooks (`snapshot_type`: opening/closing/current)
- `game_log` - Every D1 game with model predictions, opening/closing odds, and results
- Plus additional tables (23 total in full schema)

### game_log.py

Game log tracking — records every D1 NCAAB game with predictions and odds.

| Export | Type | Purpose |
|--------|------|---------|
| `insert_game_log_entries(db_path, game_date, games, predictions, bets)` | function | Insert all games for a date (INSERT OR IGNORE) |
| `settle_game_log_entries(db_path, completed_games, closing_odds)` | function | Update scores, closing odds, and results for completed games |

**Dependencies:** sqlite3

### logger.py

Paper bet logging utilities with validation and batch operations.

| Export | Type | Purpose |
|--------|------|---------|
| `log_paper_bet(db, bet_data)` | function | Insert single paper bet (is_live=FALSE) |
| `log_multiple_bets(db, bets)` | function | Batch insert with error handling |
| `get_pending_bets(db, sport)` | function | Query unsettled bets |
| `get_bets_by_date(db, game_date, sport)` | function | Query bets for a specific date |
| `validate_bet_limits(bet_stake, db, bankroll_config)` | function | Check exposure limits |

**Validation Checks:**

1. Stake <= max bet (3% of bankroll)
2. Daily exposure <= 10% of bankroll
3. Required fields present (sport, game_date, bet_type, selection, odds_placed, stake, sportsbook)

**Dependencies:** config.constants (BANKROLL), tracking.database (BettingDatabase)

### reports.py

Performance reports and monitoring for the paper betting pipeline.

| Export | Type | Purpose |
|--------|------|---------|
| `daily_report(db, report_date)` | function | Daily P/L, win rate, CLV for a single date |
| `weekly_report(db, weeks)` | function | Rolling weekly: ROI, Sharpe ratio, CLV trend |
| `clv_analysis(db, days)` | function | CLV distribution, by bet type, daily trend |
| `model_health_check(db)` | function | Drift detection with CRITICAL/WARNING alerts |
| `odds_system_health(db)` | function | Provider success rates, stale data detection |

**Health Check Alerts:**

| Condition | Level | Action |
|-----------|-------|--------|
| CLV < 0 for 7+ days | CRITICAL | Review model predictions and odds accuracy |
| 5+ consecutive losses | WARNING | Reduce bet sizing by 50% |
| Win rate < 48% over 100 bets | WARNING | Review model calibration |

**Dependencies:** tracking.database (BettingDatabase)

### models.py

SQLAlchemy ORM models mirroring the SQL schema. All timestamps stored in UTC.

| Export | Type | Purpose |
|--------|------|---------|
| `Base` | class | SQLAlchemy DeclarativeBase |
| `Team` | class | Teams reference (team_id, sport, name, conference, division) |
| `Game` | class | Game records (home/away teams, scores, game_time) |
| `Bet` | class | Bet tracking (odds, stake, result, CLV, model data) |
| `Prediction` | class | Model predictions (predicted vs actual vs closing) |
| `TeamRating` | class | Elo ratings per team/season/type |
| `BankrollLog` | class | Daily balance and PnL tracking |
| `OddsSnapshot` | class | Point-in-time odds captures from sportsbooks |

**Relationships:**

- Team -> Game (home_games, away_games)
- Team -> TeamRating
- Game -> Bet, Prediction, OddsSnapshot

**Dependencies:** sqlalchemy

### forecasting_db.py

Superforecasting-methodology prediction market database interface based on Philip Tetlock's work.

| Export | Type | Purpose |
|--------|------|---------|
| `ForecastingDatabase` | class | CRUD for forecasts, revisions, calibration analysis |
| `Platform` | enum | POLYMARKET, KALSHI, PREDICTIT, METACULUS, MANIFOLD, PAPER, GJP |
| `QuestionCategory` | enum | GEOPOLITICS, ECONOMICS, SPORTS, TECHNOLOGY, SCIENCE, ELECTIONS, etc. |
| `RevisionTrigger` | enum | NEW_DATA, NEWS_EVENT, EXPERT_OPINION, MODEL_UPDATE, MARKET_MOVEMENT, etc. |

**Key Methods on ForecastingDatabase:**

- `create_forecast(question_text, platform, initial_probability, ...)` - New forecast
- `record_revision(forecast_id, new_probability, trigger, reasoning)` - Bayesian update
- `resolve_forecast(forecast_id, outcome)` - Record actual outcome
- `get_calibration(platform, category)` - Calibration analysis per bin
- `get_brier_scores(platform, category)` - Per-forecast Brier scores
- `get_revision_history(forecast_id)` - Full belief revision audit trail

**Forecasting Tables (7):**

- `forecasts` - Active and resolved forecasts
- `forecast_revisions` - Belief revision history (Bayesian tracking)
- `calibration_bins` - Pre-computed calibration statistics
- Plus supporting tables for platforms and categories

### cost_tracker.py

Enforces zero-cost data retrieval and tracks opportunity costs from stale data.

| Export | Type | Purpose |
|--------|------|---------|
| `CostTracker` | class | Monitors API costs, enforces zero-cost constraint |
| `CostViolationType` | enum | PAID_API, RATE_LIMIT_EXCEEDED, AUTH_REQUIRED, BILLING_HEADER, SUBSCRIPTION |
| `SLACategory` | enum | CLOSING_ODDS, MARKET_PRICES, TEAM_RATINGS, SCHEDULE_DATA, HISTORICAL_DATA |
| `SLADefinition` | dataclass | SLA parameters (max_age, edge_loss per violation) |

### doc_metrics.py

Documentation health tracking and quality metrics.

| Export | Type | Purpose |
|--------|------|---------|
| `DocumentationMetrics` | dataclass | Coverage, staleness, broken links, average age |
| `generate_coverage_report()` | function | Docstring coverage report across project |
| `find_stale_documentation(days)` | function | Find docs not updated in N days |

## Data Flow

```text
scripts/ (daily_predictions, record_paper_bets, settle_paper_bets)
     |
     +---> logger.py (log_paper_bet, validate_bet_limits)
     |         |
     |         +---> database.py (BettingDatabase)
     |                   |
     |                   +---> bets, predictions, team_ratings, odds_snapshots, bankroll_log
     |
     +---> reports.py (daily_report, weekly_report, clv_analysis, model_health_check)
               |
               +---> database.py (queries bets, odds_snapshots)

pipelines/ (fetchers, odds_orchestrator)
     |
     +---> database.py (BettingDatabase) -- store odds, predictions
     +---> forecasting_db.py (ForecastingDatabase) -- store forecasts
     +---> cost_tracker.py -- enforce zero-cost

backtesting/ (reads from database for validation)
     |
     +---> database.py (reads bets, predictions)
```

## External Dependencies

| Package | Used In | Purpose |
|---------|---------|---------|
| sqlite3 | database.py, forecasting_db.py, cost_tracker.py | Database access |
| sqlalchemy | models.py | ORM for typed database access |
| git (GitPython) | doc_metrics.py | File modification dates for staleness tracking |
| ast | doc_metrics.py | Python AST for docstring coverage analysis |
| config.constants | logger.py | BANKROLL limits for validation |

## Related Areas

- [pipelines.md](pipelines.md) - Fetchers write to database via tracking; odds_orchestrator stores to odds_snapshots
- [scripts.md](scripts.md) - All paper betting scripts depend on logger.py and reports.py
- [backtesting.md](backtesting.md) - Gatekeeper persists reports to data/ via tracking
- [config.md](config.md) - SLA definitions, rate limits, and bankroll config
