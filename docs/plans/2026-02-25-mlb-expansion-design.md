# MLB Expansion Design

**Date:** 2026-02-25
**Status:** Approved — skeleton created, implementation pending

## Decisions Summary

| # | Decision | Choice |
|---|----------|--------|
| 1 | Markets | All: moneylines, run lines, totals, player props (phase 2) |
| 2 | Model approach | Full regression, pitcher-centric, NOT Elo-based |
| 3 | Database | Hybrid: shared `betting.db` + separate `mlb_data.db` |
| 4 | Data sources | All free: MLB Stats API, pybaseball/FanGraphs, Statcast, Open-Meteo |
| 5 | Historical depth | 3 seasons (2023-2025), pre-2023 as stretch goal |
| 6 | Timeline | Paper betting by Opening Day, live by early May |
| 7 | Pitcher DB design | Raw game logs + matchup features computed at prediction time |
| 8 | Player props | Phase 2 (after core team-level model proves CLV) |
| 9 | File architecture | Mirror NCAAB pattern within existing directory structure |
| 10 | Run-scoring model | Poisson run distribution (single model → ML, RL, totals) |
| 11 | Preseason projections | Consume ZiPS + Steamer from FanGraphs, blend with observed |
| 12 | Pipeline timing | Event-driven (fallback to 3-cycle if too complex) |
| 13 | Weather source | Open-Meteo (free, no key, historical data for backtests) |
| 14 | Gatekeeper | Extend existing 5-dim framework with MLB-specific checks |
| 15 | Backtest enrichment | Phased: core pitcher signal first, weather/umpire for totals later |

## Architecture Overview

```text
                    ┌─────────────────────────────────────┐
                    │         data/mlb_data.db             │
                    │  (14 tables + views, game_pk key)    │
                    └──────────────┬──────────────────────┘
                                   │
        ┌──────────────────────────┼──────────────────────────┐
        │                          │                           │
  ┌─────▼─────┐           ┌───────▼───────┐          ┌───────▼───────┐
  │ Pipelines │           │   Features    │          │    Models     │
  │           │           │               │          │               │
  │ mlb_stats │──fetch──▶ │ pitcher_feat  │──feed──▶ │ poisson_model │
  │ pybaseball│           │ lineup_feat   │          │ pitcher_model │
  │ weather   │           │ bullpen_feat  │          │ lineup_model  │
  │ projections│          │ weather_feat  │          │ proj_blender  │
  │ lineup_mon│           │ park_feat     │          │               │
  │ park_fact │           │ umpire_feat   │          └───────┬───────┘
  │ odds      │           └───────────────┘                  │
  └───────────┘                                              │
                                                    ┌────────▼────────┐
                                                    │  Poisson Output │
                                                    │                 │
                                                    │ λ_home, λ_away  │
                                                    │ → win prob (ML) │
                                                    │ → run line prob │
                                                    │ → total prob    │
                                                    │ → F5 variants   │
                                                    └────────┬────────┘
                                                             │
                                                    ┌────────▼────────┐
                                                    │  Kelly Sizing   │
                                                    │  (shared infra) │
                                                    │  → CLV tracking │
                                                    │  → Gatekeeper   │
                                                    └─────────────────┘
```

## Database Schema

See `docs/mlb/DATA_DICTIONARY.md` for full schema (14 tables in `mlb_data.db`).
Shared tables (`betting.db`): bets, bankroll_log, predictions, odds_snapshots, calibration_metrics.

## Phase Plan

### Phase 1: Infrastructure + Moneylines (Weeks 1-3)
- Skeleton files, DB schema, data fetchers
- Historical data pull (2023-2025): games, pitcher logs, team stats, odds
- Poisson model v1: pitcher matchup + team strength → lambda → win prob
- Walk-forward backtest, Gatekeeper validation
- Paper betting moneylines by Opening Day

### Phase 2: Totals + Run Lines (Weeks 4-6)
- Weather enrichment (Open-Meteo historical + live)
- Park factors, umpire data
- Extend Poisson to totals and run line markets
- F5 innings modeling

### Phase 3: Player Props (Month 2+)
- Pitcher strikeout model (K-rate projections already exist)
- Batter props (hits, HRs, bases)
- Separate validation per prop type

## File Tree

```text
models/sport_specific/mlb/
├── __init__.py              (existing)
├── poisson_model.py         Poisson run distribution → ML/RL/totals/F5
├── pitcher_model.py         Pitcher evaluation and projection
├── lineup_model.py          Lineup strength with platoon splits
└── projection_blender.py    ZiPS/Steamer blending with observed data

features/sport_specific/mlb/
├── __init__.py
├── pitcher_features.py      K-BB%, SIERA, xFIP, Stuff+, rolling stats
├── lineup_features.py       Aggregate wRC+, platoon splits, xwOBA
├── bullpen_features.py      Fatigue tracking, availability, TTOP
├── weather_features.py      Wind direction/speed, temp, dome detection
├── park_features.py         Event-specific park factors by handedness
└── umpire_features.py       Zone size, K/BB rates, run impact

pipelines/
├── mlb_stats_api.py         MLB Stats API client (schedules, lineups, rosters)
├── mlb_pybaseball_fetcher.py   pybaseball wrapper (Statcast, FanGraphs)
├── mlb_weather_fetcher.py   Open-Meteo client (forecast + historical)
├── mlb_projections_fetcher.py  ZiPS/Steamer from FanGraphs
├── mlb_odds_provider.py     MLB odds (ESPN Core API + others)
├── mlb_lineup_monitor.py    Lineup confirmation polling / event-driven
└── mlb_park_factors.py      Park factor ingestion + computation

scripts/
├── mlb_daily_run.py         Daily pipeline orchestrator (event-driven)
├── mlb_fetch_historical.py  Bulk fetch 2023-2025 data
├── mlb_backtest.py          Walk-forward backtesting
├── mlb_train_model.py       Model training
├── mlb_fetch_projections.py Preseason projections pull
└── mlb_init_db.py           Initialize mlb_data.db schema

tests/
├── test_mlb_poisson_model.py
├── test_mlb_pitcher_model.py
├── test_mlb_stats_api.py
├── test_mlb_weather_fetcher.py
└── test_mlb_daily_run.py

docs/mlb/
├── README.md                Overview and index
├── DATA_SOURCES.md          API endpoints, libraries, rate limits
├── DATA_DICTIONARY.md       mlb_data.db field definitions + schema SQL
├── MODEL_ARCHITECTURE.md    Poisson design, feature hierarchy, weighting
├── PIPELINE_DESIGN.md       Event-driven pipeline, timing, state machine
└── research/
    ├── pitching-metrics.md      SIERA, K-BB%, Stuff+, stabilization rates
    ├── bullpen-fatigue.md       Fatigue modeling, pitch count thresholds
    ├── weather-effects.md       Wind, temperature, humidity research
    ├── park-factors.md          Event-specific park effects, handedness
    ├── platoon-splits.md        L/R matchup advantages
    ├── umpire-zones.md          Strike zone analysis, umpire tendencies
    ├── market-strategies.md     F5, totals, contrarian underdogs, K props
    └── projection-systems.md    ZiPS, Steamer, PECOTA, blending weights
```
