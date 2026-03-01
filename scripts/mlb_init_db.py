"""Initialize MLB data database (mlb_data.db).

Creates the mlb_data.db schema with all 14 tables and 1 view.
Safe to run multiple times (CREATE IF NOT EXISTS).

Tables:
    - teams: 30 MLB teams with stadium coordinates
    - players: cross-reference IDs (MLBAM, FanGraphs, BBRef)
    - games: game results with game_pk as primary key
    - pitcher_game_logs: per-start stats with Statcast metrics
    - pitcher_season_stats: rolling season stats with as_of_date
    - batter_season_stats: rolling batter stats with platoon splits
    - lineups: confirmed batting orders per game
    - weather: game-time weather conditions
    - park_factors: event-specific park factors by handedness
    - umpire_stats: home plate umpire tendencies
    - projections: ZiPS/Steamer preseason projections
    - bullpen_usage: reliever pitch counts and fatigue tracking
    - schema_version: migration tracking

Views:
    - v_bullpen_fatigue: rolling 3/7-day workload per reliever

Usage:
    python scripts/mlb_init_db.py
    python scripts/mlb_init_db.py --seed-teams   # populate 30 MLB teams

References:
    - Schema: docs/mlb/DATA_DICTIONARY.md
    - Design: docs/plans/2026-02-25-mlb-expansion-design.md
"""

import argparse
import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_DB_PATH = BASE_DIR / "data" / "mlb_data.db"

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version   INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 30 MLB teams with stadium info
CREATE TABLE IF NOT EXISTS teams (
    team_id        INTEGER PRIMARY KEY,   -- MLBAM team ID
    name           TEXT NOT NULL,
    abbreviation   TEXT NOT NULL,
    city           TEXT NOT NULL,
    stadium        TEXT NOT NULL,
    latitude       REAL,
    longitude      REAL,
    dome           INTEGER NOT NULL DEFAULT 0,   -- 1 = dome/retractable roof closed
    league         TEXT NOT NULL,               -- AL / NL
    division       TEXT NOT NULL,               -- East / Central / West
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Player cross-reference IDs
CREATE TABLE IF NOT EXISTS players (
    player_id      INTEGER PRIMARY KEY,   -- MLBAM ID
    full_name      TEXT NOT NULL,
    position       TEXT,                  -- SP, RP, 1B, SS, etc.
    bats           TEXT,                  -- L / R / S
    throws         TEXT,                  -- L / R
    fangraphs_id   TEXT,
    bbref_id       TEXT,
    retrosheet_id  TEXT,
    team_id        INTEGER REFERENCES teams(team_id),
    active         INTEGER NOT NULL DEFAULT 1,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Game results (game_pk is universal MLB identifier)
CREATE TABLE IF NOT EXISTS games (
    game_pk        INTEGER PRIMARY KEY,
    game_date      DATE NOT NULL,
    season         INTEGER NOT NULL,
    home_team_id   INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id   INTEGER NOT NULL REFERENCES teams(team_id),
    home_score     INTEGER,
    away_score     INTEGER,
    status         TEXT NOT NULL DEFAULT 'scheduled',  -- scheduled/final/postponed/cancelled
    home_starter_id INTEGER REFERENCES players(player_id),
    away_starter_id INTEGER REFERENCES players(player_id),
    venue          TEXT,
    game_time_utc  TIMESTAMP,
    attendance     INTEGER,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_games_date ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_season ON games(season);
CREATE INDEX IF NOT EXISTS idx_games_home_team ON games(home_team_id);
CREATE INDEX IF NOT EXISTS idx_games_away_team ON games(away_team_id);

-- Per-start pitcher stats with Statcast metrics
CREATE TABLE IF NOT EXISTS pitcher_game_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_pk         INTEGER NOT NULL REFERENCES games(game_pk),
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    is_starter      INTEGER NOT NULL DEFAULT 1,
    pitches         INTEGER,
    strikes         INTEGER,
    ip              REAL,              -- innings pitched (e.g. 6.2)
    hits            INTEGER,
    runs            INTEGER,
    earned_runs     INTEGER,
    walks           INTEGER,
    strikeouts      INTEGER,
    home_runs       INTEGER,
    -- Statcast metrics (from pybaseball/FanGraphs)
    avg_velo        REAL,             -- average fastball velo (mph)
    max_velo        REAL,
    stuff_plus      REAL,             -- stuff+ from FanGraphs (100 = avg)
    k_pct           REAL,             -- strikeout rate
    bb_pct          REAL,             -- walk rate
    xfip            REAL,             -- expected FIP
    siera           REAL,             -- SIERA
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_pk, player_id)
);

CREATE INDEX IF NOT EXISTS idx_pitcher_logs_player ON pitcher_game_logs(player_id);
CREATE INDEX IF NOT EXISTS idx_pitcher_logs_game ON pitcher_game_logs(game_pk);

-- Rolling season stats snapshot (as_of_date prevents look-ahead bias)
CREATE TABLE IF NOT EXISTS pitcher_season_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    season          INTEGER NOT NULL,
    as_of_date      DATE NOT NULL,
    games_started   INTEGER,
    ip              REAL,
    era             REAL,
    whip            REAL,
    k_per_9         REAL,
    bb_per_9        REAL,
    k_bb_pct        REAL,             -- (K% - BB%)
    hr_per_9        REAL,
    fip             REAL,
    xfip            REAL,
    siera           REAL,
    stuff_plus      REAL,
    avg_velo        REAL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_pitcher_season_player ON pitcher_season_stats(player_id, season);

-- Rolling batter stats with platoon splits
CREATE TABLE IF NOT EXISTS batter_season_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    season          INTEGER NOT NULL,
    as_of_date      DATE NOT NULL,
    split           TEXT NOT NULL DEFAULT 'overall',  -- overall / vs_lhp / vs_rhp
    pa              INTEGER,
    avg             REAL,
    obp             REAL,
    slg             REAL,
    ops             REAL,
    wrc_plus        REAL,             -- wRC+ (park/league adjusted)
    xwoba           REAL,             -- expected wOBA (Statcast)
    iso             REAL,             -- isolated power
    k_pct           REAL,
    bb_pct          REAL,
    hard_hit_pct    REAL,             -- Statcast hard-hit%
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season, as_of_date, split)
);

