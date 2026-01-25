# Project: Sports Betting Model Development

## Overview

Build profitable projection models for NCAA Football, NCAA Basketball, NFL, and MLB achieving positive ROI through systematic Closing Line Value (CLV) capture with zero startup costs.

## Tech Stack

- Language: Python 3.11+
- Framework: pandas, scikit-learn, statsmodels
- Database: SQLite (local), potential PostgreSQL migration
- Testing: pytest
- Orchestration: claude-flow (multi-agent swarms)

---

## Claude Flow Configuration

### Swarm Settings

```yaml
topology: hierarchical
maxAgents: 8
strategy: parallel
memoryEnabled: true
```

### Agent Types for This Project

| Agent | Purpose |
|-------|---------|
| `architect` | Model design, system structure |
| `coder` | Implementation |
| `tester` | Write tests, validation |
| `analyst` | Data analysis, performance review |
| `reviewer` | Code review, overfitting detection |
| `researcher` | Market inefficiency research |

### Memory Namespaces

- `coordination` — Agent state (required for swarms)
- `betting/decisions` — Architectural choices, ADRs
- `betting/patterns` — Learned solutions, reusable code
- `betting/models` — Model configs, hyperparameters
- `betting/bugs` — Known issues and fixes

---

## Workflows

### New Model Development

```bash
# 1. Design
npx claude-flow@alpha sparc run specification "NCAAB Elo rating system with MOV adjustments"
npx claude-flow@alpha sparc run architecture "NCAAB Elo model"

# 2. Implement with TDD
npx claude-flow@alpha sparc tdd "NCAAB Elo model"

# 3. Or use swarm for complex features
npx claude-flow@alpha swarm init --topology hierarchical --max-agents 5
npx claude-flow@alpha swarm "Build MLB F5 pitcher model with xFIP, SIERA, Statcast metrics" --agents 4
```

### Bug Fix

```bash
# Query for similar past fixes
npx claude-flow@alpha memory query "data leakage" --reasoningbank

# Fix and store pattern
npx claude-flow@alpha memory store "leakage_fix_rolling" "Always use .shift(1) after rolling calculations" --namespace betting/patterns
```

### Backtesting

```bash
npx claude-flow@alpha swarm "Walk-forward backtest NCAAB Elo 2020-2025, track CLV" --agents 3

# Store results
npx claude-flow@alpha memory store "ncaab_elo_v1" "CLV: 1.2%, ROI: 3.1%, n=847" --namespace betting/models
```

---

## Commands Cheatsheet

```bash
# SETUP
npx claude-flow@alpha init
npx claude-flow@alpha memory init --reasoningbank

# SWARM
npx claude-flow@alpha swarm init --topology hierarchical --max-agents 6
npx claude-flow@alpha swarm "[task]" --agents 4
npx claude-flow@alpha swarm status

# AGENTS
npx claude-flow@alpha agent spawn [type] --name "[name]"
npx claude-flow@alpha agent list

# MEMORY
npx claude-flow@alpha memory store [key] "[value]" --namespace betting/[ns]
npx claude-flow@alpha memory query "[search]" --namespace betting/[ns]
npx claude-flow@alpha memory list --namespace betting/[ns]

# SPARC
npx claude-flow@alpha sparc run specification "[task]"
npx claude-flow@alpha sparc run architecture "[task]"
npx claude-flow@alpha sparc tdd "[task]"
```

---

## Project Structure

