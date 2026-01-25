# Tracking Module

## Purpose

The tracking module manages the SQLite database, ORM models, bet logging, and performance reporting for the sports betting system. It provides persistent storage for predictions, bets, ratings, and bankroll history.

## Quick Start

```python
from tracking.database import init_database, get_session
from tracking.models import Bet, TeamRating, BankrollLog

# Initialize database (first time only)
init_database()

# Create database session
session = get_session()

# Log a new bet
bet = Bet(
    sport='ncaab',
    game_id='ncaab_20260125_duke_unc',
    bet_type='spread',
    selection='duke',
    line=-3.5,
    odds_placed=-110,
    stake=100.0,
    sportsbook='draftkings',
    model_probability=0.58
)
session.add(bet)
session.commit()

# Query bet history
recent_bets = session.query(Bet).filter(Bet.sport == 'ncaab').limit(10).all()
```

## Components

### Database Management (`database.py`)

- `init_database()`: Create tables from schema
- `get_session()`: Get SQLAlchemy session
- Database connection pooling and error handling

### ORM Models (`models.py`)

**Existing Tables**:

- `Bet`: Individual bet records with CLV tracking
- `BankrollLog`: Daily bankroll snapshots
- `Prediction`: Model predictions for validation
- `TeamRating`: Elo and other rating systems
- `Game`: Game reference data

See `scripts/init_database.sql` for complete schema.

### Performance Reporting (`reports.py`)

- `weekly_report()`: CLV, ROI, win rate summary
- `monthly_summary()`: Long-term performance trends
- `model_comparison()`: Compare different model performance

## Common Patterns

### Pattern 1: Logging Bets

```python
from tracking.logger import log_bet

log_bet(
    game_id='ncaab_20260125_duke_unc',
    bet_type='spread',
    selection='duke',
    odds=-110,
    stake=100.0,
    model_prob=0.58
)
```

### Pattern 2: Updating Bet Results

```python
from tracking.database import get_session
from tracking.models import Bet

session = get_session()

# Update bet after game completes
bet = session.query(Bet).filter_by(game_id='ncaab_20260125_duke_unc').first()
bet.result = 'win'
bet.profit_loss = 90.91  # $100 at -110 odds
bet.odds_closing = -115  # Closing line
bet.clv = calculate_clv(-110, -115)
session.commit()
```

### Pattern 3: CLV Analysis

```python
import pandas as pd

# Query all completed bets
bets = pd.read_sql(
    "SELECT * FROM bets WHERE result IS NOT NULL",
    get_session().bind
)

# Calculate CLV statistics
avg_clv = bets['clv'].mean()
positive_clv_rate = (bets['clv'] > 0).mean()

print(f"Average CLV: {avg_clv:.2%}")
print(f"Positive CLV Rate: {positive_clv_rate:.1%}")
```

## Testing

```bash
pytest tests/test_tracking.py -v
pytest tests/test_tracking.py::test_database_schema -v
```

## References

- [Database Schema](../scripts/init_database.sql)
- [CLAUDE.md: Database Schema](../CLAUDE.md#database-schema)
- Related: `betting/` (generates bet decisions), `pipelines/` (automates logging)

---

**Maintained by**: Data Infrastructure Team
**Last Updated**: 2026-01-24
**Status**: ✅ Active - Production Ready
