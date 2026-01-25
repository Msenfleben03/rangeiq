# Models Module

## Purpose

The models module provides the core prediction framework for sports betting, implementing various rating systems and statistical models to generate win probabilities and point spreads. This module follows a "simple to complex" approach, starting with interpretable baseline models (Elo) before progressing to advanced machine learning techniques.

**Design Philosophy**:

- Start simple, add complexity only when justified by backtest results
- Prioritize interpretability and debugging over black-box accuracy
- Focus on Closing Line Value (CLV) as primary success metric
- Prevent data leakage through careful temporal validation

## Quick Start

```python
# Example: Basic Elo rating system for NCAAB
from models.elo import EloRating

# Initialize Elo system with sport-specific parameters
elo = EloRating(
    k_factor=20,           # NCAAB standard K-factor
    base_rating=1500.0,    # Starting rating for new teams
    home_advantage=100.0   # ~3-4 point spread equivalent
)

# Update ratings after a game
elo.update_rating(
    team_id='duke',
    expected_prob=0.65,    # Pre-game win probability
    actual=1.0,            # 1.0 = win, 0.0 = loss, 0.5 = tie
    margin=8               # Point differential (optional, for MOV models)
)

# Get current rating
rating = elo.get_rating('duke')  # Returns: 1508.0

# Predict upcoming game
win_prob = elo.predict_game(
    home_team='duke',
    away_team='unc',
    neutral_site=False
)
print(f"Duke win probability: {win_prob:.1%}")  # Output: Duke win probability: 64.2%
```

## Installation

Models module dependencies are included in main requirements.txt:

```bash
pip install -r requirements.txt
```

Required packages:

- pandas, numpy, scipy (core data science)
- scikit-learn (regression models, feature selection)
- statsmodels (statistical models, GLMs)

Optional (uncomment in requirements.txt when ready):

- xgboost, lightgbm (gradient boosting models)

## Components

### Base Model Framework

#### `base.py` (Planned)

**Purpose**: Abstract base class for all prediction models

**Key Methods**:

- `fit(data)`: Train model on historical data
- `predict(features)`: Generate predictions
- `evaluate(test_data)`: Calculate performance metrics
- `save(path)`: Serialize model
- `load(path)`: Load saved model

**Gotchas**:

- Always use walk-forward validation, never random cross-validation
- Ensure features are shifted to prevent look-ahead bias
- Track CLV, not just accuracy

---

### Elo Rating System

#### `elo.py` (Planned)

**Purpose**: Elo-based team strength ratings with sport-specific adjustments

**Features**:

- Real-time rating updates after each game
- Home field advantage adjustment
- Seasonal regression to mean
- Margin of victory (MOV) weighting (optional)

**Usage**:

```python
from models.elo import EloRating, EloMOV

# Standard Elo (binary win/loss)
elo = EloRating(k_factor=20)

# Elo with margin of victory
lo_mov = EloMOV(
    k_factor=20,
    mov_multiplier=0.1  # How much MOV affects rating change
)
```

**Sport-Specific K-Factors**:

- NCAAB: 20-32 (volatile, many upsets)
- NCAAF: 25-30
- NFL: 20-25 (fewer games, higher variance)
- MLB: 4-8 (162 games, revert to mean faster)

**References**:

- ADR-001: Why Elo Before Complex Models
- FiveThirtyEight NFL Elo: https://fivethirtyeight.com/methodology/

---

### Regression Models

#### `regression.py` (Planned)

**Purpose**: Linear and logistic regression for spread/total predictions

**Models**:

- `LinearSpreadModel`: Predict point spreads
- `LogisticWinModel`: Binary win/loss classification
- `TotalPointsModel`: Over/under predictions

**Usage**:

```python
from models.regression import LinearSpreadModel

model = LinearSpreadModel()
model.fit(train_data, features=['elo_diff', 'pace', 'offensive_rating'])
spread_pred = model.predict(game_features)
```

**Feature Engineering**:

- Use `features/` module for feature creation
- Always include temporal features (recent form, rest days)
- Check for multicollinearity (VIF > 10 problematic)

**Gotchas**:

- Don't include outcome-derived features (e.g., "final_margin")
- Standardize features for regularized regression
- Use Ridge/Lasso for feature selection

---

### Poisson Models

#### `poisson.py` (Planned)

