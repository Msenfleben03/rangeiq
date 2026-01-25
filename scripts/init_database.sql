-- Sports Betting Model Development - Database Schema
-- SQLite Database Initialization Script
-- Run: sqlite3 data/betting.db < scripts/init_database.sql

-- =============================================================================
-- PRAGMA SETTINGS
-- =============================================================================
PRAGMA journal_mode=WAL;  -- Better concurrent access
PRAGMA foreign_keys=ON;   -- Enforce referential integrity

-- =============================================================================
-- CORE TABLES
-- =============================================================================

-- Teams reference table
CREATE TABLE IF NOT EXISTS teams (
    team_id TEXT PRIMARY KEY,
    sport TEXT NOT NULL,  -- 'NCAAB', 'MLB', 'NFL', 'NCAAF'
    team_name TEXT NOT NULL,
    team_abbrev TEXT,
    conference TEXT,
    division TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_teams_sport ON teams(sport);
CREATE INDEX IF NOT EXISTS idx_teams_conference ON teams(conference);

-- Games table
CREATE TABLE IF NOT EXISTS games (
    game_id TEXT PRIMARY KEY,
    sport TEXT NOT NULL,
    season INTEGER NOT NULL,
    game_date DATE NOT NULL,
    game_time TIMESTAMP,  -- UTC

    -- Teams
    home_team_id TEXT NOT NULL,
    away_team_id TEXT NOT NULL,

    -- Location
    venue TEXT,
    is_neutral_site BOOLEAN DEFAULT FALSE,

    -- Game type
    is_postseason BOOLEAN DEFAULT FALSE,
    game_type TEXT,  -- 'regular', 'conference_tourney', 'ncaa_tourney', 'playoff', etc.

    -- Results (filled after game)
    home_score INTEGER,
    away_score INTEGER,
    is_final BOOLEAN DEFAULT FALSE,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
);

CREATE INDEX IF NOT EXISTS idx_games_sport_date ON games(sport, game_date);
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);
CREATE INDEX IF NOT EXISTS idx_games_home_team ON games(home_team_id);
CREATE INDEX IF NOT EXISTS idx_games_away_team ON games(away_team_id);

-- =============================================================================
-- BETTING LINES
-- =============================================================================

-- Odds snapshots (track line movements)
CREATE TABLE IF NOT EXISTS odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    sportsbook TEXT NOT NULL,
    captured_at TIMESTAMP NOT NULL,

    -- Spread
    spread_home REAL,
    spread_home_odds INTEGER,  -- American odds
    spread_away_odds INTEGER,

    -- Total
    total REAL,
    over_odds INTEGER,
    under_odds INTEGER,

    -- Moneyline
    moneyline_home INTEGER,
    moneyline_away INTEGER,

    -- Is this the closing line?
    is_closing BOOLEAN DEFAULT FALSE,

    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

CREATE INDEX IF NOT EXISTS idx_odds_game ON odds_snapshots(game_id);
CREATE INDEX IF NOT EXISTS idx_odds_captured ON odds_snapshots(captured_at);
CREATE INDEX IF NOT EXISTS idx_odds_closing ON odds_snapshots(is_closing);

-- =============================================================================
-- TEAM RATINGS
-- =============================================================================

CREATE TABLE IF NOT EXISTS team_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    sport TEXT NOT NULL,
    season INTEGER NOT NULL,

    -- Rating details
    rating_type TEXT NOT NULL,  -- 'elo', 'efficiency_off', 'efficiency_def', 'power', etc.
    rating_value REAL NOT NULL,

    -- When this rating was calculated
    as_of_date DATE NOT NULL,
    as_of_game_id TEXT,  -- Last game included in this rating

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    FOREIGN KEY (as_of_game_id) REFERENCES games(game_id),

    UNIQUE(team_id, season, rating_type, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_ratings_team_season ON team_ratings(team_id, season);
CREATE INDEX IF NOT EXISTS idx_ratings_type ON team_ratings(rating_type);
CREATE INDEX IF NOT EXISTS idx_ratings_date ON team_ratings(as_of_date);

-- =============================================================================
-- MODEL PREDICTIONS
-- =============================================================================

CREATE TABLE IF NOT EXISTS predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,

    -- Prediction details
    prediction_type TEXT NOT NULL,  -- 'spread', 'total', 'moneyline', 'home_win_prob'
    predicted_value REAL NOT NULL,
    confidence REAL,  -- 0-1, if available

    -- Market comparison (at time of prediction)
    market_value REAL,
    market_timestamp TIMESTAMP,

    -- For tracking
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (game_id) REFERENCES games(game_id),

    UNIQUE(game_id, model_name, model_version, prediction_type)
);

