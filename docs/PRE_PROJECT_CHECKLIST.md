# Pre-Project Checklist & Gap Analysis

## Overview

This document identifies what's ready, what's missing, and what decisions need to be made before project initiation.

---

## ✅ COMPLETE - Context Documents

| Document | Status | Purpose |
|----------|--------|---------|
| CLAUDE.md | ✅ Ready | Main Claude Code context |
| CLAUDE-FLOW.md | ✅ Ready | Multi-agent orchestration |
| DATA_DICTIONARY.md | ✅ Ready | Field definitions |
| DECISIONS.md | ✅ Ready | 11 ADRs documented |
| SESSION_HANDOFF.md | ✅ Ready | Session continuity |
| constants.py | ✅ Ready | Configuration values |

---

## ⚠️ MISSING - Critical Setup Files

### 1. Environment Configuration

| File | Priority | Purpose |
|------|----------|---------|
| `requirements.txt` | 🔴 Critical | Python dependencies |
| `environment.yml` | 🟡 Medium | Conda environment (alternative) |
| `.env.example` | 🔴 Critical | API keys template |
| `.gitignore` | 🔴 Critical | Exclude sensitive/temp files |

### 2. Project Files

| File | Priority | Purpose |
|------|----------|---------|
| `README.md` | 🟡 Medium | Human-readable project overview |
| `setup.py` or `pyproject.toml` | 🟢 Low | Package configuration |
| `Makefile` | 🟢 Low | Common commands |

### 3. Database

| File | Priority | Purpose |
|------|----------|---------|
| `scripts/init_database.sql` | 🔴 Critical | Schema creation script |
| `scripts/seed_data.py` | 🟡 Medium | Initial data population |

---

## ⚠️ MISSING - Architectural Decisions

### Undocumented Technical Decisions

| Topic | Question | Recommendation | Priority |
|-------|----------|----------------|----------|
| **Timezone Handling** | How to handle game times across timezones? | Store all times in UTC, convert for display | 🔴 Critical |
| **Missing Data** | How to handle missing features? | Document per-feature strategy (impute, drop, flag) | 🔴 Critical |
| **Model Versioning** | How to track model versions? | Semantic versioning + git tags + config hashes | 🟡 Medium |
| **Data Refresh Frequency** | When to update data? | Ratings: after each game; Odds: hourly; Stats: daily | 🟡 Medium |
| **Error Handling** | Retry logic, failure modes? | Document per-component with fallbacks | 🟡 Medium |
| **Logging Strategy** | What to log, where, retention? | Structured logging to file + console, 90-day retention | 🟡 Medium |
| **Feature Store** | How to manage engineered features? | SQLite table with feature versioning | 🟢 Low |

### Undocumented Strategic Decisions

| Topic | Question | Needs Decision | Priority |
|-------|----------|----------------|----------|
| **Model Retirement** | When to stop using a model? | Criteria: CLV < 0% over 200 bets, or 3 months | 🟡 Medium |
| **Go-Live Criteria** | Exact thresholds to deploy? | Paper CLV > 0.5%, n > 50, systems tested | 🔴 Critical |
| **Sharp Book Strategy** | Use Pinnacle/Circa for CLV tracking? | Yes for true line, No for betting (will be limited) | 🟡 Medium |
| **Account Limitation Response** | What to do when limited? | Document: reduce bet size, diversify, offshore options | 🟡 Medium |
| **Tax Handling** | Track for tax purposes? | Yes: net P&L by year, keep all records | 🟢 Low |

---

## ⚠️ MISSING - Operational Documents

### 1. Sportsbook Playbook

**Purpose:** Book-specific knowledge for optimal execution

```markdown
Needed content:
- Which books are soft on which markets
- Typical limits by market type
- When/how books limit winners
- Best times to bet each book
- Promo/bonus strategies
- Withdrawal policies
```

### 2. Operational Checklists

| Checklist | Purpose |
|-----------|---------|
| Daily Operations | Morning routine, evening reconciliation |
| Weekly Review | Performance analysis, model health check |
| Monthly Review | Deep analysis, strategy adjustments |
| Model Deployment | Pre-deployment validation steps |
| Incident Response | What to do when things break |

### 3. Emotional Discipline Rules

**Purpose:** Prevent tilt and emotional betting

```markdown
Needed content:
- When to step away (consecutive losses, life stress)
- What NOT to do after a bad beat
- How to handle winning streaks
- Rules for increasing/decreasing activity
```

