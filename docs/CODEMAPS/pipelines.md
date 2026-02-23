# Pipelines Module Codemap

**Last Updated:** 2026-02-17
**Entry Point:** `pipelines/__init__.py` (empty)
**Test Coverage:** `tests/test_odds_providers.py`, `tests/test_espn_core_odds_provider.py`,
`tests/test_unified_fetcher.py`, `tests/test_barttorvik_fetcher.py`,
`tests/test_team_name_mapping.py`, `tests/test_forecasting_db.py` (indirect)

## Architecture

```text
pipelines/
  __init__.py                  # Empty package marker
  # === Data Fetching ===
  espn_ncaab_fetcher.py        # ESPN Site API: 362 teams, scores (replaced sportsipy)
  unified_fetcher.py           # Scores + odds in one pass (incremental/nightly modes)
  ncaab_data_fetcher.py        # NCAAB game data via sportsipy (BROKEN — use espn_ncaab_fetcher)
  polymarket_fetcher.py        # Polymarket prediction market data (CLOB + Gamma APIs)
  kalshi_fetcher.py            # Kalshi prediction market data (CFTC-regulated)
  barttorvik_fetcher.py        # Barttorvik T-Rank ratings (cbbdata API, Parquet format)
  team_name_mapping.py         # ESPN team_id <-> Barttorvik team name mapping (359 teams)
  batch_fetcher.py             # Async parallel data retrieval (aiohttp)
  # === Odds Retrieval (Strategy Pattern) ===
  odds_providers.py            # 4 providers: Manual, TheOddsAPI, ESPN Site, Scraper
  espn_core_odds_provider.py   # ESPN Core API: free historical odds (open/close/current)
  odds_orchestrator.py         # Fallback chain, caching, credit budget, DB persistence
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

Manages odds retrieval across providers with automatic fallback, response caching,
credit budget tracking, and database persistence.

**Fallback Chain (auto mode):** TheOddsAPI -> ESPN Core API -> ESPN Site -> Selenium Scraper -> Cached Data -> None

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

**Dependencies:** pipelines.odds_providers (all 4 providers),
pipelines.espn_core_odds_provider, pipelines.closing_odds_collector (ClosingOdds)

### espn_core_odds_provider.py

ESPN Core API odds provider — free, no auth, historical odds (open/close/current) for completed games.

| Export | Type | Purpose |
|--------|------|---------|
| `ESPNCoreOddsFetcher` | class | Low-level ESPN Core API client for odds data |
| `ESPNCoreOddsProvider` | class | OddsProvider-compatible wrapper for orchestrator |
| `OddsSnapshot` | frozen dataclass | 29-field container: open/close/current per market |

**API:** `https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball`
**Endpoint:** `/events/{eventId}/competitions/{eventId}/odds` -> list of `$ref` links
**Auth:** None required (completely free)
**Rate:** 2 req/sec, ~3 requests per game (1 list + 2 provider refs)

**Provider IDs:**

| ID | Provider | Seasons |
|----|----------|---------|
| 58 | ESPN BET | 2025 |
| 100 | DraftKings | 2026 |
| 59 | ESPN BET Live | 2025-2026 |

**Coverage:** ~85% of games have odds (small conference/non-D1 return empty)
**Tests:** 54 tests in `tests/test_espn_core_odds_provider.py`
**Dependencies:** requests, dataclasses

## Data Fetching

### espn_ncaab_fetcher.py

Primary NCAAB data source — fetches game data from ESPN's undocumented Site API
(JSON, no scraping). Replaced sportsipy which is broken as of 2026-02-13.

| Export | Type | Purpose |
|--------|------|---------|
| `ESPNDataFetcher` | class | Fetches 362 D-I teams + schedules + scores from ESPN |

**Key Methods:**

- `fetch_teams()` - All 362 D-I teams in a single API call
- `fetch_team_schedule(team_id, season)` - Team schedule with scores
- `fetch_season_data(season, delay)` - Full season data with deduplication
- `fetch_games_by_date(target_date)` - Games for daily predictions

**API:** `http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball`
**Dependencies:** requests, pandas
**Output:** Saves raw data to `data/raw/ncaab/` (parquet, identical schema to sportsipy)

### unified_fetcher.py

Scores + odds in one pass — eliminates separate backfill step. Supports incremental, nightly, and scores-only modes.

| Export | Type | Purpose |
|--------|------|---------|
| `UnifiedNCAABFetcher` | class | Single-pass scores + odds fetcher with skip lists |

**Key Methods:**

- `fetch_season(season, incremental, include_odds)` - Main entry point
- `_fetch_odds_for_game(game)` - ESPN Core API odds lookup with skip list
- `save_enriched_parquet(df, season)` - Scores + best-provider odds
- `save_raw_odds_parquet(odds, season)` - All providers raw odds data

**Modes:** `--incremental` (only new games), `--nightly` (current season auto), `--no-odds` (fast scores only)
**Skip list:** `data/odds/skip_lists/no_odds_{season}.txt` (avoids re-fetching known-empty games)
**Dependencies:** espn_ncaab_fetcher (ESPNDataFetcher), espn_core_odds_provider (ESPNCoreOddsProvider)
**Tests:** 21 tests in `tests/test_unified_fetcher.py`

### barttorvik_fetcher.py

Barttorvik T-Rank efficiency ratings fetcher via the free cbbdata.com REST API.
Returns Apache Parquet format with daily point-in-time snapshots.

| Export | Type | Purpose |
|--------|------|---------|
| `BarttovikFetcher` | class | Main fetcher: API calls, caching, rate limiting |
| `parse_ratings_response(data, season)` | function | Parse Parquet bytes into clean DataFrame |
| `lookup_team_ratings(df, team, game_date)` | function | Point-in-time rating lookup (prevents look-ahead) |
| `compute_barttorvik_differentials(df, home, away, date)` | function | Home-away diffs for matchup features |
| `save_season_cache(df, season, cache_dir)` | function | Save season to parquet cache |
| `load_cached_season(season, cache_dir)` | function | Load from parquet cache |

**API:** `https://www.cbbdata.com/api/torvik/ratings/archive?year=YYYY&key=KEY`
**Auth:** Free API key (CBBDATA_API_KEY in .env)
**Format:** Apache Parquet (application/octet-stream), NOT JSON
**Columns:** rank, team, conf, barthag, adj_o, adj_d, adj_tempo, wab, year, date
**Coverage:** 347,392 ratings across 6 seasons (2020-2025), 353-364 teams, 134-232 dates/season
**Cache:** `data/external/barttorvik/barttorvik_ratings_{year}.parquet`
**Tests:** 18 tests in `tests/test_barttorvik_fetcher.py`
**Dependencies:** requests, pandas, pyarrow

