"""Arbitrage Detection Module.

Lightweight opportunistic arb detection that integrates with existing
odds_snapshots data. LOW PRIORITY module - runs passively on games
already being tracked by the main model.

Design Philosophy:
- PASSIVE: Only flags arbs on games you're already modeling
- MINIMAL: Uses existing tables, no major schema changes
- OPTIONAL: Can be enabled/disabled without affecting core model
- CONSERVATIVE: High threshold (>1% profit) to filter noise

Usage:
    from betting.arb_detector import ArbDetector

    detector = ArbDetector(db_path="data/betting.db")
    opportunities = detector.scan_current_games()

    for arb in opportunities:
        print(f"{arb['description']} | Profit: {arb['profit_pct']:.2%}")
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from betting.odds_converter import american_to_decimal, american_to_implied_prob


@dataclass
class ArbOpportunity:
    """Represents a detected arbitrage opportunity."""

    game_id: str
    sport: str
    arb_type: str  # 'moneyline', 'spread', 'total'

    # Leg 1
    book1: str
    selection1: str
    odds1: int
    implied_prob1: float

    # Leg 2
    book2: str
    selection2: str
    odds2: int
    implied_prob2: float

    # Arb metrics
    combined_implied: float
    profit_pct: float

    # Stakes for $100 total outlay
    stake1: float
    stake2: float

    # Timing
    detected_at: datetime
    game_time: Optional[datetime] = None

    @property
    def is_valid(self) -> bool:
        """Arb is valid if combined implied < 100%."""
        return self.combined_implied < 1.0

    @property
    def description(self) -> str:
        """Human-readable description."""
        return (
            f"{self.arb_type.upper()} ARB: "
            f"{self.selection1} @ {self.book1} ({self.odds1:+d}) + "
            f"{self.selection2} @ {self.book2} ({self.odds2:+d})"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for storage/JSON."""
        return {
            "game_id": self.game_id,
            "sport": self.sport,
            "arb_type": self.arb_type,
            "book1": self.book1,
            "selection1": self.selection1,
            "odds1": self.odds1,
            "implied_prob1": self.implied_prob1,
            "book2": self.book2,
            "selection2": self.selection2,
            "odds2": self.odds2,
            "implied_prob2": self.implied_prob2,
            "combined_implied": self.combined_implied,
            "profit_pct": self.profit_pct,
            "stake1": self.stake1,
            "stake2": self.stake2,
            "detected_at": self.detected_at.isoformat(),
            "game_time": self.game_time.isoformat() if self.game_time else None,
            "description": self.description,
        }


def calculate_arb_stakes(
    odds1: int, odds2: int, total_stake: float = 100.0
) -> tuple[float, float, float]:
    """Calculate optimal stakes for a 2-way arb.

    Args:
        odds1: American odds for selection 1
        odds2: American odds for selection 2
        total_stake: Total amount to distribute

    Returns:
        Tuple of (stake1, stake2, guaranteed_profit)
    """
    dec1 = american_to_decimal(odds1)
    dec2 = american_to_decimal(odds2)

    imp1 = 1 / dec1
    imp2 = 1 / dec2
    combined = imp1 + imp2

    if combined >= 1.0:
        return 0.0, 0.0, 0.0

    # Stake proportional to inverse of decimal odds
    stake1 = total_stake * imp1 / combined
    stake2 = total_stake * imp2 / combined

    # Guaranteed return is same regardless of outcome
    guaranteed_return = stake1 * dec1  # = stake2 * dec2
    profit = guaranteed_return - total_stake

    return stake1, stake2, profit


