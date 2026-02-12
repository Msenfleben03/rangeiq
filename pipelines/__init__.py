"""Data Pipelines Module.

This module provides data fetching and processing pipelines for:
- Polymarket prediction markets
- Kalshi prediction markets (CFTC-regulated, US legal)
- Arbitrage scanning across sportsbooks
- Sports data ingestion (future)

Example:
    ```python
    from pipelines import PolymarketFetcher, KalshiFetcher, scan_for_arbs

    # Fetch Polymarket data
    poly_fetcher = PolymarketFetcher()
    poly_markets = poly_fetcher.fetch_political_markets()

    # Fetch Kalshi data
    kalshi_fetcher = KalshiFetcher()
    kalshi_markets = kalshi_fetcher.fetch_markets(category="Politics")

    # Scan for arbitrage opportunities
    arbs = scan_for_arbs(sport="NCAAB")
    ```
"""

from pipelines.polymarket_fetcher import (
    PolymarketFetcher,
    PolymarketMarket,
    MarketCategory,
    MarketStatus,
    PricePoint,
)

from pipelines.kalshi_fetcher import (
    KalshiFetcher,
    KalshiMarket,
    KalshiCategory,
    KalshiPosition,
    KalshiOrderBook,
    OrderBookLevel,
    OrderSide,
)

from pipelines.arb_scanner import (
    scan_for_arbs,
    scan_single_game,
    format_arb_alert,
)

__all__ = [
    # Polymarket
    "PolymarketFetcher",
    "PolymarketMarket",
    "MarketCategory",
    "MarketStatus",
    "PricePoint",
    # Kalshi
    "KalshiFetcher",
    "KalshiMarket",
    "KalshiCategory",
    "KalshiPosition",
    "KalshiOrderBook",
    "OrderBookLevel",
    "OrderSide",
    # Arbitrage
    "scan_for_arbs",
    "scan_single_game",
    "format_arb_alert",
]
