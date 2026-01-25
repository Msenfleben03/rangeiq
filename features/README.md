# Features Module

## Purpose

The features module handles feature engineering and selection for predictive models. It transforms raw sports data (scores, stats, team info) into predictive features while preventing data leakage through careful temporal ordering.

**Core Principle**: All features must be available BEFORE game time. Rolling averages, recent form, and historical stats must use `.shift(1)` to prevent look-ahead bias.

## Quick Start

```python
from features.engineering import create_rolling_features, create_team_features
import pandas as pd

# Load game data
games = pd.read_csv('data/processed/ncaab_games.csv')
games['date'] = pd.to_datetime(games['date'])
games = games.sort_values('date')  # CRITICAL: Sort chronologically

# Create rolling features (5-game and 10-game averages)
games_with_rolling = create_rolling_features(
    df=games,
    columns=['points', 'assists', 'rebounds'],
    windows=[5, 10],
    group_by='team_id'  # Calculate per team
)

# Create team strength features
games_with_features = create_team_features(
    df=games_with_rolling,
    opponent_stats=True,  # Include opponent's stats
    home_away_split=True  # Separate home/away performance
)

# Verify no data leakage
from features.validation import check_for_leakage
check_for_leakage(games_with_features, date_col='date')
```

## Components

### Feature Engineering

#### `engineering.py` (Planned)

**Purpose**: Create predictive features from raw data

**Key Functions**:

- `create_rolling_features(df, columns, windows)`: Rolling averages with leak protection
- `create_expanding_features(df, columns)`: Cumulative stats
- `create_lag_features(df, columns, lags)`: Previous game stats
- `create_team_features(df)`: Team-level aggregations
- `create_matchup_features(df)`: Head-to-head history

**Usage**:

```python
# Rolling average with automatic shifting
df['points_rolling_5'] = df.groupby('team_id')['points'].rolling(5).mean().shift(1)

# ❌ WRONG: No shift = data leakage
# df['points_rolling_5'] = df.groupby('team_id')['points'].rolling(5).mean()
```

---

### Feature Selection

#### `selection.py` (Planned)

**Purpose**: Select most predictive features, remove redundant/noisy features

**Methods**:

- Correlation analysis (remove highly correlated features)
- Feature importance from tree models
- Recursive feature elimination (RFE)
- L1 regularization (Lasso)

**Usage**:

```python
from features.selection import select_top_features

# Select top 20 features by importance
selected = select_top_features(
    X=feature_matrix,
    y=target,
    method='random_forest',
    n_features=20
)
```

---

### Sport-Specific Features

#### NCAAB Features (`sport_specific/ncaab_features.py`)

**Basketball-Specific**:

- Pace of play (possessions per game)
- Offensive/defensive efficiency
- Four Factors (eFG%, TOV%, ORB%, FT Rate)
- Conference strength adjustments
- Rest days between games

#### MLB Features (`sport_specific/mlb_features.py`)

**Baseball-Specific**:

- Pitcher matchups (starter ERA, WHIP, K/9)
- Team vs. LHP/RHP splits
- Bullpen strength (recent usage, ERA)
- Park factors (Coors Field, Fenway)
- Weather (wind speed/direction, temperature)

---

## Common Patterns

### Pattern 1: Rolling Features with Data Leakage Prevention

```python
# CORRECT: Calculate then shift
df['rolling_points'] = (
    df.groupby('team_id')['points']
    .rolling(window=5, min_periods=1)
    .mean()
    .shift(1)  # CRITICAL: Shift to use only past data
)

# Result: Game on row i uses average of games i-5 to i-1
# This is what you'd know BEFORE game i starts
```

### Pattern 2: Opponent Features

```python
# Get opponent's stats for matchup features
def add_opponent_features(df):
    """Add opponent's recent form to each game."""
    # Merge home team's features as opponent for away team
    df_opp = df[['game_id', 'home_team_id', 'home_points_rolling_5']].rename(
        columns={'home_team_id': 'away_team_id', 'home_points_rolling_5': 'opp_points_rolling_5'}
    )
    df = df.merge(df_opp, on=['game_id', 'away_team_id'], how='left')
    return df
```

### Pattern 3: Handling Missing Data

```python
# Early season games won't have full rolling windows
df['rolling_points'].fillna(df['points'].mean(), inplace=True)

# Or use expanding window for early games
df['rolling_points'] = df.groupby('team_id')['points'].transform(
    lambda x: x.rolling(window=5, min_periods=1).mean().shift(1)
)
```

## Testing

```bash
pytest tests/test_features.py -v
pytest tests/test_features.py::test_no_data_leakage -v
```

## References

- [CLAUDE.md: Feature Engineering](../CLAUDE.md#features)
- [ADR-007: Data Leakage Prevention](../docs/DECISIONS.md#adr-007)
- Related: `models/` (consumes features), `pipelines/` (automates feature creation)

---

**Maintained by**: Feature Engineering Team
**Last Updated**: 2026-01-24
**Status**: ✅ Active - Foundation Phase
