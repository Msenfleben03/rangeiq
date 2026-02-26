"""Preseason projection blending with in-season phasing.

Blends external projection systems (ZiPS, Steamer) with observed in-season
data using a time-dependent weighting schedule:

    April:    90% projections / 10% observed
    May:      70% projections / 30% observed
    June:     50% projections / 50% observed
    July+:    20% projections / 80% observed

Composite projections consistently outperform any single system.
The edge comes from better in-season contextual adjustments, not
from better preseason projections.

References:
    - Research doc: docs/mlb/research/projection-systems.md
    - Data source: ZiPS and Steamer via FanGraphs (free)
"""

# TODO: Phase 1 implementation
# - ProjectionBlender class
# - Load ZiPS + Steamer from projections table
# - Compute composite (equal weight by default)
# - Time-dependent blending with observed season stats
# - Separate blending curves for pitchers vs batters
#   (pitcher metrics stabilize faster than batter metrics)
# - Handle mid-season callups with no projection (use observed only)
