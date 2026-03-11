# Professional Odds Data Vendors

**SportsDataIO** – Offers historical odds data (via API/S3) for major sports (incl. NCAA basketball) from 2019–present【18†L118-L126】.  Covers many U.S. books (DraftKings, FanDuel, BetMGM, Caesars, BetRivers, etc.) for pregame and live lines, with both moneyline/spread/totals.  Provides “Vault – Historical Odds” archives (prop and futures from 2020 onward)【18†L118-L126】.  Pricing is tiered (data feeds or S3 subscription); API access available.

**Action Network (Sports Insights/Bet Labs)** – SportsInsights (now part of Action Network) provides a “Historical Betting Database” (BetLabs) covering the six major U.S. sports (NFL, NBA, MLB, NHL, College FB, College BB) back to 2003【16†L0-L6】.  Includes opening and closing lines for spreads, moneylines (for MLB/NHL), and totals【16†L0-L6】.  Data covers NCAA basketball (explicitly listed) and is accessible via their analytics platform (requires subscription).  Historically, users exported CSVs of lines and results, but API is not public.  (The site emphasizes data back to 2003, with opening/closing prices.)【16†L0-L6】

**TxODDS (Tx Lab)** – Offers the “Tx LAB” historical odds archive (decades of odds history) via API【13†L90-L96】.  Covers pro and college sports (including NCAA basketball) with final/closing lines.  Also provides real-time feeds (Tx FUSION, etc.).  Coverage years: likely many seasons (“decades” implied)【13†L90-L96】.  Data access is commercial (contact for licensing).

**OddsMatrix (EveryMatrix)** – EveryMatrix’s OddsMatrix platform provides a *Historical Odds* feed (API).  Claims “archive odds from 30+ bookmakers across 75+ sports over multiple years”【18†L118-L126】. Coverage is global (“78 sports”), with “comprehensive data from 2021 onwards”【18†L118-L126】.  Sportsbooks: leading international books (not individually listed).  Markets: as delivered in the feed (likely moneyline/spread/total).  Updated daily via API【18†L118-L126】.  Pricing: enterprise (SaaS feed).

**Unabated Odds API** – Unabated provides a JSON “Odds API” for real-time lines and props (NFL, NBA, CFB, CBB, etc.)【22†L0-L11】. Sportsbooks covered include Pinnacle, Circa, FanDuel, DraftKings, BetMGM, Bovada, etc.【22†L0-L11】.  Its focus is current odds; historical data availability is unclear.  Pricing is a flat rate (about $3k+/mo as of 2025)【22†L0-L11】.  It includes NCAA basketball markets (spread, ML, totals) as per supported sports.  Access is via JSON REST API.

**OddsJam API** – OddsJam offers a sports betting API with real-time and historical data.  Website boasts a “Full Historical Odds Database” including closing and opening lines and live movements across all markets (100+ sportsbooks)【24†L64-L72】.  Sports include major U.S. leagues and NCAA college sports.  Years: implies multi-season (likely covering 2018–2025).  Pricing: enterprise (contact for quote).  Access: REST API.

**The Odds API** – A public odds aggregator with historical snapshots (JSON API).  Covers NCAA basketball (since late 2020) and other pro sports【27†L117-L125】.  Includes spreads, moneylines, totals, and select props.  Sportsbooks: “several bookmakers” (not fully listed on site).  Historical data: “Odds history from late 2020”【27†L117-L125】.  Free tier available; paid plans for full access.  API returns snapshot prices (no time series, only one sample per request).

**SportsGameOdds (SGO)** – Free/Paid public odds API (sportsdata.io has a page for it).  Covers NCAA basketball (and all major sports)【30†L83-L90】.  Brags “odds from 80+ bookmakers” and “historic data available”【30†L83-L90】.  Years: unspecified; “historic” implies at least recent seasons.  Data types: moneyline, spread, totals, DFS, etc.  Has free tier (with rate limits) and paid plans.

**Other Vendors:** Additional data providers exist (often via API/license) but with less public info.  For example, **DonBest** provides live odds feeds (contact for archives), **BetLabs** (above), **Genius Sports/BetGenius** (official book data provider; offers trading feeds to partners), **BetRadar/Sportradar** (OmniOdds feed for in-play odds; enterprise only), **XLN (Kambi)**, **SBTech**, and **OpenBet** – these power major sportsbooks’ engines.  (They typically do not sell to end-users but can provide odds if contracted.)  **Betfair Exchange** (see Infrastructure) offers exchange data (timestamps and matched odds) via its Historical Data service (for subscribers).

# Betting Infrastructure Providers

These are companies whose technology **powers sportsbooks** (often the ultimate source of odds):

