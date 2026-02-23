# Features Module Codemap

**Last Updated:** 2026-02-17
**Entry Point:** `features/__init__.py` (empty)

## Architecture

```text
features/
  __init__.py                       # Empty package marker
  engineering.py                    # Core utilities: safe_rolling, decay, OQ-weight, rest
  sport_specific/
    __init__.py                     # Empty package marker
    ncaab/
      __init__.py                   # Package marker
      advanced_features.py          # NCABBFeatureEngine (vol, OQ-margin, rest, decay)
```

## Core Utilities (`engineering.py`)

Safe, leak-proof primitives. Every rolling function applies `.shift(1)` internally
so callers never need to remember — prevents look-ahead bias by construction.

| Function | Purpose | Key Detail |
|----------|---------|------------|
| `safe_rolling(series, window, func)` | Rolling calculation with mandatory `.shift(1)` | Supports "mean", "std", "sum", "min", "max" |
| `exponential_weighted_rolling(series, window, half_life_games)` | EWM with `.shift(1)` | Weights recent games more heavily |
| `opponent_quality_weight(stat, opp_elo, mean_elo)` | Weight stat by `opp_elo / mean_elo` | Neutral (1.0x) when opponent is average (1500) |
| `compute_rest_days(dates, team_ids)` | Days since last game + B2B flag | Returns DataFrame with `rest_days`, `is_back_to_back` |
| `validate_no_leakage(df, feature_cols, date_col)` | Quick leakage sanity check | Raises ValueError if future data detected |

## NCAAB Feature Engine (`advanced_features.py`)

Computes advanced features orthogonal to base Elo ratings.

| Method | Feature(s) | Window | What It Captures |
|--------|-----------|--------|------------------|
| `compute_rolling_volatility(df)` | `vol_5`, `vol_10` | 5, 10 games | Scoring consistency (2nd moment) |
| `compute_opponent_weighted_margin(df)` | `oq_margin_10` | 10 games | Quality-adjusted recent form |
| `compute_rest_days(df)` | `rest_days`, `is_back_to_back` | N/A | Fatigue / schedule advantage |
| `compute_decay_weighted_margin(df)` | `decay_margin_10` | 10 games | Recent momentum (EWM) |
| `compute_all(df)` | All above | — | Single-pass computation |
| `compute_matchup_differentials(home, away)` | Diffs + B2B flags | — | Matchup-level features |
| `get_feature_names()` | List of feature names | — | For temporal validator audit |

## Feature Constants (from `config/constants.py`)

| Constant | Value | Purpose |
|----------|-------|---------|
| `FEATURES.VOLATILITY_WINDOWS` | (5, 10) | Rolling volatility windows |
| `FEATURES.OQ_MEAN_ELO` | 1500.0 | Neutral weight for opponent quality |
| `FEATURES.BACK_TO_BACK_THRESHOLD` | 1 | Days rest <= 1 = back-to-back |
| `FEATURES.DECAY_HALF_LIFE_GAMES` | 8 | Half-life for EWM decay |
| `FEATURES.FEATURES_ENABLED` | () | Empty = Elo-only baseline |
| `FEATURES.ALL_FEATURES` | (vol_5, vol_10, oq_margin_10, rest_days, is_back_to_back, decay_margin_10) | All available features |

## A/B Test Results (2026-02-16)

Features improve ROI in 5/6 seasons (pooled one-sided p=0.064).
See `docs/ADVANCED_FEATURES_RESEARCH.md` for full research report and `docs/DECISIONS.md` ADR-016.

## Barttorvik Efficiency Ratings (External Feature Source)

Barttorvik T-Rank ratings provide point-in-time AdjO, AdjD, AdjTempo, and Barthag.
These are fetched via `pipelines/barttorvik_fetcher.py` and mapped to ESPN team IDs
via `pipelines/team_name_mapping.py`. Computed differentials (home - away) serve as
additional features alongside the NCABBFeatureEngine outputs.

| Feature | Source | What It Captures |
|---------|--------|------------------|
| `adj_o_diff` | Barttorvik | Offensive efficiency gap |
| `adj_d_diff` | Barttorvik | Defensive efficiency gap |
| `adj_tempo_diff` | Barttorvik | Pace differential |
| `barthag_diff` | Barttorvik | Overall quality gap (0-1 scale) |
| `net_rating_diff` | Derived (AdjO-AdjD) | Net efficiency gap |

## Integration Points

- `scripts/backtest_ncaab_elo.py`: `run_backtest_with_features()` wrapper adjusts Elo probability
- `scripts/ab_compare_features.py`: Paired t-test A/B comparison framework
- `pipelines/barttorvik_fetcher.py`: External efficiency ratings (347K ratings, 6 seasons)
- `pipelines/team_name_mapping.py`: ESPN team ID -> Barttorvik name (359 teams)
- `tests/test_feature_engineering.py`: 30 tests covering all utilities and engine methods

## Related Areas

- [backtesting.md](backtesting.md) - `create_lagged_features()` and temporal validation
- [config.md](config.md) - FeatureConfig with window sizes and decay parameters
- [models.md](models.md) - Models consume features for predictions
- [scripts.md](scripts.md) - backtest_ncaab_elo.py and ab_compare_features.py
