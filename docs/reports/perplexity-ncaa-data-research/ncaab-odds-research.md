# Deep-Scope Guide to Historical NCAA Basketball Betting Odds (2018–2025)

## Executive overview

Historical opening and closing NCAA men’s basketball odds at multi-book granularity from 2018–2025 are not available from any single free source; practitioners combine frozen archives (e.g., SBRO), commercial odds APIs, and heavy scraping of odds screens such as OddsPortal and TeamRankings to synthesize a workable dataset. Commercial APIs like The Odds API and SportsDataIO provide the only well-documented multi-book historical feeds that explicitly include NCAAB, while community tools like OddsHarvester and various OddsPortal scrapers are the de facto approach for broader bookmaker coverage when engineering effort is available. A small number of niche datasets (e.g., Kaggle basketball-odds-history, BigDataBall’s NCAAB spreadsheets) and one-off scrapers round out the ecosystem, but most serious modelers end up building their own ETL around one or two primary sources, then backfilling gaps with scrapes or paid data.[^1][^2][^3][^4][^5][^6]

***

## 1. Problem framing: what "historical NCAAB odds" really means

For model-building, “historical NCAA basketball odds” usually implies:

- Pre-game markets (spread, total, moneyline) for every Division I game, including opening and closing prices.[^5][^1]
- Coverage across multiple sportsbooks to study line discrepancy, market efficiency, and closing line value (CLV).[^6]
- Continuous coverage for at least 5–8 seasons (here, 2018–2025), including pandemic-affected seasons and post-PASPA U.S. market expansion.[^6]

These requirements create three distinct acquisition strategies:

1. **Aggregated historical feeds (APIs or bulk files)** – multi-book odds snapshots from data providers (The Odds API, SportsDataIO, Sports Game Odds, etc.).[^2][^7]
2. **Frozen public archives and retail analytics tools** – SBRO, BigDataBall, Bet Labs/Action Network, KillerSports, TeamRankings BetIQ.[^8][^1][^5]
3. **Scraping odds screens and bookmaker sites** – OddsPortal, individual books, or stats sites with embedded consensus lines, using community scrapers like OddsHarvester or OddsPortal-specific GitHub repos.[^9][^3][^4]

The sections below enumerate concrete sources in each bucket, how practitioners actually access them, and known working scrapers or code.

***

## 2. Commercial odds APIs with NCAAB historical coverage

### 2.1 The Odds API (strongest value for 2020–2025)

- **Coverage and history**: The Odds API exposes NCAAB odds via sport key `basketball_ncaab`; historical snapshots for featured markets (moneyline, spreads, totals) start on 2020-11-16 with 10-minute intervals, improving to 5-minute intervals from September 2022.[^2][^6]
- **Bookmakers**: Documentation lists 40+ bookmakers across US, EU, and other regions, including major U.S. operators and sharp books like Pinnacle (via their EU region).[^2][^6]
- **Access pattern**: REST JSON endpoints for both current and historical odds; examples show querying by sport, region, and markets, e.g., `basketball_ncaab` with `markets=h2h,spreads,totals` and `regions=us`.[^2]
- **Historical mechanism**: Historical data is served as time-stamped snapshots at 10- or 5-minute cadence; the provider lists NCAAB and WNCAAB in its historical coverage table, with specific start timestamps.[^6]
- **Scrapers / tooling**:
  - Official language samples (including Python) in their docs, plus an R wrapper `oddsapiR` in the SportsDataverse GitHub org that wraps The Odds API endpoints.[^10]
  - In practice, modelers build custom pullers that iterate over date ranges and regions, store snapshots to S3 or databases, then reconstruct opening/closing lines from the snapshot sequence.

**Relevance to 2018–2025**: Provides dense, multi-book coverage from late 2020 onward; 2018–2020 must be backfilled from other sources.

### 2.2 SportsDataIO historical odds

- **Product**: SportsDataIO advertises a comprehensive historical odds database for pre-game, in-play, and futures markets across major sports, including NCAA basketball via its odds products.[^7]
- **Access**: Historical odds are sold as part of enterprise offerings (API plus S3 “Vault” bulk downloads). Integration is via REST endpoints and bulk feeds; no self-serve hobbyist tier is documented for deep historical odds.[^7]
- **Granularity**: Every line movement is timestamped across multiple U.S. sportsbooks; this includes opening and closing lines, alternate lines, props, and futures.[^1][^7]
- **Usage**: Common among funded trading operations and sportsbooks; for individual modelers, cost is usually prohibitive, but it is one of the only ways to obtain fully auditable, tick-level line histories across regulated U.S. books.

**Relevance**: Strong commercial option for 2019–2025 NCAAB across multiple books when budget allows, typically accessed via bulk S3 dumps for backfills and API for ongoing updates.[^7]

### 2.3 Sports Game Odds API (niche but used in the community)

