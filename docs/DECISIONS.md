# Architecture Decision Records (ADR)

## Purpose

Document significant technical and strategic decisions with rationale. This helps Claude Code understand not just *what* was decided, but *why*.

---

## ADR-001: Primary Success Metric is CLV, Not Win Rate

**Date:** January 2026
**Status:** Accepted
**Context:** Need to define how we measure model success.

**Decision:**
Closing Line Value (CLV) is the primary success metric, NOT win rate or short-term ROI.

**Rationale:**

- CLV correlates strongly with long-term profitability over 1000+ bets
- Win rate is dominated by variance over small samples
- Professional sportsbooks use CLV to identify sharp bettors
- A 48% winner with positive CLV will outperform a 52% winner with negative CLV long-term

**Consequences:**

- Must capture closing lines for every bet
- Must track line at time of placement vs close
- Short-term results (weeks/months) are less meaningful than CLV trends
- May continue betting through losing streaks if CLV remains positive

---

## ADR-002: Quarter Kelly as Default Bet Sizing

**Date:** January 2026
**Status:** Accepted
**Context:** Need consistent bet sizing strategy.

**Decision:**
Use 0.25 Kelly (quarter Kelly) as the default bet sizing fraction, with 3% bankroll maximum per bet.

**Rationale:**

- Full Kelly assumes perfect probability estimation (we don't have this)
- Full Kelly can lead to 50%+ drawdowns during variance
- Quarter Kelly reduces volatility while maintaining positive expected growth
- 3% cap prevents overexposure on any single bet
- Industry standard among professional bettors

**Consequences:**

- Slower bankroll growth during winning streaks
- Significantly reduced drawdown risk
- Can increase to 1/3 Kelly for high-confidence plays
- Must track actual vs recommended sizing for analysis

---

## ADR-003: Walk-Forward Validation Only (No Random Splits)

**Date:** January 2026
**Status:** Accepted
**Context:** Need backtesting methodology that produces realistic results.

**Decision:**
All backtests must use walk-forward validation with strict time boundaries. Random train/test splits are prohibited.

**Rationale:**

- Sports data has strong temporal dependencies
- Random splits allow data leakage (future info informing past predictions)
- Walk-forward mirrors real betting (train on past, predict future)
- Prevents overfitting to historical patterns that may not persist

**Implementation:**

```python
# CORRECT: Walk-forward
for year in range(2020, 2026):
    train = data[data.season < year]
    test = data[data.season == year]
    model.fit(train)
    predictions = model.predict(test)

# WRONG: Random split
from sklearn.model_selection import train_test_split
train, test = train_test_split(data, test_size=0.2)  # DO NOT USE
```

**Consequences:**

- Smaller effective training sets in early years
- Must carefully manage feature engineering to avoid leakage
- Results will be more conservative but realistic

---

## ADR-004: Start with Elo Before Complex Models

**Date:** January 2026
**Status:** Accepted
**Context:** Need to choose initial modeling approach.

**Decision:**
Build Elo rating systems first before attempting regression or ML models.

**Rationale:**

- Elo is simple, interpretable, and surprisingly effective
- Teaches core concepts: expected value, rating updates, regression to mean
- FiveThirtyEight's Elo models compete with complex approaches
- Provides baseline to compare more complex models against
- Fewer hyperparameters = less overfitting risk

**Consequences:**

- Initial models will be relatively simple
- Can layer complexity (margin of victory, home court) incrementally
- Regression/ML models become second priority
- Must beat Elo baseline before deploying complex models

---

## ADR-005: sportsipy for NCAAB Data (Not hoopR)

**Date:** January 2026
**Status:** Accepted
**Context:** Need to choose NCAAB data source.

**Decision:**
Use sportsipy (Python) for NCAAB data instead of hoopR (R).

**Rationale:**

- Maintains Python-only stack (no R/rpy2 complexity)
- sportsipy covers Sports Reference data adequately
- Simpler environment management
- Can always add hoopR later via rpy2 if needed

**Trade-offs:**

- hoopR has slightly more comprehensive data
- May need to supplement with direct API calls
- KenPom data requires separate handling

**Consequences:**

- NCAAB pipeline is Python-native
- May need custom scrapers for advanced metrics
- Consider adding KenPom subscription later

---

## ADR-006: SQLite for Initial Database (Not PostgreSQL)

**Date:** January 2026
**Status:** Accepted
**Context:** Need database for bet tracking and model data.

**Decision:**
Start with SQLite for all database needs.

**Rationale:**

- Zero configuration required
- File-based = easy backup and portability
- More than sufficient for individual bettor scale
- Can migrate to PostgreSQL if/when scale demands

**When to Reconsider:**

- Multiple concurrent writers needed
- Data exceeds 50GB
- Need advanced query features
- Building web interface with multiple users

**Consequences:**

- Single database file in `data/betting.db`
- Use sqlite3 module or SQLAlchemy
- Backup is just copying a file

---

## ADR-007: Focus on Player Props and Small Conferences

**Date:** January 2026
**Status:** Accepted
**Context:** Need to prioritize which markets to model.

**Decision:**
Prioritize player props (all sports) and small conference games (college) over main spreads/totals.

**Rationale:**

- Research shows main NFL/NBA spreads are highly efficient
- Player props have lowest book limits = acknowledgment of inefficiency
- Small conference games receive less modeling attention from books
- Better edge opportunity compensates for lower volume

**Market Priority Order:**

1. Player props (all sports)
2. Small conference NCAAB/NCAAF
3. Derivative markets (team totals, F5 lines)
4. Main spreads (benchmark/validation only)

**Consequences:**

- More models to build (prop models are player-specific)
- Lower volume of high-confidence plays
- Must track performance by market type

---

## ADR-008: Paper Betting Phase Before Live Capital

**Date:** January 2026
**Status:** Accepted
**Context:** Need validation before risking bankroll.

**Decision:**
Mandatory 2-4 week paper betting phase with CLV tracking before deploying real capital.

**Criteria to Go Live:**

- 50+ paper bets tracked
- Positive CLV over paper betting period
- All tracking systems operational
- Clear understanding of bet sizing execution

**Rationale:**

- Validates model in real-time market conditions
- Tests operational processes (data refresh, prediction, tracking)
- Builds confidence before risking money
- Identifies bugs in non-costly environment

**Consequences:**

- Delayed live deployment
- Must resist urge to skip paper phase
- Paper results don't count toward performance metrics

---

## ADR-009: Multiple Sportsbook Accounts Required

**Date:** January 2026
**Status:** Accepted
**Context:** Need execution strategy for placing bets.

**Decision:**
Maintain accounts at 5+ sportsbooks for line shopping.

**Required Books:**

- DraftKings (primary)
- FanDuel
- BetMGM
- Caesars
- ESPN BET or alternative

**Rationale:**

- Line shopping can be worth 1-2% ROI alone
- Different books are soft on different markets
- Account limitations are inevitable for winners
- Diversification provides execution resilience

**Consequences:**

- More complex bankroll tracking
- Must compare odds before every bet
- May need tools for odds aggregation
- Accept that some accounts will be limited eventually

---

## ADR-010: Conservative Risk Management Thresholds

**Date:** January 2026
**Status:** Accepted
**Context:** Need rules to prevent catastrophic losses.

**Decision:**
Implement strict stop-loss and exposure limits.

**Limits:**
| Limit | Threshold | Action |
|-------|-----------|--------|
| Single bet | 3% max | Hard cap |
| Daily exposure | 10% | No new bets |
| Weekly loss | 15% | Reduce sizing 50% |
| Monthly loss | 25% | Pause, full review |

**Rationale:**

- Preserves capital through inevitable downswings
- Prevents emotional betting after losses
- Forces review when underperforming
- $1,000 reserve provides rebuild option

**Consequences:**

- May miss opportunities during limit periods
- Requires discipline to follow rules
- Must track real-time exposure

---

## ADR-011: Timezone Handling

**Date:** January 2026
**Status:** Accepted
**Context:** Game times come from various sources in different timezone formats. Need consistent handling.

**Decision:**

- Store all timestamps in UTC in the database
- Convert to America/Chicago (Central Time) for display and user-facing output
- Game dates (DATE type) remain in local time of the game venue

**Implementation:**

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Always store in UTC
utc_time = datetime.now(timezone.utc)

# Convert for display
central = ZoneInfo("America/Chicago")
display_time = utc_time.astimezone(central)

# When parsing game times from sources, convert to UTC immediately
def parse_game_time(time_str: str, source_tz: str = "America/New_York") -> datetime:
    """Parse game time and convert to UTC for storage"""
    source = ZoneInfo(source_tz)
    local_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M").replace(tzinfo=source)
    return local_time.astimezone(timezone.utc)
```

**Rationale:**

- UTC is unambiguous and avoids DST issues
- Central Time matches user's location for intuitive display
- Most East Coast games at 7pm ET display as 6pm CT

**Consequences:**

- All database TIMESTAMP columns are UTC
- Must convert on input (from sources) and output (for display)
- Betting deadlines must account for timezone conversion

---

## ADR-012: Missing Data Strategy

**Date:** January 2026
**Status:** Accepted
**Context:** Real-world data has gaps. Need consistent handling per data type.

**Decision:**
Document and implement handling strategy per feature category:

| Data Type | Strategy | Rationale |
|-----------|----------|-----------|
| **Team ratings (new team)** | Initialize at conference average | Better than league average for small conferences |
| **Team ratings (mid-season)** | Carry forward last known | Ratings don't change without games |
| **Player stats (< min games)** | Exclude from model | Insufficient sample unreliable |
| **Player stats (injury mid-season)** | Use pre-injury stats with decay | Recent form still informative |
| **Odds (missing sportsbook)** | Skip that book, use others | Don't impute odds |
| **Closing line unavailable** | Mark CLV as NULL, don't calculate | Can't measure what we don't have |
| **Weather data** | Assume dome/ideal if missing | Conservative assumption |
| **Game result** | Never impute | Wait for actual result |

**Implementation:**

```python
# Example: handling missing team rating
def get_team_rating(team_id: str, as_of_date: date) -> float:
    rating = db.query_latest_rating(team_id, as_of_date)
    if rating is None:
        conference = db.get_team_conference(team_id)
        rating = db.get_conference_average_rating(conference)
        logger.warning(f"No rating for {team_id}, using conference avg: {rating}")
    return rating
```

**Consequences:**

- Must log all imputation for audit
- Some games may be excluded from betting consideration
- Different handling per feature requires documentation

---

## ADR-013: Go-Live Criteria (Formalized)

**Date:** January 2026
**Status:** Accepted
**Context:** Need clear, objective criteria before risking real capital.

**Decision:**
Must meet ALL criteria before deploying real money:

### Mandatory Criteria

| Criterion | Threshold | Measurement |
|-----------|-----------|-------------|
| Paper betting duration | ≥ 14 days | Calendar days with active betting |
| Paper bet sample size | ≥ 50 bets | Total tracked paper bets |
| Paper CLV | > 0.5% average | Mean CLV across all paper bets |
| Paper CLV consistency | > 0% in 10+ day windows | No extended negative CLV periods |
| Backtest CLV | > 1.0% | Walk-forward backtest results |
| Backtest sample | ≥ 500 bets | Backtest bet count |
| System operational | All green | Data refresh, prediction, tracking working |
| Sportsbook accounts | ≥ 4 funded | Funded and withdrawal-tested |
| Documentation | Complete | All ADRs documented, runbooks ready |

### Go-Live Checklist

```markdown
## Pre-Live Verification
- [ ] Paper betting: 14+ days completed
- [ ] Paper bets: 50+ tracked
- [ ] Paper CLV: > 0.5% average
- [ ] Backtest CLV: > 1.0% on 500+ bets
- [ ] Daily data refresh: Working 7+ consecutive days
- [ ] Prediction pipeline: Generating outputs correctly
- [ ] Bet tracking: Recording and settling accurately
- [ ] Sportsbooks: 4+ accounts funded ($750+ each)
- [ ] Line shopping: Comparison tool working
- [ ] Risk limits: Exposure tracking implemented
- [ ] Mental state: No major life stressors
- [ ] Time commitment: Can monitor daily
```

**Rationale:**

- Prevents premature deployment during excitement
- Objective criteria remove emotional decision-making
- 50 bets provides minimal statistical significance
- Multiple criteria catch different failure modes

**Consequences:**

- May delay live betting by weeks
- Requires discipline to not skip criteria
- Clear audit trail for when/why went live

---

## ADR-014: Model Versioning

**Date:** January 2026
**Status:** Accepted
**Context:** Need to track model changes, compare performance across versions.

**Decision:**
Use semantic versioning with configuration tracking:

**Version Format:** `{sport}-{model_type}-v{major}.{minor}.{patch}`

| Component | Increment When |
|-----------|---------------|
| Major | Fundamental model change (new algorithm, new features) |
| Minor | Hyperparameter tuning, threshold adjustments |
| Patch | Bug fixes, no model logic change |

**Examples:**

- `ncaab-elo-v1.0.0` → Initial Elo model
- `ncaab-elo-v1.1.0` → Adjusted K-factor from 20 to 25
- `ncaab-elo-v1.1.1` → Fixed home court calculation bug
- `ncaab-elo-v2.0.0` → Added margin of victory adjustments

**Tracking Requirements:**

```python
# Each model version must have:
model_metadata = {
    "name": "ncaab-elo",
    "version": "1.2.0",
    "config_hash": "sha256:abc123...",  # Hash of all config params
    "git_commit": "def456...",           # Code version
    "trained_on": "2020-01-01 to 2024-12-31",
    "backtest_clv": 0.012,
    "backtest_n": 847,
    "deployed_at": None,  # NULL until live
    "status": "paper"     # development, paper, live, retired
}
```

**Storage:**

- Git tags for code versions
- Database `models` table for metadata

**Consequences:**

- More overhead when making changes
- Clear audit trail for debugging
- Can A/B test model versions

---

## ADR-015: Logging Strategy

**Date:** January 2026
**Status:** Accepted
**Context:** Need comprehensive logging for debugging, auditing, and compliance.

**Decision:**
Implement structured logging with tiered retention:

### Log Levels

| Level | Use Case | Example |
|-------|----------|---------|
| DEBUG | Development only | Variable values, loop iterations |
| INFO | All predictions, bets, key events | "Placed bet: NCAAB Duke -3.5 @ -110" |
| WARNING | Data quality issues, recoverable errors | "Missing closing line for game X" |
| ERROR | System failures, unrecoverable errors | "Database connection failed" |
| CRITICAL | Requires immediate attention | "All sportsbook APIs failing" |

### Log Format

```python
import logging
from loguru import logger

# Structured JSON format for machine parsing
logger.add(
    "logs/sports_betting.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message}",
    rotation="10 MB",
    retention="90 days",
    compression="gz"
)

# Separate file for bets (permanent retention)
logger.add(
    "logs/bets.log",
    filter=lambda record: "bet_placed" in record["extra"],
    rotation="1 month",
    retention="7 years"  # Tax audit period
)
```

### What to Log

| Event | Level | Required Fields |
|-------|-------|-----------------|
| Prediction generated | INFO | game_id, model, prediction, market_line |
| Bet placed | INFO | bet_id, game_id, selection, odds, stake, book |
| Bet settled | INFO | bet_id, result, pnl, clv |
| Data refresh | INFO | sport, records_updated, duration |
| API error | WARNING | endpoint, error_code, retry_count |
| Model trained | INFO | model_version, train_dates, metrics |
| Go-live decision | INFO | all criteria values, decision |

### Retention

| Log Type | Retention | Reason |
|----------|-----------|--------|
| Application logs | 90 days | Debugging window |
| Bet logs | 7 years | Tax compliance |
| Performance metrics | Permanent | Historical analysis |
| Error logs | 1 year | Pattern detection |

**Consequences:**

- Disk space for logs (mitigated by compression)
- Must not log sensitive data (API keys, passwords)
- Enables post-hoc analysis of decisions

---

## Template for New Decisions

```markdown
## ADR-XXX: [Title]

**Date:** [Date]
**Status:** Proposed / Accepted / Deprecated / Superseded
**Context:** [What problem are we solving?]

**Decision:**
[What did we decide?]

**Rationale:**
[Why did we make this decision?]

**Alternatives Considered:**
- [Alternative 1]: [Why rejected]
- [Alternative 2]: [Why rejected]

**Consequences:**
[What are the implications?]
```
