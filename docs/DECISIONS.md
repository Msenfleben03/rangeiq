# Architecture Decision Records (ADR)

## Purpose

Document significant technical and strategic decisions with rationale.
This helps Claude Code understand not just *what* was decided, but *why*.

## Scope

This file covers **cross-sport and NCAAB-specific** decisions (ADR-001 through ADR-020).
MLB-specific decisions are in [`docs/mlb/DECISIONS.md`](mlb/DECISIONS.md).

---

## ADR-001: Primary Success Metric is CLV, Not Win Rate

**Date:** January 2026
**Status:** Accepted
**Context:** Need to define how we measure model success.

#### Decision

Closing Line Value (CLV) is the primary success metric, NOT win rate or short-term ROI.

#### Rationale

- CLV correlates strongly with long-term profitability over 1000+ bets
- Win rate is dominated by variance over small samples
- Professional sportsbooks use CLV to identify sharp bettors
- A 48% winner with positive CLV will outperform a 52% winner with negative CLV long-term

#### Consequences

- Must capture closing lines for every bet
- Must track line at time of placement vs close
- Short-term results (weeks/months) are less meaningful than CLV trends
- May continue betting through losing streaks if CLV remains positive

---

## ADR-002: Quarter Kelly as Default Bet Sizing

**Date:** January 2026
**Status:** Accepted
**Context:** Need consistent bet sizing strategy.

#### Decision

Use 0.25 Kelly (quarter Kelly) as the default bet sizing fraction, with 3% bankroll maximum per bet.

#### Rationale

