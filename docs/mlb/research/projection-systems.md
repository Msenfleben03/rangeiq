# Projection Systems Research

## Available Systems

| System | Source | Cost | Notes |
|--------|--------|------|-------|
| **ZiPS** | FanGraphs | Free | Dan Szymborski, good aging curves |
| **Steamer** | FanGraphs | Free | Weighted recent performance |
| **PECOTA** | Baseball Prospectus | Paid | Similarity-based, premium |
| **THE BAT X** | Derek Carty / EV Analytics | Paid | DFS + betting bridge |

## Blending Strategy

Composite projections consistently outperform any single system.
Default: equal weight ZiPS + Steamer (both free on FanGraphs).

## In-Season Phasing Schedule

| Month | Projections | Observed | Rationale |
|-------|------------|----------|-----------|
| April | 90% | 10% | Metrics haven't stabilized |
| May | 70% | 30% | K% starting to stabilize (~150 BF) |
| June | 50% | 50% | Sufficient sample for most rate stats |
| July+ | 20% | 80% | Season data dominates |

## Early-Season Strategy

- Weight fast-stabilizing metrics heavily: K%, BB%, Stuff+, exit velocity
- Use projections for slow-stabilizing: BA, BABIP, HR rates
- Statcast metrics (exit velo, launch angle) stabilize at 16-20 games
- Stuff+ stabilizes at ~80 pitches — usable after 2 starts

## Mid-Season Callups

Players with no preseason projection: use observed data only.
Apply aggressive regression toward replacement level until sample size
reaches stabilization thresholds.

## Implementation

1. Fetch ZiPS + Steamer via pybaseball preseason
2. Store in projections table with system='zips'/'steamer'/'composite'
3. projection_blender.py manages time-dependent weighting
4. Separate blending curves for pitchers (faster stabilization) vs batters

## Sources

- FanGraphs projections page (updated annually)
- pybaseball: `pitching_stats()` / `batting_stats()` with projection system filter
