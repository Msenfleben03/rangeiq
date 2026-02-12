# Operations Runbook

## Overview

Standard operating procedures for daily, weekly, and monthly operations. Follow these checklists to maintain consistent performance tracking and system health.

---

## Daily Operations

### Morning Routine (Before First Games)

**Time:** 2-3 hours before first game of interest

```markdown
## Daily Checklist - [DATE]

### 1. Data Refresh
- [ ] Run data refresh script: `python scripts/daily_run.py --refresh`
- [ ] Verify no API errors in logs
- [ ] Check last update timestamps in database

### 2. Generate Predictions
- [ ] Run prediction pipeline: `python scripts/daily_run.py --predict`
- [ ] Review prediction output for reasonableness
- [ ] Flag any extreme predictions (>10 point edge) for manual review

### 3. Odds Comparison
- [ ] Fetch current odds from all sportsbooks
- [ ] Compare model predictions to market lines
- [ ] Identify edges meeting threshold (≥2% spread/total, ≥3% ML/prop)

### 4. Bet Selection
- [ ] Review all opportunities meeting edge threshold
- [ ] Calculate Kelly sizing for each
- [ ] Check daily exposure limit (10% of bankroll)
- [ ] Prioritize by: edge size, confidence, market liquidity

### 5. Execution
- [ ] Place bets at best available odds
- [ ] Log each bet immediately after placement:
  - Game, selection, line, odds, stake, sportsbook
  - Model probability, edge
- [ ] Verify total exposure within limits

### 6. Documentation
- [ ] Screenshot bet slips (backup)
- [ ] Update SESSION_HANDOFF.md if needed
```

### Evening Routine (After Games Complete)

**Time:** After all tracked games are final

```markdown
## Evening Reconciliation - [DATE]

### 1. Result Collection
- [ ] Fetch final scores for all games with bets
- [ ] Update game results in database

### 2. Bet Settlement
- [ ] Settle all completed bets (win/loss/push)
- [ ] Calculate actual P&L for each bet
- [ ] Fetch closing lines if not already captured

### 3. CLV Calculation
- [ ] Calculate CLV for each settled bet
- [ ] Log any bets where closing line unavailable
- [ ] Flag any significantly negative CLV bets for review

### 4. Daily Summary
- [ ] Record daily P&L
- [ ] Record daily average CLV
- [ ] Update bankroll totals per sportsbook
- [ ] Note any observations or anomalies

### Daily Log Entry
| Metric | Value |
|--------|-------|
| Date | |
| Bets Placed | |
| Bets Settled | |
| Record | W-L-P |
| Gross P&L | $ |
| Net P&L | $ |
| Average CLV | % |
| Notes | |
```

---

## Weekly Operations

### Weekly Review (Sunday Evening)

```markdown
## Weekly Review - Week of [DATE]

### 1. Performance Summary
- [ ] Calculate weekly totals:
  - Total bets:
  - Record: W-L-P
  - Net P&L: $
  - ROI: %
  - Average CLV: %

### 2. Breakdown Analysis
- [ ] Performance by sport:
  | Sport | Bets | Record | P&L | CLV |
  |-------|------|--------|-----|-----|
  | NCAAB | | | | |
  | MLB | | | | |

- [ ] Performance by bet type:
  | Type | Bets | Record | P&L | CLV |
  |------|------|--------|-----|-----|
  | Spread | | | | |
  | Total | | | | |
  | ML | | | | |
  | Prop | | | | |

- [ ] Performance by sportsbook:
  | Book | Bets | Record | P&L | Best Odds % |
  |------|------|--------|-----|-------------|
  | DraftKings | | | | |
  | FanDuel | | | | |

### 3. Model Health Check
- [ ] Review prediction accuracy by model
- [ ] Check for any systematic biases
- [ ] Compare predicted vs actual margins
- [ ] Flag any model drift indicators

### 4. Risk Check
- [ ] Current bankroll: $
- [ ] Weekly drawdown: %
- [ ] Check against 15% weekly stop-loss threshold
- [ ] If >10% down: reduce next week sizing by 50%

### 5. System Health
- [ ] Review error logs from past week
- [ ] Check data freshness
- [ ] Verify all cron jobs/scheduled tasks running
- [ ] Test backup recovery (monthly, but note if due)

### 6. Next Week Planning
- [ ] Key games/events to target
- [ ] Any model updates to deploy
- [ ] Sportsbook balance reallocation needed?

### Weekly Report
Save to: `reports/weekly/week_[DATE].md`
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
| Closing Line Beat % | % | Target: >55% |

### 2. Bankroll Status
| Account | Start | End | Change |
|---------|-------|-----|--------|
| DraftKings | $ | $ | $ |
| FanDuel | $ | $ | $ |
| BetMGM | $ | $ | $ |
| Caesars | $ | $ | $ |
| ESPN BET | $ | $ | $ |
| **Total** | $ | $ | $ |

### 3. Model Performance
| Model | Bets | CLV | ROI | Status |
|-------|------|-----|-----|--------|
| ncaab-elo-v1.x | | | | |
| mlb-f5-v1.x | | | | |

### 4. Strategic Review
- [ ] Which markets outperformed?
- [ ] Which markets underperformed?
- [ ] Any books showing limits or restrictions?
- [ ] Edge decay observed in any markets?

### 5. Risk Assessment
- [ ] Maximum drawdown this month: %
- [ ] Longest losing streak: X bets
- [ ] Check against 25% monthly stop-loss
- [ ] If >20% down: pause and conduct full review

### 6. System Maintenance
- [ ] Database backup verification
- [ ] Log rotation check
- [ ] Clean up temporary files
- [ ] Update any deprecated dependencies

### 7. Tax Tracking (US)
- [ ] Export monthly P&L for records
- [ ] Note any W-2G forms received (wins >$600 at 300:1+)
- [ ] Update running annual total

### 8. Next Month Planning
- [ ] Season changes (start/end of sports)
- [ ] Major events to prepare for
- [ ] Model updates planned
- [ ] Bankroll reallocation strategy

### Monthly Report
Save to: `reports/monthly/[YEAR]-[MONTH].md`
```

