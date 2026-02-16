# ESPN Core API Odds Implementation Guide

**Research Date:** 2026-02-13
**Status:** Ready for Implementation
**Priority:** HIGH
**Estimated Effort:** 4-6 hours development + 2 hours testing

## Executive Summary

ESPN's undocumented Core API (`sports.core.api.espn.com`) provides **free access to betting
odds from 5+ sportsbooks** including DraftKings, FanDuel, BetMGM, Caesars, and Bet365.
This is **superior to the currently implemented ESPN Site API** for odds data.

Key Benefits:

- Free, no API key required
- Multiple bookmakers in a single request
- Historical odds via ATS (Against The Spread) endpoints
- Win probabilities for value betting
- Futures markets for long-term bets

**Risk:** Undocumented API may change without notice. Recommend conservative rate limiting (2 req/sec).

---

## API Endpoints

### Base URL

```text
https://sports.core.api.espn.com/v2/sports/{sport}/leagues/{league}
```

### Sport/League Mappings

| Sport | Sport Key | League Key | Full Path |
|-------|-----------|------------|-----------|
| NCAAB | `basketball` | `mens-college-basketball` | `basketball/mens-college-basketball` |
| NBA | `basketball` | `nba` | `basketball/nba` |
| NFL | `football` | `nfl` | `football/nfl` |
| NCAAF | `football` | `college-football` | `football/college-football` |
| MLB | `baseball` | `mlb` | `baseball/mlb` |

### Available Endpoints

#### 1. Game Odds (Primary)

```text
GET .../events/{eventId}/competitions/{eventId}/odds
```

**Returns:** Current odds from all available bookmakers for a specific game.

Example:

```text
https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/401697533/competitions/401697533/odds
```

#### 2. Win Probabilities

```text
GET .../events/{eventId}/competitions/{eventId}/probabilities
```

**Returns:** Win probability estimates (useful for identifying value bets).

#### 3. Futures Markets

```text
GET .../seasons/{year}/futures
```

**Returns:** Championship odds, conference odds, player awards, etc.

Example:

```text
https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/2026/futures
```

#### 4. ATS Records (Historical)

```text
GET .../seasons/{year}/types/{type}/teams/{id}/ats
```

**Returns:** Against The Spread records for historical analysis.

Type Values:

- `2` = Regular season
- `3` = Postseason

---

## Bookmaker Provider IDs

| Sportsbook | Provider ID | API Key |
|------------|-------------|---------|
| DraftKings | 41 | `draftkings` |
| FanDuel | 58 | `fanduel` |
| BetMGM | 45 | `betmgm` |
| Caesars | 38 | `caesars` |
| Bet365 | 2000 | `bet365` |

**Note:** Provider IDs are numeric integers in the API responses. Map these to human-readable keys.

---

## Expected JSON Response Structure

### Odds Endpoint Response

```json
{
  "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/401697533/competitions/401697533/odds",
  "count": 5,
  "pageIndex": 1,
  "pageSize": 25,
  "pageCount": 1,
  "items": [
    {
      "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/401697533/competitions/401697533/odds/41"
    },
    {
      "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/401697533/competitions/401697533/odds/58"
    }
  ]
}
```

**Note:** ESPN uses a **$ref pattern** where you must follow the reference URL to get actual odds data.

### Individual Odds Object (following $ref)

```json
{
  "provider": {
    "id": "41",
    "name": "DraftKings",
    "priority": 1
  },
  "details": "Duke -5.5 (-110)",
  "overUnder": 145.5,
  "spread": -5.5,
  "overOdds": -110,
  "underOdds": -110,
  "awayTeamOdds": {
    "favorite": false,
    "underdog": true,
    "moneyLine": 175,
    "spreadOdds": -110,
    "team": {
      "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/teams/150"
    }
  },
  "homeTeamOdds": {
    "favorite": true,
    "underdog": false,
    "moneyLine": -210,
    "spreadOdds": -110,
    "team": {
      "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/teams/150"
    }
  },
  "links": [
    {
      "href": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/401697533/competitions/401697533/odds/41"
    }
  ],
  "movement": {
    "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/401697533/competitions/401697533/odds/41/movement"
  }
}
```

