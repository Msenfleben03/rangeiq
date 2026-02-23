# CBBData API Quick Start Guide

**Last Updated**: 2026-02-16

This guide walks you through testing the CBBData REST API for Barttorvik T-Rank ratings access.

---

## TL;DR - What You Need to Know

1. **API exists and is accessible**: `https://www.cbbdata.com/api/`
2. **Historical archive endpoint confirmed**: Day-by-day ratings 2015-present
3. **Free access**: Requires account registration
4. **Critical gap**: Date-specific query format NOT documented - must test empirically

---

## Step 1: Get API Key (5 minutes)

### Option A: Use R Package (Recommended)

```r
# Install package
install.packages("devtools")
devtools::install_github("andreweatherman/cbbdata")

# Create account
library(cbbdata)
cbd_create_account(username = "your_username", password = "your_password")  # pragma: allowlist secret
# Check email for API key

# OR login if account exists
cbd_login(username = "your_username", password = "your_password")  # pragma: allowlist secret
```

### Option B: Direct HTTP (Untested)

```bash
# Try direct login
curl -X POST https://www.cbbdata.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "your_username", "password": "your_password"}'  # pragma: allowlist secret

# Response should include: {"api_key": "YOUR_KEY_HERE", ...}  # pragma: allowlist secret
```

**Note**: Account registration via direct HTTP not documented. R package may be required.

---

## Step 2: Test Archive Endpoint (10 minutes)

Use the included Python test script:

```bash
cd C:\Users\msenf\sports-betting

# Test login (if you have credentials)
python scripts/test_cbbdata_api.py --login myuser mypass

# Test basic archive query
python scripts/test_cbbdata_api.py --test-archive YOUR_API_KEY --year 2023

# Test date query formats
python scripts/test_cbbdata_api.py --test-dates YOUR_API_KEY

# Save sample data for inspection
python scripts/test_cbbdata_api.py --save-sample YOUR_API_KEY 2023
```

---

## Step 3: Inspect Response Schema

After running `--save-sample`, check:

```bash
# View sample data
cat data/external/barttorvik_archive_2023_sample.json | head -100

# View schema analysis
cat data/external/barttorvik_archive_2023_sample.schema.json
```

### What to Look For

**Critical Questions**:

1. **Date field exists?**
   - Look for: `date`, `game_date`, `day_num`, `day`, `timestamp`
   - Example: `"date": "2023-01-15"` or `"day_num": 50`

2. **Date format?**
   - ISO format: `2023-01-15`
   - Integer: `20230115`
   - Day number: `50` (days since season start)

3. **One row per team per day?**
   - Count records for one team
   - Should have ~120-150 records per season (Nov-Mar)

4. **Expected fields present?**
   - `team`, `conf`, `year`
   - `barthag` (win probability)
   - `adj_o`, `adj_d`, `adj_t` (efficiency + tempo)

---

## Step 4: Test Date Queries

The test script tries multiple date parameter formats:

```bash
# Test format 1: YYYYMMDD
?year=2023&date=20230115

# Test format 2: ISO date
?year=2023&date=2023-01-15

# Test format 3: Date range
?year=2023&start_date=20230115&end_date=20230120

# Test format 4: Day number
?year=2023&day_num=50
```

**Expected Outcomes**:

- **Best case**: One format returns filtered results → Date queries supported ✓
- **Neutral case**: All return same full dataset → Must filter client-side
- **Worst case**: All return errors → Date parameter not supported (unlikely)

---

## Step 5: Integration Plan

### If Date Queries Supported

```python
# Efficient point-in-time queries
import requests

def get_ratings_on_date(date: str, year: int, api_key: str) -> list[dict]:
    """Get all team ratings as of specific date"""
    url = "https://www.cbbdata.com/api/torvik/ratings/archive"
    params = {
        "year": year,
        "date": date,  # Use format that worked in testing
        "key": api_key
    }
    response = requests.get(url, params=params)
    return response.json()

# Use in backtest
game_date = "2023-01-15"
ratings = get_ratings_on_date(game_date, 2023, api_key)
duke_rating = next(r for r in ratings if r['team'] == 'Duke')
```

### If Date Queries NOT Supported

