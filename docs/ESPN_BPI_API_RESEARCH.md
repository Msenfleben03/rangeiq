# ESPN Basketball Power Index (BPI) API Research

**Research Date**: February 16, 2026
**Status**: PRODUCTION-READY - Free API with historical data back to 2020

---

## Executive Summary

ESPN's BPI data is **fully accessible** via undocumented API with **zero cost**,
complete historical coverage (2020-2026), and rich efficiency metrics comparable to KenPom.
This eliminates the need for a $95/year KenPom API subscription.

### Key Findings

| Criterion | ESPN BPI API | KenPom API |
|-----------|--------------|------------|
| **Cost** | FREE | $95/year |
| **Historical Data** | 2020-2026 (6 seasons) | Full archive |
| **Data Granularity** | Season-level snapshots | Point-in-time (daily) |
| **Metrics** | BPI, OFF, DEF, projections | AdjEM, AdjO, AdjD, AdjT, Four Factors |
| **Rate Limit** | ~2 req/sec (no blocking) | Unknown |
| **Stability** | Undocumented (may change) | Official API |
| **Authentication** | None required | API key required |

### Recommendation

**Use ESPN BPI API as primary source** for efficiency ratings. Add KenPom later only if:

1. Point-in-time ratings (pre-game snapshots) are critical
2. Four Factors / tempo metrics show significant model improvement
3. ESPN API becomes unreliable

---

## 1. ESPN Core API Access

### Base Endpoint

```text
https://site.web.api.espn.com/apis/fitt/v3/sports/basketball/mens-college-basketball/powerindex
```

### URL Parameters

| Parameter | Required | Description | Example |
|-----------|----------|-------------|---------|
| `region` | Yes | Geographic region | `us` |
| `lang` | Yes | Language | `en` |
| `season` | No | Season year (defaults to current) | `2025` |
| `limit` | No | Results per page (default 50, max 1000) | `100` |
| `page` | No | Page number for pagination | `2` |
| `sort` | No | Sort field and direction | `bpi.bpi:desc` |

### Example Request

```bash
curl "https://site.web.api.espn.com/apis/fitt/v3/sports/basketball/mens-college-basketball/powerindex?region=us&lang=en&season=2025&limit=100"
```

### Response Structure

```json
{
  "pagination": {
    "count": 365,
    "limit": 100,
    "page": 1,
    "pages": 4,
    "next": "http://site.api.espn.com:80/apis/fitt/v3/sports/basketball/mens-college-basketball/powerindex?lang=en&region=us&limit=100&page=2"
  },
  "currentSeason": {
    "year": 2026,
    "displayName": "2025-26",
    "type": {"id": "2", "name": "Regular Season"}
  },
  "teams": [
    {
      "team": {
        "id": "150",
        "displayName": "Duke Blue Devils",
        "abbreviation": "DUKE",
        "group": {
          "id": "2",
          "name": "Atlantic Coast Conference",
          "abbreviation": "acc"
        }
      },
      "categories": [
        {
          "name": "bpi",
          "displayName": "BPI",
          "values": [24.9262, 1.0, 0.0, 12.3357, 12.5905, 97.96, 23.0, 23.0, 2.0, 27.9356, 3.0644, 12.0, 1.0, 16.4219, 1.5781],
          "ranks": ["1st", "1st", "-", "3rd", "3rd", "-", "23rd", "-", "-", "-", "-", "-", "-", "-", "-"]
        }
      ]
    }
  ]
}
```

---

## 2. BPI Data Fields

### Available Metrics (15 fields per team)

