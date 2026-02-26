"""Pitcher-specific feature engineering for MLB model.

Computes rolling pitcher skill metrics from game logs, respecting
temporal boundaries (no look-ahead bias). Features ordered by
predictive power and stabilization speed:

Tier 1 (fast-stabilizing, highest signal):
    - K-BB%: single most telling rate stat, stabilizes ~150 BF
    - Stuff+: stabilizes at ~80 pitches, best early-season metric
    - CSW%: called strike + whiff %, combines command and stuff

Tier 2 (moderate stabilization):
    - SIERA: gold standard for pitcher evaluation in betting
    - xFIP: normalizes HR/FB rate to league average
    - xERA: Statcast expected ERA from exit velo + launch angle

Tier 3 (slow-stabilizing, regress heavily):
    - BABIP: needs ~2000 BIP (~3 years), always regress toward .300
    - LOB%: strand rate, r=-0.818 with bullpen ERA but low control

References:
    - Research doc: docs/mlb/research/pitching-metrics.md
"""

# TODO: Phase 1 implementation
# - compute_rolling_pitcher_stats(player_id, as_of_date, window_games=15)
# - compute_decay_weighted_stats(game_logs, half_life=10)
# - compute_stabilized_metrics(observed, projections, games_started)
# - Exponential decay weighting for recent starts
# - Integration with pitcher_game_logs and pitcher_season_stats tables
