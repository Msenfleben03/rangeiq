"""Preseason projection system fetcher (ZiPS + Steamer from FanGraphs).

Fetches pitcher and batter projections from FanGraphs, which publishes
ZiPS and Steamer for free. Used for early-season modeling before
observed data stabilizes.

Blending schedule (managed by projection_blender.py):
    April:    90% projections / 10% observed
    May:      70% projections / 30% observed
    June:     50% projections / 50% observed
    July+:    20% projections / 80% observed

Key projected stats:
    Pitchers: ERA, FIP, K%, BB%, IP
    Batters: wRC+, wOBA, PA

Data access: pybaseball or direct FanGraphs scrape.
Store in projections table with system='zips'/'steamer'/'composite'.

References:
    - Research doc: docs/mlb/research/projection-systems.md
    - Blending design: models/sport_specific/mlb/projection_blender.py
"""

# TODO: Phase 1 implementation (needed for early-season model)
# - ProjectionsFetcher class
# - fetch_zips_pitchers(season) → pitcher projections
# - fetch_zips_batters(season) → batter projections
# - fetch_steamer_pitchers(season) → pitcher projections
# - fetch_steamer_batters(season) → batter projections
# - compute_composite(zips, steamer, weights=(0.5, 0.5))
# - store_projections(projections_df, system, season)
# - Should be run once preseason and cached in projections table
