"""Home plate umpire feature engineering.

Umpire assignments can shift true game totals by 0.3-0.7 runs. The edge
is NOT in blindly following umpire stats — it's in interaction effects
between umpire tendencies, pitcher styles, weather, and park factors.

Key umpire metrics:
    - K%: strikeout rate in their games
    - BB%: walk rate
    - Runs per game vs league average
    - Zone size rank (percentile, 100 = largest zone)

Interaction effects (the real edge):
    - Command pitchers who paint corners + wide zone = K props OVER
    - Power pitchers less affected by zone size
    - Two-strike bias: umps 2x likely to call ball as strike with 2 strikes
    - Blind spot: top of zone called incorrectly 27% of the time

Data source: Umpire assignments from MLB Stats API (day of game),
historical umpire stats from Statcast/Savant

References:
    - Research doc: docs/mlb/research/umpire-zones.md
"""

# TODO: Phase 2 implementation
# - compute_umpire_adjustment(umpire_name, pitcher_style, park_factors)
# - fetch_umpire_assignment(game_pk) — from MLB Stats API
# - compute_umpire_pitcher_interaction(zone_size, pitcher_k_bb_pct)
# - Integration with umpire_stats table in mlb_data.db
