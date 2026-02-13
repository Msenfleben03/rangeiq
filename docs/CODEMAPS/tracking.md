# Tracking Module Codemap

**Last Updated:** 2026-02-12
**Entry Point:** `tracking/__init__.py` (empty)
**Test Coverage:** `tests/test_forecasting_db.py`

## Architecture

```text
tracking/
  __init__.py           # Empty package marker
  database.py           # SQLite connection management, schema creation (BettingDatabase)
  models.py             # SQLAlchemy ORM models (Team, Game, Bet, Prediction, etc.)
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
- `_initialize_schema()` - Creates all tables on first run

**Database:** `data/betting.db` (SQLite)

**Core Tables Created:**

- `bets` - Individual bet records (odds, stake, result, CLV, model_probability)
- `bankroll_log` - Daily balance tracking (starting/ending balance, daily PnL)
- `predictions` - Model prediction records (predicted vs actual values)
- `team_ratings` - Elo ratings by team, sport, season
- `games` - Game schedule and results
- `odds_snapshots` - Historical odds from multiple sportsbooks
- Plus additional tables (22 total in full schema)

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

**Key Principles:**

1. Zero-cost is NON-NEGOTIABLE - reject any paid API calls
2. Opportunity cost = edge_loss x bet_frequency x avg_stake
3. SLA violations accumulate quantifiable costs

**SLA Thresholds (from config/settings.py):**

- Closing odds: 15 min max age, 10% edge loss per violation
- Market prices: 5 min max age, 2% edge loss
- Team ratings: 1 day max age, 0.5% edge loss
- Schedule data: 6 hours max age, 0.1% edge loss
- Historical data: 7 days max age, 0.01% edge loss

### doc_metrics.py

Documentation health tracking and quality metrics.

| Export | Type | Purpose |
|--------|------|---------|
| `DocumentationMetrics` | dataclass | Coverage, staleness, broken links, average age |
| `generate_coverage_report()` | function | Docstring coverage report across project |
| `find_stale_documentation(days)` | function | Find docs not updated in N days |

**Dependencies:** ast (for AST analysis of docstrings), git (GitPython for file ages)

## Data Flow

```text
pipelines/ (fetchers)
     |
     +---> database.py (BettingDatabase)
     |         |
     |         +---> bets, predictions, team_ratings, odds_snapshots, ...
     |
     +---> forecasting_db.py (ForecastingDatabase)
     |         |
     |         +---> forecasts, forecast_revisions, calibration_bins, ...
     |
     +---> cost_tracker.py
               |
               +---> sla_violations, cost_events (monitoring)

backtesting/ (reads from database for validation)
     |
     +---> database.py (reads bets, predictions)

scripts/ (daily_run, reports)
     |
     +---> database.py + forecasting_db.py (reads/writes)
```

## External Dependencies

| Package | Used In | Purpose |
|---------|---------|---------|
| sqlite3 | database.py, forecasting_db.py, cost_tracker.py | Database access |
| sqlalchemy | models.py | ORM for typed database access |
| git (GitPython) | doc_metrics.py | File modification dates for staleness tracking |
| ast | doc_metrics.py | Python AST for docstring coverage analysis |

## Related Areas

- [pipelines.md](pipelines.md) - Fetchers write to database via tracking
- [backtesting.md](backtesting.md) - Gatekeeper persists reports to data/ via tracking
- [config.md](config.md) - SLA definitions and rate limits
- [scripts.md](scripts.md) - Daily run and setup scripts interact with database
