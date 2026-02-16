# ESPN Core API Odds Research Report

**Research Date:** 2026-02-13
**Researcher:** Technical Researcher (Claude Code)
**Project:** Sports Betting Model Development - NCAAB Phase

---

## Executive Summary

ESPN's Core API (`sports.core.api.espn.com`) provides undocumented odds endpoints for multiple
sports including NCAAB. **CRITICAL FINDING:** Historical odds data is **NOT available** for
completed games - the `/odds` endpoint only returns data for upcoming and live events. This is
a **major blocker** for backtesting with real market odds.

### Key Findings

| Finding | Impact | Severity |
|---------|--------|----------|
| No historical odds for completed games | Cannot backtest with real ESPN odds | **HIGH** |
| Limited provider ID documentation | Unknown which books are accessible | **MEDIUM** |
| Undocumented API - no SLA/support | Production risk without fallbacks | **MEDIUM** |
| ESPN BET → DraftKings transition | Provider landscape shifting | **LOW** |

### Recommendation

**Do NOT rely on ESPN Core API for historical backtesting.** Use The Odds API ($200/month or
500 free credits/month) for historical NCAAB odds. ESPN Core API is viable for **real-time
paper betting** with proper error handling and caching.

---

## 1. ESPN Core API vs Site API

### Architecture Differences

| Aspect | **Site API** (`site.api.espn.com`) | **Core API** (`sports.core.api.espn.com`) |
|--------|-----------------------------------|-------------------------------------------|
| **Purpose** | Scores, news, teams, standings | Detailed stats, odds, probabilities |
| **Response Format** | Consolidated, single-call | Granular, multiple calls required |
| **Best For** | Scoreboard data, game summaries | Betting odds, player stats, projections |
| **Odds Data** | Not available | Available via `/odds` endpoint |

**For sports betting:** Use **Core API** for odds and probabilities.

---

## 2. Documented Odds Endpoints

Base URL: `https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball`

### Available Endpoints

| Endpoint | Path | Purpose | Status |
|----------|------|---------|--------|
| **Game Odds** | `/events/{id}/competitions/{id}/odds` | Current odds from multiple books | **Working** |
| **Win Probabilities** | `/events/{id}/competitions/{id}/probabilities` | ESPN's own projections | **Working** |
| **Futures** | `/seasons/{year}/futures` | Championship, conference odds | **Unclear for NCAAB** |
| **ATS Records** | `/seasons/{year}/types/{type}/teams/{id}/ats` | Against-the-spread records | **Unclear** |
| **Odds Movement** | `/events/{id}/competitions/{id}/odds/{provider_id}/history/0/movement?limit=100` | Historical line movement | **Unconfirmed for NCAAB** |

### Example Request (NCAAB Game Odds)

```bash
GET https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/401642188/competitions/401642188/odds
```

**Returns:** JSON with odds from multiple providers (DraftKings, Caesars, Bet365, etc.)

---

## 3. Bookmaker Provider IDs

### Confirmed Provider IDs

| Bookmaker | Provider ID | Source | Confidence |
|-----------|-------------|--------|------------|
| **DraftKings** | 41 | pseudo-r/Public-ESPN-API | **HIGH** |
| **Caesars** | 38 | pseudo-r/Public-ESPN-API | **HIGH** |
| **Bet365** | 2000 | pseudo-r/Public-ESPN-API | **HIGH** |

### Unconfirmed Provider IDs (User-Provided)

| Bookmaker | Claimed ID | Validation Status | Action Required |
|-----------|------------|-------------------|-----------------|
| **FanDuel** | 58 | **UNCONFIRMED** | Test with live NCAAB game |
| **BetMGM** | 45 | **UNCONFIRMED** | Test with live NCAAB game |

### Additional Provider IDs Found

| Provider | ID | Notes |
|----------|-----|-------|
| William Hill | 31 | May overlap with Caesars post-acquisition |
| SugarHouse | 41 | **Conflicts with DraftKings ID** - verify |
| Unibet | 36 | |
| Westgate | 25 | |
| William Hill NJ | 45 | **Conflicts with claimed BetMGM ID** |
| accuscore | 1001 | Projection model, not bookmaker |
| consensus | 1004 | Aggregated line, not bookmaker |
| numberfire | 1003 | Projection model, not bookmaker |
| teamrankings | 1002 | Projection model, not bookmaker |

