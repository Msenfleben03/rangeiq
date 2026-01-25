-- ==============================================================================
-- SUPERFORECASTING PREDICTION MARKET TRACKING SCHEMA
-- ==============================================================================
-- Based on Philip Tetlock's Good Judgment Project methodology
-- Integrates with existing sports betting SQLite database
--
-- Run: sqlite3 data/betting.db < scripts/init_forecasting_schema.sql
--
-- Key Features:
-- - Belief revision tracking (Bayesian updating discipline)
-- - Calibration metrics (Brier score, log score, resolution)
-- - Reference class forecasting support
-- - Question decomposition (Fermi estimation)
-- - Multi-platform position tracking (Polymarket, Kalshi, PredictIt)
-- ==============================================================================

PRAGMA foreign_keys = ON;

-- ==============================================================================
-- TABLE 1: FORECASTS
-- ==============================================================================
-- Core table storing individual forecasts/predictions
-- Each row represents a unique forecast question or market position

CREATE TABLE IF NOT EXISTS forecasts (
    -- Primary identification
    forecast_id TEXT PRIMARY KEY,           -- UUID for external reference

    -- Question details
    question_text TEXT NOT NULL,            -- Full question text (e.g., "Will Russia invade Ukraine before 2025?")
    question_short TEXT,                    -- Abbreviated question for reports
    question_category TEXT NOT NULL,        -- Category: 'geopolitics', 'economics', 'sports', 'technology', 'science', 'elections', 'corporate', 'other'
    question_subcategory TEXT,              -- More specific classification

    -- Platform and market identification
    platform TEXT NOT NULL,                 -- 'polymarket', 'kalshi', 'predictit', 'metaculus', 'manifold', 'paper', 'gjp'
    market_id TEXT,                         -- Platform-specific market identifier
    contract_id TEXT,                       -- Platform-specific contract/option ID
    market_url TEXT,                        -- Direct link to market

    -- Initial forecast state
    initial_probability REAL NOT NULL       -- First probability estimate (0.0 to 1.0)
        CHECK (initial_probability >= 0 AND initial_probability <= 1),
    initial_confidence TEXT                 -- Self-rated confidence: 'low', 'medium', 'high', 'very_high'
        CHECK (initial_confidence IN ('low', 'medium', 'high', 'very_high')),
    initial_market_price REAL,              -- Market price when forecast was made (0.0 to 1.0)

    -- Current state (updated with each revision)
    current_probability REAL NOT NULL       -- Latest probability estimate
        CHECK (current_probability >= 0 AND current_probability <= 1),
    current_confidence TEXT
        CHECK (current_confidence IN ('low', 'medium', 'high', 'very_high')),
    revision_count INTEGER DEFAULT 0,       -- Number of belief revisions made

    -- Resolution timing
    resolution_date_expected DATE NOT NULL, -- When we expect resolution
    resolution_date_actual DATE,            -- When it actually resolved
    resolution_deadline DATE,               -- Hard deadline for resolution
    time_horizon_days INTEGER,              -- Days from creation to expected resolution

    -- Resolution outcome
    outcome REAL,                           -- Resolved value: 1.0 (yes), 0.0 (no), or continuous for range questions
    outcome_source TEXT,                    -- Source/URL confirming resolution
    outcome_notes TEXT,                     -- Notes about resolution
    is_resolved BOOLEAN DEFAULT FALSE,
    is_ambiguous BOOLEAN DEFAULT FALSE,     -- Resolution was unclear/disputed
    is_voided BOOLEAN DEFAULT FALSE,        -- Market was cancelled/voided

    -- Scoring (calculated after resolution)
    brier_score REAL,                       -- (forecast - outcome)^2 for this forecast
    log_score REAL,                         -- -log(forecast) if outcome=1, -log(1-forecast) if outcome=0

    -- Reference class tracking
    reference_class_id INTEGER,             -- Link to reference class used
    base_rate_used REAL,                    -- Base rate applied (0.0 to 1.0)
    adjustment_from_base REAL,              -- How much we deviated from base rate

    -- Metadata
    tags TEXT,                              -- Comma-separated tags for filtering
    notes TEXT,                             -- General notes
    source_of_question TEXT,                -- Where the question came from
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (reference_class_id) REFERENCES reference_classes(id)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_forecasts_category ON forecasts(question_category);
CREATE INDEX IF NOT EXISTS idx_forecasts_platform ON forecasts(platform);
CREATE INDEX IF NOT EXISTS idx_forecasts_resolved ON forecasts(is_resolved);
CREATE INDEX IF NOT EXISTS idx_forecasts_resolution_date ON forecasts(resolution_date_expected);
CREATE INDEX IF NOT EXISTS idx_forecasts_created ON forecasts(created_at);
CREATE INDEX IF NOT EXISTS idx_forecasts_current_prob ON forecasts(current_probability);


-- ==============================================================================
-- TABLE 2: BELIEF_REVISIONS (CRITICAL)
-- ==============================================================================
-- Tracks EVERY probability update over time
-- This is the heart of the superforecasting methodology - tracking how beliefs evolve
-- Enables analysis of: update frequency, magnitude, triggers, and calibration over time

CREATE TABLE IF NOT EXISTS belief_revisions (
    -- Primary identification
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecast_id TEXT NOT NULL,              -- Links to parent forecast
    revision_number INTEGER NOT NULL,       -- Sequential revision number (1, 2, 3...)

    -- Probability update
    previous_probability REAL NOT NULL      -- Probability before this revision
        CHECK (previous_probability >= 0 AND previous_probability <= 1),
    new_probability REAL NOT NULL           -- Probability after this revision
        CHECK (new_probability >= 0 AND new_probability <= 1),
    probability_delta REAL GENERATED ALWAYS AS (new_probability - previous_probability) STORED,

    -- Magnitude classification
    update_magnitude TEXT GENERATED ALWAYS AS (
        CASE
            WHEN ABS(new_probability - previous_probability) < 0.05 THEN 'trivial'
            WHEN ABS(new_probability - previous_probability) < 0.10 THEN 'minor'
            WHEN ABS(new_probability - previous_probability) < 0.20 THEN 'moderate'
            WHEN ABS(new_probability - previous_probability) < 0.35 THEN 'major'
            ELSE 'extreme'
        END
    ) STORED,

    -- Confidence tracking
    previous_confidence TEXT
        CHECK (previous_confidence IN ('low', 'medium', 'high', 'very_high')),
    new_confidence TEXT
        CHECK (new_confidence IN ('low', 'medium', 'high', 'very_high')),

    -- Market state at revision
    market_price_at_revision REAL           -- Market price when revision was made
        CHECK (market_price_at_revision IS NULL OR (market_price_at_revision >= 0 AND market_price_at_revision <= 1)),
    market_delta REAL,                      -- Change in market price since last revision

    -- Revision trigger/reasoning (critical for learning)
    revision_trigger TEXT NOT NULL,         -- What prompted the update
    -- Allowed values: 'new_data', 'news_event', 'expert_opinion', 'model_update',
    --                 'market_movement', 'reconsideration', 'base_rate_adjustment',
    --                 'time_decay', 'decomposition_update', 'error_correction', 'other'
    trigger_source TEXT,                    -- URL or source of trigger information
    reasoning TEXT,                         -- Detailed reasoning for the update

    -- Evidence quality assessment
    evidence_quality TEXT                   -- How strong was the evidence for this update
        CHECK (evidence_quality IN ('weak', 'moderate', 'strong', 'very_strong')),
    evidence_direction TEXT                 -- Did evidence support higher or lower probability
        CHECK (evidence_direction IN ('bullish', 'bearish', 'mixed', 'neutral')),

    -- Time tracking
    days_since_creation INTEGER,            -- Days since forecast was created
    days_until_resolution INTEGER,          -- Days until expected resolution

    -- Metadata
    revision_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (forecast_id) REFERENCES forecasts(forecast_id) ON DELETE CASCADE,
    UNIQUE(forecast_id, revision_number)
);

-- Indexes for time-series analysis and learning
CREATE INDEX IF NOT EXISTS idx_revisions_forecast ON belief_revisions(forecast_id);
CREATE INDEX IF NOT EXISTS idx_revisions_timestamp ON belief_revisions(revision_timestamp);
CREATE INDEX IF NOT EXISTS idx_revisions_trigger ON belief_revisions(revision_trigger);
CREATE INDEX IF NOT EXISTS idx_revisions_magnitude ON belief_revisions(update_magnitude);
CREATE INDEX IF NOT EXISTS idx_revisions_delta ON belief_revisions(probability_delta);


-- ==============================================================================
-- TABLE 3: REFERENCE_CLASSES
-- ==============================================================================
-- Base rate categories for reference class forecasting
-- Critical for anchoring and avoiding inside view bias

CREATE TABLE IF NOT EXISTS reference_classes (
    -- Primary identification
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_name TEXT UNIQUE NOT NULL,        -- e.g., "US Presidential Incumbent Re-election"
    class_category TEXT NOT NULL,           -- Broad category
    class_description TEXT,                 -- Detailed description

    -- Base rate data
    base_rate REAL NOT NULL                 -- Historical frequency (0.0 to 1.0)
        CHECK (base_rate >= 0 AND base_rate <= 1),
    sample_size INTEGER NOT NULL,           -- Number of historical cases
    sample_period_start DATE,               -- Start of historical data
    sample_period_end DATE,                 -- End of historical data

    -- Confidence in base rate
    base_rate_confidence TEXT               -- How reliable is this base rate
        CHECK (base_rate_confidence IN ('low', 'medium', 'high', 'very_high')),
    base_rate_notes TEXT,                   -- Caveats, methodology notes

    -- Source tracking
    source_name TEXT NOT NULL,              -- Where the base rate came from
    source_url TEXT,                        -- Link to source
    source_type TEXT,                       -- 'academic_paper', 'government_data', 'calculated', 'expert_estimate'

    -- Applicability
    applicable_question_types TEXT,         -- Comma-separated question types this applies to
    selection_criteria TEXT,                -- How to determine if this class applies

    -- Usage tracking
    times_used INTEGER DEFAULT 0,           -- How often this reference class has been used
    avg_adjustment REAL,                    -- Average adjustment from base rate when used

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,                        -- Who added this reference class
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_refclass_category ON reference_classes(class_category);
CREATE INDEX IF NOT EXISTS idx_refclass_baserate ON reference_classes(base_rate);


-- ==============================================================================
-- TABLE 4: CALIBRATION_METRICS
-- ==============================================================================
-- Aggregated performance statistics for calibration analysis
-- Supports multiple time granularities and segmentation

CREATE TABLE IF NOT EXISTS calibration_metrics (
    -- Primary identification
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Time period
    period_type TEXT NOT NULL,              -- 'daily', 'weekly', 'monthly', 'quarterly', 'yearly', 'all_time'
    period_start DATE NOT NULL,             -- Start of period
    period_end DATE NOT NULL,               -- End of period

    -- Segmentation (optional - NULL means aggregate)
    category TEXT,                          -- Question category filter
    platform TEXT,                          -- Platform filter
    time_horizon TEXT,                      -- 'short' (<30d), 'medium' (30-90d), 'long' (>90d)

    -- Sample information
    n_forecasts INTEGER NOT NULL,           -- Number of resolved forecasts in period
    n_revisions INTEGER,                    -- Total belief revisions in period

    -- Overall accuracy metrics
    brier_score REAL,                       -- Average Brier score (lower is better, 0.25 = random)
    log_score REAL,                         -- Average log score (more negative = worse)

    -- Resolution decomposition (Murphy decomposition of Brier score)
    resolution_score REAL,                  -- Variance of base rates (ability to discriminate)
    reliability_score REAL,                 -- Calibration component (deviation from perfect calibration)
    uncertainty_score REAL,                 -- Inherent uncertainty in outcomes

    -- Calibration curve data points (10 bins)
    -- Each stores: avg_forecast_prob, actual_frequency, n_in_bin
    bin_0_10_avg_prob REAL,                 -- Avg probability for forecasts 0-10%
    bin_0_10_actual_freq REAL,              -- Actual outcome frequency for 0-10% bin
    bin_0_10_count INTEGER,                 -- Count of forecasts in 0-10% bin

    bin_10_20_avg_prob REAL,
    bin_10_20_actual_freq REAL,
    bin_10_20_count INTEGER,

    bin_20_30_avg_prob REAL,
    bin_20_30_actual_freq REAL,
    bin_20_30_count INTEGER,

    bin_30_40_avg_prob REAL,
    bin_30_40_actual_freq REAL,
    bin_30_40_count INTEGER,

    bin_40_50_avg_prob REAL,
    bin_40_50_actual_freq REAL,
    bin_40_50_count INTEGER,

    bin_50_60_avg_prob REAL,
    bin_50_60_actual_freq REAL,
    bin_50_60_count INTEGER,

    bin_60_70_avg_prob REAL,
    bin_60_70_actual_freq REAL,
    bin_60_70_count INTEGER,

    bin_70_80_avg_prob REAL,
    bin_70_80_actual_freq REAL,
    bin_70_80_count INTEGER,

    bin_80_90_avg_prob REAL,
    bin_80_90_actual_freq REAL,
    bin_80_90_count INTEGER,

    bin_90_100_avg_prob REAL,
    bin_90_100_actual_freq REAL,
    bin_90_100_count INTEGER,

    -- Confidence/bias metrics
    overconfidence_score REAL,              -- Positive = overconfident, negative = underconfident
    extremity_index REAL,                   -- How often using extreme probabilities (<10% or >90%)

    -- Revision behavior metrics
    avg_revisions_per_forecast REAL,        -- Average number of updates
    avg_revision_magnitude REAL,            -- Average absolute probability change per revision
    revision_consistency REAL,              -- How often revisions move toward eventual outcome

    -- Comparison benchmarks
    market_brier_score REAL,                -- Brier score if we used market prices
    improvement_over_market REAL,           -- Our Brier - Market Brier (negative = we're better)

    -- Metadata
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    calculation_notes TEXT,

    UNIQUE(period_type, period_start, period_end, category, platform, time_horizon)
);

CREATE INDEX IF NOT EXISTS idx_calibration_period ON calibration_metrics(period_type, period_start);
CREATE INDEX IF NOT EXISTS idx_calibration_category ON calibration_metrics(category);
CREATE INDEX IF NOT EXISTS idx_calibration_brier ON calibration_metrics(brier_score);


-- ==============================================================================
-- TABLE 5: QUESTION_DECOMPOSITION
-- ==============================================================================
-- Break complex questions into sub-questions (Fermi estimation)
-- Supports hierarchical decomposition and weighted aggregation

CREATE TABLE IF NOT EXISTS question_decomposition (
    -- Primary identification
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Hierarchy
    parent_forecast_id TEXT NOT NULL,       -- Root forecast this decomposition belongs to
    parent_component_id INTEGER,            -- Parent component (NULL if root-level component)
    component_order INTEGER NOT NULL,       -- Order within parent (1, 2, 3...)
    depth_level INTEGER DEFAULT 1,          -- Nesting depth (1 = direct child of forecast)

    -- Component details
    component_question TEXT NOT NULL,       -- Sub-question text
    component_type TEXT NOT NULL,           -- 'necessary_condition', 'sufficient_condition',
                                           -- 'independent_factor', 'dependent_factor', 'scenario'

    -- Probability and weight
    component_probability REAL              -- Probability for this sub-question
        CHECK (component_probability IS NULL OR (component_probability >= 0 AND component_probability <= 1)),
    component_weight REAL DEFAULT 1.0       -- Weight in aggregation (default 1.0)
        CHECK (component_weight >= 0),
    aggregation_method TEXT,                -- 'multiply' (AND), 'add' (OR), 'weighted_avg', 'custom'

    -- Resolution tracking
    is_resolved BOOLEAN DEFAULT FALSE,
    component_outcome REAL,                 -- Actual outcome for this component
    resolution_date DATE,
    resolution_notes TEXT,

    -- Contribution analysis
    contribution_to_parent REAL,            -- How much this component contributed to parent probability
    sensitivity REAL,                       -- How sensitive is parent to changes in this component

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (parent_forecast_id) REFERENCES forecasts(forecast_id) ON DELETE CASCADE,
    FOREIGN KEY (parent_component_id) REFERENCES question_decomposition(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_decomp_parent ON question_decomposition(parent_forecast_id);
CREATE INDEX IF NOT EXISTS idx_decomp_hierarchy ON question_decomposition(parent_component_id);
CREATE INDEX IF NOT EXISTS idx_decomp_resolved ON question_decomposition(is_resolved);


-- ==============================================================================
-- TABLE 6: POSITIONS
-- ==============================================================================
-- Actual market positions taken (paper or live)
-- Tracks P&L and prediction market equivalent of CLV

CREATE TABLE IF NOT EXISTS pm_positions (
    -- Primary identification
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_uuid TEXT UNIQUE NOT NULL,     -- UUID for external reference
    forecast_id TEXT NOT NULL,              -- Links to forecast

    -- Platform and market
    platform TEXT NOT NULL,                 -- 'polymarket', 'kalshi', 'predictit', etc.
    market_id TEXT NOT NULL,
    contract_id TEXT,

    -- Position type
    position_type TEXT NOT NULL             -- 'yes', 'no', 'long', 'short'
        CHECK (position_type IN ('yes', 'no', 'long', 'short')),
    is_paper BOOLEAN DEFAULT TRUE,          -- TRUE = paper trade, FALSE = real money

    -- Entry details
    entry_price REAL NOT NULL               -- Price paid (0.0 to 1.0 or dollar amount)
        CHECK (entry_price >= 0),
    entry_quantity REAL NOT NULL            -- Number of contracts/shares
        CHECK (entry_quantity > 0),
    entry_cost REAL NOT NULL,               -- Total cost (entry_price * entry_quantity)
    entry_timestamp TIMESTAMP NOT NULL,

    -- Current/exit details
    current_price REAL,                     -- Current market price
    exit_price REAL,                        -- Price when closed (NULL if open)
    exit_quantity REAL,                     -- Quantity closed (may be partial)
    exit_proceeds REAL,                     -- Amount received on exit
    exit_timestamp TIMESTAMP,

    -- Position sizing
    our_probability_at_entry REAL           -- Our forecast probability when entering
        CHECK (our_probability_at_entry IS NULL OR
               (our_probability_at_entry >= 0 AND our_probability_at_entry <= 1)),
    edge_at_entry REAL,                     -- our_probability - market_price (for yes positions)
    kelly_fraction_used REAL,               -- What fraction of Kelly we used
    position_size_pct REAL,                 -- Position as % of bankroll

    -- P&L tracking
    realized_pnl REAL,                      -- Profit/loss on closed portion
    unrealized_pnl REAL,                    -- Mark-to-market P&L on open portion
    total_pnl REAL,                         -- Realized + unrealized
    roi REAL,                               -- Return on investment (total_pnl / entry_cost)

    -- CLV equivalent for prediction markets
    closing_price REAL,                     -- Final market price before resolution
    clv_equivalent REAL,                    -- Edge vs closing price (predictive skill measure)

    -- Status
    status TEXT DEFAULT 'open'              -- 'open', 'closed', 'partial', 'expired', 'voided'
        CHECK (status IN ('open', 'closed', 'partial', 'expired', 'voided')),

    -- Resolution
    final_outcome REAL,                     -- 1.0 (yes), 0.0 (no), or actual value
    settlement_amount REAL,                 -- Amount received at settlement

    -- Risk management
    stop_loss_price REAL,                   -- Stop loss level
    take_profit_price REAL,                 -- Take profit level

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (forecast_id) REFERENCES forecasts(forecast_id)
);

CREATE INDEX IF NOT EXISTS idx_positions_forecast ON pm_positions(forecast_id);
CREATE INDEX IF NOT EXISTS idx_positions_platform ON pm_positions(platform);
CREATE INDEX IF NOT EXISTS idx_positions_status ON pm_positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_paper ON pm_positions(is_paper);
CREATE INDEX IF NOT EXISTS idx_positions_entry ON pm_positions(entry_timestamp);


-- ==============================================================================
-- TABLE 7: FORECASTER_METRICS (For tracking forecaster skill over time)
-- ==============================================================================
-- Track individual forecaster performance if working in teams

CREATE TABLE IF NOT EXISTS forecaster_metrics (
    -- Primary identification
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    forecaster_id TEXT NOT NULL,            -- Identifier for the forecaster

    -- Time period
    period_type TEXT NOT NULL,              -- 'monthly', 'quarterly', 'yearly', 'all_time'
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Activity metrics
    n_forecasts_made INTEGER DEFAULT 0,
    n_forecasts_resolved INTEGER DEFAULT 0,
    n_revisions_made INTEGER DEFAULT 0,
    avg_revisions_per_forecast REAL,

    -- Performance metrics
    brier_score REAL,
    log_score REAL,
    calibration_error REAL,                 -- Root mean square calibration error

    -- Skill decomposition
    resolution_skill REAL,                  -- Ability to discriminate outcomes
    calibration_skill REAL,                 -- Accuracy of probability estimates

    -- Behavioral patterns
    overconfidence_index REAL,              -- Tendency toward overconfidence
    extremity_index REAL,                   -- Tendency toward extreme probabilities
    update_responsiveness REAL,             -- How quickly do they update to new info

    -- Comparative performance
    percentile_rank REAL,                   -- Rank among forecasters (0-100)
    improvement_trend REAL,                 -- Positive = improving over time

    -- Metadata
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(forecaster_id, period_type, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS idx_forecaster_period ON forecaster_metrics(period_type, period_start);
CREATE INDEX IF NOT EXISTS idx_forecaster_brier ON forecaster_metrics(brier_score);


-- ==============================================================================
-- VIEWS FOR COMMON QUERIES
-- ==============================================================================

-- Active forecasts view
CREATE VIEW IF NOT EXISTS v_active_forecasts AS
SELECT
    f.forecast_id,
    f.question_short,
    f.question_category,
    f.platform,
    f.current_probability,
    f.current_confidence,
    f.resolution_date_expected,
    f.revision_count,
    julianday(f.resolution_date_expected) - julianday('now') as days_until_resolution,
    (SELECT MAX(revision_timestamp) FROM belief_revisions br WHERE br.forecast_id = f.forecast_id) as last_revision
FROM forecasts f
WHERE f.is_resolved = FALSE AND f.is_voided = FALSE
ORDER BY f.resolution_date_expected ASC;


-- Resolved forecasts with scores
CREATE VIEW IF NOT EXISTS v_resolved_forecasts AS
SELECT
    f.forecast_id,
    f.question_short,
    f.question_category,
    f.platform,
    f.initial_probability,
    f.current_probability,
    f.outcome,
    f.brier_score,
    f.log_score,
    f.revision_count,
    CASE
        WHEN f.current_probability >= 0.5 AND f.outcome = 1 THEN 'correct'
        WHEN f.current_probability < 0.5 AND f.outcome = 0 THEN 'correct'
        ELSE 'incorrect'
    END as direction_correct,
    f.resolution_date_actual,
    julianday(f.resolution_date_actual) - julianday(f.created_at) as days_to_resolution
FROM forecasts f
WHERE f.is_resolved = TRUE
ORDER BY f.resolution_date_actual DESC;


-- Revision history view
CREATE VIEW IF NOT EXISTS v_revision_timeline AS
SELECT
    br.forecast_id,
    f.question_short,
    br.revision_number,
    br.previous_probability,
    br.new_probability,
    br.probability_delta,
    br.update_magnitude,
    br.revision_trigger,
    br.market_price_at_revision,
    br.reasoning,
    br.revision_timestamp,
    f.outcome,
    CASE
        WHEN f.outcome IS NOT NULL THEN
            CASE
                WHEN (f.outcome = 1 AND br.probability_delta > 0) OR
                     (f.outcome = 0 AND br.probability_delta < 0) THEN 'toward_truth'
                WHEN br.probability_delta = 0 THEN 'no_change'
                ELSE 'away_from_truth'
            END
        ELSE 'pending'
    END as update_quality
FROM belief_revisions br
JOIN forecasts f ON br.forecast_id = f.forecast_id
ORDER BY br.revision_timestamp DESC;


-- Open positions summary
CREATE VIEW IF NOT EXISTS v_open_positions AS
SELECT
    p.position_uuid,
    f.question_short,
    p.platform,
    p.position_type,
    p.is_paper,
    p.entry_price,
    p.entry_quantity,
    p.entry_cost,
    p.current_price,
    p.unrealized_pnl,
    p.edge_at_entry,
    p.our_probability_at_entry,
    f.current_probability,
    f.resolution_date_expected,
    julianday(f.resolution_date_expected) - julianday('now') as days_until_resolution
FROM pm_positions p
JOIN forecasts f ON p.forecast_id = f.forecast_id
WHERE p.status = 'open'
ORDER BY f.resolution_date_expected ASC;


-- ==============================================================================
-- SAMPLE INSERT STATEMENTS
-- ==============================================================================

-- Example: Insert a reference class
/*
INSERT INTO reference_classes (
    class_name, class_category, class_description,
    base_rate, sample_size, sample_period_start, sample_period_end,
    base_rate_confidence, source_name, source_type,
    applicable_question_types
) VALUES (
    'US Presidential Incumbent Re-election',
    'elections',
    'Historical rate at which sitting US presidents win re-election',
    0.57,
    45,
    '1789-01-01',
    '2024-11-01',
    'high',
    'Wikipedia/Historical Election Data',
    'government_data',
    'elections,presidential,incumbency'
);
*/

-- Example: Insert a forecast
/*
INSERT INTO forecasts (
    forecast_id, question_text, question_short, question_category,
    platform, market_id, market_url,
    initial_probability, initial_confidence, initial_market_price,
    current_probability, current_confidence,
    resolution_date_expected, time_horizon_days,
    base_rate_used
) VALUES (
    'fc_2025_001',
    'Will the Federal Reserve cut interest rates by 50+ basis points in Q1 2025?',
    'Fed 50bp+ cut Q1 2025',
    'economics',
    'polymarket',
    'fed-rate-cut-q1-2025',
    'https://polymarket.com/event/fed-rate-cut-q1-2025',
    0.35,
    'medium',
    0.32,
    0.35,
    'medium',
    '2025-03-31',
    75,
    0.30
);
*/

-- Example: Insert a belief revision
/*
INSERT INTO belief_revisions (
    forecast_id, revision_number,
    previous_probability, new_probability,
    previous_confidence, new_confidence,
    market_price_at_revision, market_delta,
    revision_trigger, trigger_source, reasoning,
    evidence_quality, evidence_direction,
    days_since_creation, days_until_resolution
) VALUES (
    'fc_2025_001',
    1,
    0.35,
    0.42,
    'medium',
    'medium',
    0.38,
    0.06,
    'news_event',
    'https://reuters.com/fed-dovish-statement',
    'FOMC meeting showed dovish tilt, multiple members expressed concern about labor market',
    'strong',
    'bullish',
    5,
    70
);
*/

-- Example: Insert a position
/*
INSERT INTO pm_positions (
    position_uuid, forecast_id,
    platform, market_id, contract_id,
    position_type, is_paper,
    entry_price, entry_quantity, entry_cost, entry_timestamp,
    our_probability_at_entry, edge_at_entry,
    kelly_fraction_used, position_size_pct,
    status
) VALUES (
    'pos_2025_001',
    'fc_2025_001',
    'polymarket',
    'fed-rate-cut-q1-2025',
    'yes',
    'yes',
    TRUE,
    0.32,
    100,
    32.00,
    '2025-01-15 10:30:00',
    0.42,
    0.10,
    0.25,
    0.02,
    'open'
);
*/


-- ==============================================================================
-- SAMPLE ANALYTICAL QUERIES
-- ==============================================================================

-- -----------------------------------------------------------------------------
-- QUERY 1: Calculate Brier Score for a time period
-- -----------------------------------------------------------------------------
/*
SELECT
    COUNT(*) as n_forecasts,
    AVG(brier_score) as avg_brier_score,
    AVG(log_score) as avg_log_score,
    -- Comparison to baseline
    0.25 - AVG(brier_score) as improvement_vs_random,
    AVG(CASE WHEN brier_score < 0.25 THEN 1.0 ELSE 0.0 END) as pct_better_than_random
FROM forecasts
WHERE is_resolved = TRUE
    AND resolution_date_actual >= date('now', '-90 days');
*/


-- -----------------------------------------------------------------------------
-- QUERY 2: Generate Calibration Curve Data
-- -----------------------------------------------------------------------------
/*
SELECT
    CASE
        WHEN current_probability < 0.1 THEN '0-10%'
        WHEN current_probability < 0.2 THEN '10-20%'
        WHEN current_probability < 0.3 THEN '20-30%'
        WHEN current_probability < 0.4 THEN '30-40%'
        WHEN current_probability < 0.5 THEN '40-50%'
        WHEN current_probability < 0.6 THEN '50-60%'
        WHEN current_probability < 0.7 THEN '60-70%'
        WHEN current_probability < 0.8 THEN '70-80%'
        WHEN current_probability < 0.9 THEN '80-90%'
        ELSE '90-100%'
    END as probability_bin,
    COUNT(*) as n_forecasts,
    ROUND(AVG(current_probability), 3) as avg_forecast,
    ROUND(AVG(outcome), 3) as actual_frequency,
    ROUND(AVG(outcome) - AVG(current_probability), 3) as calibration_error
FROM forecasts
WHERE is_resolved = TRUE
GROUP BY probability_bin
ORDER BY MIN(current_probability);
*/


-- -----------------------------------------------------------------------------
-- QUERY 3: Track Belief Revision Patterns
-- -----------------------------------------------------------------------------
/*
-- Analyze update behavior and quality
SELECT
    revision_trigger,
    COUNT(*) as n_updates,
    ROUND(AVG(ABS(probability_delta)), 3) as avg_magnitude,
    ROUND(AVG(probability_delta), 3) as avg_direction,

    -- For resolved forecasts: did updates move toward truth?
    ROUND(AVG(CASE
        WHEN f.outcome = 1 AND br.probability_delta > 0 THEN 1
        WHEN f.outcome = 0 AND br.probability_delta < 0 THEN 1
        ELSE 0
    END), 3) as toward_truth_rate

FROM belief_revisions br
JOIN forecasts f ON br.forecast_id = f.forecast_id
WHERE f.is_resolved = TRUE
GROUP BY revision_trigger
ORDER BY n_updates DESC;
*/


-- -----------------------------------------------------------------------------
-- QUERY 4: Identify Overconfidence Patterns
-- -----------------------------------------------------------------------------
/*
-- Check if forecasts at extreme probabilities are properly calibrated
SELECT
    CASE
        WHEN current_probability >= 0.9 THEN 'Very Confident Yes (90%+)'
        WHEN current_probability <= 0.1 THEN 'Very Confident No (<10%)'
        WHEN current_probability >= 0.75 THEN 'Confident Yes (75-90%)'
        WHEN current_probability <= 0.25 THEN 'Confident No (10-25%)'
        ELSE 'Moderate (25-75%)'
    END as confidence_level,
    COUNT(*) as n_forecasts,
    ROUND(AVG(current_probability), 3) as avg_forecast,
    ROUND(AVG(outcome), 3) as actual_rate,
    ROUND(AVG(outcome) - AVG(current_probability), 3) as calibration_error,
    CASE
        WHEN AVG(outcome) < AVG(current_probability) THEN 'OVERCONFIDENT'
        WHEN AVG(outcome) > AVG(current_probability) THEN 'UNDERCONFIDENT'
        ELSE 'CALIBRATED'
    END as bias_direction
FROM forecasts
WHERE is_resolved = TRUE
GROUP BY confidence_level
ORDER BY AVG(current_probability) DESC;
*/


-- -----------------------------------------------------------------------------
-- QUERY 5: Position Performance by Platform
-- -----------------------------------------------------------------------------
/*
SELECT
    platform,
    is_paper,
    COUNT(*) as n_positions,
    SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_positions,
    SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed_positions,
    ROUND(SUM(realized_pnl), 2) as total_realized_pnl,
    ROUND(SUM(unrealized_pnl), 2) as total_unrealized_pnl,
    ROUND(AVG(roi) * 100, 2) as avg_roi_pct,
    ROUND(AVG(clv_equivalent), 4) as avg_clv
FROM pm_positions
GROUP BY platform, is_paper
ORDER BY platform, is_paper;
*/


-- -----------------------------------------------------------------------------
-- QUERY 6: Reference Class Usage Effectiveness
-- -----------------------------------------------------------------------------
/*
SELECT
    rc.class_name,
    rc.base_rate,
    COUNT(f.forecast_id) as times_used,
    ROUND(AVG(f.base_rate_used), 3) as avg_base_rate_used,
    ROUND(AVG(f.adjustment_from_base), 3) as avg_adjustment,
    ROUND(AVG(f.brier_score), 4) as avg_brier_when_used,
    ROUND(AVG(f.current_probability - f.base_rate_used), 3) as avg_deviation_from_base,

    -- Was adjusting from base rate beneficial?
    ROUND(AVG(CASE
        WHEN ABS(f.current_probability - f.outcome) < ABS(f.base_rate_used - f.outcome) THEN 1
        ELSE 0
    END), 3) as adjustment_helped_rate

FROM reference_classes rc
LEFT JOIN forecasts f ON f.reference_class_id = rc.id
WHERE f.is_resolved = TRUE
GROUP BY rc.id, rc.class_name, rc.base_rate
ORDER BY times_used DESC;
*/


-- ==============================================================================
-- TRIGGERS FOR AUTOMATIC UPDATES
-- ==============================================================================

-- Trigger: Update forecast's current_probability and revision_count on new revision
CREATE TRIGGER IF NOT EXISTS trg_update_forecast_on_revision
AFTER INSERT ON belief_revisions
BEGIN
    UPDATE forecasts
    SET
        current_probability = NEW.new_probability,
        current_confidence = NEW.new_confidence,
        revision_count = revision_count + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE forecast_id = NEW.forecast_id;
END;


-- Trigger: Calculate Brier and log scores on forecast resolution
CREATE TRIGGER IF NOT EXISTS trg_calculate_scores_on_resolution
AFTER UPDATE OF outcome ON forecasts
WHEN NEW.outcome IS NOT NULL AND OLD.outcome IS NULL
BEGIN
    UPDATE forecasts
    SET
        brier_score = (NEW.current_probability - NEW.outcome) * (NEW.current_probability - NEW.outcome),
        log_score = CASE
            WHEN NEW.outcome = 1 THEN
                CASE WHEN NEW.current_probability > 0.001 THEN -1 * LOG(NEW.current_probability) ELSE 6.9 END
            ELSE
                CASE WHEN NEW.current_probability < 0.999 THEN -1 * LOG(1 - NEW.current_probability) ELSE 6.9 END
        END,
        is_resolved = TRUE,
        resolution_date_actual = COALESCE(NEW.resolution_date_actual, DATE('now')),
        updated_at = CURRENT_TIMESTAMP
    WHERE forecast_id = NEW.forecast_id;
END;


-- Trigger: Update position P&L on price change
CREATE TRIGGER IF NOT EXISTS trg_update_position_pnl
AFTER UPDATE OF current_price ON pm_positions
WHEN NEW.status = 'open'
BEGIN
    UPDATE pm_positions
    SET
        unrealized_pnl = CASE
            WHEN NEW.position_type = 'yes' THEN (NEW.current_price - NEW.entry_price) * NEW.entry_quantity
            ELSE (NEW.entry_price - NEW.current_price) * NEW.entry_quantity
        END,
        total_pnl = COALESCE(NEW.realized_pnl, 0) +
            CASE
                WHEN NEW.position_type = 'yes' THEN (NEW.current_price - NEW.entry_price) * NEW.entry_quantity
                ELSE (NEW.entry_price - NEW.current_price) * NEW.entry_quantity
            END,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
END;


-- Trigger: Update reference class usage stats
CREATE TRIGGER IF NOT EXISTS trg_update_refclass_usage
AFTER INSERT ON forecasts
WHEN NEW.reference_class_id IS NOT NULL
BEGIN
    UPDATE reference_classes
    SET
        times_used = times_used + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.reference_class_id;
END;


-- ==============================================================================
-- SCHEMA VERSION TRACKING
-- ==============================================================================

-- Create schema_version if it doesn't exist (for standalone use)
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

INSERT OR IGNORE INTO schema_version (version, description)
VALUES (2, 'Superforecasting prediction market tracking schema');


-- ==============================================================================
-- END OF SCHEMA
-- ==============================================================================
