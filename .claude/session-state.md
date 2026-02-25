## Active Task
Session 23 COMPLETE — KellySizer Platt calibration bug fix + explanation docs.

## Last Completed Step
All work done. Bug fixed, docs created, analysis run. NOT YET COMMITTED.

## Completed This Session
- [x] Diagnosed KellySizer calibration bug: edge-based Platt gave P(win)=18.7% for -410 favorites
- [x] Root cause: `calibrated_win_prob(edge)` ignores base probability; edge alone doesn't determine win rate
- [x] Fixed: changed calibration feature from `edge` to `model_prob` (standard Platt scaling)
- [x] Updated `betting/odds_converter.py`: KellySizer.calibrate(), calibrated_win_prob(), size_bet(), build_calibration_data()
- [x] Updated `scripts/daily_run.py`: variable rename edges -> model_probs
- [x] Updated `scripts/backtest_ncaab_elo.py`: variable rename edges -> model_probs
- [x] Updated `tests/test_kelly_sizer.py`: fixtures use model_prob, added test_stakes_vary_with_edge_size (16 tests)
- [x] All 103 tests pass (16 kelly + 29 daily_run + 5 fetch_odds + 53 elo), zero regressions
- [x] Ruff lint + format clean on all 4 modified files
- [x] Created `docs/explanation/platt-calibration.md` (520 lines, Diataxis explanation)
- [x] Created `docs/explanation/platt-calibration-explorer.html` (1209 lines, 4-tab interactive visualization)
- [x] Ran backtest distribution analysis (3,710 bets, 6 seasons)

## Verification Results
- 16/16 test_kelly_sizer pass
- 29/29 test_daily_run pass
- 5/5 test_fetch_opening_odds pass
- 53/53 test_elo pass
- Ruff: all checks passed, 4 files already formatted

## Key Context
### The Bug
- Old: `calibrated_win_prob(edge)` mapped edge -> P(win) via logistic regression
- Edge alone ignores base win rate; 31.4% overall win rate, mostly longshots
- A -410 favorite got cal_prob=0.187, Kelly returned $0 for EVERY bet
- All 8 production bets used flat $150 from pre-Kelly fallback

### The Fix
- New: `calibrated_win_prob(model_prob)` — standard Platt scaling preserving base rate
- Platt coefficients: coef=6.4558, intercept=-3.8831 (from 3,710 backtest bets)
- Stakes now range $0-$250 proportional to calibrated edge
- Tomorrow's 7 AM pipeline will be FIRST to produce dynamically-sized bets

### Backtest Distribution (calibrated Kelly on 6 seasons)
- 3,710 total bets, 97% on underdogs, 31.4% overall win rate
- Kelly filters out 38% of bets (1,409 marginal bets with -0.037 avg cal_edge, only +1.2% ROI)
- 2,301 surviving bets: mean stake $163, median $199, 45.5% at $250 cap
- Kelly ROI +156.9% vs flat +93.2% (+64pp improvement, every season better)
- Total Kelly P&L: +$587K on $374K staked

## Files Modified This Session
- `betting/odds_converter.py` — KellySizer calibration feature: edge -> model_prob
- `scripts/daily_run.py` — variable rename edges -> model_probs
- `scripts/backtest_ncaab_elo.py` — variable rename edges -> model_probs
- `tests/test_kelly_sizer.py` — fixtures updated, new test added (16 total)
- `docs/explanation/platt-calibration.md` — NEW: Diataxis explanation (520 lines)
- `docs/explanation/platt-calibration-explorer.html` — NEW: interactive visualization (1209 lines)

## Still Outstanding (carry forward)
- [ ] Commit and push session 23 changes (awaiting user approval)
- [ ] Monitor tomorrow's 7 AM pipeline for varied stake sizes (should NOT be flat $150)
- [ ] Fix test_logger failures (8 regressions — sqlite3 schema mismatch)
- [ ] Test coverage gaps (41.4% overall)
- [ ] Monitor injury check thresholds (currently 10pp warn, 15pp block)
- [ ] March Madness prep (bracket data Mar 15-16)
