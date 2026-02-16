# Data Sources Documentation

## Overview

This document describes all data sources used in the sports betting model development
project, including API details, rate limits, data quality notes, and known issues.

---

## Sports Data Sources

### ESPN Hidden API (NCAAB) — PRIMARY

**Module:** `pipelines/espn_ncaab_fetcher.py`
**Source:** ESPN undocumented JSON API
**Cost:** Free (no API key required)

#### Base URL

```text
http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball
```

#### Endpoints

| Endpoint | Purpose | Notes |
|----------|---------|-------|
| `/teams?limit=500` | All 362 D-I teams | Single request |
| `/teams/{id}/schedule?season={year}` | Team schedule + scores | Per-team, per-season |

#### Usage

```python
from pipelines.espn_ncaab_fetcher import ESPNDataFetcher

fetcher = ESPNDataFetcher(output_dir="data/raw/ncaab")
df = fetcher.fetch_season_data(season=2025, delay=0.3)
# Returns DataFrame: game_id, team_id, opponent_id, points_for, points_against, date, location
```

#### Data Quality

| Metric | Rating | Notes |
|--------|--------|-------|
| Completeness | ⭐⭐⭐⭐⭐ | 362 teams, all completed games |
| Timeliness | ⭐⭐⭐⭐⭐ | Updates same day |
| Accuracy | ⭐⭐⭐⭐⭐ | Official ESPN data |
| Historical depth | ⭐⭐⭐⭐ | 2002+ available |

#### Known Issues

- Score format is `{'value': 71.0, 'displayValue': '71'}` — not a simple int
- Conference names not extracted from schedule events (team-level only)
- Schedule endpoint omits status field (all returned events are completed)
- No documented rate limits, but use 0.3s delay between requests

#### Performance

- ~2 minutes per season (362 teams, 0.3s delay)
- Produces identical parquet schema to sportsipy fetcher

---

### ESPN Core API (Odds) — FREE HISTORICAL ODDS

**Module:** `pipelines/espn_core_odds_provider.py`
**Source:** ESPN Core API (undocumented)
**Cost:** Free (no API key required)

#### Base URL

```text
https://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball
```

#### Endpoints

| Endpoint | Purpose | Notes |
|----------|---------|-------|
| `/events/{id}/competitions/{id}/odds` | List odds providers for a game | Returns `$ref` links |
| `$ref` link (provider-specific) | Detailed odds data | Open, close, current lines |

#### Usage

```python
from pipelines.espn_core_odds_provider import ESPNCoreOddsFetcher, ESPNCoreOddsProvider

# Low-level fetcher
fetcher = ESPNCoreOddsFetcher()
snapshot = fetcher.fetch_odds_for_event("401524123")

# OddsProvider-compatible wrapper (for orchestrator)
provider = ESPNCoreOddsProvider()
odds = provider.fetch_game_odds("ncaab", "Duke", "UNC", "401524123")
```

#### Provider IDs

| ID | Provider | Seasons | Notes |
|----|----------|---------|-------|
| 58 | ESPN BET | 2025 | Primary for 2024-25 season |
| 100 | DraftKings | 2026 | Primary for 2025-26 season |
| 59 | ESPN BET Live | 2025-2026 | Alternative |

**Not working for NCAAB:** 41, 38, 45, 47, 48, 52, 2000 (all return 404 for completed games)

#### Data Quality

| Metric | Rating | Notes |
|--------|--------|-------|
| Completeness | ⭐⭐⭐⭐ | ~85% of games (small conference/non-D1 return empty) |
| Timeliness | ⭐⭐⭐⭐⭐ | Real-time updates |
| Accuracy | ⭐⭐⭐⭐⭐ | Official ESPN/sportsbook data |
| Historical depth | ⭐⭐⭐⭐ | Confirmed working for completed games |

#### Rate Limits

| Limit | Value | Notes |
|-------|-------|-------|
| Max requests/sec | 2 | Self-imposed for politeness |
| Requests per game | ~3 | 1 list + 2 provider refs |
| Full backfill estimate | ~15 hours | ~35,700 events across 6 seasons |

#### Data Structure