- **Scope**: Sports Game Odds markets itself as a multi-sport odds provider with coverage of 80+ bookmakers and 25+ sports; community discussions mention its use alongside The Odds API for historical odds access.[^11]
- **Evidence of NCAAB usage**: A public March Madness prediction GitHub repo (`BracketBrain`) fetches NCAA basketball betting odds from `sportsgameodds.com` and writes them to CSV, confirming a working path to NCAAB odds.[^12]
- **Access pattern**: REST API called from user code to dump moneyline and spreads into CSVs; Reddit comments highlight that its historical data is cheaper than some A-tier APIs but more limited in scope.[^11]

**Relevance**: Viable alternative or complement to The Odds API for NCAAB odds, especially if cost or limits differ; current depth and back history need direct verification but practitioners demonstrably use it.[^12][^11]

### 2.4 Other odds APIs occasionally mentioned

Community posts and reviews mention several other odds feeds; these are less directly documented for college basketball but appear in practitioner stacks:[^13][^14]

- **Oddspapi / OddsAPI (not The Odds API)** – Reddit threads on historical odds mention Oddspapi as providing complimentary historical data “down to the second”, including Pinnacle and Bet365 coverage; branding overlaps with multiple vendors, but it is cited explicitly as a historical odds provider.[^13]
- **OddsJam API** – tied to OddsJam’s line-shopping product; rarely used as a raw data feed due to price, but appears in r/algobetting discussions as a source of multi-book odds and line histories.[^15][^6]
- **OpticOdds, Sportradar, other enterprise feeds** – primarily target B2B operators and professional quants, with historical odds available but behind high pricing and NDAs, so they are underrepresented in open communities.[^1][^7]

These feeds matter mainly because they define the upper bound on data quality and coverage; most individual modelers reverse engineer similar coverage via scraping or mid-tier APIs.

***

## 3. Frozen archives and one-off datasets with NCAAB odds

### 3.1 SportsbookReviewsOnline (SBRO) – free 2007–2022 archive

- **Dataset**: SBRO publishes downloadable Excel workbooks with odds for major US sports, including NCAAB, with opening and closing spreads, totals, moneylines, and some second-half lines.[^1]
- **Coverage**: All Division I NCAAB games from 2007–08 through 2021–22 seasons with consensus lines based on a DonBest rotation feed (not individual sportsbook quotes).[^1]
- **Access**: Direct Excel downloads; no API. The archive is frozen and no longer updated beyond 2021–22.[^16][^1]

**Relevance to 2018–2025**: Provides NCAAB consensus opening and closing odds for 2018–19 through 2021–22; 2022–23 onward must be sourced elsewhere.

### 3.2 BigDataBall NCAAB spreadsheets (stats + odds)

- **Product**: BigDataBall sells season-level Excel files for NCAAB that combine team and player box scores with betting odds fields such as opening and ending spreads and totals for every Division I game.[^8]
- **Content**: Documentation states that NCAAB spreadsheets include game logs for every D1 game, advanced team stats, and “betting odds: opening and ending odds” as columns.[^8]
- **Access**: One-time purchases per season, with discounts for multi-season bundles; files are download-only (no API) but are structured and consistent across years, which simplifies ETL.[^8][^1]

**Relevance**: A highly practical way to cover multiple seasons (including 2018–2025 as they are released) with pre-joined stats and odds, though odds are typically consensus rather than per-book.

### 3.3 Scottfree Analytics NCAAB CSVs (ML-ready)

- **Scope**: Scottfree Analytics offers sport-specific CSVs designed for machine learning, with 132 columns including closing odds, derived target variables, and rich game-level features; separate SKUs exist for NCAAB and NCAAF.[^1]
- **Odds content**: Each game record includes point spread, total, and moneyline data captured close to game time (e.g., within one hour of tip), plus encoded win/loss outcomes, making these files ready for supervised learning.[^1]
- **Access**: One-time purchase per sport (e.g., NCAAB) with CSV download; no official API.

**Relevance**: Offers a straightforward way to get at least one “book-ish” closing line for 10+ seasons into ML workflows, albeit without explicit multi-book disaggregation.

### 3.4 TeamRankings BetIQ NCAAB line-history tools

- **Site feature**: TeamRankings’ BetIQ section includes NCAAB line-history pages such as “Win-Loss + Spread Records By Closing Spread”, covering 2003–04 onward.[^5]
- **Content**: Tables show ATS and over/under records keyed by closing spread and total; although they do not expose per-game lines directly, they imply the existence of an internal NCAAB odds database dating back to at least 2003.[^5]
- **Access pattern**: Easiest programmatic extraction uses `pandas.read_html` on the HTML tables, as community threads demonstrate for similar TeamRankings tables; an older GitHub `TeamRankingsWebScraper` is referenced but reported as outdated.[^17]

**Relevance**: Direct odds per game are not available out-of-the-box, but scraping these summary tables or reverse engineering underlying endpoints is a known approach in quant communities when budget is constrained.

### 3.5 Kaggle basketball-odds-history dataset