- Full Kelly assumes perfect probability estimation (we don't have this)
- Full Kelly can lead to 50%+ drawdowns during variance
- Quarter Kelly reduces volatility while maintaining positive expected growth
- 3% cap prevents overexposure on any single bet
- Industry standard among professional bettors

#### Consequences

- Slower bankroll growth during winning streaks
- Significantly reduced drawdown risk
- Can increase to 1/3 Kelly for high-confidence plays
- Must track actual vs recommended sizing for analysis

---

## ADR-003: Walk-Forward Validation Only (No Random Splits)

**Date:** January 2026
**Status:** Accepted
**Context:** Need backtesting methodology that produces realistic results.

#### Decision

All backtests must use walk-forward validation with strict time boundaries. Random train/test splits are prohibited.

#### Rationale

- Sports data has strong temporal dependencies
- Random splits allow data leakage (future info informing past predictions)
- Walk-forward mirrors real betting (train on past, predict future)
- Prevents overfitting to historical patterns that may not persist

#### Implementation

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

#### Consequences

- Smaller effective training sets in early years
- Must carefully manage feature engineering to avoid leakage
- Results will be more conservative but realistic

---

## ADR-004: Start with Elo Before Complex Models

**Date:** January 2026
**Status:** Accepted
**Context:** Need to choose initial modeling approach.

#### Decision

Build Elo rating systems first before attempting regression or ML models.

#### Rationale

- Elo is simple, interpretable, and surprisingly effective
- Teaches core concepts: expected value, rating updates, regression to mean
- FiveThirtyEight's Elo models compete with complex approaches
- Provides baseline to compare more complex models against
- Fewer hyperparameters = less overfitting risk

#### Consequences

- Initial models will be relatively simple
- Can layer complexity (margin of victory, home court) incrementally
- Regression/ML models become second priority
- Must beat Elo baseline before deploying complex models

---

## ADR-005: sportsipy for NCAAB Data (Not hoopR)

**Date:** January 2026
**Status:** Accepted
**Context:** Need to choose NCAAB data source.

#### Decision

Use sportsipy (Python) for NCAAB data instead of hoopR (R).

#### Rationale

- Maintains Python-only stack (no R/rpy2 complexity)
- sportsipy covers Sports Reference data adequately
- Simpler environment management
- Can always add hoopR later via rpy2 if needed

#### Trade-offs

- hoopR has slightly more comprehensive data
- May need to supplement with direct API calls
- KenPom data requires separate handling

#### Consequences

- NCAAB pipeline is Python-native
- May need custom scrapers for advanced metrics
- Consider adding KenPom subscription later

---

## ADR-006: SQLite for Initial Database (Not PostgreSQL)

**Date:** January 2026
**Status:** Accepted
**Context:** Need database for bet tracking and model data.

#### Decision

Start with SQLite for all database needs.

#### Rationale

- Zero configuration required
- File-based = easy backup and portability
- More than sufficient for individual bettor scale
- Can migrate to PostgreSQL if/when scale demands

#### When to Reconsider

- Multiple concurrent writers needed
- Data exceeds 50GB
- Need advanced query features
- Building web interface with multiple users

#### Consequences

- Single database file in `data/betting.db`
- Use sqlite3 module or SQLAlchemy
- Backup is just copying a file

---

## ADR-007: Focus on Player Props and Small Conferences

**Date:** January 2026
**Status:** Accepted
**Context:** Need to prioritize which markets to model.

#### Decision

Prioritize player props (all sports) and small conference games (college) over main spreads/totals.

#### Rationale

- Research shows main NFL/NBA spreads are highly efficient
- Player props have lowest book limits = acknowledgment of inefficiency
- Small conference games receive less modeling attention from books
- Better edge opportunity compensates for lower volume

#### Market Priority Order

1. Player props (all sports)
2. Small conference NCAAB/NCAAF
3. Derivative markets (team totals, F5 lines)
4. Main spreads (benchmark/validation only)

#### Consequences

- More models to build (prop models are player-specific)
- Lower volume of high-confidence plays
- Must track performance by market type

---

## ADR-008: Paper Betting Phase Before Live Capital

**Date:** January 2026
**Status:** Accepted
**Context:** Need validation before risking bankroll.

#### Decision

Mandatory 2-4 week paper betting phase with CLV tracking before deploying real capital.

#### Criteria to Go Live

- 50+ paper bets tracked
- Positive CLV over paper betting period
- All tracking systems operational
- Clear understanding of bet sizing execution

#### Rationale

- Validates model in real-time market conditions
- Tests operational processes (data refresh, prediction, tracking)
- Builds confidence before risking money
- Identifies bugs in non-costly environment

#### Consequences

- Delayed live deployment
- Must resist urge to skip paper phase
- Paper results don't count toward performance metrics

---

## ADR-009: Multiple Sportsbook Accounts Required

**Date:** January 2026
**Status:** Accepted
**Context:** Need execution strategy for placing bets.

#### Decision

Maintain accounts at 5+ sportsbooks for line shopping.

#### Required Books

- DraftKings (primary)
- FanDuel
- BetMGM
- Caesars
- ESPN BET or alternative

#### Rationale

- Line shopping can be worth 1-2% ROI alone
- Different books are soft on different markets
- Account limitations are inevitable for winners
- Diversification provides execution resilience

#### Consequences

- More complex bankroll tracking
- Must compare odds before every bet
- May need tools for odds aggregation
- Accept that some accounts will be limited eventually

---

## ADR-010: Conservative Risk Management Thresholds

**Date:** January 2026
**Status:** Accepted
**Context:** Need rules to prevent catastrophic losses.

#### Decision

Implement strict stop-loss and exposure limits.

#### Limits

| Limit | Threshold | Action |
|-------|-----------|--------|
| Single bet | 3% max | Hard cap |
| Daily exposure | 10% | No new bets |
| Weekly loss | 15% | Reduce sizing 50% |
| Monthly loss | 25% | Pause, full review |

#### Rationale

- Preserves capital through inevitable downswings
- Prevents emotional betting after losses
- Forces review when underperforming
- $1,000 reserve provides rebuild option

#### Consequences

- May miss opportunities during limit periods
- Requires discipline to follow rules
- Must track real-time exposure

---

## ADR-011: Timezone Handling

**Date:** January 2026
**Status:** Accepted
**Context:** Game times come from various sources in different timezone formats. Need consistent handling.

#### Decision

- Store all timestamps in UTC in the database
- Convert to America/Chicago (Central Time) for display and user-facing output
- Game dates (DATE type) remain in local time of the game venue

#### Implementation

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

#### Rationale

- UTC is unambiguous and avoids DST issues
- Central Time matches user's location for intuitive display
- Most East Coast games at 7pm ET display as 6pm CT

#### Consequences

- All database TIMESTAMP columns are UTC
- Must convert on input (from sources) and output (for display)
- Betting deadlines must account for timezone conversion

---

## ADR-012: Missing Data Strategy

**Date:** January 2026
**Status:** Accepted
**Context:** Real-world data has gaps. Need consistent handling per data type.

#### Decision

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

#### Implementation

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

#### Consequences

- Must log all imputation for audit
- Some games may be excluded from betting consideration
- Different handling per feature requires documentation

---

## ADR-013: Go-Live Criteria (Formalized)

**Date:** January 2026
**Status:** Accepted
**Context:** Need clear, objective criteria before risking real capital.

#### Decision

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

#### Rationale

- Prevents premature deployment during excitement
- Objective criteria remove emotional decision-making
- 50 bets provides minimal statistical significance
- Multiple criteria catch different failure modes

#### Consequences

- May delay live betting by weeks
- Requires discipline to not skip criteria
- Clear audit trail for when/why went live

---

## ADR-014: Model Versioning

**Date:** January 2026
**Status:** Accepted
**Context:** Need to track model changes, compare performance across versions.

#### Decision

Use semantic versioning with configuration tracking:

**Version Format:** `{sport}-{model_type}-v{major}.{minor}.{patch}`

| Component | Increment When |
|-----------|---------------|
| Major | Fundamental model change (new algorithm, new features) |
| Minor | Hyperparameter tuning, threshold adjustments |
| Patch | Bug fixes, no model logic change |

#### Examples

- `ncaab-elo-v1.0.0` → Initial Elo model
- `ncaab-elo-v1.1.0` → Adjusted K-factor from 20 to 25
- `ncaab-elo-v1.1.1` → Fixed home court calculation bug
- `ncaab-elo-v2.0.0` → Added margin of victory adjustments

#### Tracking Requirements

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

#### Storage

- Git tags for code versions
- Database `models` table for metadata

#### Consequences

- More overhead when making changes
- Clear audit trail for debugging
- Can A/B test model versions

---

## ADR-015: Logging Strategy

**Date:** January 2026
**Status:** Accepted
**Context:** Need comprehensive logging for debugging, auditing, and compliance.

#### Decision

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

#### Consequences

- Disk space for logs (mitigated by compression)
- Must not log sensitive data (API keys, passwords)
- Enables post-hoc analysis of decisions

---

## ADR-016: Advanced Feature Selection for NCAAB Elo Model

**Date:** February 2026
**Status:** Accepted
**Context:** The Elo-only model achieves 6.54% ROI (Sharpe 0.62) but uses no features beyond
Elo ratings, home court, and conference adjustments. Five candidate features were evaluated
through parallel research agents with web search and academic literature review.

#### Decision

Implement 4 features (3 primary GO, 1 modifier) and skip 2:

| Feature | Decision | Rationale |
|---------|----------|-----------|
| Rolling Volatility (5g, 10g) | **GO** | Orthogonal to Elo (second moment); published research; low overfit risk |
| Opponent-Quality-Weighted Margin | **GO** | Quality-adjusts margin; KenPom-inspired; non-redundant with Elo |
| Rest Days / Back-to-Back | **GO** | Fully orthogonal; NBA research shows 6-8% win% impact; zero cost |
| Time Decay (as modifier) | **GO** | Valuable as EWM modifier on margin; redundant as standalone |
| Hurst Exponent | **SKIP** | 30 games << 100 minimum sample; no sports precedent |
| Jensen's Alpha | **SKIP** | Evaluation metric, not feature; circular; redundant with CLV |

#### Alternatives Considered

- KenPom efficiency ratings: Deferred to separate initiative ($25/yr subscription)
- Travel distance: Skipped (data unavailable from ESPN API; marginal over home/away flag)
- Schedule strength trajectory: Skipped (redundant with Elo by construction)

#### Consequences

- All rolling features use `.shift(1)` internally to prevent look-ahead bias
- Features must pass TemporalValidator (0 leaky features) before deployment
- A/B comparison uses paired t-test on common games for statistical rigor
- Failure criterion: Skip features if Sharpe improvement < 0.05 at p < 0.20

**Full Research:** See `docs/ADVANCED_FEATURES_RESEARCH.md`

---

## ADR-017: CBBData REST API for Barttorvik T-Rank Integration

**Date:** February 2026
**Status:** Accepted
**Context:** Need point-in-time efficiency ratings (AdjO, AdjD, AdjEM) for NCAAB model. KenPom is
gold standard but requires $25/year subscription. Barttorvik T-Rank is free, well-respected
alternative with comparable methodology. cbbdata package provides REST API access but documentation
incomplete on date-specific queries.

#### Decision

Use CBBData REST API (`https://www.cbbdata.com/api/`) to access Barttorvik T-Rank historical ratings
archive. Implement Python client wrapper bypassing R package dependency.

#### Rationale

- **Free access** via account registration (vs $25/year for KenPom)
- **Day-by-day historical data** available 2015-present
- **REST API** enables direct Python access without R/rpy2 complexity
- **Comparable accuracy** to KenPom (correlation >0.95 on AdjEM)
- **Updated every 15 minutes** during season (same as KenPom)
- **Flask backend** suggests reliable infrastructure vs web scraping

#### Alternatives Considered

- **KenPom API** ($25/year): Better documentation, proven integration. Deferred until profitability.
- **ESPN BPI** (free): Less accurate (no venue adjustment), no historical archive.
- **sportsipy/cbbpy**: Scraping-based, broken, unmaintained.
- **toRvik R package**: Predecessor using web scraping; replaced by cbbdata API.

#### Implementation Details

API Endpoints:

```text
Base: https://www.cbbdata.com/api/
Auth: POST /auth/login (username, password) → api_key
Archive: GET /torvik/ratings/archive?year=YYYY&key=KEY
Current: GET /torvik/ratings?year=YYYY&key=KEY
```

Data Coverage:

- Seasons: 2015-present (2008-2014 for year-end only)
- Update frequency: Every 15 minutes during season
- Granularity: Day-by-day ratings (supports point-in-time queries)

Expected Fields:

- `barthag`: Win probability vs average D1 team (neutral court)
- `adj_o`: Adjusted offensive efficiency (points per 100 possessions)
- `adj_d`: Adjusted defensive efficiency
- `adj_t`: Adjusted tempo
- `date` or `day_num`: Date field (to be confirmed empirically)

#### Critical Unknown

Documentation does NOT explicitly show date-specific query support (e.g., `?date=20220115`).
Archive is described as "day-by-day" and supports filtering on "any data column", but exact
parameter format requires empirical testing. Worst case: download full season archive,
filter client-side (acceptable given free API).

#### Testing Protocol

1. Register account via R package or undocumented web registration
2. Test login endpoint to obtain API key
3. Fetch 2023 archive with `?year=2023` to inspect schema
4. Test date parameters: `?date=YYYYMMDD`, `?date=YYYY-MM-DD`, `?day_num=N`
5. Verify date field exists in response for point-in-time filtering
6. Measure rate limits and cache aggressively

#### Consequences

- **+Expected**: 20-30% Sharpe improvement (0.62 → 0.8-0.9) from efficiency ratings
- **+Expected**: 1-2% CLV improvement from better model calibration
- Must cache ratings locally to avoid repeated API calls during backtest
- Must validate point-in-time correctness (no look-ahead bias)
- Fall back to KenPom if API unreliable or date queries unsupported
- Account for missing data (T-Rank coverage ~85% of D1 games)

#### Implementation (2026-02-17)

- API returns Apache Parquet (not JSON). Column `adj_tempo` (not `adj_t`).
- Fetcher: `pipelines/barttorvik_fetcher.py` — 347K ratings cached across 6 seasons.
- Team mapper: `pipelines/team_name_mapping.py` — 359 ESPN teams mapped to Barttorvik names.
- Backtest: `--barttorvik` flag on `scripts/backtest_ncaab_elo.py`.
- Coefficients calibrated: `net_diff * 0.003 + barthag_diff * 0.1` (~5% typical adjustment).

#### A/B Results (all 6 seasons, 7.5% edge, paired t-test)

- Elo+Barttorvik vs Elo-only: **p=0.0066 (one-sided)** — significant at p<0.01
- Elo+Barttorvik+Features vs Elo-only: **p=0.0089 (one-sided)** — significant at p<0.01
- Barttorvik improves ROI in all 6 seasons vs Elo-only baseline
- Note: ROI figures are Kelly-compound; flat-stake per-bet returns are the valid metric

**Testing Script:** `scripts/test_cbbdata_api.py`
**Research Report:** `docs/CBBDATA_API_RESEARCH.md`

---

## ADR-018: Grid-Optimized Barttorvik Coefficients

**Date:** February 2026
**Status:** Accepted
**Context:** Quick grid search (12 combos, 2 seasons) found w=1.5/nc=0.003/bc=0.15 with ROI +24.2%.
Need comprehensive search across all seasons to validate and refine these coefficients.

#### Decision

Run full 80-combo grid search (5 weights x 4 net_coeffs x 4 barthag_coeffs) across 6 seasons
(2020-2025). Adopt grid-optimal coefficients for paper betting config.

#### Grid Results

- **Best config:** w=1.5, nc=0.005, bc=0.20
- **ROI:** +24.0%, Sharpe 1.89, p=2.5e-6
- vs quick-grid best: nc changed 0.003→0.005, bc changed 0.15→0.20

#### Rationale

- 6-season validation (2020-2025) provides robust out-of-sample evidence
- p=2.5e-6 rules out chance at any reasonable significance level
- Coefficients are conservative (nc=0.005 means ~0.5% adjustment per unit net rating diff)
- 2026 season excluded from grid (no odds data for backtesting)

#### Implementation

Updated `config/constants.py` PaperBettingConfig:

- `net_diff_coeff`: 0.003 → 0.005
- `barthag_diff_coeff`: 0.1 → 0.20

#### Consequences

- Model slightly more responsive to Barttorvik efficiency differences
- Must re-run grid search if new seasons significantly change optimal parameters
- Paper betting uses grid-optimal config from day 1

---

## ADR-019: Paper Betting Orchestrator (daily_run.py)

**Date:** February 2026
**Status:** Accepted
**Context:** Daily workflow involves 4-5 separate scripts (predict, record, settle, report).
Error-prone and tedious to run manually each day.

#### Decision

Build single `daily_run.py` orchestrator that chains all phases with error handling,
dry-run mode, and selective execution (settle-only, report-only).

#### Rationale

- Single command reduces operational friction for daily usage
- Dry-run mode enables safe preview before committing bets to DB
- Settle-only mode handles cases where morning predictions already ran
- Error in one phase shouldn't prevent other phases from executing
- ESPN Scoreboard API provides real-time game data (replaces manual date entry)

#### Implementation

```bash
daily_run.py --dry-run          # Preview picks, no DB writes
daily_run.py                     # Full: predict → record → settle → report
daily_run.py --settle-only       # Settle yesterday's bets
daily_run.py --report-only       # Weekly performance report
```

#### Consequences

- Daily operation reduced to single command
- 26 tests cover all orchestration paths
- Must handle API failures gracefully (ESPN down, no games today, etc.)
- DB schema must be stable (game_date, profit_loss, confidence columns verified)

---

## ADR-020: Memory/Context Management Strategy

**Date:** February 20, 2026
**Status:** Accepted
**Context:** Evaluate three options for Claude Code memory/context management:
(1) Adopt ECC continuous-learning-v2, (2) Adopt best alternative, (3) Do nothing (enhanced).
Decision driven by 10 "Wrong Approach" incidents across 8 sessions where Claude re-did completed work.

### Research Summary

Three parallel research agents evaluated the options (57K, 87K, 58K tokens respectively):

- **Q1 (Technical Researcher):** Deep code-level evaluation of ECC CL-v2 — read observe.sh, config.json, observer.md, instinct-cli.py. Found 9 failure points.
- **Q2 (Research Analyst):** Surveyed 16 alternative approaches across 4 categories with 30+ cited sources.
- **Q3 (Explore Agent):** Audited all current memory files — line counts, token footprints, redundancy, effectiveness scoring.

---

### 1. Executive Summary

**Recommendation: Option 3+ (Enhanced Current System) with a staged trigger for Option 2.**

The current auto-memory system scores 62/100 in effectiveness. Low-hanging improvements (30 min effort) can push it to 80%+. ECC continuous-learning-v2 is **incompatible with Windows** (9 failure points, python3 stub broken on every hook call) and solves the wrong problem (learns coding patterns, but the friction is session-to-session context loss). The best alternative (PreCompact hooks + Claude Diary) is viable but premature — restructuring MEMORY.md first may eliminate the need entirely.

---

### 2. Current System Assessment (62/100)

| Dimension | Score | Finding |
|-----------|-------|---------|
| Preventing re-work | 3/10 | No phase decision log; no "why was X abandoned?" rationale |
| Technical context | 8/10 | API details, gotchas well-captured in MEMORY.md |
| Context efficiency | 6/10 | ~5K tokens wasted on rule duplicates + TypeScript rules |
| Blocking bugs | 9/10 | Validation framework + Key Patterns strong |
| Session handoff | 4/10 | No structured handoff template; backtest-results.md orphaned |
| Discoverability | 5/10 | Grid search results hard to find; no index |

**Total context footprint:** ~17K tokens always loaded (MEMORY.md + CLAUDE.md + 7 rules + backups).
**Redundant/irrelevant:** ~5K tokens (backup rules, TypeScript rules for Python project).

---

### 3. Option 1: ECC Continuous Learning v2 — NO-GO

**Verdict: INCOMPATIBLE with this environment. Do not adopt.**

#### Critical Failures (code-verified)

| # | Failure | Severity |
|---|---------|----------|
| 1 | `python3` in observe.sh (lines 60, 101, 107, 129) resolves to Windows Store stub — zero observations written | **BLOCKING** |
| 2 | 4 python3 subprocess calls per hook event × 2 events = 6 broken calls per tool use | **BLOCKING** |
| 3 | `kill -USR1` (line 153) terminates observer process instead of waking it | **BLOCKING** |
| 4 | `run_mode: background` in observer.md is undocumented/non-functional in Claude Code | **BLOCKING** |
| 5 | Plugin updates overwrite any python3 fix to observe.sh | HIGH |
| 6 | ~1s added latency per tool call (6 × 157ms Python startup) | HIGH |
| 7 | No mechanism to inject instincts into Claude Code context | HIGH |
| 8 | Observer disabled by default in shipped config.json | MEDIUM |
| 9 | Instinct confidence decay creates seasonal rot (NCAAB Nov-Apr) | LOW |

#### Value Mismatch

The system learns **coding patterns** (functional vs class-based, tool sequencing). This project's friction is **session context loss** (what was already done, why was X abandoned). These are fundamentally different problems. Every "instinct" the system could generate is already explicitly documented in MEMORY.md.

#### Cost: ~$2.53/month Haiku + 47-94s dead latency/session + 45 min/week maintenance

---

### 4. Option 2: Best Alternative — PreCompact Hooks + Claude Diary (VIABLE, DEFERRED)

**Verdict: Technically sound. Deferred pending Option 3+ results.**

#### Architecture

- **Phase 1:** PreCompact + SessionStart hooks (Python scripts)
  - `save_checkpoint.py`: Fires before compaction, writes `.claude/session-state.md`
  - `inject_checkpoint.py`: Fires on startup/resume/compact, injects checkpoint as `additionalContext`
  - Zero LLM cost, zero background processes, pure file I/O
- **Phase 2:** Claude Diary (`/diary`, `/reflect` commands from github.com/rlancemartin/claude-diary)
  - `/diary`: Captures session summary before ending
  - `/reflect`: Weekly analysis → evolves CLAUDE.md rules from failures
  - ~$0.01/week LLM cost

#### Why Deferred (Not Rejected)

- The primary "Wrong Approach" friction appears to occur at **session boundaries** (new sessions), not mid-session compaction
- MEMORY.md restructuring with a handoff template may eliminate 40-60% of incidents without hooks
- Adding hooks introduces new failure modes (hooks stop after 2.5h per claude-code#16047)
- March Madness prep (Phase 5-6) needs stability over experimentation

#### Trigger to Adopt

Adopt Option 2 if, after 2 weeks with Option 3+ improvements:

- "Wrong Approach" incidents remain at 5+ per 8 sessions
- Mid-session compaction is identified as the primary cause (not session-start)
- Setup time: 1.5 hours. Maintenance: 30 min/week.

---

### 5. Option 3+: Enhanced Current System — ADOPTED

**Verdict: Implement immediately. 30 minutes effort, expected 40-60% reduction in Wrong Approach incidents.**

#### Improvements (Priority Order)

| # | Improvement | Effort | Impact | Description |
|---|-----------|--------|--------|-------------|
| P0 | MEMORY.md restructure | 15 min | HIGH | New structure: Handoff → Technical Ref → Results → Dead Ends |
| P1 | Link backtest-results.md | 5 min | MEDIUM | Add "Results Reference" section to MEMORY.md |
| P2 | Delete obsolete rules | 5 min | MEDIUM | Remove `rules/backup/` (9 files) + TypeScript rules (5 files) |
| P3 | Anti-pattern checklist | 10 min | MEDIUM | "NEVER DO" / "ALWAYS DO" section in MEMORY.md |
| -- | **Total** | **35 min** | **HIGH** | Saves ~5K tokens, prevents re-work, improves discoverability |

#### Proposed MEMORY.md Structure

```
## Session Handoff [Latest]
├── Completed Phases (with decisions + rationale)
├── Current State (active task, cached data)
├── Active Blockers (decisions needed)
├── Dead Ends (don't revisit, with WHY)

## Technical Reference [Stable]
├── API Endpoints (KenPom, Barttorvik, ESPN)
├── Known Gotchas (venv, deepcopy, column names)

## Results Archive [Historical]
├── Best Config: w=1.5, nc=0.005, bc=0.20
├── See: memory/backtest-results.md

## Anti-Patterns [CRITICAL]
├── NEVER: [list with reasons]
├── ALWAYS: [list with reasons]
```

---

### 6. Cost-Benefit Matrix (Weighted)

Weights: Wrong Approach reduction (3x), Windows reliability (2x), Weekly maintenance (2x),
Session continuity (2x), Context help (1.5x), Risk of breaking (1.5x), others (1x).

| Dimension (weight) | Option 1: ECC CL-v2 | Option 2: Hybrid | Option 3+: Enhanced |
|---------------------|---------------------|------------------|---------------------|
| Wrong Approach (3x) | 2/5 → 6 | 4/5 → 12 | 3/5 → 9 |
| Windows reliability (2x) | 1/5 → 2 | 5/5 → 10 | 5/5 → 10 |
| Setup time (1x) | 1/5 → 1 | 4/5 → 4 | 5/5 → 5 |
| Weekly maintenance (2x) | 2/5 → 4 | 4/5 → 8 | 5/5 → 10 |
| Token/API cost (1x) | 3/5 → 3 | 5/5 → 5 | 5/5 → 5 |
| Context exhaustion (1.5x) | 1/5 → 1.5 | 4/5 → 6 | 3/5 → 4.5 |
| Session continuity (2x) | 2/5 → 4 | 5/5 → 10 | 3/5 → 6 |
| Risk of breaking (1.5x) | 1/5 → 1.5 | 4/5 → 6 | 5/5 → 7.5 |
| Complexity (1x) | 1/5 → 1 | 3/5 → 3 | 5/5 → 5 |
| Reversibility (1x) | 4/5 → 4 | 5/5 → 5 | 5/5 → 5 |
| **TOTAL (/75)** | **28** | **69** | **67** |

**Sensitivity:** Option 2 and 3+ are within 3% of each other. The deciding factor is **timing**: Option 3+ delivers 85% of Option 2's value at 20% of the effort, and can be layered with Option 2 later.

---

### 7. Risk Register

| Risk | Option | Likelihood | Impact | Mitigation |
|------|--------|------------|--------|------------|
| python3 stub breaks all hooks | 1 | CERTAIN | HIGH | Use absolute interpreter path (fragile) |
| Plugin update overwrites observe.sh fix | 1 | HIGH | HIGH | Fork plugin (maintenance burden) |
| Hooks stop after 2.5h (known bug) | 1, 2 | MEDIUM | MEDIUM | Use PreCompact, not PreToolUse |
| Stop hook infinite loop | 2 | LOW | MEDIUM | Guard with stop_hook_active check |
| MEMORY.md hits 200-line limit | 3+ | MEDIUM | LOW | Externalize Results Archive section |
| Restructured MEMORY.md not followed | 3+ | LOW | LOW | SessionStart hook could enforce |

---

### Decision

**Adopt Option 3+ (Enhanced Current System) immediately. Stage Option 2 as a contingency.**

#### Rationale

1. **Root cause is retrieval, not capture.** MEMORY.md already contains good state — the issue is structure and discoverability, not missing data.
2. **Minimum viable intervention.** 35 minutes of restructuring addresses the same root causes that Option 2 automates, without new failure modes.
3. **Stability during critical phase.** March Madness prep (Phase 5-6) starts in 1 week. Adding hooks now risks destabilizing a working pipeline.
4. **Option 1 is dead on Windows.** 9 failure points, 3 blocking, no viable workaround without forking the plugin.
5. **Option 2 remains available.** If Wrong Approach incidents persist at 5+/8 sessions after restructuring, adopt PreCompact hooks (1.5h setup). Claude Diary can layer on top for long-term rule evolution.

#### Conditions to Re-evaluate

- Wrong Approach incidents remain at 5+/8 sessions after 2 weeks with Option 3+
- Mid-session compaction identified as primary cause (not session-start)
- Project expands to multi-developer or multi-sport pipelines
- ECC CL-v2 ships a Windows-native observer (no python3/bash dependency)

#### Alternatives Considered

- **Option 1 (ECC CL-v2):** Rejected. Windows-incompatible, value mismatch, excessive overhead.
- **Option 2 (PreCompact + Claude Diary):** Deferred. Technically sound but premature given cheaper Option 3+ available.
- **claude-mem (thedotmack):** Rejected. Heavy (Bun + SQLite + Chroma), Stop hook infinite loop risk.
- **memsearch (Zilliz):** Rejected. Requires OpenAI API key for embeddings, Windows untested.
- **idnotbe/claude-memory:** Considered. More sophisticated than needed; revisit if project scales.

#### Consequences

- Immediate: 35 min to restructure MEMORY.md + delete obsolete rules
- Ongoing: ~5 min/session for manual handoff update (already part of workflow)
- Saves: ~5K tokens/session from rule deduplication
- Tracks: "Wrong Approach" incident count as success metric

**Full Research:** See `docs/MEMORY_APPROACHES_RESEARCH.md`

---

## ADR-021: Per-Sport Database Architecture

**Date:** March 2026
**Status:** Accepted
**Context:** The original `betting.db` was a single shared database for all sports with a `sport TEXT` column in every table. After a data wipe incident (Session 44), the rebuild moment presented an opportunity to reconsider whether this architecture served the project well.

#### Decision

Each sport gets its own SQLite database. No shared `betting.db`.

| Database | Owner | Tables |
|----------|-------|--------|
| `data/ncaab_betting.db` | NCAAB pipeline | bets, predictions, odds_snapshots, bankroll_log, team_ratings, barttorvik_ratings, prop_bets, kenpom_ratings, schema_version |
| `data/mlb_data.db` | MLB pipeline | all existing feature store tables + bets, prop_bets, odds_snapshots, game_umpire, linescore |

`config/settings.py` exports `NCAAB_DATABASE_PATH`, `MLB_DATABASE_PATH`, and `DATABASE_PATH` (alias for NCAAB, backwards compat).

#### Rationale

- **No real benefit to sharing**: The `sport` column everywhere added complexity without enabling meaningful cross-sport queries — each pipeline already ran independently
- **Schema divergence**: MLB bets need `pitcher_adj_home/away`, F5 `market_type`, `game_pk` FK — columns that make no sense in NCAAB. A shared table would accumulate NULL-heavy sport-specific columns over time.
- **Season isolation**: NCAAB (Nov–Apr) and MLB (Mar–Oct) have minimal overlap. Cross-sport bankroll aggregation is trivially done at the application layer when needed.
- **Blast radius reduction**: The Session 44 wipe zeroed `betting.db` and destroyed both NCAAB and MLB bet history. Per-sport DBs limit the damage of any single file corruption.
- **Simplicity**: `WHERE sport = 'MLB'` on every query is replaced by just using the right connection.

#### Alternatives Considered

- **Keep shared `betting.db`**: Rejected. No upside; accumulates cross-sport schema complexity.
- **Separate `betting.db` per sport + keep `mlb_data.db` as feature-store-only**: Rejected. Adds a third file with no benefit — `mlb_data.db` is already the natural home for MLB bets since it has FKs to `games`, `players`, `teams`.
- **PostgreSQL with schema-per-sport**: Rejected per ADR-006 (SQLite sufficient at current scale).

#### Consequences

- `prop_bets` table defined in both DBs from day one (empty, ready for when props are modeled)
- `barttorvik_ratings` wide table replaces EAV rows in `team_ratings` for Barttorvik data — stores all four-factor columns (efg_o/d, tov_o/d, orb, drb, ftr_o/d) fetched but previously discarded
- MLB `odds_snapshots` includes `market_type` column (`full_game`, `f5`) enabling F5 odds storage without future schema migrations
- MLB schema bumped to version 2 (`schema_version` table tracks this)
- Backup covers both files: `C:\Users\msenf\sports-betting-backups\` (7 daily, 4 weekly via GFS rotation)

**Implementation plan:** `docs/plans/2026-03-05-schema-overhaul.md`

---

## Template for New Decisions

```markdown
## ADR-XXX: [Title]

**Date:** [Date]
**Status:** Proposed / Accepted / Deprecated / Superseded
**Context:** [What problem are we solving?]

#### Decision
[What did we decide?]

#### Rationale
[Why did we make this decision?]

#### Alternatives Considered
- [Alternative 1]: [Why rejected]
- [Alternative 2]: [Why rejected]

#### Consequences
[What are the implications?]
```
