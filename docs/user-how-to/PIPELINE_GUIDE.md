# Daily Pipeline Guide

Last updated: 2026-03-07

---

## Schedule Overview

The project runs one automated pipeline daily via Windows Task Scheduler.

| Pipeline | Script | Schedule | Trigger |
|----------|--------|----------|---------|
| Daily Pipeline | `scripts/daily-pipeline.ps1` | **7:00 AM ET, daily** | Windows Task Scheduler |

There are no other scheduled tasks. Everything runs in sequence within this single pipeline invocation.

---

## How Task Scheduler Works

Windows Task Scheduler is the built-in Windows service that runs programs on a schedule.
Here is how it is configured for this project:

**Task name:** `Sports Betting Daily Pipeline` (or similar -- check Task Scheduler Library)

**What happens at 7:00 AM ET:**

1. Task Scheduler launches PowerShell with the pipeline script
2. The pipeline runs each step sequentially using `venv\Scripts\python.exe`
3. Each step has a timeout -- if a script hangs, it gets killed and the pipeline moves on
4. A checkpoint file (`logs/pipeline-state.json`) saves progress after each step
5. If the pipeline crashes mid-run and is triggered again the same day,
   it **resumes from the last incomplete step** (no re-running finished work)
6. A lock file (`logs/pipeline.lock`) prevents two pipeline instances from running simultaneously
7. On completion, a Slack notification is sent (if `SLACK_WEBHOOK_URL` is configured in `.env`)

**The Task Scheduler invocation command:**

```powershell
powershell.exe -ExecutionPolicy Bypass -File C:\Users\msenf\sports-betting\scripts\daily-pipeline.ps1
```