- **Kambi** – Provides the **Odds Feed+** (a B2B odds distribution platform) to many sportsbooks.  Covers 100+ sports (likely includes NCAA basketball) with real-time and pre-match odds【32†L130-L138】.  Acts as an official data source (API to licensees).  *Citation:* Kambi promotional site notes “access more than 1M pre-match and 450K live markets per year, spanning 100 sports”【32†L130-L138】.

- **SBTech (now Sportradar SBTech)** – Developed sportsbook platform/odds feed technology. Supports major sports including NCAA. (After acquisition by DK, still offered odds feed.)

- **OpenBet (IGT)** – Classic sportsbook platform. Provides pre-match and live odds for all sports. (Used by many operators like BetMGM.)

- **Genius Sports / BetGenius** – Official data/trading partner to many leagues. Offers odds aggregation and trading feeds to sportsbooks. (Exact details proprietary, but it’s a primary source for some book odds.)

- **Sportradar** – Offers the **Unified Odds Feed** (formerly OmniOdds). This is an enterprise feed of global bookmakers’ pre-game and live odds (including point-spreads, ML, totals) for all sports (NFL, NCAAF, NBA, CBB, etc.). Also provides Official statistics, play-by-play, etc. (Coverage: global, up-to-date; historical access via corporate contracts).

- **Betfair Exchange** – As a betting exchange, it provides historical matched odds (time-stamped) via its Betfair Historic Data service (sell data for all sports on its exchange)【39†L1-L4】.  (Not a bookmaker, but an alternative “market” with its own historical prices.)

- **Others**: Other platform providers (e.g. **SBTech (Sportradar)**, **NextGen Gaming**, etc.) indirectly provide data. Also, **Sportsbook back-office analytics** vendors (like Btrax, Qlik), but these repurpose the above feeds.

# Public Odds Data APIs

- **The Odds API** – (the-odds-api.com) Covers NCAA basketball. Free tier available; historical endpoint back to ~2020【27†L117-L125】. Supports spreads/ML/totals. Rate-limited REST API.

- **SportsGameOdds (SGO)** – (sportsgameodds.com) Free/Paid API for all major sports (incl. CBB)【30†L83-L90】. Provides current and historic lines (spread, ML, totals, DFS). Has “historic data” option and lists 80+ bookmakers.

- **RapidAPI** – Multiple providers via RapidAPI marketplace. E.g. Flashscore4 (scrapes Flashscore) – covers many leagues but is essentially an odds aggregator. (User on Reddit noted Flashscore API for global odds【72†L174-L184】.)

- **Pinnacle Sports API** – Pinnacle’s own XML API (free to affiliates) provides current and some historical MLB/NBA/NFL odds (esp. live odds). NCAA is limited (Pinnacle has few college markets). Not fully public.

- **Kambi API** – Some licensed partners can pull odds via Kambi’s feed (if you have partnership). Not open.

- **OddsJam, BetLab APIs** – Closed/proprietary.

- **Hidden/Sportsbook APIs** – Many sportsbook websites have unpublished JSON endpoints (accessed by web apps). E.g. DraftKings’ “sportsbook API” (used by Apify actors). These require scraping or paid access. (No easy open doc.)

# Open-Source Scraping Tools

Numerous GitHub projects scrape odds from websites:

- **OddsHarvester** (Jordan Tete’s OddsHarvester)【56†L320-L328】 – Python/Playwright scraper for OddsPortal. Supports NCAA (via “Basketball” category) and many markets (1X2, ML, Handicap, O/U)【56†L340-L348】. Last commit Jan 2026 (actively maintained). Can scrape upcoming and historical odds from OddsPortal. *Key:* covers global leagues and NCAA.

- **sportsbook-odds-scraper** (declanwalpole)【53†L213-L221】 – Python tool scraping live/pregame odds from major sportsbooks via their hidden APIs (DraftKings, BetMGM, Caesars, BetRivers, Superbook, Bovada, AUS books). Last commit Apr 2025【53†L213-L221】. Supports NFL, NBA, NHL, MLB, CFB, CBB, UFC, etc. Can continuously fetch odds to create time series. (Open-source on GitHub.)

- **BowTiedBettor/DraftKings Scraper** – Selenium scraper for DraftKings sportsbook (initially NHL odds)【47†L1-L10】. Last commit Feb 2023【48†L202-L210】. Modifiable for other sports (DK covers NBA, CFB, CBB, etc.). Pulls pregame lines via DK’s website (undocumented endpoint).

- **agad495/DKscraPy** – Another DraftKings scraper (BeautifulSoup). Covers specific markets (MLBs, Super Bowl, NFL spreads)【49†L236-L244】. Last commit Nov 2023【50†L213-L221】. Limited scope (not NCAA).

