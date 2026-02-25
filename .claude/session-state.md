## Active Task
CLV Collection System — subagent-driven implementation from plan

## Last Completed Step
Design phase complete. Plan written and saved. No implementation started.

## Plan Location
`docs/plans/2026-02-24-clv-collection.md`

## Execution Method
**Subagent-driven development** — dispatch fresh subagent per task, review between tasks.
Use `superpowers:executing-plans` skill to implement task-by-task.

## Remaining (6 tasks)
- [ ] Task 1: Add `snapshot_type` column to `odds_snapshots` (`tracking/database.py`)
- [ ] Task 2: Create `scripts/fetch_opening_odds.py` + tests
- [ ] Task 3: Add opening odds step to `nightly-refresh.ps1`
- [ ] Task 4: Add CLV calculation to `settle_yesterdays_bets()` in `scripts/daily_run.py` + tests
- [ ] Task 5: Update settlement output display in `daily_run.py:main()`
- [ ] Task 6: Clean up inline `american_to_decimal` import

## Key Context

### Architecture (DO NOT re-derive)
- **No pre-game fetch needed.** ESPN Core API returns actual closing odds for completed games via `close` fields.
- **Two pipeline modifications, zero new scheduled tasks:**
  1. Nightly (11pm): new step `fetch_opening_odds.py` after `scrape_barttorvik` — fetches tomorrow's opening odds via ESPN Core API
  2. Morning (10am): `settle_yesterdays_bets()` gains Pass 2 — fetches ESPN Core API `close` fields, stores closing snapshot, calculates CLV
- **CLV formula:** `(prob_closing - prob_placed) / prob_placed` using `calculate_clv()` from `betting/odds_converter.py:116`
- **Closing odds lookup:** JOIN from `odds_snapshots` by `game_id + snapshot_type='closing'` — NOT denormalized onto `bets` table (decision: option B)

### ESPN Core API Verified Data
Tested on completed games (Feb 23). Returns all three markets:
- ML: open home=+105, close home=+124 (line moved)
- Spread: open -2.5 (-115), close -2.5 (-112/-108)
- Total: open 136.5 (-110/-110), close 138.5 (-108/-112)
- Provider: DraftKings (id=100) for 2026 season
- Coverage: ~90%+ of NCAAB games

### Schema Change
- Add `snapshot_type TEXT DEFAULT 'current'` to `odds_snapshots`
- Values: `'opening'`, `'closing'`, `'current'`
- Keep `is_closing` boolean for backward compatibility
- Backfill 81 existing rows as `'current'`

### Key Files to Modify
| File | Change |
|------|--------|
| `tracking/database.py:160-179` | ALTER TABLE migration + CREATE TABLE update |
| `scripts/fetch_opening_odds.py` | NEW — opening odds fetcher |
| `tests/test_fetch_opening_odds.py` | NEW — 6 tests |
| `scripts/nightly-refresh.ps1:79-97` | Add step to `$steps` hashtable |
| `scripts/daily_run.py:52-153` | Rewrite `settle_yesterdays_bets()` with CLV Pass 2 |
| `tests/test_daily_run.py:365+` | Add 3 CLV tests to `TestSettlement` |

### Existing Functions Used (DO NOT rewrite)
- `calculate_clv(odds_placed, odds_closing)` — `betting/odds_converter.py:116`
- `american_to_implied_prob(american)` — `betting/odds_converter.py:33`
- `ESPNCoreOddsFetcher.fetch_game_odds(event_id)` — `pipelines/espn_core_odds_provider.py:472`
- `OddsSnapshot` dataclass — `pipelines/espn_core_odds_provider.py:61`
- `fetch_espn_scoreboard(target_date)` — `scripts/daily_predictions.py:66`

## Files Modified This Session
- `docs/plans/2026-02-24-clv-collection.md` (created — implementation plan)

## Still Outstanding (non-CLV, carry forward)
- [ ] Fix test_logger failures (8 regressions — sqlite3 schema mismatch)
- [ ] Test coverage gaps (41.4% overall)
- [ ] Monitor injury check thresholds (currently 10pp warn, 15pp block)
- [ ] March Madness prep (bracket data Mar 15-16)
