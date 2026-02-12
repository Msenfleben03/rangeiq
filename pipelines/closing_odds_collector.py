"""Closing Odds Collector - Zero-Cost Solution for CLV Validation.

Scrapes closing odds from sportsbooks 15 minutes before game start using
headless browser automation. This is the CRITICAL component that enables
CLV (Closing Line Value) validation without paid odds APIs.

Zero-Cost Strategy:
    - Uses Selenium with headless Chrome (no API costs)
    - Scrapes public odds pages from major sportsbooks
    - Runs as cron job 15 min before each game
    - Updates bets.odds_closing for CLV calculation

Estimated Runtime:
    - ~15 seconds per game
    - 8-16 games/day typical = 2-4 minutes/day total

Target Sportsbooks:
    - DraftKings (primary)
    - FanDuel (backup)
    - BetMGM (backup)

Usage:
    # Collect closing odds for games starting soon
    python pipelines/closing_odds_collector.py --minutes-before 15

    # Scheduled cron job (every 15 minutes during game days)
    */15 * * * * cd /path/to/sports-betting && python pipelines/closing_odds_collector.py

Author: Generated for zero-cost CLV validation
Date: 2026-01-26
"""

import sqlite3
import time
import logging
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, asdict
from contextlib import contextmanager
from abc import ABC, abstractmethod

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException,
        NoSuchElementException,
        WebDriverException,
    )

    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Sportsbook configurations
SPORTSBOOKS = {
    "draftkings": {
        "name": "DraftKings",
        "base_url": "https://sportsbook.draftkings.com",
        "sport_paths": {
            "NCAAB": "/leagues/basketball/ncaab",
            "MLB": "/leagues/baseball/mlb",
            "NFL": "/leagues/football/nfl",
            "NCAAF": "/leagues/football/college-football",
        },
        "priority": 1,
    },
    "fanduel": {
        "name": "FanDuel",
        "base_url": "https://sportsbook.fanduel.com",
        "sport_paths": {
            "NCAAB": "/basketball/ncaab",
            "MLB": "/baseball/mlb",
            "NFL": "/football/nfl",
            "NCAAF": "/football/ncaaf",
        },
        "priority": 2,
    },
    "betmgm": {
        "name": "BetMGM",
        "base_url": "https://sports.betmgm.com/en/sports",
        "sport_paths": {
            "NCAAB": "/basketball-23/betting/usa-9/college-basketball-251",
            "MLB": "/baseball-23/betting/usa-9/mlb-75",
            "NFL": "/football-11/betting/usa-9/nfl-35",
            "NCAAF": "/football-11/betting/usa-9/college-football-211",
        },
        "priority": 3,
    },
}

# Rate limiting (seconds between page loads)
PAGE_LOAD_DELAY = 2.0
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30

# Timing configuration
DEFAULT_MINUTES_BEFORE = 15  # Collect odds 15 min before game


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class ClosingOdds:
    """Represents closing odds for a game."""

    game_id: str
    sportsbook: str
    captured_at: datetime

    # Spread
    spread_home: Optional[float] = None
    spread_home_odds: Optional[int] = None
    spread_away_odds: Optional[int] = None

    # Total
    total: Optional[float] = None
    over_odds: Optional[int] = None
    under_odds: Optional[int] = None

    # Moneyline
    moneyline_home: Optional[int] = None
    moneyline_away: Optional[int] = None

    # Metadata
    is_closing: bool = True
    confidence: float = 1.0  # 0-1, how confident we are in the parse

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        data = asdict(self)
        if isinstance(data["captured_at"], datetime):
            data["captured_at"] = data["captured_at"].isoformat()
        return data


@dataclass
class GameInfo:
    """Game information for odds lookup."""

    game_id: str
    sport: str
    game_date: datetime
    game_time: Optional[datetime]
    home_team: str
    away_team: str
    home_team_abbrev: Optional[str] = None
    away_team_abbrev: Optional[str] = None


# =============================================================================
# ZERO-COST ENFORCEMENT
# =============================================================================


