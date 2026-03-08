# MLB Model Architecture

## Overview

Poisson regression model projecting expected runs (lambda) per team.
Single model outputs feed all market types: moneylines, run lines, totals, F5.

## Model Pipeline

```text
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│   Pitcher     │   │   Lineup     │   │  Contextual  │
│   Features    │   │   Features   │   │  Features    │
│               │   │              │   │              │
│ K-BB%, SIERA  │   │ wRC+, xwOBA  │   │ Park factors │
│ xFIP, Stuff+  │   │ Platoon adj  │   │ Weather      │
│ Rolling decay │   │ Handedness   │   │ Umpire       │
│ Bullpen xFIP  │   │ Rest/travel  │   │ HFA          │
└──────┬───────┘   └──────┬───────┘   └──────┬───────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                    ┌──────▼───────┐
                    │   Poisson    │
                    │  Regression  │
                    │              │
                    │ λ = exp(Xβ)  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
       ┌──────▼──────┐ ┌──▼──────┐ ┌──▼──────────┐
       │ λ_home      │ │ λ_away  │ │ λ_home_f5        │
       │ (full game) │ │ (full)  │ │ λ_away_f5        │
       │             │ │         │ │ ≈ λ_full × 5/9   │
       │             │ │         │ │ + 1st-inn bump   │
       └──────┬──────┘ └──┬──────┘ └──┬──────────────┘
              │            │            │
              └────────────┼────────────┘
                           │
                    ┌──────▼───────┐
                    │ Score Matrix │
                    │ P(H=i, A=j) │
                    │  i,j ∈ 0..15 │
                    └──────┬───────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                  │
  ┌──────▼──────┐  ┌──────▼──────┐   ┌──────▼──────┐
  │  Moneyline  │  │  Run Line   │   │   Totals    │
  │  P(H > A)   │  │ P(H > A+1.5)│   │ P(H+A > T) │
  └─────────────┘  └─────────────┘   └─────────────┘
```

## Feature Hierarchy (by importance)

1. **Starting pitcher quality** — K-BB%, SIERA, xFIP, Stuff+ (dominant factor)
2. **Opposing lineup strength** — platoon-adjusted wRC+/xwOBA
3. **Bullpen quality** — team bullpen xFIP, fatigue-adjusted availability
4. **Park factors** — event-specific, handedness-adjusted
5. **Home field advantage** — ~54% home win rate in MLB
6. **Weather** — wind direction/speed (especially for totals)
7. **Umpire** — zone size interaction with pitcher style
8. **Rest/travel** — eastward travel penalty, back-to-back series

## Poisson Distribution

Baseball scoring modeled as Poisson because runs are discrete, independent events.

```text
P(X = k) = (λ^k × e^(-λ)) / k!

where λ = expected runs for that team in that game
```

Exponent: 1.83 (Huemann, not the traditional 2.0)

## Preseason Projection Blending

| Month | Projections Weight | Observed Weight |
|-------|-------------------|-----------------|
| April | 90% | 10% |
| May | 70% | 30% |
| June | 50% | 50% |
| July+ | 20% | 80% |

## Metric Stabilization Rates

| Metric | Stabilizes At | Usable By |
|--------|--------------|-----------|
| Stuff+ | ~80 pitches | Start 2 |
| K% | ~150 BF | Start 5-6 |
| BB% | ~200 BF | Start 7-8 |
| Exit velocity | 16-20 games | Mid-April |
| OBP/SLG | ~500 PA | Mid-season |
| BA | ~910 PA | Never (>1 season) |
| BABIP (pitcher) | ~2000 BIP | Never (~3 years) |

## Validation

Model must pass Gatekeeper with MLB-specific extensions:

- Per-market-type CLV validation (ML, RL, totals independently)
- Pitcher availability temporal check (no post-game data leakage)
- Weather feature temporal correctness
- Three-season regime stability (Apr-May / Jun-Jul / Aug-Sep)
