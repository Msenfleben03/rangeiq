"""
Polymarket Data Fetcher

Fetches prediction market data from Polymarket's CLOB API for sports,
political, and other markets. Integrates with the forecasting database
for tracking and analysis.

Uses the py-clob-client library for API access.
Install: pip install py-clob-client

API Documentation: https://docs.polymarket.com
"""

import sqlite3
import time
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from contextlib import contextmanager
import json

try:
    import requests
except ImportError:
    raise ImportError("requests not installed. Run: pip install requests")

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds
except ImportError:
    # Define stub for type hints when library not installed
    ClobClient = None
    ApiCreds = None
    logging.warning(
        "py-clob-client not installed. Some features may be limited. "
        "Run: pip install py-clob-client"
    )

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Polymarket API endpoints
POLYMARKET_CLOB_BASE_URL = "https://clob.polymarket.com"
POLYMARKET_GAMMA_BASE_URL = "https://gamma-api.polymarket.com"
POLYMARKET_STRAPI_BASE_URL = "https://strapi-matic.polymarket.com"

# Rate limiting
DEFAULT_RATE_LIMIT_DELAY = 1.0  # seconds between requests
MAX_REQUESTS_PER_MINUTE = 100
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # Base delay for exponential backoff


# =============================================================================
# DATA CLASSES
# =============================================================================


class MarketCategory(Enum):
    """Polymarket market categories."""

    SPORTS = "sports"
    POLITICS = "politics"
    CRYPTO = "crypto"
    ECONOMICS = "economics"
    SCIENCE = "science"
    ENTERTAINMENT = "entertainment"
    OTHER = "other"


class MarketStatus(Enum):
    """Market trading status."""

    ACTIVE = "active"
    CLOSED = "closed"
    RESOLVED = "resolved"
    PAUSED = "paused"


@dataclass
class PolymarketMarket:
    """Represents a Polymarket prediction market."""

    market_id: str
    condition_id: str
    question: str
    description: Optional[str] = None
    category: str = "other"
    subcategory: Optional[str] = None
    end_date: Optional[datetime] = None

    # Token information
    tokens: List[Dict[str, Any]] = field(default_factory=list)

    # Current prices
    yes_price: Optional[float] = None
    no_price: Optional[float] = None
    yes_bid: Optional[float] = None
    yes_ask: Optional[float] = None
    no_bid: Optional[float] = None
    no_ask: Optional[float] = None
    spread: Optional[float] = None

    # Market stats
    volume: Optional[float] = None
    volume_24h: Optional[float] = None
    liquidity: Optional[float] = None

    # Status
    status: str = "active"
    is_resolved: bool = False
    outcome: Optional[str] = None

    # Metadata
    url: Optional[str] = None
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for key in ["end_date", "created_at", "updated_at"]:
            if data[key] is not None and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data


@dataclass
class PricePoint:
    """A single price observation."""

    timestamp: datetime
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "bid": self.bid,
            "ask": self.ask,
            "volume": self.volume,
        }


@dataclass
class MarketPrices:
    """Current market prices and order book summary."""

    token_id: str
    market_id: str
    timestamp: datetime
    mid_price: float
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    bid_depth: Optional[float] = None
    ask_depth: Optional[float] = None
    implied_probability: Optional[float] = None
    american_odds: Optional[int] = None


# =============================================================================
# POLYMARKET FETCHER CLASS
# =============================================================================