**Purpose**: Goal/run scoring models for baseball and soccer

**Use Cases**:

- MLB run totals
- Soccer goal predictions
- Hockey scoring

**Usage**:

```python
from models.poisson import PoissonScoring

model = PoissonScoring()
model.fit(team_data, features=['runs_per_game', 'opponent_runs_allowed'])

# Predict run distribution
home_runs_dist = model.predict_distribution(home_team='yankees')
# Returns: {0: 0.05, 1: 0.15, 2: 0.20, 3: 0.25, 4: 0.18, ...}
```

---

### Ensemble Models

#### `ensemble.py` (Planned)

**Purpose**: Combine multiple models for robust predictions

**Strategies**:

- Simple averaging
- Weighted by historical performance
- Stacking (meta-model learns weights)

**Usage**:

```python
from models.ensemble import ModelEnsemble

ensemble = ModelEnsemble([elo_model, regression_model, poisson_model])
ensemble.fit_weights(validation_data)  # Learn optimal weights
prediction = ensemble.predict(game_features)
```

**Best Practices**:

- Combine models with different strengths (Elo + stats-based)
- Weight by recent CLV performance, not just accuracy
- Re-fit weights periodically (monthly)

---

### Sport-Specific Models

#### NCAAB Models (`sport_specific/ncaab/`)

**Planned Components**:

- `team_ratings.py`: Elo, BPI-style ratings
- `player_impact.py`: Player-level impact on team strength
- `tournament.py`: March Madness specific models

**NCAAB Specifics**:

- Conference strength adjustments
- Tournament seeding effects
- Pace of play considerations

#### MLB Models (`sport_specific/mlb/`)

**Planned Components**:

- `pitcher_model.py`: Starting pitcher impact
- `team_offense.py`: Team batting metrics
- `f5_model.py`: First 5 innings predictions (starting pitcher only)
- `player_props.py`: Individual player prop predictions

**MLB Specifics**:

- Pitcher vs. lineup matchups
- Park factors (Coors Field, Fenway)
- Weather impact (wind, temperature)

#### NFL Models (`sport_specific/nfl/`) - Future

**Planned**: Elo, EPA-based models, quarterback ratings

#### NCAAF Models (`sport_specific/ncaaf/`) - Future

**Planned**: SP+, recruiting rankings, conference adjustments

---

## Architecture Decisions

This module implements the following design decisions:

