# Features Module Codemap

**Last Updated:** 2026-02-12
**Entry Point:** `features/__init__.py` (empty)

## Architecture

```text
features/
  __init__.py                  # Empty package marker
  sport_specific/
    __init__.py                # Empty package marker
```

## Status

The features module is currently a **placeholder structure** with no implemented
code. Feature engineering logic is distributed across other modules:

- **Lagged features:** `backtesting/walk_forward.py` provides `create_lagged_features()` for safe `.shift(n)` operations
- **Feature validation:** `backtesting/validators/temporal_validator.py` checks features for look-ahead bias
- **Feature constants:** `config/constants.py` defines `FeatureConfig` with rolling window sizes and decay factors
- **Feature count limits:** `backtesting/validators/overfit_validator.py` enforces sqrt(n_samples) rule

## Planned Structure

Per the CLAUDE.md project plan:

```text
features/
  engineering.py           # Feature creation utilities (not yet implemented)
  selection.py             # Feature importance, selection (not yet implemented)
  sport_specific/
    ncaab_features.py      # NCAAB-specific features (not yet implemented)
    mlb_features.py        # MLB-specific features (not yet implemented)
```

## Feature Engineering Constants (from config/constants.py)

| Constant | Value | Purpose |
|----------|-------|---------|
| `FEATURES.ROLLING_WINDOW_SHORT` | 5 games | Short-term rolling average |
| `FEATURES.ROLLING_WINDOW_MEDIUM` | 10 games | Medium-term rolling average |
| `FEATURES.ROLLING_WINDOW_LONG` | 20 games | Long-term rolling average |
| `FEATURES.DECAY_FACTOR` | 0.95 | Exponential decay for weighting recent games |
| `FEATURES.MIN_LAG_GAMES` | 1 | Minimum lag to prevent look-ahead bias |

## Related Areas

- [backtesting.md](backtesting.md) - `create_lagged_features()` and temporal validation
- [config.md](config.md) - FeatureConfig with window sizes and decay parameters
- [models.md](models.md) - Models consume features for predictions
