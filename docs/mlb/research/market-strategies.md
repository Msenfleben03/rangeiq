# MLB Market Strategies Research

## Documented Edges

### 1. Wind-Based Totals (55.5% Since 2005)

Wind in from center at 5+ mph → bet Under. Only 1 losing season in 14 years.
Act on weather info before lines reflect it (especially Wrigley).

### 2. First-Five-Innings (F5)

Isolates starting pitcher matchup, eliminates bullpen variance.
Only 30 pitchers average 6+ IP/start. Sportsbooks invest less modeling
effort in F5 → structural inefficiency.
Best when: ace vs #5 starter, or dominant starter behind weak bullpen.

### 3. Contrarian Underdog + Reverse Line Movement

Teams <30% of ML bets + 10+ cents reverse line movement:
+72.71 units at 4.2% ROI since tracking began.
MLB underdogs win ~44% of games, need only ~43.5% at +130 avg to break even.
Divisional underdogs with high totals (≥8.5): +172.95 units at 2.3% ROI.

### 4. Fading Streaking Home Teams

Bet visitor when home team on exactly 4-game win streak:
~7% ROI on ML and RL, ~100 occurrences/year, profitable 8/10 years.
Public overreacts to recent performance.

### 5. Strikeout Props (Phase 2)

Largest inefficiency in player prop markets.
Inputs: pitcher K%, opponent team K%, chase rate (O-Swing%), umpire zone.
High-K pitcher vs 25%+ team K rate = prime Over spot.
Books adjust slowly after late lineup changes.

## Vig Management (CRITICAL)

| Line Type | Vig | Impact on 1000 Bets |
|-----------|-----|---------------------|
| Dime lines (-105/-105) | ~2.4% | Baseline |
| 20-cent lines (-110/-110) | ~4.5% | Costs 1-2% ROI |

For most models, 1-2% IS the entire edge. Vig discipline is essential.

## Sharp-Tolerant Books

| Book | Notes |
|------|-------|
| Pinnacle | Lowest margins, never limits (via Asian brokers) |
| Circa Sports | High limits, tolerates sharp action |
| Heritage Sports | -108 juice, -104 overnight |
| BetAnySports | Dime run lines, nickel overnight |

## Line Movement Timeline

1. Opening odds appear overnight (Bookmaker first, Heritage -104 overnight)
2. Lines sharpen through morning (sharp action)
3. **LARGEST MOVEMENT: lineup confirmation** (2-4h pre-game, 10-30+ cents)
4. Late sharp money + weather in final 30-60 minutes

ALWAYS bet "listed pitcher" — if pitcher changes, pricing basis evaporates.

## Realistic Benchmarks

- FiveThirtyEight: 57.7% correct (2016-2018)
- FanGraphs: 56.9%
- Best academic: 57-59.5%
- Profitable at 47% win rate on plus-money underdogs
- Realistic annual ROI: 2-5%
- Primary validation: CLV vs Pinnacle de-vigged closing line

## Decorrelation Principle (Hubáček et al.)

Your model's value is where it DISAGREES with the market.
If your model merely recapitulates Pinnacle pricing, vig guarantees losses.
The edge lives in: pitcher evaluation nuances, weather-park interactions,
bullpen availability asymmetries, lineup-specific platoon effects.
