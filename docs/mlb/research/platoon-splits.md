# Platoon Splits Research

## The Effect

Average platoon advantage: ~8% boost to offensive performance when batter
has handedness advantage (LHB vs RHP, RHB vs LHP).

Extreme cases: 60+ wRC+ point gap (e.g., Joc Pederson: 128 vs RHP, 59 vs LHP).

## Modeling Approach

Model lineup handedness composition against starting pitcher handedness
as a PRIMARY input. This is one of the most consistent and stable effects
in baseball.

## Sample Size Warning

A player's .400 average against lefties over 50 PA is statistically meaningless.
Professional models use Bayesian regression to pull small-sample splits back
toward the player's overall career mean.

Rule of thumb: need 200+ PA in a split for it to carry meaningful weight
independent of overall stats.

## BvP (Batter vs Pitcher) History

Consensus from FanGraphs and The Book: BvP stats are MOSTLY NOISE.
Need 50+ PA for minimal signal, and matchup occurred over years during which
both players changed. Use BvP only as minor tiebreaker for K props with
extreme sample sizes.

## Implementation

- Compute lineup handedness composition (% L/R/S batters in confirmed lineup)
- Fetch platoon-specific wRC+/xwOBA for each batter
- Apply Bayesian shrinkage to regress small samples toward overall mean
- Aggregate platoon-adjusted lineup strength vs starter handedness
