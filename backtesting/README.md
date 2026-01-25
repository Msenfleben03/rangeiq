# Backtesting Module

## Purpose

The backtesting module validates betting models through rigorous walk-forward testing, preventing overfitting and providing realistic performance estimates. It simulates historical betting to calculate CLV, ROI, Sharpe ratio, and drawdown metrics.

**Critical Principle**: Walk-forward validation only. Never use random cross-validation for time series betting data.

## Quick Start

```python
from backtesting.walk_forward import walk_forward_backtest
from models.elo import EloRating

# Run walk-forward backtest on NCAAB 2020-2025
results = walk_forward_backtest(
    model=EloRating(k_factor=20),
    data_path='data/processed/ncaab_2020_2025.csv',
    train_size=500,  # 500 games for training
    test_size=50,    # 50 games for testing
    step_size=25     # Move forward 25 games each iteration
)

# View results
print(f"Average CLV: {results['avg_clv']:.2%}")
print(f"ROI: {results['roi']:.2%}")
print(f"Win Rate: {results['win_rate']:.1%}")
print(f"Sharpe Ratio: {results['sharpe']:.2f}")
print(f"Max Drawdown: {results['max_drawdown']:.1%}")
```

## Components

### Walk-Forward Validation (`walk_forward.py`)

**Purpose**: Simulate realistic model deployment with expanding/rolling windows

**Key Functions**:

- `walk_forward_splits(df, train_size, test_size)`: Generate train/test splits
- `walk_forward_backtest(model, data)`: Complete backtest workflow

**Why Walk-Forward**:

```python
# Traditional CV (WRONG for time series):
# Train: [1,3,5,7,9], Test: [2,4,6,8,10] ❌
# This uses future data to predict past!

# Walk-Forward (CORRECT):
# Split 1 - Train: [1-100], Test: [101-110]
# Split 2 - Train: [1-110], Test: [111-120] ✅
# Always predicting forward in time
```

---

### Metrics (`metrics.py`)

**Key Metrics**:

- **CLV (Closing Line Value)**: Primary metric - are you beating the market?
- **ROI (Return on Investment)**: Total profit / total stakes
- **Win Rate**: Percentage of winning bets
- **Sharpe Ratio**: Risk-adjusted returns
- **Max Drawdown**: Largest peak-to-trough decline
- **Kelly Growth Rate**: Expected bankroll growth

**Usage**:

```python
from backtesting.metrics import calculate_roi, calculate_sharpe

roi = calculate_roi(bets_df['profit_loss'], bets_df['stake'])
sharpe = calculate_sharpe(bets_df['profit_loss'])
```

---

### Simulation (`simulation.py`)

**Purpose**: Monte Carlo simulation to estimate variance and probability of ruin

```python
from backtesting.simulation import monte_carlo_simulation

# Simulate 10,000 scenarios
scenarios = monte_carlo_simulation(
    avg_clv=0.01,       # 1% average CLV
    num_bets=1000,      # 1000 bets
    bet_size=0.02,      # 2% Kelly
    num_simulations=10000
)

# Probability of doubling bankroll
prob_double = (scenarios['final_bankroll'] > 2.0).mean()
# Probability of losing 50%
prob_ruin = (scenarios['final_bankroll'] < 0.5).mean()
```

## Common Patterns

### Pattern 1: Complete Backtest Workflow

```python
from backtesting.walk_forward import walk_forward_splits
from models.elo import EloRating
from betting.clv import calculate_clv

# Load historical data
df = pd.read_csv('data/processed/ncaab_2020_2025.csv')
df = df.sort_values('date')

# Initialize model
elo = EloRating(k_factor=20)

# Storage for results
all_predictions = []

# Walk-forward loop
for train_df, test_df in walk_forward_splits(df, train_size=500, test_size=50):
    # Train model on historical data
    elo.fit(train_df)

    # Make predictions on test set
    for _, game in test_df.iterrows():
        pred_prob = elo.predict_game(game['home_team'], game['away_team'])

        all_predictions.append({
            'game_id': game['game_id'],
            'predicted_prob': pred_prob,
            'actual_result': game['home_win'],
            'market_odds': game['market_odds'],
            'closing_odds': game['closing_odds']
        })

# Calculate performance metrics
predictions_df = pd.DataFrame(all_predictions)
avg_clv = predictions_df.apply(
    lambda row: calculate_clv(row['market_odds'], row['closing_odds']),
    axis=1
).mean()
```

### Pattern 2: Avoiding Overfitting

```python
# ❌ WRONG: Tuning hyperparameters on test set
best_k = None
best_roi = -np.inf
for k in range(10, 40):
    elo = EloRating(k_factor=k)
    roi = backtest(elo, test_data)  # Using test data!
    if roi > best_roi:
        best_roi = roi
        best_k = k

# ✅ CORRECT: Use validation set separate from final test
for k in range(10, 40):
    elo = EloRating(k_factor=k)
    roi = backtest(elo, validation_data)  # Tune on validation
    if roi > best_roi:
        best_k = k

# Final evaluation on unseen test set
final_elo = EloRating(k_factor=best_k)
final_roi = backtest(final_elo, test_data)
```

### Pattern 3: Realistic Bet Sizing

```python
from betting.kelly import fractional_kelly

# Simulate betting with Kelly criterion
bankroll = 1000.0
for _, game in test_df.iterrows():
    # Get prediction
    model_prob = elo.predict_game(game['home_team'], game['away_team'])

    # Calculate bet size
    kelly_pct = fractional_kelly(model_prob, game['decimal_odds'], fraction=0.25)
    bet_amount = bankroll * kelly_pct

    # Place bet and update bankroll
    if game['home_win']:
        profit = bet_amount * (game['decimal_odds'] - 1)
    else:
        profit = -bet_amount

    bankroll += profit
```

## Testing

```bash
pytest tests/test_backtesting.py -v
pytest tests/test_backtesting.py::test_walk_forward_splits -v
pytest tests/test_backtesting.py::test_no_leakage -v --timeout=300
```

## References

- [ADR-002: Walk-Forward Validation](../docs/DECISIONS.md#adr-002)
- [CLAUDE.md: Backtesting Guidelines](../CLAUDE.md#backtesting)
- Related: `models/` (models to backtest), `betting/` (sizing and decisions)

---

**Maintained by**: Quantitative Research Team
**Last Updated**: 2026-01-24
**Status**: ✅ Active - Critical Infrastructure