```
sports_betting/
├── CLAUDE.md                 # This file - Claude Code context
├── README.md                 # Project overview
├── requirements.txt          # Python dependencies
├── .env                      # API keys (gitignored)
├── .gitignore
├── .claude-flow/             # Claude-flow configuration (auto-generated)
│   ├── config.yaml
│   └── memory/
│
├── config/
│   ├── settings.py           # Global configuration
│   ├── constants.py          # Magic numbers, thresholds
│   └── sportsbooks.py        # Book-specific settings
│
├── data/
│   ├── raw/                  # Unprocessed data downloads
│   │   ├── ncaab/
│   │   ├── mlb/
│   │   ├── nfl/
│   │   └── ncaaf/
│   ├── processed/            # Cleaned, feature-engineered data
│   ├── odds/                 # Historical and current odds
│   └── external/             # Weather, injuries, etc.
│
├── models/
│   ├── base.py               # Abstract base model class
│   ├── elo.py                # Elo rating system
│   ├── regression.py         # Linear/logistic regression models
│   ├── poisson.py            # Poisson models (run scoring)
│   ├── ensemble.py           # Model combination logic
│   └── sport_specific/
│       ├── ncaab/
│       │   ├── team_ratings.py
│       │   ├── player_impact.py
│       │   └── tournament.py
│       ├── mlb/
│       │   ├── pitcher_model.py
│       │   ├── team_offense.py
│       │   ├── f5_model.py
│       │   └── player_props.py
│       ├── nfl/
│       │   └── [future]
│       └── ncaaf/
│           └── [future]
│
├── features/
│   ├── engineering.py        # Feature creation utilities
│   ├── selection.py          # Feature importance, selection
│   └── sport_specific/
│       ├── ncaab_features.py
│       ├── mlb_features.py
│       └── [others]
│
├── betting/
│   ├── kelly.py              # Kelly criterion calculations
│   ├── ev.py                 # Expected value calculations
│   ├── clv.py                # Closing line value tracking
│   ├── odds_converter.py     # American/decimal/implied prob
│   └── line_shopping.py      # Multi-book comparison
│
├── tracking/
│   ├── database.py           # SQLite interface
│   ├── models.py             # Database schema/ORM
│   ├── logger.py             # Bet logging utilities
│   └── reports.py            # Performance reporting
│
├── backtesting/
│   ├── walk_forward.py       # Walk-forward validation
│   ├── metrics.py            # Evaluation metrics
│   └── simulation.py         # Monte Carlo simulations
│
├── pipelines/
│   ├── data_refresh.py       # Daily data updates
│   ├── prediction.py         # Generate daily predictions
│   └── betting_workflow.py   # End-to-end betting flow
│
├── notebooks/
│   ├── exploration/          # EDA notebooks
│   ├── modeling/             # Model development
│   └── analysis/             # Performance analysis
│
├── tests/
│   ├── test_models.py
│   ├── test_betting.py
│   └── test_data.py
│
├── scripts/
│   ├── setup_database.py     # Initialize SQLite
│   ├── daily_run.py          # Daily prediction script
│   └── backtest_runner.py    # Run backtests
│
└── docs/
    ├── DATA_DICTIONARY.md    # Field definitions
    ├── DECISIONS.md          # Architecture decisions
    └── SESSION_HANDOFF.md    # Session continuity
```

---

## Current Phase & Timeline

### Status Dashboard

| Phase | Dates | Focus | Status |
|-------|-------|-------|--------|
| 1-2 | Jan 24 - Feb 6 | NCAAB foundation | 🔄 In Progress |
| 3-4 | Feb 7 - Feb 20 | NCAAB paper betting + MLB build | ⏳ Upcoming |
| 5-6 | Feb 21 - Mar 6 | March Madness prep | ⏳ Upcoming |
| 7-8 | Mar 7 - Mar 20 | Live testing (small stakes) | ⏳ Upcoming |
| 9-10 | Mar 21 - Apr 3 | MLB deployment | ⏳ Upcoming |

### Current Sprint Focus

- [ ] Set up project structure and environment
- [ ] Initialize claude-flow with memory namespaces
- [ ] Implement NCAAB data pipeline (sportsipy)
- [ ] Build baseline NCAAB Elo model
- [ ] Create SQLite database with schema
- [ ] Begin paper betting tracking

---

## Domain Knowledge - CRITICAL CONTEXT

### Core Principle: CLV > Win Rate

**Closing Line Value is the PRIMARY success metric.** A bettor who consistently gets better odds than closing lines WILL profit long-term, even through losing streaks. Track CLV religiously.

### Key Formulas