CREATE INDEX IF NOT EXISTS idx_batter_season_player ON batter_season_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_batter_season_team ON batter_season_stats(team_id, season, as_of_date);

-- Confirmed batting orders (9 rows per team per game = 18 rows per game)
CREATE TABLE IF NOT EXISTS lineups (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_pk         INTEGER NOT NULL REFERENCES games(game_pk),
    team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    batting_order   INTEGER NOT NULL,   -- 1-9
    position        TEXT,               -- 1B, SS, etc. (fielding position)
    confirmed       INTEGER NOT NULL DEFAULT 0,  -- 1 = official lineup card
    confirmed_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_pk, team_id, batting_order)
);

CREATE INDEX IF NOT EXISTS idx_lineups_game ON lineups(game_pk, team_id);

-- Game-time weather conditions (outdoor games only; dome=NULL)
CREATE TABLE IF NOT EXISTS weather (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_pk         INTEGER NOT NULL REFERENCES games(game_pk) UNIQUE,
    temperature_f   REAL,
    humidity_pct    REAL,
    wind_speed_mph  REAL,
    wind_dir_deg    REAL,             -- 0=N, 90=E, 180=S, 270=W
    wind_to_cf      REAL,             -- component toward CF (positive = out)
    precipitation   REAL,             -- mm
    dome            INTEGER NOT NULL DEFAULT 0,
    source          TEXT,             -- open-meteo / manual
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Event-specific park factors by handedness
CREATE TABLE IF NOT EXISTS park_factors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    season          INTEGER NOT NULL,
    bats            TEXT NOT NULL DEFAULT 'overall',  -- overall / L / R
    pf_hr           REAL NOT NULL DEFAULT 1.0,
    pf_1b           REAL NOT NULL DEFAULT 1.0,
    pf_2b           REAL NOT NULL DEFAULT 1.0,
    pf_3b           REAL NOT NULL DEFAULT 1.0,
    pf_bb           REAL NOT NULL DEFAULT 1.0,
    pf_k            REAL NOT NULL DEFAULT 1.0,
    pf_runs         REAL NOT NULL DEFAULT 1.0,
    source          TEXT,             -- fangraphs / computed
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, season, bats)
);