- **Dataset**: A Kaggle dataset titled “Basketball-odds-history” aggregates basketball odds across NBA, WNBA, and “college” basketball, with odds in European format and repeated scraping attempts.[^18]
- **Coverage**: Public description lists “global, NBA, college, and WNBA basketball odds,” but exact date range and bookmaker list are not visible without Kaggle login.[^18]
- **Origin**: The dataset is described as scraped, implying an underlying odds portal or bookmaker site source; it could be a ready-made starting point for at least some recent seasons of NCAAB odds.

**Relevance**: A rare public dump that explicitly mentions “college basketball odds”; given Kaggle’s typical licensing, it is often used as a quick prototype dataset or for replicating published analyses rather than as production-grade input.

### 3.6 Other academic and institutional references

Academic work on NCAA basketball betting markets (e.g., studies on efficiency and favorite–underdog bias) often builds bespoke datasets from newspaper archives, bookmaker feeds, or proprietary vendors; they rarely publish full odds tables, but the references can hint at usable data providers. University sports-data lists such as Ohio State’s Sports and Society Initiative catalog general CBB data sources (Sports-Reference, NCAA stats) but not odds; odds-specific datasets like[^19]
BaseballOdds are listed only for MLB.[^20]

**Relevance**: These sources are more useful for understanding market behavior than as direct odds feeds; however, reading their methodology sections can reveal vendors (e.g., DonBest, Sports Insights) that still sell similar NCAAB packages.

***

## 4. Multi-book odds comparison sites and scrapers

### 4.1 OddsPortal – core multi-book source (requires scraping)

- **Site**: OddsPortal lists pre-game odds for dozens of sports, including NCAA basketball, across 80+ bookmakers, with separate tabs for opening, closing, and odds movement.[^21][^9][^1]
- **NCAAB coverage**: Public descriptions note NCAAB results available from at least the late 2000s; user-written scrapers regularly target NBA and football, with code easily generalizable to NCAAB leagues.[^22][^23][^9]
- **Access friction**: Pages are dynamically rendered with JavaScript, making raw HTTP scraping insufficient; Selenium or similar browser automation is needed to render odds tables and follow per-match links for book-level prices.[^9][^22]

**Known scrapers and tools:**

- **OddsHarvester (jordantete/OddsHarvester)** – An open-source CLI app to scrape historical and upcoming odds from OddsPortal, extract match metadata, and export JSON/CSV or stream to S3, with proxy support and Docker images.[^24][^25][^3]
- **gingeleski/odds-portal-scraper and oddsporter** – Python-based full-site scrapers with `full_scraper` capable of scraping nearly any sport to JSON; `oddsporter` is an archived but still-readable repo explicitly tested on NBA, NFL, NHL, etc., and is adaptable to NCAAB via config files.[^4][^26]
- **Apify Betting Odds Scraper** – A commercial no-code actor (“Betting Odds Scraper”) that scrapes OddsPortal’s odds across multiple sports into structured JSON.[^21]
- **WebHarvy and Simplescraper templates** – Visual scraping tools that publish step-by-step recipes or prebuilt configs for extracting opening/closing odds and bookmaker-specific prices from OddsPortal pages.[^27][^9]
- **ScrapeHero tutorial** – A detailed guide to scraping OddsPortal with Selenium, including dealing with dynamic loading and extracting odds across matches and bookmakers.[^22]

**Relevance**: For multi-book, book-level NCAAB odds back to ~2008–09, OddsPortal plus OddsHarvester or a similar scraper is the de facto community standard, especially among technically inclined bettors on Reddit’s r/algobetting.[^25][^24]

### 4.2 Sportsbook Review (SBR) and the FinnedAI scraper

- **Site**: Historically, SportsbookReview (SBR) hosted multi-book odds screens for major US sports, including NCAAB, with line history.[^1]
- **Scraper**: The open-source FinnedAI SportsbookReview scraper project publishes pre-scraped NFL/NBA/MLB/NHL CSVs from SBR plus an MIT-licensed Python scraper; while college sports are not included in the ready-made CSVs, the codebase demonstrates a working pipeline for multi-book odds from SBR.[^1]

**Relevance**: Indicates that SBR’s odds pages can be scraped for book-level lines; extending this approach to NCAAB is feasible but requires custom work and may face modern anti-bot measures.

### 4.3 Other odds screens used in practice

Modelers sometimes scrape or at least snapshot other odds-comparison sites:

- **EV Analytics NCAAB ATS pages** – Provide historical ATS results “for the consensus odd and closing line” on NCAAB, implying embedded odds history that can be reverse engineered.[^28]
- **Covers and SportsOddsHistory** – Covers NCAAB section and SportsOddsHistory pages offer line history content and ATS records, historically scraped by some practitioners for both pro and college sports.[^29][^1]
- **OddsShark interactive database** – Claimed to host multi-decade odds histories for some sports, though bulk NCAAB extraction requires HTML scraping and is more commonly used for NCAAF.[^1]

In all these cases, no public API exists; usage consists of HTML table scraping via `pandas.read_html`, BeautifulSoup, or browser automation.

***

## 5. College-basketball-specific scrapers and tooling