- **[ADR-001: Use Elo Ratings for Initial Model](../docs/DECISIONS.md#adr-001)** — Start with interpretable baseline before ML complexity
- **[ADR-002: Walk-Forward Validation Required](../docs/DECISIONS.md#adr-002)** — Prevent look-ahead bias in backtests
- **[ADR-004: SQLite for Initial Database](../docs/DECISIONS.md#adr-004)** — Store model outputs and ratings

## Common Patterns

### Pattern 1: Model Training with Walk-Forward Validation

```python
from backtesting.walk_forward import walk_forward_splits

# CORRECT: Walk-forward validation
for train_df, test_df in walk_forward_splits(df, train_size=500, test_size=50):
    model.fit(train_df)
    predictions = model.predict(test_df)
    evaluate_predictions(predictions, test_df['actual'])

# ❌ WRONG: Random cross-validation (leaks future data)
# from sklearn.model_selection import cross_val_score
# cross_val_score(model, X, y, cv=5)  # DON'T DO THIS!
```

### Pattern 2: Feature Engineering with Data Leakage Prevention

```python
# CORRECT: Shift rolling features to use only past data
df['rolling_avg_points'] = df.groupby('team_id')['points'].rolling(5).mean().shift(1)

# ❌ WRONG: No shift = using current game in average
# df['rolling_avg_points'] = df.groupby('team_id')['points'].rolling(5).mean()
```

### Pattern 3: Model Evaluation Focused on CLV

```python
from betting.clv import calculate_clv

# Don't just track accuracy
accuracy = (predictions == actuals).mean()

# Track CLV - did we beat the closing line?
for pred, closing_odds in zip(predictions, closing_odds):
    clv = calculate_clv(our_odds, closing_odds)
    clv_results.append(clv)

# Positive average CLV = long-term profitability
print(f"Average CLV: {np.mean(clv_results):.2%}")  # Target: >0.5%
```

### Pattern 4: Seasonal Regression for Ratings

```python
# Regress Elo ratings toward mean at season start
def regress_to_mean(rating, mean=1500, regression_factor=0.33):
    """
    Partially revert ratings to mean between seasons.

    Args:
        regression_factor: 0.33 = keep 67% of rating, lose 33% to mean
    """
    return mean + (rating - mean) * (1 - regression_factor)

# Apply at season start
for team_id in elo.ratings:
    elo.ratings[team_id] = regress_to_mean(elo.ratings[team_id])
```

## Testing

Run tests for models module:

```bash
# All model tests
pytest tests/test_models.py -v

# Specific model
pytest tests/test_models.py::test_elo_rating -v

# With coverage
pytest tests/test_models.py --cov=models --cov-report=html

# Backtest validation (slow)
pytest tests/test_models.py -m backtest --timeout=300
```

## Performance Considerations

- **Speed**: Elo updates are O(1), very fast. ML models slower (retrain weekly).
- **Memory**: Store only essential ratings, not full game history (use database).
- **Scaling**: For 10,000+ games/season, use vectorized operations (pandas, numpy).

**Optimization Tips**:

- Cache Elo ratings in Redis for real-time updates
- Pre-compute features for upcoming games
- Use joblib for parallel model training

## Examples

### Example 1: End-to-End Model Training

```python
"""
Train Elo model on full NCAAB season, generate predictions for next week
"""
from models.elo import EloRating
from data.loaders import load_ncaab_games
import pandas as pd

# Load historical data
games = load_ncaab_games(seasons=[2023, 2024])

# Initialize Elo
elo = EloRating(k_factor=20, base_rating=1500)

# Train on completed games
for _, game in games[games['status'] == 'complete'].iterrows():
    expected = elo.predict_game(game['home_team'], game['away_team'])
    actual = 1.0 if game['home_score'] > game['away_score'] else 0.0

    elo.update_rating(game['home_team'], expected, actual)
    elo.update_rating(game['away_team'], 1 - expected, 1 - actual)

# Predict upcoming games
upcoming = games[games['status'] == 'scheduled']
predictions = []

for _, game in upcoming.iterrows():
    win_prob = elo.predict_game(game['home_team'], game['away_team'])
    spread = elo.elo_to_spread(
        elo.get_rating(game['home_team']) - elo.get_rating(game['away_team'])
    )

    predictions.append({
        'game_id': game['game_id'],
        'home_team': game['home_team'],
        'away_team': game['away_team'],
        'home_win_prob': win_prob,
        'predicted_spread': spread
    })

# Save predictions
pd.DataFrame(predictions).to_csv('predictions.csv', index=False)
```

### Example 2: Model Comparison

```python
"""
Compare Elo vs Regression model on same test set
"""
from models.elo import EloRating
from models.regression import LinearSpreadModel
from backtesting.metrics import calculate_roi, calculate_clv

# Train both models on same data
elo_model = EloRating()
regression_model = LinearSpreadModel()

elo_model.fit(train_games)
regression_model.fit(train_games, features=['pace', 'offensive_rating'])

# Predict on test set
elo_preds = elo_model.predict(test_games)
reg_preds = regression_model.predict(test_games)

# Compare performance
print("Elo Model:")
print(f"  Accuracy: {accuracy_score(test_games['winner'], elo_preds):.1%}")
print(f"  Average CLV: {calculate_clv(elo_preds, market_odds):.2%}")

print("\nRegression Model:")
print(f"  Accuracy: {accuracy_score(test_games['winner'], reg_preds):.1%}")
print(f"  Average CLV: {calculate_clv(reg_preds, market_odds):.2%}")

# Choose model with higher CLV, not accuracy!
```

## Error Handling

Common errors and solutions:

### Error: KeyError when accessing team rating

```python
# Error: New team not in Elo system
try:
    rating = elo.get_rating('new_team_id')
except KeyError:
    # Solution: Initialize with base rating
    rating = elo.base_rating
    elo.ratings['new_team_id'] = rating
```

### Error: Model predictions outside [0, 1] range

```python
# Error: Linear regression can predict >1.0 or <0.0
raw_pred = model.predict(features)  # Could be 1.2 or -0.1

# Solution: Clip to valid probability range
clipped_pred = np.clip(raw_pred, 0.0, 1.0)
```

### Error: Data leakage in features

```python
# Error: Using future data in rolling calculations
# Check if predictions are too good to be true (>60% accuracy)

# Solution: Validate with walk-forward, check for .shift(1)
from backtesting.validate import check_for_leakage
check_for_leakage(df, features=['rolling_avg', 'recent_form'])
```

## References

### Related Modules

- `features/` — Feature engineering for model inputs
- `betting/` — Convert model outputs to betting decisions
- `backtesting/` — Validate models with walk-forward splits
- `tracking/` — Store model predictions and performance

### External Documentation

- Elo Rating System: https://en.wikipedia.org/wiki/Elo_rating_system
- FiveThirtyEight Methodology: https://fivethirtyeight.com/methodology/
- Sports Reference Stats: https://www.sports-reference.com/

### Domain Knowledge

- [CLAUDE.md: Elo Formulas](../CLAUDE.md#elo-rating-system)
- [CLAUDE.md: Model Development Workflow](../CLAUDE.md#new-model-development)
- [docs/DECISIONS.md: Architecture Decisions](../docs/DECISIONS.md)

### Code Examples in Memory

Query claude-flow memory for model patterns:

```bash
npx claude-flow@alpha memory query "elo implementation" --namespace betting/code-examples
npx claude-flow@alpha memory query "model validation" --namespace betting/patterns
```

## Contributing

When modifying this module:

1. **Update docstrings** for any changed functions (Google style)
2. **Add tests** for new model types (>80% coverage required)
3. **Update this README** if module structure changes
4. **Create ADR** for new model approaches or major changes
5. **Backtest thoroughly** with walk-forward validation before deployment
6. **Track CLV** as primary metric, not just accuracy

**Data Leakage Checklist**:

- [ ] All rolling features use `.shift(1)`
- [ ] No future data in feature calculations
- [ ] Walk-forward validation only (no random CV)
- [ ] Features available before game time
- [ ] Tested on out-of-sample data

## Roadmap

### Phase 1: Foundation (Weeks 1-2) - Current

- [ ] Implement `base.py` abstract model class
- [ ] Implement `elo.py` basic Elo rating
- [ ] Implement `elo.py` Elo with MOV adjustment
- [ ] Create NCAAB Elo model in `sport_specific/ncaab/`

### Phase 2: Statistical Models (Weeks 3-4)

- [ ] Implement `regression.py` for spreads
- [ ] Implement `poisson.py` for MLB run totals
- [ ] Create MLB pitcher model in `sport_specific/mlb/`

### Phase 3: Advanced Models (Weeks 5-6)

- [ ] Implement `ensemble.py` model combination
- [ ] Add gradient boosting models (XGBoost)
- [ ] Create tournament-specific models for March Madness

### Phase 4: Continuous Improvement (Ongoing)

- [ ] Monitor CLV degradation
- [ ] Retrain models weekly
- [ ] Incorporate new data sources (injuries, weather)
- [ ] Optimize hyperparameters

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-01-24 | Initial README with structure planning |

## Troubleshooting

### Issue 1: Elo Ratings Diverging

**Symptom**: Some team ratings exceed 2000 or drop below 1000

**Cause**: K-factor too high or no seasonal regression

**Solution**:

```python
# Reduce K-factor
elo.k_factor = 15  # Instead of 30

# Apply stronger seasonal regression
for team in elo.ratings:
    elo.ratings[team] = regress_to_mean(elo.ratings[team], factor=0.5)
```

### Issue 2: Model Accuracy Too High (>65%)

**Symptom**: Backtest shows >65% accuracy against spread

**Cause**: Likely data leakage - using future information

**Solution**:

1. Check all features for `.shift(1)`
2. Verify walk-forward validation
3. Test on completely unseen season
4. Review feature engineering for look-ahead bias

### Issue 3: Poor CLV Despite Good Accuracy

**Symptom**: 60% accuracy but negative CLV

**Cause**: Model picks favorites, ignores value

**Solution**:

```python
# Don't bet on favorites with negative EV
if model_prob > market_prob and calculate_ev(model_prob, odds) > 0:
    place_bet()
```

---

**Maintained by**: Model Development Team
**Last Updated**: 2026-01-24
**Status**: ✅ Active - Foundation Phase
**Claude-Flow Integration**: Use `documentation-engineer` agent for updates
