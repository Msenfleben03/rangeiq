"""Sports Betting Database Management.

Handles SQLite database creation, connection, and schema management
for tracking bets, predictions, and team ratings.
"""

import sqlite3
from pathlib import Path
from typing import Optional
from contextlib import contextmanager
import logging

# Configure logging
logger = logging.getLogger(__name__)


class BettingDatabase:
    """Manages SQLite database for sports betting tracking.

    Handles connection pooling, schema creation, and provides
    context managers for safe transaction handling.
    """

    def __init__(self, db_path: str = "data/betting.db"):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Create database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def get_cursor(self):
        """Context manager for database operations.

        Yields:
            sqlite3.Cursor: Database cursor

        Example:
            with db.get_cursor() as cursor:
                cursor.execute("SELECT * FROM bets")
                results = cursor.fetchall()
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def _initialize_schema(self):
        """Create database tables if they don't exist."""
        with self.get_cursor() as cursor:
            # Core bet tracking table
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS bets (
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
                )
            """
            )

            # Bankroll tracking table
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS bankroll_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL UNIQUE,
                    starting_balance REAL,
                    ending_balance REAL,
                    daily_pnl REAL,
                    bets_placed INTEGER,
                    bets_won INTEGER,
                    bets_lost INTEGER,
                    avg_clv REAL
                )
            """
            )

            # Model predictions table
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS predictions (
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
                )
            """
            )

            # Team ratings table
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS team_ratings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sport TEXT NOT NULL,
                    team_id TEXT NOT NULL,
                    team_name TEXT NOT NULL,
                    season INTEGER NOT NULL,
                    rating_type TEXT NOT NULL,
                    rating_value REAL NOT NULL,

                    UNIQUE(sport, team_id, season, rating_type)
                )
            """
            )

            # Odds snapshots table
            cursor.execute(
                """CREATE TABLE IF NOT EXISTS odds_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT NOT NULL,
                    sportsbook TEXT NOT NULL,
                    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    spread_home REAL,
                    spread_home_odds INTEGER,
                    spread_away_odds INTEGER,
                    total REAL,
                    over_odds INTEGER,
                    under_odds INTEGER,
                    moneyline_home INTEGER,
                    moneyline_away INTEGER,
                    is_closing BOOLEAN DEFAULT FALSE,
                    confidence REAL DEFAULT 1.0,
                    snapshot_type TEXT DEFAULT 'current'
                )
            """
            )

            # Migration: add snapshot_type column if missing
            try:
                cursor.execute(
                    "ALTER TABLE odds_snapshots ADD COLUMN snapshot_type TEXT DEFAULT 'current'"
                )
                logger.info("Added snapshot_type column to odds_snapshots")
            except Exception:
                pass  # Column already exists

            # Backfill existing rows without snapshot_type
            cursor.execute(
                "UPDATE odds_snapshots SET snapshot_type = 'current' WHERE snapshot_type IS NULL"
            )

            logger.info(f"Database initialized at {self.db_path}")

    def execute_query(self, query: str, params: Optional[tuple] = None):
        """Execute a SQL query.

        Args:
            query: SQL query string
            params: Query parameters (optional)

        Returns:
            List of results
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()

    def insert_bet(self, bet_data: dict) -> int:
        """Insert a new bet record.

        Args:
            bet_data: Dictionary containing bet information

        Returns:
            ID of inserted bet, or -1 if duplicate (IntegrityError).
        """
        columns = ", ".join(bet_data.keys())
        placeholders = ", ".join(["?" for _ in bet_data])
        query = f"INSERT INTO bets ({columns}) VALUES ({placeholders})"  # nosec B608

        try:
            with self.get_cursor() as cursor:
                cursor.execute(query, tuple(bet_data.values()))
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning("Duplicate bet skipped: %s", bet_data.get("game_id", "unknown"))
            return -1

    def update_bet_result(
        self, bet_id: int, result: str, profit_loss: float, clv: Optional[float] = None
    ):
        """Update bet result after game completion.

        Args:
            bet_id: Bet ID
            result: Outcome ('win', 'loss', 'push')
            profit_loss: Profit or loss amount
            clv: Closing line value (optional)
        """
        query = """UPDATE bets
            SET result = ?, profit_loss = ?, clv = ?
            WHERE id = ?
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, (result, profit_loss, clv, bet_id))

    def get_active_bets(self, sport: Optional[str] = None) -> list:
        """Get all bets without results.

        Args:
            sport: Filter by sport (optional)

        Returns:
            List of active bets
        """
        query = "SELECT * FROM bets WHERE result IS NULL"
        params = ()

        if sport:
            query += " AND sport = ?"
            params = (sport,)

        return self.execute_query(query, params)

    def get_performance_stats(self, sport: Optional[str] = None, days: int = 30) -> dict:
        """Calculate performance statistics.

        Args:
            sport: Filter by sport (optional)
            days: Number of days to analyze

        Returns:
            Dictionary of performance metrics
        """
        query = """SELECT
                COUNT(*) as total_bets,
                SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(profit_loss) as total_pnl,
                AVG(clv) as avg_clv,
                AVG(stake) as avg_stake
            FROM bets
            WHERE result IS NOT NULL
            AND created_at >= date('now', '-' || ? || ' days')
        """
        params = [days]

        if sport:
            query += " AND sport = ?"
            params.append(sport)

        result = self.execute_query(query, tuple(params))
        if result and len(result) > 0:
            row = result[0]
            total = row["total_bets"] or 0
            wins = row["wins"] or 0

            return {
                "total_bets": total,
                "wins": wins,
                "losses": row["losses"] or 0,
                "win_rate": wins / total if total > 0 else 0,
                "total_pnl": row["total_pnl"] or 0,
                "avg_clv": row["avg_clv"] or 0,
                "avg_stake": row["avg_stake"] or 0,
                "roi": (row["total_pnl"] / (row["avg_stake"] * total))
                if (row["avg_stake"] and total > 0)
                else 0,
            }

        return {}

    def insert_prediction(self, prediction_data: dict) -> int:
        """Insert a model prediction.

        Args:
            prediction_data: Dict with sport, game_id, game_date, model_name,
                prediction_type, predicted_value. Optional: market_value, closing_value.

        Returns:
            ID of inserted prediction.
        """
        columns = ", ".join(prediction_data.keys())
        placeholders = ", ".join(["?" for _ in prediction_data])
        query = f"INSERT OR REPLACE INTO predictions ({columns}) VALUES ({placeholders})"

        with self.get_cursor() as cursor:
            cursor.execute(query, tuple(prediction_data.values()))
            return cursor.lastrowid

    def get_predictions_by_date(self, game_date: str, sport: Optional[str] = None) -> list:
        """Get predictions for a specific date.

        Args:
            game_date: Date string (YYYY-MM-DD).
            sport: Optional sport filter.

        Returns:
            List of prediction records.
        """
        query = "SELECT * FROM predictions WHERE game_date = ?"
        params: list = [game_date]
        if sport:
            query += " AND sport = ?"
            params.append(sport)
        return self.execute_query(query, tuple(params))

    def insert_odds_snapshot(self, odds_data: dict) -> int:
        """Insert an odds snapshot.

        Args:
            odds_data: Dict with game_id, sportsbook, captured_at, and odds fields.

        Returns:
            ID of inserted snapshot.
        """
        columns = ", ".join(odds_data.keys())
        placeholders = ", ".join(["?" for _ in odds_data])
        query = f"INSERT OR REPLACE INTO odds_snapshots ({columns}) VALUES ({placeholders})"

        with self.get_cursor() as cursor:
            cursor.execute(query, tuple(odds_data.values()))
            return cursor.lastrowid

    def insert_bankroll_entry(self, entry: dict) -> int:
        """Insert or update a bankroll log entry.

        Args:
            entry: Dict with date, starting_balance, ending_balance, daily_pnl, etc.

        Returns:
            ID of inserted entry.
        """
        columns = ", ".join(entry.keys())
        placeholders = ", ".join(["?" for _ in entry])
        query = f"INSERT OR REPLACE INTO bankroll_log ({columns}) VALUES ({placeholders})"

        with self.get_cursor() as cursor:
            cursor.execute(query, tuple(entry.values()))
            return cursor.lastrowid


if __name__ == "__main__":
    # Initialize database
    db = BettingDatabase()
    print(f"Database created successfully at: {db.db_path}")

    # Test connection
    with db.get_cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print("\nDatabase tables:")
        for table in tables:
            print(f"  - {table['name']}")