### 5.1 Play-by-play and stats scrapers (to be paired with odds)

Several open-source projects focus on NCAA basketball play-by-play and stats rather than odds but are commonly combined with odds datasets:

- **SportsDataverse ecosystem** – `hoopR` (NBA/ESPN), `gamezoneR` (NCAA men’s basketball based on STATSGAMEZONE), and related R packages provide clean CBB play-by-play and box-score data from ESPN and stats vendors.[^10]
- **CBBpy** – A Python package to scrape NCAA D1 men’s and women’s basketball data (game metadata, box scores, play-by-play) from ESPN, accessible via functions like `get_game_pbp` and `get_game_boxscore`.[^30]
- **MichaelE919/ncaa-stats-webscraper** – Early Python script to pull NCAA stats (team-level metrics) from TeamRankings and KenPom into Excel via BeautifulSoup and Pandas.[^31]

**Relevance**: These tools do not provide odds, but they are the standard way to obtain high-resolution performance data and are frequently merged with SBRO, API, or scraped odds to build inputs for predictive models.

### 5.2 One-off odds scrapers and experiments

GitHub contains several smaller projects that scrape basketball odds and results from various sites:

- **LauLeysen/Sports-result-Scraper-with-odds** – Scrapes basketball match odds (mostly Bet365 pre-match odds) and results from a sports data website to analyze strategies like “always bet home/away.”[^32]
- **DavideGiardini/OddsPortal-WebScraper** – Scrapes NBA Asian handicap and totals markets from OddsPortal to assess market accuracy.[^23][^33]

While not NCAAB-specific, these repos are frequently forked or adapted by community members to target NCAA leagues once the underlying URL scheme is understood.

***

## 6. Reddit, Kaggle, and community practices

### 6.1 Reddit r/algobetting and r/datasets threads

Reddit’s r/algobetting and r/datasets subreddits are the central places where quants compare historical odds sources:

- Threads on “Is there an API that can let you find historical odds for a game?” and “Historical Sports Bet Odds past 2020?” consistently point to The Odds API as the go-to API for historical match odds and highlight limitations (e.g., lack of scores in some endpoints).[^14][^11]
- Commenters mention alternative APIs like Sports Game Odds and “Odds API” (distinct from The Odds API), as well as Oddspapi, for cheaper or more granular historical feeds, particularly mentioning Pinnacle and Bet365 coverage.[^11][^13]
- In dataset-request threads, users suggest BigDataBall and SportsbookReview/SBRO as primary historical sources for odds data, reinforcing their de facto status in the community.[^34]

These exchanges reflect actual usage patterns more accurately than marketing material and often reference specific price points and pitfalls.

### 6.2 Kaggle sports betting datasets

Beyond the basketball-odds-history dataset, Kaggle hosts:

- **Official NCAA basketball competition data** – NCAA’s own Kaggle dataset provides game, team, and player data back to 2009 but does not include sportsbook odds.[^35]
- **College Basketball Dataset (Andrew Sundberg)** – Aggregates D1 seasons from 2013 onward, focusing on stats and ratings rather than odds.[^36]

Some tournament-focused notebooks manually join these datasets with external odds (often from bookmaker CSV exports or scraped sources), but full odds tables are rarely published due to licensing.

***

## 7. Betting communities, Discords, and tooling ecosystems

### 7.1 Unabated community and tools

- **Platform**: Unabated is a subscription-based suite of tools (odds screens, alt-line calculators, Unabated Line) targeting serious sports bettors.[^37][^38]
- **Community**: Unabated runs a professional sports betting Discord, accessible via login from their dashboard, where line history, screen usage, and data integration are regular topics.[^39]
- **Data**: Public materials emphasize real-time line shopping and derived “vig-free” prices rather than raw historical odds exports; historical line histories may exist internally but are not generally exposed as downloadable datasets.[^40][^37]

### 7.2 Rithmm, Outlier, and AI-driven Discord bots

- **Rithmm**: An AI sports betting app with its own Discord community, focusing on custom models and real-time data. Discussions often revolve around model-building but not specifically on exporting historical odds.[^41]
- **Outlier Insights bot and others**: Discord bots highlighted in 2026 overviews provide real-time odds screens, price discrepancy alerts, and simple analytics within Discord servers, but their backends usually depend on commercial APIs and do not expose raw historical data dumps.[^42]

### 7.3 Generic sports betting Discord servers

Lists of “top sports betting Discord servers” show many pick-selling and community servers (e.g., ParlayScience) where data discussion is secondary to handicapping. For deep data engineering, r/algobetting and niche quants’ private Discords are more important than these retail-focused communities.[^43]

***

## 8. How practitioners actually assemble 2018–2025 NCAAB odds

Synthesis of open discussions, existing datasets, and tooling suggests a few standard build patterns:

1. **Free+paid hybrid for consensus odds**
   - 2018–2021: SBRO Excel files for consensus opening/closing lines.[^16][^1]
   - 2021–2025: BigDataBall and/or Scottfree Analytics for per-game closing odds, with stats already joined.[^8][^1]
   - Advantage: Low cost, simple ETL; Disadvantage: lack of per-book variance, limited insight into market microstructure.

