"""Kalshi Data Fetcher.

Fetches prediction market data from Kalshi's REST API for political,
economic, and event markets. CFTC-regulated, US-legal platform.

API Documentation: https://trading-api.readme.io/reference
Kalshi Python SDK: pip install kalshi-python

Key Features:
    - Full API client with authentication (API key + token rotation)
    - Market fetching by category (politics, economics, climate, etc.)
    - Order book depth and price history
    - Position management integration
    - Rate limiting with exponential backoff
    - SQLite persistence with forecasting DB integration
"""

import sqlite3
import time
import logging
import hmac
import hashlib
import base64
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from contextlib import contextmanager
import json

try:
    import requests
except ImportError:
    raise ImportError("requests not installed. Run: pip install requests")


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTS
# =============================================================================

# Kalshi API endpoints
KALSHI_BASE_URL = "https://trading-api.kalshi.com/trade-api/v2"
KALSHI_DEMO_URL = "https://demo-api.kalshi.co/trade-api/v2"

# Rate limiting (Kalshi is more restrictive than Polymarket)
DEFAULT_RATE_LIMIT_DELAY = 0.5  # seconds between requests
MAX_REQUESTS_PER_MINUTE = 60
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # Base delay for exponential backoff

# Token rotation settings
TOKEN_REFRESH_BUFFER = 300  # Refresh token 5 min before expiry


# =============================================================================
# DATA CLASSES
# =============================================================================


class KalshiCategory(Enum):
    """Kalshi market categories."""

    POLITICS = "Politics"
    ECONOMICS = "Economics"
    CLIMATE = "Climate"
    SCIENCE = "Science"
    FINANCIAL = "Financial"
    CRYPTO = "Crypto"
    SPORTS = "Sports"
    ENTERTAINMENT = "Entertainment"
    OTHER = "Other"


class MarketStatus(Enum):
    """Market trading status."""

    ACTIVE = "open"
    CLOSED = "closed"
    SETTLED = "settled"


class OrderSide(Enum):
    """Order side for trading."""

    YES = "yes"
    NO = "no"


@dataclass
class KalshiMarket:
    """Represents a Kalshi prediction market."""

    ticker: str
    event_ticker: str
    title: str
    subtitle: Optional[str] = None
    category: str = "Other"

    # Market parameters
    yes_price: Optional[float] = None  # 0-100 cents
    no_price: Optional[float] = None
    yes_bid: Optional[float] = None
    yes_ask: Optional[float] = None
    no_bid: Optional[float] = None
    no_ask: Optional[float] = None
    spread: Optional[float] = None  # In cents

    # Volume and liquidity
    volume: Optional[int] = None  # Number of contracts
    volume_24h: Optional[int] = None
    open_interest: Optional[int] = None
    dollar_volume: Optional[float] = None

    # Market timing
    open_time: Optional[datetime] = None
    close_time: Optional[datetime] = None
    expiration_time: Optional[datetime] = None

    # Status and result
    status: str = "open"
    result: Optional[str] = None  # "yes", "no", or None if not settled
    settled_price: Optional[float] = None

    # Strike price for ranged markets (e.g., "Will GDP growth be above 2%?")
    strike_type: Optional[str] = None
    floor_strike: Optional[float] = None
    cap_strike: Optional[float] = None

    # Fee structure
    taker_fee_rate: float = 0.012  # 1.2% default

    # Metadata
    url: Optional[str] = None
    rules_primary: Optional[str] = None
    settlement_source: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        for key in ["open_time", "close_time", "expiration_time", "created_at", "updated_at"]:
            if data[key] is not None and isinstance(data[key], datetime):
                data[key] = data[key].isoformat()
        return data

    @property
    def implied_prob_yes(self) -> Optional[float]:
        """Get implied probability for YES outcome."""
        if self.yes_price is not None:
            return self.yes_price / 100.0
        return None

    @property
    def effective_vig(self) -> Optional[float]:
        """Calculate effective vig from bid-ask spread."""
        if self.yes_bid and self.yes_ask:
            spread = self.yes_ask - self.yes_bid
            mid = (self.yes_ask + self.yes_bid) / 2
            if mid > 0:
                return spread / (2 * mid)
        return None