Key Fields:

- `provider.id`: Bookmaker provider ID (41 = DraftKings)
- `provider.name`: Human-readable sportsbook name
- `spread`: Point spread (negative = home favored)
- `overUnder`: Total points line
- `overOdds` / `underOdds`: American odds for totals
- `homeTeamOdds.moneyLine`: Home team moneyline
- `awayTeamOdds.moneyLine`: Away team moneyline
- `homeTeamOdds.spreadOdds`: Home spread odds (usually -110)
- `movement.$ref`: Historical line movement data

---

## Implementation Plan

### Step 1: Test Endpoints with Real Event IDs

```python
import requests

# Example NCAAB event ID (get from ESPN scoreboard API)
event_id = "401697533"

# Test odds endpoint
url = f"https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/{event_id}/competitions/{event_id}/odds"

response = requests.get(url, timeout=30)
print(response.status_code)
print(response.json())
```

Action Items:

1. Fetch today's NCAAB games from ESPN scoreboard API
2. Extract event IDs from scoreboard response
3. Test Core API odds endpoint with 3-5 event IDs
4. Verify which bookmakers return data (may vary by game)
5. Document response structure variations

### Step 2: Create ESPNCoreOddsProvider Class

```python
# File: pipelines/espn_core_odds_provider.py

"""ESPN Core API Odds Provider.

Retrieves odds from ESPN's undocumented Core API endpoints.
Provides access to multiple bookmakers (DraftKings, FanDuel, BetMGM, etc.)
via free API with no authentication required.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from pipelines.closing_odds_collector import ClosingOdds
from pipelines.odds_providers import OddsProvider

logger = logging.getLogger(__name__)

ESPN_CORE_SPORT_PATHS = {
    "ncaab": "basketball/mens-college-basketball",
    "nba": "basketball/nba",
    "nfl": "football/nfl",
    "ncaaf": "football/college-football",
    "mlb": "baseball/mlb",
}

ESPN_PROVIDER_ID_MAP = {
    "41": "draftkings",
    "58": "fanduel",
    "45": "betmgm",
    "38": "caesars",
    "2000": "bet365",
}


class ESPNCoreOddsProvider(OddsProvider):
    """Retrieves odds from ESPN Core API (sports.core.api.espn.com).

    Free, no API key needed. Endpoints are undocumented and may change.
    Supports multiple bookmakers per game via $ref pattern.
    """

    BASE_URL = "https://sports.core.api.espn.com/v2/sports"

    def __init__(self, rate_limit_rps: float = 2.0):
        """Initialize the ESPN Core API odds provider.

        Args:
            rate_limit_rps: Rate limit in requests per second.
        """
        self._rate_limit_delay = 1.0 / rate_limit_rps
        self._last_request_time = 0.0

    @property
    def provider_name(self) -> str:
        """Return the human-readable provider name."""
        return "espn_core_api"

    @property
    def is_available(self) -> bool:
        """Check if the provider is currently usable."""
        return True  # No dependencies

    @property
    def cost_per_request(self) -> float:
        """Return cost per API request (free for ESPN Core API)."""
        return 0.0

    def _rate_limited_get(self, url: str) -> dict:
        """Make a rate-limited GET request to ESPN Core API."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)

        response = requests.get(url, timeout=30)
        self._last_request_time = time.time()
        response.raise_for_status()
        return response.json()

    def _fetch_odds_refs(self, sport: str, event_id: str) -> list[str]:
        """Fetch odds reference URLs for a given event.

        Args:
            sport: Sport code (e.g., 'ncaab').
            event_id: ESPN event ID.

        Returns:
            List of $ref URLs to fetch individual bookmaker odds.
        """
        sport_path = ESPN_CORE_SPORT_PATHS.get(sport.lower())
        if not sport_path:
            logger.warning("ESPN Core API: unsupported sport '%s'", sport)
            return []

        url = f"{self.BASE_URL}/{sport_path}/events/{event_id}/competitions/{event_id}/odds"

        try:
            data = self._rate_limited_get(url)
        except Exception as e:
            logger.error("ESPN Core API request failed: %s", e)
            return []

        items = data.get("items", [])
        return [item["$ref"] for item in items if "$ref" in item]

    def _parse_odds_object(self, odds_data: dict, event_id: str) -> Optional[ClosingOdds]:
        """Parse a single odds object from ESPN Core API.

        Args:
            odds_data: Odds data from following a $ref URL.
            event_id: ESPN event ID for ClosingOdds.game_id.

        Returns:
            ClosingOdds object or None if parsing fails.
        """
        provider = odds_data.get("provider", {})
        provider_id = str(provider.get("id", ""))
        sportsbook = ESPN_PROVIDER_ID_MAP.get(provider_id, provider.get("name", "unknown").lower())

        odds = ClosingOdds(
            game_id=event_id,
            sportsbook=sportsbook,
            captured_at=datetime.now(timezone.utc),
            is_closing=False,
            confidence=0.90,  # Higher confidence than Site API
        )

        # Spread
        spread = odds_data.get("spread")
        if spread is not None:
            odds.spread_home = float(spread)
            home_odds = odds_data.get("homeTeamOdds", {})
            away_odds = odds_data.get("awayTeamOdds", {})
            odds.spread_home_odds = home_odds.get("spreadOdds")
            odds.spread_away_odds = away_odds.get("spreadOdds")

        # Total
        over_under = odds_data.get("overUnder")
        if over_under is not None:
            odds.total = float(over_under)
            odds.over_odds = odds_data.get("overOdds")
            odds.under_odds = odds_data.get("underOdds")

        # Moneyline
        home_odds = odds_data.get("homeTeamOdds", {})
        away_odds = odds_data.get("awayTeamOdds", {})
        odds.moneyline_home = home_odds.get("moneyLine")
        odds.moneyline_away = away_odds.get("moneyLine")

        return odds

    def fetch_game_odds(
        self,
        sport: str,
        home: str,
        away: str,
        game_id: str,
    ) -> Optional[ClosingOdds]:
        """Fetch odds for a single game from ESPN Core API.

        Note: game_id should be ESPN event ID.
        """
        # Get all odds reference URLs for this event
        refs = self._fetch_odds_refs(sport, game_id)
        if not refs:
            logger.warning("ESPN Core API: no odds found for event %s", game_id)
            return None

        # Fetch odds from all bookmakers
        all_odds = []
        for ref_url in refs:
            try:
                odds_data = self._rate_limited_get(ref_url)
                odds = self._parse_odds_object(odds_data, game_id)
                if odds:
                    all_odds.append(odds)
            except Exception as e:
                logger.warning("Failed to fetch odds from %s: %s", ref_url, e)
                continue

        if not all_odds:
            return None

        # Prefer DraftKings, then FanDuel, then first available
        for book_key in ["draftkings", "fanduel"]:
            for odds in all_odds:
                if odds.sportsbook == book_key:
                    return odds

        return all_odds[0]

    def fetch_slate_odds(self, sport: str, date: str) -> list[ClosingOdds]:
        """Fetch odds for all games on a given date.

        Note: ESPN Core API requires event IDs. Must combine with
        ESPN Site API scoreboard to get event IDs for a date.
        """
        logger.warning("ESPN Core API: slate fetching not supported (requires event IDs)")
        logger.info("Use ESPN Site API to get event IDs, then call fetch_game_odds")
        return []
```