2. **API-first multi-book pipeline (The Odds API + backfill)**
   - 2020–2025: Use The Odds API historical snapshots for NCAAB and WNCAAB (sport keys `basketball_ncaab` and `basketball_wncaab`) to reconstruct opening and closing odds for 40+ bookmakers.[^6][^2]
   - 2018–2020: Backfill using SBRO or, for multi-book detail, an OddsPortal scrape focused on major books during those seasons.[^3][^22][^1]
   - Implementation: Schedule historical pulls in batches, store raw snapshots, then compute for each event and book: first-quote, pre-tipoff quote, and closing quote; integrate with CBB play-by-play (via CBBpy or SportsDataverse) for model features.[^30][^10]

3. **Scraper-maximal OddsPortal-centric build**
   - 2008–2025: Design a robust OddsPortal scraper using OddsHarvester, `odds-portal-scraper`, or custom Selenium scripts, targeting NCAAB competitions; store all bookmaker quotes from opening to closing.[^3][^4][^9]
   - Pros: Deepest book-level breadth; includes obscure books and alt markets;
   - Cons: High engineering cost, CAPTCHAs, rate limits, fragile selectors, and legal/ethical considerations around scraping.

4. **Enterprise vendor strategy (SportsDataIO, Sportradar)**
   - 2019–2025: License historical odds from SportsDataIO or similar; pull S3 bulk archives for backfill and use API for ongoing capture.[^7]
   - 2018–2019 and earlier: Supplement with SBRO or vendor-specific archives (Action Network/Bet Labs, KillerSports) if available.[^1]
   - This is common for commercial operators and advanced quants with sufficient budget who require compliance-grade data.

Across these patterns, the consensus in r/algobetting and related circles is that The Odds API plus SBRO/BigDataBall (or Scottfree) hits the best ROI frontier for solo or small-team projects, with OddsPortal scraping reserved for those willing to invest heavily in data engineering.[^14][^11][^1]

***

## 9. Practical implications for model-building

For a forecasting model targeting 2018–2025 NCAAB with opening and closing prices across multiple books, the ecosystem implies:

- **No single perfect source** – trade-offs between cost, engineering effort, and multi-book detail are unavoidable.[^6][^1]
- **APIs are best for recent seasons** – especially from 2020 onward, where snapshot-based odds APIs are mature and come with clean, documented interfaces.[^2][^6]
- **Scraping remains necessary for pre-2020 and fringe markets** – the combination of OddsPortal and legacy odds screens (SBR, EV Analytics, TeamRankings BetIQ) is still the only way to reconstruct some historical line movements and book-specific spreads.[^9][^22][^5]

In practice, serious practitioners architect modular ETL pipelines where each data domain (odds, stats, IDs) can be swapped as better sources are found, and they invest early in canonical game identifiers (e.g., ESPN game IDs via CBBpy or SportsDataverse) to avoid rework when changing odds providers.[^10][^30]

***

## 10. Summary of key sources and access methods

The table below recaps the most relevant sources for 2018–2025 NCAAB odds, focusing on how they are accessed and whether proven scrapers/tools exist.

| Source / tool | Type | NCAAB coverage (approx.) | Multi-book? | Access method | Known scrapers / tooling |
|---------------|------|--------------------------|-------------|--------------|---------------------------|
| The Odds API | Commercial API | From 2020-11-16, 5–10 min snapshots | Yes (40+ books) | REST JSON API, historical snapshots | Official samples; `oddsapiR` R client; custom Python/R scripts[^2][^6][^10] |
| SportsDataIO historical odds | Commercial API + bulk | 2019 onward | Yes (9+ US books) | Enterprise API + S3 Vault bulk exports | Vendor SDKs and client code; internal ETL[^7][^1] |
| Sports Game Odds | Commercial API | NCAAB supported (depth varies) | Yes (80+ books) | REST JSON API | GitHub `BracketBrain` shows CSV export pattern[^12][^11] |
| Oddspapi / other historical APIs | Commercial APIs | Sport/book coverage varies; Pinnacle, Bet365 noted | Yes | REST APIs | Community scripts; vendor docs (not open)[^13] |
| SBRO Excel archive | Free static files | 2007–08 to 2021–22 D1 games | Consensus only | Excel downloads | Manual ETL, Pandas import, Kaggle NBA derivations[^1][^16] |
| BigDataBall NCAAB | Paid per-season spreadsheets | Multiple seasons incl. recent | Consensus odds | Excel downloads | Manual ETL; used by bettors and researchers[^8][^1] |
| Scottfree Analytics NCAAB | Paid CSV | 10+ seasons ML-ready | Consensus-like closing | CSV downloads | Direct CSV ingestion; ML workflows[^1] |
| TeamRankings BetIQ | Web tool | 2003–04 onward (closing lines only) | Consensus | Web tables | `pandas.read_html`, legacy TeamRankings scraper[^5][^17] |
| Kaggle basketball-odds-history | Public dataset | Multiple seasons, incl. college | Unclear | Kaggle CSV | Direct download from Kaggle[^18] |
| OddsPortal | Odds-comparison site | NCAAB from ~2008–09 | Yes (80+ books) | Web UI only | OddsHarvester, `odds-portal-scraper`, Apify actor, WebHarvy, Selenium scripts[^3][^4][^21][^9][^22] |
| Sportsbook Review odds | Odds-comparison site | Historically covered NCAAB | Yes | Web UI only | FinnedAI SBR scraper (NFL/NBA/MLB/NHL), extensible to NCAAB[^1] |
| EV Analytics NCAAB ATS | Stats/odds site | Historical ATS, consensus closing | Consensus | Web tables | HTML scraping with Pandas/BS4[^28] |
| Covers + SportsOddsHistory | Editorial + stats | Multi-decade, NCAAB lines / ATS | Consensus | Web pages | Custom scrapers; widely referenced in community[^1][^29] |
| CBBpy / SportsDataverse | Stats / PBP scrapers | 2009+ play-by-play and box scores | N/A (no odds) | Python/R packages | Used for merging stats with external odds[^30][^10] |
| OddsHarvester | Scraper | Whatever OddsPortal supports | Yes (book-level) | CLI Python app | Docker images; S3 export; used in Reddit threads[^3][^24][^25] |