`OddsSnapshot` frozen dataclass with 29 fields including:

- Open/close/current spread, total, moneyline
- Provider info, game details, timestamps
- Home/away favorite indicators

#### Known Issues

- URL pattern requires `/leagues/` segment: `basketball/leagues/mens-college-basketball`
- Small conference and non-D1 games often return empty odds
- Provider availability varies by season (ESPN BET for 2025, DraftKings for 2026)

---

### sportsipy (NCAAB, NFL, MLB, NHL) — BROKEN

**Status:** BROKEN as of 2026-02-13. Returns 0 teams for all seasons (2020-2025).
sports-reference.com responds 200 OK but the HTML parser cannot extract data.
**Replacement:** Use ESPN Hidden API (`pipelines/espn_ncaab_fetcher.py`) instead.

**Package:** `sportsipy` / `sportsreference`
**Source:** Sports Reference websites (sports-reference.com family)
**Cost:** Free (web scraping)

#### Installation

```bash
pip install sportsipy sportsreference
```

#### Usage

```python
from sportsipy.ncaab.teams import Teams
from sportsipy.ncaab.schedule import Schedule
from sportsipy.ncaab.boxscore import Boxscore

# Get all NCAAB teams
teams = Teams(year=2024)

# Get team schedule
schedule = Schedule('DUKE', year=2024)

# Get game details
game = Boxscore('2024-01-15-12-duke')
```

#### Rate Limits

| Limit | Value | Notes |
|-------|-------|-------|
| Requests/minute | ~30 | Unofficial, be respectful |
| Recommended delay | 2 seconds | Between requests |
| Concurrent requests | 1 | Single-threaded only |

#### Data Quality

| Metric | Rating | Notes |
|--------|--------|-------|
| Completeness | ⭐⭐⭐⭐ | Good for major stats |
| Timeliness | ⭐⭐⭐ | Updates within 24 hours |
| Accuracy | ⭐⭐⭐⭐⭐ | Sports Reference is authoritative |
| Historical depth | ⭐⭐⭐⭐⭐ | Back to early 1900s for some sports |

#### Known Issues

- Rate limiting can cause intermittent failures
- Some advanced stats not available for older seasons
- Team name changes require mapping (e.g., "Charlotte" vs "Charlotte 49ers")
- Conference tournament games may have different identifiers

#### Best Practices

```python
import time
from sportsipy.ncaab.teams import Teams

def fetch_with_retry(func, *args, max_retries=3, delay=2):
    """Fetch data with retry logic and rate limiting"""
    for attempt in range(max_retries):
        try:
            time.sleep(delay)  # Rate limiting
            return func(*args)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(delay * (attempt + 1))  # Exponential backoff
```

---

### pybaseball (MLB)

**Package:** `pybaseball`
**Source:** Baseball Reference, FanGraphs, Baseball Savant (Statcast)
**Cost:** Free

#### Installation

```bash
pip install pybaseball
```

#### Usage

```python
import pybaseball as pyb

# Enable caching (recommended)
pyb.cache.enable()

# Statcast data
statcast = pyb.statcast(start_dt='2024-04-01', end_dt='2024-04-30')

# Pitcher stats
pitchers = pyb.pitching_stats(2024, qual=50)

# Team batting
batting = pyb.team_batting(2024)

# FanGraphs leaderboards
fg_pitching = pyb.fg_pitching_data(2024, qual=50)
```

#### Rate Limits

| Limit | Value | Notes |
|-------|-------|-------|
| Statcast requests | ~5/minute | Baseball Savant rate limits |
| FanGraphs | ~10/minute | Less strict |
| Recommended delay | 5 seconds | For Statcast |

#### Data Quality

| Metric | Rating | Notes |
|--------|--------|-------|
| Completeness | ⭐⭐⭐⭐⭐ | Excellent MLB coverage |
| Timeliness | ⭐⭐⭐⭐ | Statcast updates same day |
| Accuracy | ⭐⭐⭐⭐⭐ | Official MLB data source |
| Historical depth | ⭐⭐⭐⭐ | Statcast from 2015, others earlier |

#### Known Issues

- Statcast data very large (can overwhelm memory)
- Some deprecated functions - check latest docs
- Player name matching can be inconsistent
- Minor league data limited

