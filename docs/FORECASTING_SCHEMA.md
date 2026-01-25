# Superforecasting Prediction Market Tracking Schema

## Overview

This database schema implements a comprehensive system for tracking prediction market forecasts and positions, inspired by Philip Tetlock's Good Judgment Project methodology. It integrates with the existing sports betting SQLite database and supports:

- **Belief revision tracking** - Every probability update is recorded with reasoning
- **Calibration analysis** - Brier scores, log scores, and calibration curves
- **Reference class forecasting** - Base rate anchoring and adjustment tracking
- **Question decomposition** - Fermi estimation support
- **Position management** - Paper and live trading across multiple platforms

## Schema Files

| File | Purpose |
|------|---------|
| `scripts/init_forecasting_schema.sql` | SQL DDL statements for all tables, views, triggers |
| `tracking/forecasting_db.py` | Python interface for database operations |

## Table Reference

### 1. FORECASTS

The core table storing individual predictions/forecasts.

```sql
-- Key fields:
forecast_id TEXT PRIMARY KEY      -- UUID identifier
question_text TEXT NOT NULL       -- Full question
question_category TEXT            -- 'geopolitics', 'economics', 'elections', etc.
platform TEXT NOT NULL            -- 'polymarket', 'kalshi', 'predictit', etc.
initial_probability REAL          -- First estimate (0-1)
current_probability REAL          -- Latest estimate (0-1)
resolution_date_expected DATE     -- When we expect resolution
outcome REAL                      -- Actual result (1.0 = yes, 0.0 = no)
brier_score REAL                  -- Scoring (calculated on resolution)
log_score REAL                    -- Alternative scoring metric
```

**Indexes:** category, platform, resolved status, resolution date

### 2. BELIEF_REVISIONS (Critical)

Tracks every probability update - the heart of superforecasting discipline.

```sql
-- Key fields:
forecast_id TEXT                  -- Links to parent forecast
revision_number INTEGER           -- Sequential (1, 2, 3...)
previous_probability REAL         -- Before update
new_probability REAL              -- After update
probability_delta REAL            -- Auto-calculated difference
update_magnitude TEXT             -- 'trivial', 'minor', 'moderate', 'major', 'extreme'
revision_trigger TEXT             -- What prompted the update
reasoning TEXT                    -- Explanation for the change
market_price_at_revision REAL     -- Market price at time of update
```

**Revision Triggers:**

- `new_data` - New statistical data
- `news_event` - Breaking news
- `expert_opinion` - Expert input
- `model_update` - Quantitative model changed
- `market_movement` - Significant market shift
- `reconsideration` - Rethinking existing evidence
- `base_rate_adjustment` - Reference class refinement
- `time_decay` - Time-based update
- `decomposition_update` - Sub-question resolution
- `error_correction` - Fixing a mistake

### 3. REFERENCE_CLASSES

Base rates for reference class forecasting (outside view).

```sql
-- Key fields:
class_name TEXT UNIQUE            -- e.g., "US Presidential Incumbent Re-election"
base_rate REAL                    -- Historical frequency (0-1)
sample_size INTEGER               -- Number of historical cases
source_name TEXT                  -- Where the data came from
applicable_question_types TEXT    -- When to apply this class
times_used INTEGER                -- Usage tracking
```

### 4. CALIBRATION_METRICS

Aggregated performance statistics for tracking forecasting skill.

```sql
-- Key fields:
period_type TEXT                  -- 'daily', 'weekly', 'monthly', 'all_time'
period_start DATE                 -- Period boundaries
period_end DATE
n_forecasts INTEGER               -- Sample size
brier_score REAL                  -- Average Brier score
log_score REAL                    -- Average log score
overconfidence_score REAL         -- Positive = overconfident
bin_X_Y_avg_prob REAL             -- Calibration curve data (10 bins)
bin_X_Y_actual_freq REAL
bin_X_Y_count INTEGER
```

### 5. QUESTION_DECOMPOSITION

Breaks complex questions into sub-questions (Fermi estimation).

```sql
-- Key fields:
parent_forecast_id TEXT           -- Root forecast
parent_component_id INTEGER       -- For nested hierarchies
component_question TEXT           -- Sub-question text
component_type TEXT               -- 'necessary_condition', 'sufficient_condition', etc.
component_probability REAL        -- Probability for sub-question
component_weight REAL             -- Weight in aggregation
aggregation_method TEXT           -- 'multiply' (AND), 'add' (OR), 'weighted_avg'
```

### 6. PM_POSITIONS

Market positions for paper trading and live trading.