CREATE INDEX IF NOT EXISTS idx_predictions_game ON predictions(game_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions(model_name, model_version);

-- =============================================================================
-- BETS TRACKING
-- =============================================================================

CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Identification
    bet_uuid TEXT UNIQUE NOT NULL,  -- UUID for external reference
    game_id TEXT,
    sport TEXT NOT NULL,

    -- Bet details
    bet_type TEXT NOT NULL,  -- 'spread', 'total', 'moneyline', 'prop', 'f5_spread', 'f5_total', etc.
    selection TEXT NOT NULL,  -- 'home', 'away', 'over', 'under', or player name for props
    line REAL,  -- Spread or total number (NULL for ML)

    -- Odds
    odds_placed INTEGER NOT NULL,  -- American odds when bet was placed
    odds_closing INTEGER,  -- American odds at close (filled later)

    -- Model data
    model_name TEXT,
    model_version TEXT,
    model_probability REAL,  -- Our estimated win probability
    model_edge REAL,  -- model_prob - implied_prob

    -- Sizing
    kelly_recommended REAL,  -- What Kelly suggested
    stake REAL NOT NULL,  -- What we actually bet
    potential_profit REAL,  -- Stake * (decimal_odds - 1)

    -- Execution
    sportsbook TEXT NOT NULL,
    placed_at TIMESTAMP NOT NULL,

    -- Results (filled after game)
    result TEXT,  -- 'win', 'loss', 'push', 'void'
    actual_profit_loss REAL,
    clv REAL,  -- Closing line value
    settled_at TIMESTAMP,

    -- Categorization
    is_live BOOLEAN DEFAULT FALSE,  -- FALSE = paper bet, TRUE = real money
    is_settled BOOLEAN DEFAULT FALSE,

    -- Notes
    notes TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

CREATE INDEX IF NOT EXISTS idx_bets_game ON bets(game_id);
CREATE INDEX IF NOT EXISTS idx_bets_sport ON bets(sport);
CREATE INDEX IF NOT EXISTS idx_bets_type ON bets(bet_type);
CREATE INDEX IF NOT EXISTS idx_bets_sportsbook ON bets(sportsbook);
CREATE INDEX IF NOT EXISTS idx_bets_placed ON bets(placed_at);
CREATE INDEX IF NOT EXISTS idx_bets_settled ON bets(is_settled);
CREATE INDEX IF NOT EXISTS idx_bets_live ON bets(is_live);

-- =============================================================================
-- BANKROLL TRACKING
-- =============================================================================

CREATE TABLE IF NOT EXISTS bankroll_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL UNIQUE,

    -- Balances
    starting_balance REAL NOT NULL,
    ending_balance REAL NOT NULL,

    -- Daily activity
    deposits REAL DEFAULT 0,
    withdrawals REAL DEFAULT 0,

    -- Betting activity
    total_staked REAL DEFAULT 0,
    total_returned REAL DEFAULT 0,
    net_profit_loss REAL DEFAULT 0,

    -- Bet counts
    bets_placed INTEGER DEFAULT 0,
    bets_settled INTEGER DEFAULT 0,
    bets_won INTEGER DEFAULT 0,
    bets_lost INTEGER DEFAULT 0,
    bets_pushed INTEGER DEFAULT 0,

    -- Performance metrics
    win_rate REAL,
    roi REAL,
    avg_clv REAL,

    -- Metadata
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_bankroll_date ON bankroll_daily(date);

-- Sportsbook-specific balances
CREATE TABLE IF NOT EXISTS sportsbook_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    sportsbook TEXT NOT NULL,
    balance REAL NOT NULL,

    -- Activity
    deposits REAL DEFAULT 0,
    withdrawals REAL DEFAULT 0,
    bonuses REAL DEFAULT 0,

    -- Status
    is_limited BOOLEAN DEFAULT FALSE,
    limit_notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(date, sportsbook)
);

CREATE INDEX IF NOT EXISTS idx_sb_balances_date ON sportsbook_balances(date);
CREATE INDEX IF NOT EXISTS idx_sb_balances_book ON sportsbook_balances(sportsbook);

-- =============================================================================
-- MODEL METADATA
-- =============================================================================

CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name TEXT NOT NULL,
    model_version TEXT NOT NULL,
    sport TEXT NOT NULL,

    -- Description
    description TEXT,
    model_type TEXT,  -- 'elo', 'regression', 'ensemble', 'neural_net', etc.

    -- Configuration (JSON)
    config_json TEXT,

    -- Backtest results
    backtest_start_date DATE,
    backtest_end_date DATE,
    backtest_n_bets INTEGER,
    backtest_clv REAL,
    backtest_roi REAL,

    -- Status
    status TEXT DEFAULT 'development',  -- 'development', 'paper', 'live', 'retired'
    deployed_at TIMESTAMP,
    retired_at TIMESTAMP,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(model_name, model_version)
);

