"""pybaseball wrapper for Statcast, FanGraphs, and Baseball Reference data.

Foundational data library unifying access to multiple baseball data sources.
Library: pip install pybaseball

Key functions:
    - statcast(start_dt, end_dt): pitch-level data (~700K+ pitches/season)
        exit velocity, spin rate, launch angle, expected stats
    - pitching_stats(season): FanGraphs leaderboards (334 columns)
        WAR, FIP, xERA, CSW%, barrel%, SIERA, K-BB%
    - batting_stats(season): FanGraphs batting leaderboards
        wRC+, xwOBA, barrel%, hard_hit%
    - playerid_lookup(last, first): cross-reference player IDs
    - schedule_and_record(season, team): game-by-game results

IMPORTANT: Enable caching for large Statcast pulls:
    pybaseball.cache.enable()

References:
    - GitHub: https://github.com/jldbc/pybaseball
    - Data sources: docs/mlb/DATA_SOURCES.md
"""

# TODO: Phase 1 implementation
# - PybaseballFetcher class with caching enabled
# - fetch_pitcher_season_stats(season) → pitcher leaderboard DataFrame
# - fetch_batter_season_stats(season) → batter leaderboard DataFrame
# - fetch_statcast_pitcher(player_id, start, end) → pitch-level data
# - fetch_game_logs_pitcher(player_id, season) → start-by-start logs
# - fetch_park_factors(season) → FanGraphs park factors
# - Player ID cross-reference mapping (MLBAM ↔ FanGraphs ↔ BBRef)
# - Bulk historical fetch for backtesting (2023-2025)
# - Rate limiting and caching strategy