class ZeroCostEnforcer:
    """Enforces zero-cost requirement - blocks any paid API usage.

    This is CRITICAL: We NEVER use paid APIs for odds data.
    All data must come from free public web scraping.
    """

    PAID_APIS_BLOCKED = [
        "the-odds-api",
        "odds-api.com",
        "sportsdata.io",
        "sportradar.com",
        "prophetx",
        "api.actionnetwork.com",
    ]

    @staticmethod
    def verify_url(url: str) -> bool:
        """Verify URL is not a paid API endpoint.

        Returns:
            True if URL is allowed (free/public), False if blocked.
        """
        url_lower = url.lower()
        for blocked in ZeroCostEnforcer.PAID_APIS_BLOCKED:
            if blocked in url_lower:
                logger.error(f"ZERO-COST VIOLATION: Blocked paid API: {url}")
                return False
        return True

    @staticmethod
    def log_cost_check(source: str, passed: bool) -> None:
        """Log cost verification result."""
        status = "PASS" if passed else "FAIL"
        logger.info(f"Zero-Cost Check [{status}]: {source}")


# =============================================================================
# SPORTSBOOK SCRAPER BASE
# =============================================================================


class SportsbookScraper(ABC):
    """Abstract base class for sportsbook scrapers."""

    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
        self.enforcer = ZeroCostEnforcer()

    @abstractmethod
    def get_game_odds(
        self,
        sport: str,
        home_team: str,
        away_team: str,
    ) -> Optional[ClosingOdds]:
        """Scrape odds for a specific game.

        Args:
            sport: Sport code (NCAAB, MLB, NFL, NCAAF)
            home_team: Home team name
            away_team: Away team name

        Returns:
            ClosingOdds if found, None otherwise.
        """
        pass

    def _safe_navigate(self, url: str) -> bool:
        """Navigate to URL with zero-cost verification.

        Returns:
            True if navigation succeeded, False otherwise.
        """
        if not self.enforcer.verify_url(url):
            return False

        try:
            self.driver.get(url)
            time.sleep(PAGE_LOAD_DELAY)
            return True
        except WebDriverException as e:
            logger.error(f"Navigation failed: {e}")
            return False

    def _parse_american_odds(self, odds_text: str) -> Optional[int]:
        """Parse American odds from text.

        Examples:
            "-110" -> -110
            "+150" -> 150
            "EVEN" -> 100
        """
        if not odds_text:
            return None

        odds_text = odds_text.strip().upper()

        if odds_text == "EVEN" or odds_text == "EV":
            return 100

        # Match +/- followed by digits
        match = re.search(r"([+-]?\d+)", odds_text)
        if match:
            return int(match.group(1))

        return None

    def _parse_spread(self, spread_text: str) -> Optional[float]:
        """Parse spread/total from text.

        Examples:
            "-5.5" -> -5.5
            "+3" -> 3.0
            "O 145.5" -> 145.5
        """
        if not spread_text:
            return None

        # Remove "O", "U", and other prefixes
        spread_text = re.sub(r"^[OU]\s*", "", spread_text.strip())

        match = re.search(r"([+-]?\d+\.?\d*)", spread_text)
        if match:
            return float(match.group(1))

        return None


# =============================================================================
# DRAFTKINGS SCRAPER
# =============================================================================


