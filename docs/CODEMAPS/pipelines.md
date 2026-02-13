# Pipelines Module Codemap

**Last Updated:** 2026-02-12
**Entry Point:** `pipelines/__init__.py` (empty)
**Test Coverage:** `tests/test_forecasting_db.py` (indirect, via forecasting DB integration)

## Architecture

```text
pipelines/
  __init__.py                  # Empty package marker
  ncaab_data_fetcher.py        # NCAAB game data via sportsipy
  polymarket_fetcher.py        # Polymarket prediction market data (CLOB + Gamma APIs)
  kalshi_fetcher.py            # Kalshi prediction market data (CFTC-regulated)
  batch_fetcher.py             # Async parallel data retrieval (aiohttp)
  closing_odds_collector.py    # Selenium-based closing odds scraper for CLV
  arb_scanner.py               # CLI wrapper for betting.arb_detector
```

## Key Modules

### ncaab_data_fetcher.py

Fetches NCAA Men's Basketball data using the sportsipy library.

| Export | Type | Purpose |
|--------|------|---------|
| `NCAABDataFetcher` | class | Fetches teams, schedules, game results by season |

**Key Methods:**

- `fetch_teams(season)` - All team info for a season -> DataFrame
- `fetch_schedule(team_id, season)` - Team schedule and results
- `fetch_boxscores(date)` - Game boxscores for a specific date

**Dependencies:** sportsipy (sportsipy.ncaab.teams, schedule, boxscore), pandas
**Output:** Saves raw data to `data/raw/ncaab/`

### polymarket_fetcher.py

Full API client for Polymarket's CLOB and Gamma APIs.

| Export | Type | Purpose |
|--------|------|---------|
| `PolymarketFetcher` | class | Fetches markets, prices, order books from Polymarket |
| `MarketCategory` | enum | SPORTS, POLITICS, CRYPTO, ECONOMICS, SCIENCE, ENTERTAINMENT, OTHER |
| `MarketStatus` | enum | Market trading status |

**API Endpoints:**

- CLOB API: `https://clob.polymarket.com` - Trading data, order books
- Gamma API: `https://gamma-api.polymarket.com` - Market metadata
- Strapi API: `https://strapi-matic.polymarket.com` - Content

**Key Methods:**

- `fetch_political_markets()` - Political prediction markets
- `fetch_markets_by_category(category)` - Markets filtered by category
- `get_market_prices(market_id)` - Current price data
- `get_order_book(market_id)` - Order book depth

**Rate Limiting:** 100 requests/min, 1.0s delay between requests, exponential backoff on retry

**Dependencies:** requests, py-clob-client (optional), sqlite3 (for persistence)

### kalshi_fetcher.py

API client for Kalshi's CFTC-regulated prediction market platform.

| Export | Type | Purpose |
|--------|------|---------|
| `KalshiFetcher` | class | Fetches political, economic, event markets from Kalshi |

**API Endpoints:**

- Production: `https://trading-api.kalshi.com/trade-api/v2`
- Demo: `https://demo-api.kalshi.co/trade-api/v2`

**Key Methods:**

- `fetch_political_markets()` - Political markets
- `fetch_economic_markets()` - Economic indicators markets
- `get_market_prices(market_id)` - Price data
- `get_order_book(market_id)` - Order book depth

**Authentication:** API key + HMAC signature with token rotation (5 min refresh buffer)
**Rate Limiting:** 60 requests/min, 0.5s delay, exponential backoff

### batch_fetcher.py

Async parallel data retrieval for 75%+ time reduction.

| Export | Type | Purpose |
|--------|------|---------|
| `BatchFetcher` | class | Async parallel API calls with rate limiting |

**Performance Targets:**

- Polymarket: 60s -> 15s (75% reduction)
- Kalshi: 30s -> 10s (67% reduction)
- NCAAB: 100s -> 25s (75% reduction)

**Key Methods:**

- `fetch_polymarket_batch(categories)` - Parallel Polymarket fetching
- `fetch_polymarket_batch_sync(categories)` - Synchronous wrapper
- `fetch_kalshi_batch(categories)` - Parallel Kalshi fetching

**Dependencies:** aiohttp (optional), asyncio, hashlib (cache keys)
**Zero-Cost:** All operations use free APIs only, no paid tier upgrades

### closing_odds_collector.py

Selenium-based closing odds scraper for CLV validation.

| Export | Type | Purpose |
|--------|------|---------|
| `ClosingOddsCollector` | class | Scrapes closing odds from sportsbooks before game start |

**Target Sportsbooks:** DraftKings (primary), FanDuel (backup), BetMGM (backup)

**Operation:**

- Runs as cron job 15 minutes before each game
- Uses headless Chrome via Selenium
- Updates `bets.odds_closing` column for CLV calculation
- ~15 seconds per game, 2-4 minutes/day typical

**Dependencies:** selenium, sqlite3
**CLI:** `python pipelines/closing_odds_collector.py --minutes-before 15`

### arb_scanner.py

CLI wrapper and pipeline integration point for arbitrage detection.

| Export | Type | Purpose |
|--------|------|---------|
| `scan_for_arbs()` | function | Main integration point for arb scanning |

**Usage:**

```bash
python -m pipelines.arb_scanner              # Scan all upcoming games
python -m pipelines.arb_scanner --sport NCAAB  # Filter by sport
python -m pipelines.arb_scanner --json        # Output as JSON
```

**Dependencies:** betting.arb_detector (ArbDetector, ArbOpportunity)

## Data Flow

```text
External APIs / Web Scraping
         |
         +-- ncaab_data_fetcher.py --> data/raw/ncaab/ (CSV files)
         |
         +-- polymarket_fetcher.py --> tracking/forecasting_db.py (SQLite)
         |
         +-- kalshi_fetcher.py ------> tracking/forecasting_db.py (SQLite)
         |
         +-- batch_fetcher.py -------> (wraps above for parallel execution)
         |
         +-- closing_odds_collector.py --> bets.odds_closing (SQLite)
         |
         +-- arb_scanner.py ---------> arb_opportunities (SQLite)
```

## External Dependencies

| Package | Used In | Required | Purpose |
|---------|---------|----------|---------|
| sportsipy | ncaab_data_fetcher.py | Yes | NCAAB data (Teams, Schedule, Boxscores) |
| requests | polymarket_fetcher.py, kalshi_fetcher.py | Yes | HTTP requests |
| py-clob-client | polymarket_fetcher.py | Optional | Polymarket CLOB API client |
| aiohttp | batch_fetcher.py | Optional | Async HTTP for parallel fetching |
| selenium | closing_odds_collector.py | Optional | Headless Chrome for odds scraping |

## Related Areas

- [betting.md](betting.md) - arb_detector consumed by arb_scanner
- [tracking.md](tracking.md) - Fetched data persisted to SQLite via database.py and forecasting_db.py
- [config.md](config.md) - RATE_LIMITS and PAID_APIS_BLOCKED enforce zero-cost constraint
- [models.md](models.md) - ncaab_data_fetcher provides training data for Elo models