```sql
-- Key fields:
position_uuid TEXT UNIQUE         -- Position identifier
forecast_id TEXT                  -- Associated forecast
platform TEXT                     -- Trading platform
position_type TEXT                -- 'yes' or 'no'
entry_price REAL                  -- Entry price
entry_quantity REAL               -- Number of contracts
is_paper BOOLEAN                  -- Paper vs live
realized_pnl REAL                 -- Closed P&L
unrealized_pnl REAL               -- Open P&L
clv_equivalent REAL               -- Edge vs closing price
```

## Key Queries

### Calculate Brier Score

```sql
SELECT
    COUNT(*) as n_forecasts,
    AVG(brier_score) as avg_brier_score,
    0.25 - AVG(brier_score) as improvement_vs_random
FROM forecasts
WHERE is_resolved = TRUE
    AND resolution_date_actual >= date('now', '-90 days');
```

**Interpretation:**

- Brier score of 0.25 = random guessing (50% on everything)
- Brier score of 0.0 = perfect prediction
- Superforecasters typically achieve ~0.15

### Generate Calibration Curve

```sql
SELECT
    CASE
        WHEN current_probability < 0.1 THEN '0-10%'
        WHEN current_probability < 0.2 THEN '10-20%'
        -- ... (see full query in schema file)
    END as probability_bin,
    COUNT(*) as n_forecasts,
    ROUND(AVG(current_probability), 3) as avg_forecast,
    ROUND(AVG(outcome), 3) as actual_frequency,
    ROUND(AVG(outcome) - AVG(current_probability), 3) as calibration_error
FROM forecasts
WHERE is_resolved = TRUE
GROUP BY probability_bin;
```

**Interpretation:**

- Perfect calibration: avg_forecast = actual_frequency for each bin
- Overconfidence: actual_frequency < avg_forecast
- Underconfidence: actual_frequency > avg_forecast

### Analyze Revision Patterns

```sql
SELECT
    revision_trigger,
    COUNT(*) as n_updates,
    AVG(ABS(probability_delta)) as avg_magnitude,
    AVG(CASE
        WHEN f.outcome = 1 AND br.probability_delta > 0 THEN 1
        WHEN f.outcome = 0 AND br.probability_delta < 0 THEN 1
        ELSE 0
    END) as toward_truth_rate
FROM belief_revisions br
JOIN forecasts f ON br.forecast_id = f.forecast_id
WHERE f.is_resolved = TRUE
GROUP BY revision_trigger;
```

**Interpretation:**

- High `toward_truth_rate` (>0.5) = updates improve accuracy
- Low `toward_truth_rate` (<0.5) = updates hurt accuracy

### Identify Overconfidence

```sql
SELECT
    CASE
        WHEN current_probability >= 0.9 THEN 'Very Confident (90%+)'
        WHEN current_probability <= 0.1 THEN 'Very Confident (<10%)'
        ELSE 'Moderate'
    END as confidence_level,
    COUNT(*) as n_forecasts,
    AVG(current_probability) as avg_forecast,
    AVG(outcome) as actual_rate,
    CASE
        WHEN AVG(outcome) < AVG(current_probability) THEN 'OVERCONFIDENT'
        ELSE 'UNDERCONFIDENT'
    END as bias
FROM forecasts
WHERE is_resolved = TRUE
GROUP BY confidence_level;
```

## Python Usage

### Basic Workflow

```python
from tracking.forecasting_db import ForecastingDatabase

# Initialize
db = ForecastingDatabase("data/betting.db")

# Create a forecast
forecast_id = db.create_forecast(
    question_text="Will the Fed cut rates by 50+ bps in Q1 2025?",
    question_category="economics",
    platform="polymarket",
    initial_probability=0.35,
    resolution_date_expected=date(2025, 3, 31),
    question_short="Fed 50bp+ cut Q1 2025",
    initial_confidence="medium",
    base_rate_used=0.30
)

# Record a belief revision
db.record_revision(
    forecast_id=forecast_id,
    new_probability=0.42,
    revision_trigger="news_event",
    reasoning="FOMC showed dovish tilt",
    evidence_quality="strong",
    evidence_direction="bullish"
)

# Open a position
position_id = db.create_position(
    forecast_id=forecast_id,
    platform="polymarket",
    market_id="fed-rate-cut-q1-2025",
    position_type="yes",
    entry_price=0.38,
    entry_quantity=100,
    is_paper=True,
    our_probability_at_entry=0.42
)

# Later: resolve the forecast
scores = db.resolve_forecast(
    forecast_id=forecast_id,
    outcome=1.0,  # Yes happened
    outcome_source="https://federalreserve.gov/..."
)
print(f"Brier Score: {scores['brier_score']:.4f}")

# Analyze calibration
bins = db.generate_calibration_curve()
for b in bins:
    print(f"{b.bin_label}: forecast={b.avg_forecast:.2f}, actual={b.actual_frequency:.2f}")
```