- **nkasmanoff/scrape_action** – Simple Python script to scrape lines from the Action Network public betting pages (e.g. NBA lines)【59†L236-L244】. Last updates ~2019. Can fetch current and opening lines by sport (swap the “nba” in URL).

- **OddsPortal H2H Scraper** (carlaiau) – Selenium script to scrape head-to-head results and odds from OddsPortal (supports multiple sports, but only head-to-head market)【60†L291-L300】. Last active 2019. Extracts final result and closing odds from OddsPortal league results pages.

- **Others**: Repositories exist for VegasInsider scrapers (StackOverflow references), Pinnacle (few examples), FanDuel, Bet365, etc. Eg. GitHub “sportsbet” scrapers and Apify actors (see “Scraping Tools” below). Many use Selenium/Puppeteer with rotating proxies.

# Odds Aggregator Websites

Public sites that *display* historical odds (often scraped by users):

- **OddsPortal.com** – A major global odds aggregator with archives of pre-match lines (all book’s best odds) for hundreds of leagues, including NCAA basketball. Widely scraped by researchers (via tools like OddsHarvester). Provides opening and closing lines for spreads/over-unders/etc across ~30-40 bookies. (No official API; has hidden XHR calls which scripts reverse-engineer.) Known for comprehensive historical archives.

- **VegasInsider.com** – Offers odds lines, especially for U.S. sports (including NCAA). Includes historical against-the-spread records and opening/closing lines. Data behind tables can be scraped (though some protection exists).

- **SportsbookReview (SBR)** – A betting news site that also archives lines (e.g. consensus spreads). Has a database of lines; used as reference. (No official API.)

- **Covers.com Sports Odds History** – Covers provides historical odds (including college) – e.g. spreads and totals by season. Not easily machine-readable, but accessible. (Their “Sports Odds History” section shows past odds and results, albeit not raw data.)

- **ActionNetwork.com** – Besides selling data, they have public odds pages (for NFL, CFB, NBA, CBB) showing current spreads/MLs with % public bets. These can be scraped (as scrape_action shows).

- **OddsShark, TeamRankings, etc.** – TeamRankings (through BetIQ) offers NCAA Basketball line history (spreads and team records) but mostly via web pages requiring login. OddsShark explains betting markets (not raw data). These are less used for scraping.

Many aggregators rely on hidden APIs (e.g. OddsPortal’s JSON endpoints). Scrapers often bypass robot checks via proxies or headless browsers. (On Reddit, practitioners note that scraping these sites is common practice for historical odds, despite block risks.)

# Academic / Public Datasets

No prominent *public academic dataset* of NCAA betting odds was found. Research papers rarely release full odds data due to licensing. Some Kaggle or academic listings exist for team stats, but not complete odds. For example, Ohio State’s “Sports & Society” list points to Kaggle NCAA basketball game data (teams, scores)【77†L282-L290】, but not lines.

One partial source: **Scottfree Analytics** provides free sample CSV of “Pro and College” historical odds【76†L176-L184】. (This includes some NCAA odds fields.) But full data is paid.

Else, academics often scrape or license via vendors. We did not find a known open repository of 2018–2025 NCAA odds (teams may share data only in supplements). Kaggle has some user-curated datasets (e.g. NCAA game outcomes), but not pre-game lines.

In short, no openly licensed NCAA odds dataset; most come from private scraping or vendor access.

# Community Knowledge (Forums/Reddit)

Practitioner forums (e.g. r/algobetting, r/sportsanalytics) confirm that **historical odds data is hard to find and often assembled piecemeal**.  For example, Reddit users recommend TheOddsAPI for historical lines (up to 5 years back)【70†L124-L131】 and discuss using Selenium/VPN to scrape sportsbooks【72†L172-L181】. A common theme is that there is no one free source – analysts rely on either scraping or expensive feeds.

Key mentions:

- **TheOddsAPI** – noted as a paid API with ~5-year historical archive【70†L124-L131】.
- **Apify/Zenscrape** – some mention using scraping-as-a-service (or proxy services) to avoid blocking when scraping sportsbooks【72†L174-L184】.
- Community posts also list “Sportsbooks and their odds providers” (a compilation) and share tools (like Apify actors).

While not citable academic sources, these discussions corroborate that most data comes from scraping or paying for feeds.

# Paid Datasets & Marketplaces

