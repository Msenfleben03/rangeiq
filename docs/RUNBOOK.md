# Operations Runbook

**Last Updated:** 2026-02-12
**Review Cycle:** Monthly
**Next Review:** 2026-03-12

## Overview

Standard operating procedures for the NCAAB paper betting pipeline.
Follow these checklists for consistent performance tracking and health.

---

## Daily Operations

### Morning Routine (Before First Games)

**Time:** 2-3 hours before first game of interest

```markdown
## Daily Checklist - [DATE]

### 1. Generate Predictions
- [ ] Run predictions: `python scripts/daily_predictions.py --date today`
- [ ] Review output for reasonableness (no >15 point edges)
- [ ] Check odds API credit budget in output footer

### 2. Record Bets
- [ ] Record selected bets: `python scripts/record_paper_bets.py --date today`
  - Interactive mode: enter each bet at prompt
  - OR CSV import: `python scripts/record_paper_bets.py --import-csv bets.csv`
- [ ] Verify exposure limits not exceeded (max 10% daily)
- [ ] Confirm all bets logged (check total in output)
```

### Evening Routine (After Games Complete)

**Time:** After all tracked games are final

```markdown
## Evening Reconciliation - [DATE]

### 1. Settle Bets
- [ ] Run settlement: `python scripts/daily_run.py --settle-only` (auto-calculates CLV)
- [ ] Review P/L and CLV for each settled bet (CLV now populated automatically)
- [ ] Note any games not yet final (skipped)

### 2. Daily Report
- [ ] Run report: `python scripts/generate_report.py --daily --odds-health`
- [ ] Check for health alerts (CRITICAL / WARNING)
- [ ] Record daily P/L and CLV in notes

### Daily Log Entry
| Metric | Value |
|--------|-------|
| Date | |
| Bets Placed | |
| Bets Settled | |
| Record | W-L-P |
| Daily P/L | $ |
| Average CLV | % |
| Notes | |
```

### Quick Daily Commands

```bash
# Morning
python scripts/daily_predictions.py --date today
python scripts/record_paper_bets.py --date today

# Evening
python scripts/settle_paper_bets.py --date today
python scripts/generate_report.py --daily --odds-health
```

---

## Weekly Operations

### Weekly Review (Sunday Evening)

```markdown
## Weekly Review - Week of [DATE]

### 1. Performance Summary
- [ ] Run weekly report: `python scripts/generate_report.py --weekly --clv`
- [ ] Review: total bets, record, P/L, ROI, CLV, Sharpe

### 2. Model Health
- [ ] Run health check: `python scripts/generate_report.py --health`
- [ ] Check for alerts:
  - CRITICAL: CLV < 0 for 7+ days -> review model
  - WARNING: 5+ consecutive losses -> reduce sizing 50%
  - WARNING: Win rate < 48% over 100 bets -> review calibration

### 3. Odds System Health
- [ ] Run odds check: `python scripts/generate_report.py --odds-health`
- [ ] Check provider success rates
- [ ] Review API credit usage (500/month budget)

### 4. Risk Check
- [ ] Current bankroll: $___
- [ ] Weekly drawdown: ____%
- [ ] Check against 15% weekly stop-loss threshold
- [ ] If >10% down: reduce next week sizing by 50%

### 5. Full Dashboard (all reports)
- [ ] Run: `python scripts/generate_report.py --all`
```

---

## Monthly Operations

### Monthly Review (Last Day of Month)

```markdown
## Monthly Review - [MONTH YEAR]

### 1. Performance Summary
| Metric | Value | vs Target |
|--------|-------|-----------|
| Total Bets | | |
| Record | W-L-P | |
| Net P&L | $ | |
| ROI | % | Target: >2% |
| Average CLV | % | Target: >1% |
| Sharpe Ratio | | Target: >0.5 |

### 2. Bankroll Status
| Account | Start | End | Change |
|---------|-------|-----|--------|
| DraftKings | $ | $ | $ |
| FanDuel | $ | $ | $ |
| BetMGM | $ | $ | $ |
| Caesars | $ | $ | $ |
| ESPN BET | $ | $ | $ |
| **Total** | $ | $ | $ |

### 3. Model Revalidation
- [ ] Re-run Gatekeeper: `python scripts/run_gatekeeper_validation.py`
- [ ] Verify model still passes all blocking checks:
  - Sample size >= 200, Sharpe >= 0.5, ROI <= 15%, CLV >= 1.5%
- [ ] If QUARANTINE: investigate and retrain

### 4. Strategic Review
- [ ] Which bet types outperformed?
- [ ] Any sportsbooks showing limits?
- [ ] Edge decay in any markets?

### 5. Risk Assessment
- [ ] Maximum drawdown this month: %
- [ ] Longest losing streak: __ bets
- [ ] Check against 25% monthly stop-loss
- [ ] If >20% down: pause and conduct full review

### 6. System Maintenance
- [ ] Database backup: `cp data/betting.db data/backups/betting_$(date +%Y%m%d).db`
- [ ] Check API credit reset (resets on month boundary)
- [ ] Review `data/odds_api_usage.json` credits
- [ ] Run `python scripts/verify_schema.py` to check DB health

### 7. Tax Tracking (US)
- [ ] Export monthly P/L for records
- [ ] Note any W-2G forms (wins >$600 at 300:1+)
- [ ] Update running annual total
```

