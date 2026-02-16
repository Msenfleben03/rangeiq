# Pipelines Module

## Purpose

The pipelines module orchestrates automated workflows for data refresh, prediction
generation, and bet placement. It coordinates between data sources, models, betting
logic, and tracking systems to create end-to-end betting workflows.

## Quick Start

```python
from pipelines.daily_run import run_daily_workflow

# Run complete daily workflow
results = run_daily_workflow(
    sport='ncaab',
    date='2026-01-25'
)

# Results include:
# - Data refreshed (latest games, odds, injuries)
# - Models updated (Elo ratings, predictions)
# - Bets identified (positive EV opportunities)
# - Logs updated (predictions stored in database)
```

## Components

### ESPN NCAAB Fetcher (`espn_ncaab_fetcher.py`)

**Purpose**: Fetch NCAAB game data from ESPN's hidden JSON API

**Steps**:

1. Fetch all 362 D-I teams in a single request
2. For each team, fetch schedule with scores
3. Deduplicate and validate game data
4. Save as parquet to `data/raw/ncaab/`

**Usage**:

```python
from pipelines.espn_ncaab_fetcher import ESPNDataFetcher

fetcher = ESPNDataFetcher(output_dir="data/raw/ncaab")
df = fetcher.fetch_season_data(season=2025, delay=0.3)
```

**Note**: Replaced sportsipy (broken as of 2026-02-13). See `docs/DATA_SOURCES.md` for details.

---

### ESPN Core Odds Provider (`espn_core_odds_provider.py`)

**Purpose**: Fetch free historical odds from ESPN Core API (open/close/current lines)

**Steps**:

1. Query events endpoint for available odds providers
2. Fetch detailed odds from best available provider (ESPN BET, DraftKings)
3. Parse into OddsSnapshot frozen dataclass (29 fields)
4. Return spread, total, and moneyline data

**Usage**:

```python
from pipelines.espn_core_odds_provider import ESPNCoreOddsFetcher, ESPNCoreOddsProvider

# Direct fetcher
fetcher = ESPNCoreOddsFetcher()
snapshot = fetcher.fetch_odds_for_event("401524123")

# OddsProvider-compatible (for orchestrator integration)
provider = ESPNCoreOddsProvider()
odds = provider.fetch_game_odds("ncaab", "Duke", "UNC", "401524123")
```

**Coverage**: ~85% of games (small conference/non-D1 return empty). No auth required.

---

### Unified Fetcher (`unified_fetcher.py`)

**Purpose**: Fetch scores + odds in a single pass, eliminating separate backfill steps

**Steps**:

1. Fetch game scores via ESPN Site API (espn_ncaab_fetcher)
2. For each game, fetch odds via ESPN Core API
3. Track skip list for games with no available odds
4. Save enriched parquet (scores + best odds) and raw odds parquet (all providers)

**Usage**:

```python
from pipelines.unified_fetcher import UnifiedNCAABFetcher

fetcher = UnifiedNCAABFetcher()
df = fetcher.fetch_season(season=2025, incremental=True, include_odds=True)
```

**CLI**: `python scripts/fetch_season_data.py --season 2025 --incremental`

**Modes**: `--incremental` (only new games), `--nightly` (current season auto), `--no-odds` (fast scores only)

---

### Data Refresh Pipeline (`data_refresh.py`)

**Purpose**: Daily data updates from all sources

**Steps**:

1. Fetch new games and results from ESPN API / nfl-data-py
2. Update team standings and schedules
3. Fetch current odds from sportsbooks (via OddsOrchestrator)
4. Check injury reports
5. Validate and clean data
6. Store in database

**Usage**:

```python
from pipelines.data_refresh import refresh_sport_data

refresh_sport_data(sport='ncaab', days_back=7)
```

---

### Prediction Pipeline (`prediction.py`)

**Purpose**: Generate predictions for upcoming games

**Steps**:

1. Load latest models (Elo, regression, ensemble)
2. Create features for upcoming games
3. Generate win probabilities and spreads
4. Store predictions in database

**Usage**:

```python
from pipelines.prediction import generate_predictions

predictions = generate_predictions(
    sport='ncaab',
    model_names=['elo', 'regression'],
    lookahead_days=3
)
```

---

### Betting Workflow (`betting_workflow.py`)

**Purpose**: End-to-end bet evaluation and placement

**Steps**:

1. Load predictions for today's games
2. Fetch current odds (line shopping)
3. Calculate EV and Kelly sizing
4. Filter for positive EV bets
5. Log recommended bets
6. (Optional) Auto-place bets via API

**Usage**:

```python
from pipelines.betting_workflow import daily_betting_workflow

recommendations = daily_betting_workflow(
    sport='ncaab',
    min_edge=0.01,    # Require 1%+ edge
    min_kelly=0.01,   # Require 1%+ Kelly
    auto_place=False  # Manual approval required
)
```

## Common Patterns

### Pattern 1: Scheduled Daily Run

```python
# Run via cron: 0 10 * * * (10am daily)
from pipelines.daily_run import run_daily_workflow

try:
    results = run_daily_workflow(sport='ncaab')

    print(f"Data refreshed: {results['games_updated']} games")
    print(f"Predictions generated: {results['predictions_count']}")
    print(f"Bets recommended: {results['bets_count']}")

except Exception as e:
    # Send alert
    send_alert(f"Daily pipeline failed: {e}")
    raise
```

### Pattern 2: Multi-Sport Pipeline

```python
sports = ['ncaab', 'mlb', 'nfl']

for sport in sports:
    try:
        refresh_sport_data(sport)
        generate_predictions(sport)
        run_betting_workflow(sport)
    except Exception as e:
        logging.error(f"{sport} pipeline failed: {e}")
        continue  # Continue with other sports
```

### Pattern 3: Error Recovery

```python
from pipelines.data_refresh import refresh_sport_data
import time

def refresh_with_retry(sport, max_retries=3):
    """Retry data refresh on API failures."""
    for attempt in range(max_retries):
        try:
            return refresh_sport_data(sport)
        except APIRateLimitError:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt * 60  # Exponential backoff
                time.sleep(wait_time)
            else:
                raise
```

## Testing

```bash
pytest tests/test_pipelines.py -v
pytest tests/test_pipelines.py::test_daily_workflow -v --timeout=300
```

## References

- [docs/RUNBOOK.md: Daily Operations](../docs/RUNBOOK.md#daily-workflow)
- [CLAUDE.md: Pipeline Commands](../CLAUDE.md#daily-workflow)
- Related: All other modules (coordinates between them)

---

**Maintained by**: Platform Engineering Team
**Last Updated**: 2026-02-13
**Status**: ✅ Active - Core Infrastructure