### team_name_mapping.py

Maps ESPN team abbreviations (e.g., 'HOU') to Barttorvik team names (e.g., 'Houston').

| Export | Type | Purpose |
|--------|------|---------|
| `espn_id_to_barttorvik(espn_id)` | function | Cached lookup: ESPN ID -> Barttorvik name |
| `build_espn_barttorvik_mapping()` | function | Build full mapping from game data + manual overrides |
| `MANUAL_OVERRIDES` | dict | 41 hand-verified ESPN->Barttorvik name overrides |

**Strategy:** Auto-match by stripping mascot from ESPN opponent_name, with State->St. substitution.
Manual overrides for teams that never appear as opponents or have naming mismatches.
**Coverage:** 359 teams mapped (of ~360 D1)
**Tests:** 11 tests in `tests/test_team_name_mapping.py`
**Dependencies:** pandas (reads ESPN + Barttorvik parquet files)

### ncaab_data_fetcher.py (LEGACY)

Fetches NCAA Men's Basketball data using the sportsipy library.
**Status:** BROKEN as of 2026-02-13. Use `espn_ncaab_fetcher.py` instead.

| Export | Type | Purpose |
|--------|------|---------|
| `NCAABDataFetcher` | class | Fetches teams, schedules, game results by season |

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
         +-- espn_ncaab_fetcher.py --> data/raw/ncaab/ (parquet files)
         |
         +-- espn_core_odds_provider.py --> OddsSnapshot (open/close/current)
         |       |
         +-- odds_providers.py (4 strategies)
         |       |
         |       +-- odds_orchestrator.py (fallback chain + cache + credit budget)
         |               |
         |               +-- odds_snapshots (SQLite) via store_odds()
         |               +-- scripts/daily_predictions.py (consume)
         |               +-- scripts/settle_paper_bets.py (closing odds)
         |
         +-- unified_fetcher.py --> enriched parquet (scores + odds) + raw odds parquet
         |       |
         |       +-- espn_ncaab_fetcher.py (scores)
         |       +-- espn_core_odds_provider.py (odds)
         |
         +-- polymarket_fetcher.py --> tracking/forecasting_db.py (SQLite)
         |
         +-- kalshi_fetcher.py ------> tracking/forecasting_db.py (SQLite)
         |
         +-- barttorvik_fetcher.py --> data/external/barttorvik/ (parquet, 347K ratings)
         |       |
         |       +-- team_name_mapping.py (ESPN ID -> Barttorvik name, 359 teams)
         |       +-- scripts/backtest_ncaab_elo.py (point-in-time efficiency features)
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
| requests | espn_ncaab_fetcher.py, espn_core_odds_provider.py, odds_providers.py, polymarket_fetcher.py, kalshi_fetcher.py | Yes | HTTP requests |
| pandas | espn_ncaab_fetcher.py, unified_fetcher.py | Yes | DataFrame processing |
| sportsipy | ncaab_data_fetcher.py | No (BROKEN) | Legacy NCAAB data (replaced by ESPN fetcher) |
| py-clob-client | polymarket_fetcher.py | Optional | Polymarket CLOB API client |
| aiohttp | batch_fetcher.py | Optional | Async HTTP for parallel fetching |
| selenium | closing_odds_collector.py, odds_providers.py (ScraperOddsProvider) | Optional | Headless Chrome for odds scraping |

## Related Areas

- [betting.md](betting.md) - arb_detector consumed by arb_scanner; odds_converter used by providers
- [tracking.md](tracking.md) - Fetched data persisted to SQLite via database.py and forecasting_db.py
- [config.md](config.md) - ODDS_CONFIG, RATE_LIMITS, PAID_APIS_BLOCKED
- [models.md](models.md) - espn_ncaab_fetcher provides training data for Elo models
- [scripts.md](scripts.md) - daily_predictions.py and settle_paper_bets.py use OddsOrchestrator
