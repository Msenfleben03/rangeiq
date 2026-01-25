# Quick Start Guide

## ✅ Environment Setup Complete

Your sports betting development environment is fully configured and tested.

## 🔍 What's Ready

### 1. Database System

```bash
# Verified: SQLite database initialized
Location: data/betting.db
Tables: 15+ tables for bets, predictions, ratings, bankroll tracking
```

### 2. Core Utilities

```bash
# Verified: Odds conversion and betting calculations
✅ American ↔ Decimal ↔ Implied Probability
✅ Expected Value calculation
✅ Closing Line Value (CLV) tracking
✅ Fractional Kelly bet sizing
```

### 3. Configuration

```bash
# Verified: Bankroll and risk management settings
Bankroll: $5,000 total ($4,000 active, $1,000 reserve)
Risk Limits: 3% max bet, 10% daily exposure
Kelly Sizing: Quarter Kelly (0.25 fraction)
```

### 4. Data Pipeline

```bash
# Ready: NCAAB data fetcher using sportsipy
Features: Team stats, game results, multi-season support
Rate Limiting: 1s delay between requests
Output Format: Parquet for efficient storage
```

## 🚀 Next Steps

### Option 1: Fetch Historical Data (Recommended First)

```python
# Activate environment
./venv/Scripts/activate

# Run data fetcher
./venv/Scripts/python -c "
from pipelines.ncaab_data_fetcher import NCAABDataFetcher

fetcher = NCAABDataFetcher()
# Fetch 2024 season (2023-24)
data = fetcher.fetch_season_data(2024, delay=1.0)
print(f'Fetched {len(data)} games')
"
```

**Note**: This will take 5-10 minutes due to rate limiting. Each team's schedule is fetched with a 1-second delay to avoid overwhelming the API.

### Option 2: Build Elo Rating Model

Create `models/sport_specific/ncaab/elo.py`:

```python
"""
NCAAB Elo Rating System

Implements Elo ratings for NCAA Basketball with:
- Margin of victory adjustment
- Home court advantage
- Offseason regression to mean
"""

def elo_expected(rating_a: float, rating_b: float, home_advantage: float = 100) -> float:
    """Calculate expected win probability for team A"""
    adjusted_a = rating_a + home_advantage
    return 1 / (1 + 10 ** ((rating_b - adjusted_a) / 400))

def elo_update(
    rating: float,
    expected: float,
    actual: float,
    k: int = 20,
    margin: int = 0
) -> float:
    """
    Update Elo rating after game.

    Args:
        rating: Current Elo rating
        expected: Expected win probability
        actual: Actual result (1=win, 0=loss)
        k: K-factor (update rate)
        margin: Point margin (for MOV adjustment)
    """
    # Base update
    base_update = k * (actual - expected)

    # Margin of victory multiplier
    if margin > 0:
        mov_multiplier = (margin + 3) ** 0.8 / (7.5 + 0.006 * (rating - 1500))
        base_update *= mov_multiplier

    return rating + base_update
```

### Option 3: Test Betting Calculations

```python
from betting.odds_converter import *

# Example: You think Duke has 58% chance to win
# Market offers -110 (implied 52.4%)

model_prob = 0.58
market_odds = -110

edge = calculate_edge(model_prob, market_odds)
print(f"Edge: {edge:.2%}")  # Should show ~5.6% edge

# Calculate bet size
decimal_odds = american_to_decimal(market_odds)
bet_pct = fractional_kelly(model_prob, decimal_odds, fraction=0.25)
print(f"Recommended bet: {bet_pct:.1%} of bankroll")  # ~3% of bankroll

# If you placed at -105 and it closed at -110
clv = calculate_clv(-105, -110)
print(f"CLV: {clv:.2%}")  # 2.27% CLV - excellent!
```

## 📊 Verification Checklist

Run these commands to verify everything works:

```bash
# Activate environment
./venv/Scripts/activate

# Test Python packages
python -c "import pandas, numpy, scipy, sklearn, sportsipy; print('✅ Packages OK')"

# Test database
python tracking/database.py

# Test betting utilities
python betting/odds_converter.py

# Test configuration
python config/settings.py

# Optional: Run tests (if you create test files)
# pytest tests/
```

## 💡 Development Tips

### Using Claude-Flow Memory

Store important findings and decisions:

```bash
# Store a decision
npx @claude-flow/cli@latest memory store -k "elo_k_factor" -v "Using K=20 for NCAAB based on backtesting" -n "betting/decisions"

# Query past decisions
npx @claude-flow/cli@latest memory query "elo" -n "betting/decisions"

# List all stored items
npx @claude-flow/cli@latest memory list -n "betting/decisions"
```

### Database Queries

```bash
# Open database
sqlite3 data/betting.db

# View tables
.tables

# Sample queries
SELECT * FROM team_ratings LIMIT 10;
SELECT * FROM bets WHERE result = 'win' ORDER BY clv DESC LIMIT 5;
.exit
```

### Jupyter Notebooks

For exploration and analysis:

```bash
# Start Jupyter
jupyter lab

# Navigate to notebooks/exploration/
# Create a new notebook
# Select kernel: sports_betting (Python 3.14)
```

## 🎯 Recommended Workflow

1. **Week 1**: Fetch historical data (2020-2024 seasons)
2. **Week 2**: Build and backtest Elo model
3. **Week 3**: Paper trading (track bets without money)
4. **Week 4**: Model refinement based on paper results
5. **Week 5+**: Small stakes live betting

## 📈 Success Metrics

Track these in your database:

| Metric | Target | Frequency |
|--------|--------|-----------|
| CLV | > 1% | Every bet |
| Closing Line Beat % | > 55% | Weekly |
| ROI | > 2% | Monthly |
| Sample Size | 50+ bets | Before live |

## ⚠️ Important Reminders

1. **Never skip CLV tracking** - It's the only metric that predicts long-term success
2. **Use paper trading first** - Get 50+ bets before risking real money
3. **Respect bankroll limits** - 3% max bet, 10% daily exposure
4. **Walk-forward validation** - Never backtest on future data
5. **Check for data leakage** - Always use `.shift(1)` on rolling calculations

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| Import errors | Ensure virtual environment is activated |
| Database locked | Close any SQLite browser windows |
| API rate limits | Increase delay parameter in fetcher |
| Memory errors | Fetch data in smaller chunks (season by season) |

## 📚 Next Documentation

- Create `docs/DATA_DICTIONARY.md` - Define all database fields
- Create `docs/DECISIONS.md` - Track architectural choices
- Create `docs/RUNBOOK.md` - Daily/weekly operations

---

**Ready to build! Start with data fetching or Elo model development.**
