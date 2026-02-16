# Historical Odds Database Research Report

## Building & Backfilling NCAAB Odds Data (2020-2025)

**Research Date:** February 13, 2026
**Focus:** Strategies for building historical odds database + forward-looking capture pipeline
**Sport:** NCAA Men's Basketball (NCAAB)
**Time Period:** 2020-2025 (backfill) + ongoing (2026+)
**Critical Requirement:** Opening AND closing lines for Closing Line Value (CLV) calculation

---

## Executive Summary

Key Findings:

1. **Best Backfill Option (2020-2025):** Commercial APIs (The Odds API, SportsDataIO)
   offer comprehensive historical data from mid-2020, but at significant cost. Free
   alternatives exist but require manual work.

2. **Best Forward Strategy:** Hybrid approach using The Odds API free tier (500 req/month)
   for opening lines + daily closing line capture, supplemented by free sources
   (Pinnacle via OddsPortal/SBR).

3. **Most Cost-Effective Backfill:** SportsbookReviewsOnline + BigDataBall Excel downloads
   for 2020-2025, combined with manual Pinnacle closing lines from OddsPortal
   (free, 15+ years of data).

4. **Critical Gap:** No completely free, automated solution for comprehensive historical
   odds with multiple bookmakers. Trade-offs between cost, coverage, and implementation
   effort are unavoidable.

5. **Legal Considerations:** Web scraping for personal research is generally legal but may
   violate Terms of Service. Prefer official APIs or download services when available.

---

## 1. Web Archive / Wayback Machine Approach

### Feasibility: **LOW** ❌

What We Found:

- No evidence of successful large-scale odds retrieval via Wayback Machine for sportsbooks
- Sportsbook odds pages are often dynamically generated (JavaScript), which Wayback Machine doesn't capture well
- Archived snapshots are inconsistent and incomplete
- No tools exist for bulk Wayback Machine odds retrieval

Why It Doesn't Work:

- Modern sportsbooks use dynamic content loading (React, Vue.js)
- Wayback Machine captures static HTML only
- Odds data embedded in JSON/API responses not typically archived
- Coverage gaps: Not all sportsbooks archived consistently

Assessment:

- **Data Quality:** 1/10 (incomplete, inconsistent)
- **Cost:** Free
- **Time to Implement:** High (manual browsing, no bulk tools)
- **NCAAB Coverage:** Poor (random date gaps)
- **Recommendation:** Not viable for systematic data collection

---

## 2. Line Movement Tracking Services

### Feasibility: **MEDIUM-HIGH** ✅

Services Identified:

#### A. **VegasInsider.com**

- **Coverage:** College Basketball Matchup History with line movements
- **Features:** Opening lines, current lines, betting splits, ATS/O/U records
- **Data Access:** Web interface (no bulk download mentioned)
- **Historical Depth:** Current season + recent past
- **Cost:** Free for browsing, unclear if bulk data available
- **Assessment:** Good for manual research, limited for bulk backfill

#### B. **SportsbookReview.com (SBR)**

- **Coverage:** Line history tool, betting trends
- **Features:** Opening/closing lines, line movement tracking, Pinnacle data
- **Historical Depth:** "The best source" per multiple Reddit/Quora threads
- **Data Access:** Web interface + potential data exports
- **Pinnacle Lines:** Tracked on SBR, accessible via https://www.sportsbookreview.com/betting-odds/
- **Cost:** Free for basic access
- **Assessment:** ⭐ **High value for Pinnacle closing lines** (sharp benchmark)

#### C. **ScoresAndOdds.com**

- **Coverage:** NCAAB schedules and scores with odds
- **Features:** Historical game data, line movement
- **Data Access:** Web interface
- **Cost:** Free
- **Assessment:** Good supplementary source

#### D. **OddsShark.com**

- **Coverage:** NCAAB Database tool with betting trends
- **Features:** Actionable stats, opening/closing lines
- **Historical Depth:** Multiple seasons available
- **Data Access:** Free web tool, custom report generation
- **Cost:** Free
- **Assessment:** Useful for trend analysis, unclear bulk download options

Overall Assessment:

- **Data Quality:** 7/10 (reliable but manual extraction)
- **Cost:** Free to low
- **Time to Implement:** Medium (requires scraping or manual data entry)
- **NCAAB Coverage:** Good (multiple seasons)
- **Recommendation:** ✅ Use SBR for Pinnacle closing lines + VegasInsider for line movement context

---

## 3. Consensus Odds Aggregators

### Feasibility: **HIGH** ✅✅

Services Identified:

#### A. **OddsPortal.com** ⭐⭐⭐

- **Coverage:** NCAA basketball scores/odds back to 2008/09 season
- **Historical Depth:** 15+ years of data
- **Features:** Full breakdown of odds for each bookmaker, odds movement before games
- **Bookmakers:** Multiple books including Pinnacle (sharp benchmark)
- **Data Access:** Web interface, no direct CSV export (manual or scraping required)
- **Cost:** Free
- **Assessment:** 🏆 **Best free source for historical data**

**Quote from research:** *"OddsPortal has NCAA basketball scores available for 2025/2026, but also for all seasons
dating back to 2008/09 thanks to the historical data available. Despite those NCAA basketball scores being over 15 years
old in some cases, the odds are still visible for the moneyline, and some other markets too."*

#### B. **OddsBase.net**