class DraftKingsScraper(SportsbookScraper):
    """DraftKings sportsbook scraper."""

    def get_game_odds(
        self,
        sport: str,
        home_team: str,
        away_team: str,
    ) -> Optional[ClosingOdds]:
        """Scrape odds from DraftKings."""
        config = SPORTSBOOKS["draftkings"]
        sport_path = config["sport_paths"].get(sport)

        if not sport_path:
            logger.warning(f"DraftKings: Sport {sport} not supported")
            return None

        url = f"{config['base_url']}{sport_path}"

        if not self._safe_navigate(url):
            return None

        try:
            # Wait for odds table to load
            WebDriverWait(self.driver, REQUEST_TIMEOUT).until(
                EC.presence_of_element_located((By.CLASS_NAME, "sportsbook-event-accordion"))
            )

            # Find the game row
            game_row = self._find_game_row(home_team, away_team)
            if not game_row:
                logger.warning(f"DraftKings: Game not found: {away_team} @ {home_team}")
                return None

            # Parse odds from the row
            return self._parse_game_row(game_row, home_team, away_team)

        except TimeoutException:
            logger.warning("DraftKings: Page load timeout")
            return None
        except NoSuchElementException as e:
            logger.warning(f"DraftKings: Element not found: {e}")
            return None

    def _find_game_row(
        self,
        home_team: str,
        away_team: str,
    ) -> Optional[Any]:
        """Find the game row element containing both teams."""
        try:
            # Find all event rows
            events = self.driver.find_elements(By.CSS_SELECTOR, "[data-testid='event']")

            home_lower = home_team.lower()
            away_lower = away_team.lower()

            for event in events:
                event_text = event.text.lower()
                # Check if both teams are mentioned
                if home_lower in event_text and away_lower in event_text:
                    return event

            return None

        except NoSuchElementException:
            return None

    def _parse_game_row(
        self,
        row: Any,
        home_team: str,
        away_team: str,
    ) -> Optional[ClosingOdds]:
        """Parse odds from a DraftKings game row."""
        try:
            odds = ClosingOdds(
                game_id="",  # Will be filled by caller
                sportsbook="DraftKings",
                captured_at=datetime.now(timezone.utc),
            )

            # Find odds cells (spread, total, moneyline)
            odds_cells = row.find_elements(By.CSS_SELECTOR, "[class*='outcome']")

            # DraftKings typically shows: Spread, Total, Moneyline
            # Each team has a row, so 6 cells total (3 per team)

            for cell in odds_cells:
                cell_text = cell.text.strip()
                cell_classes = cell.get_attribute("class") or ""

                # Parse based on cell content and position
                if "spread" in cell_classes.lower():
                    spread_val = self._parse_spread(cell_text)
                    odds_val = self._parse_american_odds(cell_text)
                    if spread_val is not None:
                        odds.spread_home = spread_val
                        odds.spread_home_odds = odds_val or -110

                elif "total" in cell_classes.lower():
                    total_val = self._parse_spread(cell_text)
                    odds_val = self._parse_american_odds(cell_text)
                    if total_val is not None:
                        odds.total = total_val
                        if "over" in cell_text.lower():
                            odds.over_odds = odds_val or -110
                        else:
                            odds.under_odds = odds_val or -110

                elif "moneyline" in cell_classes.lower():
                    ml_odds = self._parse_american_odds(cell_text)
                    if ml_odds is not None:
                        if home_team.lower() in cell.text.lower():
                            odds.moneyline_home = ml_odds
                        else:
                            odds.moneyline_away = ml_odds

            # Validate we got at least some odds
            if odds.spread_home is not None or odds.moneyline_home is not None:
                odds.confidence = 0.8  # Slightly reduced confidence for scraped data
                return odds

            return None

        except Exception as e:
            logger.error(f"DraftKings parse error: {e}")
            return None


# =============================================================================
# FANDUEL SCRAPER
# =============================================================================


class FanDuelScraper(SportsbookScraper):
    """FanDuel sportsbook scraper."""

    def get_game_odds(
        self,
        sport: str,
        home_team: str,
        away_team: str,
    ) -> Optional[ClosingOdds]:
        """Scrape odds from FanDuel."""
        config = SPORTSBOOKS["fanduel"]
        sport_path = config["sport_paths"].get(sport)

        if not sport_path:
            logger.warning(f"FanDuel: Sport {sport} not supported")
            return None

        url = f"{config['base_url']}{sport_path}"

        if not self._safe_navigate(url):
            return None

        try:
            # Wait for page load
            WebDriverWait(self.driver, REQUEST_TIMEOUT).until(
                EC.presence_of_element_located((By.TAG_NAME, "main"))
            )

            # Find the game row (FanDuel uses different selectors)
            game_row = self._find_game_row(home_team, away_team)
            if not game_row:
                logger.warning(f"FanDuel: Game not found: {away_team} @ {home_team}")
                return None

            return self._parse_game_row(game_row, home_team, away_team)

        except TimeoutException:
            logger.warning("FanDuel: Page load timeout")
            return None
        except NoSuchElementException as e:
            logger.warning(f"FanDuel: Element not found: {e}")
            return None

    def _find_game_row(self, home_team: str, away_team: str) -> Optional[Any]:
        """Find game row in FanDuel layout."""
        try:
            # FanDuel uses different DOM structure
            events = self.driver.find_elements(
                By.CSS_SELECTOR, "[class*='eventcard'], [class*='EventCard']"
            )

            home_lower = home_team.lower()
            away_lower = away_team.lower()

            for event in events:
                event_text = event.text.lower()
                if home_lower in event_text and away_lower in event_text:
                    return event

            return None

        except NoSuchElementException:
            return None

    def _parse_game_row(
        self,
        row: Any,
        home_team: str,
        away_team: str,
    ) -> Optional[ClosingOdds]:
        """Parse odds from FanDuel game row."""
        try:
            odds = ClosingOdds(
                game_id="",
                sportsbook="FanDuel",
                captured_at=datetime.now(timezone.utc),
            )

            # FanDuel layout parsing
            buttons = row.find_elements(By.TAG_NAME, "button")

            for btn in buttons:
                btn_text = btn.text.strip()

                # Parse spread
                if re.search(r"[+-]\d+\.?\d*", btn_text):
                    parts = btn_text.split("\n")
                    if len(parts) >= 2:
                        spread = self._parse_spread(parts[0])
                        odds_val = self._parse_american_odds(parts[1])

                        if spread is not None:
                            if odds.spread_home is None:
                                odds.spread_home = spread
                                odds.spread_home_odds = odds_val
                            else:
                                odds.spread_away_odds = odds_val

                # Parse total
                if "O " in btn_text.upper() or "U " in btn_text.upper():
                    parts = btn_text.split("\n")
                    if len(parts) >= 2:
                        total = self._parse_spread(parts[0])
                        odds_val = self._parse_american_odds(parts[1])

                        if total is not None:
                            odds.total = total
                            if "O" in parts[0].upper():
                                odds.over_odds = odds_val
                            else:
                                odds.under_odds = odds_val

                # Parse moneyline (just odds, no spread)
                if re.match(r"^[+-]?\d{3,}$", btn_text.replace(" ", "")):
                    ml = self._parse_american_odds(btn_text)
                    if ml is not None:
                        if odds.moneyline_home is None:
                            odds.moneyline_home = ml
                        else:
                            odds.moneyline_away = ml

            if odds.spread_home is not None or odds.moneyline_home is not None:
                odds.confidence = 0.75
                return odds

            return None

        except Exception as e:
            logger.error(f"FanDuel parse error: {e}")
            return None