@dataclass
class KalshiPosition:
    """Represents a position in a Kalshi market."""

    ticker: str
    side: str  # "yes" or "no"
    quantity: int
    avg_entry_price: float  # In cents
    market_price: float  # Current price
    unrealized_pnl: float
    realized_pnl: float = 0.0

    @property
    def total_value(self) -> float:
        """Calculate total position value in dollars."""
        return (self.quantity * self.market_price) / 100.0


@dataclass
class OrderBookLevel:
    """Single level in the order book."""

    price: int  # In cents (1-99)
    quantity: int


@dataclass
class KalshiOrderBook:
    """Order book snapshot for a market."""

    ticker: str
    timestamp: datetime
    yes_bids: list[OrderBookLevel] = field(default_factory=list)
    yes_asks: list[OrderBookLevel] = field(default_factory=list)

    @property
    def best_bid(self) -> Optional[int]:
        """Get best bid price."""
        if self.yes_bids:
            return max(level.price for level in self.yes_bids)
        return None

    @property
    def best_ask(self) -> Optional[int]:
        """Get best ask price."""
        if self.yes_asks:
            return min(level.price for level in self.yes_asks)
        return None

    @property
    def spread(self) -> Optional[int]:
        """Get bid-ask spread in cents."""
        bid = self.best_bid
        ask = self.best_ask
        if bid is not None and ask is not None:
            return ask - bid
        return None


# =============================================================================
# KALSHI FETCHER
# =============================================================================


