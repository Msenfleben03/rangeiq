"""MLB Stats API client for schedules, lineups, rosters, and probable pitchers.

Primary data source for daily pipeline operations. Free, unauthenticated,
rate-limit-friendly.

Base URL: https://statsapi.mlb.com/api/v1/
Library: pip install MLB-StatsAPI

Key endpoints:
    - /schedule: daily games with probable pitchers
    - /game/{game_pk}/feed/live: play-by-play, lineups, scoring
    - /teams: roster, standings
    - /people/{player_id}: player details, stats

game_pk is the universal game identifier used across all MLB tables.

References:
    - API docs: docs/mlb/DATA_SOURCES.md
    - Pipeline design: docs/mlb/PIPELINE_DESIGN.md
"""

# TODO: Phase 1 implementation
# - MLBStatsAPIClient class
# - fetch_schedule(date) → list of games with probable pitchers
# - fetch_confirmed_lineups(game_pk) → batting orders
# - fetch_game_result(game_pk) → final score, box score
# - fetch_roster(team_id, season) → active roster
# - fetch_probable_pitchers(date) → starter assignments
# - fetch_umpire_assignment(game_pk) → home plate umpire
# - Player ID resolution (MLBAM IDs)
# - Rate limiting / retry logic