---

## Incident Response

### Data Pipeline Failure

```markdown
## Incident: Data Pipeline Failure

### Immediate Actions
1. Check API status pages for data sources
2. Review error logs: `tail -100 logs/sports_betting.log | grep ERROR`
3. Attempt manual data refresh with verbose logging
4. If API is down, use cached data with staleness warning

### Resolution Steps
1. Identify root cause (API down, rate limit, code bug)
2. If rate limit: implement backoff, reduce frequency
3. If API down: switch to backup source if available
4. If code bug: fix, test, deploy

### Post-Incident
- [ ] Document incident in logs
- [ ] Update runbook if new failure mode
- [ ] Consider adding monitoring/alerting
```

### Model Performance Degradation

```markdown
## Incident: Model CLV Dropping

### Detection
- Weekly CLV < 0% for 2+ consecutive weeks
- OR 30-day rolling CLV drops below 0.5%

### Immediate Actions
1. Reduce bet sizing by 50%
2. Review recent bets for patterns
3. Check for data quality issues
4. Compare model predictions to sharp lines (Pinnacle)

### Investigation
1. Is the market becoming more efficient?
2. Did a key feature become stale or unreliable?
3. Regime change in the sport (rule changes, etc.)?
4. Overfitting becoming apparent?

### Resolution
1. If data issue: fix pipeline, retrain if needed
2. If market efficiency: reduce edge thresholds, find new edges
3. If overfitting: simplify model, increase regularization
4. If fundamental change: rebuild model with new data

### Recovery Criteria
- Return to 0.5%+ CLV over 50+ bets
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

### Prevention
- Vary bet timing (don't always bet at same time)
- Mix in some recreational bets
- Don't max bet every play
- Use multiple accounts per book (if legally allowed via family)
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
3. [ ] Review every losing bet for errors/patterns
4. [ ] Check for tilt-induced overbetting
5. [ ] Verify models still have positive expectation
6. [ ] Review bankroll management compliance
7. [ ] Consult with trusted advisor if available

### Resume Criteria
- [ ] Clear explanation for losses identified
- [ ] Model still shows positive backtest CLV
- [ ] Emotional state stable
- [ ] Revised plan documented
- [ ] Reduced sizing (50% of normal) for 2 weeks

### Documentation
Create incident report: `reports/incidents/[DATE]-monthly-stop.md`
```

---

## Automation Scripts

### Cron Schedule (Linux/Mac)

```bash
# Edit crontab: crontab -e

# Daily data refresh (6am CT = 12:00 UTC)
0 12 * * * cd ~/sports_betting && python scripts/daily_run.py --refresh >> logs/cron.log 2>&1

# Evening reconciliation (11pm CT = 05:00 UTC next day)
0 5 * * * cd ~/sports_betting && python scripts/daily_run.py --reconcile >> logs/cron.log 2>&1

# Weekly backup (Sunday 3am CT)
0 9 * * 0 cd ~/sports_betting && ./scripts/backup.sh >> logs/backup.log 2>&1
```

