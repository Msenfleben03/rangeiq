"""Bulk historical data fetcher for MLB backtesting (2023-2025).

Pulls all required data for walk-forward backtesting:
    - Game results and scores (MLB Stats API)
    - Pitcher game logs (pybaseball / FanGraphs)
    - Batter season stats (pybaseball / FanGraphs)
    - Historical odds (ESPN Core API / archive sources)
    - Confirmed lineups (retroactive from box scores)
    - Park factors per season (FanGraphs)

Phase 2 additions:
    - Historical weather (Open-Meteo archive API)
    - Umpire assignments and stats (Retrosheet / Savant)
    - Bullpen usage logs (retroactive from box scores)

Usage:
    python scripts/mlb_fetch_historical.py --seasons 2023 2024 2025
    python scripts/mlb_fetch_historical.py --seasons 2025 --incremental
    python scripts/mlb_fetch_historical.py --seasons 2023 2024 2025 --weather

Note: Full 3-season pull may take 30-60 minutes due to Statcast data volume.
Use pybaseball.cache.enable() to avoid re-fetching.
"""

# TODO: Phase 1 implementation
# - fetch_season_games(season) → all games with scores
# - fetch_season_pitcher_logs(season) → pitcher game logs
# - fetch_season_batter_stats(season) → batter leaderboards
# - fetch_season_odds(season) → historical odds from ESPN Core
# - backfill_lineups_from_boxscores(season) → retroactive lineups
# - fetch_season_park_factors(season) → FanGraphs park factors
# - Checkpoint/resume for long-running fetches
# - Progress reporting
