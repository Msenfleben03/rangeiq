# MLB Betting Model Documentation

## Overview

Full regression model for MLB betting built on Poisson run distributions.
Projects expected runs per team → derives moneyline, run line, total, and F5 probabilities.

## Key Differences from NCAAB

| Aspect | NCAAB | MLB |
|--------|-------|-----|
| Core model | Elo + Barttorvik ensemble | Poisson regression |
| Primary driver | Team-level ratings | Starting pitcher matchup |
| Games/day | 5-15 | 10-15 |
| Season length | ~35 games/team | 162 games/team |
| Markets | Spreads, moneylines | ML, run lines, totals, F5, props |
| Pipeline timing | Single morning run | Event-driven (lineup-dependent) |
| Data sources | ESPN API, Barttorvik | MLB Stats API, pybaseball, FanGraphs |
| Database | Shared betting.db | Hybrid: betting.db + mlb_data.db |
| Preseason | Elo carries over | ZiPS/Steamer projection blending |
| Weather impact | None | Major (especially totals) |

## Documentation Index

- [DATA_SOURCES.md](DATA_SOURCES.md) — API endpoints, libraries, rate limits
- [DATA_DICTIONARY.md](DATA_DICTIONARY.md) — mlb_data.db schema and field definitions
- [MODEL_ARCHITECTURE.md](MODEL_ARCHITECTURE.md) — Poisson model design and feature hierarchy
- [PIPELINE_DESIGN.md](PIPELINE_DESIGN.md) — Event-driven pipeline architecture

## Research

- [pitching-metrics.md](research/pitching-metrics.md) — SIERA, K-BB%, Stuff+, stabilization
- [bullpen-fatigue.md](research/bullpen-fatigue.md) — Fatigue modeling and availability
- [weather-effects.md](research/weather-effects.md) — Wind, temperature, humidity
- [park-factors.md](research/park-factors.md) — Event-specific park effects
- [platoon-splits.md](research/platoon-splits.md) — L/R matchup advantages
- [umpire-zones.md](research/umpire-zones.md) — Strike zone analysis
- [market-strategies.md](research/market-strategies.md) — F5, totals, K props, contrarian
- [projection-systems.md](research/projection-systems.md) — ZiPS, Steamer, blending

## Design Document

Full design with all decisions: [docs/plans/2026-02-25-mlb-expansion-design.md](../plans/2026-02-25-mlb-expansion-design.md)