### Step 3: Add to OddsOrchestrator

```python
# File: pipelines/odds_orchestrator.py

# Add import
from pipelines.espn_core_odds_provider import ESPNCoreOddsProvider

# Update __init__ method
def __init__(
    self,
    api_key: str | None = None,
    manual_csv_path: str | Path | None = None,
    db_path: str = "data/betting.db",
):
    """Initialize the odds orchestrator with all providers."""
    self.providers = {
        "manual": ManualOddsProvider(manual_csv_path),
        "the_odds_api": TheOddsAPIProvider(api_key),
        "espn_core_api": ESPNCoreOddsProvider(),  # NEW
        "espn": ESPNOddsProvider(),
        "scraper": ScraperOddsProvider(db_path),
    }

    # Update default fallback chain
    self.default_chain = [
        "manual",
        "the_odds_api",
        "espn_core_api",  # NEW: Insert before espn_site_api
        "espn",
        "scraper",
    ]
```

### Step 4: Hybrid Workflow (ESPN Site API + Core API)

**Recommended Approach:** Use ESPN Site API to discover event IDs, then use Core API for odds.

```python
# Example: Fetch odds for today's NCAAB games

from pipelines.espn_ncaab_fetcher import ESPNDataFetcher
from pipelines.espn_core_odds_provider import ESPNCoreOddsProvider

# Step 1: Get today's event IDs from ESPN Site API
fetcher = ESPNDataFetcher()
scoreboard_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
scoreboard = fetcher._fetch_json(scoreboard_url)

event_ids = [event["id"] for event in scoreboard.get("events", [])]

# Step 2: Fetch odds for each event from Core API
core_provider = ESPNCoreOddsProvider()
all_odds = []

for event_id in event_ids:
    odds = core_provider.fetch_game_odds(
        sport="ncaab",
        home="",  # Not needed for Core API
        away="",  # Not needed for Core API
        game_id=event_id,
    )
    if odds:
        all_odds.append(odds)

print(f"Fetched odds for {len(all_odds)} games from {len(event_ids)} events")
```

