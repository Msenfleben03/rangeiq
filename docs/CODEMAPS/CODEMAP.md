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
                          |   (entry points)  |
                          +--------+----------+
                                   |
                    +--------------+--------------+
                    |                             |
              +-----v-----+              +-------v-------+
              | pipelines/ |              |   models/     |
              | (data in)  |              | (predictions) |
              +-----+------+              +-------+-------+
                    |                             |
                    v                             v
              +----------+                +-------+-------+
              | tracking/|<---------------| backtesting/  |
              | (storage)|                | (validation)  |
              +-----+----+                +-------+-------+
                    |                             |
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
| config/ | [config.md](config.md) | 3 | Global settings, sport-specific constants, sportsbook configuration |
| models/ | [models.md](models.md) | 8 | Elo rating system (base + sport-specific), model protocols |
| pipelines/ | [pipelines.md](pipelines.md) | 6 | Data fetching (NCAAB, Polymarket, Kalshi), batch processing, closing odds |
| tracking/ | [tracking.md](tracking.md) | 6 | SQLite database, SQLAlchemy ORM, forecasting DB, cost tracking |
| features/ | [features.md](features.md) | 2 | Feature engineering and selection (placeholder modules) |
| tests/ | [tests.md](tests.md) | 10 | pytest suite covering validators, models, betting, forecasting |
| scripts/ | [scripts.md](scripts.md) | 4 | Database setup, validation runners, maintenance utilities |

## Data Flow

```text
1. INGEST:   pipelines/ fetches data -> tracking/database.py stores to SQLite
2. MODEL:    models/ reads historical data -> generates predictions
3. VALIDATE: backtesting/ runs walk-forward validation -> 5-dimension checks
4. GATE:     backtesting/validators/gatekeeper.py -> PASS/QUARANTINE decision
5. BET:      betting/ calculates EV, CLV, Kelly sizing -> tracking/ logs bets
6. MONITOR:  tracking/ generates reports -> scripts/ runs daily workflow
```

## Dependency Graph (Key Imports)

```text
config/constants.py
  <- models/elo.py
  <- models/sport_specific/ncaab/team_ratings.py

betting/odds_converter.py
  <- backtesting/metrics.py
  <- backtesting/simulation.py
  <- backtesting/validators/betting_validator.py
  <- betting/arb_detector.py
  <- pipelines/arb_scanner.py

models/elo.py
  <- models/sport_specific/ncaab/team_ratings.py

backtesting/validators/*.py
  <- backtesting/validators/__init__.py
  <- backtesting/__init__.py
  <- backtesting/validators/gatekeeper.py (imports all validators)

tracking/database.py
  <- pipelines/ (various fetchers store data here)
```

## Key Patterns

1. **Immutable Data Classes** - All result containers use `@dataclass` (frozen where appropriate)
2. **Protocol-Based Models** - `BaseModel` protocol defines fit/predict interface
3. **Pipeline Pattern** - Raw Model -> Temporal -> Statistical -> Overfit -> Betting -> Gatekeeper
4. **CLV-First Design** - Closing Line Value is the primary metric throughout
5. **Zero-Cost Enforcement** - All data sources must be free; paid APIs are blocked

## Quick Reference

```python
# Validate a model before deployment
from backtesting.validators import Gatekeeper, GateDecision
gk = Gatekeeper()
gk.load_validators()
report = gk.generate_report("model_name", results, metadata)

# Convert odds and calculate edge
from betting import american_to_decimal, calculate_edge, fractional_kelly

# Run walk-forward validation
from backtesting import WalkForwardValidator
validator = WalkForwardValidator(train_window_days=180, test_window_days=30)

# Get NCAAB predictions
from models.sport_specific.ncaab.team_ratings import NCAABEloModel
model = NCAABEloModel()
```