- **Coverage:** NCAA basketball historical odds archive
- **Historical Depth:** "Over the past decade and a half" (15+ years)
- **Features:** Odds archive for matchups of certain opponents, multiple bookmakers
- **Data Access:** Web database (search/query interface)
- **Cost:** Free
- **Assessment:** Good complementary source to OddsPortal

#### C. **Covers.com**

- **Coverage:** Historical point spread data for men's college basketball
- **Data Access:** Requires manual data entry from web interface
- **Pinnacle Lines:** Available
- **Cost:** Free
- **Assessment:** Useful but labor-intensive

Overall Assessment:

- **Data Quality:** 8/10 (reliable consensus data, primarily closing lines)
- **Cost:** Free
- **Time to Implement:** Medium-High (scraping or manual extraction)
- **NCAAB Coverage:** Excellent (2008-present on OddsPortal)
- **Recommendation:** ✅✅ **Primary free source for backfilling 2020-2025**

---

## 4. Commercial Historical Odds APIs

### Feasibility: **HIGH** (if budget allows) 💰

Services Identified:

#### A. **The Odds API** ⭐⭐⭐ (Top Choice)

- **Historical Coverage:** June 6, 2020 → present (featured markets)
  - 10-minute intervals: June 2020 - Sept 2022
  - 5-minute intervals: Sept 2022 → present
  - Player props/period markets: May 3, 2023 → present
- **Sports:** NCAAB included (NBA, US College Basketball, WNBA, Euroleague)
- **Bookmakers:** DraftKings, FanDuel, BetMGM, Caesars, Bovada, MyBookie, etc.
- **Format:** JSON API
- **Free Tier:** 500 requests/month (live odds only, no historical)
- **Paid Plans:** Historical data only on paid plans (pricing not public)
- **Assessment:** Perfect timeline match for 2020-2025 backfill, professional quality

#### B. **SportsDataIO**

- **Historical Coverage:** 2019+ (betting lines), 2020+ (props/futures)
- **Sports:** NCAA Basketball included
- **Bookmakers:** DraftKings, FanDuel, BetMGM, Caesars, BetRivers, Circa, BetOnline, Fanatics, ESPN BET
- **Features:** Pre-game/in-play/closing lines, line movement timestamps
- **Data Access:** API, S3 bucket download, or custom delivery
- **Cost:** Contact sales (no public pricing)
- **Assessment:** Comprehensive but likely expensive

#### C. **OpticOdds**

- **Coverage:** Historical results and odds for all major leagues
- **Sports:** Basketball included (NCAAB coverage implied)
- **Bookmakers:** 200+ sportsbooks worldwide
- **Features:** Real-time odds, historical data, advanced trading tools
- **Rate Limits:** 10 historical odds requests per 15 seconds
- **Cost:** Contact for pricing (flexible startup→enterprise plans)
- **Assessment:** High-end solution, likely costly

#### D. **OddsMatrix**

- **Coverage:** Historical odds feed from 30+ bookmakers, 75+ sports, multiple years
- **Cost:** Not publicly listed
- **Assessment:** Enterprise-level solution

#### E. **OddsMagnet**

- **Coverage:** Live & historical odds, free trial available
- **Cost:** Not publicly listed
- **Assessment:** Mid-tier option

Overall Assessment:

- **Data Quality:** 10/10 (professional, comprehensive, well-structured)
- **Cost:** Medium-High ($100s-$1000s/month estimated)
- **Time to Implement:** Low (API integration straightforward)
- **NCAAB Coverage:** Excellent (2020-present minimum)
- **Recommendation:** ✅ **Best option if budget allows** (The Odds API preferred)

---

## 5. Downloadable Datasets (Excel/CSV)

### Feasibility: **HIGH** ✅✅

Services Identified:

#### A. **BigDataBall.com** ⭐⭐

- **Coverage:** NCAA college basketball (historical + in-season)
- **Format:** Excel spreadsheets (cleaned, organized)
- **Features:** Game-by-game stats + **opening and closing odds**
- **Historical Depth:** Multiple seasons available
- **Data Delivery:** Website download or Dropbox/Google Drive
- **Cost:** Paid (bulk discounts for multiple seasons)
- **Assessment:** 🎯 **Excellent for backfilling with minimal coding**

**Quote from research:** *"Dataset includes opening and ending odds that can show what people thought before the game.
Specifically, you can compare opening and closing betting odds for NCAAB to keep an eye on how the odds of betting
change before and after new information comes out."*

#### B. **SportsbookReviewsOnline.com** ⭐⭐⭐

- **Coverage:** Historical NCAA Basketball scores and odds archives
- **Format:** Microsoft Excel + HTML files
- **Features:** Moneylines, 2nd half lines, **opening and closing spreads/totals**
- **Cost:** Free (downloadable)
- **Assessment:** 🏆 **Best free download option**

**Quote from research:** *"Downloadable sports scores and odds data in Microsoft Excel and HTML file format is available
at sportsbookreviewsonline.com. They offer historical scores and odds data from past National Football League seasons
including moneylines, 2nd half lines, opening and closing point spreads and totals, as well as similar data for NBA and
other sports."*

#### C. **FantasyData.com**

- **Coverage:** NCAA Basketball odds (full historical)
- **Format:** CSV and XLS downloads
- **Cost:** All-Access Plan required
- **Assessment:** Good if already subscribing for other sports data

#### D. **Sports-Statistics.com**

