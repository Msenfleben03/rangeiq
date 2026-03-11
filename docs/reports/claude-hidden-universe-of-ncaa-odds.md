# The hidden universe of NCAAB historical odds data

**The most valuable NCAAB historical odds data lives not in the well-known APIs, but in a fragmented ecosystem of legacy Las Vegas data vendors, obscure European aggregators, reverse-engineered JavaScript endpoints, and community-built scrapers.** This landscape analysis uncovers dozens of sources, tools, and techniques beyond the 18+ providers and GitHub tools you already know — revealing that complete 2018–2025 coverage requires stitching together at least 3–4 sources across different eras. The critical gap sits between SBRO's cutoff (2021-22) and The Odds API's historical start (late 2020), while the pre-2020 period remains best served by a $35/season Las Vegas data vendor most researchers have never heard of.

---

## The Stardust line lives on: legacy and obscure data vendors

The single most valuable discovery for pre-2020 NCAAB odds is **The Logical Approach**, a one-person Las Vegas operation selling Excel-compatible data files with **opening and closing lines from the Stardust Sports Book (pre-2006) and Westgate/LVH Sportsbook (2006 onward)**. Coverage spans 1990-91 through approximately 2019-20 at **$35 per season**, with every Division I game (4,500–6,000+ games/season) included. A special NCAA Tournament compilation covering all **2,451 tournament games since 1985** costs $150. This is one of the only sources anywhere providing Stardust opening lines — a historically significant Vegas book whose data is otherwise lost to time. Volume discounts drop prices 20–40% on larger orders. Contact: logical7@cox.net, P.O. Box 20405, Las Vegas, NV 89112.

**Killer Sports** offers a radically different approach through its proprietary **Sports Data Query Language (SDQL)**, a SQL-like interface enabling conditional trend queries against a multi-decade NCAAB database. Queries like "team as home underdog after a road loss on a back-to-back" are possible and unique to this platform. Recently moved to a freemium model (late 2024). VSiN partners with Killer Sports for contests, and sharp bettors consider it one of the most comprehensive public databases available, though data accuracy is acknowledged as imperfect.

**BetExplorer** (betexplorer.com/basketball/usa/ncaa/) is frequently overlooked by US researchers. This European platform archives NCAAB closing odds from multiple international bookmakers — including **Pinnacle, bet365, Unibet, and others** — going back to the 2008-09 season. Its clean interface makes manual research easy, and it covers European and Asian bookmakers absent from US-focused aggregators. No API exists, but standard scraping tools work.

**SportsOddsHistory.com** (now operated by Covers.com) fills a different niche: it archives **preseason championship futures odds** and Final Four game spreads going back decades. This is one of the only places to find how futures markets historically priced NCAAB championship contenders. Cited by ESPN, FiveThirtyEight, and Sports Illustrated. Free to access, though it covers only futures and major tournament game spreads — not regular-season lines.

**NowGoal** (nowgoal3.com) surfaces in SBR forum recommendations as a source for Asian-market odds including Pinnacle lines, though NCAAB depth is unverified. **Flashscore** and **Sofascore** similarly provide NCAAB odds from European/Asian bookmakers not found on US sites, with multiple seasons of historical results available for free.

---

## 50+ GitHub repositories you probably haven't found

The open-source ecosystem for NCAAB odds scraping is far richer than the four known repos. Here are the most significant discoveries organized by target site.