#### Best Practices

```python
import pybaseball as pyb

# Always enable caching
pyb.cache.enable()

# For large Statcast pulls, chunk by date
def get_statcast_chunked(start, end, chunk_days=7):
    """Fetch Statcast in smaller chunks to avoid timeouts"""
    import pandas as pd
    from datetime import datetime, timedelta

    all_data = []
    current = datetime.strptime(start, '%Y-%m-%d')
    end_dt = datetime.strptime(end, '%Y-%m-%d')

    while current < end_dt:
        chunk_end = min(current + timedelta(days=chunk_days), end_dt)
        data = pyb.statcast(
            start_dt=current.strftime('%Y-%m-%d'),
            end_dt=chunk_end.strftime('%Y-%m-%d')
        )
        all_data.append(data)
        current = chunk_end + timedelta(days=1)

    return pd.concat(all_data, ignore_index=True)
```

---

### nfl-data-py (NFL)

**Package:** `nfl_data_py`
**Source:** nflfastR project, Pro Football Reference
**Cost:** Free

#### Installation

```bash
pip install nfl_data_py
```

#### Usage

```python
import nfl_data_py as nfl

# Play-by-play data
pbp = nfl.import_pbp_data([2023, 2024])

# Weekly stats
weekly = nfl.import_weekly_data([2023, 2024])

# Roster data
rosters = nfl.import_rosters([2023, 2024])

# Schedules
schedules = nfl.import_schedules([2023, 2024])
```

#### Rate Limits

| Limit | Value | Notes |
|-------|-------|-------|
| Requests | Reasonable use | No strict limits |
| Data is cached | GitHub releases | Fast downloads |

#### Data Quality

| Metric | Rating | Notes |
|--------|--------|-------|
| Completeness | ⭐⭐⭐⭐⭐ | Comprehensive NFL data |
| Timeliness | ⭐⭐⭐⭐ | Updated weekly during season |
| Accuracy | ⭐⭐⭐⭐⭐ | nflfastR is gold standard |
| Historical depth | ⭐⭐⭐⭐⭐ | Play-by-play back to 1999 |

#### Known Issues

- Large file sizes (PBP data is ~500MB per season)
- Memory intensive for full season analysis
- Pre-2009 data has some gaps

#### Best Practices

```python
import nfl_data_py as nfl

# Use columns parameter to reduce memory
pbp = nfl.import_pbp_data(
    years=[2023],
    columns=['game_id', 'play_id', 'epa', 'wp', 'down', 'ydstogo']
)

# Cache locally for repeated use
pbp.to_parquet('data/raw/nfl/pbp_2023.parquet')
```

---

## Odds Data Sources

### The Odds API

**URL:** https://the-odds-api.com/
**Cost:** Free tier (500 requests/month), Paid plans available

#### Setup

```bash
# Add to .env
ODDS_API_KEY=your_key_here
```

#### Usage

```python
import requests
import os

API_KEY = os.getenv('ODDS_API_KEY')
BASE_URL = 'https://api.the-odds-api.com/v4'

def get_odds(sport='basketball_ncaab', markets='spreads,totals'):
    """Fetch current odds for a sport"""
    url = f'{BASE_URL}/sports/{sport}/odds'
    params = {
        'apiKey': API_KEY,
        'regions': 'us',
        'markets': markets,
        'oddsFormat': 'american'
    }
    response = requests.get(url, params=params)
    return response.json()

# Available sports
sports = requests.get(f'{BASE_URL}/sports', params={'apiKey': API_KEY}).json()
```

#### Rate Limits

| Tier | Requests/Month | Notes |
|------|---------------|-------|
| Free | 500 | ~16/day |
| Basic ($20/mo) | 5,000 | ~166/day |
| Standard ($50/mo) | 15,000 | ~500/day |

#### Sports Available

| Sport Key | Description |
|-----------|-------------|
| `basketball_ncaab` | College Basketball |
| `basketball_nba` | NBA |
| `baseball_mlb` | MLB |
| `americanfootball_nfl` | NFL |
| `americanfootball_ncaaf` | College Football |

