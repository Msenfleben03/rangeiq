# Pipelines Module Codemap

**Last Updated:** 2026-02-12
**Entry Point:** `pipelines/__init__.py` (empty)
**Test Coverage:** `tests/test_forecasting_db.py` (indirect), `tests/test_odds_providers.py`

## Architecture

```text
pipelines/
  __init__.py                  # Empty package marker
  # === Odds Retrieval (Strategy Pattern) ===
  odds_providers.py            # 4 providers: Manual, TheOddsAPI, ESPN, Scraper
  odds_orchestrator.py         # Fallback chain, caching, credit budget, DB persistence
  # === Data Fetching ===
  ncaab_data_fetcher.py        # NCAAB game data via sportsipy
  polymarket_fetcher.py        # Polymarket prediction market data (CLOB + Gamma APIs)
  kalshi_fetcher.py            # Kalshi prediction market data (CFTC-regulated)
  batch_fetcher.py             # Async parallel data retrieval (aiohttp)
  # === CLV & Arbitrage ===
  closing_odds_collector.py    # Selenium-based closing odds scraper for CLV
  arb_scanner.py               # CLI wrapper for betting.arb_detector
```

## Odds Retrieval System

### odds_providers.py

Strategy-pattern architecture with 4 interchangeable odds data sources sharing a common `OddsProvider` ABC.

**Abstract Base:**

| Method | Signature | Purpose |
|--------|-----------|---------|
| `fetch_game_odds()` | `(sport, home, away, game_id) -> Optional[ClosingOdds]` | Single game odds |
| `fetch_slate_odds()` | `(sport, date) -> list[ClosingOdds]` | Full slate for a date |
| `provider_name` | property -> str | Human-readable name |
| `is_available` | property -> bool | Whether provider is usable |
| `cost_per_request` | property -> float | Cost per call (0.0 for free) |

**Providers:**

| Provider | Source | Cost | Confidence | Notes |
|----------|--------|------|------------|-------|
| `ManualOddsProvider` | CSV file | Free | 1.0 | Human-verified, always available if CSV exists |
| `TheOddsAPIProvider` | the-odds-api.com | Free (500 credits/mo) | 0.95 | Credit tracking via response headers |
| `ESPNOddsProvider` | ESPN scoreboard API | Free | 0.80 | Undocumented endpoints, 2 req/sec rate limit |
| `ScraperOddsProvider` | Selenium (DraftKings/FanDuel) | Free | N/A | Wraps ClosingOddsCollector, no slate support |

**Helpers:** `_safe_float()`, `_safe_int()`, `_normalize_team_name()`, `_fuzzy_match()`, `_fuzzy_match_any()`

**Sport Key Mappings:** `ODDS_API_SPORT_KEYS` (ncaab, nba, nfl, ncaaf, mlb), `ESPN_SPORT_PATHS`

**Dependencies:** requests (optional), pipelines.closing_odds_collector (ClosingOdds dataclass)

### odds_orchestrator.py

Manages odds retrieval across providers with automatic fallback, response caching, credit budget tracking, and database persistence.

**Fallback Chain (auto mode):** TheOddsAPI -> ESPN -> Selenium Scraper -> Cached Data -> None

| Export | Type | Purpose |
|--------|------|---------|
| `OddsOrchestrator` | class | Main entry point for all odds retrieval |
| `OddsCache` | class | TTL-based response cache (default 5 min) |
| `CacheEntry` | dataclass | Cached odds with TTL and age tracking |
| `CreditBudget` | class | Monthly API credit tracking and enforcement |
| `VALID_MODES` | set | auto, manual, api, espn, scraper, agent |

**Key Methods on OddsOrchestrator:**

- `add_provider(provider)` - Add to fallback chain (order matters)
- `register_default_providers(api_key, csv_path)` - Standard chain setup
- `fetch_odds(sport, home, away, game_id, mode)` - Single game with fallback
- `fetch_slate(sport, date, mode)` - Full date slate with fallback
- `store_odds(odds)` - Persist to odds_snapshots table
- `get_credit_budget()` - Current API credit status
- `get_provider_health()` - Provider availability and success rates

**CreditBudget:**

- Tracks usage in `data/odds_api_usage.json`
- Auto-resets on month boundaries
- Warning at 80%, cutoff at 90% of 500 monthly credits
- Skips API provider when over budget

**Dependencies:** pipelines.odds_providers (all 4 providers), pipelines.closing_odds_collector (ClosingOdds)