class ArbDetector:
    """Lightweight arbitrage detector for sports betting.

    Scans odds_snapshots table for cross-book arbitrage opportunities
    on games already being tracked. Does NOT require any model changes.
    """

    # Minimum profit threshold to flag (filters noise)
    MIN_PROFIT_PCT = 0.01  # 1%

    # Lookback window for recent odds
    ODDS_WINDOW_HOURS = 2

    def __init__(self, db_path: str = "data/betting.db"):
        """Initialize detector with database path.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self._ensure_arb_table()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_arb_table(self) -> None:
        """Create arb_opportunities table if not exists.

        This is the ONLY schema addition - completely optional.
        """
        create_sql = """
        CREATE TABLE IF NOT EXISTS arb_opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL,
            sport TEXT,
            arb_type TEXT NOT NULL,

            book1 TEXT NOT NULL,
            selection1 TEXT NOT NULL,
            odds1 INTEGER NOT NULL,

            book2 TEXT NOT NULL,
            selection2 TEXT NOT NULL,
            odds2 INTEGER NOT NULL,

            combined_implied REAL NOT NULL,
            profit_pct REAL NOT NULL,
            stake1 REAL,
            stake2 REAL,

            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            acted_on BOOLEAN DEFAULT FALSE,
            notes TEXT,

            FOREIGN KEY (game_id) REFERENCES games(game_id)
        );

        CREATE INDEX IF NOT EXISTS idx_arb_game ON arb_opportunities(game_id);
        CREATE INDEX IF NOT EXISTS idx_arb_detected ON arb_opportunities(detected_at);
        CREATE INDEX IF NOT EXISTS idx_arb_profit ON arb_opportunities(profit_pct);
        """

        with self._get_connection() as conn:
            conn.executescript(create_sql)

    def _get_latest_odds_by_book(self, game_id: str) -> dict[str, dict]:
        """Get most recent odds snapshot for each sportsbook.

        Args:
            game_id: Game identifier

        Returns:
            Dict mapping sportsbook -> latest odds data
        """
        cutoff = datetime.now() - timedelta(hours=self.ODDS_WINDOW_HOURS)

        query = """
        SELECT
            o.*,
            g.sport,
            g.game_time
        FROM odds_snapshots o
        JOIN games g ON o.game_id = g.game_id
        WHERE o.game_id = ?
          AND o.captured_at >= ?
        ORDER BY o.sportsbook, o.captured_at DESC
        """

        with self._get_connection() as conn:
            rows = conn.execute(query, (game_id, cutoff.isoformat())).fetchall()

        # Keep only most recent per sportsbook
        latest: dict[str, dict] = {}
        for row in rows:
            book = row["sportsbook"]
            if book not in latest:
                latest[book] = dict(row)

        return latest

    def _detect_moneyline_arb(
        self, game_id: str, sport: str, odds_by_book: dict[str, dict], game_time: Optional[datetime]
    ) -> Optional[ArbOpportunity]:
        """Check for moneyline arbitrage across books.

        Args:
            game_id: Game identifier
            sport: Sport code
            odds_by_book: Dict of sportsbook -> odds data
            game_time: Scheduled game time

        Returns:
            ArbOpportunity if found, None otherwise
        """
        if len(odds_by_book) < 2:
            return None

        # Find best home ML and best away ML across all books
        best_home = {"book": None, "odds": -9999}
        best_away = {"book": None, "odds": -9999}

        for book, odds in odds_by_book.items():
            home_ml = odds.get("moneyline_home")
            away_ml = odds.get("moneyline_away")

            if home_ml and home_ml > best_home["odds"]:
                best_home = {"book": book, "odds": home_ml}

            if away_ml and away_ml > best_away["odds"]:
                best_away = {"book": book, "odds": away_ml}

        if not best_home["book"] or not best_away["book"]:
            return None

        # Calculate combined implied probability
        imp_home = american_to_implied_prob(best_home["odds"])
        imp_away = american_to_implied_prob(best_away["odds"])
        combined = imp_home + imp_away

        if combined >= 1.0:
            return None

        profit_pct = (1 / combined) - 1

        if profit_pct < self.MIN_PROFIT_PCT:
            return None

        stake1, stake2, _ = calculate_arb_stakes(best_home["odds"], best_away["odds"])

        return ArbOpportunity(
            game_id=game_id,
            sport=sport,
            arb_type="moneyline",
            book1=best_home["book"],
            selection1="home",
            odds1=best_home["odds"],
            implied_prob1=imp_home,
            book2=best_away["book"],
            selection2="away",
            odds2=best_away["odds"],
            implied_prob2=imp_away,
            combined_implied=combined,
            profit_pct=profit_pct,
            stake1=stake1,
            stake2=stake2,
            detected_at=datetime.now(),
            game_time=game_time,
        )

    def _detect_spread_arb(
        self, game_id: str, sport: str, odds_by_book: dict[str, dict], game_time: Optional[datetime]
    ) -> Optional[ArbOpportunity]:
        """Check for spread arbitrage (same spread, different juice).

        Looks for cases where you can bet both sides of the SAME spread
        number at different books for a guaranteed profit.
        """
        if len(odds_by_book) < 2:
            return None

        # Group by spread value
        spreads: dict[float, list] = {}
        for book, odds in odds_by_book.items():
            spread = odds.get("spread_home")
            if spread is None:
                continue

            if spread not in spreads:
                spreads[spread] = []

            spreads[spread].append(
                {
                    "book": book,
                    "home_odds": odds.get("spread_home_odds"),
                    "away_odds": odds.get("spread_away_odds"),
                }
            )

        # Check each spread value for arb
        for spread_val, book_odds in spreads.items():
            if len(book_odds) < 2:
                continue

            # Find best home spread odds and best away spread odds
            best_home = max(
                [b for b in book_odds if b["home_odds"]], key=lambda x: x["home_odds"], default=None
            )
            best_away = max(
                [b for b in book_odds if b["away_odds"]], key=lambda x: x["away_odds"], default=None
            )

            if not best_home or not best_away:
                continue

            imp_home = american_to_implied_prob(best_home["home_odds"])
            imp_away = american_to_implied_prob(best_away["away_odds"])
            combined = imp_home + imp_away

            if combined >= 1.0:
                continue

            profit_pct = (1 / combined) - 1

            if profit_pct < self.MIN_PROFIT_PCT:
                continue

            stake1, stake2, _ = calculate_arb_stakes(best_home["home_odds"], best_away["away_odds"])

            return ArbOpportunity(
                game_id=game_id,
                sport=sport,
                arb_type="spread",
                book1=best_home["book"],
                selection1=f"home {spread_val:+.1f}",
                odds1=best_home["home_odds"],
                implied_prob1=imp_home,
                book2=best_away["book"],
                selection2=f"away {-spread_val:+.1f}",
                odds2=best_away["away_odds"],
                implied_prob2=imp_away,
                combined_implied=combined,
                profit_pct=profit_pct,
                stake1=stake1,
                stake2=stake2,
                detected_at=datetime.now(),
                game_time=game_time,
            )

        return None

    def _detect_total_arb(
        self, game_id: str, sport: str, odds_by_book: dict[str, dict], game_time: Optional[datetime]
    ) -> Optional[ArbOpportunity]:
        """Check for over/under total arbitrage."""
        if len(odds_by_book) < 2:
            return None

        # Group by total value
        totals: dict[float, list] = {}
        for book, odds in odds_by_book.items():
            total = odds.get("total")
            if total is None:
                continue

            if total not in totals:
                totals[total] = []

            totals[total].append(
                {
                    "book": book,
                    "over_odds": odds.get("over_odds"),
                    "under_odds": odds.get("under_odds"),
                }
            )

        for total_val, book_odds in totals.items():
            if len(book_odds) < 2:
                continue

            best_over = max(
                [b for b in book_odds if b["over_odds"]], key=lambda x: x["over_odds"], default=None
            )
            best_under = max(
                [b for b in book_odds if b["under_odds"]],
                key=lambda x: x["under_odds"],
                default=None,
            )

            if not best_over or not best_under:
                continue

            imp_over = american_to_implied_prob(best_over["over_odds"])
            imp_under = american_to_implied_prob(best_under["under_odds"])
            combined = imp_over + imp_under

            if combined >= 1.0:
                continue

            profit_pct = (1 / combined) - 1

            if profit_pct < self.MIN_PROFIT_PCT:
                continue

            stake1, stake2, _ = calculate_arb_stakes(
                best_over["over_odds"], best_under["under_odds"]
            )

            return ArbOpportunity(
                game_id=game_id,
                sport=sport,
                arb_type="total",
                book1=best_over["book"],
                selection1=f"over {total_val}",
                odds1=best_over["over_odds"],
                implied_prob1=imp_over,
                book2=best_under["book"],
                selection2=f"under {total_val}",
                odds2=best_under["under_odds"],
                implied_prob2=imp_under,
                combined_implied=combined,
                profit_pct=profit_pct,
                stake1=stake1,
                stake2=stake2,
                detected_at=datetime.now(),
                game_time=game_time,
            )

        return None

    def scan_game(self, game_id: str) -> list[ArbOpportunity]:
        """Scan a single game for arbitrage opportunities.

        Args:
            game_id: Game identifier

        Returns:
            List of detected ArbOpportunity objects
        """
        odds_by_book = self._get_latest_odds_by_book(game_id)

        if len(odds_by_book) < 2:
            return []

        # Get sport and game time from first entry
        first_odds = next(iter(odds_by_book.values()))
        sport = first_odds.get("sport", "UNKNOWN")
        game_time = first_odds.get("game_time")
        if game_time and isinstance(game_time, str):
            try:
                game_time = datetime.fromisoformat(game_time)
            except ValueError:
                game_time = None

        opportunities = []

        # Check all arb types
        ml_arb = self._detect_moneyline_arb(game_id, sport, odds_by_book, game_time)
        if ml_arb:
            opportunities.append(ml_arb)

        spread_arb = self._detect_spread_arb(game_id, sport, odds_by_book, game_time)
        if spread_arb:
            opportunities.append(spread_arb)

        total_arb = self._detect_total_arb(game_id, sport, odds_by_book, game_time)
        if total_arb:
            opportunities.append(total_arb)

        return opportunities

    def scan_current_games(
        self, sport: Optional[str] = None, hours_ahead: int = 24
    ) -> list[ArbOpportunity]:
        """Scan all upcoming games for arbitrage opportunities.

        Args:
            sport: Filter by sport (None = all sports)
            hours_ahead: How far ahead to look for games

        Returns:
            List of detected ArbOpportunity objects
        """
        now = datetime.now()
        cutoff = now + timedelta(hours=hours_ahead)

        query = """
        SELECT DISTINCT g.game_id
        FROM games g
        JOIN odds_snapshots o ON g.game_id = o.game_id
        WHERE g.is_final = FALSE
          AND g.game_time >= ?
          AND g.game_time <= ?
        """
        params = [now.isoformat(), cutoff.isoformat()]

        if sport:
            query += " AND g.sport = ?"
            params.append(sport)

        with self._get_connection() as conn:
            game_ids = [row[0] for row in conn.execute(query, params).fetchall()]

        all_opportunities = []
        for game_id in game_ids:
            opportunities = self.scan_game(game_id)
            all_opportunities.extend(opportunities)

        # Sort by profit percentage descending
        all_opportunities.sort(key=lambda x: x.profit_pct, reverse=True)

        return all_opportunities

    def log_opportunity(self, arb: ArbOpportunity) -> int:
        """Log detected opportunity to database.

        Args:
            arb: ArbOpportunity to log

        Returns:
            Inserted row ID
        """
        insert_sql = """
        INSERT INTO arb_opportunities (
            game_id, sport, arb_type,
            book1, selection1, odds1,
            book2, selection2, odds2,
            combined_implied, profit_pct,
            stake1, stake2, detected_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self._get_connection() as conn:
            cursor = conn.execute(
                insert_sql,
                (
                    arb.game_id,
                    arb.sport,
                    arb.arb_type,
                    arb.book1,
                    arb.selection1,
                    arb.odds1,
                    arb.book2,
                    arb.selection2,
                    arb.odds2,
                    arb.combined_implied,
                    arb.profit_pct,
                    arb.stake1,
                    arb.stake2,
                    arb.detected_at.isoformat(),
                ),
            )
            return cursor.lastrowid

    def get_recent_opportunities(self, hours: int = 24, min_profit: float = 0.0) -> list[dict]:
        """Retrieve recently logged opportunities.

        Args:
            hours: Lookback period
            min_profit: Minimum profit percentage filter

        Returns:
            List of opportunity dicts
        """
        cutoff = datetime.now() - timedelta(hours=hours)

        query = """
        SELECT * FROM arb_opportunities
        WHERE detected_at >= ?
          AND profit_pct >= ?
        ORDER BY profit_pct DESC
        """

        with self._get_connection() as conn:
            rows = conn.execute(query, (cutoff.isoformat(), min_profit)).fetchall()

        return [dict(row) for row in rows]


# =============================================================================
# CLI INTERFACE
# =============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scan for arbitrage opportunities")
    parser.add_argument("--sport", type=str, help="Filter by sport (NCAAB, MLB, etc.)")
    parser.add_argument("--hours", type=int, default=24, help="Hours ahead to scan")
    parser.add_argument("--min-profit", type=float, default=0.01, help="Min profit %")
    parser.add_argument("--db", type=str, default="data/betting.db", help="Database path")

    args = parser.parse_args()

    detector = ArbDetector(db_path=args.db)
    detector.MIN_PROFIT_PCT = args.min_profit

    print(f"\n{'='*60}")
    print(f"ARBITRAGE SCANNER | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    print(f"Sport Filter: {args.sport or 'ALL'}")
    print(f"Scan Window: Next {args.hours} hours")
    print(f"Min Profit: {args.min_profit:.1%}")
    print(f"{'='*60}\n")

    opportunities = detector.scan_current_games(sport=args.sport, hours_ahead=args.hours)

    if not opportunities:
        print("No arbitrage opportunities detected.")
    else:
        print(f"Found {len(opportunities)} opportunities:\n")

        for i, arb in enumerate(opportunities, 1):
            print(f"{i}. {arb.description}")
            print(f"   Combined Implied: {arb.combined_implied:.2%}")
            print(f"   Profit: {arb.profit_pct:.2%} (${arb.profit_pct * 100:.2f} per $100)")
            print(f"   Stakes: ${arb.stake1:.2f} @ {arb.book1}, ${arb.stake2:.2f} @ {arb.book2}")
            if arb.game_time:
                print(f"   Game Time: {arb.game_time.strftime('%Y-%m-%d %H:%M')}")
            print()

            # Log to database
            row_id = detector.log_opportunity(arb)
            print(f"   [Logged as ID: {row_id}]")
            print()
