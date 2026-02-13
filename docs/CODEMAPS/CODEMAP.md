# Sports Betting Project - Codemap Index

**Last Updated:** 2026-02-12
**Project Root:** `C:\Users\msenf\sports-betting`
**Language:** Python 3.11+
**Testing:** pytest
**Database:** SQLite (data/betting.db)

## Architecture Overview

```text
                          +-------------------+
                          |   scripts/        |
                          |   (12 entry pts)  |
                          +--------+----------+
                                   |
                    +--------------+--------------+
                    |                             |
              +-----v-----+              +-------v-------+
              | pipelines/ |              |   models/     |
              | (data +    |              | (predictions  |
              |  odds in)  |              |  + persist)   |
              +-----+------+              +-------+-------+
                    |                             |
                    v                             v
              +----------+                +-------+-------+
              | tracking/|<---------------| backtesting/  |
              | (storage |                | (validation)  |
              |  + logs  |                +-------+-------+
              |  + rpts) |                        |
              +-----+----+                        |
                    +----------+------------------+
                               |
                    +----------v-----------+
                    |  betting/            |
                    |  (odds, EV, Kelly)   |
                    +----------+-----------+
                               |
                    +----------v-----------+
                    |  config/             |
                    |  (constants, paths)  |
                    +----------------------+
```

## Module Codemaps

| Module | Codemap | Files | Purpose |
|--------|---------|-------|---------|
| backtesting/ | [backtesting.md](backtesting.md) | 10 | Walk-forward validation, metrics, simulation, 5-dimension validator framework |
| betting/ | [betting.md](betting.md) | 3 | Odds conversion, EV/CLV calculations, Kelly criterion, arbitrage detection |
| config/ | [config.md](config.md) | 3 | Global settings, sport-specific constants, sportsbook configuration, OddsConfig |
| models/ | [models.md](models.md) | 9 | Elo rating system (base + sport-specific), model persistence (save/load/export) |
| pipelines/ | [pipelines.md](pipelines.md) | 8 | Data fetching (NCAAB, Polymarket, Kalshi), odds providers (4 strategies), orchestrator |
| tracking/ | [tracking.md](tracking.md) | 8 | SQLite database, ORM, bet logger, performance reports, forecasting DB, cost tracking |
| features/ | [features.md](features.md) | 2 | Feature engineering and selection (placeholder modules) |
| tests/ | [tests.md](tests.md) | 15 | pytest suite: 458 tests covering validators, models, betting, tracking, pipelines |
| scripts/ | [scripts.md](scripts.md) | 12 | Full 6-phase paper betting pipeline + utilities |

## Data Flow — Paper Betting Pipeline

```text
Phase 1 - DATA:
  scripts/fetch_historical_data.py -> data/raw/ncaab/*.parquet

Phase 1 - TRAIN:
  scripts/train_ncaab_elo.py -> data/processed/ncaab_elo_model.pkl
                              -> data/processed/ncaab_elo_ratings_current.csv
                              -> team_ratings (SQLite)

Phase 3 - BACKTEST:
  scripts/backtest_ncaab_elo.py -> data/backtests/ncaab_elo_backtest_*.parquet

Phase 3 - VALIDATE:
  scripts/run_gatekeeper_validation.py -> data/validation/*_gatekeeper_report.json
    [TEMPORAL -> STATISTICAL -> OVERFIT -> BETTING -> GATEKEEPER -> PASS/QUARANTINE]

Phase 4 - PREDICT (daily morning):
  scripts/daily_predictions.py
    models/model_persistence.py (load) -> predictions
    pipelines/odds_orchestrator.py (fetch odds) -> odds_snapshots
    betting/odds_converter.py (edge + Kelly) -> bet recommendations

Phase 5 - BET (daily morning):
  scripts/record_paper_bets.py
    tracking/logger.py (validate + insert) -> bets table

Phase 5 - SETTLE (daily evening):
  scripts/settle_paper_bets.py
    tracking/logger.py (get_pending) -> results
    pipelines/odds_orchestrator.py (closing odds) -> CLV
    models/model_persistence.py (update + save) -> bets + bankroll_log

Phase 6 - REPORT:
  scripts/generate_report.py
    tracking/reports.py (daily, weekly, CLV, health) -> console output
```

