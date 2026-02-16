# Historical sports betting odds data: a complete source guide

**The most cost-effective path to comprehensive historical odds data combines a free archive
(SportsbookReviewsOnline.com) covering all six target sports from 2007–2022 with a modest $99–200 investment in
specialized datasets for recent seasons and college-specific coverage.** No single source covers everything — the market
is fragmented between free archives that stopped updating, affordable one-time purchases with gaps in college sports,
and commercial APIs that only reach back to 2019–2020. For building projection models across NCAAB, NBA, NFL, MLB,
NCAAF, and futures markets, a layered strategy using 3–4 complementary sources delivers the best ROI. The critical
college sports gap can be filled, but it requires combining multiple sources since no single provider offers deep,
downloadable, multi-bookmaker college odds history at an affordable price.

---

## The free tier: surprisingly deep if you know where to look

**SportsbookReviewsOnline.com (SBRO)** stands as the single most valuable free resource for this use case. It provides
downloadable Excel files covering all six target sports — NFL, NBA, MLB, NHL, NCAAF, and NCAAB — with **opening and
closing spreads, moneylines, totals, and second-half lines** sourced from the DonBest rotation (a mix of offshore and
Nevada sportsbooks). NCAAB coverage includes all Division I games from 2007–08 through 2021–22 (**15 seasons**), while
NCAAF covers all FBS games over a similar timeframe with FCS games added from 2019. The archive is frozen and will not
receive new data, but it directly overlaps with the user's 2020–2025 NCAAB statistics window for at least two full
seasons. The limitation is that it provides consensus lines from a single aggregated source rather than individual
sportsbook prices.

The **FinnedAI SportsbookReview Scraper** on GitHub fills a different niche: pre-scraped CSV data from SBR covering NFL,
NBA, MLB, and NHL from **2011–2021 with 5–8 individual sportsbook lines** (including Pinnacle, 5Dimes, BookMaker) and
both opening and closing odds. This is the only free source offering multi-book historical data in a readily
downloadable format, though it lacks college sports coverage. The MIT-licensed Python scraper can potentially be
extended to additional sports.

**OddsPortal.com** offers the widest free multi-bookmaker comparison, tracking **80+ bookmakers** across all major
sports including NCAAB (from 2008–09) with odds movement from opening to closing for each book. The catch: data exists
only on dynamically rendered web pages requiring Selenium-based scraping. The open-source OddsHarvester CLI tool
(Python) can automate this, outputting JSON or CSV with bookmaker-level granularity, but building a complete historical
dataset demands significant engineering effort and patience with rate limiting.

**SportsOddsHistory.com** (now part of Covers.com) provides unmatched historical depth — NFL point spreads back to
**1952** using newspaper sources, plus archived championship futures odds (Super Bowl, World Series, NBA Finals)
spanning decades. For futures market backtesting, this is irreplaceable. However, it offers only web-based editorial
content with single consensus closing lines, requiring scraping for programmatic use.

