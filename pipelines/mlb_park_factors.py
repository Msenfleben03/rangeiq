"""Park factor data ingestion and computation.

Fetches event-specific park factors from FanGraphs via pybaseball.
Parks affect singles, doubles, triples, strikeouts, and walks
independently — not just home runs.

Notable parks:
    - Coors Field: balls travel ~9% farther, -3" breaking ball movement
    - Dodger Stadium: 132 HR factor (leads MLB)
    - Wrigley Field: wind-dependent (variable within game)
    - Yankee Stadium: short right-field porch (LHB advantage)

Factors stored per-team, per-season with handedness breakdown for HRs.
Updated annually (stable year-to-year for most parks).

Data source: FanGraphs park factors via pybaseball.
Enhanced: Ballpark Pal (premium, optional) for ML-based factors.

References:
    - Research doc: docs/mlb/research/park-factors.md
    - Schema: park_factors table in mlb_data.db
"""

# TODO: Phase 2 implementation
# - ParkFactorsFetcher class
# - fetch_park_factors(season) → DataFrame with event-specific factors
# - store_park_factors(factors_df, season) → insert into mlb_data.db
# - Stadium metadata: lat/lon, dome flag, orientation angle (for wind)
# - 30 MLB stadium reference data (hardcoded or fetched)
# - Annual refresh logic (park factors change rarely)
