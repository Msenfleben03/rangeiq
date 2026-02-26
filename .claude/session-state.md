## Active Task
Session 24 — MLB expansion: brainstorming + skeleton file architecture

## Last Completed Step
All skeleton files created (45 files across models, features, pipelines, scripts, tests, docs).
Design document written. Research docs copied. NOT YET COMMITTED.

## Completed This Session
- [x] Brainstormed MLB expansion design (15 questions, all answered)
- [x] Wrote design doc: `docs/plans/2026-02-25-mlb-expansion-design.md`
- [x] Created 4 model skeletons: `models/sport_specific/mlb/` (poisson, pitcher, lineup, projection_blender)
- [x] Created 6 feature skeletons: `features/sport_specific/mlb/` (pitcher, lineup, bullpen, weather, park, umpire)
- [x] Created 7 pipeline skeletons: `pipelines/mlb_*.py` (stats_api, pybaseball, weather, projections, odds, lineup_monitor, park_factors)
- [x] Created 6 script skeletons: `scripts/mlb_*.py` (daily_run, fetch_historical, backtest, train, fetch_projections, init_db)
- [x] Created 5 test skeletons: `tests/test_mlb_*.py` (poisson, pitcher, stats_api, weather, daily_run)
- [x] Created 5 doc files: `docs/mlb/` (README, DATA_SOURCES, DATA_DICTIONARY, MODEL_ARCHITECTURE, PIPELINE_DESIGN)
- [x] Created 8 research stubs: `docs/mlb/research/` (pitching-metrics, bullpen-fatigue, weather-effects, park-factors, platoon-splits, umpire-zones, market-strategies, projection-systems)
- [x] Copied 2 source research docs into `docs/mlb/research/source-research-*.md`

## Key Design Decisions
- Hybrid DB: shared betting.db (bets, bankroll) + separate mlb_data.db (14 tables)
- Poisson run distribution model → single model outputs ML, RL, totals, F5
- Pitcher-centric full regression (NOT Elo-based)
- Event-driven pipeline (lineup confirmation triggers per-game predictions)
- Open-Meteo for weather (free, historical back to 1940)
- ZiPS + Steamer projection blending for early-season
- Phase 1: moneylines, Phase 2: totals + RL + weather, Phase 3: player props
- 3 seasons backtest (2023-2025), pre-2023 stretch goal
- Timeline: paper betting Opening Day, live by early May

## Files Created This Session (47 total)
### Design
- docs/plans/2026-02-25-mlb-expansion-design.md

### Models (4)
- models/sport_specific/mlb/poisson_model.py
- models/sport_specific/mlb/pitcher_model.py
- models/sport_specific/mlb/lineup_model.py
- models/sport_specific/mlb/projection_blender.py

### Features (7)
- features/sport_specific/mlb/__init__.py
- features/sport_specific/mlb/pitcher_features.py
- features/sport_specific/mlb/lineup_features.py
- features/sport_specific/mlb/bullpen_features.py
- features/sport_specific/mlb/weather_features.py
- features/sport_specific/mlb/park_features.py
- features/sport_specific/mlb/umpire_features.py

### Pipelines (7)
- pipelines/mlb_stats_api.py
- pipelines/mlb_pybaseball_fetcher.py
- pipelines/mlb_weather_fetcher.py
- pipelines/mlb_projections_fetcher.py
- pipelines/mlb_odds_provider.py
- pipelines/mlb_lineup_monitor.py
- pipelines/mlb_park_factors.py

### Scripts (6)
- scripts/mlb_daily_run.py
- scripts/mlb_fetch_historical.py
- scripts/mlb_backtest.py
- scripts/mlb_train_model.py
- scripts/mlb_fetch_projections.py
- scripts/mlb_init_db.py

### Tests (5)
- tests/test_mlb_poisson_model.py
- tests/test_mlb_pitcher_model.py
- tests/test_mlb_stats_api.py
- tests/test_mlb_weather_fetcher.py
- tests/test_mlb_daily_run.py

### Docs (15)
- docs/mlb/README.md
- docs/mlb/DATA_SOURCES.md
- docs/mlb/DATA_DICTIONARY.md
- docs/mlb/MODEL_ARCHITECTURE.md
- docs/mlb/PIPELINE_DESIGN.md
- docs/mlb/research/pitching-metrics.md
- docs/mlb/research/bullpen-fatigue.md
- docs/mlb/research/weather-effects.md
- docs/mlb/research/park-factors.md
- docs/mlb/research/platoon-splits.md
- docs/mlb/research/umpire-zones.md
- docs/mlb/research/market-strategies.md
- docs/mlb/research/projection-systems.md
- docs/mlb/research/source-research-playbook.md
- docs/mlb/research/source-research-quantitative.md

## Still Outstanding
- [ ] Commit and push skeleton (awaiting user approval)
- [ ] Update CLAUDE.md with MLB file structure
- [ ] Begin Phase 1 implementation (mlb_init_db.py first)
- [ ] Fetch 2023-2025 historical data
- [ ] Build Poisson model v1