**OddsPortal scrapers** represent the largest category, with at least seven distinct repositories. **gingeleski/odds-portal-scraper** is the most comprehensive, supporting multiple sports with JSON output via Selenium. **scooby75/webscraping-oddsportal** (based on DMPierre's work) explicitly handles basketball's 12-outcome format and outputs CSV with opening or closing odds. **karolmico/OddsPortalScrape** collects from 12 major bookmakers including Pinnacle, bet365, and bwin, using login-based scraping to reduce blocking. Additional variants include **tvl/scrapy-oddsportal** (Scrapy framework), **frobi/oddsportal** (SQLite storage), **carlaiau/oddsportal-h2h-scraper**, and **derrykid/oddsportal-scrape** (confirmed working April 2023).

The most technically interesting OddsPortal approach comes from **jckkrr/Unlayering_Oddsportal**, which reverse-engineered OddsPortal's data architecture. Odds data loads via hidden `.dat` files from `fb.oddsportal.com` following the URL pattern `https://fb.oddsportal.com/feed/match/1-1-{match_id}-1-2-{secondary_id}.dat`. The workflow involves extracting `xeid` match codes from season pages, decoding URL-encoded secondary IDs from page HTML using `urllib.parse.unquote()`, then requesting the `.dat` files to access raw JSON with all bookmaker odds. This technique powered the BuzzFeed/BBC tennis match-fixing investigation.

**SportsBookReview scrapers** include **nkgilley/sbrscrape** — a Python library (`from sbrscrape import Scoreboard`) returning structured data from 7 sportsbooks (FanDuel, DraftKings, BetMGM, PointsBet, Caesars, Wynn, BetRivers) that explicitly supports NCAAB. **FinnedAI/sportsbookreview-scraper** (44 stars) includes **pre-scraped datasets for 2011-2021** for NFL/NBA/MLB/NHL and is extendable to NCAAB. **SharpChiCity/SBRscraper** uses SBR's internal GraphQL-like API (`/ms-odds-v2/odds-v2-service`) with Tor integration for IP anonymity.

**Action Network scrapers** are led by **timsonater/action-network-scraper**, which has dedicated NCAAB sync logic (`sql_odds_sync.ncaab_sync()`), MySQL storage, `smart_sleep()` anti-detection, and automatic driver restart on session failure. **nkasmanoff/scrape_action** provides a simpler alternative for opening and current lines.

For NCAAB-specific tools: **cresswellkg/Sports_Utilities** contains `dailyOddsNCAA.py` pulling NCAA basketball odds daily from SBR into CSV. **fattmarley/cbbscraper** combines KenPom/HaslaMetrics/BartTorvik predictions with FanDuel betting lines via Selenium. **aself101/cbb-api** wraps the College Basketball Data API with dedicated `--lines` CLI endpoints, storing organized JSON datasets. **pmelgren/NCAAodds** is purpose-built to scrape and store historical NCAAB odds.

**Pinnacle API tools** include the official **pinnacleapi/pinnacleapi-documentation** (Basketball = sportId 4), **rozzac90/pinnacle** (`pip install pinnacle`), **marcoblume/pinnacle.API** (R/CRAN package), and **aigeon-ai/pinnacle-odds** (MCP Server for AI integration). **Critical update: Pinnacle closed API access to the general public on July 23, 2025**, now requiring application to api@pinnacle.com — but they explicitly support "academics and pregame handicapping projects."

Additional notable repos include **mc-buckets/donbest.py** (`pip install donbest`) for DonBest API access, **agad495/DKscraPy** and **BowTiedBettor/DraftKings** for DraftKings scraping, **pseudo-r/Public-ESPN-API** documenting 17 sports' worth of undocumented ESPN endpoints including betting and odds, and **deephaven-examples/sports-betting-data** explicitly supporting NCAAB via scoresandodds.com.

**PyPI packages** worth noting: `sbrscrape`, `pinnacle`, `donbest`, `draft_kings`, `sportsipy`, `oddsapi-ev` (EV calculator using Pinnacle as sharp benchmark), and the SportsDataverse family (`hoopR`, `oddsapiR`).

---

## Commercial sources: pricing the sharp line

The commercial landscape stratifies into four tiers by price and accessibility.

**Budget tier ($0–$50/month):** **API-Sports/API-Basketball** offers NCAAB odds data starting at $10/month (100 free requests/day), claiming 15+ years of historical data across 2,000+ competitions. Quality and depth for NCAAB specifically needs verification. **TheRundown** provides historical line movement since 2020 across **15+ sportsbooks** (including Pinnacle, Matchbook, Betcris, Bovada) with a free tier offering 20,000 data points/day from 3 sportsbooks. Paid plans run $49 (all books, live data), $149 (near real-time), or $399/month (high-volume). This is the most accessible paid source for post-2020 historical data.

**Mid tier ($100–$500/month):** **SportsGameOdds** covers NCAAB across **80+ bookmakers** with historical data on paid plans ($99–$249/month, 7-day free trial). Unlike competitors charging per market + bookmaker, SGO charges per game returned and includes Pinnacle data. **OddsJam API** starts around $500–$1,000/month (enterprise contact required) but processes over 1 million odds per second and provides complete historical feeds including opening, closing, and all line changes across 100+ sportsbooks. **Betstamp Pro** covers **150+ odds sets** — more offshore and sharp book coverage than any competitor — with 5+ years of history and a market-maker-weighted "true line." Currently running a 70% off promotion.

**Premium tier ($1,000–$5,000/month):** **Unabated API** starts at $3,000/month for personal use with no call limits or throttling. It provides the proprietary "Unabated Line" — a vig-free consensus from market-making sportsbooks (Pinnacle, Circa, Bookmaker) that sharp bettors consider a gold-standard reference. NCAAB is a core market. Their consumer subscription is far cheaper and includes line history browsing. **DonBest** (Scientific Games) ranges $100–$10,000/month depending on needs, offering the industry-standard reference data that most US sportsbooks use for line benchmarking. Their XML/RESTful feeds cover all NCAAB games in the DonBest rotation. Individual desktop access is possible; bulk feeds are primarily B2B.

**Enterprise tier (custom pricing):** **TxODDS Tx LAB** is arguably the deepest historical archive in the industry — **5 million+ fixtures across decades, 250+ bookmakers, 100+ betting markets** — but targets sportsbooks and trading teams exclusively. They recently partnered with gameplAI specifically for AI-powered NCAAB pricing. **Sportradar** (official NCAA data partner) offers free marketplace trials with the same data at lower rate limits, but production access requires enterprise contracts. **Genius Sports** is the NCAA's official data partner covering 70,000+ championship games but focuses on powering sportsbooks rather than selling historical odds comparison data. Neither publishes pricing.

**Special access routes:** Pinnacle now explicitly supports academic access — email api@pinnacle.com with your research use case. **Sports Insights/Bet Labs** offers NCAAB data back to **2003/2005** with unique features: book-specific steam move tracking (e.g., "5Dimes College Basketball steam move: 1,204-960 for +134.51 units since 2005"), public betting percentages, and reverse line movement indicators. This is a web-based system-building tool rather than raw data export, but the historical depth is unmatched.

---

## Community intelligence: what the forums actually say

The SBR forum thread "Is there an easy way to get Pinnacle closing odds data?" (October 2020, active through January 2024) contains a critical warning from user **KVB** (74,866 posts, Hall of Famer status): **SBR odds feeds sometimes stop updating hours before game time, so the "closing line" recorded may not be the actual closing line.** This data quality issue affects anyone using SBR-sourced closing lines for CLV analysis.

Reddit's **r/algobetting** community has converged on a rough consensus hierarchy: The Odds API for budget-friendly multi-book data, SportsGameOdds for developer-friendly access with Pinnacle, and Unabated for premium sharp-line analysis. The **r/sportsbook** community's Discord server remains the largest informal gathering for data discussion, though specific dataset sharing has moved to more private channels.

Several Discord communities have emerged specifically around data-driven betting: **Bandemic** (machine learning models, arbitrage alerts across 100+ sportsbooks), **Rithmm** (AI-powered picks with historical training data), and **Stellariea Sports** (ML tool development). These communities occasionally share data sources and scraping techniques but rarely distribute bulk datasets publicly.

On Quora, **The Logical Approach** is repeatedly recommended as the go-to source for historical college basketball point spreads — a notable signal given how obscure this vendor is in online discussions.

---

## Novel data recovery: mining the Internet Archive and reverse-engineering APIs

The **Internet Archive CDX API** enables systematic recovery of historical odds pages. The approach works: query `http://web.archive.org/cdx/search/cdx?url=vegasinsider.com/college-basketball/odds/las-vegas/&output=json&filter=statuscode:200` to enumerate all archived snapshots, then iterate through them scraping with `pd.read_html()`. Append `id_` to timestamps (e.g., `/web/2022id_/`) to retrieve raw HTML without the Archive.org navigation bar. **This technique works best for VegasInsider** (static HTML odds tables) but poorly for OddsPortal (JavaScript-rendered content shows blank tables in archives). Python tools `cdx_toolkit` and `wayback` (both pip-installable) provide clean interfaces to both Internet Archive and Common Crawl CDX indices.

**Apify's marketplace** contains three relevant pre-built scraping actors: the **Sportsbook Odds Scraper** ($25/month + usage) extracts from BetMGM, Caesars, DraftKings, FanDuel, and Bet365 with explicit College Basketball support; the **Betting Odds Scraper** (~$1.50 per 1,000 results) handles OddsPortal across all sports; and a dedicated **OddsPortal.com Scraper** supports any sport/league with multiple odds formats. These eliminate the need to maintain your own scraping infrastructure.

**Bright Data** offers an AI-powered OddsPortal scraper with **150M+ residential proxy IPs**, CAPTCHA solving, and auto-scaling, outputting to JSON, CSV, Parquet, or direct delivery to S3/BigQuery/Snowflake. **Octoparse** provides a point-and-click OddsPortal template requiring no coding.

For discovering undocumented APIs, the **API Reverse Engineer Chrome Extension** (github.com/ctala/api-reverse-engineer) captures all fetch/XHR requests on any page with one click, recording methods, headers, request/response bodies, and timing into deduplicated JSON. Run it while browsing OddsPortal to discover the `fb.oddsportal.com` `.dat` endpoints, or on DraftKings/FanDuel to map their internal APIs. The Apify "DraftKings API Actor" confirms that DraftKings has a direct API accessible without browser rendering.

A forward-collection strategy using **The Odds API's Google Sheets Apps Script integration** (github.com/the-odds-api/apps-script) with time-driven triggers creates an automated, code-free odds capture pipeline — effectively a no-code alternative to GitHub Actions for building your own historical dataset going forward.

---

## Data quality matrix: what actually has opening lines and Pinnacle closes

The question of which sources provide **opening lines** (not just closing) narrows the field significantly:

- **The Logical Approach**: Opening AND closing from Stardust/Westgate, 1990–2020
- **SBRO (SportsbookReviewsOnline)**: Opening AND closing spreads and totals, 2007–2022
- **BigDataBall**: Opening and closing odds, ~$25/season
- **OddsPortal**: Opening and closing from 80+ bookmakers (requires scraping), 2008+
- **The Odds API**: 5-minute snapshots from Sept 2022 (captures opening via early snapshots)
- **DonBest**: Real-time line movement including opening, enterprise pricing
- **Sports Insights/Bet Labs**: Opening and closing Pinnacle lines since 2005
- **TxODDS**: Full odds lifecycle from 250+ bookmakers, enterprise only

For **Pinnacle closing lines** specifically: Pinnacle's own API (apply to api@pinnacle.com for academic access), Sports Insights/Bet Labs (since 2005), OddsPortal (scrapable), BetExplorer (browsable), SportsGameOdds (API, aggregated), Betstamp Pro (150+ odds sets), OddsBase.net (free browsing), and the `marcoblume/pinnacle.data` R package (limited sports coverage).

**Pre-2020 coverage** is the hardest gap to fill. The Logical Approach, SBRO, OddsPortal, BetExplorer, and Sports Insights/Bet Labs are the only sources with substantial 2018-2020 NCAAB data. **Post-2022 coverage** (filling the SBRO gap) requires TheRundown, The Odds API, SportsGameOdds, BigDataBall, or scraping OddsPortal. **Multi-sportsbook coverage** is available from OddsPortal (80+), TxODDS (250+), Betstamp Pro (150+), OddsJam (100+), The Odds API (15+ US books), and TheRundown (15+).

For **regular season AND tournament coverage**: SBRO, The Logical Approach, BigDataBall, OddsPortal, and all API providers cover both. SportsOddsHistory covers only tournament and futures.

---

## Conclusion: a practical acquisition strategy

The optimal approach for building a complete 2018–2025 NCAAB historical odds dataset combines four sources. **The Logical Approach** ($35/season × 2 seasons = $70) fills 2018-2020 with Westgate opening and closing lines. **SBRO** (free Excel downloads) covers 2018-2022 with opening/closing spreads, moneylines, and totals from the DonBest rotation. **OddsPortal** (free, scraped via OddsHarvester or Apify at ~$1.50/1K results) provides 2018-present multi-bookmaker data including Pinnacle closes. **TheRundown** ($49-149/month) or **The Odds API** (paid historical tier) delivers structured, multi-sportsbook data from 2020 forward with proper timestamps.

The three highest-value discoveries for researchers are: the OddsPortal reverse-engineering technique (accessing raw JSON via `fb.oddsportal.com` `.dat` files), the Pinnacle academic access program (email api@pinnacle.com), and The Logical Approach's Stardust/Westgate archive — a dataset that preserves Las Vegas line-making history available nowhere else. For those willing to invest in commercial data, Betstamp Pro's 150+ odds sets with offshore book coverage and TxODDS's enterprise archive of 5 million fixtures represent the ceiling of what's possible.
