# NCAAB Model Recovery Plan

**Date**: 2026-03-07
**Status**: PENDING APPROVAL
**Goal**: Restore NCAAB model to full operational state after Mar 4 data wipe

---

## Context

The Mar 4 incident wiped all historical data. Session 47 recovered:
- 2026 game scores (5,954 games)
- 2026 Elo model (714 teams, cold-start — no historical warmup)
- Barttorvik 2020-2025 historical ratings (347,392 ratings via CBBdata) + 2026 daily scrape
- KenPom 2020-2026 ratings (2,522 team-season ratings)
- beautifulsoup4 installed, python-dotenv wired into settings.py

**Still missing**: Historical scores (2020-2025), historical odds, calibration data,
closing odds collection (never activated).

---

## Phase 1: Historical Score Recovery (2020-2025)

**Script**: `fetch_season_data.py --season YYYY --no-odds`
**Source**: ESPN API (free, proven — fetched 5,954 games for 2026 in 4 min)
**Output**: `data/raw/ncaab/ncaab_games_YYYY.parquet`

### Execution
Run 2 concurrent ESPN instances:
```
Wave 1: 2020 + 2021   (running now)
Wave 2: 2022 + 2023   (chain when wave 1 completes)
Wave 3: 2024 + 2025   (chain when wave 2 completes)
```

### Acceptance Gate
- Each season: >= 4,000 games
- All 6 parquet files present in `data/raw/ncaab/`

### Estimated Time: ~25 min total (4-5 min per season, 2 concurrent)

---

## Phase 2: Historical Odds Backfill (2020-2025)

**Script**: `backfill_historical_odds.py --season YYYY --resume`
**Source**: ESPN Core API (free, no key required)
**Output**: `data/odds/ncaab_odds_YYYY.parquet` (opening + closing per provider)

### What It Captures (all three market types)
| Market | Opening | Closing | Provider |
|--------|---------|---------|----------|
| Moneyline | home_ml_open, away_ml_open | home_ml_close, away_ml_close | Per-provider (ESPN BET 58) |
| Spread | home_spread_open, away_spread_open + odds | home_spread_close, away_spread_close + odds | Per-provider |
| Totals | total_open, over_odds_open, under_odds_open | total_close, over_odds_close, under_odds_close | Per-provider |

### Why This Script (not fetch_season_data.py)
- Dedicated checkpoint/resume per season (file: `data/odds/checkpoints/`)
- Separates opening vs. closing explicitly
- Per-provider rows (not merged columns)
- Can interrupt and resume safely across sessions

### Execution
Run sequentially (single ESPN Core API stream, 2 req/s rate limit):
```
2020 → 2021 → 2022 → 2023 → 2024 → 2025
```

### Acceptance Gate
- Each season: >90% games with odds data
- Opening AND closing odds present for completed games

### Estimated Time: ~2-3 hours per season, ~12-18 hours total
**Recommendation**: Start and run overnight. Checkpoint/resume handles interruptions.

---

## Phase 3: Elo Retraining (full warmup)

**Script**: `train_ncaab_elo.py --end 2026`
**Depends on**: Phase 1 complete (all 6 season parquets)

### What Changes
- Currently: Elo trained on 2026 only (cold-start, ratings are coarse)
- After: 6 seasons of warmup (2020-2026), ratings properly calibrated

### Execution
```bash
venv/Scripts/python.exe scripts/train_ncaab_elo.py --end 2026
```

### Acceptance Gate
- 6 seasons processed (no "Skipping season" errors)
- Mean rating ~1500, range ~[1200, 1900]
- Top 25 looks reasonable (Duke, Michigan, Arizona near top)

### Estimated Time: ~3 min

---

## Phase 4: Backtesting + Calibration

**Script**: `backtest_ncaab_elo.py --barttorvik --test-season 2025 --calibrated-kelly`
**Depends on**: Phase 1, 2, 3 all complete

### What This Produces
- Walk-forward backtest results (2025 test season, 2020-2024 training)
- Platt calibration data: (edge, win/loss) pairs
- KellySizer calibration curve (corrects ~10pp model overconfidence)