## Data Fetching

### ncaab_data_fetcher.py

Fetches NCAA Men's Basketball data using the sportsipy library.

| Export | Type | Purpose |
|--------|------|---------|
| `NCAABDataFetcher` | class | Fetches teams, schedules, game results by season |

**Key Methods:**

- `fetch_teams(season)` - All team info for a season -> DataFrame
- `fetch_schedule(team_id, season)` - Team schedule and results
- `fetch_boxscores(date)` - Game boxscores for a specific date
- `fetch_season_data(season, delay)` - Full season data with rate limiting
- `fetch_games_by_date(target_date)` - Games for daily predictions

**Dependencies:** sportsipy (sportsipy.ncaab.teams, schedule, boxscore), pandas
**Output:** Saves raw data to `data/raw/ncaab/`

### polymarket_fetcher.py

Full API client for Polymarket's CLOB and Gamma APIs.

| Export | Type | Purpose |
|--------|------|---------|
| `PolymarketFetcher` | class | Fetches markets, prices, order books from Polymarket |
| `MarketCategory` | enum | SPORTS, POLITICS, CRYPTO, ECONOMICS, SCIENCE, ENTERTAINMENT, OTHER |

**API Endpoints:** CLOB API, Gamma API, Strapi API
**Rate Limiting:** 100 requests/min, 1.0s delay, exponential backoff

### kalshi_fetcher.py

API client for Kalshi's CFTC-regulated prediction market platform.

| Export | Type | Purpose |
|--------|------|---------|
| `KalshiFetcher` | class | Fetches political, economic, event markets from Kalshi |

**Authentication:** API key + HMAC signature with token rotation
**Rate Limiting:** 60 requests/min, 0.5s delay, exponential backoff

### batch_fetcher.py

Async parallel data retrieval for 75%+ time reduction.

| Export | Type | Purpose |
|--------|------|---------|
| `BatchFetcher` | class | Async parallel API calls with rate limiting |

**Dependencies:** aiohttp (optional), asyncio

### closing_odds_collector.py

Selenium-based closing odds scraper for CLV validation.

| Export | Type | Purpose |
|--------|------|---------|
| `ClosingOddsCollector` | class | Scrapes closing odds from sportsbooks before game start |
| `ClosingOdds` | dataclass | Standard odds container used across all providers |

**Target Sportsbooks:** DraftKings (primary), FanDuel (backup), BetMGM (backup)
**Dependencies:** selenium, sqlite3

### arb_scanner.py

CLI wrapper and pipeline integration point for arbitrage detection.

| Export | Type | Purpose |
|--------|------|---------|
| `scan_for_arbs()` | function | Main integration point for arb scanning |

**Dependencies:** betting.arb_detector (ArbDetector, ArbOpportunity)

## Data Flow

```text
External APIs / Web Scraping
         |
         +-- odds_providers.py (4 strategies)
         |       |
         |       +-- odds_orchestrator.py (fallback chain + cache + credit budget)
         |               |
         |               +-- odds_snapshots (SQLite) via store_odds()
         |               +-- scripts/daily_predictions.py (consume)
         |               +-- scripts/settle_paper_bets.py (closing odds)
         |
         +-- ncaab_data_fetcher.py --> data/raw/ncaab/ (parquet files)
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
| requests | odds_providers.py, polymarket_fetcher.py, kalshi_fetcher.py | Yes | HTTP requests |
| sportsipy | ncaab_data_fetcher.py | Yes | NCAAB data (Teams, Schedule, Boxscores) |
| py-clob-client | polymarket_fetcher.py | Optional | Polymarket CLOB API client |
| aiohttp | batch_fetcher.py | Optional | Async HTTP for parallel fetching |
| selenium | closing_odds_collector.py, odds_providers.py (ScraperOddsProvider) | Optional | Headless Chrome for odds scraping |

## Related Areas

- [betting.md](betting.md) - arb_detector consumed by arb_scanner; odds_converter used by providers
- [tracking.md](tracking.md) - Fetched data persisted to SQLite via database.py and forecasting_db.py
- [config.md](config.md) - ODDS_CONFIG, RATE_LIMITS, PAID_APIS_BLOCKED
- [models.md](models.md) - ncaab_data_fetcher provides training data for Elo models
- [scripts.md](scripts.md) - daily_predictions.py and settle_paper_bets.py use OddsOrchestrator