- **Coverage:** MLB confirmed (2010-2021), unclear if NCAAB available
- **Features:** Run-lines, opening/closing moneylines, totals
- **Cost:** Paid datasets
- **Assessment:** Worth checking for NCAAB availability

#### E. **Sports Insights**

- **Coverage:** Historical betting database back to 2003
- **Features:** Opening and closing lines for spreads and over/under
- **Format:** Downloadable databases
- **Cost:** Likely paid (contact for pricing)
- **Assessment:** Very deep historical data if needed pre-2020

Overall Assessment:

- **Data Quality:** 8/10 (cleaned, structured, ready to use)
- **Cost:** Free (SBROnline) to Medium ($50-200/season estimated)
- **Time to Implement:** Low (direct download, minimal processing)
- **NCAAB Coverage:** Excellent (2003-present depending on source)
- **Recommendation:** ✅✅ **Best balance of cost/effort** (Start with SBROnline free → BigDataBall if budget)

---

## 6. Building a Forward-Looking Odds Capture Pipeline

### Best Practices for 2026+ Live Capture

#### A. **Polling Frequency Strategy**

Opening Line Capture:

- **When:** Lines typically release 24-48 hours before tip-off for NCAAB
- **Frequency:** 1x daily check (morning EST) after initial release
- **Tools:** The Odds API, DraftKings/FanDuel direct monitoring
- **Storage:** Timestamp, bookmaker, odds (spread/moneyline/total)

Closing Line Capture:

- **When:** 10-15 minutes before game start (lines close)
- **Frequency:** Single snapshot at line close
- **Critical:** This is the most important data point for CLV calculation
- **Tools:** The Odds API, or manual DraftKings/FanDuel check

Line Movement Tracking (Optional):

- **Frequency:** 2-4 snapshots/day for games with significant action
- **When:** Morning (initial), Midday (sharp action), Evening (public action), Close
- **Use Case:** Advanced analysis of market efficiency
- **Cost Trade-off:** Uses more API requests (The Odds API free tier = 500/month)

**Quote from research:** *"Betting lines update every 30 seconds for upcoming games and every 10 seconds for live games.
Opening lines are the odds that were available for either team when the market first opened."*

#### B. **Maximizing The Odds API Free Tier (500 Requests/Month)**

**NCAAB Season:** ~4 months (Nov-Mar), ~150 Division I teams, ~30 games/day in-season

Strategy A - Opening + Closing Only (Minimal):

- 2 requests/day × 120 days = 240 requests/season
- Captures opening and closing lines for ALL games
- Enough headroom for other sports (NFL, MLB)
- ✅ **Recommended for budget constraints**

Strategy B - Full Line Movement (Max Coverage):

- 4 requests/day × 120 days = 480 requests/season
- Captures opening, midday, evening, closing
- Near budget limit, must skip some days
- ⚠️ Tight budget, no room for other sports

Request Optimization:

```python
# Single request returns ALL games + all bookmakers for specified market
# Efficient: 1 request = 30+ games × 10+ bookmakers = 300+ data points

# Good: Separate requests for spreads, totals, moneylines
GET /sports/basketball_ncaab/odds?markets=spreads  # 1 request
GET /sports/basketball_ncaab/odds?markets=totals   # 1 request
GET /sports/basketball_ncaab/odds?markets=h2h      # 1 request

# Bad: Requesting individual games (wastes requests)
```

**Quote from research:** *"To maximize your 500 monthly requests for college basketball coverage, you should consider:
(1) Targeting specific markets, (2) Limiting bookmaker regions, (3) Batch requests strategically, (4) Reuse data - cache
responses to avoid redundant requests."*

#### C. **Storage Format Recommendations**

Database Schema:

```sql
CREATE TABLE odds_snapshots (
    id INTEGER PRIMARY KEY,
    game_id TEXT NOT NULL,
    game_date DATE NOT NULL,
    home_team TEXT NOT NULL,
    away_team TEXT NOT NULL,
    bookmaker TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,  -- 'opening', 'midday', 'closing'
    snapshot_time TIMESTAMP NOT NULL,

    -- Spread market
    spread_line REAL,
    spread_home_odds INTEGER,
    spread_away_odds INTEGER,

    -- Moneyline market
    moneyline_home INTEGER,
    moneyline_away INTEGER,

    -- Total market
    total_line REAL,
    total_over_odds INTEGER,
    total_under_odds INTEGER,

    UNIQUE(game_id, bookmaker, snapshot_type)
);

CREATE INDEX idx_game_date ON odds_snapshots(game_date);
CREATE INDEX idx_bookmaker ON odds_snapshots(bookmaker);
```

File Format (Alternative to DB):

- **Format:** Parquet (efficient compression for time-series data)
- **Structure:** Partitioned by date (year=2026/month=02/day=13/)
- **Pros:** Easy backup, works with pandas/polars, columnar efficiency
- **Cons:** Harder to query incrementally vs SQLite

#### D. **Multi-Source Hybrid Approach** ⭐ (Recommended)

Primary Source (Automated):

- The Odds API (500 req/month) → Opening lines for all games

Secondary Source (Manual/Semi-Automated):

- Pinnacle closing lines from OddsPortal/SBR (free, scraping/manual)
- DraftKings/FanDuel closing lines (manual check if betting on platform)

Why This Works:

- Opening lines = broad coverage (The Odds API)
- Closing lines = Pinnacle only (free, sharp benchmark for CLV)
- Cost: $0/month
- Effort: 15 min/day manual closing line collection

