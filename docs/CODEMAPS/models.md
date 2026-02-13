# Models Module Codemap

**Last Updated:** 2026-02-12
**Entry Point:** `models/__init__.py` (empty)
**Test Coverage:** `tests/test_elo.py`

## Architecture

```text
models/
  __init__.py                          # Empty package marker
  elo.py                               # Base Elo rating system (pure functions + class)
  sport_specific/
    __init__.py                        # Empty
    ncaab/
      __init__.py                      # Empty
      team_ratings.py                  # NCAAB Elo model (extends EloRatingSystem)
    ncaaf/
      __init__.py                      # Empty (future)
    nfl/
      __init__.py                      # Empty (future)
    mlb/
      __init__.py                      # Empty (future)
```

## Key Modules

### elo.py

Base Elo rating system providing both pure functions and a stateful class for managing team ratings.

**Pure Functions:**

| Function | Signature | Purpose |
|----------|-----------|---------|
| `elo_expected()` | `(rating_a, rating_b) -> float` | Win probability from Elo difference: 1/(1+10^((Rb-Ra)/400)) |
| `elo_update()` | `(rating, expected, actual, k=20) -> float` | Standard Elo update: rating + k*(actual - expected) |
| `elo_to_spread()` | `(elo_diff, points_per_elo=25) -> float` | Convert Elo diff to predicted point spread |
| `spread_to_elo()` | `(spread, points_per_elo=25) -> float` | Convert spread to equivalent Elo difference |
| `regress_to_mean()` | `(rating, mean=1500, factor=0.33) -> float` | Between-season regression: mean + (rating - mean) * (1 - factor) |
| `mov_multiplier()` | `(margin, elo_diff, mov_cap=25) -> float` | Margin-of-victory multiplier: ln(margin+1) * autocorr_adj |

**EloRatingSystem Class:**

| Method | Purpose |
|--------|---------|
| `get_rating(team_id)` | Current Elo (default: initial_rating for unknown teams) |
| `set_rating(team_id, rating)` | Set rating (clamped to min/max bounds) |
| `get_all_ratings()` | Dictionary of all team ratings |
| `predict_win_probability(home, away, neutral)` | Home win probability with home advantage |
| `predict_spread(home, away, neutral)` | Point spread prediction |
| `get_effective_k(margin, elo_diff)` | K-factor adjusted for margin of victory |
| `update_game(home, away, h_score, a_score, neutral)` | Update ratings after game result |
| `apply_season_regression()` | Regress all ratings to mean between seasons |
| `reset()` | Clear all ratings and history |
| `to_dict()` / `from_dict()` | Serialization for persistence |

**Attributes:** k_factor, initial_rating, home_advantage, mov_cap,
regression_factor, min_rating, max_rating, points_per_elo,
ratings (dict), game_history (list)

**Dependencies:** config.constants.ELO

### sport_specific/ncaab/team_ratings.py

NCAAB-specific Elo model extending EloRatingSystem with basketball-specific features.

**NCAABEloModel Class (extends EloRatingSystem):**

| Method | Purpose |
|--------|---------|
| `get_k_factor(is_tournament, games_played)` | Context-aware K (tournament=32, early season=70% of base) |
| `get_conference_adjustment(conference)` | Elo adjustment for conference strength |
| `set_conference(team_id, conference)` | Assign team to conference |
| `predict_win_probability(..., apply_conference_adj)` | With optional conference strength adjustment |
| `predict_spread(..., apply_conference_adj)` | With optional conference strength adjustment |
| `seed_to_elo_estimate(seed)` | Tournament seed -> expected Elo (1=1750, 16=1350) |
| `update_game(..., is_tournament)` | Tracks games_played and matchup_history |
| `get_matchup_history(team_a, team_b)` | Head-to-head historical record |
| `process_games(games_list)` | Batch process games in chronological order |
| `to_dataframe()` | Export ratings to pandas DataFrame |
| `apply_season_regression()` | Regression + reset games_played |
| `to_dict()` / `from_dict()` | Full state serialization |

**Module-Level Constants:**

| Constant | Type | Purpose |
|----------|------|---------|
| `CONFERENCE_ADJUSTMENTS` | dict | Elo adjustments by conference (Big Ten: +50, SWAC: -25) |
| `SEED_TO_ELO` | dict | Tournament seed -> expected Elo rating mapping |

**Utility Functions:**

- `load_team_conferences(filepath)` - Load conference mappings from CSV
- `initialize_from_previous_season(model, previous_ratings)` - Initialize with regressed prior ratings

**NCAAB-Specific Defaults (from config.constants.ELO):**

- K-factor: 20
- Home advantage: 100 Elo points (~4 points spread)
- MOV cap: 25 points
- Regression factor: 0.50 (50% regression between seasons)
- Tournament K-factor: 32 (higher for tournament games)
- Early season: first 5 games at 70% K

### Future Sport Models (placeholders)

The following directories contain only empty `__init__.py` files:

- `models/sport_specific/ncaaf/` - NCAA Football (future)
- `models/sport_specific/nfl/` - NFL (future)
- `models/sport_specific/mlb/` - MLB (future)

All sport-specific constants are already defined in `config/constants.py` (EloConfig, MLBConstants, NFLConstants).

## Data Flow

```text
config/constants.py (ELO parameters)
        |
        v
models/elo.py (base system + pure functions)
        |
        v
models/sport_specific/ncaab/team_ratings.py (NCAAB extensions)
        |
        v
backtesting/ (walk-forward validation of predictions)
        |
        v
betting/ (EV calculation, Kelly sizing from model probabilities)
```

## External Dependencies

| Package | Used In | Purpose |
|---------|---------|---------|
| pandas | team_ratings.py | DataFrame export, CSV loading |
| math | elo.py | log() for MOV multiplier |
| config.constants | elo.py, team_ratings.py | ELO configuration parameters |

## Related Areas

- [config.md](config.md) - EloConfig provides all tunable parameters
- [backtesting.md](backtesting.md) - Walk-forward validation tests model predictions
- [pipelines.md](pipelines.md) - ncaab_data_fetcher provides game data for model training
- [tests.md](tests.md) - test_elo.py covers base Elo and NCAAB model
