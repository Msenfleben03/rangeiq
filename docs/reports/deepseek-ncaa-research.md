Excellent research prompt. This requires a systematic exploration of the entire betting data ecosystem. Based on your vectors, I have mapped the landscape to identify every realistic path for acquiring historical NCAA basketball odds.

Here is a comprehensive ecosystem map structured according to your requirements.

### **1. Professional Odds Data Vendors**

These are the primary, reliable sources for institution-grade data, offering structured, historical data via APIs.

| Name | URL | Data Type | Years Covered | Sportsbooks Included | Opening vs Closing | Access Method | Reliability for Modeling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **iSports API** | [isportsapi.com](https://www.isportsapi.com) | Historical odds, live scores, fixtures, statistics for football and basketball. | Historical football data from 2000-2020; basketball data coverage not specified but available.  | Aggregates from licensed bookmakers including Bet365, SBObet, and 188Bet.  | Provides minute-level snapshots during matches, enabling line movement analysis.  | RESTful JSON API with a free tier (~200 requests/day) and paid plans for higher volume.  | High. Cited as a choice for betting analytics and historical datasets, with structured data.  |
| **The Odds API** | [the-odds-api.com](https://the-odds-api.com) | Real-time and historical odds for H2H, spreads, totals from multiple bookmakers. | Implements a historical endpoint that can capture odds at specific timestamps (e.g., match start).  | Broad coverage including Pinnacle, FanDuel, DraftKings, Bet365, and many others. | Pipelines like `sportstensor` use it to capture "tipoff" odds (closing lines) by querying the historical endpoint at match start.  | RESTful API. Requires an API key. Freemium model with rate limits. | High. A primary source for many open-source and commercial projects. Sharpness hierarchy (preferring Pinnacle) is a common practice.  |
| **Pinnacle API** | [pinnacle.com](https://www.pinnacle.com) | Real-time and historical odds directly from the "sharpest" bookmaker. | Since at least 2017, with historical datasets for MLB 2016 released to CRAN.  | Pinnacle only. | The `pinnacle.API` R package was created to interact with their live feeds. Closing lines are available as they are the final odds before an event starts.  | Direct API access, often used by professional bettors. There are R packages like `pinnacle.API` and `odds.converter` to interface with it.  | Very High. Pinnacle is widely regarded as the market maker and sharpest book. Its data is a benchmark.  |
| **SportsDataIO** | [sportsdata.io](https://sportsdata.io) | Advanced metrics, odds, and statistics for North American sports (NFL, NBA, MLB, NHL). | Not specified for NCAA. | Not specified, but provides odds data. | Their paid plans offer access to odds data, though specific historical depth is unclear. | 7-day free trial (credit card required), then paid plans starting at ~$99/month.  | High for US sports. Known for detailed advanced metrics, making it suitable for sophisticated modeling.  |

### **2. Betting Market Infrastructure (The Source)**

These companies power the sportsbooks themselves. Accessing their historical archives is difficult but represents the ultimate source of truth.

| Name | URL | Data Type | Years Covered | Sportsbooks Included | Opening vs Closing | Access Method | Reliability for Modeling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Kambi (Odds Feed+)** | [kambi.com](https://www.kambi.com) | Low-latency odds feed, event resulting, and bet settlement services for operators.  | Not specified, but they have been in operation since 2010, implying deep historical archives.  | Kambi powers sportsbooks for 40+ operators globally, including many major brands.  | Their feed includes both pre-match and live odds. Historical archives are likely available to partners.  | Enterprise B2B API. Access is typically for operators, not individual modelers.  | Very High. As a primary odds compiler, the data is definitive, drawn from their global partner network.  |
| **Genius Sports** | [geniussports.com](https://www.geniussports.com) | Official data, odds feeds, and integrity services. A major competitor to Sportradar. | Full historical archives are likely available via enterprise agreements. | Powers a vast network of sportsbooks and media outlets. | Provides comprehensive odds data, including line movement. | Enterprise B2B APIs and feeds. | Very High. Another primary source for official league data and betting information. |
| **Sportradar** | [sportradar.com](https://www.sportradar.com) | Comprehensive sports data and odds feeds. A dominant force in the market. | Extensive historical data archives available for enterprise clients. | Supplies data to numerous sportsbooks globally. | Offers both pre-match and live odds data with full history. | Enterprise-level APIs and data feeds. | Very High. As a primary data distributor, their data is the gold standard. |

### **3. Public APIs for Odds Data**

These are more accessible than enterprise solutions and are widely used by practitioners.

| Name | URL | Data Type | Years Covered | Sportsbooks Included | Opening vs Closing | Access Method | Reliability for Modeling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **The Odds API** | [the-odds-api.com](https://the-odds-api.com) | Real-time and historical odds. | Historical data is available via specific endpoints, allowing you to query past events.  | 30+ bookmakers including Pinnacle, FanDuel, DraftKings, Bet365.  | The `sportstensor` pipeline demonstrates how to use the `/historical/.../odds/` endpoint to capture "tipoff" (closing) odds.  | RESTful API. Requires an API key. Free tier available with rate limits. | High. It's a backbone for many projects. The ability to query historical snapshots is critical.  |
| **iSports API** | [isportsapi.com](https://www.isportsapi.com) | Odds and historical sports data. | Historical football data (2000-2020). Basketball data is a core focus, so historical depth is likely strong.  | Aggregates from multiple licensed bookmakers like Bet365, SBObet, 188Bet.  | Provides minute-level match snapshots, which is ideal for tracking line movement.  | RESTful JSON API. Free tier available (~200 requests/day).  | High. Specifically mentioned for "match-fixing detection" and "long-term statistical modeling."  |

### **4. Open-Source Scraping Infrastructure**

These tools and projects are used by the community to build their own odds databases.

| Name | URL | Data Type | Years Covered | Sportsbooks Included | Opening vs Closing | Access Method | Reliability for Modeling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **anscrapR** | [github.com/john-b-edwards/anscrapR](https://github.com/john-b-edwards/anscrapR) | An R package to interface with the **Action Network API** to pull betting information.  | Action Network data dates back to 2017.  | Action Network aggregates lines from "a variety of different books."  | The API provides data on a `game_id` basis, including `book`, `updated` timestamps, `bet_type`, and `value`. This allows for historical line movement analysis.  | R package that scrapes the Action Network API. Must be run by the user.  | Medium-High. Depends on the stability of the Action Network's underlying API. The package is actively maintained (last updated May 2024 for V2 API).  |
| **OddsComparator-Project** | [github.com/Rorouh/OddsComparator-Project](https://github.com/Rorouh/OddsComparator-Project) | A complete ETL pipeline that scrapes The Odds API and stores data in a MySQL database.  | Real-time focused, but the pipeline is designed for continuous data collection, making it suitable for building a historical archive.  | It filters for specific bookies of interest, including 888sport, 1xBet, and Betfair.  | The script `Obtener_cuotas_API.py` fetches the `h2h` market. If run continuously, it would capture line movements.  | Python scripts that use The Odds API. It includes automated ETL and can be scheduled via cron.  | High. It's a well-architected, production-ready pipeline for building a custom historical database using a reliable data source.  |

### **5. Odds Aggregator Websites**

These sites are common targets for scraping due to their long historical archives.

| Name | URL | Data Type | Years Covered | Sportsbooks Included | Opening vs Closing | Access Method | Reliability for Modeling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Action Network** | [actionnetwork.com](https://actionnetwork.com) | Aggregated odds and betting information from various sportsbooks. | Data dating back to 2017, as evidenced by the `anscrapR` package.  | Aggregates lines from a wide variety of books.  | The API provides timestamps and values, making it possible to reconstruct line movements.  | Their API can be scraped using tools like `anscrapR`. The website itself is also a target for web scraping.  | Medium. Depends on the stability of their anti-scraping measures and the underlying API's structure. |
| **OddsPortal** | [oddsportal.com](https://www.oddsportal.com) | Extensive historical odds archive for major sports and leagues. | Deep historical archives for many leagues, including NCAA basketball. | Covers hundreds of bookmakers from around the world. | Clearly displays opening and closing odds, and allows users to view odds history and movement. | Primarily accessed via web scraping (Selenium, Puppeteer). There are known GitHub projects for this. | Medium-High. The data is comprehensive, but scraping is challenging due to aggressive anti-bot protections. |
| **VegasInsider** | [vegasinsider.com](https://www.vegasinsider.com) | Odds, lines, and betting information, primarily focused on the US market. | Long historical archives, particularly for major US sports like NCAA basketball. | Covers major US sportsbooks and Las Vegas sportsbooks. | Typically displays opening and current lines, with some historical data available. | Web scraping is the primary method. | Medium. A long-standing source, but its structure can change, breaking scrapers. |

### **6. Academic Research Datasets**

These datasets are often used in published research and can be a source of clean, curated data.

| Name | URL | Data Type | Years Covered | Sportsbooks Included | Opening vs Closing | Access Method | Reliability for Modeling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Kaggle: College Basketball Dataset** | [kaggle.com](https://www.kaggle.com/datasets/andrewsundberg/college-basketball-dataset) | Aggregated team statistics (win %, seed, adjusted efficiency, WAB, etc.) from 2013-2023.  | 2013-2023 (excluding 2020).  | Does **not** contain bookmaker odds. | N/A | Direct download from Kaggle. | N/A for odds data. This is cited as an example of the *type* of dataset used in prediction models, often combined with a separate odds feed.  |
| **CRAN: Pinnacle MLB 2016 Dataset (Planned)** | [cran.r-project.org](https://cran.r-project.org) | A planned R package containing all Pinnacle odds for the 2016 MLB season.  | 2016 MLB Season.  | Pinnacle.  | The dataset would contain full-season odds, presumably including opening and closing lines.  | R package from CRAN (upon release). | Very High. This is an example of a vendor (Pinnacle) releasing a clean, complete historical dataset for academic/educational use.  |

### **7. Community Knowledge Sources**

These are places where practitioners discuss the challenges and solutions of data acquisition.

| Name | URL | Data Type | Years Covered | Sportsbooks Included | Opening vs Closing | Access Method | Reliability for Modeling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **r/algobetting** | [reddit.com/r/algobetting](https://reddit.com/r/algobetting) | Discussions on data sources, modeling strategies, and scraping techniques. | N/A | N/A | N/A | Web access. Search for terms like "historical data," "API," "scraping," "Pinnacle." | High (for qualitative insights). The community shares practical knowledge on what works and what doesn't. |
| **r/sportsbook** | [reddit.com/r/sportsbook](https://reddit.com/r/sportsbook) | General betting discussion, with some threads on data and analytics. | N/A | N/A | N/A | Web access. | Medium. Less technical than algobetting, but can be a source for identifying new data tools or sites. |
| **sportstensor DeepWiki** | [deepwiki.com/sportstensor/sportstensor](https://deepwiki.com/sportstensor/sportstensor/5.2-odds-data-ingestion-pipeline) | A detailed technical breakdown of a production-grade odds ingestion pipeline.  | N/A | Pinnacle (primary), others as fallback. | The system explicitly captures "tipoff" odds for closing lines.  | This is a knowledge resource, not a data source. It provides a blueprint for building your own system. | Very High. It documents best practices like vig normalization and bookmaker preference logic.  |

### **8. Paid Datasets and Marketplaces**

These are datasets sold directly, often by individual researchers or smaller companies.

| Name | URL | Data Type | Years Covered | Sportsbooks Included | Opening vs Closing | Access Method | Reliability for Modeling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Unabated** | [unabated.com](https://unabated.com) | A sharp betting tool that provides access to historical lines, closing line value (CLV) data, and market projections. | Deep historical archives for major sports, including NCAA basketball. | Aggregates data from many sportsbooks, with a focus on sharp books like Pinnacle and CRIS. | Their entire platform is built on analyzing opening and closing lines. CLV is a core metric. | Subscription-based access to their web interface and data tools. | High. Built by professional bettors specifically for sharp analysis. |
| **OddsJam** | [oddsjam.com](https://www.oddsjam.com) | Real-time and historical odds data for arbitrage and +EV betting. | Historical odds data is a core part of their offering for finding positive EV opportunities. | Covers a vast number of sportsbooks, including major US and offshore books. | Provides tools to see historical odds movements and identify the best lines over time. | Subscription-based access to their platform and data via API. | High. Their business model depends on the accuracy and timeliness of their odds data. |

### **9. Scraping Automation Tools**

These platforms and tools are used to build and manage scrapers at scale.

| Name | URL | Data Type | Years Covered | Sportsbooks Included | Opening vs Closing | Access Method | Reliability for Modeling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Apify** | [apify.com](https://apify.com) | A platform for deploying and running web scrapers (called Actors) at scale. | Users can run scrapers continuously to build historical archives. | The platform hosts community-created Actors for many sportsbooks and odds sites. | Depends on the specific Actor used. Some are designed to capture odds movements. | Platform access. You can use pre-built Actors or deploy your own Python/Node.js code. | Medium. Reliability depends on the quality of the Actor and the anti-scraping measures of the target site. |
| **Browserless/Puppeteer** | [browserless.io](https://browserless.io) / [pptr.dev](https://pptr.dev) | Headless browser automation for scraping dynamic websites. | N/A | N/A | N/A | Self-hosted or via a service like browserless. Used to run scraping scripts. | N/A (Infrastructure). This is the tooling used to build scrapers for sites like OddsPortal.  |
| **Scrapy** | [scrapy.org](https://scrapy.org) | An open-source and collaborative framework for extracting the data you need from websites. | N/A | N/A | N/A | Python framework for building large-scale web scrapers. | N/A (Infrastructure). A powerful tool for building robust scrapers for aggregator sites. |

### **10. Deprecated or Obscure Data Sources**

These are sources that may no longer be active but could contain valuable historical data.

| Name | URL | Data Type | Years Covered | Sportsbooks Included | Opening vs Closing | Access Method | Reliability for Modeling |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **DonBest (Historical)** | [donbest.com](https://www.donbest.com) | Once a premier source for odds data, it was acquired by Genius Sports. The public-facing historical archives may be gone or restricted. | Pre-acquisition, they had extensive historical data. | Aggregated from major Las Vegas and offshore sportsbooks. | Their data was the industry standard for opening and closing lines. | The original public API and website are deprecated. Data may be available in archived datasets or through Genius Sports enterprise agreements. | N/A (Deprecated). If you can find an old archive, it could be a goldmine, but it's unlikely to be in a usable format. |
| **Pinnacle API (Historical R Package)** | Mentioned in useR! 2017 conference.  | A planned CRAN package with full 2016 MLB season odds from Pinnacle.  | 2016 MLB Season.  | Pinnacle.  | The package was intended to provide full-season data, including opening and closing lines.  | It is unclear if this package was ever released. Searching CRAN for it would be necessary. | Unknown. If it exists, it would be very high. This is an example of a potentially obscure but perfect dataset.  |