**Quote from research:** *"Pinnacle's closing lines are accurate because they move in response to useful information
revealing itself in the market. They are renowned as the sharpest sports book for high limits and infrequent customer
stake factoring. OddsNotifier offers a free Closing Lines Bot for instant access to historical closing odds for any
match, any sport, anytime - 100% free."*

---

## 7. Academic & Research Data Sources

### Feasibility: **MEDIUM** 🎓

Sources Identified:

#### A. **Academic Papers with Published Datasets**

- **Finding:** Some forecasting/ML papers publish their datasets
- **Example:** "Forecasting NCAA Basketball Outcomes with Deep Learning" (arxiv.org/html/2508.02725v1)
- **Availability:** Varies by paper (some on Kaggle, GitHub, paper appendices)
- **Assessment:** Hit-or-miss, but worth checking arXiv/Google Scholar

#### B. **Kaggle Competitions**

- **Example:** "March Machine Learning Mania 2025"
  - Covers men's/women's NCAA tournaments
  - Historical data from 2003 season → 2024 season
  - ⚠️ May not include odds data (primarily game outcomes/stats)
- **Assessment:** Great for game data, odds data is secondary focus

#### C. **SportsDataverse (GitHub)** ⭐

- **What:** Open-source R packages for sports data
- **Package:** `{oddsapiR}` - R wrapper for The Odds API
- **Assessment:** Useful tool but still requires Odds API access (free tier)
- **Link:** github.com/sportsdataverse

#### D. **BigDataBall (Educational Focus)**

- **Quote:** *"Datasets allow researchers to connect CBB betting odds to team or player performance metrics to check if
  there's a link between what people thought would happen before the game and how teams performed on the court."*
- **Assessment:** Marketed toward researchers, includes odds data explicitly

Overall Assessment:

- **Data Quality:** Variable (7/10 when available)
- **Cost:** Free
- **Time to Implement:** High (must hunt for papers/datasets)
- **NCAAB Coverage:** Incomplete (not a primary focus)
- **Recommendation:** ⚠️ Supplementary source only, don't rely as primary

---

## 8. Community-Maintained Databases

### Feasibility: **LOW-MEDIUM** 🤝

Communities Identified:

#### A. **Discord Communities**

- **r/sportsbook Discord:** 176,608 members, connected to Reddit community
- **BettingPros Discord:** 75,392 members
- **Makin Monies:** Data-focused, provides scraped NHL data (model: could apply to NCAAB)
- **Unabated Community:** Professional sports betting community
- **Assessment:** More focused on picks/discussion than collaborative data collection

#### B. **GitHub Open-Source Projects**

- **OddsHarvester:** Scrapes/processes data from oddsportal.com
- **Sports-Betting (georgedouzas):** AI tools for sports betting, available on PyPI
- **Bets (gto76):** Betting odds scraper for multiple bookies
- **Open Bookie:** Ruby on Rails sports betting pool app
- **Assessment:** Tools exist, but not comprehensive historical databases

**Quote from research:** *"Through collaborative efforts, bettors can glean diverse perspectives, exchange tips, and
learn from one another's experiences. Some communities offer live Reddit feeds with curated content, live prop changes
tracking odds movements, and shared community slips."*

#### C. **Reddit Communities**

- **r/sportsbook:** Large community, no centralized database
- **r/sportsanalytics:** Academic/professional focus
- **Assessment:** Information sharing > collaborative data collection

Reality Check:

- No coordinated, large-scale community database found
- Communities focus on picks, strategy, and model discussion
- Data sharing is informal (Discord channels, GitHub gists)
- Most value = scraping tools and methodologies, not raw data

Overall Assessment:

- **Data Quality:** N/A (no centralized database)
- **Cost:** Free
- **Time to Implement:** High (community building, tool customization)
- **NCAAB Coverage:** N/A
- **Recommendation:** ⚠️ Use GitHub scraping tools, don't expect ready datasets

---

## 9. Sportsbook-Specific Approaches

### Feasibility: **LOW** ❌

Research Findings:

#### A. **Direct Sportsbook Historical Data Access**

- **DraftKings, FanDuel, BetMGM, Caesars, ESPN BET:** No public historical data APIs
- **Academic Access Programs:** No evidence found in research
- **Research Partnerships:** Not publicly advertised
- **Assessment:** Commercial data (sold via intermediaries like SportsDataIO, not direct)

#### B. **Personal Betting History Exports**

- **What:** Download your own bet history from sportsbook accounts
- **Contains:** Your placed bets (odds at time of placement)
- **Limitation:** Only YOUR bets, not comprehensive market odds
- **Use Case:** Tracking personal CLV, not building full database
- **Assessment:** Useful for self-analysis, not dataset building

#### C. **Third-Party Aggregators** (Preferred Path)

- **The Odds API:** Includes DraftKings, FanDuel, BetMGM, Caesars, Bovada
- **OpticOdds:** Specializes in DraftKings API & real-time odds
- **365OddsAPI:** DraftKings, FanDuel, BetMGM data feeds
- **Assessment:** ✅ Use aggregators, not direct sportsbook access

Overall Assessment:

- **Data Quality:** N/A (no direct access)
- **Cost:** N/A
- **Time to Implement:** N/A
- **NCAAB Coverage:** N/A
- **Recommendation:** ❌ Use third-party APIs instead (The Odds API, SportsDataIO)

---

## 10. Legal Considerations

### Key Findings