### Windows Task Scheduler

Create scheduled tasks for same operations using Task Scheduler GUI or PowerShell.

---

## Quick Reference

### Key Thresholds

| Metric | Threshold | Action |
|--------|-----------|--------|
| Minimum edge (spread/total) | 2% | Below = no bet |
| Minimum edge (ML/prop) | 3% | Below = no bet |
| Maximum single bet | 3% bankroll | Hard cap |
| Daily exposure limit | 10% bankroll | Stop betting |
| Weekly loss trigger | 15% bankroll | Reduce sizing 50% |
| Monthly loss trigger | 25% bankroll | Full stop, review |
| CLV target | >1% | Below = investigate |

### Emergency Contacts

- Gambling helpline: 1-800-522-4700
- [Add personal emergency contacts]

### Key File Locations

| File | Location |
|------|----------|
| Database | `data/betting.db` |
| Logs | `logs/` |
| Config | `config/constants.py` |
| Reports | `reports/` |
| Backups | `backups/` |

---

## Seasonal Operations

### Season Start Checklist

**NCAAB Season (November)**:

```markdown
## NCAAB Season Start - [YEAR]

### 2-3 Weeks Before Season
- [ ] Collect offseason roster changes (transfers, NBA draft losses)
- [ ] Apply seasonal regression to Elo ratings (33% regression to mean)
- [ ] Update conference memberships for realignment
- [ ] Backtest model on last 3 seasons with walk-forward
- [ ] Set K-factor for new season (default: 20-24)

### 1 Week Before
- [ ] Verify data pipeline works (scrape preseason games if available)
- [ ] Test prediction generation on exhibition games
- [ ] Set up sportsbook accounts if needed
- [ ] Review ADRs for any changes to strategy

### Season Start
- [ ] Begin paper betting for first 10-15 games
- [ ] Track CLV daily
- [ ] Flag any model misbehavior early
- [ ] Go live after meeting criteria (50+ bets, positive CLV)
```

**MLB Season (April)**:

```markdown
## MLB Season Start - [YEAR]

### March (Spring Training)
- [ ] Update pitcher stats with spring training data
- [ ] Set platoon splits from previous season + spring
- [ ] Verify ballpark factors haven't changed
- [ ] Test weather API integration

### Opening Week
- [ ] Start with F5 lines only (more stable early season)
- [ ] Avoid full-game totals until 2-3 weeks in
- [ ] Focus on established starters (avoid rookies early)
- [ ] Increase bet sizing gradually over first month
```

### Season End Procedures

**End of NCAAB Regular Season (March)**:

```markdown
## NCAAB Tournament Preparation

### Pre-Tournament
- [ ] Update models with conference tournament results
- [ ] Create tournament-specific features (seeding, recent performance)
- [ ] Review historical upset patterns
- [ ] Adjust for tournament variance (single elimination)

### Tournament Betting Strategy
- [ ] Reduce position sizes (more variance)
- [ ] Focus on extreme mismatches (avoid coin flips)
- [ ] Track "March Madness" specific CLV separately
```

**End of MLB Season (September)**:

```markdown
## MLB Postseason Transition

### Regular Season Wrap-up
- [ ] Export final stats for offseason analysis
- [ ] Calculate full-season ROI and CLV
- [ ] Document learnings in memory: `betting/models/mlb-season-review`

### Postseason
- [ ] STOP automated betting (playoff rosters/bullpen usage changes)
- [ ] Manual analysis only for postseason bets
- [ ] Much lower volume, higher research per bet
```

---

## Model Deployment Procedures

### Deploying New Model Version

```markdown
## Model Deployment: [MODEL-VERSION]

### Pre-Deployment (Development)
- [ ] Complete model development and hyperparameter tuning
- [ ] Backtest on ≥3 seasons with walk-forward validation
- [ ] Verify backtest CLV > 1.0% on 500+ bets
- [ ] Document in ADR if fundamental change
- [ ] Create model version record in database

### Paper Betting Phase
- [ ] Deploy to paper betting pipeline
- [ ] Run in parallel with existing model (if replacing)
- [ ] Track predictions but don't place real bets
- [ ] Minimum 50 paper bets OR 14 days
- [ ] Calculate paper CLV

### Go-Live Decision
- [ ] Paper CLV > 0.5%
- [ ] Backtest and paper metrics align
- [ ] No major bugs discovered
- [ ] Documented in `docs/DECISIONS.md` or memory

### Production Deployment
- [ ] Update production config to use new model
- [ ] Gradual rollout: 25% → 50% → 100% of bets
- [ ] Monitor first 25 live bets closely
- [ ] Compare live vs paper CLV

### Post-Deployment
- [ ] Monitor for 100 bets or 30 days
- [ ] If CLV drops <0%, roll back immediately
- [ ] Document performance in `betting/models` memory namespace
- [ ] Retire old model after successful 30-day period
```

