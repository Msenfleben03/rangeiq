# MLB Data Sources

## Primary Sources

### MLB Stats API (Free, No Auth)

- **Library:** `pip install MLB-StatsAPI`
- **Base URL:** `https://statsapi.mlb.com/api/v1/`
- **Rate limits:** Generous, no documented cap
- **Provides:** Schedules, probable pitchers, confirmed lineups, live game feeds,
  rosters, standings, player details, umpire assignments
- **Game ID:** `game_pk` (integer, universal across all MLB systems)

Key endpoints:

```text
/schedule?date=YYYY-MM-DD&sportId=1        → daily schedule + probable pitchers
/game/{game_pk}/feed/live                   → play-by-play, lineups, scoring
/game/{game_pk}/boxscore                    → box score with player stats
/teams/{team_id}/roster?season=YYYY         → active roster
/people/{player_id}                         → player details
```

### pybaseball (Free, Wraps Multiple Sources)

- **Library:** `pip install pybaseball`
- **GitHub:** https://github.com/jldbc/pybaseball
- **Wraps:** Baseball Savant (Statcast), FanGraphs, Baseball Reference
- **Cache:** `pybaseball.cache.enable()` — ESSENTIAL for large queries

Key functions:

```python
statcast(start_dt, end_dt)         # Pitch-level Statcast data (~700K/season)
pitching_stats(season)             # FanGraphs pitcher leaderboard (334 cols)
batting_stats(season)              # FanGraphs batter leaderboard
playerid_lookup(last, first)       # Cross-reference player IDs
schedule_and_record(season, team)  # Game-by-game results
```

### Open-Meteo (Free, No Auth, No Rate Limits)

- **Forecast API:** `https://api.open-meteo.com/v1/forecast`
- **Historical API:** `https://archive-api.open-meteo.com/v1/archive`
- **Provides:** Hourly weather data (temp, wind, humidity, precipitation)
- **Historical coverage:** Back to 1940 (covers backtest needs)
- **Query by:** Latitude/longitude + datetime

### FanGraphs Projections (Free)

- **ZiPS:** Published preseason, updated periodically
- **Steamer:** Published preseason
- **Access:** Via pybaseball `pitching_stats()` / `batting_stats()` with `qual=0`
- **Player types:** Pitchers (ERA, FIP, K%, BB%, IP) and batters (wRC+, wOBA, PA)

## Secondary Sources

### ESPN Core API (Free, Reuse Existing Infrastructure)

- **Existing code:** `pipelines/espn_core_odds_provider.py`
- **MLB sport ID:** TBD (different from NCAAB)
- **Provides:** Historical odds, opening/closing lines

### The Odds API (Freemium)

- **URL:** https://the-odds-api.com/
- **Free tier:** 500 calls/month
- **Paid:** $49/month for 90,000 calls
- **Covers:** 40+ sportsbooks, ML/RL/totals/props
- **Useful for:** Line shopping, live odds comparison

## Reference Data (One-Time Fetch)

### FiveThirtyEight MLB Elo (Archived)

- **GitHub:** archived CSV with game-by-game Elo ratings back to 1871
- **Use:** Benchmark model against published probabilities

### Retrosheet

- **URL:** https://www.retrosheet.org/
- **Provides:** Historical play-by-play, umpire assignments
- **Format:** Custom text format (parsers available)

## Player ID Cross-Reference

| System | ID Column | Example |
|--------|-----------|---------|
| MLBAM (MLB Stats API) | `player_id` | 545361 (Mike Trout) |
| FanGraphs | `fangraphs_id` | 10155 |
| Baseball Reference | `bbref_id` | "troutmi01" |
| Retrosheet | `retrosheet_id` | "troum001" |

Use `pybaseball.playerid_lookup()` to resolve across systems.
Store all IDs in the `players` table for cross-referencing.