class KalshiFetcher:
    """Fetches and manages Kalshi prediction market data.

    Features:
        - API key authentication with token rotation
        - Market data fetching by category
        - Order book and price history
        - Position management
        - SQLite persistence
        - Rate limiting with exponential backoff
        - Forecasting DB integration

    Example:
        ```python
        fetcher = KalshiFetcher(
            api_key="your_api_key",  # pragma: allowlist secret
            api_secret="your_api_secret"  # pragma: allowlist secret
        )

        # Fetch political markets
        markets = fetcher.fetch_markets(category="Politics")

        # Get specific market
        market = fetcher.fetch_market("PRES-2024-DEM")

        # Get order book
        order_book = fetcher.fetch_order_book("PRES-2024-DEM")

        # Store to database
        fetcher.store_markets(markets)
        ```
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        db_path: str = "data/betting.db",
        use_demo: bool = False,
        rate_limit_delay: float = DEFAULT_RATE_LIMIT_DELAY,
    ):
        """Initialize Kalshi fetcher.

        Args:
            api_key: Kalshi API key (optional for public data).
            api_secret: Kalshi API secret for signing requests.
            db_path: Path to SQLite database.
            use_demo: Use demo API instead of production.
            rate_limit_delay: Delay between requests in seconds.
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.db_path = Path(db_path)
        self.base_url = KALSHI_DEMO_URL if use_demo else KALSHI_BASE_URL
        self.rate_limit_delay = rate_limit_delay

        # Token management
        self._access_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

        # Rate limiting state
        self._last_request_time = 0.0
        self._request_count = 0
        self._minute_start = time.time()

        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

        # Initialize database schema
        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema for Kalshi data."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._get_db() as conn:
            conn.executescript(
                """
                -- Kalshi markets table
                CREATE TABLE IF NOT EXISTS kalshi_markets (
                    ticker TEXT PRIMARY KEY,
                    event_ticker TEXT NOT NULL,
                    title TEXT NOT NULL,
                    subtitle TEXT,
                    category TEXT,
                    yes_price REAL,
                    no_price REAL,
                    yes_bid REAL,
                    yes_ask REAL,
                    spread REAL,
                    volume INTEGER,
                    volume_24h INTEGER,
                    open_interest INTEGER,
                    dollar_volume REAL,
                    open_time TEXT,
                    close_time TEXT,
                    expiration_time TEXT,
                    status TEXT,
                    result TEXT,
                    settled_price REAL,
                    strike_type TEXT,
                    floor_strike REAL,
                    cap_strike REAL,
                    taker_fee_rate REAL DEFAULT 0.012,
                    url TEXT,
                    rules_primary TEXT,
                    settlement_source TEXT,
                    created_at TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP
                );

                -- Kalshi price history table
                CREATE TABLE IF NOT EXISTS kalshi_price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    yes_price REAL,
                    yes_bid REAL,
                    yes_ask REAL,
                    volume INTEGER,
                    open_interest INTEGER,
                    FOREIGN KEY (ticker) REFERENCES kalshi_markets(ticker),
                    UNIQUE(ticker, timestamp)
                );

                -- Kalshi positions table
                CREATE TABLE IF NOT EXISTS kalshi_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    avg_entry_price REAL NOT NULL,
                    entry_timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                    exit_timestamp TEXT,
                    exit_price REAL,
                    realized_pnl REAL,
                    forecast_id INTEGER,
                    notes TEXT,
                    FOREIGN KEY (ticker) REFERENCES kalshi_markets(ticker),
                    FOREIGN KEY (forecast_id) REFERENCES forecasts(id)
                );

                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_kalshi_markets_category
                    ON kalshi_markets(category);
                CREATE INDEX IF NOT EXISTS idx_kalshi_markets_status
                    ON kalshi_markets(status);
                CREATE INDEX IF NOT EXISTS idx_kalshi_price_history_ticker_ts
                    ON kalshi_price_history(ticker, timestamp);
                CREATE INDEX IF NOT EXISTS idx_kalshi_positions_ticker
                    ON kalshi_positions(ticker);
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

    def _sign_request(
        self,
        method: str,
        path: str,
        timestamp: str,
    ) -> str:
        """Generate HMAC signature for authenticated requests.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path.
            timestamp: ISO timestamp.

        Returns:
            Base64-encoded signature.
        """
        if not self.api_secret:
            raise ValueError("API secret required for authenticated requests")

        message = f"{timestamp}{method}{path}"
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return base64.b64encode(signature).decode("utf-8")

    def _get_auth_headers(self, method: str, path: str) -> dict[str, str]:
        """Get authentication headers for request.

        Args:
            method: HTTP method.
            path: API path.

        Returns:
            Headers dict with authentication.
        """
        if not self.api_key or not self.api_secret:
            return {}

        timestamp = datetime.now(timezone.utc).isoformat()
        signature = self._sign_request(method, path, timestamp)

        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-SIGNATURE": signature,
            "KALSHI-ACCESS-TIMESTAMP": timestamp,
        }

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        current_time = time.time()

        # Reset minute counter
        if current_time - self._minute_start >= 60:
            self._request_count = 0
            self._minute_start = current_time

        # Check minute limit
        if self._request_count >= MAX_REQUESTS_PER_MINUTE:
            sleep_time = 60 - (current_time - self._minute_start)
            if sleep_time > 0:
                logger.info(f"Rate limit reached, sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)
            self._request_count = 0
            self._minute_start = time.time()

        # Apply per-request delay
        elapsed = current_time - self._last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)

        self._last_request_time = time.time()
        self._request_count += 1

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        data: Optional[dict] = None,
        authenticated: bool = False,
    ) -> dict[str, Any]:
        """Make API request with rate limiting and retries.

        Args:
            method: HTTP method.
            path: API path (without base URL).
            params: Query parameters.
            data: Request body.
            authenticated: Whether to include auth headers.

        Returns:
            JSON response data.

        Raises:
            requests.HTTPError: On API error after retries.
        """
        self._rate_limit()

        url = f"{self.base_url}{path}"
        headers = {}

        if authenticated:
            headers.update(self._get_auth_headers(method, path))

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data,
                    headers=headers,
                    timeout=30,
                )
                response.raise_for_status()
                return response.json()

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:  # Rate limited
                    wait_time = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(f"Rate limited, waiting {wait_time}s")
                    time.sleep(wait_time)
                elif e.response.status_code >= 500:  # Server error
                    wait_time = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(f"Server error, retry {attempt + 1}/{MAX_RETRIES}")
                    time.sleep(wait_time)
                else:
                    raise
            except requests.exceptions.RequestException as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(f"Request failed: {e}, retry {attempt + 1}/{MAX_RETRIES}")
                    time.sleep(wait_time)
                else:
                    raise

        raise requests.HTTPError(f"Failed after {MAX_RETRIES} retries")

    # -------------------------------------------------------------------------
    # MARKET DATA
    # -------------------------------------------------------------------------

    def fetch_markets(
        self,
        category: Optional[str] = None,
        status: str = "open",
        limit: int = 100,
        cursor: Optional[str] = None,
    ) -> list[KalshiMarket]:
        """Fetch markets from Kalshi.

        Args:
            category: Filter by category (e.g., "Politics", "Economics").
            status: Market status filter ("open", "closed", "settled").
            limit: Maximum markets to return (max 100).
            cursor: Pagination cursor.

        Returns:
            List of KalshiMarket objects.
        """
        params = {
            "limit": min(limit, 100),
            "status": status,
        }
        if category:
            params["series_ticker"] = category
        if cursor:
            params["cursor"] = cursor

        response = self._request("GET", "/markets", params=params)
        markets = []

        for market_data in response.get("markets", []):
            market = self._parse_market(market_data)
            markets.append(market)

        logger.info(f"Fetched {len(markets)} markets")
        return markets

    def fetch_market(self, ticker: str) -> Optional[KalshiMarket]:
        """Fetch a single market by ticker.

        Args:
            ticker: Market ticker (e.g., "PRES-2024-DEM").

        Returns:
            KalshiMarket or None if not found.
        """
        try:
            response = self._request("GET", f"/markets/{ticker}")
            if "market" in response:
                return self._parse_market(response["market"])
        except requests.HTTPError as e:
            if e.response.status_code == 404:
                logger.warning(f"Market {ticker} not found")
                return None
            raise
        return None

    def fetch_order_book(self, ticker: str, depth: int = 10) -> Optional[KalshiOrderBook]:
        """Fetch order book for a market.

        Args:
            ticker: Market ticker.
            depth: Number of levels to fetch (max 100).

        Returns:
            KalshiOrderBook or None if not available.
        """
        try:
            response = self._request(
                "GET",
                f"/markets/{ticker}/orderbook",
                params={"depth": min(depth, 100)},
            )

            order_book = KalshiOrderBook(
                ticker=ticker,
                timestamp=datetime.now(timezone.utc),
            )

            for bid in response.get("yes", {}).get("bids", []):
                order_book.yes_bids.append(OrderBookLevel(price=bid[0], quantity=bid[1]))

            for ask in response.get("yes", {}).get("asks", []):
                order_book.yes_asks.append(OrderBookLevel(price=ask[0], quantity=ask[1]))

            return order_book

        except requests.HTTPError:
            logger.warning(f"Could not fetch order book for {ticker}")
            return None

    def fetch_price_history(
        self,
        ticker: str,
        start_ts: Optional[datetime] = None,
        end_ts: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """Fetch price history for a market.

        Args:
            ticker: Market ticker.
            start_ts: Start timestamp.
            end_ts: End timestamp.

        Returns:
            List of price history points.
        """
        params = {}
        if start_ts:
            params["min_ts"] = int(start_ts.timestamp())
        if end_ts:
            params["max_ts"] = int(end_ts.timestamp())

        try:
            response = self._request(
                "GET",
                f"/markets/{ticker}/history",
                params=params,
            )
            return response.get("history", [])
        except requests.HTTPError:
            logger.warning(f"Could not fetch history for {ticker}")
            return []

    def _parse_market(self, data: dict[str, Any]) -> KalshiMarket:
        """Parse market data from API response.

        Args:
            data: Raw market data dict.

        Returns:
            KalshiMarket object.
        """

        def parse_datetime(value: Any) -> Optional[datetime]:
            if not value:
                return None
            if isinstance(value, int):
                return datetime.fromtimestamp(value, tz=timezone.utc)
            if isinstance(value, str):
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    return None
            return None

        yes_price = data.get("yes_bid")
        no_price = data.get("no_bid")
        if yes_price is None and no_price is not None:
            yes_price = 100 - no_price

        return KalshiMarket(
            ticker=data.get("ticker", ""),
            event_ticker=data.get("event_ticker", ""),
            title=data.get("title", ""),
            subtitle=data.get("subtitle"),
            category=data.get("category", "Other"),
            yes_price=yes_price,
            no_price=no_price,
            yes_bid=data.get("yes_bid"),
            yes_ask=data.get("yes_ask"),
            no_bid=data.get("no_bid"),
            no_ask=data.get("no_ask"),
            spread=data.get("spread"),
            volume=data.get("volume"),
            volume_24h=data.get("volume_24h"),
            open_interest=data.get("open_interest"),
            dollar_volume=data.get("dollar_volume"),
            open_time=parse_datetime(data.get("open_time")),
            close_time=parse_datetime(data.get("close_time")),
            expiration_time=parse_datetime(data.get("expiration_time")),
            status=data.get("status", "open"),
            result=data.get("result"),
            settled_price=data.get("settlement_price"),
            strike_type=data.get("strike_type"),
            floor_strike=data.get("floor_strike"),
            cap_strike=data.get("cap_strike"),
            taker_fee_rate=data.get("taker_fee_rate", 0.012),
            url=f"https://kalshi.com/markets/{data.get('ticker', '')}",
            rules_primary=data.get("rules_primary"),
            settlement_source=data.get("settlement_source"),
        )

    # -------------------------------------------------------------------------
    # DATABASE OPERATIONS
    # -------------------------------------------------------------------------

    def store_markets(self, markets: list[KalshiMarket]) -> int:
        """Store markets to database.

        Args:
            markets: List of markets to store.

        Returns:
            Number of markets stored/updated.
        """
        with self._get_db() as conn:
            count = 0
            for market in markets:
                data = market.to_dict()
                conn.execute(
                    """
                    INSERT OR REPLACE INTO kalshi_markets (
                        ticker, event_ticker, title, subtitle, category,
                        yes_price, no_price, yes_bid, yes_ask, spread,
                        volume, volume_24h, open_interest, dollar_volume,
                        open_time, close_time, expiration_time,
                        status, result, settled_price,
                        strike_type, floor_strike, cap_strike,
                        taker_fee_rate, url, rules_primary, settlement_source,
                        fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        data["ticker"],
                        data["event_ticker"],
                        data["title"],
                        data["subtitle"],
                        data["category"],
                        data["yes_price"],
                        data["no_price"],
                        data["yes_bid"],
                        data["yes_ask"],
                        data["spread"],
                        data["volume"],
                        data["volume_24h"],
                        data["open_interest"],
                        data["dollar_volume"],
                        data["open_time"],
                        data["close_time"],
                        data["expiration_time"],
                        data["status"],
                        data["result"],
                        data["settled_price"],
                        data["strike_type"],
                        data["floor_strike"],
                        data["cap_strike"],
                        data["taker_fee_rate"],
                        data["url"],
                        data["rules_primary"],
                        data["settlement_source"],
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                count += 1

        logger.info(f"Stored {count} markets")
        return count

    def store_price_snapshot(self, market: KalshiMarket) -> None:
        """Store current price as historical snapshot.

        Args:
            market: Market with current price data.
        """
        with self._get_db() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO kalshi_price_history (
                    ticker, timestamp, yes_price, yes_bid, yes_ask,
                    volume, open_interest
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    market.ticker,
                    datetime.now(timezone.utc).isoformat(),
                    market.yes_price,
                    market.yes_bid,
                    market.yes_ask,
                    market.volume,
                    market.open_interest,
                ),
            )

    def get_stored_markets(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get markets from database.

        Args:
            category: Filter by category.
            status: Filter by status.

        Returns:
            List of market dicts.
        """
        query = "SELECT * FROM kalshi_markets WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY volume_24h DESC"

        with self._get_db() as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    # -------------------------------------------------------------------------
    # POSITION MANAGEMENT
    # -------------------------------------------------------------------------

    def record_position(
        self,
        ticker: str,
        side: str,
        quantity: int,
        entry_price: float,
        forecast_id: Optional[int] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Record a new position.

        Args:
            ticker: Market ticker.
            side: "yes" or "no".
            quantity: Number of contracts.
            entry_price: Entry price in cents.
            forecast_id: Optional link to forecast.
            notes: Optional notes.

        Returns:
            Position ID.
        """
        with self._get_db() as conn:
            cursor = conn.execute(
                """
                INSERT INTO kalshi_positions (
                    ticker, side, quantity, avg_entry_price,
                    forecast_id, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
            """,
                (ticker, side, quantity, entry_price, forecast_id, notes),
            )
            return cursor.lastrowid

    def close_position(
        self,
        position_id: int,
        exit_price: float,
    ) -> float:
        """Close a position and calculate P&L.

        Args:
            position_id: Position ID.
            exit_price: Exit price in cents.

        Returns:
            Realized P&L in cents.
        """
        with self._get_db() as conn:
            row = conn.execute(
                "SELECT * FROM kalshi_positions WHERE id = ?", (position_id,)
            ).fetchone()

            if not row:
                raise ValueError(f"Position {position_id} not found")

            # Calculate P&L
            entry = row["avg_entry_price"]
            quantity = row["quantity"]
            side = row["side"]

            if side == "yes":
                pnl = (exit_price - entry) * quantity
            else:  # no
                pnl = (entry - exit_price) * quantity

            # Update position
            conn.execute(
                """
                UPDATE kalshi_positions
                SET exit_timestamp = ?,
                    exit_price = ?,
                    realized_pnl = ?
                WHERE id = ?
            """,
                (
                    datetime.now(timezone.utc).isoformat(),
                    exit_price,
                    pnl,
                    position_id,
                ),
            )

            return pnl

    # -------------------------------------------------------------------------
    # FORECASTING DB INTEGRATION
    # -------------------------------------------------------------------------

    def link_to_forecast(
        self,
        ticker: str,
        forecast_id: int,
    ) -> None:
        """Link a market to a forecast in the forecasting DB.

        Args:
            ticker: Market ticker.
            forecast_id: Forecast ID from forecasting_db.
        """
        with self._get_db() as conn:
            conn.execute(
                """
                UPDATE kalshi_positions
                SET forecast_id = ?
                WHERE ticker = ? AND forecast_id IS NULL
            """,
                (forecast_id, ticker),
            )

    def create_forecast_from_market(
        self,
        market: KalshiMarket,
        probability: float,
        confidence: str = "MEDIUM",
    ) -> Optional[int]:
        """Create a forecast entry from a Kalshi market.

        Note: Requires forecasting_db module.

        Args:
            market: Kalshi market.
            probability: Your probability estimate (0-1).
            confidence: Confidence level.

        Returns:
            Forecast ID if created, None otherwise.
        """
        try:
            from tracking.forecasting_db import ForecastingDatabase

            db = ForecastingDatabase(str(self.db_path))
            forecast_id = db.create_forecast(
                question_text=market.title,
                platform="kalshi",
                external_id=market.ticker,
                category="PREDICTION_MARKET",
                initial_probability=probability,
                market_probability=market.implied_prob_yes,
                close_date=market.close_time,
                confidence=confidence,
            )
            return forecast_id

        except ImportError:
            logger.warning("forecasting_db not available")
            return None


# =============================================================================
# CLI INTERFACE
# =============================================================================


def main():
    """CLI entry point for Kalshi fetcher."""
    import argparse

    parser = argparse.ArgumentParser(description="Kalshi Data Fetcher")
    parser.add_argument("--category", help="Filter by category")
    parser.add_argument("--status", default="open", help="Market status filter")
    parser.add_argument("--limit", type=int, default=50, help="Max markets to fetch")
    parser.add_argument("--db", default="data/betting.db", help="Database path")
    parser.add_argument("--demo", action="store_true", help="Use demo API")
    parser.add_argument("--ticker", help="Fetch specific market by ticker")
    parser.add_argument("--store", action="store_true", help="Store to database")

    args = parser.parse_args()

    # Initialize fetcher (no auth for public data)
    fetcher = KalshiFetcher(
        db_path=args.db,
        use_demo=args.demo,
    )

    if args.ticker:
        # Fetch single market
        market = fetcher.fetch_market(args.ticker)
        if market:
            print(json.dumps(market.to_dict(), indent=2, default=str))
        else:
            print(f"Market {args.ticker} not found")
    else:
        # Fetch markets
        markets = fetcher.fetch_markets(
            category=args.category,
            status=args.status,
            limit=args.limit,
        )

        print(f"\nFetched {len(markets)} markets:")
        for market in markets[:10]:  # Show first 10
            print(f"  {market.ticker}: {market.title}")
            if market.yes_price:
                print(f"    YES: {market.yes_price}c | Volume: {market.volume}")

        if args.store:
            count = fetcher.store_markets(markets)
            print(f"\nStored {count} markets to {args.db}")


if __name__ == "__main__":
    main()