Other free sources worth noting: **OddsShark** provides an interactive database claiming **30+ years of data** for NCAAF
(odds back to 1990) and covers all six target sports, but offers no bulk download capability. **Covers.com** team pages
have ATS/O-U records going back to the early 1990s for NBA and other sports, scrapeable team-by-team. **Kaggle** hosts
popular NFL datasets (Toby Crabtree's dataset: spreads from 1979, 27K+ downloads) and smaller NBA datasets, but NCAAB
and NCAAF coverage is essentially nonexistent on the platform.

| Source | Sports | Years back | Multi-book | Open+Close | Format | Props/Halves |
|--------|--------|-----------|------------|------------|--------|-------------|
| SBRO | All 6 | 2007–2022 | No | Yes | Excel | 2H lines only |
| SBR Scraper (GitHub) | NFL/NBA/MLB/NHL | 2011–2021 | Yes (5–8) | Yes | CSV | No |
| OddsPortal | All major | 10–20 yr | Yes (80+) | Yes | Scraping | Some basketball |
| SportsOddsHistory | All 6 + futures | NFL since 1952 | No | Closing only | Scraping | No |
| OddsShark | All 6 | 30+ yr | No | Varies | Web-only | No |
| Kaggle (NFL) | NFL | Since 1979 | No | Closing | CSV | No |

---

## Commercial APIs ranked by value for model builders

**The Odds API** delivers the strongest value proposition for programmatic historical odds access. At **$20–249/month**
depending on volume, it covers all six target sports (confirmed NCAAB and NCAAF coverage) with snapshots from **40+
bookmakers** (DraftKings, FanDuel, BetMGM, Caesars, Pinnacle, and more) captured every 5 minutes since September 2022
(every 10 minutes from June 2020). Featured markets (moneyline, spread, total) extend back to June 2020, while player
props, half lines, quarter lines, alternate lines, and team totals are available from May 2023. The REST API returns
JSON with excellent Swagger documentation, official Python samples, and Excel/Google Sheets add-ons. Historical endpoint
costs 10 credits per region per market per call. At the $99/month Superstar tier (4.5M credits), a user could
systematically download the entire 2020-present historical archive across all sports in a matter of days. **This is the
only affordable API confirmed to provide multi-bookmaker historical data for college sports.**

**SportsDataIO** (formerly MySportsFeeds, incorporating DonBest data) is the enterprise-grade option, covering all six
sports from **2019 onward** with every line movement timestamped across **9+ major US sportsbooks**. It tracks opening
lines through every price change to closing lines, plus props and futures from 2020. Data is accessible via REST API or
S3 bulk download through their "Vault" product. Pricing is enterprise-level — estimated at **$599+/month** — making it
prohibitive for individual model builders but ideal for funded operations. The documentation and data mapping (universal
game/team/player IDs) is industry-leading.

**Sports Game Odds** ($99+/month) tracks **80+ bookmakers** across 25+ sports with props, period odds, alternate lines,
and exchange odds. It represents a middle ground between The Odds API's affordability and SportsDataIO's depth, though
historical depth varies by league and exact college sports coverage needs verification.

**OpticOdds** serves the professional trading market with **200+ sportsbooks** and sub-second latency, trusted by
operators like BetMGM. It's built by ex-traders and quants, covering all markets including props and outrights with
historical data access, but at enterprise pricing (contact required). **Sportradar**, the world's largest sports data
provider at **$500–2,000+/month**, offers the broadest global coverage (80+ sports, 500+ leagues) with 100+ bookmakers,
but pricing makes it impractical for individual projects.

**Pinnacle** — long considered the gold standard for "sharp" closing lines — **shut down public API access in July
2025**. Historical Pinnacle data is now only available through third-party aggregators: The Odds API includes Pinnacle
as an EU bookmaker in its historical snapshots, and Oddsbase.net maintains a Pinnacle archive. **Betfair Exchange**
sells historical exchange data (back/lay prices with traded volumes) from April 2015 onward, but US sports have thin
exchange liquidity, making it unsuitable for NCAAB/NCAAF backtesting.

| Provider | Monthly cost | College sports | Historical from | Books tracked | Props/Halves |
|----------|-------------|---------------|----------------|---------------|-------------|
| The Odds API | $20–249 | ✅ Both | June 2020 | 40+ | ✅ (from 2023) |
| Sports Game Odds | $99+ | Likely | Varies | 80+ | ✅ |
| SportsDataIO | ~$599+ | ✅ Both | 2019 | 9+ US books | ✅ (from 2020) |
| OpticOdds | Enterprise | ✅ Both | Available | 200+ | ✅ |
| Sportradar | $500–2,000+ | ✅ Both | Undisclosed | 100+ | ✅ |
| OddsJam | ~$500+ | Likely | Undisclosed | 100+ | ✅ |

---

## Specialized databases and one-time purchase options

Three specialized sources stand out for their unique offerings. **Action Network / Bet Labs** (formerly Sports Insights)
maintains the deepest continuously available historical odds database in the industry: **data going back to 2003**
across all six target sports, including NCAAB and NCAAF. The dataset includes opening/closing lines, proprietary betting
percentages (ticket and money splits), and 45+ queryable filters through the Bet Labs tool. At approximately
**$50/month**, this represents 22+ years of data with unique sharp money indicators. The critical limitation: **no API
or bulk data export** — data is accessible only through their web-based tools, making programmatic integration
impossible without scraping.

**KillerSports.com** offers another deep historical database (**15+ years** across all major US sports including
college) queryable through their proprietary SDQL (Sports Database Query Language) or an AI-powered natural language
search tool. It provides consensus closing lines for spreads, moneylines, and totals. The query-based interface is
powerful for trend analysis but does not support bulk CSV downloads, requiring subscription access (pricing not publicly
listed).

For **one-time bulk purchases**, three options target different needs:

- **Odds Warehouse** ($79 for 10+ years of data, on sale from $199) delivers clean CSV files for MLB (2009–2023), NBA
  (2006–2023), NFL (2009–2023), and NHL (2008–2023) with opening and closing consensus lines. Princeton University
  Library purchased this dataset for their research repository. **Critical gap: no college sports coverage.**

- **Scottfree Analytics** ($99 per sport, one-time) provides CSV files with **132 columns** specifically designed for
  machine learning, including ML target variables and closing odds captured within one hour of game time. Both NCAAB and
  NCAAF are available. This is the most ML-ready dataset identified.

- **BigDataBall** (~$15–30 per season with bulk discounts up to 15%) uniquely combines game box scores, player
  statistics, DFS salary data, AND betting odds (opening/closing spreads, moneylines, totals) in single Excel files for
  NCAAB, NCAAF, and all pro sports. Buying 11+ seasons triggers 15% off, plus a 20% member discount on historical data.
  Trusted by league offices and academic researchers, it's the only source where stats and odds come pre-merged with
  universal IDs.

---

## Solving the college sports data gap

College odds data is demonstrably harder to source than professional sports data. The research confirms this gap across
the market. Here is the practical hierarchy for NCAAB and NCAAF specifically:

**For the user's immediate need** (matching 2020–2025 NCAAB statistics with corresponding odds), the optimal path
combines SBRO's free Excel files (covering 2020–21 and 2021–22 with opening/closing lines for all D1 games) with The
Odds API for 2022–23 through 2024–25 seasons (multi-bookmaker snapshots every 5 minutes, including Pinnacle). This
creates a **complete 5-season odds dataset** for roughly $100–200 in API costs over one to two months of access.

For deeper college history, **TeamRankings.com** provides NCAAB closing spreads and ATS records back to the **2003–04
season** (22 seasons) and similar depth for NCAAF, though extraction requires web scraping from their BetIQ tool.
OddsPortal has NCAAB results with multi-bookmaker odds from 2008–09. OddsShark's interactive database claims NCAAF odds
back to 1990, though it's web-only with no download option.

The analytics sites commonly associated with college sports — KenPom, Sagarin, Massey Ratings, Haslametrics — provide
power ratings and efficiency metrics but **none offer sportsbook odds data**. They are complementary inputs to a
projection model, not sources of odds for backtesting.

Among paid options specifically addressing the college gap: Scottfree Analytics ($99 one-time for NCAAB, $99 for NCAAF)
provides ML-ready CSV data; BigDataBall offers combined stats-and-odds datasets per season; and Sports Insights/Bet Labs
has college data back to 2003 through their web tools. No provider offers a comprehensive, multi-bookmaker, downloadable
college odds archive spanning more than five years at a sub-$500 price point — this represents the single largest gap in
the market.

---

## Top 10 sources ranked by value for projection model development

This ranking weights data volume, quality, college sports coverage, programmatic accessibility, and cost-effectiveness
for someone building a multi-sport betting model with backtesting capabilities:

1. **SportsbookReviewsOnline.com** — Free. All 6 sports, 15 seasons, opening+closing lines, Excel download. The
   foundation layer. *$0 for 2007–2022 data.*

2. **The Odds API** — Best affordable API. All 6 sports, multi-bookmaker (40+), 5-min snapshots, props/halves/quarters
   from 2023, confirmed college coverage. *~$99–199/month; pull all historical data in 1–2 months for ~$200–400 total.*

3. **Scottfree Analytics** — Best ML-ready purchase. NCAAB + NCAAF + pro sports, 132-column CSVs with target variables.
   *$99 per sport, one-time.*

4. **FinnedAI SBR Scraper (GitHub)** — Best free multi-book source. NFL/NBA/MLB/NHL from 5–8 individual sportsbooks,
   2011–2021. *$0 for pre-scraped data.*

5. **BigDataBall** — Best combined stats+odds source. All 6 sports with box scores, player data, and odds merged.
   *~$75–150 for 5 seasons with bulk discount.*

6. **Odds Warehouse** — Best bulk pro sports purchase. Clean CSVs, NBA from 2006, NFL/MLB from 2009. No college. *$79
   one-time for 10+ years.*

7. **Action Network / Bet Labs** — Deepest history (2003+) with unique betting % data. All 6 sports. No API or export.
   *~$50/month.*

8. **OddsPortal + OddsHarvester** — Best free multi-bookmaker source (80+ books). Requires technical scraping setup. All
   major sports including college. *$0 plus engineering time.*

9. **SportsDataIO** — Enterprise gold standard. All 6 sports from 2019, every line movement, props/futures, S3 bulk
   delivery. *~$599+/month — best for funded operations.*

10. **KillerSports / SDQL** — Deepest queryable database (15+ years) for trend analysis across all sports including
    college. Query-only, no bulk download. *Subscription required.*

---

## Recommended acquisition strategy and budget estimate

A practical, phased approach minimizes cost while maximizing coverage:

**Phase 1 — Free foundation ($0):** Download all SBRO Excel archives immediately. Grab the FinnedAI SBR scraper's
pre-built CSV files from GitHub. Bookmark SportsOddsHistory for futures research. This alone provides 15 seasons of all
six sports with opening/closing consensus lines.

**Phase 2 — Fill the college gap ($99–198):** Purchase Scottfree Analytics NCAAB dataset ($99) and optionally NCAAF
($99). These ML-ready CSVs with 132 columns and closing odds within one hour of tip-off are purpose-built for the user's
modeling use case.

**Phase 3 — Multi-bookmaker depth ($99–199):** Subscribe to The Odds API for one to two months at the Superstar tier
($99/month). Systematically pull all historical snapshots from June 2020 to present across all six sports. This yields
multi-bookmaker data from 40+ sportsbooks with 5-minute granularity — invaluable for closing line value analysis and
market efficiency research. Cancel after extraction.

**Phase 4 — Ongoing collection ($20–49/month):** Downgrade The Odds API to a lower tier for real-time data collection
going forward, building an increasingly deep proprietary database over time.

**Total estimated cost for comprehensive historical coverage: $200–500 one-time plus $20–49/month ongoing.** This
compares favorably to the enterprise alternative (SportsDataIO at $599+/month or Sportradar at $500–2,000+/month) while
covering all six target sports, multiple bookmakers, and the critical college sports gap. For the deepest possible
backtesting (pre-2007), supplementing with Action Network/Bet Labs ($50/month for access to data from 2003) or
engineering a scraping pipeline against OddsPortal adds incremental value at modest cost.