```python
# ═══════════════════════════════════════════════════════════════
# ODDS CONVERSIONS
# ═══════════════════════════════════════════════════════════════

def american_to_decimal(american: int) -> float:
    """Convert American odds to decimal odds"""
    if american > 0:
        return (american / 100) + 1
    return (100 / abs(american)) + 1

def american_to_implied_prob(american: int) -> float:
    """Convert American odds to implied probability"""
    if american > 0:
        return 100 / (american + 100)
    return abs(american) / (abs(american) + 100)

def decimal_to_american(decimal: float) -> int:
    """Convert decimal odds to American odds"""
    if decimal >= 2.0:
        return int((decimal - 1) * 100)
    return int(-100 / (decimal - 1))

# ═══════════════════════════════════════════════════════════════
# EXPECTED VALUE
# ═══════════════════════════════════════════════════════════════

def expected_value(win_prob: float, profit_if_win: float, stake: float) -> float:
    """
    Calculate expected value of a bet
    EV = (p × profit) - (q × stake)
    """
    return (win_prob * profit_if_win) - ((1 - win_prob) * stake)

def calculate_edge(model_prob: float, american_odds: int) -> float:
    """Calculate edge: model probability minus implied probability"""
    implied = american_to_implied_prob(american_odds)
    return model_prob - implied

# ═══════════════════════════════════════════════════════════════
# CLOSING LINE VALUE
# ═══════════════════════════════════════════════════════════════

def calculate_clv(odds_placed: int, odds_closing: int) -> float:
    """
    Calculate Closing Line Value
    Positive CLV = got better odds than market closed at
    THIS IS THE KEY PREDICTOR OF LONG-TERM PROFITABILITY
    """
    prob_placed = american_to_implied_prob(odds_placed)
    prob_closing = american_to_implied_prob(odds_closing)
    return (prob_closing - prob_placed) / prob_placed

# ═══════════════════════════════════════════════════════════════
# KELLY CRITERION
# ═══════════════════════════════════════════════════════════════

def fractional_kelly(
    win_prob: float,
    decimal_odds: float,
    fraction: float = 0.25,  # Quarter Kelly default
    max_bet: float = 0.03    # 3% max
) -> float:
    """
    Conservative fractional Kelly bet sizing
    ALWAYS use fractional Kelly - full Kelly is too aggressive
    """
    b = decimal_odds - 1
    q = 1 - win_prob

    if b <= 0:
        return 0.0

    kelly = (b * win_prob - q) / b
    recommended = max(0, kelly * fraction)
    return min(recommended, max_bet)

# ═══════════════════════════════════════════════════════════════
# ELO RATING SYSTEM
# ═══════════════════════════════════════════════════════════════

def elo_expected(rating_a: float, rating_b: float) -> float:
    """Calculate expected win probability for team A"""
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

def elo_update(
    rating: float,
    expected: float,
    actual: float,  # 1=win, 0.5=tie, 0=loss
    k: int = 20
) -> float:
    """Update Elo rating after game result"""
    return rating + k * (actual - expected)

def elo_to_spread(elo_diff: float, points_per_elo: float = 25) -> float:
    """Convert Elo difference to predicted point spread"""
    return elo_diff / points_per_elo

def regress_to_mean(rating: float, mean: float = 1500, factor: float = 0.33) -> float:
    """Apply offseason regression to mean"""
    return mean + (rating - mean) * (1 - factor)
```

### Break-Even Win Rates

| American Odds | Implied Prob | Break-Even |
|---------------|--------------|------------|
| -110 | 52.38% | 52.38% |
| -105 | 51.22% | 51.22% |
| +100 | 50.00% | 50.00% |
| +150 | 40.00% | 40.00% |
| -200 | 66.67% | 66.67% |

### Market Inefficiency Priorities

| Priority | Market | Why |
|----------|--------|-----|
| 1 | Player props (all sports) | Highest inefficiency, lowest book limits |
| 2 | Small conference games (NCAAB/NCAAF) | Reduced coverage |
| 3 | Derivative markets (team totals, F5 lines) | Less sharp action |
| 4 | Main spreads/totals | Highly efficient, benchmark only |

---

## Bankroll & Risk Management

### Current Allocation

| Category | Amount | Notes |
|----------|--------|-------|
| **Total Bankroll** | $5,000 | |
| Active Capital | $4,000 | Distributed across sportsbooks |
| Reserve | $1,000 | Never touch |

### Sportsbook Distribution

| Book | Allocation | Purpose |
|------|------------|---------|
| DraftKings | $1,000 | Primary volume, props |
| FanDuel | $1,000 | Line shopping |
| BetMGM | $750 | Soft lines |
| Caesars | $750 | Line shopping |
| ESPN BET | $500 | Backup |

### Bet Sizing Rules

| Confidence | Kelly Fraction | Max Bet |
|------------|----------------|---------|
| Standard | 0.25 (Quarter) | 3% ($150) |
| High | 0.33 (Third) | 4% ($200) |
| Uncertain | 0.15 | 2% ($100) |

### Risk Limits

| Limit Type | Threshold | Action |
|------------|-----------|--------|
| Daily exposure | 10% ($500) | No new bets |
| Weekly loss | 15% ($750) | Reduce sizing 50% |
| Monthly loss | 25% ($1,250) | Pause, full review |

---

## Database Schema

