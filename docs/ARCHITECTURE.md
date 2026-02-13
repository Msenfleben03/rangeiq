# Sports Betting System Architecture

## High-Level System Diagram

```text
 ╔══════════════════════════════════════════════════════════════════════════════╗
 ║                        SPORTS BETTING SYSTEM ARCHITECTURE                  ║
 ╚══════════════════════════════════════════════════════════════════════════════╝

 ┌─────────────────────────── DATA INGESTION ───────────────────────────────┐
 │                                                                          │
 │  pipelines/                                                              │
 │  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐       │
 │  │ ncaab_data_     │  │ polymarket_      │  │ kalshi_           │       │
 │  │ fetcher.py      │  │ fetcher.py       │  │ fetcher.py        │       │
 │  │ (sportsipy)     │  │ (Polymarket API) │  │ (Kalshi REST API) │       │
 │  └───────┬─────────┘  └────────┬─────────┘  └─────────┬─────────┘       │
 │          │                     │                       │                 │
 │  ┌───────┴─────────┐  ┌───────┴──────────┐  ┌─────────┴─────────┐       │
 │  │ closing_odds_   │  │ batch_fetcher.py │  │ arb_scanner.py    │       │
 │  │ collector.py    │  │ (async batching) │  │ ──► arb_detector  │       │
 │  └───────┬─────────┘  └────────┬─────────┘  └─────────┬─────────┘       │
 └──────────┼──────────────────────┼──────────────────────┼─────────────────┘
            │                      │                      │
            ▼                      ▼                      ▼
 ┌──────────────────────────── STORAGE ─────────────────────────────────────┐
 │                                                                          │
 │  data/                       tracking/                                   │
 │  ┌──────────┐  ┌───────┐    ┌──────────────┐  ┌──────────────────┐      │
 │  │ raw/     │  │ odds/ │    │ database.py  │  │ forecasting_db.py│      │
 │  │ processed│  │       │    │ (SQLite)     │  │ (belief tracking)│      │
 │  │ external │  │       │    │  ┌─────────┐ │  └──────────────────┘      │
 │  └────┬─────┘  └───┬───┘    │  │ bets    │ │  ┌──────────────────┐      │
 │       │            │        │  │ bankroll│ │  │ models.py (ORM)  │      │
 │       │            │        │  │ predict.│ │  └──────────────────┘      │
 │       │            │        │  │ ratings │ │  ┌──────────────────┐      │
 │       │            │        │  └─────────┘ │  │ cost_tracker.py  │      │
 │       │            │        └──────────────┘  └──────────────────┘      │
 └───────┼────────────┼──────────────────────────────────────────────────────┘
         │            │
         ▼            ▼
 ┌──────────────── FEATURE ENGINEERING & MODELING ──────────────────────────┐
 │                                                                          │
 │  config/                   features/               models/               │
 │  ┌────────────┐            ┌──────────┐            ┌──────────────────┐  │
 │  │constants.py│──────────► │(planned) │──────────► │ elo.py           │  │
 │  │ ELO params │            │eng., sel.│            │ (core Elo math)  │  │
 │  │settings.py │            └──────────┘            └────────┬─────────┘  │
 │  └────────────┘                                             │            │
 │                                                             ▼            │
 │                      models/sport_specific/                              │
 │                      ┌──────────┬──────────┬──────────┬──────────┐       │
 │                      │ ncaab/   │ ncaaf/   │ nfl/     │ mlb/     │       │
 │                      │team_     │(planned) │(planned) │(planned) │       │
 │                      │ratings.py│          │          │          │       │
 │                      └────┬─────┴──────────┴──────────┴──────────┘       │
 └───────────────────────────┼──────────────────────────────────────────────┘
                             │
                             ▼
 ┌──────────────── BETTING CALCULATIONS ────────────────────────────────────┐
 │                                                                          │
 │  betting/                                                                │
 │  ┌─────────────────┐  ┌──────────────────┐  ┌────────────────────┐       │
 │  │odds_converter.py│  │ arb_detector.py  │  │ (planned)          │       │
 │  │ amer↔dec↔prob   │  │ cross-book arb   │  │ kelly.py, ev.py    │       │
 │  │                 │  │ detection        │  │ clv.py             │       │
 │  └─────────────────┘  └──────────────────┘  └────────────────────┘       │
 └──────────────────────────────────────────────────────────────────────────┘
                             │
                             ▼
 ┌──────────────── BACKTESTING & VALIDATION ────────────────────────────────┐
 │                                                                          │
 │  backtesting/                                                            │
 │  ┌──────────────────┐  ┌────────────┐  ┌──────────────┐                  │
 │  │ walk_forward.py  │  │ metrics.py │  │ simulation.py│                  │
 │  │ (time-series CV) │  │ (eval)     │  │ (Monte Carlo)│                  │
 │  └──────────┬───────┘  └─────┬──────┘  └──────┬───────┘                  │
 │             └────────────────┼─────────────────┘                         │
 │                              ▼                                           │
 │  validators/   ═══════ 5-DIMENSION GATE (219 tests) ═══════             │
 │                                                                          │
 │  ┌────────────┐ ┌─────────────┐ ┌──────────┐ ┌──────────┐               │
 │  │ TEMPORAL   │ │ STATISTICAL │ │ OVERFIT  │ │ BETTING  │               │
 │  │ (26 tests) │ │ (49 tests)  │ │(42 tests)│ │(52 tests)│               │
 │  │            │ │             │ │          │ │          │               │
 │  │ leakage    │ │ sample size │ │ IS vs OOS│ │ CLV      │               │
 │  │ look-ahead │ │ Sharpe      │ │ variance │ │ vig      │               │
 │  │ future-info│ │ p-values    │ │ features │ │ Kelly    │               │
 │  └──────┬─────┘ └──────┬──────┘ └────┬─────┘ └────┬─────┘               │
 │         └───────────────┼─────────────┼────────────┘                     │
 │                         ▼             │                                  │
 │                 ┌───────────────────┐  │                                  │
 │                 │   GATEKEEPER      │◄─┘                                  │
 │                 │   (29 tests)      │                                     │
 │                 │                   │                                     │
 │                 │  ┌─────┐ ┌─────┐ │                                     │
 │                 │  │PASS │ │QUAR.│ │                                     │
 │                 │  └──┬──┘ └──┬──┘ │                                     │
 │                 └─────┼───────┼────┘                                     │
 └───────────────────────┼───────┼──────────────────────────────────────────┘
                         │       │
                         ▼       ▼
                    ┌────────┐ ┌──────────────┐
                    │DEPLOY  │ │ data/        │
                    │(live   │ │ quarantine/  │
                    │betting)│ │ scorecards/  │
                    └────────┘ └──────────────┘

 ┌──────────────── TEST SUITE ──────────────────────────────────────────────┐
 │  tests/                                                                  │
 │  ┌──────────────┐ ┌─────────────────────┐ ┌──────────────────────────┐   │
 │  │ test_elo.py  │ │ test_backtesting.py │ │ test_temporal_validator  │   │
 │  │ test_setup   │ │ test_forecasting_db │ │ test_statistical_val.   │   │
 │  │              │ │                     │ │ test_overfit_validator   │   │
 │  │              │ │                     │ │ test_betting_validator   │   │
 │  │              │ │                     │ │ test_gatekeeper          │   │
 │  └──────────────┘ └─────────────────────┘ └──────────────────────────┘   │
 └──────────────────────────────────────────────────────────────────────────┘

 ═══════════════════════════ DATA FLOW SUMMARY ══════════════════════════════

   APIs (sportsipy, Polymarket, Kalshi)
     │
     ▼
   Pipelines (fetch, batch, collect closing odds)
     │
     ▼
   Storage (SQLite DB + flat files in data/)
     │
     ▼
   Models (Elo ratings → sport-specific implementations)
     │
     ▼
   Betting Math (odds conversion, EV, edge calculation)
     │
     ▼
   Validation (5-dimension gate: temporal → statistical → overfit → betting → gatekeeper)
     │
     ├── PASS ──► Deploy to live betting (DraftKings, FanDuel, etc.)
     └── FAIL ──► Quarantine + scorecard for review
```