### Calibration Analysis

```python
# Overall Brier score
scores = db.calculate_brier_score(days=90)
print(f"Last 90 days: {scores['avg_brier_score']:.4f}")

# By category
for category in ['economics', 'geopolitics', 'elections']:
    scores = db.calculate_brier_score(category=category)
    if scores['n_forecasts'] > 0:
        print(f"{category}: {scores['avg_brier_score']:.4f} (n={scores['n_forecasts']})")

# Overconfidence analysis
analysis = db.analyze_overconfidence()
for level, metrics in analysis.items():
    print(f"{level}: {metrics['bias']} by {abs(metrics['calibration_error']):.2%}")
```

### Revision Pattern Analysis

```python
patterns = db.analyze_revision_patterns()
for trigger, metrics in patterns.items():
    print(f"{trigger}:")
    print(f"  Updates: {metrics['n_updates']}")
    print(f"  Avg magnitude: {metrics['avg_magnitude']:.2%}")
    print(f"  Toward truth: {metrics['toward_truth_rate']:.1%}")
```

## Scoring Metrics Explained

### Brier Score

The Brier score measures the accuracy of probabilistic predictions:

```
Brier Score = (probability - outcome)^2
```

| Score | Interpretation |
|-------|---------------|
| 0.00 | Perfect prediction |
| 0.10 | Excellent (superforecaster level) |
| 0.15 | Very good |
| 0.20 | Good |
| 0.25 | Random guessing (50% on everything) |
| 0.50 | Maximally wrong (100% confident and wrong) |

### Log Score

More punishing for confident wrong predictions:

```
Log Score = -log(probability) if outcome = 1
          = -log(1 - probability) if outcome = 0
```

### CLV Equivalent

For prediction markets, analogous to Closing Line Value in sports betting:

```
CLV = closing_price - entry_price  (for "yes" positions)
```

Positive CLV indicates you got a better price than where the market settled.

## Best Practices

### 1. Record All Revisions

Every time you update your probability, record it with reasoning:

```python
db.record_revision(
    forecast_id=fc_id,
    new_probability=0.45,
    revision_trigger="news_event",
    reasoning="Detailed explanation of what changed your mind",
    evidence_quality="strong",
    evidence_direction="bullish"
)
```

### 2. Use Reference Classes

Anchor predictions with base rates:

```python
# Create reference class
ref_id = db.create_reference_class(
    class_name="Startup Series A Success",
    class_category="corporate",
    base_rate=0.20,
    sample_size=1000,
    source_name="CB Insights"
)

# Use when creating forecast
db.create_forecast(
    ...,
    reference_class_id=ref_id,
    base_rate_used=0.20
)
```

### 3. Decompose Complex Questions

Break questions into sub-questions:

```python
# For "Will X win the election?"
# Decompose into:
# - Will X win the primary? (necessary)
# - Will X maintain current polling? (factor)
# - Will there be a major scandal? (risk)
```

### 4. Regular Calibration Review

Run calibration analysis regularly:

```python
# Weekly review
db.store_calibration_metrics(
    period_type="weekly",
    period_start=last_monday,
    period_end=today
)
```

### 5. Track Both Paper and Live

Paper trade extensively before live trading:

```python
# Paper trade first
db.create_position(..., is_paper=True)

# Move to live after demonstrating skill
db.create_position(..., is_paper=False)
```

## Integration with Sports Betting

The forecasting schema complements the existing sports betting schema:

| Sports Betting | Prediction Markets |
|---------------|-------------------|
| `bets` table | `pm_positions` table |
| `odds_placed` / `odds_closing` | `entry_price` / `closing_price` |
| CLV tracking | `clv_equivalent` |
| `model_probability` | `our_probability_at_entry` |

Both systems share:

- Bankroll tracking
- Performance analysis
- Kelly criterion sizing

## Database Maintenance

### Initialize Schema

```bash
sqlite3 data/betting.db < scripts/init_forecasting_schema.sql
```

### Backup

```bash
# Regular backup
cp data/betting.db data/betting_backup_$(date +%Y%m%d).db
```

### Vacuum (optimize)

```sql
VACUUM;
ANALYZE;
```

## Appendix: Full Schema Diagram

```
forecasts (1) ----< belief_revisions (many)
    |
    +---- reference_classes (many:1)
    |
    +----< question_decomposition (many)
    |
    +----< pm_positions (many)

calibration_metrics (standalone aggregates)
forecaster_metrics (for team tracking)
```