-- HP umpire tendencies per season
CREATE TABLE IF NOT EXISTS umpire_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    umpire_name     TEXT NOT NULL,
    season          INTEGER NOT NULL,
    as_of_date      DATE NOT NULL,
    games           INTEGER,
    k_per_game      REAL,             -- strikeouts called per game (both teams)
    bb_per_game     REAL,
    run_impact      REAL,             -- runs above/below average per game
    zone_size_pct   REAL,             -- called strikes outside true zone (%)
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(umpire_name, season, as_of_date)
);

-- ZiPS / Steamer preseason projections
CREATE TABLE IF NOT EXISTS projections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    season          INTEGER NOT NULL,
    system          TEXT NOT NULL,    -- ZiPS / Steamer / Marcel
    player_type     TEXT NOT NULL,    -- pitcher / batter
    -- Pitcher projections
    proj_era        REAL,
    proj_fip        REAL,
    proj_ip         REAL,
    proj_k_pct      REAL,
    proj_bb_pct     REAL,
    proj_hr_per_9   REAL,
    -- Batter projections
    proj_pa         INTEGER,
    proj_avg        REAL,
    proj_obp        REAL,
    proj_slg        REAL,
    proj_wrc_plus   REAL,
    proj_iso        REAL,
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_id, season, system)
);

CREATE INDEX IF NOT EXISTS idx_projections_player ON projections(player_id, season);

-- Reliever pitch counts and fatigue tracking
CREATE TABLE IF NOT EXISTS bullpen_usage (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    game_pk         INTEGER NOT NULL REFERENCES games(game_pk),
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    pitches         INTEGER NOT NULL DEFAULT 0,
    outs_recorded   INTEGER NOT NULL DEFAULT 0,
    inherited_runners INTEGER NOT NULL DEFAULT 0,
    game_date       DATE NOT NULL,   -- denormalized for fast range queries
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_pk, player_id)
);

CREATE INDEX IF NOT EXISTS idx_bullpen_player_date ON bullpen_usage(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_bullpen_team_date ON bullpen_usage(team_id, game_date);

-- Historical odds from ESPN Core API
CREATE TABLE IF NOT EXISTS odds (
    game_pk         INTEGER NOT NULL REFERENCES games(game_pk),
    provider        TEXT NOT NULL,
    home_ml_open    INTEGER,
    away_ml_open    INTEGER,
    home_ml_close   INTEGER,
    away_ml_close   INTEGER,
    total_open      REAL,
    total_close     REAL,
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_pk, provider)
);
CREATE INDEX IF NOT EXISTS idx_odds_game ON odds(game_pk);
"""

VIEW_SQL = """
CREATE VIEW IF NOT EXISTS v_bullpen_fatigue AS
SELECT
    bu.player_id,
    bu.team_id,
    bu.game_date,
    (SELECT COALESCE(SUM(b2.pitches), 0)
     FROM bullpen_usage b2
     WHERE b2.player_id = bu.player_id
       AND b2.game_date > date(bu.game_date, '-3 days')
       AND b2.game_date <= bu.game_date) AS pitches_last_3d,
    (SELECT COALESCE(SUM(b2.pitches), 0)
     FROM bullpen_usage b2
     WHERE b2.player_id = bu.player_id
       AND b2.game_date > date(bu.game_date, '-7 days')
       AND b2.game_date <= bu.game_date) AS pitches_last_7d
