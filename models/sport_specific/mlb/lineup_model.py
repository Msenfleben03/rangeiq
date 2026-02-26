"""Lineup strength evaluation with platoon splits.

Projects a lineup's expected offensive output against a specific pitcher:
- Aggregate wRC+ and xwOBA for confirmed lineup
- Platoon adjustments: L/R splits for each batter vs starter handedness
- Park factor interaction with lineup handedness composition
- Rest and travel adjustments (eastward travel penalty)

Key insight from research: average platoon gap can reach 60+ wRC+ points
in extreme cases. Model lineup handedness composition against starting
pitcher handedness as a primary input.

References:
    - Research doc: docs/mlb/research/platoon-splits.md
    - Park interaction: docs/mlb/research/park-factors.md
"""

# TODO: Phase 1 implementation
# - LineupStrength class
# - Aggregate lineup wRC+ / xwOBA from confirmed batting order
# - Platoon split adjustment (regress small samples via Bayesian shrinkage)
# - Park factor interaction with handedness composition
# - Rest/travel penalty (eastward travel ~ cancel HFA)
# - Handle unconfirmed lineups: use projected/typical lineup