**Running manually from Claude Code or Git Bash (MUST use `-NoProfile`):**

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/daily-pipeline.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/daily-pipeline.ps1 -DryRun
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/daily-pipeline.ps1 -SettleOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/daily-pipeline.ps1 -Force
```

**Why `-NoProfile`?** The user's PowerShell profile loads modules that interfere
with stdout capture. Task Scheduler does not load profiles by default, so it
works as-is. But any manual invocation from a shell must include `-NoProfile`.

**Pipeline-level flags:**

| Flag | Effect |
|------|--------|
| `-DryRun` | Preview all steps without executing any Python scripts |
| `-Force` | Ignore checkpoint -- run all steps from scratch |
| `-SettleOnly` | Only run health_check + settle_bets, skip everything else |
| `-SkipSettle` | Skip the settlement step |
| `-SkipPredict` | Skip the prediction step |
| `-SkipHealthCheck` | Skip the health check (acquires lock immediately) |
| `-MaxRetries N` | Retry failed steps up to N times (default: 1, no retry) |

**Critical vs. non-critical steps:** Steps marked `critical = $true` abort
the entire pipeline if they fail. Non-critical steps log a warning and the
pipeline continues. See the step reference below for which is which.

**Logs:** Written to `logs/pipeline-daily-YYYY-MM-DD.log`. Each step's
stdout/stderr (first 500 chars) is captured in the log.

---

## Pipeline Steps (Chronological Order)

The pipeline runs these 12 steps in order. Total runtime is typically
**8-20 minutes** depending on game slate size and API response times.

---

### Step 1: backup_databases

**Script:** `scripts/backup_db.py`
**Critical:** No
**Timeout:** 60 seconds

- Copies `data/ncaab_betting.db` and `data/mlb_data.db` to `C:\Users\msenf\sports-betting-backups\`
- Uses GFS (Grandfather-Father-Son) rotation: keeps 7 daily + 4 weekly backups
- Runs first so that if anything downstream corrupts the DB, you have a restore point

**Key parameters:**

- `--list` -- show existing backups
- `--verify` -- verify latest backup integrity (table counts, checksums)

**Runtime:** ~5-10 seconds (just file copies)

**Manual usage:**

```bash
venv/Scripts/python.exe scripts/backup_db.py
venv/Scripts/python.exe scripts/backup_db.py --list
venv/Scripts/python.exe scripts/backup_db.py --verify
```

---

### Step 2: health_check

**Script:** `scripts/pipeline_health_check.py --json`
**Critical:** Yes -- pipeline aborts if this fails
**Timeout:** 30 seconds

- Pre-flight validation that all prerequisites are met
- Checks performed:
  - `venv/Scripts/python.exe` exists and runs
  - `data/ncaab_betting.db` exists and has recent data (within 48 hours)
  - Disk space > 500 MB
  - No stale pipeline lock file (> 60 minutes old)
  - Required Python packages importable
- Acquires the pipeline lock after passing (prevents concurrent runs)

**Exit codes:**

- `0` = healthy
- `1` = warnings (non-critical, pipeline proceeds)
- `2` = critical (pipeline aborts)

**Runtime:** ~2-5 seconds

---

### Step 3: fetch_scores

**Script:** `scripts/fetch_season_data.py --season 2026 --incremental --no-odds`
**Critical:** Yes -- pipeline aborts if this fails
**Timeout:** 300 seconds (5 minutes)

- Fetches latest game scores from the ESPN Scoreboard API
- `--incremental` means it only fetches games not already in the database
- `--no-odds` skips odds fetching (handled by dedicated steps later)
- Writes game results to `data/ncaab_betting.db` and raw data to `data/raw/ncaab/ncaab_games_2026.parquet`

**Key parameters:**

- `--season YYYY` -- which season to fetch
- `--incremental` -- only new games (skip existing)
- `--no-odds` -- scores only
- `--force` -- re-fetch all games (overwrite)
- `--nightly` -- shorthand for `--incremental --season <current>`

**Runtime:**

- Light day (0-5 new games): ~10-30 seconds
- Heavy day (15+ games, e.g., full Saturday slate): ~1-3 minutes
- Full season fetch (non-incremental): ~5-10 minutes

---

### Step 4: train_elo

**Script:** `scripts/train_ncaab_elo.py --end 2026`
**Critical:** Yes -- pipeline aborts if this fails
**Timeout:** 180 seconds (3 minutes)

- Retrains the Elo rating model using all available game data from 2020 through 2026
- Loads raw parquet files, processes games chronologically (prevents look-ahead bias)
- Applies between-season regression (ratings regress toward mean each new season)
- Outputs:
  - `data/processed/ncaab_elo_ratings_current.csv` (human-readable current ratings)
  - `data/processed/ncaab_elo_model.pkl` (pickled model state for predictions)
  - `team_ratings` table in `ncaab_betting.db`

**Key parameters:**

- `--start YYYY` / `--end YYYY` -- season range (default: 2020 to current)
- `--validate` -- print top 25 teams and run sanity checks after training

**Runtime:**

- Typical: ~30-90 seconds (processing ~30,000 games across 6 seasons)
- First run after data recovery: ~2 minutes

---

### Step 5: scrape_barttorvik

**Script:** `scripts/fetch_barttorvik_data.py --seasons 2026 --scrape`
**Critical:** No
**Timeout:** 120 seconds (2 minutes)

- Scrapes today's Barttorvik T-Rank efficiency ratings for all 365 D1 teams
- `--scrape` flag triggers live scraping from barttorvik.com (vs. API for historical)
- Cached as parquet files in `data/external/barttorvik/`
- Barttorvik provides four-factor metrics: AdjOE, AdjDE, AdjTempo, and composite rating
- These ratings feed into the Elo+Barttorvik ensemble used for predictions

**Key parameters:**

- `--seasons YYYY [YYYY ...]` -- which seasons
- `--scrape` -- live scrape (required for current season, API only has completed seasons)
- `--force` -- re-download even if today's snapshot already cached

**Runtime:** ~15-45 seconds (single page scrape + parse)

**Requires:** `beautifulsoup4` installed in venv

---

### Step 6: scrape_kenpom

**Script:** `scripts/fetch_kenpom_data.py --daily-only --store-db`
**Critical:** No
**Timeout:** 120 seconds (2 minutes)

- Fetches today's KenPom efficiency ratings (AdjEM, AdjO, AdjD, AdjTempo, rank)
- `--daily-only` fetches only the current season
- `--store-db` writes ratings to the `kenpom_ratings` table in `ncaab_betting.db`
- Cached as parquet in `data/external/kenpom/`

**Key parameters:**

- `--seasons YYYY [YYYY ...]` -- specific seasons
- `--daily-only` -- current season only
- `--store-db` -- persist to SQLite (not just parquet cache)
- `--force` -- ignore cache

**Runtime:** ~10-30 seconds

**Requires:** KenPom subscription ($25/year). Credentials in `.env`:

- `KENPOM_EMAIL`
- `KENPOM_PASSWORD`

---

### Step 7: settle_bets

**Script:** `scripts/daily_run.py --settle-only`
**Critical:** No
**Timeout:** 120 seconds (2 minutes)

- Settles yesterday's paper bets by checking ESPN final scores
- For each pending bet:
  - Looks up the game result from ESPN Scoreboard API
  - Determines win/loss based on bet type (ML, spread, total)
  - Calculates profit/loss based on odds and stake
  - Fetches closing odds from ESPN Core API
  - Calculates CLV (Closing Line Value) for each bet
- Updates `bets` table: `is_settled`, `result`, `profit_loss`, `odds_closing`, `clv`

**Key parameters:**

- `--settle-only` -- only settle, skip predictions
- `--settle-date YYYY-MM-DD` -- settle a specific date (default: yesterday)

**Runtime:**

- 0 pending bets: ~5 seconds (quick DB check, no API calls)
- 1-5 bets: ~15-30 seconds (includes closing odds fetch per game)
- 10+ bets: ~1-2 minutes

---

### Step 8: collect_closing_odds

**Script:** `scripts/collect_closing_odds.py --hours 48`
**Critical:** No
**Timeout:** 300 seconds (5 minutes)

- Fetches closing odds for ALL completed games in the last 48 hours (not just games with bets)
- Queries multiple providers for cross-book closing lines:
  - **ESPN Core API** (free, primary) -- returns DraftKings closing lines for completed games
  - **The Odds API** (free tier, 500 credits/month) -- returns lines from DraftKings, FanDuel, BetMGM, Caesars, ESPN BET
- Stores all provider snapshots in `odds_snapshots` table with `is_closing = 1`
- Updates `bets.odds_closing` and `bets.clv` for any bets matched to collected games
- Skips games that already have closing odds stored (idempotent)

**Key parameters:**

- `--hours N` -- lookback window (default: 48)
- `--date YYYY-MM-DD` -- collect for a specific date only
- `--espn-only` -- skip The Odds API (save credits)
- `--dry-run` -- show what would be collected without DB writes

**Runtime:**

- Light day (5-8 games): ~30-60 seconds
- Heavy day (15-20 games): ~2-4 minutes
- Most time spent on ESPN Core API calls (rate limited to 2 req/sec)

**Environment variable:** `ODDS_API_KEY` in `.env` (optional -- without it, only ESPN Core is used)

---

### Step 9: predictions

**Script:** `scripts/daily_run.py --skip-settle`
**Critical:** No
**Timeout:** 600 seconds (10 minutes)

- Generates predictions for today's (and lookahead window) games
- Full prediction pipeline:
  1. Fetches today's game slate from ESPN Scoreboard API
  2. Loads trained Elo model + Barttorvik + KenPom ratings
  3. Generates win probabilities for each game
  4. Compares model probabilities to available odds
  5. Identifies +EV bets (model edge > threshold)
  6. Sizes bets using Dynamic Kelly with Platt calibration
  7. Records paper bets to `bets` table in `ncaab_betting.db`
  8. Records predictions to `predictions` table
- `--skip-settle` prevents re-settling (already done in step 7)

**Key parameters:**

- `--skip-settle` -- skip settlement (already handled)
- `--dry-run` -- preview picks without recording to DB
- `--date YYYY-MM-DD` -- predict for specific date
- `--report-only` -- generate weekly performance report

**Runtime:**

- No games today: ~5-10 seconds
- Light slate (5-8 games): ~30-60 seconds
- Heavy slate (15+ games with lookahead): ~2-8 minutes
- Lookahead scanning (7+ days): up to 10 minutes

---

### Step 10: fetch_opening_odds

**Script:** `scripts/fetch_opening_odds.py`
**Critical:** No
**Timeout:** 300 seconds (5 minutes)

- Fetches current odds (which serve as "opening" lines at this time of day) for upcoming games
- Scans the full lookahead window (typically 7+ days of scheduled games)
- Data source: ESPN Scoreboard API to discover games, then ESPN Core API for odds
- Stores odds in `odds_snapshots` table with `snapshot_type = 'current'`
- These opening odds are later compared against closing odds to calculate CLV

**Key parameters:**

- `--date YYYY-MM-DD` -- start date (default: today)
- `--lookahead-days N` -- how many days ahead to scan
- `--dry-run` -- preview without DB writes

**Runtime:**

- Light week (20-30 games in window): ~1-2 minutes
- Heavy week (60+ games, tournament time): ~3-5 minutes

---

### Step 11: generate_dashboard

**Script:** `scripts/generate_dashboard_data.py`
**Critical:** No
**Timeout:** 60 seconds

- Generates a merged JSON data bundle for the NCAAB dashboard
- Combines:
  - Current Elo ratings (from trained model)
  - Latest Barttorvik T-Rank snapshot
  - Season game stats (W-L record, PPG, PAPG, margin)
- Output: `data/processed/ncaab_dashboard_bundle.json`

**Key parameters:**

- `--season YYYY` -- target season (default: 2026)

**Runtime:** ~5-15 seconds (reads local data, no API calls)

---

### Step 12: deploy_dashboard

**Script:** `scripts/deploy_dashboard.py`
**Critical:** No
**Timeout:** 90 seconds

- Thin Python wrapper that invokes `scripts/deploy-dashboard.ps1`
- Deploys the dashboard HTML + data bundle to Vercel (or configured host)
- Returns the PowerShell script's exit code

**Runtime:** ~10-30 seconds (network dependent)

---

## Total Pipeline Runtime Estimates

| Scenario | Estimated Runtime |
|----------|-------------------|
| **No games (off-day)** | 3-5 minutes |
| **Light day (5-8 games)** | 5-10 minutes |
| **Normal day (10-15 games)** | 8-15 minutes |
| **Heavy day (20+ games, Saturday/tournament)** | 12-20 minutes |

The pipeline is designed so that non-critical step failures do not block
subsequent steps. A typical run with 1-2 non-critical failures still
completes the remaining steps and reports `partial_failure`.

---

## Supporting Infrastructure

### pipeline-common.ps1

Shared PowerShell functions used by the pipeline orchestrator:

| Function | Purpose |
|----------|---------|
| `Import-DotEnv` | Loads `.env` file variables into the process environment |
| `Write-Log` | Timestamped logging to console + log file |
| `Initialize-PipelineLog` | Creates daily log file in `logs/` |
| `Load-Checkpoint` | Loads checkpoint JSON for resume-on-failure |
| `Save-Checkpoint` | Atomically saves pipeline state after each step |
| `Send-PipelineNotification` | Sends Slack webhook notification (if configured) |
| `Invoke-PipelineStep` | Runs a Python script with timeout, retry, and output capture |
| `Acquire-PipelineLock` | Prevents concurrent pipeline runs (stale lock auto-cleared after 60 min) |
| `Release-PipelineLock` | Releases the lock file |

### Key Files

| File | Purpose |
|------|---------|
| `logs/pipeline-daily-YYYY-MM-DD.log` | Daily pipeline log |
| `logs/pipeline-state.json` | Checkpoint state for resume |
| `logs/pipeline.lock` | Concurrency lock |
| `.env` | API keys and credentials |
| `data/ncaab_betting.db` | Primary NCAAB database |
| `data/mlb_data.db` | MLB database |

### Environment Variables (in `.env`)

| Variable | Required By | Purpose |
|----------|-------------|---------|
| `KENPOM_EMAIL` | fetch_kenpom_data.py | KenPom login |
| `KENPOM_PASSWORD` | fetch_kenpom_data.py | KenPom login |
| `CBBDATA_API_KEY` | fetch_barttorvik_data.py | CBBdata API (historical Barttorvik) |
| `ODDS_API_KEY` | collect_closing_odds.py | The Odds API free tier (optional) |
| `SLACK_WEBHOOK_URL` | pipeline-common.ps1 | Slack notifications (optional) |

---

## Troubleshooting

**Pipeline did not run this morning:**

1. Open Task Scheduler, find the task, check "Last Run Result"
2. Check `logs/pipeline-daily-YYYY-MM-DD.log` for errors
3. Run manually: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/daily-pipeline.ps1`

**Pipeline is stuck / lock file stale:**

1. Check `logs/pipeline.lock` -- if older than 60 minutes, the pipeline auto-clears it
2. To force-clear: delete `logs/pipeline.lock` manually
3. Re-run with `-Force` to ignore checkpoint

**A non-critical step failed:**

- Pipeline continues past non-critical failures
- Check the log for the specific error
- Re-run just that step manually (see individual script commands above)

**A critical step failed (health_check, fetch_scores, train_elo):**

- Pipeline aborts and sends a Slack notification (if configured)
- Fix the root cause, then re-run: `daily-pipeline.ps1 -Force`
- Or skip the health check: `daily-pipeline.ps1 -SkipHealthCheck`

**Checkpoint is stale / want a fresh run:**

- Use `-Force` flag to ignore checkpoints and run everything from scratch