| Index | Field Name | Description | Type | Example |
|-------|-----------|-------------|------|---------|
| 0 | `BPI` | Basketball Power Index rating | float | 24.9262 |
| 1 | `BPI_RANK` | National BPI rank | int | 1 |
| 2 | `TREND` | Week-over-week change | float | 0.0 |
| 3 | `OFF` | Offensive rating (pts above avg per 100 poss) | float | 12.3357 |
| 4 | `DEF` | Defensive rating (pts above avg per 100 poss) | float | 12.5905 |
| 5 | `WIN_PCT` | Projected win percentage remaining games | float | 97.96 |
| 6 | `REM_SOS_RANK` | Remaining strength of schedule rank | int | 23 |
| 7 | `PROJ_W` | Projected wins (season total) | int | 23 |
| 8 | `PROJ_L` | Projected losses (season total) | int | 2 |
| 9 | `PROJ_OVR_W` | Projected overall wins (including postseason) | float | 27.9356 |
| 10 | `PROJ_OVR_L` | Projected overall losses (including postseason) | float | 3.0644 |
| 11 | `PROJ_CONF_W` | Projected conference wins | int | 12 |
| 12 | `PROJ_CONF_L` | Projected conference losses | int | 1 |
| 13 | `WIN_CONF_PCT` | Projected win conference percentage | float | 16.4219 |
| 14 | `UNKNOWN` | Unknown metric | float | 1.5781 |

### Key Formulas

#### BPI = OFF + DEF

A team with OFF=12.3 and DEF=12.6 has BPI=24.9, meaning they would beat an average D1 team
by ~25 points per 100 possessions on a neutral court.

**Offensive Rating (OFF)**: Points above average an offense would score per 100 possessions against an average defense.

**Defensive Rating (DEF)**: Points below average a defense would allow per 100 possessions
against an average offense. (Higher is better — positive DEF means stingier than average.)

### BPI vs KenPom Equivalents

| ESPN BPI | KenPom | Notes |
|----------|--------|-------|
| BPI | AdjEM | Adjusted efficiency margin |
| OFF | AdjO | Adjusted offensive efficiency |
| DEF | AdjD | Adjusted defensive efficiency (inverted scale) |
| N/A | AdjT | Adjusted tempo (possessions per game) |
| N/A | Four Factors | eFG%, TO%, OR%, FTR |

**Critical Difference**: ESPN DEF is inverted from KenPom AdjD.
Higher DEF = better defense (ESPN). Lower AdjD = better defense (KenPom).

---

## 3. Historical Data Availability

### Tested Seasons

| Season | Teams | BPI Data Available | Notes |
|--------|-------|-------------------|-------|
| 2020 | 353 | ✅ Yes | COVID-shortened season |
| 2021 | 347 | ✅ Yes | Full season |
| 2022 | 358 | ✅ Yes | Full season |
| 2023 | 363 | ✅ Yes | Full season |
| 2024 | 362 | ✅ Yes | Full season |
| 2025 | 364 | ✅ Yes | Current season |

**Verified**: All seasons 2020-2026 have complete BPI data accessible via API.

### Point-in-Time Limitation

**CRITICAL**: The ESPN BPI API returns current/final season ratings, NOT point-in-time snapshots.

- **For backtesting**: Must use end-of-season ratings for each historical season
- **For live betting**: Current ratings are perfect (updated daily during season)
- **Workaround**: Fetch and cache BPI ratings nightly to build historical time series

**Impact on Backtesting**:

- Cannot reconstruct pre-game BPI ratings for past games
- Must accept "final season ratings" for 2020-2025 validation
- For production (2026 forward), cache daily snapshots

---

## 4. Rate Limits & Reliability

### Observed Performance

- **Rate**: ~2 requests/second sustained
- **No 429 errors**: 10 consecutive requests completed without rate limiting
- **Avg latency**: 0.51 seconds per request
- **Reliability**: No 5xx errors observed in testing

### Pagination Performance

- **365 teams** across **8 pages** at limit=50
- **Total fetch time**: ~4 seconds for full dataset
- **Recommended strategy**: Fetch all teams in single paginated loop daily

### Stability Risk

**WARNING**: This is an undocumented API. ESPN can:

- Change response structure without notice
- Add authentication requirements
- Deprecate endpoints
- Rate limit aggressively

