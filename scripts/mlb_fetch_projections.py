"""Fetch preseason projections (ZiPS + Steamer) from FanGraphs.

Run once before the season starts to populate the projections table.
Used by projection_blender.py for early-season modeling.

FanGraphs publishes projections for free:
    - ZiPS (Dan Szymborski): component-based, good at aging curves
    - Steamer: weighted recent performance, consistent baseline

Usage:
    python scripts/mlb_fetch_projections.py --season 2026
    python scripts/mlb_fetch_projections.py --season 2026 --system zips
    python scripts/mlb_fetch_projections.py --season 2026 --system steamer

References:
    - Research: docs/mlb/research/projection-systems.md
    - Blender: models/sport_specific/mlb/projection_blender.py
"""

# TODO: Phase 1 implementation (needed before Opening Day)
# - Fetch ZiPS pitcher projections via pybaseball
# - Fetch ZiPS batter projections via pybaseball
# - Fetch Steamer pitcher projections via pybaseball
# - Fetch Steamer batter projections via pybaseball
# - Compute composite projections (equal weight default)
# - Store in projections table with system and fetched_date
# - Player ID resolution (FanGraphs → MLBAM)