---

## Testing Plan

### Test 1: Endpoint Availability (15 min)

```bash
# Run from venv
venv/Scripts/python.exe -c "
import requests
event_id = '401697533'  # Replace with current event ID
url = f'https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/{event_id}/competitions/{event_id}/odds'
response = requests.get(url, timeout=30)
print(f'Status: {response.status_code}')
print(f'Response: {response.json()}')
"
```

**Expected:** 200 OK with JSON containing `items` array of `$ref` URLs.

### Test 2: Provider ID Mapping (30 min)

1. Fetch odds for 5 different NCAAB games
2. Collect all unique provider IDs from responses
3. Verify mapping to known sportsbooks (DraftKings, FanDuel, etc.)
4. Update `ESPN_PROVIDER_ID_MAP` if new IDs found

### Test 3: Integration Test (1 hour)

```python
# File: tests/test_espn_core_odds_provider.py

import pytest
from pipelines.espn_core_odds_provider import ESPNCoreOddsProvider

def test_fetch_game_odds():
    """Test fetching odds for a real NCAAB game."""
    provider = ESPNCoreOddsProvider()

    # Replace with current event ID
    event_id = "401697533"

    odds = provider.fetch_game_odds(
        sport="ncaab",
        home="Duke",
        away="UNC",
        game_id=event_id,
    )

    assert odds is not None
    assert odds.game_id == event_id
    assert odds.sportsbook in ["draftkings", "fanduel", "betmgm", "caesars", "bet365"]

    # Check odds fields populated
    assert odds.spread_home is not None or odds.moneyline_home is not None

def test_provider_availability():
    """Test provider is available."""
    provider = ESPNCoreOddsProvider()
    assert provider.is_available
    assert provider.cost_per_request == 0.0
    assert provider.provider_name == "espn_core_api"
```

Run:

```bash
pytest tests/test_espn_core_odds_provider.py -v
```

### Test 4: Fallback Chain Validation (30 min)

```python
# File: tests/test_odds_orchestrator.py

def test_espn_core_api_in_chain():
    """Verify ESPN Core API is in default fallback chain."""
    from pipelines.odds_orchestrator import OddsOrchestrator

    orch = OddsOrchestrator()
    assert "espn_core_api" in orch.default_chain

    # Verify order: API -> Core API -> Site API
    api_idx = orch.default_chain.index("the_odds_api")
    core_idx = orch.default_chain.index("espn_core_api")
    site_idx = orch.default_chain.index("espn")

    assert api_idx < core_idx < site_idx
```