#### Data Quality

| Metric | Rating | Notes |
|--------|--------|-------|
| Completeness | ⭐⭐⭐⭐ | Major US sportsbooks |
| Timeliness | ⭐⭐⭐⭐⭐ | Real-time updates |
| Accuracy | ⭐⭐⭐⭐⭐ | Direct from books |
| Historical depth | ⭐⭐ | Live only, no historical |

#### Known Issues

- Limited historical data
- Some books may have incomplete coverage
- Player props limited on free tier

#### Best Practices

```python
# Cache responses to conserve API calls
import json
from datetime import datetime
from pathlib import Path

def get_odds_cached(sport, cache_minutes=15):
    """Fetch odds with local caching"""
    cache_file = Path(f'data/odds/cache_{sport}.json')

    if cache_file.exists():
        cached = json.loads(cache_file.read_text())
        cache_time = datetime.fromisoformat(cached['timestamp'])
        if (datetime.now() - cache_time).seconds < cache_minutes * 60:
            return cached['data']

    data = get_odds(sport)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({
        'timestamp': datetime.now().isoformat(),
        'data': data
    }))
    return data
```

---

### Historical Odds (Alternative Sources)

#### Kaggle Datasets

- Various historical odds datasets available
- Quality varies significantly
- Good for backtesting

#### Sportsbook Specific

- DraftKings, FanDuel sometimes publish historical data
- Web scraping possible but against TOS

#### Recommendation

For historical odds backtesting:

1. Use Kaggle datasets for initial model development
2. Capture live odds going forward using The Odds API
3. Build your own historical database over time

---

## External Data Sources

### Weather Data

**Service:** Open-Meteo (free) or Visual Crossing (paid)
**Use:** MLB outdoor games, potentially NFL

```python
import requests

def get_weather(lat, lon, date):
    """Fetch historical weather for a location/date"""
    url = 'https://archive-api.open-meteo.com/v1/archive'
    params = {
        'latitude': lat,
        'longitude': lon,
        'start_date': date,
        'end_date': date,
        'hourly': 'temperature_2m,wind_speed_10m,precipitation'
    }
    response = requests.get(url, params=params)
    return response.json()
```

#### MLB Park Coordinates

Store in config for weather lookups:

```python
MLB_PARKS = {
    'yankee_stadium': {'lat': 40.8296, 'lon': -73.9262, 'dome': False},
    'tropicana_field': {'lat': 27.7682, 'lon': -82.6534, 'dome': True},
    # ... etc
}
```

---

## Data Source Priority Matrix

| Sport | Primary Source | Backup Source | Odds Source |
|-------|---------------|---------------|-------------|
| NCAAB | ESPN Hidden API | sportsipy (broken) | The Odds API |
| MLB | pybaseball | Baseball Reference | The Odds API |
| NFL | nfl-data-py | Pro Football Reference | The Odds API |
| NCAAF | cfbd (API) | ESPN Hidden API | The Odds API |

---

## Data Freshness Requirements

| Data Type | Max Staleness | Refresh Frequency |
|-----------|---------------|-------------------|
| Team ratings | After each game | Daily during season |
| Player stats | 24 hours | Daily |
| Odds | 15 minutes | Before each bet |
| Weather | 6 hours | Day of game |
| Injuries | 1 hour | Multiple times daily |

---

## API Key Management

### Storage

- Store all API keys in `.env` file
- Never commit `.env` to git
- Use `.env.example` as template

### Rotation

- Rotate keys annually or if compromised
- Document key locations and expiration dates

### Monitoring

- Track API usage against limits
- Set up alerts at 80% of limit

---

## Troubleshooting

### Common Issues

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| 429 Too Many Requests | Rate limit exceeded | Implement backoff, cache more |
| Empty response | Off-season, no data | Check date ranges |
| Timeout | Large data request | Chunk into smaller requests |
| Data mismatch | Team name variation | Implement name mapping |
| Stale cache | Cache not invalidating | Check cache expiry logic |

### Debugging Checklist

1. Check API status page (if available)
2. Verify API key is valid
3. Check rate limit counters
4. Review error response body
5. Test with minimal request
6. Check for date/timezone issues