### Model Rollback Procedure

```markdown
## Emergency Model Rollback

### Triggers
- CLV drops below 0% for 50+ consecutive bets
- Critical bug discovered in production
- Model predictions consistently unreasonable

### Rollback Steps
1. [ ] STOP using new model immediately
2. [ ] Revert to previous stable model version
3. [ ] Document incident: `reports/incidents/model-rollback-[DATE].md`
4. [ ] Investigate root cause
5. [ ] Fix in development environment
6. [ ] Re-run full deployment procedure

### Communication
- Update `DECISIONS.md` with rollback decision
- Store incident summary in `betting/bugs` memory namespace
- Tag code version with failure notes in git
```

---

## Troubleshooting

### Common Issues

**Issue**: Predictions seem too extreme (>15 point spreads)
**Solution**:

1. Check for data errors (wrong team IDs, flipped home/away)
2. Verify Elo ratings haven't diverged (max diff should be <500)
3. Apply seasonal regression if early in season
4. Check logs for feature calculation errors

**Issue**: Cannot fetch odds from sportsbook API
**Solution**:

1. Check API status page
2. Verify API key hasn't expired
3. Check rate limits (may need to slow requests)
4. Fall back to manual odds entry if needed

**Issue**: Bet tracking database locked
**Solution**:

1. Check for long-running queries: `sqlite3 data/betting.db ".timeout 1000"`
2. Close any open database connections
3. Restart application
4. If persistent, copy to backup and rebuild database

**Issue**: CLV calculation returns NaN
**Solution**:

1. Verify closing line was captured (not NULL)
2. Check odds format (ensure American odds, not decimal)
3. Verify odds aren't edge cases (0, extreme values)
4. Review `betting/clv.py` calculation logic

---

## Appendix: Command Reference

### Standalone Scripts

```bash
# Run full daily workflow
python scripts/daily_run.py --all

# Just data refresh
python scripts/daily_run.py --refresh

# Just predictions
python scripts/daily_run.py --predict

# Just reconciliation
python scripts/daily_run.py --reconcile

# Backtest specific model
python scripts/backtest_runner.py --model elo --sport ncaab --seasons 2020-2025

# Generate weekly report
python -c "from tracking.reports import weekly_report; weekly_report()"

# Generate monthly report
python -c "from tracking.reports import monthly_report; monthly_report()"

# Check documentation health
python tracking/doc_metrics.py
```

### Database Queries

```sql
-- Check recent bets
SELECT game_date, selection, odds_placed, result, clv
FROM bets
WHERE game_date >= date('now', '-7 days')
ORDER BY game_date DESC;

-- Calculate average CLV by sport
SELECT sport, COUNT(*) as bets, AVG(clv) as avg_clv, AVG(profit_loss) as avg_pnl
FROM bets
WHERE result IS NOT NULL
GROUP BY sport;

-- Find best performing sportsbook
SELECT sportsbook, COUNT(*) as bets, SUM(profit_loss) as total_pnl, AVG(clv) as avg_clv
FROM bets
WHERE result IS NOT NULL
GROUP BY sportsbook
ORDER BY avg_clv DESC;

-- Check bankroll history
SELECT date, ending_balance, daily_pnl, avg_clv
FROM bankroll_log
ORDER BY date DESC
LIMIT 30;
```

### Git Workflow

```bash
# Before making changes
git status
git pull origin main

# After implementing feature
git add .
git commit -m "Add: MLB pitcher matchup model

- Implemented platoon split adjustments
- Added Statcast pitch quality metrics
- Backtest shows 1.2% CLV over 500 bets"

# Create feature branch for major work
git checkout -b feature/mlb-f5-model
# ... develop ...
git push -u origin feature/mlb-f5-model
# Create PR via gh CLI
gh pr create --title "MLB F5 Model" --body "..."
```

---

**Last Updated**: 2026-01-24
**Maintained By**: Operations Team
**Review Cycle**: Monthly
**Next Review**: 2026-02-24