This ecosystem is dynamic—APIs appear, rebrand, or deprecate; odds sites change layouts and anti-bot defenses. As a result, the most robust forecast-model pipeline is one that accepts this volatility and treats data acquisition as an ongoing engineering problem rather than a one-time purchase.

---

## References

1. [Historical-Odds-Data-Resources-Report.md](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/56669934/6ca4c20f-c2c0-4587-95b2-6145f27e264c/Historical-Odds-Data-Resources-Report.md?AWSAccessKeyId=ASIA2F3EMEYEQDVZIXHP&Signature=evMy%2FDRY4m9TBPqTuy9kCCMDYds%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEFgaCXVzLWVhc3QtMSJHMEUCIDk%2BZPDynmuhq3X6DCsNinN%2B9fYnqB0p%2FKCbPqrvEFvcAiEA7oQvrkZLN4fPgFwXGYakhup091TIkmE8j4tr43XOdMAq8wQIIRABGgw2OTk3NTMzMDk3MDUiDG0%2F3YRNu4S%2BFFxSbirQBPH28cKVjFEwPETi%2BqZG6Xiuf3li0C5goC1FcdzPZ1lIBxR662Ozci5BPTaXzWplPEo%2F59k8bCwLL9E9ZLQVJWMZe0T4h5QxRLTt5vNz4y44z1f23yZHHJ86ilMuSCBSxDnmZhfLOavw5Sv727p0xRZI3IDUN1Tk8AO%2FMDpXuOb26TCBYXj0Niw7tjpjNEkmtbtitrwXwKHOZNXWBodWx%2Belq9mtmc5MJVPdWuaMN8LGUZGMlhFgvBs5JMjDpm3cSlRZHchYpgoXCw25nAte1yW633eDP6WzSwSGAe11avcLO00yd9IMoVRMQ5M%2FbJ5J16tyfXrvPWVX4hq4sqfTsGxiZRO8vW13HnTbH0HCMBTzRkqitbo6xVuOhz19PgSR4rwxfbQ3lVM1p%2FOYmcgkrG1ZYsIPVg5bKRt6NcKqBtyrzlLE4Ia%2B4pcxufE%2FFRhqxQhttDRvX3N099IarUmTvdE755lvcEzhkq5%2F9lL%2BWFftlVjxIvQOaJ6tkKN%2B2hO9bBECPXT0ivGwFm%2BnY5C0Gz7V9MDq7mg2p2jRy5fhl5APvrOxsnf6tKoFrSEPV3%2BPZpY9EeQvmzCAHhVjCKRchCnXUgqjNKECmzowzaM62kgds9e0SnZ3jbHM43fWyP8o3SRL8j4YLbMCTooEjkva0k%2B9f20nDH6H0X%2FVB8OgxtkzsbZtywBrKrYzXanFP3Q0l6wnOexa8x19We0Ermo%2BN7XvlfopC40ZB0qlqolYyBgFKktINK1Ypho%2Fou1zTfgU3CHvvkomppwCercL%2BwkotBEw2JW4zQY6mAHzcPKOtcahpfm2OzwwOJM9yDRJ1ffur%2F4N2kPA53GIbB%2F5z8o2o5EpnCYqLuqDb5idTVe2BTRf5%2Fds2fsZUKxpqO9%2Fqgx%2BGbprYPgXmdyB%2BnriU3VCKMbIGt%2FaBe5J8Kij4taXyn6X%2B7FfchQRwYzHdpf0BE7LXSIEbj5ryYtF9Dz256TbtAdvaYkxzwFgAk2QBsLoGoqK%2Bg%3D%3D&Expires=1773018276) - # Historical sports betting odds data: a complete source guide

