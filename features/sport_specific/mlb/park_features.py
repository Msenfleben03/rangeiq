"""Event-specific park factor feature engineering.

Park effects in MLB are enormous compared to any venue effect in
basketball or football. Critical insight: parks affect singles, doubles,
triples, strikeouts, and walks INDEPENDENTLY — not just home runs.

Must use event-specific factors, not a single run-scoring multiplier.
Account for handedness interaction (e.g., Yankee Stadium short right-field
porch disproportionately benefits LHB).

Park factor dimensions:
    - runs_factor: overall run-scoring environment
    - hr_factor: home run park factor (overall)
    - hr_factor_lhb / hr_factor_rhb: HR factor by batter handedness
    - hits_factor, doubles_factor, triples_factor
    - bb_factor, so_factor: walk and strikeout park effects

Notable parks:
    - Coors Field: balls travel ~9% farther, -3 inches breaking ball movement
    - Dodger Stadium: 132 HR factor (leads MLB)
    - Wrigley Field: wind-dependent, can shift total by full run

Data sources: FanGraphs park factors (free, updated annually)

References:
    - Research doc: docs/mlb/research/park-factors.md
"""

# TODO: Phase 2 implementation
# - compute_park_adjusted_lambda(raw_lambda, park_factors, lineup_handedness)
# - fetch_park_factors(season) — from FanGraphs via pybaseball
# - apply_handedness_interaction(park_hr_factor, pct_lhb_in_lineup)
# - Integration with park_factors table in mlb_data.db
