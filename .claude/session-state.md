## Active Task
Session 15 -- Pipeline bug fixes (nightly self-deadlock, daily_run sqlite3.Row, predictions index alignment)

## Last Completed Step
Fixed 3 bugs, ran nightly pipeline manually, verified predictions dry-run clean.

## Completed This Session (Session 15, 2026-02-22)
- [x] Diagnosed nightly pipeline failure (Feb 21 23:00): health_check self-deadlock
  - Root cause: pipeline acquired lock BEFORE health_check, health_check's stale_lock detector saw its own lock → critical → abort
  - Fix: moved lock acquisition to AFTER health_check passes in nightly-refresh.ps1
  - Also handles -SkipHealthCheck flag (acquires lock upfront when no health check)
- [x] Ran nightly pipeline manually with pwsh -- all 6 steps OK (scores, Elo, Barttorvik, dashboard, Vercel deploy)
- [x] Fixed daily_run.py sqlite3.Row .get() bug (AttributeError on bet settlement)
- [x] Fixed daily_predictions.py pandas IndexingError (rec_side column check)
- [x] Verified dry-run: 2 games today, no bets above threshold
- [x] Settled 3 paper bets from Feb 21

## Previous Session (Session 14, 2026-02-22)
- Password gate added to dashboard, deployed to Vercel (commit 2df8d11)

## Previous Session (Session 13, 2026-02-21)
- Dashboard consolidation: merged elo_dashboard + ncaab_dashboard into unified 9-tab dashboard

## Key Context
- **Nightly pipeline**: Self-deadlock FIXED. Uses pwsh.exe (PS 5.1 has separate param binding bug -- not relevant to Task Scheduler which uses pwsh)
- **Task Scheduler**: 3 jobs registered, all Ready state. Nightly at 23:00, Morning at 10:00, Settlement at 23:30
- **Morning task**: Has never fired (LastResult=267011 "no prior execution"). NextRun Feb 22 10:00.
- **Dashboard**: deployed, data fresh as of Feb 22 06:12
- **Paper betting**: 3 bets settled from Feb 21, pipeline now clean

## Still Outstanding (from prior sessions)
- [ ] Fix test_logger failures (8 regressions -- sqlite3 schema mismatch)
- [ ] Test coverage gaps (41.4% overall; betting 21.2%, tracking 36.1%)
- [ ] Backfill 2026 odds (0% coverage currently)
- [ ] March Madness prep (bracket data not until Mar 15-16)
- [ ] Cleanup: delete scripts/kenpom_barttorvik_redundancy.py, scripts/kenpom_staleness_analysis.py

## Files Modified This Session
- scripts/nightly-refresh.ps1 (moved lock acquisition after health_check)
- scripts/daily_run.py (sqlite3.Row .get() → bracket access)
- scripts/daily_predictions.py (rec_side column existence check)