FROM bullpen_usage bu;
"""

# ---------------------------------------------------------------------------
# 30 MLB Teams seed data (MLBAM IDs, 2026 rosters)
# ---------------------------------------------------------------------------

TEAMS_SEED = [
    # (team_id, name, abbreviation, city, stadium, latitude, longitude, dome, league, division)
    (
        108,
        "Los Angeles Angels",
        "LAA",
        "Anaheim",
        "Angel Stadium",
        33.8003,
        -117.8827,
        0,
        "AL",
        "West",
    ),
    (
        109,
        "Arizona Diamondbacks",
        "ARI",
        "Phoenix",
        "Chase Field",
        33.4453,
        -112.0667,
        1,
        "NL",
        "West",
    ),
    (
        110,
        "Baltimore Orioles",
        "BAL",
        "Baltimore",
        "Oriole Park at Camden Yards",
        39.2839,
        -76.6216,
        0,
        "AL",
        "East",
    ),
    (111, "Boston Red Sox", "BOS", "Boston", "Fenway Park", 42.3467, -71.0972, 0, "AL", "East"),
    (112, "Chicago Cubs", "CHC", "Chicago", "Wrigley Field", 41.9484, -87.6553, 0, "NL", "Central"),
    (
        113,
        "Cincinnati Reds",
        "CIN",
        "Cincinnati",
        "Great American Ball Park",
        39.0979,
        -84.5082,
        0,
        "NL",
        "Central",
    ),
    (
        114,
        "Cleveland Guardians",
        "CLE",
        "Cleveland",
        "Progressive Field",
        41.4962,
        -81.6852,
        0,
        "AL",
        "Central",
    ),
    (115, "Colorado Rockies", "COL", "Denver", "Coors Field", 39.7559, -104.9942, 0, "NL", "West"),
    (
        116,
        "Detroit Tigers",
        "DET",
        "Detroit",
        "Comerica Park",
        42.3390,
        -83.0485,
        0,
        "AL",
        "Central",
    ),
    (
        117,
        "Houston Astros",
        "HOU",
        "Houston",
        "Minute Maid Park",
        29.7573,
        -95.3555,
        1,
        "AL",
        "West",
    ),
    (
        118,
        "Kansas City Royals",
        "KC",
        "Kansas City",
        "Kauffman Stadium",
        39.0517,
        -94.4803,
        0,
        "AL",
        "Central",
    ),
    (
        119,
        "Los Angeles Dodgers",
        "LAD",
        "Los Angeles",
        "Dodger Stadium",
        34.0739,
        -118.2400,
        0,
        "NL",
        "West",
    ),
    (
        120,
        "Washington Nationals",
        "WSH",
        "Washington",
        "Nationals Park",
        38.8730,
        -77.0074,
        0,
        "NL",
        "East",
    ),
    (121, "New York Mets", "NYM", "New York", "Citi Field", 40.7571, -73.8458, 0, "NL", "East"),
    (
        133,
        "Oakland Athletics",
        "OAK",
        "Sacramento",
        "Sutter Health Park",
        38.5766,
        -121.5083,
        0,
        "AL",
        "West",
    ),
    (
        134,
        "Pittsburgh Pirates",
        "PIT",
        "Pittsburgh",
        "PNC Park",
        40.4468,
        -80.0057,
        0,
        "NL",
        "Central",
    ),
    (135, "San Diego Padres", "SD", "San Diego", "Petco Park", 32.7073, -117.1566, 0, "NL", "West"),
    (
        136,
        "Seattle Mariners",
        "SEA",
        "Seattle",
        "T-Mobile Park",
        47.5914,
        -122.3325,
        1,
        "AL",
        "West",
    ),
    (
        137,
        "San Francisco Giants",
        "SF",
        "San Francisco",
        "Oracle Park",
        37.7786,
        -122.3893,
        0,
        "NL",
        "West",
    ),
    (
        138,
        "St. Louis Cardinals",
        "STL",
        "St. Louis",
        "Busch Stadium",
        38.6226,
        -90.1928,
        0,
        "NL",
        "Central",
    ),
    (
        139,
        "Tampa Bay Rays",
        "TB",
        "St. Petersburg",
        "Tropicana Field",
        27.7683,
        -82.6534,
        1,
        "AL",
        "East",
    ),
    (
        140,
        "Texas Rangers",
        "TEX",
        "Arlington",
        "Globe Life Field",
        32.7473,
        -97.0823,
        1,
        "AL",
        "West",
    ),
    (
        141,
        "Toronto Blue Jays",
        "TOR",
        "Toronto",
        "Rogers Centre",
        43.6414,
        -79.3894,
        1,
        "AL",
        "East",
    ),
    (
        142,
        "Minnesota Twins",
        "MIN",
        "Minneapolis",
        "Target Field",
        44.9817,
        -93.2776,
        0,
        "AL",
        "Central",
    ),
    (
        143,
        "Philadelphia Phillies",
        "PHI",
        "Philadelphia",
        "Citizens Bank Park",
        39.9057,
        -75.1665,
        0,
        "NL",
        "East",
    ),
    (144, "Atlanta Braves", "ATL", "Cumberland", "Truist Park", 33.8907, -84.4678, 0, "NL", "East"),
    (
        145,
        "Chicago White Sox",
        "CWS",
        "Chicago",
        "Guaranteed Rate Field",
        41.8300,
        -87.6339,
        0,
        "AL",
        "Central",
    ),
    (146, "Miami Marlins", "MIA", "Miami", "loanDepot park", 25.7781, -80.2197, 1, "NL", "East"),
    (
        147,
        "New York Yankees",
        "NYY",
        "New York",
        "Yankee Stadium",
        40.8296,
        -73.9262,
        0,
        "AL",
        "East",
    ),
    (
        158,
        "Milwaukee Brewers",
        "MIL",
        "Milwaukee",
        "American Family Field",
        43.0280,
        -87.9712,
        1,
        "NL",
        "Central",
    ),
]

# Default park factors (neutral 1.0) — override with FanGraphs data after seeding
PARK_FACTORS_SEED = [
    (team_id, season, bats, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, "default")
    for team_id, *_ in TEAMS_SEED
    for season in (2023, 2024, 2025, 2026)
    for bats in ("overall", "L", "R")
]


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


@contextmanager
def get_cursor(db_path: Path):
    """Context manager for SQLite cursor with auto-commit/rollback."""
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def init_schema(db_path: Path) -> None:
    """Create all tables and views (idempotent)."""
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        # executescript() handles multi-statement DDL correctly
        conn.executescript(SCHEMA_SQL + "\n" + VIEW_SQL)
        # Record schema version separately (after executescript commits)
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        conn.commit()
    finally:
        conn.close()
    logger.info("Schema initialized (version %d)", SCHEMA_VERSION)


def seed_teams(db_path: Path) -> int:
    """Insert 30 MLB teams (INSERT OR IGNORE — safe to re-run)."""
    with get_cursor(db_path) as cur:
        cur.executemany(
            """INSERT OR IGNORE INTO teams
               (team_id, name, abbreviation, city, stadium, latitude, longitude,
                dome, league, division)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            TEAMS_SEED,
        )
        count = cur.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    logger.info("Teams table: %d rows", count)
    return count