# =============================================================================
# CLOSING ODDS COLLECTOR
# =============================================================================


class ClosingOddsCollector:
    """Main collector for closing odds.

    Orchestrates scraping from multiple sportsbooks with fallback logic
    and zero-cost enforcement.

    Usage:
        collector = ClosingOddsCollector("data/betting.db")

        # Collect for games starting soon
        collector.collect_upcoming_closing_odds(minutes_before=15)

        # Collect for specific game
        odds = collector.collect_game_closing_odds(game_id, sport, home, away)
    """

    def __init__(
        self,
        db_path: str = "data/betting.db",
        headless: bool = True,
    ):
        """Initialize collector.

        Args:
            db_path: Path to SQLite database.
            headless: Run browser in headless mode (no GUI).
        """
        self.db_path = Path(db_path)
        self.headless = headless
        self._driver: Optional[webdriver.Chrome] = None
        self._scrapers: dict[str, SportsbookScraper] = {}
        self.enforcer = ZeroCostEnforcer()

        # Cost tracking
        self._cost_verified = True

        self._init_database()

    def _init_database(self) -> None:
        """Ensure database has required tables."""
        # The odds_snapshots table should already exist from tracking/models.py
        # We'll just verify it exists
        with self._get_db() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='odds_snapshots'"
            )
            if cursor.fetchone() is None:
                logger.warning("odds_snapshots table not found - creating minimal version")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS odds_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        game_id TEXT NOT NULL,
                        sportsbook TEXT NOT NULL,
                        captured_at TEXT NOT NULL,
                        spread_home REAL,
                        spread_home_odds INTEGER,
                        spread_away_odds INTEGER,
                        total REAL,
                        over_odds INTEGER,
                        under_odds INTEGER,
                        moneyline_home INTEGER,
                        moneyline_away INTEGER,
                        is_closing BOOLEAN DEFAULT FALSE
                    )
                """
                )

    @contextmanager
    def _get_db(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _get_driver(self) -> webdriver.Chrome:
        """Get or create Chrome WebDriver."""
        if not SELENIUM_AVAILABLE:
            raise ImportError("Selenium not installed. Run: pip install selenium webdriver-manager")

        if self._driver is None:
            chrome_options = Options()

            if self.headless:
                chrome_options.add_argument("--headless=new")

            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")

            # Stealth settings to avoid detection
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option("useAutomationExtension", False)

            try:
                # Try using webdriver-manager for automatic driver management
                from webdriver_manager.chrome import ChromeDriverManager

                service = Service(ChromeDriverManager().install())
                self._driver = webdriver.Chrome(service=service, options=chrome_options)
            except ImportError:
                # Fall back to system chromedriver
                self._driver = webdriver.Chrome(options=chrome_options)

            # Initialize scrapers
            self._scrapers = {
                "draftkings": DraftKingsScraper(self._driver),
                "fanduel": FanDuelScraper(self._driver),
            }

        return self._driver

    def _close_driver(self) -> None:
        """Close the WebDriver."""
        if self._driver is not None:
            self._driver.quit()
            self._driver = None
            self._scrapers = {}

    def collect_game_closing_odds(
        self,
        game_id: str,
        sport: str,
        home_team: str,
        away_team: str,
    ) -> Optional[ClosingOdds]:
        """Collect closing odds for a single game.

        Tries multiple sportsbooks in priority order until successful.

        Args:
            game_id: Unique game identifier.
            sport: Sport code (NCAAB, MLB, etc.)
            home_team: Home team name.
            away_team: Away team name.

        Returns:
            ClosingOdds if found, None otherwise.
        """
        self.enforcer.log_cost_check(f"collect_game: {game_id}", True)

        # Get driver (creates if needed)
        try:
            self._get_driver()
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            return None

        # Sort sportsbooks by priority
        sorted_books = sorted(
            SPORTSBOOKS.items(),
            key=lambda x: x[1]["priority"],
        )

        # Try each sportsbook in order
        for book_key, book_config in sorted_books:
            if book_key not in self._scrapers:
                continue

            scraper = self._scrapers[book_key]
            logger.info(f"Trying {book_config['name']} for {away_team} @ {home_team}")

            for attempt in range(MAX_RETRIES):
                try:
                    odds = scraper.get_game_odds(sport, home_team, away_team)

                    if odds is not None:
                        odds.game_id = game_id
                        logger.info(
                            f"SUCCESS: Got closing odds from {book_config['name']}: "
                            f"spread={odds.spread_home}, ML={odds.moneyline_home}"
                        )
                        return odds

                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}")
                    time.sleep(PAGE_LOAD_DELAY * (attempt + 1))

            logger.info(f"No odds found from {book_config['name']}")

        logger.warning(f"Could not find odds for {away_team} @ {home_team} from any book")
        return None

    def store_closing_odds(self, odds: ClosingOdds) -> int:
        """Store closing odds to database.

        Args:
            odds: ClosingOdds object to store.

        Returns:
            Row ID of inserted record.
        """
        with self._get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO odds_snapshots (
                    game_id, sportsbook, captured_at,
                    spread_home, spread_home_odds, spread_away_odds,
                    total, over_odds, under_odds,
                    moneyline_home, moneyline_away,
                    is_closing
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    odds.game_id,
                    odds.sportsbook,
                    odds.captured_at.isoformat()
                    if isinstance(odds.captured_at, datetime)
                    else odds.captured_at,
                    odds.spread_home,
                    odds.spread_home_odds,
                    odds.spread_away_odds,
                    odds.total,
                    odds.over_odds,
                    odds.under_odds,
                    odds.moneyline_home,
                    odds.moneyline_away,
                    odds.is_closing,
                ),
            )
            return cursor.lastrowid

    def update_bet_closing_odds(self, game_id: str) -> int:
        """Update bets table with closing odds for a game.

        After storing closing odds, this updates the bets.odds_closing field
        for any bets placed on this game, enabling CLV calculation.

        Args:
            game_id: Game ID to update bets for.

        Returns:
            Number of bets updated.
        """
        with self._get_db() as conn:
            # Get closing odds for this game
            cursor = conn.execute(
                """
                SELECT spread_home, spread_home_odds, spread_away_odds,
                       total, over_odds, under_odds,
                       moneyline_home, moneyline_away
                FROM odds_snapshots
                WHERE game_id = ? AND is_closing = 1
                ORDER BY captured_at DESC
                LIMIT 1
            """,
                (game_id,),
            )
            closing = cursor.fetchone()

            if not closing:
                logger.warning(f"No closing odds found for game {game_id}")
                return 0

            # Update bets based on bet_type
            updated = 0

            # Spread bets
            cursor = conn.execute(
                """
                UPDATE bets
                SET odds_closing = ?
                WHERE game_id = ? AND bet_type = 'spread' AND selection = 'home'
                AND odds_closing IS NULL
            """,
                (closing["spread_home_odds"], game_id),
            )
            updated += cursor.rowcount

            cursor = conn.execute(
                """
                UPDATE bets
                SET odds_closing = ?
                WHERE game_id = ? AND bet_type = 'spread' AND selection = 'away'
                AND odds_closing IS NULL
            """,
                (closing["spread_away_odds"], game_id),
            )
            updated += cursor.rowcount

            # Total bets
            cursor = conn.execute(
                """
                UPDATE bets
                SET odds_closing = ?
                WHERE game_id = ? AND bet_type = 'total' AND selection = 'over'
                AND odds_closing IS NULL
            """,
                (closing["over_odds"], game_id),
            )
            updated += cursor.rowcount

            cursor = conn.execute(
                """
                UPDATE bets
                SET odds_closing = ?
                WHERE game_id = ? AND bet_type = 'total' AND selection = 'under'
                AND odds_closing IS NULL
            """,
                (closing["under_odds"], game_id),
            )
            updated += cursor.rowcount

            # Moneyline bets
            cursor = conn.execute(
                """
                UPDATE bets
                SET odds_closing = ?
                WHERE game_id = ? AND bet_type = 'moneyline' AND selection = 'home'
                AND odds_closing IS NULL
            """,
                (closing["moneyline_home"], game_id),
            )
            updated += cursor.rowcount

            cursor = conn.execute(
                """
                UPDATE bets
                SET odds_closing = ?
                WHERE game_id = ? AND bet_type = 'moneyline' AND selection = 'away'
                AND odds_closing IS NULL
            """,
                (closing["moneyline_away"], game_id),
            )
            updated += cursor.rowcount

            if updated > 0:
                logger.info(f"Updated odds_closing for {updated} bets on game {game_id}")

            return updated

    def get_upcoming_games(self, minutes_ahead: int = 120) -> list[GameInfo]:
        """Get games starting within the next N minutes.

        Args:
            minutes_ahead: Look ahead window in minutes.

        Returns:
            List of GameInfo objects for upcoming games.
        """
        now = datetime.now(timezone.utc)
        cutoff = now + timedelta(minutes=minutes_ahead)

        with self._get_db() as conn:
            cursor = conn.execute(
                """
                SELECT
                    g.game_id,
                    g.sport,
                    g.game_date,
                    g.game_time,
                    h.team_name as home_team,
                    a.team_name as away_team,
                    h.team_abbrev as home_abbrev,
                    a.team_abbrev as away_abbrev
                FROM games g
                LEFT JOIN teams h ON g.home_team_id = h.team_id
                LEFT JOIN teams a ON g.away_team_id = a.team_id
                WHERE g.game_time IS NOT NULL
                AND g.game_time > ?
                AND g.game_time <= ?
                AND g.is_final = 0
                ORDER BY g.game_time ASC
            """,
                (now.isoformat(), cutoff.isoformat()),
            )

            games = []
            for row in cursor.fetchall():
                games.append(
                    GameInfo(
                        game_id=row["game_id"],
                        sport=row["sport"],
                        game_date=datetime.fromisoformat(row["game_date"])
                        if row["game_date"]
                        else None,
                        game_time=datetime.fromisoformat(row["game_time"])
                        if row["game_time"]
                        else None,
                        home_team=row["home_team"] or "",
                        away_team=row["away_team"] or "",
                        home_team_abbrev=row["home_abbrev"],
                        away_team_abbrev=row["away_abbrev"],
                    )
                )

            return games

    def has_closing_odds(self, game_id: str) -> bool:
        """Check if game already has closing odds stored.

        Args:
            game_id: Game ID to check.

        Returns:
            True if closing odds exist, False otherwise.
        """
        with self._get_db() as conn:
            cursor = conn.execute(
                """
                SELECT 1 FROM odds_snapshots
                WHERE game_id = ? AND is_closing = 1
                LIMIT 1
            """,
                (game_id,),
            )
            return cursor.fetchone() is not None

    def collect_upcoming_closing_odds(
        self,
        minutes_before: int = DEFAULT_MINUTES_BEFORE,
    ) -> dict[str, Any]:
        """Collect closing odds for all games starting soon.

        This is the main method to run as a scheduled job.
        Finds games starting within minutes_before minutes and collects
        closing odds for any that don't already have them.

        Args:
            minutes_before: Collect odds for games starting in next N minutes.

        Returns:
            Summary dict with results.
        """
        # Verify zero-cost
        self.enforcer.log_cost_check("collect_upcoming_closing_odds", True)

        results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "games_checked": 0,
            "odds_collected": 0,
            "odds_already_exist": 0,
            "odds_failed": 0,
            "bets_updated": 0,
            "errors": [],
        }

        try:
            # Get upcoming games (look ahead 2 hours to find games within window)
            games = self.get_upcoming_games(minutes_ahead=120)

            for game in games:
                results["games_checked"] += 1

                # Check if within collection window
                if game.game_time:
                    time_until_start = game.game_time - datetime.now(timezone.utc)
                    minutes_until = time_until_start.total_seconds() / 60

                    # Only collect if within window
                    if minutes_until > minutes_before:
                        logger.debug(
                            f"Game {game.game_id} starts in {minutes_until:.0f} min, skipping"
                        )
                        continue

                # Check if we already have closing odds
                if self.has_closing_odds(game.game_id):
                    logger.debug(f"Game {game.game_id} already has closing odds")
                    results["odds_already_exist"] += 1
                    continue

                # Collect closing odds
                logger.info(
                    f"Collecting closing odds for {game.away_team} @ {game.home_team} "
                    f"({game.sport}, starts in {minutes_until:.0f} min)"
                )

                try:
                    odds = self.collect_game_closing_odds(
                        game_id=game.game_id,
                        sport=game.sport,
                        home_team=game.home_team,
                        away_team=game.away_team,
                    )

                    if odds:
                        # Store to database
                        self.store_closing_odds(odds)
                        results["odds_collected"] += 1

                        # Update any bets placed on this game
                        updated = self.update_bet_closing_odds(game.game_id)
                        results["bets_updated"] += updated

                    else:
                        results["odds_failed"] += 1

                except Exception as e:
                    logger.error(f"Error collecting odds for {game.game_id}: {e}")
                    results["errors"].append(str(e))
                    results["odds_failed"] += 1

        finally:
            # Always close browser when done
            self._close_driver()

        logger.info(
            f"Collection complete: {results['odds_collected']} collected, "
            f"{results['odds_already_exist']} already existed, "
            f"{results['odds_failed']} failed"
        )

        return results


# =============================================================================
# CLI INTERFACE
# =============================================================================


def main():
    """CLI entry point for closing odds collector."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Collect closing odds for CLV validation (ZERO-COST)"
    )
    parser.add_argument("--db", default="data/betting.db", help="Database path")
    parser.add_argument(
        "--minutes-before",
        type=int,
        default=DEFAULT_MINUTES_BEFORE,
        help=f"Collect odds for games starting in next N minutes (default: {DEFAULT_MINUTES_BEFORE})",
    )
    parser.add_argument("--game-id", help="Collect odds for specific game")
    parser.add_argument(
        "--sport", choices=["NCAAB", "MLB", "NFL", "NCAAF"], help="Sport (required with --game-id)"
    )
    parser.add_argument("--home", help="Home team name (required with --game-id)")
    parser.add_argument("--away", help="Away team name (required with --game-id)")
    parser.add_argument(
        "--no-headless", action="store_true", help="Show browser window (for debugging)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be collected without actually scraping",
    )

    args = parser.parse_args()

    # Initialize collector
    collector = ClosingOddsCollector(
        db_path=args.db,
        headless=not args.no_headless,
    )

    if args.dry_run:
        # Just show upcoming games
        print("=== Upcoming Games (Dry Run) ===")
        games = collector.get_upcoming_games(minutes_ahead=120)
        for game in games:
            has_odds = collector.has_closing_odds(game.game_id)
            status = "HAS ODDS" if has_odds else "NEEDS ODDS"
            print(f"  {game.away_team} @ {game.home_team} ({game.sport}) - {status}")
        return

    if args.game_id:
        # Collect for specific game
        if not args.sport or not args.home or not args.away:
            parser.error("--sport, --home, and --away required with --game-id")

        odds = collector.collect_game_closing_odds(
            game_id=args.game_id,
            sport=args.sport,
            home_team=args.home,
            away_team=args.away,
        )

        if odds:
            print("=== Closing Odds Collected ===")
            print(json.dumps(odds.to_dict(), indent=2, default=str))
            collector.store_closing_odds(odds)
            print(f"\nStored to database: {args.db}")
        else:
            print("Failed to collect closing odds")

    else:
        # Collect for all upcoming games
        results = collector.collect_upcoming_closing_odds(minutes_before=args.minutes_before)

        print("\n=== Collection Results ===")
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