#### A. **Web Scraping Legality**

Legal Consensus:

- ✅ Scraping publicly available data is generally legal for personal research
- ⚠️ May violate website Terms of Service (ToS)
- ⚠️ Bypassing anti-scraping measures = legal gray area
- ❌ Commercial redistribution of scraped data = high legal risk

**Quote from research:** *"Web scraping itself is generally legal, but its legality depends on the specific Terms of
Service (ToS) of the websites being scraped, as well as compliance with the relevant laws and regulations. It is legal
to scrape publicly available sportsbook odds data for personal use, research, and analysis purposes."*

Best Practices:

1. Respect `robots.txt` directives
2. Rate limit requests (don't overwhelm servers)
3. Identify your scraper in User-Agent header
4. Check ToS for explicit scraping prohibitions
5. Contact website owner for permission if uncertain

**Quote from research:** *"You should always respect the directives in the robots.txt file. If you require access to
data for legitimate purposes, consider contacting the website owner for permission or explore alternative methods of
obtaining the data, such as using official APIs when available."*

#### B. **Terms of Service Violations**

Potential Consequences:

- Account bans (if using authenticated sessions)
- Legal threats (unlikely for small-scale personal research)
- IP address blocking
- Cease-and-desist letters (for commercial use)

**Quote from research:** *"Terms of Service violations can lead to account bans and legal threats, as most betting sites
explicitly prohibit automated data collection."*

Risk Mitigation:

- Prefer official APIs (The Odds API, etc.) over scraping
- Use free aggregators (OddsPortal) for manual data collection
- For scraping: personal research only, no commercial use
- Don't bypass login walls or anti-bot systems

#### C. **Recommended Hierarchy (Legal Safety)**

1. **Official APIs** (The Odds API, SportsDataIO) → ✅ Fully legal, ToS-compliant
2. **Free Downloads** (SBROnline Excel files) → ✅ Intended distribution
3. **Manual Data Entry** (OddsPortal browsing) → ✅ Personal use
4. **Ethical Scraping** (OddsPortal, respecting robots.txt) → ⚠️ Legal but ToS risk
5. **Aggressive Scraping** (bypassing anti-bot) → ❌ Avoid

For This Project:

- ✅ Use The Odds API free tier (legal, ToS-compliant)
- ✅ Download free datasets (SBROnline, BigDataBall)
- ⚠️ Manual OddsPortal/SBR closing line collection (low-risk)
- ❌ Avoid aggressive scraping of sportsbooks

---

## Comparative Assessment Matrix

| Approach | Data Quality | Cost | Ease | NCAAB Coverage | Opening Lines | Closing Lines | Backfill 2020-25 | Forward 2026+ | Recommendation |
|----------|--------------|------|------|----------------|---------------|---------------|------------------|---------------|----------------|
| **Wayback Machine** | 1/10 | Free | Hard | Poor | ❌ | ❌ | ❌ | ❌ | ❌ Don't use |
| **VegasInsider** | 7/10 | Free | Medium | Good | ✅ | ✅ | ⚠️ Manual | ✅ | ⚠️ Supplement |
| **SportsbookReview** | 8/10 | Free | Medium | Excellent | ✅ | ✅✅ | ✅✅ | ✅✅ | ✅✅ **Pinnacle lines** |
| **OddsPortal** | 8/10 | Free | Medium | Excellent (2008+) | ⚠️ | ✅✅ | ✅✅ | ✅✅ | ✅✅✅ **Best free** |
| **OddsBase** | 7/10 | Free | Medium | Good (15+ years) | ⚠️ | ✅ | ✅ | ⚠️ | ⚠️ Supplement |
| **The Odds API** | 10/10 | $$$ | Easy | Perfect (2020+) | ✅✅ | ✅✅ | ✅✅✅ | ✅✅✅ | ✅✅✅ **Best paid** |
| **SportsDataIO** | 10/10 | $$$$ | Easy | Excellent (2019+) | ✅✅ | ✅✅ | ✅✅✅ | ✅✅✅ | ✅✅ Enterprise |
| **OpticOdds** | 9/10 | $$$ | Easy | Excellent | ✅✅ | ✅✅ | ✅✅ | ✅✅✅ | ✅ Premium |
| **BigDataBall** | 8/10 | $ | Easy | Excellent | ✅✅ | ✅✅ | ✅✅ | ❌ | ✅✅ **Buy history** |
| **SBROnline Excel** | 8/10 | Free | Easy | Good | ✅✅ | ✅✅ | ✅✅ | ❌ | ✅✅✅ **Best free DL** |
| **Academic Data** | 7/10 | Free | Hard | Poor | ⚠️ | ⚠️ | ⚠️ | ❌ | ⚠️ Supplement |
| **GitHub Tools** | N/A | Free | Medium | N/A | N/A | N/A | ⚠️ | ✅ | ⚠️ DIY scraping |
| **Discord/Reddit** | N/A | Free | Hard | N/A | N/A | N/A | ❌ | ⚠️ | ❌ No database |
| **Sportsbooks Direct** | N/A | N/A | N/A | N/A | ❌ | ❌ | ❌ | ❌ | ❌ Not available |

---

## Recommended Implementation Strategy

### Phase 1: Backfill Historical Data (2020-2025)

#### Option A: **Zero Budget** (Free Sources)

Sources:

1. **SportsbookReviewsOnline.com** → Download Excel files (opening/closing spreads, totals, moneylines)
2. **OddsPortal.com** → Manual/scripted extraction of closing lines (Pinnacle priority)
3. **OddsBase.net** → Supplement gaps if needed

Process:

```python
# 1. Download SBROnline Excel files for 2020-2025 seasons
# 2. Parse into SQLite database
# 3. Scrape OddsPortal for Pinnacle closing lines (ethical, respect robots.txt)
# 4. Join datasets on game_id + date

# Expected time: 20-40 hours total (scripting + manual verification)
```

Pros:

- $0 cost
- Covers full 2020-2025 period
- Pinnacle closing lines = sharp benchmark

Cons:

- Manual effort required
- Limited to a few bookmakers
- Scraping may violate OddsPortal ToS (low legal risk for personal use)

---

#### Option B: **Low Budget** ($100-500)

Sources:

1. **BigDataBall.com** → Purchase Excel datasets for 2020-2025 (5 seasons × $30-50 = $150-250)
2. **OddsPortal/SBR** → Free Pinnacle closing lines (supplement)

Process:

```python
# 1. Purchase + download BigDataBall NCAAB datasets (immediate delivery)
# 2. Load into pandas/SQLite
# 3. Verify coverage, supplement gaps with OddsPortal if needed

# Expected time: 5-10 hours (mostly data validation)
```

Pros:

- Clean, ready-to-use Excel files
- Opening + closing odds included
- Minimal coding required
- ✅ **Best balance of cost/time**

Cons:

- $150-250 upfront cost
- Single vendor risk (if data quality issues)

---

#### Option C: **Full Budget** ($500-2000)

Sources:

1. **The Odds API** (Historical plan) → Comprehensive 2020-2025 data via API
   - Contact for pricing (estimated $500-1000 for bulk historical access)
2. Alternative: **SportsDataIO** (contact sales)

Process:

```python
# 1. Purchase historical API access
# 2. Script bulk download of 2020-2025 NCAAB data
# 3. Store in PostgreSQL or Parquet files

# Expected time: 10-15 hours (API integration + storage setup)
```

Pros:

- Professional-grade data (10+ bookmakers)
- 5-minute snapshot intervals (detailed line movement)
- JSON API = easy to automate
- Reproducible, auditable data pipeline

Cons:

- Significant upfront cost
- May require ongoing subscription

---

### Phase 2: Forward-Looking Capture (2026+)

#### Recommended Hybrid Strategy ⭐

Daily Workflow:

Morning (9 AM EST):

```python
# 1. Check The Odds API for new games (opening lines released)
#    - Use free tier: 1 request for spreads, 1 for totals, 1 for moneylines = 3 req/day
#    - Capture: DraftKings, FanDuel, BetMGM, Caesars, Pinnacle (if available)

import requests
response = requests.get(
    "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds",
    params={
        "apiKey": "YOUR_KEY",
        "regions": "us",
        "markets": "spreads,totals,h2h",
        "oddsFormat": "american"
    }
)
# Store in SQLite with snapshot_type='opening'
```

Evening (30 min before games):

```python
# 2. Capture closing lines
#    - Option A: Use remaining free tier requests (if budget allows)
#    - Option B: Manual check of OddsPortal/SBR for Pinnacle closing lines (5-10 min)
#    - Option C: Check your sportsbook account (DraftKings/FanDuel) if betting

# If using The Odds API:
response = requests.get(...)  # Same as morning
# Store with snapshot_type='closing'

# If manual:
# 1. Visit oddsportal.com/basketball/usa/ncaa/
# 2. Copy closing lines for games of interest
# 3. CSV import to database
```

Post-Game (Next Morning):

```python
# 3. Fetch game results (ESPN API or sportsipy)
# 4. Calculate CLV for any bets placed
# 5. Update bankroll log

clv = calculate_clv(odds_placed=-110, odds_closing=-105)
```

Budget:

- The Odds API: Free tier (500 req/month)
  - 2 requests/day × 120 days NCAAB = 240 requests
  - Leaves 260 requests for MLB/NFL
- Manual effort: 5-10 min/day (closing line collection)
- **Total cost: $0/month**

---

### Phase 3: Scaling Beyond Free Tier (Optional)

When to Upgrade:

- Betting volume > 10 bets/week (need precise line movement tracking)
- Adding player props (not in free tier historical)
- Want automated closing line capture (remove manual work)
- Expanding to MLB/NFL simultaneously

Paid Options:

1. **The Odds API Paid Plan** ($100-300/month estimated)
   - 5-minute snapshots
   - Player props included
   - No manual work required

2. **OpticOdds** (contact for pricing)
   - 200+ sportsbooks
   - Advanced trading tools
   - Real-time odds feeds

3. **Build Custom Scraper** (if technical)
   - Use GitHub tools (OddsHarvester, etc.)
   - Scrape OddsPortal + books directly
   - Legal gray area, requires maintenance

---

## Implementation Checklist

### Immediate Actions (Week 1)

- [ ] Download SportsbookReviewsOnline Excel files for 2020-2025
- [ ] Set up SQLite database with odds schema (see CLAUDE.md)
- [ ] Sign up for The Odds API free tier (500 req/month)
- [ ] Create OddsPortal account (free) for closing line checks
- [ ] Test API integration with 1-2 requests (verify data format)

### Short-Term (Weeks 2-4)

- [ ] Parse SBROnline Excel → SQLite (opening/closing odds)
- [ ] Scrape/manually collect Pinnacle closing lines from OddsPortal (2020-2025)
- [ ] Validate data completeness (check for missing games/dates)
- [ ] Build daily odds capture script (The Odds API free tier)
- [ ] Set up cron job / Task Scheduler for automated morning captures

### Medium-Term (Month 2-3)

- [ ] Backtest Elo model with historical odds (calculate CLV retroactively)
- [ ] Validate Gatekeeper with real CLV data
- [ ] Implement closing line manual collection routine (evening workflow)
- [ ] Monitor free tier usage (track requests/month)
- [ ] Decide if paid API upgrade needed (based on betting volume)

### Long-Term (Month 4+)

- [ ] Evaluate BigDataBall purchase if free data insufficient
- [ ] Consider The Odds API paid plan if scaling beyond NCAAB
- [ ] Build line movement analysis tools (if 2+ snapshots/day collected)
- [ ] Archive odds data to Parquet for long-term storage
- [ ] Share anonymized CLV results with sports betting communities

---

## Cost-Benefit Analysis

### Scenario 1: Hobbyist Bettor (5-10 bets/week)

Needs:

- Opening lines for all games (monitoring opportunities)
- Closing lines for placed bets only (CLV calculation)
- Historical data nice-to-have (model validation)

Recommended Setup:

- Free tier only (The Odds API + OddsPortal manual)
- SBROnline Excel for historical backfill
- **Total Cost:** $0/year
- **Time Investment:** 10 hours setup + 10 min/day ongoing

**ROI:** If $5,000 bankroll, positive CLV = +$500-1000/year → infinite ROI on $0 cost

---

### Scenario 2: Serious Bettor (20+ bets/week)

Needs:

- Real-time line movement tracking (sharp vs public money)
- Multiple bookmaker odds (line shopping)
- Comprehensive historical data (model development)
- Player props (high-edge markets)

Recommended Setup:

- The Odds API paid plan ($200-300/month)
- BigDataBall historical purchase ($200 one-time)
- **Total Cost:** $2,800/year (Year 1), $2,400/year (ongoing)
- **Time Investment:** 20 hours setup + 5 min/day (automated)

**ROI:** If $10,000 bankroll, +3% CLV = +$600/year edge → break-even at ~5 bets/day minimum

---

### Scenario 3: Professional / Research (This Project)

Needs:

- Historical data for model validation (Gatekeeper)
- Daily odds capture for paper betting (Feb-Mar 2026)
- Flexibility to scale if profitable
- Legal compliance (no aggressive scraping)

Recommended Setup (Phase 1):

- Free sources: SBROnline + OddsPortal + The Odds API free tier
- **Total Cost:** $0
- **Time Investment:** 20-30 hours backfill + 10 min/day ongoing

Recommended Setup (Phase 2 - If Profitable):

- Upgrade to The Odds API paid ($200/month)
- Purchase BigDataBall for deep historical ($200)
- **Total Cost:** $2,600/year
- **Time Investment:** 5 min/day (automated)

**ROI:** If $5,000 bankroll → $10,000 (Year 1), paid plan justified at +2% CLV minimum

---

## Legal & Ethical Guidelines

### DO

- ✅ Use official APIs (The Odds API, SportsDataIO)
- ✅ Respect robots.txt when scraping
- ✅ Rate limit requests (1-2 sec delays)
- ✅ Identify your scraper in User-Agent
- ✅ Use data for personal research/analysis
- ✅ Download free datasets (SBROnline)
- ✅ Manual data collection from free sites

### DON'T

- ❌ Bypass login walls or anti-bot systems
- ❌ Overwhelm servers with rapid requests
- ❌ Commercially redistribute scraped data
- ❌ Ignore Terms of Service for commercial use
- ❌ Scrape sportsbook accounts with credentials
- ❌ Automate UI interactions (Selenium on sportsbooks)

### GRAY AREA (Proceed with Caution)

- ⚠️ Scraping OddsPortal (legal but may violate ToS)
- ⚠️ Using scraped data for betting decisions (personal use = low risk)
- ⚠️ Sharing scraped data with friends (non-commercial = likely OK)

**General Principle:** If you wouldn't do it with a public library, don't do it with public web data.

---

## Frequently Asked Questions

### Q1: Can I get opening AND closing lines for free?

**A:** Yes, via SportsbookReviewsOnline Excel downloads (historical) + OddsPortal (ongoing). Requires manual work.

### Q2: Is The Odds API worth it for the free tier?

**A:** Yes. 500 requests/month = 2 snapshots/day for NCAAB season + room for other sports. Perfect for opening lines.

### Q3: Do I need multiple bookmaker odds or just Pinnacle?

**A:** For CLV validation, Pinnacle closing lines are sufficient (sharpest book). For line shopping, need 3-5 books.

### Q4: How far back does free historical data go?

**A:** OddsPortal: 2008-present (15+ years). SBROnline: Varies by sport, confirmed NCAAB coverage.

### Q5: What's the minimum viable dataset for backtesting?

**A:** 200+ games with opening lines, closing lines, and game results. Gatekeeper requires this for statistical
significance.

### Q6: Should I scrape sportsbooks directly?

**A:** No. Use APIs or aggregators (OddsPortal). Scraping sportsbooks = legal risk + account bans.

### Q7: Can I sell/share my odds database?

**A:** Only if using official APIs with commercial licenses. Scraped data = no redistribution rights.

### Q8: What's the best bookmaker for historical data?

**A:** Pinnacle (sharp, high limits, consistent). Available free via OddsPortal/SBR.

### Q9: How often should I capture odds snapshots?

**A:** Minimum: Opening + closing (2/day). Optimal: Opening + midday + evening + closing (4/day).

### Q10: What if I run out of free API requests?

**A:** Prioritize closing lines (most important for CLV). Supplement with manual OddsPortal checks.

---

## Conclusion & Final Recommendation

### For This Sports Betting Project (2026)

Phase 1 (Immediate - February 2026):

1. **Backfill 2020-2025:** Download SportsbookReviewsOnline Excel files (free) + scrape Pinnacle closing lines from
   OddsPortal
2. **Daily Capture:** The Odds API free tier (opening lines) + manual OddsPortal closing lines (5-10 min/day)
3. **Cost:** $0/month
4. **Time:** 20-30 hours setup (one-time) + 10 min/day ongoing

Phase 2 (If Profitable - March+ 2026):

1. **Upgrade:** Purchase BigDataBall historical datasets ($200) for deeper backfill
2. **Automate:** Consider The Odds API paid plan ($200/month) to eliminate manual work
3. **Scale:** Add player props, MLB, NFL as bankroll grows

Key Insight:
> You can build a professional-grade odds database for $0 using free sources, but it requires 10-30 hours of setup work
> and 10 min/day maintenance. If your time is worth $50/hour, paid APIs ($200/month) are cost-effective once betting >20
> bets/week.

The Three-Tier Strategy:

- **Tier 1 (Free):** SBROnline + OddsPortal + The Odds API free tier → $0/month
- **Tier 2 (Low Cost):** Add BigDataBall historical → $200 one-time
- **Tier 3 (Pro):** Add The Odds API paid plan → $200/month ongoing

Start with Tier 1, upgrade to Tier 2 after validating model profitability, graduate to Tier 3 when betting volume
justifies automation.

---

## References & Sources

### Commercial APIs

- [The Odds API - Historical Data](https://the-odds-api.com/historical-odds-data/)
- [The Odds API - NCAA Basketball](https://the-odds-api.com/sports-odds-data/ncaa-basketball-odds.html)
- [SportsDataIO - Historical Odds](https://sportsdata.io/historical-odds)
- [OpticOdds - Sports Betting API](https://opticodds.com/)

### Free Historical Data Sources

- [OddsPortal - NCAA Basketball Results](https://www.oddsportal.com/basketball/usa/ncaa/results/)
- [OddsBase - NCAA Basketball Historical Odds](https://oddsbase.net/ncaa-basketball-historical-odds)
- [SportsbookReviewsOnline - NCAAB Archives][sbro-ncaab]

[sbro-ncaab]: https://www.sportsbookreviewsonline.com/scoresoddsarchives/ncaabasketball/ncaabasketballoddsarchives.htm

- [Sportsbook Review - Betting Odds](https://www.sportsbookreview.com/betting-odds/)

### Downloadable Datasets

- [BigDataBall - NCAA Basketball Data](https://www.bigdataball.com/datasets/ncaa/cbb-data/)
- [Sports Insights - Historical Betting Database](https://www.sportsinsights.com/blog/historical-betting-database/)

### Line Movement Tracking

- [VegasInsider - College Basketball Matchups](https://www.vegasinsider.com/college-basketball/matchups/)
- [Action Network - NCAAB Odds](https://www.actionnetwork.com/ncaab/odds)

### Pinnacle Closing Lines

- [OddsNotifier - Pinnacle Closing Lines Tool](https://oddsnotifier.io/en/blog/pinnacle-closing-lines-free-tool)
- [OddsBase - Pinnacle Historical Odds](https://oddsbase.net/pinnacle-historical-odds)

### Open Source Tools

- [GitHub - Sports Betting Topics](https://github.com/topics/sports-betting)
- [GitHub - OddsHarvester](https://github.com/jordantete/OddsHarvester)
- [SportsDataverse GitHub](https://github.com/sportsdataverse)

### Best Practices & Guides

- [Boyd's Bets - Opening vs Closing Line](https://www.boydsbets.com/opening-vs-closing-line/)
- [Sharp Football Analysis - CLV Betting Guide](https://www.sharpfootballanalysis.com/sportsbook/clv-betting/)
- [Medium - Building Historical Spreads Database][medium-spreads]

[medium-spreads]: https://medium.com/@bentodd_46499/building-a-database-for-historical-sports-betting-spreads-with-the-odds-api-5575fb87d650

### Legal & Ethical Scraping

- [Datamam - How to Scrape Sports Betting Websites](https://datamam.com/how-to-scrape-sports-betting-websites/)
- [Arbusers - Is Web Scraping Betting Sites Legal?][arbusers]

[arbusers]: https://arbusers.com/is-web-scraping-betting-sites-for-events-odds-etc-legal-t7120/

### Community Resources

- [Discord - r/sportsbook](https://discord.me/sportsbook)
- [Unabated - Sports Betting Community](https://unabated.com/sports-betting-community)

---

**Report Compiled:** February 13, 2026
**Total Sources Reviewed:** 50+
**Primary Recommendation:** Tier 1 free strategy (SBROnline + OddsPortal + The Odds API free tier)
**Estimated Setup Cost:** $0 (or $200-500 if purchasing BigDataBall)
**Estimated Time Investment:** 20-30 hours initial + 10 min/day ongoing