## Key Architectural Properties

1. **Linear pipeline flow** - data moves top-down from ingestion
   through modeling to validation before any deployment
2. **The Gatekeeper is the critical choke point** - all 219 tests
   across 5 dimensions must pass before a model goes live
3. **Two parallel tracks** - sports betting (NCAAB Elo, odds) and
   prediction markets (Polymarket/Kalshi) share storage and tracking
4. **NCAAB is the only active sport** - MLB/NFL/NCAAF models are
   stubbed out as `__init__.py` only
5. **Planned but not yet built** - `kelly.py`, `ev.py`, `clv.py`,
   and feature engineering are referenced in CLAUDE.md but don't exist

## Module Dependencies

```text
config/constants.py ──► models/elo.py ──► models/sport_specific/ncaab/team_ratings.py
                                                        │
pipelines/* ──► tracking/database.py (SQLite)           │
                                                        ▼
betting/arb_detector.py ◄── pipelines/arb_scanner.py   scripts/validate_ncaab_elo.py
                                                        │
                                                        ▼
                                              backtesting/validators/*
```

## Sportsbook Distribution (Live Deployment Target)

| Book | Allocation | Purpose |
|------|-----------|---------|
| DraftKings | $1,000 | Primary volume, props |
| FanDuel | $1,000 | Line shopping |
| BetMGM | $750 | Soft lines |
| Caesars | $750 | Line shopping |
| ESPN BET | $500 | Backup |

---
Generated: 2026-02-12