- **Scottfree Analytics (Robert Scott)** – Sells historical odds CSV by sport/market. (The “Free Sample” page【76†L176-L184】 shows they offer “complete season” datasets of pro and college lines. They highlight 132 columns and final odds within 1 hour of tip-off【76†L176-L184】.) Their shop lists separate products for NCAAB ML/OU/spread, etc. (So one can buy NCAA basketball odds for each season.)

- **Sports Data Companies** – Many (SportsDataIO, Sportradar, Genius, etc.) sell data via enterprise contracts. (Not direct “datasets” for purchase by individuals.)

- **Kaggle/Analytics Vendors** – Occasionally private contributors or companies release limited datasets. Example: Kaggle has user-uploaded “NCAA Basketball Dataset” with schedules and scores (not odds)【77†L282-L290】. Paid analytics firms (e.g. TeamRankings’ BetIQ) compile odds internally but do not sell raw data publicly.

- **Data Marketplaces** – No known NFT or marketplace specifically for betting lines. Some AI/ML data brokers may list sports data bundles (e.g. figshare or AWS Data Exchange occasionally list general sports stats, not odds).

# Scraping Tools & Automation

Beyond code projects above, there are platforms and agents for automated odds scraping:

- **Apify Actors** – Pre-built scrapers available in the Apify Store: e.g. “Odds API” actor (scrapes BetMGM/Caesars/DK/FD FanDuel/Bet365)【79†L444-L452】, “DraftKings Sportsbook Odds Scraper” (mherzog)【80†L129-L137】, “Sportsbook Odds Scraper” (harvest)【81†L182-L191】, and “OddsPortal.com Universal Odds Scraper”【82†L181-L190】. These are ready-to-run; some are free-tier or low-cost ($5–$25 per 1k results). They use headless browser/HTTP to gather odds and output JSON/CSV (formats indicated in their docs【81†L182-L191】【82†L181-L190】). The Apify Odds API actor explicitly lists NCAA basketball (“College-Basketball”) in its input parameters【79†L462-L470】.

- **Proxy & Cloud Services** – Tools like Apify include proxy rotation. Other solutions include ScraperAPI, Crawlera, or residential proxies to avoid bans when crawling sportsbook sites.  Tools like Selenium Grid or Playwright (used by OddsHarvester) allow automation of dynamic pages with proper delays/headers.

- **Rapid Scraping Platforms** – e.g. Scrapinghub’s (Zyte) platforms, or dedicated sports data scrapers (RapidAPI). Some sportsbook makers (e.g. Betfair) provide official feed APIs (but not for all odds).

- **Betting-Specific Scrapers** – There are commercial bots (e.g. BetCoinMachine arbitrage bot) and Python libraries (unofficial) to poll bookmaker APIs directly.

# Deprecated or Obscure Sources

Some older or hidden sources include:

- **Betfair Historical Data** (as above) – Once Betfair had a free exchange API, now superseded by the paid Historical Data service. It provides second-by-second exchange prices (not bookmaker lines)【39†L1-L4】.

- **OLD Odds APIs** – e.g. “Football-Data.org” was a soccer scores/odds site (shut down). “TheRundown API” (an early free odds API) is defunct.

- **Archived Bookmaker Feeds** – Some legacy books (e.g. William Hill’s now-closed U.S. API) no longer exist. Occasionally, old Kaggle datasets hint at defunct sources (e.g. “BenchOdds” from old competitions), but none specifically found.

- **Private Research Archives** – Some researchers have their own odds archives (not public). No public online dataset for NCAA lines pre-2018 was found other than scraping.

- **Odds Aggregation Sites (Hidden APIs)** – Sites like OddsPortal, ActionNetwork, VegasInsider sometimes use undocumented JSON calls. These are “hidden” APIs that skilled scrapers exploit (like Apify’s OddsPortal actor uses). These are not official sources, but are data sources if reverse-engineered.

In summary, the NCAA betting odds ecosystem includes a mix of **paid data feeds** (SportsDataIO, TxODDS, Scottfree, sportsbooks’ own partners), **public APIs** (OddsAPI, SGO), **websites to scrape** (OddsPortal, Covers, ActionNetwork), and **open-source tools** (OddsHarvester, sportsbook-odds-scraper, Apify actors) used by modelers. The most reliable way to build a 2018–2025 NCAA basketball odds dataset is likely a combination: license a feed (or purchase bulk CSVs from a vendor like SportsDataIO or Scottfree) for core coverage, and supplement/gap-fill by scraping archival sources (OddsPortal, VegasInsider) and using aggregator APIs (TheOddsAPI, SGO).

**Sources:** Vendor websites and documentation【18†L118-L126】【27†L117-L125】【22†L0-L11】, GitHub repos【56†L320-L328】【81†L182-L191】, and community posts【70†L124-L131】【72†L174-L184】, as cited above.
