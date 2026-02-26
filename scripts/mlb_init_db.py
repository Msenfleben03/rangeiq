"""Initialize MLB data database (mlb_data.db).

Creates the mlb_data.db schema with all 14 tables and views.
Safe to run multiple times (CREATE IF NOT EXISTS).

Tables:
    - teams: 30 MLB teams with stadium coordinates
    - players: cross-reference IDs (MLBAM, FanGraphs, BBRef)
    - games: game results with game_pk as primary key
    - pitcher_game_logs: per-start stats with Statcast metrics
    - pitcher_season_stats: rolling season stats with as_of_date
    - batter_season_stats: rolling batter stats with platoon splits
    - lineups: confirmed batting orders per game
    - weather: game-time weather conditions
    - park_factors: event-specific park factors by handedness
    - umpire_stats: home plate umpire tendencies
    - projections: ZiPS/Steamer preseason projections
    - bullpen_usage: reliever pitch counts and fatigue tracking

Views:
    - v_bullpen_fatigue: rolling 3/7-day workload per reliever

Usage:
    python scripts/mlb_init_db.py
    python scripts/mlb_init_db.py --seed-teams   # populate 30 MLB teams

References:
    - Schema: docs/mlb/DATA_DICTIONARY.md
    - Design: docs/plans/2026-02-25-mlb-expansion-design.md
"""

# TODO: Phase 1 implementation (first thing to build)
# - Create mlb_data.db with full schema
# - Seed teams table with 30 MLB teams (ID, name, stadium, lat/lon, dome)
# - Seed park_factors with FanGraphs defaults
# - Schema version tracking
# - Safe re-run (CREATE IF NOT EXISTS)
