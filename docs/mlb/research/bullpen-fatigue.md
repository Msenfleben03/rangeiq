# Bullpen Fatigue Research

## Fatigue as "Toxin" Model

Every pitch thrown is a fatigue-inducing toxin. Bayesian hierarchical models
establish clear dose-response relationship between pitch count and effectiveness.

| Threshold | Effect |
|-----------|--------|
| >15 pitches in outing | Small velocity decrease |
| >20 pitches in outing | Amplified performance dip |
| PC_L3 > 30-40 pitches | Reliever likely degraded or unavailable |
| 2+ consecutive days | High risk of velocity loss + command issues |
| High-leverage innings in last 2 days | Closer/setup likely unavailable |

## Modeling Impact

Split pitcher impact approximately 2/3 starter, 1/3 bullpen.
Adjust bullpen weight dynamically based on expected starter innings.

Bullpen ERA is ~1 full run more variable than starter ERA due to defense
and luck — use xFIP and SIERA over raw ERA for bullpen evaluation.

Highest-signal bullpen metrics:

- Hard-contact avoidance (barrel rate, hard-hit%)
- Ground-ball rate
- LOB% (r=-0.818 with bullpen ERA, but low pitcher control — regress)

## Opener Detection

Flag as opener when:

1. 5+ career appearances
2. Hasn't exceeded 2 IP in last 10 outings
3. Has opened at least once in last 20 appearances

When opener detected → default to team-average pitcher adjustment.

## Betting Edge

The real edge is AVAILABILITY TRACKING — books use cruder approximations.
Track: innings pitched L3/L7, pitches last outing, days since closer appearance.

## Sources

- "Out of gas: quantifying fatigue in MLB relievers" (2018)
- Outlier: https://help.outlier.bet/en/articles/11906728
