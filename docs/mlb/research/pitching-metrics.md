# Pitching Metrics Research

## Metric Hierarchy (by predictive power for betting)

### Tier 1: Fast-Stabilizing, Highest Signal

**Stuff+** — Stabilizes at ~80 pitches (~2 starts). Best early-season metric.
Pitching+ (Stuff+ + Location+) outpredicts all projection systems for relievers
before the season begins.

**K-BB%** — Single most telling rate stat. Strips away long ball variance and
BABIP luck. Focuses purely on strike zone dominance. K% stabilizes ~150 BF,
BB% ~200 BF. A 20%+ K-BB% is elite.

**CSW%** — Called Strike + Whiff percentage. Captures both command and stuff quality.

### Tier 2: Moderate Stabilization

**SIERA** — Gold standard for pitcher evaluation in betting. Unlike FIP, recognizes
that generating weak contact is a repeatable skill. Models how high-K pitchers
also tend to allow lower BABIP. Approximately r ≈ 0.52 for predicting next-year ERA.

**xFIP** — Normalizes HR/FB rate to league average. Critical for pitchers in
extreme parks (Coors, Great American). Also r ≈ 0.52 for next-year ERA.

**xERA** — Statcast expected ERA from exit velocity + launch angle of every BIP.
Identifies pitchers helped/hurt by defense quality.

### Tier 3: Slow-Stabilizing (Regress Heavily)

**BABIP** — Needs ~2000 BIP (~3 years). Always regress toward .300.

**LOB%** — Strand rate, r=-0.818 with bullpen ERA. But largely outside pitcher
control — regress aggressively toward league average.

## Exponential Decay Weighting

Recent starts weighted more heavily than season-long or career stats.
FiveThirtyEight approach: rolling Game Scores normalized for era, stadium, opponent.

## Times Through the Order Penalty (TTOP)

OPS-against climbs from .705 (1st time) → .735 (2nd) → .771 (3rd).
Modern managers pull starters earlier → higher bullpen burden.
Model should flag when starter likely to face order 3rd time.

## Sources

- FanGraphs SIERA: https://library.fangraphs.com/pitching/siera/
- The Book (Tango, Lichtman, Dolphin) — platoon, TTOP, leverage
- Statcast search: https://baseballsavant.mlb.com/statcast_search
