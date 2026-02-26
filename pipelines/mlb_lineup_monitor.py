"""Lineup confirmation monitor for event-driven pipeline.

Polls MLB Stats API for confirmed lineups. Lineups are typically
published 2-4 hours before first pitch. This is the largest single
line movement event — can move lines 10-30+ cents.

Architecture:
    Event-driven (preferred):
        - Poll MLB API every 15-30 minutes starting 4 hours before first pitch
        - Per-game state tracking: scheduled → pitchers_confirmed → lineup_confirmed
        - Trigger prediction pipeline per-game as lineups lock
        - Post-prediction: apply Kelly sizing, compare to market, log picks

    3-cycle fallback:
        - Morning (8 AM ET): schedules, probable pitchers, opening odds
        - Pre-game (1 PM ET): confirmed lineups, weather, predictions
        - Post-game (11 PM ET): results, settlement, stat updates

State machine per game:
    SCHEDULED → PITCHERS_SET → LINEUPS_CONFIRMED → PREDICTED → SETTLED

References:
    - Pipeline design: docs/mlb/PIPELINE_DESIGN.md
    - Lineup source: MLB Stats API + RotoWire (backup)
"""

# TODO: Phase 1 implementation
# - LineupMonitor class with per-game state tracking
# - poll_lineups(game_pk) → confirmed lineup or None
# - check_all_games(date) → list of newly confirmed games
# - GameState enum: SCHEDULED, PITCHERS_SET, LINEUPS_CONFIRMED, PREDICTED, SETTLED
# - Polling interval configuration (default: 15 min)
# - Trigger callback when lineup confirmed
# - Fallback to projected/typical lineup if not confirmed by threshold
# - Integration with lineups table in mlb_data.db