### Provider ID Validation Script

```python
import requests

def test_provider_id(event_id: str, provider_id: int) -> bool:
    """Test if provider ID returns odds data for a given event"""
    url = f"https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/{event_id}/competitions/{event_id}/odds/{provider_id}"

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data and 'items' in data:
                print(f"✓ Provider {provider_id}: VALID - {len(data['items'])} odds found")
                return True
        print(f"✗ Provider {provider_id}: INVALID or no data")
        return False
    except Exception as e:
        print(f"✗ Provider {provider_id}: ERROR - {e}")
        return False

# Test with live NCAAB game
event_id = "401642188"  # Replace with current game ID
for provider_id in [41, 38, 2000, 58, 45]:
    test_provider_id(event_id, provider_id)
```

---

## 4. Historical Odds Availability

### CRITICAL FINDING: No Historical Odds for Completed Games

The `/odds` endpoint **DOES NOT return data** for completed games. Confirmed via:

- [ESPN's Hidden API Guide (Zuplo)](https://zuplo.com/learning-center/espn-hidden-api-guide)
- [ESPN hidden API Docs (akeaswaran)](https://gist.github.com/akeaswaran/b48b02f1c94f873c6655e7129910fc3b)
- Community reports on data availability

### What This Means

| Scenario | ESPN Core API Support | Impact |
|----------|----------------------|--------|
| **Backtesting with historical odds** | ❌ NOT SUPPORTED | Cannot validate Elo model with real market data |
| **Real-time odds capture (upcoming games)** | ✅ SUPPORTED | Can track CLV for paper betting |
| **Odds movement history (live games)** | ⚠️ UNCLEAR | `/movement` endpoint exists but behavior unknown |
| **Post-game analysis of closing lines** | ❌ NOT SUPPORTED | Must capture before game starts |

### Workarounds for Historical Backtesting

| Solution | Cost | Coverage | Data Quality |
|----------|------|----------|--------------|
| **The Odds API** | $200/month (or 500 free credits) | NCAAB from late 2020 | **HIGH** - real market data |
| **SportsDataIO** | Varies | NCAAB from 2019 | **HIGH** - comprehensive |
| **Manual web scraping** | Free (legal gray area) | As far back as archived | **MEDIUM** - gaps possible |
| **Proceed without historical odds** | Free | N/A | **LOW** - simulated odds unrealistic |

**Recommendation:** Subscribe to The Odds API free tier (500 credits/month) for historical
2024-2025 NCAAB season backtest. Upgrade to paid if insufficient.

---

## 5. Rate Limits and Known Issues

### Rate Limiting

| Aspect | Official Guidance | Community Practice | Risk |
|--------|------------------|-------------------|------|
| **Published Limits** | None | None | High - unknown threshold |
| **Enforcement** | "Excessive requests may be blocked" | 0.3-0.5s delay recommended | Ban possible |
| **Authentication** | Not required | Not available | No appeal process |

### Best Practices

```python
import time
import requests

class ESPNOddsClient:
    def __init__(self, delay_seconds: float = 0.5):
        self.delay = delay_seconds
        self.last_request = 0

    def get_odds(self, event_id: str, provider_id: int):
        """Fetch odds with rate limiting"""
        # Enforce delay
        elapsed = time.time() - self.last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

        url = f"https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/{event_id}/competitions/{event_id}/odds/{provider_id}"

        try:
            response = requests.get(url, timeout=10)
            self.last_request = time.time()

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print("Rate limited - waiting 60s")
                time.sleep(60)
                return self.get_odds(event_id, provider_id)
            else:
                print(f"Error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"Request failed: {e}")
            return None
```

### Known Issues

| Issue | Description | Severity | Workaround |
|-------|-------------|----------|------------|
| **No completed game odds** | `/odds` returns empty for past games | **HIGH** | Capture before tip-off |
| **Undocumented provider IDs** | No official ID list | **MEDIUM** | Trial and error validation |
| **Data quality inconsistencies** | Player IDs, missing 3PT data (non-odds) | **LOW** | Use for odds only |
| **ESPN BET shutdown** | Provider landscape changing | **LOW** | Monitor DraftKings integration |
| **No official support** | Undocumented API | **HIGH** | Build fallback systems |

---

## 6. Core vs Site API - Practical Comparison

### When to Use Site API

```python
# Get NCAAB scoreboard with game summaries
url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates=20260213&limit=500"
response = requests.get(url)
data = response.json()

# Returns: Consolidated game data (scores, teams, status) in single response
# Best for: Daily predictions, game identification, score tracking
```

### When to Use Core API

```python
# Get detailed odds for specific game
event_id = "401642188"
url = f"https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/{event_id}/competitions/{event_id}/odds"
response = requests.get(url)
odds_data = response.json()

# Returns: Multi-bookmaker odds (spread, moneyline, total)
# Best for: Line shopping, CLV tracking, betting decisions
```

---

## 7. Community Insights

### Reddit & Forums

**Search Results:** Limited Reddit discussions found specifically about ESPN API odds endpoints.

Key Observations:

- ESPN NBA data described as "unreliable and incomplete" by community
- "ESPN was noted as being unreliable with updates"
- Most discussions focus on alternative APIs (The Odds API, SportsDataIO)
- Developers prefer documented APIs over ESPN's undocumented endpoints

### Stack Overflow

**Search Results:** No dedicated threads found for ESPN API odds/bookmaker integration.

**Interpretation:** Low community adoption for production use due to lack of documentation and support.

### Sports Analytics Forums

Popular Alternatives:

1. **The Odds API** - Most recommended paid solution
2. **SportsDataIO** - Preferred for historical data
3. **OddsMatrix** - For comprehensive betting markets
4. **Unabated** - For sharp/closing line analysis

**Common Sentiment:** ESPN Core API is "powerful but unpredictable" - suitable for hobbyist
projects but risky for production without fallbacks.

---

## 8. ESPN BET → DraftKings Transition

### Timeline

| Date | Event | Impact on API |
|------|-------|---------------|
| **Dec 1, 2025** | ESPN BET app shutdown | Provider ID availability unclear |
| **Dec 1, 2025** | DraftKings partnership begins | DraftKings (41) likely primary provider |
| **2026** | Full DraftKings integration in ESPN app | Potential Core API enhancements |

### Implications

- **DraftKings (ID 41)** likely to be most reliable provider going forward
- Other bookmaker provider IDs (Caesars, FanDuel, BetMGM) may receive less maintenance
- Possible API changes during integration - monitor for breaking changes
- Increased scrutiny due to NBA betting scandal - potential for stricter rate limiting

---

## 9. Implementation Recommendations

### Recommended Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                     ODDS RETRIEVAL PIPELINE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. ESPN Core API (Primary - Real-time)                         │
│     ├─ DraftKings (41) ✓                                        │
│     ├─ Caesars (38) ✓                                           │
│     ├─ Bet365 (2000) ✓                                          │
│     ├─ FanDuel (58) ? - needs validation                        │
│     └─ BetMGM (45) ? - needs validation                         │
│                                                                  │
│  2. The Odds API (Fallback + Historical)                        │
│     ├─ All major US sportsbooks                                 │
│     ├─ Historical data from late 2020                           │
│     └─ 500 free credits/month or $200/month                     │
│                                                                  │
│  3. Local Cache (SQLite)                                        │
│     ├─ Store all odds with timestamp                            │
│     ├─ Enable offline analysis                                  │
│     └─ Fallback if APIs unavailable                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Use Case: Real-time Paper Betting (RECOMMENDED)

```python
# pipelines/espn_odds_fetcher.py
import requests
import time
from typing import Optional, Dict, List

class ESPNOddsFetcher:
    BASE_URL = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball"
    PROVIDER_IDS = {
        'draftkings': 41,
        'caesars': 38,
        'bet365': 2000,
        'fanduel': 58,  # UNCONFIRMED
        'betmgm': 45    # UNCONFIRMED
    }

    def __init__(self, delay: float = 0.5):
        self.delay = delay
        self.last_request = 0

    def fetch_game_odds(self, event_id: str, providers: Optional[List[str]] = None) -> Dict:
        """Fetch odds from multiple providers for a given game"""
        if providers is None:
            providers = ['draftkings', 'caesars', 'bet365']

        odds_data = {}
        for provider in providers:
            provider_id = self.PROVIDER_IDS.get(provider)
            if not provider_id:
                continue

            odds = self._fetch_provider_odds(event_id, provider_id)
            if odds:
                odds_data[provider] = odds

            # Rate limiting
            time.sleep(self.delay)

        return odds_data

    def _fetch_provider_odds(self, event_id: str, provider_id: int) -> Optional[Dict]:
        """Fetch odds from single provider"""
        url = f"{self.BASE_URL}/events/{event_id}/competitions/{event_id}/odds/{provider_id}"

        elapsed = time.time() - self.last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

        try:
            response = requests.get(url, timeout=10)
            self.last_request = time.time()

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print(f"Rate limited for provider {provider_id} - waiting 60s")
                time.sleep(60)
                return self._fetch_provider_odds(event_id, provider_id)
            else:
                return None
        except Exception as e:
            print(f"Error fetching provider {provider_id}: {e}")
            return None
```

### Use Case: Historical Backtesting (REQUIRES PAID API)

Do NOT use ESPN Core API - it will not work.

```python
# pipelines/odds_api_fetcher.py (The Odds API)
import requests
from typing import List, Dict
from datetime import datetime

class OddsAPIFetcher:
    BASE_URL = "https://api.the-odds-api.com/v4"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def fetch_historical_odds(self, sport: str, date: str) -> List[Dict]:
        """
        Fetch historical odds for a given date

        Args:
            sport: 'basketball_ncaab'
            date: ISO format '2025-01-15T00:00:00Z'
        """
        url = f"{self.BASE_URL}/sports/{sport}/odds-history/"

        params = {
            'apiKey': self.api_key,
            'regions': 'us',
            'markets': 'h2h,spreads,totals',
            'bookmakers': 'draftkings,fanduel,betmgm,caesars',
            'date': date
        }

        response = requests.get(url, params=params)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error {response.status_code}: {response.text}")
            return []
```

### Critical Implementation Notes

1. **Capture Timing for CLV**
   - **Opening odds:** Capture when game first appears (7+ days before)
   - **Closing odds:** Capture 5-10 minutes before scheduled tip-off
   - **Do NOT wait until after game completes** - odds will be purged

2. **Provider ID Validation**
   - Test FanDuel (58) and BetMGM (45) with live games BEFORE production
   - If invalid, remove from provider list and rely on confirmed IDs

3. **Error Handling**
   - Always implement fallback to The Odds API or cached data
   - Log all API failures for monitoring
   - Build retry logic with exponential backoff

4. **Database Schema for Odds Storage**

```sql
CREATE TABLE odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    game_date DATE NOT NULL,
    provider TEXT NOT NULL,
    snapshot_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Spread
    spread_line REAL,
    spread_home_odds INTEGER,
    spread_away_odds INTEGER,

    -- Moneyline
    moneyline_home INTEGER,
    moneyline_away INTEGER,

    -- Total
    total_line REAL,
    total_over_odds INTEGER,
    total_under_odds INTEGER,

    -- Metadata
    is_opening BOOLEAN DEFAULT FALSE,
    is_closing BOOLEAN DEFAULT FALSE,

    UNIQUE(event_id, provider, snapshot_time)
);

CREATE INDEX idx_odds_event ON odds_snapshots(event_id);
CREATE INDEX idx_odds_snapshot_time ON odds_snapshots(snapshot_time);
```

---

## 10. Decision Matrix for Sports Betting Project

### Decision 1: Use ESPN Core API for Real-time Paper Betting?

| Factor | Assessment | Weight | Score |
|--------|------------|--------|-------|
| **Cost** | Free | HIGH | ✓✓✓ |
| **Reliability** | Undocumented, no SLA | HIGH | ✗✗ |
| **Coverage** | 3 confirmed books, 2 unconfirmed | MEDIUM | ✓✓ |
| **Historical Data** | Not available | LOW (for paper betting) | ✓ |
| **Implementation Effort** | Low - simple REST calls | MEDIUM | ✓✓✓ |

**Recommendation:** ✅ **YES** - Use for paper betting phase with The Odds API as fallback.

### Decision 2: Use ESPN Core API for Historical Backtesting?

| Factor | Assessment | Weight | Score |
|--------|------------|--------|-------|
| **Historical Availability** | Not available for completed games | **CRITICAL** | ✗✗✗ |
| **Data Accuracy** | N/A - data doesn't exist | HIGH | ✗✗✗ |
| **Cost** | Free | LOW | ✓✓✓ |

**Recommendation:** ❌ **NO** - Impossible. Must use The Odds API or other paid service.

### Decision 3: Subscribe to The Odds API?

| Tier | Cost | Credits | Use Case | Recommendation |
|------|------|---------|----------|----------------|
| **Free** | $0 | 500/month | Historical backtest (1 season) | ✅ **START HERE** |
| **Starter** | $200/month | 10,000 | Paper betting + monitoring | ⚠️ **IF FREE INSUFFICIENT** |

**Recommendation:** Start with **free tier** (500 credits) to fetch 2024-2025 NCAAB
historical odds for backtest. Monitor usage. Upgrade if paper betting phase requires
real-time tracking.

---

## 11. Next Steps for Sports Betting Project

### Immediate Actions (Today)

1. ✅ **Validate ESPN Core API with live NCAAB game**

   ```bash
   # Test with today's games
   curl "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard?dates=20260213&limit=10"
   # Extract event_id, test odds endpoint
   ```

2. ✅ **Test provider IDs 41, 38, 2000, 58, 45**
   - Confirm DraftKings, Caesars, Bet365
   - Validate or reject FanDuel, BetMGM

3. ✅ **Sign up for The Odds API free tier**
   - 500 credits/month
   - Test historical endpoint with 2025-01-15 NCAAB games

### Short-term (This Week)

1. ⏳ **Integrate The Odds API into `pipelines/odds_providers.py`**
   - Add `OddsAPIFetcher` class
   - Implement historical fetch for 2024-2025 season
   - Store in `data/odds/historical/ncaab_2024_2025.parquet`

2. ⏳ **Re-run backtest with real odds**

   ```bash
   python scripts/backtest_ncaab_elo.py --season 2025 --odds-source the-odds-api
   ```

3. ⏳ **Re-run Gatekeeper validation**

   ```bash
   python scripts/run_gatekeeper_validation.py --model ncaab_elo_v2 --backtest-file data/backtests/ncaab_elo_backtest_2025_real_odds.parquet
   ```

   - **Expected outcome:** PASS (Sharpe > 0.5, CLV > 1.5%)

### Long-term (Next 2 Weeks)

1. ⏳ **Build real-time odds capture pipeline**
   - Integrate `ESPNOddsFetcher` into `daily_predictions.py`
   - Capture opening odds at prediction time
   - Schedule closing odds capture via cron (5 min before tip-off)

2. ⏳ **Implement CLV tracking**
   - Update `tracking/logger.py` to record odds
   - Calculate CLV post-game in `settle_paper_bets.py`
   - Report weekly CLV in `generate_report.py`

3. ⏳ **Monitor ESPN Core API stability**
   - Log all 404/429/500 errors
   - Track provider ID success rates
   - Build alerting for API changes

---

## 12. Sources & Citations

### Primary Sources

1. [pseudo-r. "Public-ESPN-API." GitHub, 2024.][espn-api-gh]
2. [akeaswaran. "ESPN hidden API Docs." GitHub Gist, 2024.][espn-api-gist]
3. [ScrapeCreators. "ESPN's Hidden API." ScrapeCreators Blog, 2024.][scrapecreators]
4. [Zuplo. "Unlocking ESPN's Hidden API." Zuplo Learning Center, 2024.][zuplo]

### Secondary Sources

1. [The Odds API. "NCAA Basketball Odds API."][odds-api-ncaab]
2. [SportsDataIO. "NCAA College Basketball Data API."][sportsdata-ncaab]
3. [SportsGameOdds. "Best Sports Betting APIs."][sportsgameodds]
4. [ESPN. "ESPN names DraftKings its official sportsbook." 2025.][espn-dk]

[espn-api-gh]: https://github.com/pseudo-r/Public-ESPN-API
[espn-api-gist]: https://gist.github.com/akeaswaran/b48b02f1c94f873c6655e7129910fc3b
[scrapecreators]: https://scrapecreators.com/blog/espn-api-free-sports-data
[zuplo]: https://zuplo.com/learning-center/espn-hidden-api-guide
[odds-api-ncaab]: https://the-odds-api.com/sports-odds-data/ncaa-basketball-odds.html
[sportsdata-ncaab]: https://sportsdata.io/developers/api-documentation/ncaa-basketball
[sportsgameodds]: https://sportsgameodds.com/best-sports-betting-apis-according-to-reddit/
[espn-dk]: https://www.espn.com/espn/story/_/id/46868973/espn-names-draftkings-official-sportsbook-odds-provider

---

## Appendix A: Example API Responses

### ESPN Core API - Game Odds Response (Abbreviated)

```json
{
  "count": 3,
  "items": [
    {
      "provider": {
        "id": "41",
        "name": "DraftKings",
        "priority": 1
      },
      "details": "Duke -6.5",
      "overUnder": 152.5,
      "spread": -6.5,
      "overOdds": -110,
      "underOdds": -110,
      "awayTeamOdds": {
        "favorite": false,
        "underdog": true,
        "moneyLine": 220,
        "spreadOdds": -110
      },
      "homeTeamOdds": {
        "favorite": true,
        "underdog": false,
        "moneyLine": -270,
        "spreadOdds": -110
      }
    },
    {
      "provider": {
        "id": "38",
        "name": "Caesars",
        "priority": 2
      },
      "details": "Duke -6",
      "overUnder": 153,
      "spread": -6,
      "overOdds": -105,
      "underOdds": -115,
      "awayTeamOdds": {
        "favorite": false,
        "underdog": true,
        "moneyLine": 215,
        "spreadOdds": -108
      },
      "homeTeamOdds": {
        "favorite": true,
        "underdog": false,
        "moneyLine": -265,
        "spreadOdds": -112
      }
    }
  ]
}
```

### The Odds API - Historical Odds Response (Abbreviated)

```json
{
  "id": "abc123",
  "sport_key": "basketball_ncaab",
  "sport_title": "NCAAB",
  "commence_time": "2025-01-15T19:00:00Z",
  "home_team": "Duke Blue Devils",
  "away_team": "UNC Tar Heels",
  "bookmakers": [
    {
      "key": "draftkings",
      "title": "DraftKings",
      "last_update": "2025-01-15T18:55:00Z",
      "markets": [
        {
          "key": "h2h",
          "outcomes": [
            {"name": "Duke Blue Devils", "price": -270},
            {"name": "UNC Tar Heels", "price": 220}
          ]
        },
        {
          "key": "spreads",
          "outcomes": [
            {"name": "Duke Blue Devils", "price": -110, "point": -6.5},
            {"name": "UNC Tar Heels", "price": -110, "point": 6.5}
          ]
        },
        {
          "key": "totals",
          "outcomes": [
            {"name": "Over", "price": -110, "point": 152.5},
            {"name": "Under", "price": -110, "point": 152.5}
          ]
        }
      ]
    }
  ]
}
```

---

## Appendix B: Quick Reference - Provider IDs

### Confirmed (Safe to Use)

```python
CONFIRMED_PROVIDERS = {
    'draftkings': 41,
    'caesars': 38,
    'bet365': 2000
}
```

### Unconfirmed (Test Before Use)

```python
UNCONFIRMED_PROVIDERS = {
    'fanduel': 58,  # NEEDS VALIDATION
    'betmgm': 45    # NEEDS VALIDATION - conflicts with William Hill NJ
}
```

### Not Recommended (Projection Models, Not Bookmakers)

```python
PROJECTION_PROVIDERS = {
    'accuscore': 1001,
    'teamrankings': 1002,
    'numberfire': 1003,
    'consensus': 1004
}
```

---

End of Report