CREATE INDEX IF NOT EXISTS idx_models_sport ON models(sport);
CREATE INDEX IF NOT EXISTS idx_models_status ON models(status);

-- =============================================================================
-- FEATURES STORE (for tracking engineered features)
-- =============================================================================

CREATE TABLE IF NOT EXISTS features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    feature_set_version TEXT NOT NULL,  -- Version of feature engineering code

    -- Store features as JSON for flexibility
    features_json TEXT NOT NULL,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (game_id) REFERENCES games(game_id),

    UNIQUE(game_id, feature_set_version)
);

CREATE INDEX IF NOT EXISTS idx_features_game ON features(game_id);

-- =============================================================================
-- PLAYER PROPS (separate table due to different structure)
-- =============================================================================

CREATE TABLE IF NOT EXISTS player_props (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    player_team TEXT,

    -- Prop details
    prop_type TEXT NOT NULL,  -- 'strikeouts', 'hits', 'total_bases', 'passing_yards', etc.
    line REAL NOT NULL,

    -- Odds
    over_odds INTEGER,
    under_odds INTEGER,

    -- Our prediction
    model_prediction REAL,
    over_probability REAL,
    under_probability REAL,

    -- Result
    actual_value REAL,

    -- Metadata
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_closing BOOLEAN DEFAULT FALSE,

    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

CREATE INDEX IF NOT EXISTS idx_props_game ON player_props(game_id);
CREATE INDEX IF NOT EXISTS idx_props_player ON player_props(player_name);
CREATE INDEX IF NOT EXISTS idx_props_type ON player_props(prop_type);

-- =============================================================================
-- AUDIT LOG
-- =============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    action TEXT NOT NULL,  -- 'INSERT', 'UPDATE', 'DELETE'
    old_values TEXT,  -- JSON
    new_values TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_table ON audit_log(table_name);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);

-- =============================================================================
-- VIEWS
-- =============================================================================

-- Active bets view
CREATE VIEW IF NOT EXISTS v_active_bets AS
SELECT
    b.*,
    g.game_date,
    g.home_team_id,
    g.away_team_id,
    g.home_score,
    g.away_score,
    g.is_final
FROM bets b
LEFT JOIN games g ON b.game_id = g.game_id
WHERE b.is_settled = FALSE;

-- Performance summary by model
CREATE VIEW IF NOT EXISTS v_model_performance AS
SELECT
    model_name,
    model_version,
    sport,
    is_live,
    COUNT(*) as total_bets,
    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
    SUM(CASE WHEN result = 'push' THEN 1 ELSE 0 END) as pushes,
    ROUND(AVG(CASE WHEN result IN ('win', 'loss') THEN
        CASE WHEN result = 'win' THEN 1.0 ELSE 0.0 END
    END) * 100, 2) as win_rate,
    ROUND(SUM(actual_profit_loss), 2) as total_pnl,
    ROUND(SUM(actual_profit_loss) / SUM(stake) * 100, 2) as roi,
    ROUND(AVG(clv) * 100, 3) as avg_clv_pct
FROM bets
WHERE is_settled = TRUE
GROUP BY model_name, model_version, sport, is_live;

-- Daily P&L view
CREATE VIEW IF NOT EXISTS v_daily_pnl AS
SELECT
    DATE(settled_at) as date,
    sport,
    is_live,
    COUNT(*) as bets_settled,
    SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
    ROUND(SUM(actual_profit_loss), 2) as daily_pnl,
    ROUND(AVG(clv) * 100, 3) as avg_clv_pct
FROM bets
WHERE is_settled = TRUE AND settled_at IS NOT NULL
GROUP BY DATE(settled_at), sport, is_live
ORDER BY date DESC;

-- =============================================================================
-- INITIAL DATA
-- =============================================================================

-- Insert common sportsbooks
INSERT OR IGNORE INTO sportsbook_balances (date, sportsbook, balance) VALUES
    (DATE('now'), 'draftkings', 0),
    (DATE('now'), 'fanduel', 0),
    (DATE('now'), 'betmgm', 0),
    (DATE('now'), 'caesars', 0),
    (DATE('now'), 'espn_bet', 0);

-- =============================================================================
-- DONE
-- =============================================================================
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

INSERT INTO schema_version (version, description) VALUES (1, 'Initial schema');
