"""Bullpen fatigue and availability feature engineering.

Tracks reliever workload to project bullpen quality for a given game.
The real edge in bullpen modeling is availability tracking — back-to-back
appearances degrade performance measurably.

Key fatigue metrics:
    - PC_L3: pitch count last 3 days (concern threshold: >30-40)
    - PC_L7: pitch count last 7 days
    - Consecutive days worked (concern: 2+ days)
    - Days since closer's last appearance
    - High-leverage innings in last 2 days

Modeling approach:
    - Split pitcher impact ~2/3 starter, ~1/3 bullpen
    - Adjust bullpen weight based on expected starter innings
    - Use xFIP/SIERA over raw ERA for bullpen (1 run more variable)
    - Regress LOB% aggressively (largely outside pitcher control)

Opener detection:
    - 5+ career appearances
    - Hasn't exceeded 2 IP in last 10 outings
    - Has opened at least once in last 20 appearances
    → Default to team-average pitcher adjustment

References:
    - Research doc: docs/mlb/research/bullpen-fatigue.md
    - TTOP: docs/mlb/research/pitching-metrics.md
"""

# TODO: Phase 1 implementation
# - compute_bullpen_fatigue(team_id, game_date)
# - compute_reliever_availability(player_id, game_date)
# - detect_opener(player_id, game_date)
# - compute_team_bullpen_xfip(team_id, as_of_date)
# - Integration with bullpen_usage table and v_bullpen_fatigue view