---

## Incident Response

### Data Pipeline Failure

```markdown
## Incident: Data Pipeline Failure

### Immediate Actions
1. Check sportsipy connectivity: `python -c "from pipelines.ncaab_data_fetcher import NCAABDataFetcher; print('OK')"`
2. Check odds API status: `python -c "from pipelines.odds_providers import TheOddsAPIProvider; p = TheOddsAPIProvider(); print(p.is_available)"`
3. If API down: use `--mode manual` with CSV odds file
4. If sportsipy down: use cached parquet in `data/raw/ncaab/`

### Resolution Steps
1. Identify root cause (API down, rate limit, code bug)
2. If rate limit: increase `--delay` parameter
3. If API down: switch to ESPN provider (`--mode espn`)
4. If code bug: fix, test, deploy

### Post-Incident
- [ ] Document incident in logs
- [ ] Update runbook if new failure mode
```

### Model Performance Degradation

```markdown
## Incident: Model CLV Dropping

### Detection (via generate_report.py --health)
- CRITICAL: CLV < 0 for 7+ consecutive days
- WARNING: 5+ consecutive losses

### Immediate Actions
1. Reduce bet sizing by 50%
2. Review `python scripts/generate_report.py --clv` for trends
3. Check data quality: `python scripts/verify_schema.py`

### Investigation
1. Market becoming more efficient?
2. Data source issues (stale/missing data)?
3. Regime change (rule changes, conference realignment)?
4. Overfitting? Re-run Gatekeeper validation

### Resolution
1. If data issue: fix pipeline, `python scripts/fetch_historical_data.py --force`
2. If efficiency: tighten edge thresholds (`--min-edge 0.03`)
3. If overfitting: retrain with `python scripts/train_ncaab_elo.py`
4. Re-validate: `python scripts/run_gatekeeper_validation.py`

### Recovery Criteria
- Return to >0.5% CLV over 50+ bets
- Model passes Gatekeeper with PASS decision
- Then gradually restore normal sizing
```

### Sportsbook Account Limited

```markdown
## Incident: Account Limited/Restricted

### Immediate Actions
1. Document the limitation (max bet amounts, banned markets)
2. Screenshot any communications
3. Do NOT contact support (usually makes it worse)

### Adaptation
1. Reallocate bankroll to remaining books
2. If prop limits: focus on main markets
3. If main market limits: use for line shopping only
4. Consider adding new sportsbook accounts
```

---

## Emergency Procedures

### 25% Monthly Loss Trigger

```markdown
## STOP: 25% Monthly Loss Reached

### Immediate Actions
1. **STOP all betting immediately**
2. Do NOT place any more bets until review complete
3. Do NOT try to "win it back"

### Required Review (Before Resuming)
1. [ ] Wait minimum 48 hours (cooling off)
2. [ ] Calculate exact loss amount and timeline
3. [ ] Review every losing bet for patterns
4. [ ] Run: `python scripts/generate_report.py --all`
5. [ ] Re-validate model: `python scripts/run_gatekeeper_validation.py`
6. [ ] Review bankroll management compliance

### Resume Criteria
- [ ] Clear explanation for losses identified
- [ ] Model still passes Gatekeeper (PASS)
- [ ] Revised plan documented
- [ ] Reduced sizing (50% of normal) for 2 weeks
```

---

## Model Deployment Procedures

### Deploying New Model Version

```markdown
## Model Deployment: [MODEL-VERSION]

### Pre-Deployment
- [ ] Train model: `python scripts/train_ncaab_elo.py --validate`
- [ ] Backtest: `python scripts/backtest_ncaab_elo.py --test-season 2025`
- [ ] Validate: `python scripts/run_gatekeeper_validation.py`
- [ ] Must get GateDecision.PASS

### Paper Betting Phase
- [ ] Run daily pipeline for 14+ days
- [ ] Track 50+ paper bets
- [ ] Calculate paper CLV (must be >0.5%)

### Go-Live Decision
- [ ] Paper CLV > 0.5%
- [ ] Backtest and paper metrics align
- [ ] No major bugs discovered
- [ ] Documented in `docs/DECISIONS.md`

### Model Rollback
If CLV drops below 0% for 50+ consecutive bets:
1. STOP using new model
2. Revert to previous `.pkl` from `data/processed/`
3. Document incident
4. Investigate root cause
```

---

## Automation

### Windows Task Scheduler

```powershell
# Preferred: Use PowerShell orchestrators via Task Scheduler
.\scripts\setup-scheduled-tasks.ps1 -Action register

# Nightly (11pm): fetch scores, train Elo, scrape Barttorvik, fetch opening odds, dashboard
# Morning (10am): settle yesterday (with auto-CLV) + predict today
```