**The most cost-effective path to ...

2. [NCAA Basketball Odds API](https://the-odds-api.com/sports/ncaab-odds.html) - Historical NCAAB odds data is available on paid usage plans. Historical odds for featured markets (m...

3. [jordantete/OddsHarvester: A python app designed to scrape and ...](https://github.com/jordantete/OddsHarvester) - OddsHarvester provides a Command-Line Interface (CLI) to scrape sports betting data from oddsportal....

4. [GitHub - gingeleski/odds-portal-scraper](https://github.com/gingeleski/odds-portal-scraper) - This repository contains multiple scraping projects for Odds Portal. Each one has its own README.md ...

5. [NCAA Basketball Odds & Line History - Win-Loss + Spread Records ...](https://betiq.teamrankings.com/college-basketball/betting-trends/by-closing-line/win-loss-and-spread-records/) - College Basketball odds and basketball betting line history results. Includes both win-loss records ...

6. [Historical Sports Odds Data API](https://the-odds-api.com/historical-odds-data/) - Historical odds data is available for all sports and bookmakers covered by The Odds API. Historical ...

7. [Historical Odds - SportsDataIO](https://sportsdata.io/historical-odds) - SportsDataIO's historical odds database provides the most robust and complete set of pre-game, in-pl...

8. [NCAA College Basketball Data: Game Log Spreadsheets with Stats ...](https://www.bigdataball.com/datasets/ncaa/cbb-data/) - NCAA college basketball data -historical and inseason- in Excel spreadsheets available for game-by-g...

9. [Scrape Betting Odds from Oddsportal website - WebHarvy](https://www.webharvy.com/articles/scraping-oddsportal.html) - Learn how to scrape betting odds data from Oddsportal using WebHarvy. Step-by-step guide to extract ...

10. [SportsDataverse - GitHub](https://github.com/sportsdataverse) - Retrieves sports data from a popular sports website as well as from the NCAA website, with support f...

11. [Is there an API that can let you find historical odds for a game, and ...](https://www.reddit.com/r/algobetting/comments/1n7o2gb/is_there_an_api_that_can_let_you_find_historical/) - I recently found the-odds-api https://the-odds-api.com and it seems great for making API calls to ge...

12. [ankitdevalla/BracketBrain - GitHub](https://github.com/ankitdevalla/March_Madness_Pred) - Fetches NCAA basketball betting odds from the sportsgameodds.com API and saves them to CSV files. Se...

13. [Historical corners odds/prices (Pinnacle / Bet365) - Reddit](https://www.reddit.com/r/algobetting/comments/1q1uspu/historical_corners_oddsprices_pinnacle_bet365_any/) - Does anyone know a reliable API/historical dataset/website for corners odds/prices (as much coverage...

14. [Historical Sports Bet Odds past 2020? : r/datasets - Reddit](https://www.reddit.com/r/datasets/comments/1f49v8q/historical_sports_bet_odds_past_2020/) - NFL, NBA, MLB, NHL, NCAAB, and NCAAF Historical Odds Data in CSV format: ... [OddsHarvester] Open-so...

15. [Odds Screen Recommendations? : r/algobetting - Reddit](https://www.reddit.com/r/algobetting/comments/113kr7r/odds_screen_recommendations/) - Anyone have a good odds screen that is either free or reasonably priced? The more features the bette...

16. [NBA Betting Data | October 2007 to June 2025](https://www.kaggle.com/datasets/cviaxmiwnptr/nba-betting-data-october-2007-to-june-2024) - Scores, point spreads, totals, and other odds from all NBA games.

17. [Scraping data from TeamRankings.com - python - Stack Overflow](https://stackoverflow.com/questions/74997100/scraping-data-from-teamrankings-com) - I want to scrape some NBA data from TeamRankings.com for my program in python. Here is an example li...

18. [Basketball-odds-history - Kaggle](https://www.kaggle.com/datasets/zachht/wnba-odds-history) - About Dataset. Global, NBA, college, and WNBA basketball odds. Odds shown are euro-style. Scraping a...

19. [Evidence from the NCAA men׳s basketball betting market](https://www.sciencedirect.com/science/article/abs/pii/S1386418115000439) - In this paper, we test whether accuracy in the wagering markets for NCAA Division I men׳s basketball...

20. [Sports Data Sets - Sports and Society Initiative](https://sportsandsociety.osu.edu/sports-data-sets) - The data has been tracked since 1946. This data includes statistics, leaders, teams, and draft histo...

21. [Betting Odds Scraper - Lines & Spreads - Apify](https://apify.com/consummate_mandala/betting-odds-scraper) - Betting Odds Scraper scrapes sports betting odds from OddsPortal across multiple sports including NF...

22. [Web Scraping oddsportal.com - ScrapeHero](https://www.scrapehero.com/scraping-odds-portal/) - In this example of web scraping, you will be extracting NBA betting odds from oddsportal.com. You wi...

23. [GitHub - DavideGiardini/OddsPortal-WebScraper](https://github.com/DavideGiardini/OddsPortal-WebScraper) - WebScraping NBA's Asian Handicaps and Over/Unders from OddsPortal, to evaluate the accuracy of NBA o...

24. [[OddsHarvester] Open-source tool to collect historical & live sports ...](https://www.reddit.com/r/opensource/comments/1l9hyu8/oddsharvester_opensource_tool_to_collect/) - OddsHarvester, an open-source tool that scrapes and structures sports betting odds data from oddspor...

25. [Retrieve Historical and Upcoming Match Odds Data Easily - Reddit](https://www.reddit.com/r/algobetting/comments/1ibcwqn/oddsharvester_retrieve_historical_and_upcoming/) - Over the last few weeks, I've worked on OddsHarvester – an open-source app designed to scrape sports...

26. [gingeleski/oddsporter: Comprehensive scraping utility for ... - GitHub](https://github.com/gingeleski/oddsporter) - Comprehensive scraping utility for Odds Portal (oddsportal.com) results. Note this has now been rele...

27. [Extract Sports Betting Statistics Data From OddsPortal - Simplescraper](https://simplescraper.io/templates/extract-sports-betting-statistics-data-from-oddsportal) - This prebuilt scrape recipe extracts key data points such as Lost Bets, Predictions Made, Return on ...

28. [Against The Spread (ATS) - NCAAB Betting Stats - EV Analytics](https://evanalytics.com/ncaab/stats/spread) - Explore historical betting results to identify betting trends and profitability. Records are for the...

29. [March Madness Trends 2026 - NCAA Tournament Betting Trends](https://www.covers.com/ncaab/march-madness/trends) - March Madness betting trends are like breadcrumbs. Some lead you down the path of NCAA Tournament pr...

30. [CBBpy: A Python-based web scraper for NCAA basketball - GitHub](https://github.com/dcstats/CBBpy) - This package is designed to bridge the gap between data and analysis for NCAA D1 basketball. CBBpy c...

31. [Python webscraping module for NCAA Basketball Stats - GitHub](https://github.com/MichaelE919/ncaa-stats-webscraper) - Collects team stats for the top 68 NCAA basketball teams and writes them to a preformatted Excel spr...

32. [LauLeysen/Sports-result-Scraper-with-odds - GitHub](https://github.com/LauLeysen/Sports-result-Scraper-with-odds) - We scrape AI score and the pre match odds(mostly bet365) / results and calculate whatever we want to...

33. [OddsPortal-WebScraper/oddsportal_webscraper.py at main - GitHub](https://github.com/DavideGiardini/OddsPortal-WebScraper/blob/main/oddsportal_webscraper.py) - WebScraping NBA's Asian Handicaps and Over/Unders from OddsPortal, to evaluate the accuracy of NBA o...

34. [Historical Odds : r/algobetting - Reddit](https://www.reddit.com/r/algobetting/comments/1gv0fho/historical_odds/) - Historical odds for football matches can be found here https://www.football-data.co.uk/ for a number...

35. [NCAA Basketball](https://www.kaggle.com/datasets/ncaa/ncaa-basketball) - This dataset contains data about NCAA Basketball games, teams, and players. Game data covers play-by...

36. [College Basketball Dataset - Kaggle](https://www.kaggle.com/datasets/andrewsundberg/college-basketball-dataset) - Data from the 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024 Division I coll...

37. [Unabated Sports Review 2026 – Worth It? - SportBot AI](https://www.sportbotai.com/blog/tools/unabated-sports-review) - Complete Unabated Sports review with features, pricing, pros & cons. See if it's worth it for your b...

38. [How to Get the Most out of Unabated NBA](https://unabated.com/articles/how-to-get-the-most-out-of-unabated-nba) - Unabated is an authentic trusted source for tools and resources all designed to assist you in becomi...

39. [Professional Sports Betting Community Discord - Unabated](https://unabated.com/sports-betting-community) - Unabated's community via Discord provides a safe space to learn more about sports betting and networ...

40. [The Unabated Podcast - Spotify for Creators](https://creators.spotify.com/pod/profile/unabated-sports/episodes/Could-Pro-Sports-Bettors-Go-Extinct--And-Other-Burning-Questions-e30q6rm) - The best minds in sports gambling are here to help you become a better bettor. Thomas Viola hosts as...

41. [Sports Betting Discord: Best Online Community with Rithmm](https://www.rithmm.com/post/best-sports-betting-discord-community) - Rithmm is a powerful AI sports betting app built to give bettors an edge through predictive analytic...

42. [Top Sports Betting Discord Bots in 2026 - BettorEdge](https://www.bettoredge.com/post/sports-betting-discord-bots) - Explore the top sports betting Discord bots of 2026 that enhance community engagement and provide re...

43. [Top 44 best sports betting Discord servers [February 2026] - Whop](https://whop.com/blog/sports-betting-discord-servers/) - Sports betting Discord servers connect bettors with professional handicappers who use data-driven an...