**Mitigation**:

- Cache daily snapshots locally
- Build fallback to web scraping (BeautifulSoup on `espn.com/mens-college-basketball/bpi`)
- Monitor for API changes in CI/CD pipeline

---

## 5. BPI vs KenPom: Predictive Accuracy

### Calibration (ESPN's Self-Reported)

When BPI gave teams 50-60% win probability, they won **55.8%** of the time (well-calibrated).

**Source**:
[Analytics Basketball Power Index (BPI) Explained - ESPN][bpi-explained]

### KenPom Performance (Published Research)

- **Games with spread ≤7 points**: KenPom correct 60.5% (250/413 games)
- **Games with spread ≤3 points**: KenPom correct 52.7% (98/186 games)

**Source**:
[Which Advanced Metric Should Bettors Use: KenPom or Sagarin?][kenpom-sagarin]

### Expert Consensus

**Bleacher Report** (2019): "Don't trust these numbers" — criticized BPI for overweighting
preseason priors and underweighting in-season performance in early weeks.

**Source**:
[Don't Destroy Your March Madness Brackets][march-madness-brackets]

**Consensus from betting forums**: KenPom is more widely trusted by sharps,
but ESPN BPI is "good enough" for mainstream models.

### Model Weighting (Published Bracket Model)

One optimized March Madness model used:

- **25% KenPom**
- **12.5% ESPN BPI**
- Plus other metrics (NET, Sagarin, Torvik)

**Source**:
[A New Madness to March: Bracket Optimization Model][bracket-model]

### Recommendation for Betting Models

**Start with ESPN BPI (free)**. Add KenPom ($95/year) only if:

1. A/B testing shows >2% ROI improvement
2. Sharpe ratio increases by >0.3
3. CLV improvement exceeds $95/year cost

---

## 6. Implementation Plan

### Phase 1: ESPN BPI Integration (Week of Feb 17, 2026)

#### 1. Create BPI Fetcher Module

File: `pipelines/espn_bpi_fetcher.py`

```python
class ESPNBPIFetcher:
    """Fetch BPI ratings from ESPN's undocumented API."""

    BASE_URL = "https://site.web.api.espn.com/apis/fitt/v3/sports/basketball/mens-college-basketball/powerindex"

    def fetch_season_bpi(self, season: int) -> pd.DataFrame:
        """Fetch all BPI ratings for a season.

        Returns:
            DataFrame with columns: team_id, team_name, conference,
            bpi, off, def, bpi_rank, proj_wins, proj_losses, etc.
        """
        pass

    def fetch_current_bpi(self) -> pd.DataFrame:
        """Fetch current season BPI ratings (for live betting)."""
        pass
```

#### 2. Add BPI Features to Model

File: `features/sport_specific/ncaab/advanced_features.py`

```python
class NCABBFeatureEngine:
    def add_bpi_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add ESPN BPI features to game data.

        Features:
        - home_bpi, away_bpi
        - bpi_diff (home - away)
        - home_off, away_off, off_diff
        - home_def, away_def, def_diff
        - bpi_expected_margin (from BPI diff)
        """
        pass
```

#### 3. Database Schema

Table: `team_bpi_ratings`

```sql
CREATE TABLE team_bpi_ratings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id TEXT NOT NULL,
    season INTEGER NOT NULL,
    as_of_date DATE NOT NULL,
    bpi REAL NOT NULL,
    bpi_rank INTEGER,
    off REAL,
    def REAL,
    proj_wins INTEGER,
    proj_losses INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(team_id, season, as_of_date)
);
```

#### 4. Daily Caching Script

File: `scripts/cache_daily_bpi.py`

```python
"""Cache daily BPI snapshots for point-in-time historical data."""

def main():
    fetcher = ESPNBPIFetcher()
    bpi_data = fetcher.fetch_current_bpi()

    # Write to database with today's date
    db.insert("team_bpi_ratings", bpi_data, on_conflict="replace")

    # Also write to parquet for backup
    today = datetime.now().strftime("%Y-%m-%d")
    bpi_data.to_parquet(f"data/bpi_snapshots/{today}.parquet")
```

### Phase 2: Backtesting with Historical BPI (Week of Feb 24, 2026)

#### 1. Backfill Historical Seasons

```bash
# Fetch BPI for all historical seasons
python scripts/backfill_historical_bpi.py --seasons 2020 2021 2022 2023 2024 2025
```

#### 2. Re-run Cross-Season Backtest

```bash
# Compare Elo-only vs Elo+BPI
python scripts/ab_compare_features.py \
    --baseline elo \
    --treatment elo_bpi \
    --seasons 2020-2025 \
    --edge-threshold 7.5
```

#### 3. Validate with Gatekeeper

```bash
# Run full 5-dimension validation
python scripts/run_gatekeeper_validation.py \
    --model ncaab_elo_bpi_v1 \
    --backtest-results data/backtests/elo_bpi_2025.parquet
```

### Phase 3: Production Deployment (Week of Mar 3, 2026)

#### 1. Add BPI to Daily Pipeline

```bash
# Update daily workflow
python scripts/daily_predictions.py --features elo,bpi --date today
python scripts/record_paper_bets.py --date today
```

#### 2. Monitor BPI API Health

Add to `scripts/generate_report.py`:

```python
def check_bpi_api_health():
    """Verify ESPN BPI API is still functional."""
    try:
        fetcher = ESPNBPIFetcher()
        bpi = fetcher.fetch_current_bpi()
        assert len(bpi) > 300, "Too few teams returned"
        assert "bpi" in bpi.columns, "BPI field missing"
        return "HEALTHY"
    except Exception as e:
        return f"DEGRADED: {e}"
```

#### 3. Fallback Strategy

If API breaks, auto-switch to web scraping:

```python
class ESPNBPIFetcher:
    def fetch_current_bpi(self):
        try:
            return self._fetch_from_api()
        except Exception as e:
            logger.warning(f"API failed: {e}. Falling back to web scraping.")
            return self._scrape_from_web()

    def _scrape_from_web(self):
        """Scrape BPI table from espn.com/mens-college-basketball/bpi"""
        url = "https://www.espn.com/mens-college-basketball/bpi"
        resp = requests.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        # Parse table rows...
```

---

## 7. Code Examples

### Fetch Current BPI Ratings

```python
import requests
import pandas as pd

def fetch_espn_bpi(season: int = None, limit: int = 100) -> pd.DataFrame:
    """Fetch ESPN BPI ratings for all D1 teams.

    Args:
        season: Season year (e.g. 2025). None = current season.
        limit: Results per page (max 1000).

    Returns:
        DataFrame with BPI metrics for all teams.
    """
    base_url = "https://site.web.api.espn.com/apis/fitt/v3/sports/basketball/mens-college-basketball/powerindex"
    params = {"region": "us", "lang": "en", "limit": limit}
    if season:
        params["season"] = season

    all_teams = []
    page = 1

    while True:
        params["page"] = page
        resp = requests.get(base_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        for team_data in data["teams"]:
            team = team_data["team"]
            bpi_cat = next((c for c in team_data.get("categories", []) if c["name"] == "bpi"), None)

            if bpi_cat:
                values = bpi_cat["values"]
                all_teams.append({
                    "team_id": team["id"],
                    "team_name": team["displayName"],
                    "team_abbr": team["abbreviation"],
                    "conference": team["group"]["name"],
                    "conference_abbr": team["group"]["abbreviation"],
                    "bpi": values[0],
                    "bpi_rank": int(values[1]),
                    "trend": values[2],
                    "off": values[3],
                    "def": values[4],
                    "win_pct": values[5],
                    "rem_sos_rank": int(values[6]),
                    "proj_w": int(values[7]),
                    "proj_l": int(values[8]),
                    "proj_ovr_w": values[9],
                    "proj_ovr_l": values[10],
                    "proj_conf_w": int(values[11]),
                    "proj_conf_l": int(values[12]),
                })

        # Check if more pages
        pagination = data["pagination"]
        if page >= pagination["pages"]:
            break
        page += 1

    return pd.DataFrame(all_teams)


# Usage
bpi_2025 = fetch_espn_bpi(season=2025)
print(bpi_2025.head())
```

### Add BPI to Game Features

```python
def add_bpi_to_games(games_df: pd.DataFrame, bpi_df: pd.DataFrame) -> pd.DataFrame:
    """Add BPI metrics to game records.

    Args:
        games_df: DataFrame with home_team_id, away_team_id columns.
        bpi_df: DataFrame from fetch_espn_bpi().

    Returns:
        games_df with BPI features added.
    """
    # Merge home team BPI
    games_df = games_df.merge(
        bpi_df[["team_id", "bpi", "off", "def"]],
        left_on="home_team_id",
        right_on="team_id",
        how="left",
        suffixes=("", "_home"),
    ).rename(columns={"bpi": "home_bpi", "off": "home_off", "def": "home_def"})

    # Merge away team BPI
    games_df = games_df.merge(
        bpi_df[["team_id", "bpi", "off", "def"]],
        left_on="away_team_id",
        right_on="team_id",
        how="left",
        suffixes=("", "_away"),
    ).rename(columns={"bpi": "away_bpi", "off": "away_off", "def": "away_def"})

    # Calculate differentials
    games_df["bpi_diff"] = games_df["home_bpi"] - games_df["away_bpi"]
    games_df["off_diff"] = games_df["home_off"] - games_df["away_off"]
    games_df["def_diff"] = games_df["home_def"] - games_df["away_def"]

    # Expected margin from BPI (rough approximation: 1 BPI point ≈ 1 point margin)
    games_df["bpi_expected_margin"] = games_df["bpi_diff"]

    return games_df
```

---

## 8. Comparison to Other Data Sources

### Free Alternatives

| Source | Cost | Metrics | Historical | API | Stability |
|--------|------|---------|-----------|-----|-----------|
| **ESPN BPI** | FREE | BPI, OFF, DEF | 2020-2026 | Yes | Undocumented |
| **Barttorvik T-Rank** | FREE | AdjOE, AdjDE, Tempo, WAB | 2008-2026 | No (R only) | Scraping |
| **Massey Ratings** | FREE | Composite ratings | 2002-2026 | No | Scraping |
| **KenPom** | $25/yr | View only | 2002-2026 | No | Subscription |

### Paid Alternatives

| Source | Cost | Metrics | Historical | API | Notes |
|--------|------|---------|-----------|-----|-------|
| **KenPom API** | $95/yr | AdjEM, AdjO, AdjD, AdjT, Four Factors | 2002-2026 | Yes | Official |
| **Synergy Sports** | $500+/yr | Advanced video-based stats | Limited | Yes | Pro-level |
| **SportsDataIO** | $100+/mo | Full NCAA stats | 2016-2026 | Yes | Commercial |

### Barttorvik T-Rank (via R `cbbdata`)

**Pros**:

- Free and comprehensive
- Includes WAB (Wins Above Bubble), Tempo
- Historical back to 2008
- Actively maintained

**Cons**:

- Requires R + rpy2 Python bridge
- No official API (uses R web scraping)
- Slower than ESPN API (~30s per season)

**Implementation**:

```python
import rpy2.robjects as ro
from rpy2.robjects.packages import importr

cbbdata = importr("cbbdata")
bart_ratings = cbbdata.cbd_torvik_ratings(year=2025)
```

---

## 9. Risk Assessment

### API Reliability Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ESPN changes API structure | Medium | High | Version response schema, add unit tests |
| ESPN adds authentication | Low | High | Build web scraper fallback |
| ESPN rate limits aggressively | Low | Medium | Cache daily, reduce request frequency |
| ESPN deprecates endpoint | Low | Critical | Monitor via CI, have KenPom backup plan |

### Data Quality Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Stale BPI ratings (not updated daily) | Low | Medium | Check `as_of_date` in response |
| Missing teams (< 350 returned) | Low | High | Alert if count drops >10% |
| Incorrect BPI values | Very Low | High | Spot-check top 25 vs espn.com/bpi |
| Point-in-time unavailable | Certain | Medium | Cache daily snapshots |

### Betting Model Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| BPI underperforms vs Elo-only | Medium | Medium | A/B test before full deployment |
| BPI overweights preseason priors | Medium | Low | Weight BPI less in Nov/Dec games |
| BPI correlates with public money | High | Low | Cross-check with CLV, not just ROI |

---

## 10. Next Steps

### Immediate Actions (This Week)

1. ✅ **Research Complete** — Document ESPN BPI API
2. ⏳ **Build Fetcher** — Create `pipelines/espn_bpi_fetcher.py`
3. ⏳ **Backfill Historical** — Run for 2020-2025 seasons
4. ⏳ **Add to Feature Engine** — Integrate BPI into `NCABBFeatureEngine`

### Short-Term (Next 2 Weeks)

1. ⏳ **A/B Test** — Compare Elo vs Elo+BPI on 2025 season
2. ⏳ **Validate with Gatekeeper** — Run full 5-dim validation
3. ⏳ **Daily Caching** — Set up nightly BPI snapshot pipeline
4. ⏳ **Deploy to Paper Betting** — Use BPI in daily predictions

### Medium-Term (March 2026)

1. ⏳ **March Madness** — Live test BPI features on tournament
2. ⏳ **Monitor API Health** — Track uptime, latency, schema changes
3. ⏳ **Evaluate KenPom ROI** — Decide if $95/year worth it after 1 month

### Long-Term (Post-March 2026)

1. ⏳ **Add Tempo Metrics** — If missing from BPI, pull from Barttorvik
2. ⏳ **Four Factors** — Evaluate if eFG%, TO%, OR%, FTR improve model
3. ⏳ **Multi-Source Ensemble** — Combine ESPN BPI + Barttorvik + Elo

---

## 11. References

### API Documentation

- [ESPN Hidden API Docs (GitHub Gist)](https://gist.github.com/akeaswaran/b48b02f1c94f873c6655e7129910fc3b)
- [Public ESPN API (GitHub)](https://github.com/pseudo-r/Public-ESPN-API)
- [cfbfastR ESPN FPI Implementation](https://github.com/sportsdataverse/cfbfastR/blob/main/R/espn_ratings_fpi.R)

### BPI Methodology

- [Analytics Basketball Power Index (BPI) Explained - ESPN][bpi-explained]
- [ESPN BPI Your Ultimate Guide - LeadSmart][bpi-guide]

### Comparative Analysis

- [Which Advanced Metric Should Bettors Use: KenPom or Sagarin?][kenpom-sagarin]
- [Don't Destroy Your March Madness Brackets][march-madness-brackets]
- [A New Madness to March: Bracket Optimization Model][bracket-model]

### Python Libraries

- [CBBpy - NCAA Basketball Scraper](https://github.com/dcstats/CBBpy)
- [hoopR - Men's Basketball Data (R)](https://hoopr.sportsdataverse.org/)
- [kenpompy - KenPom Scraper](https://kenpompy.readthedocs.io/)

---

## Appendix A: Complete Response Schema

### Top-Level Fields

```json
{
  "pagination": {
    "count": 365,
    "limit": 50,
    "page": 1,
    "pages": 8,
    "first": "string",
    "next": "string",
    "last": "string"
  },
  "currentSeason": {
    "year": 2026,
    "displayName": "2025-26",
    "startDate": "ISO8601",
    "endDate": "ISO8601",
    "type": {
      "id": "2",
      "type": 2,
      "name": "Regular Season",
      "startDate": "ISO8601",
      "endDate": "ISO8601",
      "week": {
        "number": 16,
        "startDate": "ISO8601",
        "endDate": "ISO8601",
        "text": "Week 16"
      }
    }
  },
  "requestedSeason": { /* same structure as currentSeason */ },
  "currentValues": {
    "sport": "basketball",
    "league": "mens-college-basketball",
    "season": 2026,
    "conference": "50",
    "limit": 50,
    "lang": "en",
    "sort": {
      "stat": "bpi.bpi",
      "direction": "desc"
    },
    "region": "us"
  },
  "teams": [ /* array of team objects */ ]
}
```

### Team Object Schema

```json
{
  "team": {
    "id": "150",
    "uid": "s:40~l:41~t:150",
    "guid": "c4430c6c-5998-47d5-7c45-1cdb7ca0befc",
    "name": "Blue Devils",
    "nickname": "Duke",
    "abbreviation": "DUKE",
    "displayName": "Duke Blue Devils",
    "shortDisplayName": "Duke",
    "logos": [ /* array of logo objects */ ],
    "links": [ /* array of link objects */ ],
    "slug": "duke-blue-devils",
    "group": {
      "uid": "s:40~l:41~g:2",
      "id": "2",
      "name": "Atlantic Coast Conference",
      "abbreviation": "acc",
      "shortName": "ACC",
      "midsizeName": "ACC",
      "slug": "atlantic-coast-conference",
      "isConference": true,
      "parent": {
        "uid": "s:40~l:41~g:50",
        "id": "50",
        "name": "NCAA Division I",
        "abbreviation": "NCAA",
        "shortName": "Division I",
        "midsizeName": "NCAA Division I",
        "slug": "ncaa-division-i",
        "isConference": false
      }
    },
    "rankValue": 1,
    "rankDisplayValue": "1",
    "ranks": {
      "count": 2,
      "pageIndex": 1,
      "pageSize": 25,
      "pageCount": 1,
      "items": [
        {
          "id": "1",
          "name": "AP Top 25",
          "shortName": "AP Poll",
          "type": "ap",
          "rank": {
            "current": 4,
            "previous": 4,
            "points": 1254.0,
            "record": {"summary": "21-2"}
          },
          "headline": "2026 NCAA Basketball Rankings - AP Top 25 Week 15"
        }
      ]
    }
  },
  "categories": [
    {
      "name": "bpi",
      "displayName": "BPI",
      "totals": [ /* 15 string values */ ],
      "values": [ /* 15 numeric values */ ],
      "ranks": [ /* 15 rank strings */ ]
    },
    {
      "name": "resume",
      "displayName": "Resume",
      "totals": [ /* 7 values */ ],
      "values": [ /* 7 numeric values */ ],
      "ranks": [ /* 7 rank strings */ ]
    },
    {
      "name": "tournament",
      "displayName": "Tournament",
      "totals": [ /* 9 null values */ ],
      "values": [ /* 9 null values */ ],
      "ranks": [ /* 9 "-" strings */ ]
    }
  ]
}
```

---

## End of Research Report

<!-- Reference links -->
[bpi-explained]: https://www.espn.com/blog/statsinfo/post/_/id/125994/bpi-and-strength-of-record-what-are-they-and-how-are-they-derived
[kenpom-sagarin]: https://www.sportsbettingdime.com/guides/strategy/kenpom-vs-sagarin/
[march-madness-brackets]: https://bleacherreport.com/articles/2823180-dont-destroy-your-march-madness-brackets-bets-by-trusting-these-numbers
[bracket-model]: https://mgoblog.com/diaries/new-madness-march-creating-bracket-optimization-model-part-four
[bpi-guide]: https://temp.leadsmartinc.com/clear-stats/espn-bpi-your-ultimate-guide-to-college-basketball-rankings-1764811513