---

## Rate Limiting & Error Handling

### Recommended Rate Limits

| Endpoint | Rate Limit | Reasoning |
|----------|------------|-----------|
| Game Odds | 2 req/sec | Conservative (undocumented API) |
| Movement Data | 1 req/sec | Secondary data, less critical |
| Futures | 0.5 req/sec | Large responses, infrequent use |

### Error Handling Patterns

```python
# Pattern 1: HTTP errors
try:
    data = self._rate_limited_get(url)
except requests.HTTPError as e:
    if e.response.status_code == 404:
        logger.info("ESPN Core API: event %s not found (may not have odds yet)", event_id)
        return None
    elif e.response.status_code == 429:
        logger.warning("ESPN Core API: rate limited, backing off")
        time.sleep(5.0)
        return None
    else:
        logger.error("ESPN Core API: HTTP %s error: %s", e.response.status_code, e)
        return None

# Pattern 2: Missing data
if not items:
    logger.info("ESPN Core API: no bookmakers available for event %s", event_id)
    return None

# Pattern 3: Malformed response
try:
    odds = self._parse_odds_object(odds_data, event_id)
except (KeyError, ValueError, TypeError) as e:
    logger.warning("ESPN Core API: failed to parse odds: %s", e)
    return None
```

---

## Maintenance & Monitoring

### Monitoring Checklist

- [ ] Track API response times (alert if >2 seconds)
- [ ] Log provider ID coverage (detect new bookmakers)
- [ ] Monitor error rates (alert if >10% failure rate)
- [ ] Track which sports/leagues return odds (NCAAB may differ from NFL)
- [ ] Log when endpoints return empty results (API degradation)

### Maintenance Tasks

| Task | Frequency | Action |
|------|-----------|--------|
| Verify endpoints | Weekly | Test 5 random events |
| Update provider IDs | Monthly | Check for new bookmakers |
| Review error logs | Daily | Identify API changes |
| Compare vs The Odds API | Weekly | Validate data quality |

---

## References

1. [GitHub - pseudo-r/Public-ESPN-API][ref1] - Comprehensive ESPN API documentation
2. [ESPN Hidden API Docs (Gist)][ref2] - Community-maintained endpoint list
3. [ScrapeCreators - ESPN Hidden API Guide][ref3] - Tutorial on using ESPN APIs
4. [Zuplo - ESPN Hidden API Developer's Guide][ref4] - Best practices

[ref1]: https://github.com/pseudo-r/Public-ESPN-API
[ref2]: https://gist.github.com/akeaswaran/b48b02f1c94f873c6655e7129910fc3b
[ref3]: https://scrapecreators.com/blog/espn-api-free-sports-data
[ref4]: https://zuplo.com/learning-center/espn-hidden-api-guide

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-02-13 | Implement ESPN Core API odds provider | Free, multi-bookmaker, higher quality than Site API |
| 2026-02-13 | Insert Core API before Site API in fallback chain | Better data quality, use Site API as fallback |
| 2026-02-13 | Set rate limit at 2 req/sec | Conservative due to undocumented status |
| 2026-02-13 | Hybrid workflow: Site API for events, Core API for odds | Leverage strengths of both endpoints |

---

## Next Actions

1. **Immediate (Today):**
   - [ ] Test Core API odds endpoint with 5 current NCAAB event IDs
   - [ ] Verify response structure matches documentation
   - [ ] Identify which bookmakers return NCAAB odds

2. **Short-term (This Week):**
   - [ ] Implement `ESPNCoreOddsProvider` class
   - [ ] Write unit tests
   - [ ] Add to `OddsOrchestrator` fallback chain
   - [ ] Run integration tests with live data

3. **Medium-term (Next 2 Weeks):**
   - [ ] Monitor error rates and response times
   - [ ] Compare odds quality vs The Odds API
   - [ ] Backfill historical odds using ATS endpoints
   - [ ] Document any API quirks or limitations discovered

---

**Status:** Ready for implementation. No blockers identified.
