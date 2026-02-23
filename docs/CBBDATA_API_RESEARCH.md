# CBBData REST API Research Report

**Date**: 2026-02-16
**Objective**: Find direct REST API access to Barttorvik T-Rank historical ratings with date-specific queries

---

## Executive Summary

### Status: PARTIALLY SUCCESSFUL

**Key Findings**:

1. **Base API URL Identified**: `https://www.cbbdata.com/api/`
2. **Historical Archive Endpoint Found**: YES - with day-by-day data
3. **Date-Specific Queries**: UNCERTAIN - filtering available but exact date parameter not documented
4. **Free Access**: YES - requires free account registration
5. **Authentication**: Username/password login, returns API key

### Critical Gap

**The documentation does NOT explicitly show how to query ratings "as of" a specific date** (e.g., "show me all
team ratings on January 15, 2022"). The archive endpoint supports filtering by `year`, `team`, `conf`, and "any
other data column", but whether a `date` or `day_num` field exists for precise date queries is not documented
in the public materials reviewed.

---

## 1. CBBData API Infrastructure

### Base URLs

| Component | URL |
|-----------|-----|
| Main API Base | `https://www.cbbdata.com/api/` |
| Authentication | `https://www.cbbdata.com/api/auth/login` |
| Current Ratings | `https://www.cbbdata.com/api/torvik/ratings` |
| **Historical Archive** | `https://www.cbbdata.com/api/torvik/ratings/archive` |

### Technology Stack

- **Backend**: Flask + Python
- **Database**: SQL with direct file transfers
- **Update Frequency**: Every 15 minutes during season
- **Data Format**: JSON (some endpoints return Parquet files)

---

## 2. Authentication & Registration

### How to Get Free API Key

**Registration Endpoint**: `https://www.cbbdata.com/api/auth/login` (POST)

**Process**:

1. Create account via R package (only method documented):

   ```r
   library(cbbdata)
   cbd_create_account(username = "your_username", password = "your_password")  # pragma: allowlist secret
   ```

2. API key is emailed to you
3. Login to get API key for HTTP requests:

   ```bash
   curl -X POST https://www.cbbdata.com/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "your_username", "password": "your_password"}'  # pragma: allowlist secret
   ```

4. Response includes `api_key` field
5. Include API key in all subsequent requests as query parameter: `?key={api_key}`

**Alternative**: Store credentials in R environment file, package auto-manages authentication

---

## 3. Historical Ratings Archive Endpoint

### Endpoint Details

**URL**: `https://www.cbbdata.com/api/torvik/ratings/archive`

**Method**: GET (via R package function `get_cbd_file()`)

**Data Coverage**: 2015-present (day-by-day T-Rank ratings)

**Filtering Parameters**:

From R function documentation, the endpoint accepts optional query parameters:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `year` | Filter by season | `year=2023` |
| `team` | Filter by specific team | `team=Duke` |
| `conf` | Filter by conference | `conf=ACC` |
| `...` | "Any other data column" | Not documented |

**Example Request**:

```bash
curl "https://www.cbbdata.com/api/torvik/ratings/archive?year=2023&conf=ACC&key={api_key}"
```

### Return Fields

**Not fully documented**, but based on related functions, likely includes:

- `team` - Team name
- `year` - Season year
- `conf` - Conference
- `barthag` - Projected win % vs average team on neutral court
- `adj_o` - Adjusted offensive efficiency
- `adj_d` - Adjusted defensive efficiency
- `adj_t` - Adjusted tempo
- **`date`** or **`day_num`** - Date field (UNCONFIRMED)

---

## 4. CRITICAL UNKNOWN: Date-Specific Queries

### The Problem

For NCAAB betting model backtesting, we need **point-in-time ratings** - ratings as they existed on the day
before each game. For example:

- Game on 2022-01-15: Need ratings as of 2022-01-14
- Game on 2023-03-10: Need ratings as of 2023-03-09

### What We Know

1. The archive is described as "**day-by-day** T-Rank Ratings" (emphasis in docs)
2. Barttorvik.com has a "Day by Day Stats" page at `barttorvik.com/daily.php`
3. The documentation states data "can be aggregated by date, team, or year"
4. The R function accepts filtering on "any other data column"

### What We DON'T Know

1. **Does the API return a `date` field in the JSON response?**
2. **Can we filter by date**: `?date=20220115` or `?date=2022-01-15`?
3. **Is there a date range query**: `?start_date=X&end_date=Y`?
4. **Is there a `day_num` field** (day number within season)?

### Why This Matters

**Without date-specific queries, we would need to**:

- Download the ENTIRE archive for a season (all teams, all dates)
- Filter client-side to extract ratings for specific dates
- This is inefficient but workable if the dataset includes date fields

**Best case scenario**:

- API supports `?date=YYYYMMDD` parameter
- Returns only ratings for that specific date
- Enables efficient point-in-time queries for backtest

---

## 5. Current Ratings Endpoint (Not Archive)

**URL**: `https://www.cbbdata.com/api/torvik/ratings`

**Method**: GET

**Data**: Year-end T-Rank ratings (2008-present)

**Filtering**: Same as archive (`year`, `team`, `conf`)

**Use Case**: End-of-season analysis only - NOT suitable for backtesting

---

## 6. R Package Source Code Findings

### Key Files Analyzed

| File | Purpose | Key Discovery |
|------|---------|---------------|
| `R/utils.R` | HTTP utilities | Uses `httr2`, dynamic URL construction |
| `R/cbd_torvik_ratings_archive.R` | Archive function | Calls `/api/torvik/ratings/archive` |
| `R/cbd_torvik_ratings.R` | Current ratings | Calls `/api/torvik/ratings` |
| `R/cbd_login.R` | Authentication | POST to `/api/auth/login` |

### Request Construction Pattern

```r
# From utils.R
get_url <- function(base_url, ...) {
  args <- get_args(...)
  args$key <- Sys.getenv("CBD_API_KEY")
  httr::modify_url(base_url, query = args)
}
```

**Implication**: Any parameters passed to R functions become query string parameters in HTTP request.

### Archive Function Signature

```r
cbd_torvik_ratings_archive <- function(...) {
  get_cbd_file("https://www.cbbdata.com/api/torvik/ratings/archive", ...)
}
```

**Implication**: The `...` argument means ANY named parameter gets passed to API - if `date` field exists in
data, `cbd_torvik_ratings_archive(date = "2022-01-15")` should work.

---

## 7. Direct Barttorvik.com Access

### Website Endpoints

| Page | URL | Functionality |
|------|-----|---------------|
| T-Rank Main | `barttorvik.com/trank.php` | Current season ratings |
| Day by Day | `barttorvik.com/daily.php` | Historical day-by-day stats |

### Verification Issues

Both URLs returned Cloudflare browser verification pages during testing - could not access actual page
structure to inspect:

- URL parameters
- Form fields
- Network requests
- JSON endpoints

### Known Patterns (from R code)

```r
# From utils.R - generate_trank_factors_url()
base_url <- "https://barttorvik.com/trank.php"
params <- list(year = year, quad = quad, venue = venue, type = type)
```

**Implication**: The main `trank.php` accepts parameters, but **no date parameter documented**.

---

## 8. Comparison: toRvik vs cbbdata

### Historical Context

**toRvik** (predecessor package):

- Used web scraping against barttorvik.com
- Had `bart_archive()` function with `date` parameter (format: YYYYMMDD)
- Direct website access, no API key required
- Slower, less reliable

**cbbdata** (current package):

- Dedicated Flask REST API
- Requires free API key
- Faster, more reliable
- Better documentation (but still incomplete on date queries)

---

## 9. Alternative Data Sources

### KenPom Integration

**URL**: Via cbbdata API (requires paid KenPom subscription)

**Endpoint**: `https://www.cbbdata.com/api/kenpom/ratings` (inferred)

**Requirements**:

- Active KenPom subscription ($25/year)
- Email must match between cbbdata and KenPom accounts
- Prevents account sharing

**Archive**: `https://www.cbbdata.com/api/kenpom/ratings/archive` (likely exists)

**Advantage**: KenPom has better documentation on point-in-time ratings

---

## 10. Recommended Next Steps

### Immediate Actions

1. **Register for cbbdata account** (5 minutes):
   - Install R temporarily OR
   - Find account registration webpage (not documented but may exist)

2. **Test archive endpoint directly** (10 minutes):

   ```bash
   # Get API key via login
   curl -X POST https://www.cbbdata.com/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "test", "password": "test"}'  # pragma: allowlist secret

   # Test archive endpoint
   curl "https://www.cbbdata.com/api/torvik/ratings/archive?year=2023&key={api_key}"

   # Inspect JSON response for date fields
   ```

3. **Check for date parameter support**:

   ```bash
   # Try date parameter
   curl "https://www.cbbdata.com/api/torvik/ratings/archive?year=2023&date=20230115&key={api_key}"

   # Try date range
   curl "https://www.cbbdata.com/api/torvik/ratings/archive?year=2023&start_date=20230115&end_date=20230120&key={api_key}"
   ```

4. **Examine full response structure**:
   - Count records returned
   - Check for date/day_num fields
   - Verify data granularity (one rating per team per day?)

### Fallback Options

**If date-specific queries NOT supported**:

1. **Download entire season archive**:

   ```bash
   curl "https://www.cbbdata.com/api/torvik/ratings/archive?year=2023&key={api_key}" -o 2023_archive.json
   ```

2. **Filter client-side in Python**:

   ```python
   import pandas as pd
   df = pd.read_json("2023_archive.json")
   # Filter by date column (if exists)
   ratings_on_date = df[df['date'] == '2023-01-15']
   ```

3. **Cache locally** to avoid repeated downloads

**If no date field exists in archive**:

- Consider KenPom API (paid but well-documented)
- Fall back to ESPN BPI ratings (free, less accurate)
- Use end-of-season ratings with caveats (introduces look-ahead bias)

---

## 11. Contact & Support

### Developer

**Andrew Weatherman**

- GitHub: [@andreweatherman](https://github.com/andreweatherman)
- Website: [cbbdata.aweatherman.com](https://cbbdata.aweatherman.com/)

### Issue Tracker

GitHub Issues: <https://github.com/andreweatherman/cbbdata/issues>

**Recommended Question to Ask**:

> "Does the `/api/torvik/ratings/archive` endpoint support filtering by specific date? I need to query
> ratings as they existed on a specific historical date (e.g., 2022-01-15) for backtesting purposes.
>
> If supported, what is the correct date parameter format? If not, does the response include a date field
> so I can filter client-side after downloading the full archive?"

---

## 12. Conclusions

### What We Learned

1. **REST API exists and is accessible** - `https://www.cbbdata.com/api/`
2. **Historical archive endpoint confirmed** - `/torvik/ratings/archive` with day-by-day data
3. **Free API key available** - via account registration
4. **R package is thin wrapper** - HTTP calls can be replicated in Python

### Critical Unknown

**Date-specific query support is UNDOCUMENTED** - need to test empirically.

### Risk Assessment

| Risk | Probability | Mitigation |
|------|-------------|------------|
| No date parameter support | Medium | Download full archive, filter client-side |
| No date field in response | Low | Fall back to KenPom or end-of-season ratings |
| API rate limits not documented | High | Start conservative (1 req/sec), monitor |
| API instability/downtime | Low | Cache aggressively, build fallback pipeline |

### Recommendation

**PROCEED with testing** - the infrastructure is solid (Flask API, free access, historical data), and even
worst-case (no date queries) is workable by downloading full season archives and filtering locally.

**Estimated implementation time**:

- Account registration: 5 minutes
- API testing: 30 minutes
- Python client wrapper: 2 hours
- Integration with backtest pipeline: 4 hours
- **Total**: ~1 day of work

**Expected value**: High - Barttorvik ratings are widely respected, and point-in-time ratings will
significantly improve backtest accuracy vs current Elo-only model.

---

## References

- [CBBData GitHub Repository](https://github.com/andreweatherman/cbbdata)
- [CBBData Package Documentation](https://cbbdata.aweatherman.com/)
- [Introducing The CBBData API](https://cbbdata.aweatherman.com/articles/release.html)
- [Package Index - cbbdata](https://cbbdata.aweatherman.com/reference/index.html)
- [T-Rank Archive - toRvik](https://www.torvik.dev/reference/bart_archive.php)
- [Barttorvik Day by Day Stats](https://barttorvik.com/daily.php)
- [toRvik Package (predecessor)](https://torvik.sportsdataverse.org/)
- [What Are Torvik Ratings? - Odds Shark](https://www.oddsshark.com/ncaab/what-are-torvik-ratings)