## Dependency Graph (Key Imports)

```text
config/constants.py
  <- models/elo.py
  <- models/sport_specific/ncaab/team_ratings.py
  <- tracking/logger.py (BANKROLL)
  <- scripts/*.py (BANKROLL, ELO, THRESHOLDS, ODDS_CONFIG)

config/settings.py
  <- scripts/*.py (paths, DATABASE_PATH, ODDS_API_KEY)
  <- tracking/database.py (DATABASE_PATH)

betting/odds_converter.py
  <- backtesting/metrics.py, simulation.py, validators/betting_validator.py
  <- betting/arb_detector.py
  <- pipelines/arb_scanner.py
  <- scripts/daily_predictions.py, backtest_ncaab_elo.py, settle_paper_bets.py

models/elo.py
  <- models/sport_specific/ncaab/team_ratings.py

models/model_persistence.py
  <- scripts/train_ncaab_elo.py, backtest_ncaab_elo.py, settle_paper_bets.py, daily_predictions.py

pipelines/odds_providers.py
  <- pipelines/odds_orchestrator.py

pipelines/odds_orchestrator.py
  <- scripts/daily_predictions.py, settle_paper_bets.py

tracking/logger.py
  <- scripts/record_paper_bets.py, settle_paper_bets.py

tracking/reports.py
  <- scripts/generate_report.py

tracking/database.py
  <- tracking/logger.py, tracking/reports.py
  <- scripts/*.py (all pipeline scripts)
  <- pipelines/ (various fetchers store data here)

backtesting/validators/*.py
  <- backtesting/validators/__init__.py
  <- backtesting/validators/gatekeeper.py (imports all validators)
  <- scripts/run_gatekeeper_validation.py
```

## Key Patterns

1. **Immutable Data Classes** - All result containers use `@dataclass` (frozen where appropriate)
2. **Protocol-Based Models** - `BaseModel` protocol defines fit/predict interface
3. **Pipeline Pattern** - Raw Model -> Temporal -> Statistical -> Overfit -> Betting -> Gatekeeper
4. **CLV-First Design** - Closing Line Value is the primary metric throughout
5. **Zero-Cost Enforcement** - All data sources must be free; paid APIs are blocked
6. **Strategy Pattern (Odds)** - 4 interchangeable providers behind OddsProvider ABC
7. **Fallback Chain** - OddsOrchestrator auto-cascades: API -> ESPN -> Scraper -> Cache
8. **Credit Budget** - The Odds API credits tracked in `data/odds_api_usage.json` (500/month)

## Quick Reference

```python
# Daily workflow
python scripts/daily_predictions.py --date today           # Morning: predict
python scripts/record_paper_bets.py --date today            # Morning: record bets
python scripts/settle_paper_bets.py --date today            # Evening: settle
python scripts/generate_report.py --daily --odds-health     # Evening: review

# Validate a model before deployment
from backtesting.validators import Gatekeeper, GateDecision
gk = Gatekeeper()
gk.load_validators()
report = gk.generate_report("model_name", results, metadata)

# Convert odds and calculate edge
from betting import american_to_decimal, calculate_edge, fractional_kelly

# Load trained model
from models.model_persistence import load_model
saved = load_model("data/processed/ncaab_elo_model.pkl")
model = saved.model

# Fetch odds
from pipelines.odds_orchestrator import OddsOrchestrator
orchestrator = OddsOrchestrator(db=db)
orchestrator.register_default_providers()
odds = orchestrator.fetch_odds("ncaab", "Duke", "UNC", "game123")
```