class PolymarketFetcher:
    """
    Fetches prediction market data from Polymarket.

    Provides methods to:
    - Fetch sports, political, and other markets
    - Get current bid/ask/mid prices
    - Retrieve historical price data
    - Store markets in SQLite database

    Example:
        >>> fetcher = PolymarketFetcher()
        >>> sports = fetcher.fetch_sports_markets()
        >>> print(f"Found {len(sports)} sports markets")
        >>> prices = fetcher.fetch_market_prices(token_id="0x123...")
        >>> fetcher.store_markets(sports)
    """

    def __init__(
        self,
        db_path: str = "data/betting.db",
        rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY,
        max_retries: int = MAX_RETRIES,
    ):
        """
        Initialize Polymarket fetcher.

        Args:
            db_path: Path to SQLite database
            rate_limit_delay: Delay between API requests (seconds)
            max_retries: Maximum retry attempts for failed requests
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self._last_request_time = 0.0
        self._request_count = 0
        self._minute_start = time.time()

        # Initialize CLOB client if available
        self._clob_client: Optional[ClobClient] = None
        if ClobClient is not None:
            try:
                self._clob_client = ClobClient(
                    host=POLYMARKET_CLOB_BASE_URL, chain_id=137  # Polygon mainnet
                )
            except Exception as e:
                logger.warning(f"Failed to initialize CLOB client: {e}")

        # Create session for HTTP requests
        self._session = requests.Session()
        self._session.headers.update(
            {"User-Agent": "SportsBetting/1.0", "Accept": "application/json"}
        )

        # Initialize database tables
        self._initialize_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Create database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def get_cursor(self):
        """Context manager for database operations."""
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

    def _initialize_schema(self) -> None:
        """Create prediction market tables if they don't exist."""
        with self.get_cursor() as cursor:
            # Polymarket markets table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS polymarket_markets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT UNIQUE NOT NULL,
                    condition_id TEXT,
                    question TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    subcategory TEXT,
                    end_date TIMESTAMP,

                    -- Token IDs (JSON array)
                    tokens TEXT,

                    -- Current prices
                    yes_price REAL,
                    no_price REAL,
                    yes_bid REAL,
                    yes_ask REAL,
                    no_bid REAL,
                    no_ask REAL,
                    spread REAL,

                    -- Market stats
                    volume REAL,
                    volume_24h REAL,
                    liquidity REAL,

                    -- Status
                    status TEXT DEFAULT 'active',
                    is_resolved BOOLEAN DEFAULT FALSE,
                    outcome TEXT,

                    -- Metadata
                    url TEXT,
                    image_url TEXT,

                    -- Timestamps
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_fetched TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            # Price history table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS polymarket_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    token_id TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL,
                    price REAL NOT NULL,
                    bid REAL,
                    ask REAL,
                    volume REAL,

                    FOREIGN KEY (market_id) REFERENCES polymarket_markets(market_id),
                    UNIQUE(market_id, token_id, timestamp)
                )
            """
            )

            # Create indexes for efficient queries
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_polymarket_category
                ON polymarket_markets(category)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_polymarket_status
                ON polymarket_markets(status)
            """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_price_history_market
                ON polymarket_price_history(market_id, timestamp)
            """
            )

            logger.info("Polymarket schema initialized")

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        current_time = time.time()

        # Reset minute counter if needed
        if current_time - self._minute_start >= 60:
            self._request_count = 0
            self._minute_start = current_time

        # Check if we've exceeded the per-minute limit
        if self._request_count >= MAX_REQUESTS_PER_MINUTE:
            sleep_time = 60 - (current_time - self._minute_start)
            if sleep_time > 0:
                logger.warning(f"Rate limit reached, sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
                self._request_count = 0
                self._minute_start = time.time()

        # Apply minimum delay between requests
        elapsed = current_time - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

        self._last_request_time = time.time()
        self._request_count += 1

    def _make_request(
        self, url: str, params: Optional[Dict[str, Any]] = None, method: str = "GET"
    ) -> Optional[Dict[str, Any]]:
        """
        Make an HTTP request with retry logic and rate limiting.

        Args:
            url: Request URL
            params: Query parameters
            method: HTTP method

        Returns:
            Response JSON or None if failed
        """
        for attempt in range(self.max_retries):
            self._rate_limit()

            try:
                if method.upper() == "GET":
                    response = self._session.get(url, params=params, timeout=30)
                else:
                    response = self._session.post(url, json=params, timeout=30)

                response.raise_for_status()
                return response.json()

            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:  # Rate limited
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(f"Rate limited, retry in {delay}s")
                    time.sleep(delay)
                elif response.status_code >= 500:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(f"Server error {response.status_code}, retry in {delay}s")
                    time.sleep(delay)
                else:
                    logger.error(f"HTTP error: {e}")
                    return None

            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}")
                if attempt < self.max_retries - 1:
                    delay = RETRY_BASE_DELAY * (2**attempt)
                    time.sleep(delay)

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                return None

        logger.error(f"Request failed after {self.max_retries} attempts")
        return None

    # =========================================================================
    # MARKET FETCHING
    # =========================================================================

    def fetch_all_markets(
        self, limit: int = 100, offset: int = 0, active_only: bool = True
    ) -> List[PolymarketMarket]:
        """
        Fetch all available markets from Polymarket.

        Args:
            limit: Maximum markets to return per page
            offset: Pagination offset
            active_only: Only return active markets

        Returns:
            List of PolymarketMarket objects
        """
        logger.info(f"Fetching all markets (limit={limit}, offset={offset})")

        url = f"{POLYMARKET_GAMMA_BASE_URL}/markets"
        params = {"limit": limit, "offset": offset, "closed": "false" if active_only else "true"}

        data = self._make_request(url, params)
        if not data:
            logger.warning("Failed to fetch markets")
            return []

        markets = self._parse_markets(data)
        logger.info(f"Fetched {len(markets)} markets")
        return markets

    def fetch_sports_markets(self, sport: Optional[str] = None) -> List[PolymarketMarket]:
        """
        Fetch sports prediction markets.

        Args:
            sport: Filter by sport (e.g., 'nfl', 'nba', 'mlb')

        Returns:
            List of sports-related markets
        """
        logger.info(f"Fetching sports markets (sport={sport})")

        # Polymarket uses tags/categories for sports
        search_terms = [
            "sports",
            "nfl",
            "nba",
            "mlb",
            "ncaa",
            "football",
            "basketball",
            "baseball",
            "soccer",
            "hockey",
            "super bowl",
            "world series",
            "championship",
            "playoffs",
            "march madness",
        ]

        if sport:
            search_terms = [sport.lower()]

        all_markets = []
        seen_ids = set()

        for term in search_terms:
            url = f"{POLYMARKET_GAMMA_BASE_URL}/markets"
            params = {"limit": 100, "closed": "false", "tag": term}

            data = self._make_request(url, params)
            if not data:
                continue

            markets = self._parse_markets(data)
            for market in markets:
                if market.market_id not in seen_ids:
                    market.category = MarketCategory.SPORTS.value
                    all_markets.append(market)
                    seen_ids.add(market.market_id)

        # Also search by keyword in question
        text_search_url = f"{POLYMARKET_GAMMA_BASE_URL}/markets"
        for term in ["NFL", "NBA", "MLB", "Super Bowl", "World Series"]:
            if sport and sport.lower() not in term.lower():
                continue

            params = {"limit": 50, "closed": "false", "search": term}
            data = self._make_request(text_search_url, params)

            if data:
                markets = self._parse_markets(data)
                for market in markets:
                    if market.market_id not in seen_ids:
                        market.category = MarketCategory.SPORTS.value
                        all_markets.append(market)
                        seen_ids.add(market.market_id)

        logger.info(f"Found {len(all_markets)} sports markets")
        return all_markets

    def fetch_political_markets(self) -> List[PolymarketMarket]:
        """
        Fetch political and economic prediction markets.

        Returns:
            List of political/economic markets
        """
        logger.info("Fetching political markets")

        search_terms = [
            "politics",
            "election",
            "president",
            "congress",
            "senate",
            "governor",
            "trump",
            "biden",
            "democratic",
            "republican",
            "economy",
            "fed",
            "inflation",
            "recession",
            "policy",
        ]

        all_markets = []
        seen_ids = set()

        for term in search_terms:
            url = f"{POLYMARKET_GAMMA_BASE_URL}/markets"
            params = {"limit": 100, "closed": "false", "tag": term}

            data = self._make_request(url, params)
            if not data:
                continue

            markets = self._parse_markets(data)
            for market in markets:
                if market.market_id not in seen_ids:
                    # Determine subcategory
                    question_lower = market.question.lower()
                    if any(
                        t in question_lower
                        for t in ["economy", "fed", "inflation", "gdp", "recession"]
                    ):
                        market.category = MarketCategory.ECONOMICS.value
                    else:
                        market.category = MarketCategory.POLITICS.value
                    all_markets.append(market)
                    seen_ids.add(market.market_id)

        logger.info(f"Found {len(all_markets)} political/economic markets")
        return all_markets

    def fetch_market_by_id(self, market_id: str) -> Optional[PolymarketMarket]:
        """
        Fetch a specific market by its ID.

        Args:
            market_id: Polymarket market ID or condition ID

        Returns:
            PolymarketMarket or None if not found
        """
        logger.info(f"Fetching market: {market_id}")

        url = f"{POLYMARKET_GAMMA_BASE_URL}/markets/{market_id}"
        data = self._make_request(url)

        if not data:
            logger.warning(f"Market not found: {market_id}")
            return None

        markets = self._parse_markets([data])
        return markets[0] if markets else None

    def _parse_markets(self, data: Union[List[Dict], Dict]) -> List[PolymarketMarket]:
        """
        Parse raw API response into PolymarketMarket objects.

        Args:
            data: API response data

        Returns:
            List of PolymarketMarket objects
        """
        if isinstance(data, dict):
            data = [data]

        markets = []
        for item in data:
            try:
                # Handle nested market structure
                if "markets" in item:
                    # This is an event with multiple markets
                    for sub_market in item.get("markets", []):
                        market = self._parse_single_market(sub_market, item)
                        if market:
                            markets.append(market)
                else:
                    market = self._parse_single_market(item)
                    if market:
                        markets.append(market)

            except Exception as e:
                logger.debug(f"Error parsing market: {e}")
                continue

        return markets

    def _parse_single_market(
        self, item: Dict[str, Any], parent: Optional[Dict[str, Any]] = None
    ) -> Optional[PolymarketMarket]:
        """Parse a single market entry."""
        try:
            market_id = item.get("id") or item.get("conditionId") or item.get("condition_id")
            if not market_id:
                return None

            # Parse question
            question = item.get("question") or item.get("title", "")
            if parent:
                parent_q = parent.get("question") or parent.get("title", "")
                if parent_q and parent_q not in question:
                    question = f"{parent_q} - {question}"

            # Parse tokens
            tokens = []
            if "tokens" in item:
                tokens = item["tokens"]
            elif "outcomes" in item:
                tokens = [
                    {"outcome": o, "token_id": f"{market_id}_{i}"}
                    for i, o in enumerate(item["outcomes"])
                ]

            # Parse prices
            yes_price = None
            no_price = None

            if "outcomePrices" in item:
                prices = item["outcomePrices"]
                if isinstance(prices, list) and len(prices) >= 2:
                    yes_price = float(prices[0]) if prices[0] else None
                    no_price = float(prices[1]) if prices[1] else None
            elif "bestBid" in item or "bestAsk" in item:
                yes_price = item.get("lastTradePrice")

            # Parse end date
            end_date = None
            end_str = item.get("endDate") or item.get("end_date_iso")
            if end_str:
                try:
                    end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            # Parse volume
            volume = item.get("volume") or item.get("volumeNum")
            if isinstance(volume, str):
                try:
                    volume = float(volume.replace(",", ""))
                except ValueError:
                    volume = None

            # Build market URL
            slug = item.get("slug") or item.get("market_slug", "")
            url = f"https://polymarket.com/event/{slug}" if slug else None

            return PolymarketMarket(
                market_id=str(market_id),
                condition_id=item.get("conditionId") or item.get("condition_id", ""),
                question=question,
                description=item.get("description", ""),
                category=item.get("category", "other"),
                subcategory=item.get("subcategory"),
                end_date=end_date,
                tokens=tokens,
                yes_price=yes_price,
                no_price=no_price,
                yes_bid=item.get("bestBid"),
                yes_ask=item.get("bestAsk"),
                volume=float(volume) if volume else None,
                volume_24h=item.get("volume24hr"),
                liquidity=item.get("liquidity"),
                status=item.get("status", "active"),
                is_resolved=item.get("resolved", False) or item.get("closed", False),
                outcome=item.get("resolutionValue"),
                url=url,
                image_url=item.get("image"),
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

        except Exception as e:
            logger.debug(f"Error parsing single market: {e}")
            return None

    # =========================================================================
    # PRICE FETCHING
    # =========================================================================

    def fetch_market_prices(self, token_id: str) -> Optional[MarketPrices]:
        """
        Fetch current bid/ask/mid prices for a token.

        Args:
            token_id: Token ID from Polymarket

        Returns:
            MarketPrices object with current prices
        """
        logger.info(f"Fetching prices for token: {token_id}")

        # Use CLOB client if available
        if self._clob_client:
            try:
                book = self._clob_client.get_order_book(token_id)
                return self._parse_order_book(token_id, book)
            except Exception as e:
                logger.debug(f"CLOB client error: {e}")

        # Fallback to REST API
        url = f"{POLYMARKET_CLOB_BASE_URL}/book"
        params = {"token_id": token_id}

        data = self._make_request(url, params)
        if not data:
            return None

        return self._parse_order_book(token_id, data)

    def _parse_order_book(self, token_id: str, data: Dict[str, Any]) -> Optional[MarketPrices]:
        """Parse order book data into MarketPrices."""
        try:
            bids = data.get("bids", [])
            asks = data.get("asks", [])

            best_bid = float(bids[0]["price"]) if bids else None
            best_ask = float(asks[0]["price"]) if asks else None

            # Calculate mid price
            if best_bid is not None and best_ask is not None:
                mid_price = (best_bid + best_ask) / 2
                spread = best_ask - best_bid
            elif best_bid is not None:
                mid_price = best_bid
                spread = None
            elif best_ask is not None:
                mid_price = best_ask
                spread = None
            else:
                return None

            # Calculate depth
            bid_depth = sum(float(b["size"]) for b in bids) if bids else None
            ask_depth = sum(float(a["size"]) for a in asks) if asks else None

            # Convert to implied probability and American odds
            implied_prob = mid_price
            american_odds = self._probability_to_american(mid_price)

            return MarketPrices(
                token_id=token_id,
                market_id=data.get("market", ""),
                timestamp=datetime.now(),
                mid_price=mid_price,
                best_bid=best_bid,
                best_ask=best_ask,
                spread=spread,
                bid_depth=bid_depth,
                ask_depth=ask_depth,
                implied_probability=implied_prob,
                american_odds=american_odds,
            )

        except Exception as e:
            logger.error(f"Error parsing order book: {e}")
            return None

    def fetch_price_history(
        self, token_id: str, interval: str = "1d", limit: int = 100
    ) -> List[PricePoint]:
        """
        Fetch historical price data for a token.

        Args:
            token_id: Token ID
            interval: Time interval ('1h', '6h', '1d', '1w')
            limit: Maximum number of data points

        Returns:
            List of PricePoint objects
        """
        logger.info(f"Fetching price history for {token_id} (interval={interval})")

        # Map interval to CLOB API parameters
        interval_map = {
            "1h": 60,  # 1 hour in minutes
            "6h": 360,  # 6 hours
            "1d": 1440,  # 1 day
            "1w": 10080,  # 1 week
        }

        fidelity = interval_map.get(interval, 1440)

        url = f"{POLYMARKET_CLOB_BASE_URL}/prices-history"
        params = {"market": token_id, "interval": fidelity, "limit": limit}

        data = self._make_request(url, params)
        if not data:
            # Try alternative endpoint
            url = f"{POLYMARKET_GAMMA_BASE_URL}/prices-history"
            data = self._make_request(url, params)

        if not data:
            logger.warning(f"No price history found for {token_id}")
            return []

        return self._parse_price_history(data)

    def _parse_price_history(self, data: Union[List, Dict]) -> List[PricePoint]:
        """Parse price history response."""
        if isinstance(data, dict):
            data = data.get("history", [])

        points = []
        for item in data:
            try:
                # Parse timestamp
                ts = item.get("t") or item.get("timestamp")
                if isinstance(ts, (int, float)):
                    timestamp = datetime.fromtimestamp(ts / 1000 if ts > 1e10 else ts)
                else:
                    timestamp = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))

                price = float(item.get("p") or item.get("price", 0))

                points.append(
                    PricePoint(
                        timestamp=timestamp,
                        price=price,
                        bid=item.get("bid"),
                        ask=item.get("ask"),
                        volume=item.get("volume"),
                    )
                )

            except Exception as e:
                logger.debug(f"Error parsing price point: {e}")
                continue

        return sorted(points, key=lambda x: x.timestamp)

    # =========================================================================
    # ODDS CONVERSION
    # =========================================================================

    @staticmethod
    def _probability_to_american(prob: float) -> Optional[int]:
        """
        Convert probability to American odds.

        Args:
            prob: Probability (0-1)

        Returns:
            American odds
        """
        if prob <= 0 or prob >= 1:
            return None

        if prob >= 0.5:
            return int(-100 * prob / (1 - prob))
        else:
            return int(100 * (1 - prob) / prob)

    @staticmethod
    def probability_to_decimal(prob: float) -> Optional[float]:
        """
        Convert probability to decimal odds.

        Args:
            prob: Probability (0-1)

        Returns:
            Decimal odds
        """
        if prob <= 0 or prob >= 1:
            return None
        return 1 / prob

    @staticmethod
    def calculate_market_vig(yes_price: float, no_price: float) -> float:
        """
        Calculate market vig (vigorish/overround).

        Args:
            yes_price: Price of YES shares
            no_price: Price of NO shares

        Returns:
            Vig as a percentage (e.g., 0.02 for 2%)
        """
        total = yes_price + no_price
        return total - 1.0

    @staticmethod
    def calculate_no_vig_probability(yes_price: float, no_price: float) -> Tuple[float, float]:
        """
        Calculate vig-free probabilities.

        Args:
            yes_price: Price of YES shares
            no_price: Price of NO shares

        Returns:
            Tuple of (yes_prob, no_prob) without vig
        """
        total = yes_price + no_price
        if total == 0:
            return 0.5, 0.5
        return yes_price / total, no_price / total

    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================

    def store_markets(self, markets: List[PolymarketMarket]) -> int:
        """
        Store markets in SQLite database.

        Args:
            markets: List of PolymarketMarket objects

        Returns:
            Number of markets stored/updated
        """
        logger.info(f"Storing {len(markets)} markets in database")

        stored_count = 0

        with self.get_cursor() as cursor:
            for market in markets:
                try:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO polymarket_markets (
                            market_id, condition_id, question, description,
                            category, subcategory, end_date, tokens,
                            yes_price, no_price, yes_bid, yes_ask, no_bid, no_ask, spread,
                            volume, volume_24h, liquidity,
                            status, is_resolved, outcome,
                            url, image_url, updated_at, last_fetched
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                        (
                            market.market_id,
                            market.condition_id,
                            market.question,
                            market.description,
                            market.category,
                            market.subcategory,
                            market.end_date.isoformat() if market.end_date else None,
                            json.dumps(market.tokens),
                            market.yes_price,
                            market.no_price,
                            market.yes_bid,
                            market.yes_ask,
                            market.no_bid,
                            market.no_ask,
                            market.spread,
                            market.volume,
                            market.volume_24h,
                            market.liquidity,
                            market.status,
                            market.is_resolved,
                            market.outcome,
                            market.url,
                            market.image_url,
                        ),
                    )
                    stored_count += 1

                except Exception as e:
                    logger.warning(f"Failed to store market {market.market_id}: {e}")
                    continue

        logger.info(f"Stored {stored_count} markets")
        return stored_count

    def store_price_history(self, market_id: str, token_id: str, prices: List[PricePoint]) -> int:
        """
        Store price history in database.

        Args:
            market_id: Market ID
            token_id: Token ID
            prices: List of PricePoint objects

        Returns:
            Number of price points stored
        """
        logger.info(f"Storing {len(prices)} price points for {token_id}")

        stored_count = 0

        with self.get_cursor() as cursor:
            for point in prices:
                try:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO polymarket_price_history (
                            market_id, token_id, timestamp, price, bid, ask, volume
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            market_id,
                            token_id,
                            point.timestamp.isoformat(),
                            point.price,
                            point.bid,
                            point.ask,
                            point.volume,
                        ),
                    )
                    stored_count += 1

                except Exception as e:
                    logger.debug(f"Failed to store price point: {e}")
                    continue

        logger.info(f"Stored {stored_count} price points")
        return stored_count

    def get_stored_markets(
        self, category: Optional[str] = None, active_only: bool = True, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve markets from database.

        Args:
            category: Filter by category
            active_only: Only return non-resolved markets
            limit: Maximum number of markets

        Returns:
            List of market dictionaries
        """
        query = "SELECT * FROM polymarket_markets WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)

        if active_only:
            query += " AND is_resolved = FALSE"

        query += " ORDER BY volume DESC LIMIT ?"
        params.append(limit)

        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_price_history_from_db(
        self, market_id: str, token_id: Optional[str] = None, since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve price history from database.

        Args:
            market_id: Market ID to query
            token_id: Optional token ID filter
            since: Only return prices after this time

        Returns:
            List of price history records
        """
        query = "SELECT * FROM polymarket_price_history WHERE market_id = ?"
        params = [market_id]

        if token_id:
            query += " AND token_id = ?"
            params.append(token_id)

        if since:
            query += " AND timestamp > ?"
            params.append(since.isoformat())

        query += " ORDER BY timestamp ASC"

        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # =========================================================================
    # INTEGRATION WITH FORECASTING DB
    # =========================================================================

    def link_to_forecast(self, market_id: str, forecast_id: str) -> bool:
        """
        Link a Polymarket market to a forecast in the forecasting schema.

        Args:
            market_id: Polymarket market ID
            forecast_id: Forecast ID from forecasting_db

        Returns:
            True if successful
        """
        try:
            # Update the forecast with market reference
            with self.get_cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE forecasts
                    SET market_id = ?, platform = 'polymarket'
                    WHERE forecast_id = ?
                """,
                    (market_id, forecast_id),
                )

                if cursor.rowcount > 0:
                    logger.info(f"Linked market {market_id} to forecast {forecast_id}")
                    return True
                else:
                    logger.warning(f"Forecast not found: {forecast_id}")
                    return False

        except Exception as e:
            logger.error(f"Failed to link market to forecast: {e}")
            return False

    def create_forecast_from_market(
        self, market: PolymarketMarket, initial_probability: float, confidence: str = "medium"
    ) -> Optional[str]:
        """
        Create a forecast entry from a Polymarket market.

        Args:
            market: PolymarketMarket object
            initial_probability: Your initial probability estimate
            confidence: Confidence level

        Returns:
            Forecast ID if created, None otherwise
        """
        try:
            import uuid

            forecast_id = f"fc_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"

            # Calculate time horizon
            time_horizon = None
            if market.end_date:
                time_horizon = (market.end_date.date() - date.today()).days

            with self.get_cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO forecasts (
                        forecast_id, question_text, question_short,
                        question_category, platform, market_id, market_url,
                        initial_probability, current_probability,
                        initial_confidence, current_confidence,
                        initial_market_price, resolution_date_expected,
                        time_horizon_days, tags, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        forecast_id,
                        market.question,
                        market.question[:100] if market.question else None,
                        market.category,
                        "polymarket",
                        market.market_id,
                        market.url,
                        initial_probability,
                        initial_probability,
                        confidence,
                        confidence,
                        market.yes_price,
                        market.end_date.date() if market.end_date else None,
                        time_horizon,
                        market.subcategory,
                        market.description,
                    ),
                )

            logger.info(f"Created forecast {forecast_id} from market {market.market_id}")
            return forecast_id

        except Exception as e:
            logger.error(f"Failed to create forecast from market: {e}")
            return None

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def get_market_summary(self, market_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a summary of a market with current prices and stats.

        Args:
            market_id: Market ID

        Returns:
            Summary dictionary
        """
        market = self.fetch_market_by_id(market_id)
        if not market:
            return None

        summary = {
            "market_id": market.market_id,
            "question": market.question,
            "category": market.category,
            "status": market.status,
            "yes_price": market.yes_price,
            "no_price": market.no_price,
            "implied_yes_prob": market.yes_price,
            "implied_no_prob": market.no_price,
            "american_odds_yes": self._probability_to_american(market.yes_price)
            if market.yes_price
            else None,
            "american_odds_no": self._probability_to_american(market.no_price)
            if market.no_price
            else None,
            "volume": market.volume,
            "end_date": market.end_date.isoformat() if market.end_date else None,
            "url": market.url,
        }

        # Calculate vig if both prices available
        if market.yes_price and market.no_price:
            summary["vig"] = self.calculate_market_vig(market.yes_price, market.no_price)
            no_vig_yes, no_vig_no = self.calculate_no_vig_probability(
                market.yes_price, market.no_price
            )
            summary["no_vig_yes_prob"] = no_vig_yes
            summary["no_vig_no_prob"] = no_vig_no

        return summary

    def refresh_all_markets(self) -> int:
        """
        Refresh all stored markets with current data.

        Returns:
            Number of markets updated
        """
        logger.info("Refreshing all stored markets")

        stored = self.get_stored_markets(active_only=True, limit=1000)
        updated = 0

        for row in stored:
            market_id = row["market_id"]
            market = self.fetch_market_by_id(market_id)

            if market:
                self.store_markets([market])
                updated += 1

            # Rate limiting is handled in fetch methods

        logger.info(f"Refreshed {updated} markets")
        return updated

    def close(self) -> None:
        """Clean up resources."""
        self._session.close()
        logger.info("PolymarketFetcher closed")


# =============================================================================
# MAIN - Example Usage
# =============================================================================

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    print("=" * 70)
    print("POLYMARKET DATA FETCHER")
    print("=" * 70)

    # Initialize fetcher
    fetcher = PolymarketFetcher(db_path="data/betting.db")

    # Fetch sports markets
    print("\n[1] Fetching sports markets...")
    try:
        sports = fetcher.fetch_sports_markets()
        print(f"    Found {len(sports)} sports markets")

        if sports:
            print("\n    Top 5 sports markets by volume:")
            sorted_sports = sorted(sports, key=lambda x: x.volume or 0, reverse=True)[:5]
            for i, m in enumerate(sorted_sports, 1):
                vol_str = f"${m.volume:,.0f}" if m.volume else "N/A"
                price_str = f"{m.yes_price:.1%}" if m.yes_price else "N/A"
                print(f"    {i}. {m.question[:60]}...")
                print(f"       Yes Price: {price_str}, Volume: {vol_str}")
    except Exception as e:
        print(f"    Error fetching sports markets: {e}")
        sports = []

    # Fetch political markets
    print("\n[2] Fetching political/economic markets...")
    try:
        political = fetcher.fetch_political_markets()
        print(f"    Found {len(political)} political/economic markets")

        if political:
            print("\n    Top 5 political markets by volume:")
            sorted_political = sorted(political, key=lambda x: x.volume or 0, reverse=True)[:5]
            for i, m in enumerate(sorted_political, 1):
                vol_str = f"${m.volume:,.0f}" if m.volume else "N/A"
                price_str = f"{m.yes_price:.1%}" if m.yes_price else "N/A"
                print(f"    {i}. {m.question[:60]}...")
                print(f"       Yes Price: {price_str}, Volume: {vol_str}")
    except Exception as e:
        print(f"    Error fetching political markets: {e}")
        political = []

    # Store markets
    print("\n[3] Storing markets in database...")
    all_markets = sports + political
    if all_markets:
        stored = fetcher.store_markets(all_markets)
        print(f"    Stored {stored} markets in {fetcher.db_path}")
    else:
        print("    No markets to store")

    # Demo price fetching (if we have a market)
    if all_markets:
        print("\n[4] Fetching price for first market...")
        first_market = all_markets[0]
        if first_market.tokens:
            token_id = first_market.tokens[0].get("token_id", first_market.market_id)
            prices = fetcher.fetch_market_prices(token_id)
            if prices:
                print(f"    Token: {token_id}")
                print(f"    Mid Price: {prices.mid_price:.4f}")
                print(f"    Bid: {prices.best_bid:.4f}" if prices.best_bid else "    Bid: N/A")
                print(f"    Ask: {prices.best_ask:.4f}" if prices.best_ask else "    Ask: N/A")
                print(f"    Spread: {prices.spread:.4f}" if prices.spread else "    Spread: N/A")
            else:
                print("    Could not fetch prices")

    # Get market summary
    if all_markets:
        print("\n[5] Market summary example...")
        summary = fetcher.get_market_summary(all_markets[0].market_id)
        if summary:
            print(f"    Question: {summary['question'][:60]}...")
            print(f"    Category: {summary['category']}")
            print(
                f"    Yes Price: {summary['yes_price']:.1%}"
                if summary["yes_price"]
                else "    Yes Price: N/A"
            )
            if summary.get("american_odds_yes"):
                print(f"    American Odds (Yes): {summary['american_odds_yes']:+d}")
            if summary.get("vig"):
                print(f"    Market Vig: {summary['vig']:.2%}")

    # Clean up
    fetcher.close()

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