### Execution
```bash
# Standard backtest
venv/Scripts/python.exe scripts/backtest_ncaab_elo.py --barttorvik --test-season 2025

# With calibrated Kelly (needs backtest results from above)
venv/Scripts/python.exe scripts/backtest_ncaab_elo.py --barttorvik --test-season 2025 --calibrated-kelly
```

### Acceptance Gate
- Backtest completes without errors
- Results comparable to pre-wipe: ROI ~+24%, CLV > 0
- Calibrator fitted successfully (no "No backtest data for calibration" warnings)

### Estimated Time: ~5-10 min

---

## Phase 5: Closing Odds Collection (activate for live betting)

**Script**: `closing_odds_collector.py`
**Status**: Code exists, never wired into pipeline

### Current Architecture Gap
- Opening odds: captured nightly via `fetch_opening_odds.py` (pipeline step 9)
- Closing odds: **never captured** — `bets.odds_closing` is always NULL
- CLV formula incomplete: falls back to opening odds, understating true CLV

### Fix: Post-Game Closing Odds Retrieval
Closing odds are available from ESPN Core API after a game starts (they're the
final pre-game line). Rather than scraping 15 min before each game, we retrieve
closing odds from ESPN Core API during the next pipeline run (after games complete).

**Implementation approach**:
1. Add a `collect_closing_odds` step to `daily-pipeline.ps1` that runs AFTER
   `settle_bets` — queries ESPN Core API for closing odds on recently completed games
2. Uses `ESPNCoreOddsFetcher` (same as backfill) — no Selenium dependency needed
3. Updates `odds_snapshots` (is_closing=True) and `bets.odds_closing`

### Execution
- New script: `scripts/collect_closing_odds.py`
- Runs daily in pipeline after settlement
- Fetches closing odds for any games completed in the last 48 hours
  that don't yet have closing odds recorded

### Acceptance Gate
- Script runs without errors in daily pipeline
- `bets.odds_closing` populated for settled bets
- CLV calculation uses actual closing lines

### Estimated Time: Implementation ~1 hour

---

## Phase 6: Dashboard Refresh + Verification

**Depends on**: Phases 3-5 complete

### Execution
```bash
venv/Scripts/python.exe scripts/generate_dashboard_data.py
venv/Scripts/python.exe scripts/deploy_dashboard.py
```

### Final Verification Checklist
- [ ] All 7 season parquets exist (2020-2026)
- [ ] Historical odds: >90% coverage per season (2020-2025)
- [ ] Elo trained on 6 seasons, ratings look correct
- [ ] Backtest results regenerated, Platt calibrator fitted
- [ ] Daily pipeline runs end-to-end without errors
- [ ] Opening odds collected for upcoming games
- [ ] Closing odds collected for completed games
- [ ] CLV calculation uses real closing lines
- [ ] Dashboard deployed with full historical data

---

## Execution Timeline

| Phase | Task | Duration | Can Overlap? |
|-------|------|----------|-------------|
| 1 | Score recovery (6 seasons, 2 concurrent) | ~25 min | Running now |
| 2 | Odds backfill (6 seasons, sequential) | ~12-18 hrs | After Phase 1; run overnight |
| 3 | Elo retraining | ~3 min | After Phase 1 |
| 4 | Backtest + calibration | ~10 min | After Phase 1+2+3 |
| 5 | Closing odds script | ~1 hr impl | Anytime (independent) |
| 6 | Dashboard + verification | ~5 min | After all above |

### Parallelism
- Phase 1 (scores) is running now
- Phase 3 (Elo retrain) can start as soon as Phase 1 finishes (doesn't need odds)
- Phase 5 (closing odds script) is independent — can be built anytime
- Phase 2 (odds backfill) is the long pole: start tonight, runs overnight
- Phase 4 (backtest) needs both scores AND odds

---

## Outstanding Items (not in recovery scope)

- [ ] K=32 tournament fix (before Mar 15-16 bracket)
- [ ] Add `beautifulsoup4` to requirements.txt
- [ ] Fix health_check to warn-not-abort on empty DB
- [ ] Fix PowerShell `Invoke-PipelineStep` param binding (profile conflict)
- [ ] Backfill 2026 odds (0% coverage currently)