def seed_park_factors(db_path: Path) -> int:
    """Insert neutral park factors for all 30 teams × 4 seasons × 3 splits."""
    with get_cursor(db_path) as cur:
        cur.executemany(
            """INSERT OR IGNORE INTO park_factors
               (team_id, season, bats, pf_hr, pf_1b, pf_2b, pf_3b, pf_bb, pf_k,
                pf_runs, source)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            PARK_FACTORS_SEED,
        )
        count = cur.execute("SELECT COUNT(*) FROM park_factors").fetchone()[0]
    logger.info("Park factors table: %d rows", count)
    return count


def verify_schema(db_path: Path) -> dict:
    """Return table row counts for quick sanity check."""
    tables = [
        "schema_version",
        "teams",
        "players",
        "games",
        "pitcher_game_logs",
        "pitcher_season_stats",
        "batter_season_stats",
        "lineups",
        "weather",
        "park_factors",
        "umpire_stats",
        "projections",
        "bullpen_usage",
    ]
    counts = {}
    with get_cursor(db_path) as cur:
        for table in tables:
            sql = f"SELECT COUNT(*) FROM {table}"  # noqa: S608 # nosec B608
            counts[table] = cur.execute(sql).fetchone()[0]
    return counts


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for mlb_init_db."""
    parser = argparse.ArgumentParser(description="Initialize mlb_data.db schema")
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to mlb_data.db (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--seed-teams",
        action="store_true",
        help="Populate teams + park_factors with default data",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Print table row counts and exit",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Database: %s", db_path)

    init_schema(db_path)

    if args.seed_teams:
        seed_teams(db_path)
        seed_park_factors(db_path)

    if args.verify or args.seed_teams:
        counts = verify_schema(db_path)
        print("\nTable row counts:")
        for table, n in counts.items():
            print(f"  {table:<30} {n:>6}")

    logger.info("Done.")


if __name__ == "__main__":
    main()