---

## ⚠️ MISSING - Data Source Documentation

### Data Source Reliability Matrix

| Source | Sport | Reliability | Rate Limits | Cost | Notes |
|--------|-------|-------------|-------------|------|-------|
| sportsipy | NCAAB | ? | ? | Free | Need to document |
| pybaseball | MLB | ? | ? | Free | Need to document |
| nfl-data-py | NFL | ? | ? | Free | Need to document |
| Odds API | All | ? | 500/month | Free tier | Need to document |
| Covers.com | All | ? | Scraping | Free | Legal concerns? |

---

## 🔴 PRIORITY ACTIONS BEFORE PROJECT START

### Must Have (Day 0)

1. [ ] `requirements.txt` - Can't install dependencies without it
2. [ ] `.gitignore` - Prevent committing secrets/data
3. [ ] `.env.example` - Document required API keys
4. [ ] `scripts/init_database.sql` - Database schema ready to execute
5. [ ] ADR-012: Timezone Handling
6. [ ] ADR-013: Missing Data Strategy
7. [ ] ADR-014: Go-Live Criteria (formalize)

### Should Have (Week 1)

8. [ ] Sportsbook Playbook (basic version)
9. [ ] Daily Operations Checklist
10. [ ] Data Source Documentation
11. [ ] ADR-015: Model Versioning
12. [ ] ADR-016: Logging Strategy

### Nice to Have (Week 2+)

13. [ ] README.md
14. [ ] Weekly/Monthly Review Templates
15. [ ] Emotional Discipline Rules
16. [ ] Incident Response Playbook

---

## Recommended New ADRs

### ADR-012: Timezone Handling

```
Decision: Store all timestamps in UTC. Convert to America/Chicago for display.
Rationale: Game times come in various formats. UTC is unambiguous.
Implementation:
- Database: All TIMESTAMP columns are UTC
- Display: Convert using pytz or zoneinfo
- Odds timestamps: Convert from source timezone to UTC on ingestion
```

### ADR-013: Missing Data Strategy

```
Decision: Document handling per feature category.
Categories:
- Team ratings: Impute with conference average for new teams
- Player stats: Require minimum games, exclude otherwise
- Odds: Skip bet if closing line unavailable
- Weather: Use fallback (dome assumption) if missing
```

### ADR-014: Go-Live Criteria (Formalized)

```
Decision: Must meet ALL criteria before deploying real capital.
Criteria:
- Paper betting period: Minimum 14 days
- Sample size: Minimum 50 tracked bets
- CLV: > 0.5% average over paper period
- Systems: Data refresh, prediction, tracking all operational
- Sportsbooks: 5+ accounts funded and tested
- Mental state: No major life stressors
```

### ADR-015: Model Versioning

```
Decision: Use semantic versioning with config tracking.
Format: {sport}-{model_type}-v{major}.{minor}.{patch}
Example: ncaab-elo-v1.2.0
Track: Git tag + config hash + backtest results
Storage: betting/models namespace in claude-flow memory
```

### ADR-016: Logging Strategy

```
Decision: Structured logging with tiered retention.
Levels:
- DEBUG: Development only
- INFO: All predictions, bets placed
- WARNING: Data quality issues, API failures
- ERROR: System failures, missing required data
Retention: 90 days files, permanent for bet records
Format: JSON for machine parsing
```

---

## Questions for You Before I Create Files

1. **Timezone preference:** You're in America/Chicago - should all display times use this, or do you want UTC?

2. **Data source priorities:** Which do you want documented first?
   - [ ] sportsipy (NCAAB) - needed immediately
   - [ ] pybaseball (MLB) - needed by Week 3
   - [ ] nfl-data-py (NFL) - needed by summer
   - [ ] Odds API - needed immediately

3. **Sportsbook accounts:** Which books do you already have accounts with?
   - This affects the Sportsbook Playbook content

4. **Any API keys you already have?**
   - Odds API?
   - CollegeFootballData.com?
   - Others?

5. **Risk tolerance confirmation:** The 25% monthly stop-loss means at $5K bankroll, you pause at $3,750. Comfortable with this?

---

## Next Steps

If you confirm priorities, I'll create:

1. `requirements.txt` with pinned versions
2. `.gitignore` for Python/data science project
3. `.env.example` with required variables
4. `scripts/init_database.sql` with full schema
5. ADRs 012-016 added to DECISIONS.md
6. Any other priority items you identify