```sql
-- Core bet tracking
CREATE TABLE bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sport TEXT NOT NULL,
    league TEXT,
    game_date DATE NOT NULL,
    game_id TEXT,

    -- Bet details
    bet_type TEXT NOT NULL,
    selection TEXT NOT NULL,
    line REAL,
    odds_placed INTEGER NOT NULL,
    odds_closing INTEGER,

    -- Model data
    model_probability REAL,
    model_edge REAL,

    -- Execution
    stake REAL NOT NULL,
    sportsbook TEXT NOT NULL,

    -- Results
    result TEXT,
    profit_loss REAL,
    clv REAL,

    -- Metadata
    notes TEXT,
    is_live BOOLEAN DEFAULT FALSE,

    UNIQUE(game_id, bet_type, selection, sportsbook)
);

-- Bankroll tracking
CREATE TABLE bankroll_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL UNIQUE,
    starting_balance REAL,
    ending_balance REAL,
    daily_pnl REAL,
    bets_placed INTEGER,
    bets_won INTEGER,
    bets_lost INTEGER,
    avg_clv REAL
);

-- Model predictions
CREATE TABLE predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sport TEXT NOT NULL,
    game_id TEXT NOT NULL,
    game_date DATE NOT NULL,
    model_name TEXT NOT NULL,
    prediction_type TEXT,
    predicted_value REAL,
    market_value REAL,
    closing_value REAL,
    actual_value REAL,

    UNIQUE(game_id, model_name, prediction_type)
);

-- Team ratings
CREATE TABLE team_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sport TEXT NOT NULL,
    team_id TEXT NOT NULL,
    team_name TEXT NOT NULL,
    season INTEGER NOT NULL,
    rating_type TEXT NOT NULL,
    rating_value REAL NOT NULL,

    UNIQUE(sport, team_id, season, rating_type)
);
```

---

## Coding Standards

### Style

- Follow PEP 8
- Use type hints for all function signatures
- Docstrings for all public functions (Google style)
- Maximum line length: 100 characters

### Naming

- Functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Files: `snake_case.py`

### Testing Requirements

- All model calculations must have unit tests
- Backtest results must be reproducible (set random seeds)
- Test with edge cases: missing data, extreme odds, zero probabilities

### Error Handling Pattern

```python
try:
    data = fetch_game_data(game_id)
except DataNotFoundError:
    logger.warning(f"Game {game_id} not found, skipping")
    return None
except APIRateLimitError:
    logger.error("API rate limit hit, waiting 60s")
    time.sleep(60)
    return fetch_game_data(game_id)
```

---

## Quick Start Commands

```bash
# ═══════════════════════════════════════════════════════════════
# ENVIRONMENT SETUP
# ═══════════════════════════════════════════════════════════════
conda activate sports_betting
cd ~/sports_betting

# ═══════════════════════════════════════════════════════════════
# CLAUDE-FLOW INITIALIZATION (first time only)
# ═══════════════════════════════════════════════════════════════
npx claude-flow@alpha init
npx claude-flow@alpha memory init --reasoningbank

# ═══════════════════════════════════════════════════════════════
# DAILY WORKFLOW
# ═══════════════════════════════════════════════════════════════
python scripts/daily_run.py --sport ncaab
# OR with swarm:
npx claude-flow@alpha swarm "Daily: refresh NCAAB data, generate predictions, find edges" --agents 3

# ═══════════════════════════════════════════════════════════════
# RUN BACKTESTS
# ═══════════════════════════════════════════════════════════════
python scripts/backtest_runner.py --sport ncaab --seasons 2020-2025
# OR with swarm:
npx claude-flow@alpha swarm "Backtest NCAAB Elo 2020-2025, walk-forward, track CLV" --agents 4

# ═══════════════════════════════════════════════════════════════
# PERFORMANCE REPORT
# ═══════════════════════════════════════════════════════════════
python -c "from tracking.reports import weekly_report; weekly_report()"

# ═══════════════════════════════════════════════════════════════
# DATABASE ACCESS
# ═══════════════════════════════════════════════════════════════
sqlite3 data/betting.db
```

---

## Notes for Claude Code / Claude Flow

### Personality & Approach

- Prefer clean, modular code over clever one-liners
- Always explain the "why" behind model choices
- Proactively flag potential overfitting or data leakage risks
- Suggest tests for any new functionality
- Store successful patterns in memory for future reference

### Domain Expertise Expected

- Understand sports betting fundamentals (odds, EV, CLV)
- Know the difference between sharp and soft books
- Recognize common modeling pitfalls (look-ahead bias, leakage)
- Understand walk-forward validation vs random cross-validation

### Memory Usage Guidelines

- **Store** successful patterns, bug fixes, and insights in appropriate namespaces
- **Query** memory before implementing to check for existing solutions
- **Update** performance namespace after each significant backtest or live period
- Use **reasoningbank** for complex debugging and problem-solving

### When In Doubt

- Ask clarifying questions rather than assume
- Default to simpler implementations first
- Prioritize correctness over performance initially
- Always consider: "Could this leak future information?"
- Query memory: `npx claude-flow@alpha memory query "[topic]" --reasoningbank`
