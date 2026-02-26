"""Pitcher evaluation and projection model.

Projects a starting pitcher's expected run allowance per game, incorporating:
- Skill metrics: K-BB%, SIERA, xFIP, xERA, Stuff+
- Recent form: exponential decay weighting of recent starts
- Matchup context: opposing lineup platoon composition
- Workload: pitch count trends, days rest
- Times Through Order Penalty (TTOP): OPS climbs ~.705 → .771

Stabilization rates (critical for early-season weighting):
    - Stuff+: ~80 pitches (usable after 2 starts)
    - K%: ~150 batters faced (~5-6 starts)
    - BB%: ~200 batters faced (~7-8 starts)
    - BABIP: ~2000 BIP (~3 years, regress heavily)

References:
    - Research doc: docs/mlb/research/pitching-metrics.md
    - Projection blending: docs/mlb/research/projection-systems.md
"""

# TODO: Phase 1 implementation
# - PitcherProjection class
# - Rolling stat computation with exponential decay
# - Preseason/in-season blending (90/10 April → 20/80 July)
# - TTOP adjustment for expected innings
# - Integration with projection_blender.py for early-season
