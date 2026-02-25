## Active Task
Session 21 COMPLETE — KenPom nightly scraper + pipeline merge.

## Last Completed Step
All work done. 6 commits merged to main (ad7b8e1), pushed to origin.

## Completed This Session
- [x] Technical discussion: KenPom nightly scraping requirements
- [x] Implementation plan written (docs/plans/2026-02-25-kenpom-nightly-scraper.md)
- [x] Task 1: Added kenpompy>=0.5.0 to requirements.txt, installed
- [x] Task 2: Added kenpom_ratings table to SQLite schema (tracking/database.py)
- [x] Task 3: Added store_snapshot_to_db() function + --store-db CLI flag
- [x] Task 4: Added scrape_kenpom step to nightly-refresh.ps1
- [x] Task 5: Created daily-pipeline.ps1 merging nightly + morning (10 steps)
- [x] Task 6: Updated setup-scheduled-tasks.ps1 for single 7 AM job
- [x] Task 7: End-to-end verification (72/72 tests pass, 0 regressions)
- [x] Manual: Added KENPOM_EMAIL/KENPOM_PASSWORD to .env
- [x] Manual: Merged feat/kenpom-nightly-scraper to main, pushed
- [x] Manual: Unregistered old tasks, registered SportsBetting-Daily at 07:00

## Verification Results
- 38/38 KenPom tests pass (9 new + 29 existing)
- 34/34 core pipeline tests pass (zero regressions)
- Ruff check clean on all modified files
- All 15 pre-commit hooks pass on every commit
- Task Scheduler: SportsBetting-Daily Ready, next run 07:00

## Files Modified This Session
- `requirements.txt` — added kenpompy>=0.5.0
- `tracking/database.py` — added kenpom_ratings table creation
- `pipelines/kenpom_fetcher.py` — added store_snapshot_to_db(), _to_py()
- `scripts/fetch_kenpom_data.py` — added --store-db flag
- `scripts/daily-pipeline.ps1` — NEW: merged 10-step pipeline
- `scripts/nightly-refresh.ps1` — added KenPom step + deprecation warning
- `scripts/morning-betting.ps1` — added deprecation warning
- `scripts/setup-scheduled-tasks.ps1` — single SportsBetting-Daily at 07:00
- `tests/test_kenpom_scraper_db.py` — NEW: 9 tests for DB storage
- `docs/plans/2026-02-25-kenpom-nightly-scraper.md` — implementation plan
- `.env` — added KENPOM_EMAIL, KENPOM_PASSWORD

## Still Outstanding (carry forward)
- [ ] Monitor first 7 AM pipeline run (check logs/pipeline-daily-*.log)
- [ ] Verify KenPom data accumulating: SELECT snapshot_date, COUNT(*) FROM kenpom_ratings GROUP BY snapshot_date
- [ ] Verify CLV collection in production (settle bets, check odds_closing/clv populated)
- [ ] Fix test_logger failures (8 regressions — sqlite3 schema mismatch)
- [ ] Test coverage gaps (41.4% overall)
- [ ] Monitor injury check thresholds (currently 10pp warn, 15pp block)
- [ ] March Madness prep (bracket data Mar 15-16)