```python
# Download once, cache locally, filter client-side
import json
from pathlib import Path

def cache_season_ratings(year: int, api_key: str) -> None:
    """Download and cache full season archive"""
    url = "https://www.cbbdata.com/api/torvik/ratings/archive"
    params = {"year": year, "key": api_key}
    response = requests.get(url, params=params)

    cache_file = Path(f"data/external/barttorvik_{year}.json")
    with open(cache_file, "w") as f:
        json.dump(response.json(), f)

def get_ratings_on_date_cached(date: str, year: int) -> list[dict]:
    """Get ratings from cached archive"""
    cache_file = Path(f"data/external/barttorvik_{year}.json")
    with open(cache_file) as f:
        all_ratings = json.load(f)

    # Filter by date field (name depends on testing results)
    return [r for r in all_ratings if r['date'] == date]

# Pre-download all seasons once
for year in range(2020, 2026):
    cache_season_ratings(year, api_key)

# Use in backtest (fast, no API calls)
ratings = get_ratings_on_date_cached("2023-01-15", 2023)
```

---

## Fallback Options

### If API Fails or Date Field Missing

#### Priority 1: KenPom API ($25/year)

- Better documentation
- Proven cbbdata integration
- Same Flask API infrastructure
- Implement after first $100 profit

#### Priority 2: End-of-Season Ratings

- Use year-end `barthag` as proxy
- Introduces look-ahead bias (acceptable for initial testing)
- Document bias in validation report

#### Priority 3: ESPN BPI

- Free, available via undocumented API
- Less accurate (no venue adjustment)
- Use as benchmark only

---

## Rate Limiting (Unknown)

**Assume conservative limits until tested**:

- 1 request per second (60/min)
- 1000 requests per day
- Cache aggressively
- Implement exponential backoff on 429 errors

**Test empirically**:

```python
import time
import requests

# Spam 100 requests, measure when rate limited
for i in range(100):
    response = requests.get(url, params=params)
    print(f"{i}: {response.status_code}")
    if response.status_code == 429:
        print(f"Rate limited after {i} requests")
        break
    time.sleep(0.1)  # 10 req/sec
```

---

## Expected Integration Timeline

| Task | Time | Status |
|------|------|--------|
| Get API key | 5 min | TODO |
| Test endpoints | 30 min | TODO |
| Implement Python client | 2 hours | TODO |
| Add to backtest pipeline | 4 hours | TODO |
| Re-run validation | 1 hour | TODO |
| **Total** | **~1 day** | - |

---

## Success Metrics

### Immediate (Testing Phase)

- [ ] API key obtained
- [ ] Archive endpoint returns data
- [ ] Date field identified in response
- [ ] Date queries tested (supported or not)
- [ ] Sample data cached locally

### Integration Phase

- [ ] Python client wrapper implemented
- [ ] Ratings cached for 2020-2025 seasons
- [ ] Point-in-time queries validated (no look-ahead)
- [ ] Integrated with `backtest_ncaab_elo.py`
- [ ] A/B comparison: Elo-only vs Elo+Barttorvik

### Validation Phase

- [ ] Sharpe improvement: 0.62 → >0.8 (target)
- [ ] CLV improvement: 1.67% → >2.0% (target)
- [ ] TemporalValidator passes (0 leaky features)
- [ ] Gatekeeper validation: PASS (was QUARANTINE)

---

## Questions to Ask Developer (If Needed)

If testing reveals gaps, open GitHub issue:

**Repository**: <https://github.com/andreweatherman/cbbdata/issues>

**Question Template**:

> **Subject**: Date-specific queries for `/api/torvik/ratings/archive`
>
> Hi Andrew,
>
> I'm using the cbbdata API for NCAAB betting model backtesting and need point-in-time ratings
> (ratings as they existed on specific historical dates). The documentation mentions the archive
> endpoint provides "day-by-day" data, but I couldn't find the date parameter format.
>
> **Questions**:
>
> 1. Does `/api/torvik/ratings/archive` support filtering by specific date?
> 2. If yes, what parameter format: `?date=20230115`, `?date=2023-01-15`, `?day_num=N`?
> 3. What date-related fields are included in the response JSON?
> 4. If date queries aren't supported, can I download the full archive and filter client-side?
>
> **Use case**: For each game on 2023-01-15, I need team ratings as of 2023-01-14 (before game)
> to avoid look-ahead bias.
>
> Thanks for the excellent API!

---

## Resources

- **Test Script**: `scripts/test_cbbdata_api.py`
- **Research Report**: `docs/CBBDATA_API_RESEARCH.md`
- **ADR-017**: `docs/DECISIONS.md` (decision rationale)
- **GitHub**: <https://github.com/andreweatherman/cbbdata>
- **Docs**: <https://cbbdata.aweatherman.com/>