### Cron Schedule (Linux/Mac)

```bash
# Morning predictions (6am CT = 12:00 UTC)
0 12 * * * cd ~/sports-betting && venv/bin/python scripts/daily_predictions.py --date today >> logs/cron.log 2>&1

# Evening settlement (11pm CT = 05:00 UTC next day)
0 5 * * * cd ~/sports-betting && venv/bin/python scripts/settle_paper_bets.py --date today >> logs/cron.log 2>&1

# Weekly report (Sunday 10pm CT)
0 4 * * 1 cd ~/sports-betting && venv/bin/python scripts/generate_report.py --all >> logs/cron.log 2>&1
```

---

## Quick Reference

### Key Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| Minimum edge (spread/total) | 2% | Below = no bet |
| Minimum edge (ML/prop) | 3% | Below = no bet |
| Maximum single bet | 3% bankroll ($150) | Hard cap |
| Daily exposure limit | 10% bankroll ($500) | Stop betting |
| Weekly loss trigger | 15% bankroll ($750) | Reduce sizing 50% |
| Monthly loss trigger | 25% bankroll ($1,250) | Full stop, review |
| CLV target | >1% | Below = investigate |
| Odds API credits | 500/month | Warning at 80%, cutoff at 90% |

### Key File Locations

| File | Location |
|------|----------|
| Database | `data/betting.db` |
| Trained model | `data/processed/ncaab_elo_model.pkl` |
| Model metadata | `data/processed/ncaab_elo_model.meta.json` |
| Ratings CSV | `data/processed/ncaab_elo_ratings_current.csv` |
| Backtest results | `data/backtests/ncaab_elo_backtest_*.parquet` |
| Validation reports | `data/validation/*_gatekeeper_report.json` |
| API credit tracking | `data/odds_api_usage.json` |
| Raw game data | `data/raw/ncaab/ncaab_games_*.parquet` |
| Config | `config/constants.py`, `config/settings.py` |
| Codemaps | `docs/CODEMAPS/` |

### Command Reference

```bash
# Full pipeline
python scripts/fetch_historical_data.py             # Phase 1: fetch data
python scripts/train_ncaab_elo.py --validate         # Phase 1: train model
python scripts/backtest_ncaab_elo.py                 # Phase 3: backtest
python scripts/run_gatekeeper_validation.py          # Phase 3: validate
python scripts/daily_predictions.py --date today     # Phase 4: predict
python scripts/record_paper_bets.py --date today     # Phase 5: record
python scripts/daily_run.py --settle-only             # Phase 5: settle (with CLV)
python scripts/generate_report.py --all              # Phase 6: report

# Reports
python scripts/generate_report.py --daily            # Today's bets
python scripts/generate_report.py --weekly           # Rolling week
python scripts/generate_report.py --clv              # 30-day CLV analysis
python scripts/generate_report.py --health           # Model drift alerts
python scripts/generate_report.py --odds-health      # Provider health

# Tests
pytest tests/ -v                                     # All tests
pytest tests/ -k "validator" -v                      # Validator tests
pytest tests/ --cov=backtesting --cov=models -v      # With coverage
```

### Database Queries

```sql
-- Recent bets
SELECT game_date, selection, odds_placed, result, clv
FROM bets WHERE game_date >= date('now', '-7 days')
ORDER BY game_date DESC;

-- CLV by sport
SELECT sport, COUNT(*) as bets, AVG(clv) as avg_clv, AVG(profit_loss) as avg_pnl
FROM bets WHERE result IS NOT NULL GROUP BY sport;

-- Bankroll history
SELECT date, ending_balance, daily_pnl, avg_clv
FROM bankroll_log ORDER BY date DESC LIMIT 30;

-- Odds snapshot coverage
SELECT sportsbook, COUNT(*) as count, MAX(captured_at) as latest
FROM odds_snapshots GROUP BY sportsbook;
```

### Emergency Contacts

- Gambling helpline: 1-800-522-4700

---

## Seasonal Operations

### NCAAB Season Start (November)

```markdown
### 2-3 Weeks Before Season
- [ ] Fetch fresh data: `python scripts/fetch_historical_data.py --force`
- [ ] Retrain model: `python scripts/train_ncaab_elo.py --validate`
- [ ] Backtest: `python scripts/backtest_ncaab_elo.py`
- [ ] Validate: `python scripts/run_gatekeeper_validation.py`
- [ ] Verify Odds API key active and credits reset

### Season Start
- [ ] Begin daily pipeline (paper mode)
- [ ] Track CLV daily for 2+ weeks
- [ ] Go live after 50+ paper bets with positive CLV
```

### March Madness Preparation

```markdown
### Pre-Tournament
- [ ] Update model with conference tournament results
- [ ] Verify tournament K-factor (32) active in config
- [ ] Reduce position sizes (more variance in single elimination)
- [ ] Focus on extreme mismatches, avoid coin flips
```
