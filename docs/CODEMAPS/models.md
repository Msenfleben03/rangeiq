# Models Module Codemap

**Last Updated:** 2026-02-25
**Entry Point:** `models/__init__.py` (empty)
**Test Coverage:** `tests/test_elo.py`, `tests/test_model_persistence.py`,
`tests/test_mlb_poisson_model.py`, `tests/test_mlb_pitcher_model.py`

## Architecture

```text
models/
  __init__.py                          # Empty package marker
  elo.py                               # Base Elo rating system (pure functions + class)
  model_persistence.py                 # Save, load, export trained models with metadata
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
      __init__.py                      # Empty package marker
      poisson_model.py                 # Poisson run distribution → ML/RL/totals/F5 (SKELETON)
      pitcher_model.py                 # Pitcher evaluation: K-BB%, SIERA, Stuff+, TTOP (SKELETON)
      lineup_model.py                  # Lineup strength with platoon splits (SKELETON)
      projection_blender.py            # ZiPS/Steamer blending with in-season phasing (SKELETON)
```

## Key Modules

### model_persistence.py

Save, load, and export trained models with metadata tracking.
Supports pickle serialization, CSV export, and database export.

| Export | Type | Purpose |
|--------|------|---------|
| `ModelMetadata` | dataclass | Metadata: model_name, sport, training_date, seasons_used, game_count, team_count, config_snapshot, notes |
| `SavedModel` | dataclass | Container wrapping model + metadata |
| `save_model(model, path, metadata)` | function | Pickle model + JSON metadata sidecar |
| `load_model(path)` | function | Load model with backwards compatibility for raw pickles |
| `export_ratings_csv(model, path, sport)` | function | Export ratings to CSV for human review |
| `export_ratings_db(model, db, sport, season, rating_type)` | function | Insert/update team_ratings table via UPSERT |

**File Outputs:**

- `.pkl` - Pickled `SavedModel` (model + metadata)
- `.meta.json` - JSON sidecar for easy inspection

**Usage Pattern:**

```python
from models.model_persistence import save_model, load_model, ModelMetadata

# Save
metadata = ModelMetadata(model_name="ncaab_elo_v1", sport="ncaab", ...)
save_model(model, "data/processed/ncaab_elo_model.pkl", metadata)

# Load
saved = load_model("data/processed/ncaab_elo_model.pkl")
model = saved.model
print(saved.metadata.training_date)
```

**Dependencies:** pickle, json, pandas, pathlib

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

**NCAAB-Specific Defaults (from config.constants.ELO):**

- K-factor: 20, Home advantage: 100 Elo points (~4 points spread)
- MOV cap: 25 points, Regression factor: 0.50
- Tournament K-factor: 32, Early season: first 5 games at 70% K

### MLB Models (skeletons — Phase 1 implementation pending)

Four skeleton modules implementing a pitcher-centric Poisson regression approach for MLB.
Unlike NCAAB's Elo-based system, MLB uses Poisson run distribution derived from pitcher
matchups and lineup composition. All files contain docstrings and TODOs, no executable code yet.

**sport_specific/mlb/poisson_model.py** — Core model: computes lambda (expected runs) per team
from pitcher + lineup + context, builds Poisson score matrix (0-15 x 0-15), extracts ML/RL/totals/F5 probabilities.

**sport_specific/mlb/pitcher_model.py** — Projects starter's expected run allowance using
skill metrics (K-BB%, SIERA, xFIP, Stuff+), exponential decay weighting of recent starts,
matchup context (platoon composition), and TTOP (Times Through Order Penalty).

**sport_specific/mlb/lineup_model.py** — Projects lineup offensive output against a specific
pitcher: aggregate wRC+/xwOBA, platoon adjustments (L/R splits), park factor interaction,
rest/travel penalties. Handles unconfirmed lineups via projected/typical fallback.

**sport_specific/mlb/projection_blender.py** — Blends preseason projections (ZiPS, Steamer)
with observed in-season data using time-dependent schedule: 90/10 April → 20/80 July+.
Separate blending curves for pitchers vs batters (pitcher metrics stabilize faster).

**Planned Tests:** `tests/test_mlb_poisson_model.py` (8 tests), `tests/test_mlb_pitcher_model.py` (6 tests)

### Future Sport Models (placeholders)

Empty `__init__.py` files for: ncaaf/, nfl/

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
        +------> models/model_persistence.py (save/load/export)
        |                |
        |                +-> data/processed/ncaab_elo_model.pkl
        |                +-> data/processed/ncaab_elo_ratings_current.csv
        |                +-> team_ratings table (SQLite)
        |
        +------> backtesting/ (walk-forward validation of predictions)
        |
        +------> betting/ (EV calculation, Kelly sizing from model probabilities)

# MLB Model Data Flow (planned)
pipelines/mlb_projections_fetcher.py (ZiPS/Steamer)
        |
        v
models/sport_specific/mlb/projection_blender.py (blend projections + observed)
        |
        +------> models/sport_specific/mlb/pitcher_model.py (starter evaluation)
        |                |
        |                +------> models/sport_specific/mlb/poisson_model.py (lambda computation)
        |                                   ^
        +------> models/sport_specific/mlb/lineup_model.py (lineup strength)
                         |
                         +------> poisson_model.py (consume lambda → ML/RL/totals/F5)
                                          |
                                          +------> betting/ (edge calc, Kelly sizing)
                                          +------> models/model_persistence.py (save/load)
```

## External Dependencies

| Package | Used In | Purpose |
|---------|---------|---------|
| pandas | team_ratings.py, model_persistence.py | DataFrame export, CSV loading |
| pickle | model_persistence.py | Model serialization |
| json | model_persistence.py | Metadata sidecar files |
| math | elo.py | log() for MOV multiplier |
| config.constants | elo.py, team_ratings.py | ELO configuration parameters |

## Related Areas

- [config.md](config.md) - EloConfig provides all tunable parameters
- [backtesting.md](backtesting.md) - Walk-forward validation tests model predictions
- [pipelines.md](pipelines.md) - ncaab_data_fetcher provides game data for model training
- [scripts.md](scripts.md) - train_ncaab_elo.py, backtest_ncaab_elo.py, settle_paper_bets.py use model_persistence
- [tests.md](tests.md) - test_elo.py covers base Elo and NCAAB model; test_model_persistence.py covers save/load/export
