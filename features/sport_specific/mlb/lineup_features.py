"""Lineup and offensive feature engineering.

Computes lineup-level offensive projections from individual batter stats,
handling platoon splits and confirmed vs projected lineups.

Key metrics:
    - Aggregate wRC+ (park/league adjusted)
    - Aggregate xwOBA (Statcast expected weighted on-base)
    - Platoon-adjusted lineup strength vs starter handedness
    - Lineup handedness composition (% L/R/S batters)

Stabilization rates for batters:
    - Swing%: ~50 PA
    - K%: ~150 PA
    - BB%: ~200 PA
    - OBP/SLG: ~500 PA
    - BA: ~910 PA (more than a full season!)
    - Exit velocity: ~16-20 games (Statcast)

References:
    - Research doc: docs/mlb/research/platoon-splits.md
"""

# TODO: Phase 1 implementation
# - compute_lineup_strength(lineup_player_ids, pitcher_throws, as_of_date)
# - compute_platoon_adjustment(batter_splits, pitcher_handedness)
# - bayesian_regress_splits(observed_split, career_mean, sample_size)
# - aggregate_lineup_xwoba(lineup, pitcher_throws, park_factors)
# - handle_missing_lineup(team_id, as_of_date) — use typical lineup
