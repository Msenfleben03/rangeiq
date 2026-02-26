# Umpire Strike Zone Research

## Impact

Umpire assignments can shift true game totals by 0.3-0.7 runs.
BU study: umpires made 34,000+ incorrect calls in a single season (2018).

## Key Biases

1. **Two-Strike Bias:** Umpires 2x likely to call a true ball as a strike
   with 2 strikes → suppresses BA → helps Under bettors
2. **Top-of-Zone Blind Spot:** Pitches called incorrectly ~27% of the time
   at the top of the strike zone
3. **Liberal vs Tight Zones:** Some umpires have zones 26% larger than others

## Betting Implications

| Umpire Trait | Scoring Effect | Betting Lean |
|-------------|---------------|--------------|
| High BCR (bad call ratio) | Increased variance + walks | Over |
| Large zone (kzone50) | Advantage to corner pitchers | Under / K props Over |
| Small zone | Forces pitchers to heart of zone | Over |
| Two-strike bias | Suppressed batting averages | Under |

## The Real Edge

NOT in blindly following umpire stats. The edge is in INTERACTION EFFECTS:

- Command pitcher + wide zone = K props OVER
- Power pitcher less affected by zone size
- Umpire tendency + weather + park = non-obvious interactions

## Data Sources

- Umpire assignments: MLB Stats API (available day of game)
- Historical stats: Baseball Savant / Statcast zone data
- Covers.com umpire betting stats

## Implementation Priority

Phase 2 (after core model). Add as contextual adjustment for totals.
