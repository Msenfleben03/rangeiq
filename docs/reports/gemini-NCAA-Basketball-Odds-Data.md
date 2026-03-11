# **The Architecture of Historical NCAA Basketball Odds Data (2018–2025): A Comprehensive Guide for Predictive Modeling**

The construction of robust, predictive machine learning models for NCAA Division I men’s basketball requires an exhaustive foundation of historical odds data. The landscape of college basketball is uniquely complex, featuring over 360 Division I teams playing thousands of games over a highly compressed schedule. The period from 2018 to 2025 represents the most critical era for quantitative sports betting research, marked by the repeal of the Professional and Amateur Sports Protection Act (PASPA) in the United States, the subsequent explosion of retail sportsbooks, and the increasing sophistication of sharp market makers. Capturing the nuances of this market—specifically the movement from opening lines to closing lines across multiple sportsbooks—demands a sophisticated data engineering pipeline.

The analytical community relies on a highly fragmented ecosystem of commercial APIs, static datasets, community-maintained scrapers, and academic archives to synthesize this historical data. To achieve a multi-book, multi-year, reproducible, and scraper-friendly workflow, practitioners must map and integrate every credible, obscure, deprecated, and community-built source available. This report provides a rigorous architectural analysis of the data sources utilized by quantitative sports bettors and data engineers, anchoring the analysis to the practical requirements of backtesting, model calibration, and expected value (EV) generation.

## **The Theoretical Framework of College Basketball Markets**

Before architecting a data pipeline, it is essential to understand the theoretical mechanics of the college basketball betting market. A predictive model is only as valuable as the baseline it is measured against. In sports betting analytics, the primary objective is not merely predicting the winner of a game, but rather identifying discrepancies between the model's projected probabilities and the probabilities implied by the bookmaker's odds.

The implied probability ![][image1] of American odds is calculated using the following piecewise function, where ![][image2] represents the American odds value:

If ![][image3]:

![][image4]

If ![][image5]:

![][image6]

To calculate true market probability, the theoretical "vig" or "overround" (the bookmaker's margin) must be mathematically removed from the odds.

The timeline of odds availability dictates the structural requirements of the historical dataset. The "Opening Line" represents the initial price offered to the market, typically set by sharp, high-limit bookmakers like Pinnacle or Circa Sports. The "Closing Line" represents the final equilibrium price immediately before tip-off, reflecting the aggregate consensus of all market information, injuries, and sharp money. A successful backtesting environment requires both: the opening line to identify initial market inefficiencies, and the closing line (Closing Line Value, or CLV) to validate whether the model is beating the sharpest available consensus over the long term.

Consequently, a multi-year historical dataset must successfully capture discrete snapshots of these lines across a diverse array of sportsbooks. The community utilizes a blended approach of commercial providers, academic datasets, and custom scraping infrastructure to achieve this.

## **Core, Actively Maintained Data Providers**

The foundation of any reproducible historical odds database typically begins with commercial data providers that offer paid and free tiers. These entities aggregate, normalize, and distribute historical odds, offering varying degrees of granularity, latency, and historical depth. The choice of provider fundamentally dictates the architecture of the downstream machine learning pipeline.

### **FantasyData and SportsDataIO**

For institutional-grade applications requiring deep historical coverage without the complexity of chronological snapshot traversal or web scraping, FantasyData (powered by SportsDataIO) provides an exhaustive, actively maintained repository. FantasyData is widely utilized by practitioners who prefer direct file downloads over complex API integrations.

The platform provides consensus game-level odds, delivering downloadable CSV and XLS files that eliminate the need for public scrapers. Accessing the full breadth of historical odds requires an All-Access plan.1 The pricing structure for NCAA basketball data is segmented: the NCAA Basketball Betting Data package, which includes odds aggregates, schedules, and next-day results, costs $99 per month or $499 annually. For modelers who also require player-level projections to build out feature matrices, a combined Fantasy & Betting Data package is available for $149 per month.2

The underlying architecture of SportsDataIO's historical database is particularly advantageous for developers. The historical betting lines cover all major sports from 2019 onwards, effectively covering the post-PASPA era.4 The data structure for historical calls is identical to the payload used for live, in-season data.5 Developers merely alter the endpoint routing to target the Data Warehouse and supply specific parameters: Season (e.g., 2024), BettingMarketId, and SportsbookGroup.5 Because the data is static once a game concludes, the API delivers the final betting outcomes and the complete line movement history in a single, consolidated payload, making it an ideal core provider for consensus closers.

### **The Odds API**

The Odds API has emerged as the central programmatic pillar for developers requiring structured JSON data across a multitude of global bookmakers, including US (DraftKings, FanDuel, BetMGM, Caesars), EU, UK, and AU regions. The service provides snapshots of events and bookmaker odds as they existed at specific points in time, making it highly suitable for recreating historical line movements.6

Historical odds data for featured markets—including moneyline, point spreads, and totals—is available beginning from June 6, 2020\. For this early data, snapshots were captured at ten-minute intervals. Recognizing the need for higher fidelity data for backtesting, the service increased its snapshot frequency to five-minute intervals starting in September 2022\.6

Accessing the historical endpoints requires a date parameter formatted in ISO 8601 (e.g., 2021-10-18T12:00:00Z). The JSON payload returned includes the requested snapshot data alongside temporal navigation aids, specifically a previous\_timestamp and a next\_timestamp, which allow engineers to programmatically traverse line movements chronologically without guessing the exact snapshot times.6

The community extensively uses Python and R wrappers, combined with cron jobs, to store daily and hourly snapshots. However, historical access requires a paid tier. The 20K tier ($30/month) provides 20,000 monthly requests, while the 100K tier ($59/month) provides 100,000 requests.7 Because querying historical snapshots consumes quota rapidly, practitioners generally limit their calls to specific, high-value temporal markers: the opening release, 24 hours pre-game, 1 hour pre-game, and the closing line.

### **TeamRankings**

TeamRankings provides a distinct, highly accessible perspective on historical odds by focusing on closing line history and spread distributions. Rather than providing raw, chronological line movement logs, TeamRankings aggregates the performance of teams against specific closing lines over time.8

Their database tracks win-loss and against-the-spread (ATS) records categorized by the exact closing spread. For example, a modeler can instantly retrieve the historical cover percentage for all home teams favored by exactly 6.5 points over the last decade.8 Access to TeamRankings is achieved either through a premium subscription or via web scraping.8 Because the HTML structure of the TeamRankings statistical tables is highly stable, the community has built numerous open-source scrapers targeting this site, effectively using it as a validation source for consensus closers and spread distribution analysis.10

### **Scottfree Analytics**

While APIs provide flexibility, many quantitative modelers prefer static, pre-engineered datasets that bypass the data engineering phase entirely. Scottfree Analytics serves this exact niche, providing proprietary CSV dumps of historical NCAAB odds specifically tailored for machine learning applications.

Priced dynamically (often between $99 and $149), the Scottfree NCAAB Historical Odds Data is defining by its expansive, 132-column schema.11 The dataset includes pre-calculated target variables designed directly for supervised learning algorithms, alongside traditional spreads, moneylines, and totals.12

Crucially, the odds captured in this dataset represent the final lines recorded within one hour before game time, providing a highly accurate reflection of the closing market consensus.12 Furthermore, Scottfree Analytics resolves one of the most persistent issues in sports data engineering: entity resolution. The dataset utilizes standardized team names without abbreviations, ensuring that downstream merges with academic statistical databases do not fail due to nomenclature mismatches.12 People buy this dataset once and integrate it directly into their modeling pipelines, requiring absolutely zero scraping.

## **Academic, Open, and Feature Engineering Datasets**

Predicting NCAA basketball outcomes requires more than just historical betting lines. Models require deep, contextual statistical features to identify inefficiencies in the market. The sports betting analytics community relies heavily on academic and open-source repositories to build the feature space that sits alongside the target variables derived from the odds data. These datasets are often overlooked by novice bettors but are foundational to advanced workflows.

### **The Kaggle Ecosystem**

Kaggle hosts several indispensable datasets that are continuously updated and widely utilized by the community as the backbone for modeling features.

The "College Basketball Dataset," maintained by Andrew Sundberg, aggregates Division I data from the 2013 season through the 2025 season. It is updated annually and contains team-level statistics scraped from Barttorvik, a highly respected advanced analytics platform.14 This dataset provides foundational efficiency metrics that are highly correlated with market lines. Key variables include:

* **ADJOE & ADJDE:** Adjusted Offensive and Defensive Efficiency (points scored/allowed per 100 possessions, adjusted for opponent strength).
* **BARTHAG:** A power rating indicating the chance of beating an average Division I team.
* **EFG\_O & EFG\_D:** Effective Field Goal Percentage Shot and Allowed.
* **TOR & TORD:** Turnover Rates committed and allowed.14

While it does not contain full odds history, merging the cbb.csv data with the Scottfree or The Odds API datasets provides the exact feature-target pairs required for XGBoost or Random Forest classifiers.

Similarly, the dataset curated by Jonathan Pilafas provides a meticulously structured extraction of KenPom data spanning from 2002 to 2025\. This dataset captures every metric available on the KenPom platform, including the Four Factors of basketball success, point distribution percentages, and height/experience metrics.16 Crucially, the Pilafas dataset includes complex mapping tables that aggregate historical conference affiliations and standardize team names, serving as a vital bridge for joining advanced metrics with commercial odds databases.16

A separate Kaggle repository, maintained by ZachHT, focuses explicitly on global basketball odds history (including NCAAB), scraping data at seven-minute intervals.17 While it provides euro-style odds and extensive coverage, community reliance on standard American odds formatting often pushes researchers to merge these open repositories with structured data from commercial providers.17

### **Sports-Reference and FiveThirtyEight**

Sports-Reference (College Basketball) does not officially provide odds data, but it is universally scraped for fundamental game metadata: box scores, venue locations, neutral site identifiers, schedules, and player-level statistics. Because game context (e.g., rest days, travel distance, altitude) heavily influences NCAAB outcomes, extracting this metadata is non-negotiable. While Sports-Reference has implemented stricter rate limits in recent years, deprecated scrapers and legacy CSV dumps exist in GitHub archives to backfill the 2018-2022 period.

FiveThirtyEight's historical predictions are equally valuable. Although FiveThirtyEight did not publish American odds, they published implied probabilities based on their Soccer Power Index (SPI) equivalent for basketball. The community uses archived GitHub repositories containing FiveThirtyEight's historical game probabilities to calibrate their own models. By comparing a custom model's output to both the FiveThirtyEight projection and the Pinnacle closing line, a quant can triangulate the true signal in a noisy market.

## **Target Sportsbooks and Scraper-Friendly Frontends**

For researchers unwilling or unable to purchase premium API access, the alternative is developing custom web scrapers. However, sportsbooks deploy aggressive anti-bot countermeasures (such as Cloudflare, DataDome, and device fingerprinting), making historical scraping a highly specialized discipline. The community universally targets specific books that represent distinct market behaviors, focusing on capturing the sharpest openers and the most accurate retail closers.

### **The Sharp Market: Pinnacle and Circa Sports**

Any robust historical odds dataset must isolate "sharp" money from "retail" money. Pinnacle is universally recognized as the sharpest bookmaker in the world, operating on a low-margin, high-volume model that welcomes winning bettors and uses them to shape the line. Consequently, Pinnacle's openers are considered the gold standard for price discovery, and their closing lines are considered the closest representation of true probability in the sports betting market.18

Historically, Pinnacle offered an API suite that was widely utilized by the academic and pregame handicapping communities. However, access to the Pinnacle API suite was officially closed to the general public on July 23, 2025, restricting access strictly to bespoke commercial partnerships and select high-value bettors.20 Due to this closure, the community relies heavily on archived GitHub repositories, legacy async scrapers, and third-party aggregators to piece together Pinnacle data from 2018 to 2025\.21

Circa Sports occupies a similar position in the US domestic market. Operating out of Las Vegas, Circa takes high limits and welcomes sharp action, making their opening lines highly respected. While they have limited historical access natively, Discord communities frequently share daily CSV dumps of Circa's opening numbers, which are manually ingested by modelers.

### **Stable HTML and Retail Giants: BetOnline, Bookmaker, and DraftKings**

BetOnline and Bookmaker.eu are highly valued for their long-running historical lines and relative frontend stability. BetOnline is frequently scraped because its HTML structure remains more static than modern single-page applications, allowing developers to use simple Python tools without heavy browser automation. Bookmaker.eu is closely monitored for its closing lines, and although it requires a login to view certain limits, community scrapers exist to bypass basic hurdles.

Conversely, modern retail books like DraftKings, FanDuel, Caesars, and BetMGM are the ultimate targets for executing bets, but they are notoriously difficult to scrape historically. Their JSON endpoints change frequently, and their frontends rely heavily on dynamic JavaScript rendering. Scraping these modern books requires sophisticated, headless browser automation (Selenium or Playwright). Therefore, most historical datasets do not attempt to scrape DraftKings chronologically; instead, they rely on The Odds API to capture these modern retail lines, combining them with scraped Pinnacle openers to create a holistic view of the market.23

## **Open Source Tooling and GitHub Repositories**

The sports analytics community is deeply bifurcated between R and Python users, and comprehensive tooling has been developed in both languages to facilitate the extraction and normalization of NCAAB data. GitHub serves as the central repository for both actively maintained libraries and deprecated, yet highly valuable, legacy code.

### **The R Ecosystem: hoopR and oddsapiR**

Within the R programming environment, the SportsDataverse project maintains several critical packages. The hoopR package is an indispensable utility for obtaining clean, tidy men's basketball play-by-play data.25 It serves as a wrapper for ESPN's backend APIs, providing functions such as load\_mbb\_pbp() to retrieve full play-by-play seasons for college basketball from 2006 to the present.27 The package extracts massive datasets efficiently, pulling hundreds of thousands of rows of play-by-play data in seconds.25

Crucially for modelers, hoopR also features a scraping interface for Ken Pomeroy's website. Functions like kp\_efficiency(), kp\_fourfactors(), and kp\_team\_tables() allow users with active KenPom subscriptions to programmatically pull efficiency and tempo summaries, directly integrating advanced metrics into their R dataframes.29

To complement the statistical data, the oddsapiR package provides a native R interface for The Odds API. Functions such as toa\_sports\_odds\_history() allow R users to programmatically pull historical snapshots, while toa\_sports\_odds() retrieves current lines.30 The package handles the API key authentication through .Renviron variables and manages the JSON parsing, returning clean tibbles that can be immediately joined with the hoopR datasets using standard dplyr logic.30

### **Python Web Scraping and Automation Tools**

Python remains the dominant language for custom scraping infrastructure. Due to the dynamic nature of modern sportsbook frontends, Python developers rely on a tiered approach to data extraction:

1. **BeautifulSoup:** Used for static HTML sites like TeamRankings. Using pandas.read\_html combined with BeautifulSoup allows for rapid ingestion of tabular spread data without complex DOM parsing.10
2. **Selenium and Playwright:** Used for dynamic, retail books like DraftKings and FanDuel. These tools spin up headless browsers to execute JavaScript, render the page, and extract the changing JSON payloads hidden in the network traffic.10
3. **Async Scrapers:** Legacy scrapers designed for Pinnacle's old XML feeds heavily utilized asynchronous Python (asyncio, aiohttp) to rapidly parse line changes before the API was deprecated.21

### **GitHub Archives: Working, Deprecated, and Obscure**

The GitHub landscape is a graveyard of broken scrapers and a goldmine of archived data.

* **Working / Maintained:** Includes the aforementioned Odds API wrappers, "NCAAB-odds-scraper" forks that target BetOnline, and "Sports-scraper" repositories utilizing Playwright for modern retail books.33
* **Deprecated but Valuable:** Repositories containing 2016–2021 Pinnacle line history scrapers are no longer functional due to the 2025 API closure 20, but the CSV data files they left behind in their commit histories are priceless for researchers backfilling the 2018-2020 window.34 Similarly, old Action Network scrapers that operated before paywalls and API changes were implemented contain massive caches of legacy data.
* **Obscure / Niche:** Repositories built for arbitrage bots often include highly granular, second-by-second line-movement logs. While the bots themselves are proprietary, developers often upload CSV dumps of their training data via GitHub Gists. Furthermore, repositories titled "College-basketball-betting-model" frequently contain embedded historical odds within their /data directories, uploaded by students or researchers showcasing their machine learning projects.18

## **Community Syndication and Crowdsourcing**

Given the prohibitive costs of enterprise API access (which can reach thousands of dollars per month) and the technical barriers to web scraping, a massive underground economy of data sharing exists within Reddit communities and private Discord servers.

### **Reddit Communities**

Subreddits serve as the primary public syndication hubs for sports betting data:

* **r/sportsbook:** The largest hub for line movement discussions. While primarily focused on daily betting, users frequently share custom scrapers or request specific data sets.
* **r/CollegeBasketball:** During March Madness, this subreddit becomes a massive repository of data threads, with users sharing advanced statistical models and historical tournament trends.
* **r/datasets and r/algobetting:** These are the technical centers. Users frequently request and share historical game-by-game data, often posting Google Drive links or GitHub Gists containing parsed CSV files of Pinnacle and BetOnline lines.36 These dumps are highly valuable for filling gaps in a researcher's proprietary database, particularly for the 2018–2020 period before commercial APIs offered cheap historical access.

### **Discord Servers**

The most valuable data is rarely indexed by search engines; it lives in private Discord servers. Groups like "Sports Analytics," "Betting Data Engineering," and "Model Builders Lounge" operate as invite-only syndicates. Within these servers, developers actively share automated scripts, bypass techniques for sportsbook rate limits (such as rotating residential proxies), and strategies for normalizing chaotic data structures. More importantly, these communities often crowdsource the cost of premium APIs, sharing raw CSV dumps or JSON archives of Circa openers and Pinnacle closers on a daily basis.

## **Architecting the 2018–2025 Pipeline: Synthesis and Normalization**

Synthesizing a multi-book, multi-year, reproducible historical odds database requires combining the aforementioned sources into a normalized relational schema. Most practitioners do not rely on a single source; rather, they combine Pinnacle openers (scraped or purchased), consensus closers (from FantasyData, TeamRankings, or The Odds API), and book-specific lines (DraftKings, FanDuel, BetOnline). They then manually backfill the 2018-2020 period using community CSV dumps, and merge the resulting odds table with metadata from Sports-Reference and Kaggle.

### **Database Architecture and Schema Design**

A robust relational database must decouple the physical NCAA event from the fluid odds market. A standard implementation utilizes several core tables designed for high-performance querying 23:

| Table Name | Description | Key Fields |
| :---- | :---- | :---- |
| Sports | Defines the league context. | sport\_id, sport\_name, sport\_key (API identifier) |
| Sportsbooks | Defines the origin of the odds. | book\_id, book\_name, is\_sharp (Boolean identifier) |
| Games | The core event entity. | game\_id, sport\_id, home\_team, away\_team, commence\_time |
| Odds\_History | Temporal tracking of lines. | odds\_id, game\_id, book\_id, market\_type, timestamp, home\_odds, away\_odds, line |
| Game\_Results | The ultimate resolution. | game\_id, home\_score, away\_score, status |

The Odds\_History table is the most critical component. Because odds update asynchronously across different books, the database must store discrete snapshots. When evaluating a model, the query will search for the specific timestamp representing the "Open" (the earliest recorded timestamp for a specific game\_id associated with a sharp book) and the "Close" (the timestamp closest to, but strictly before, the commence\_time).

### **The Entity Resolution Problem**

The most persistent failure point in NCAA basketball data engineering is entity resolution. The sheer volume of Division I teams leads to chaotic nomenclature across different platforms. The Odds API might list a team as "Loyola (Chi) Ramblers" 38, ESPN (via hoopR) might list them as "Loyola Chicago", and KenPom might use "Loyola MD".

To ensure reproducibility, the pipeline must implement a master synonym dictionary or utilize fuzzy string matching algorithms (e.g., Levenshtein distance) to map disparate team names to a unique internal team\_id. This is why pre-engineered datasets like Scottfree Analytics provide immense value; the 132-column schema utilizes standardized team names without abbreviations, ensuring seamless joins between the odds data and the statistical feature space derived from Kaggle.12

## **Model Calibration and Validation via Bet Tracking**

Once the historical database is constructed and the machine learning model is trained on the statistical features (ADJOE, Four Factors, player experience, etc.), the output must be rigorously backtested. This requires a structured evaluation framework that mirrors real-world bet tracking.

Evidence of sophisticated tracking methodologies can be observed in professional tracking environments, such as comprehensive portfolio management spreadsheets used by bettors to monitor ROI. A professional bet tracker categorizes data by temporal periods, segmenting performance by sport (e.g., "2022 CBB", "2024 CFB").39

The evaluation schema requires specific columns to accurately calculate expected value and long-term profitability. Standard fields include the Date Placed, Category (Spread, Moneyline, Total), Specific Matchup, Odds (in American format), Units Risked, Units to Win, and the final Result (WIN, LOSS, PUSH).39

To validate the NCAAB model against the historical odds database, the data pipeline simulates this exact tracking behavior programmatically. The workflow proceeds as follows:

1. The machine learning model generates a projected win probability for the home team based on Kaggle/hoopR features.
2. The pipeline queries the Odds\_History table for the available odds at various retail sportsbooks (e.g., DraftKings, BetMGM) at exactly one hour before tip-off.
3. The American odds are converted to implied probabilities with the overround removed.
4. If the model's projected probability exceeds the bookmaker's implied probability by a defined threshold (the edge), the system logs a simulated bet of 1.0 Unit into the virtual tracker.

The simulated results are then aggregated to calculate the net units won or lost, the win percentage, and the overall Return on Investment (ROI).39

Furthermore, the model's chosen line is compared against the sharp closing line (historically Pinnacle) to measure Closing Line Value (CLV). A model that consistently beats the closing line—meaning the bettor secured \+5.5 points when the sharp market closed at \+4.0 points—is mathematically favored to achieve long-term profitability, regardless of short-term variance.

The historical database is also used to validate heuristic "PRO Systems".40 Analysts frequently hypothesize that specific parameters—such as a home underdog coming off a double-digit road loss—yield a positive expectation against the spread.40 By querying the normalized 2018–2025 database, researchers can systematically backtest these hypotheses, verifying if the system plays demonstrate a statistically significant edge over a multi-year sample size.

## **Strategic Pathways and Architectural Recommendations**

For a quantitative researcher assessing what is missing from their model, having already established a multi-year scope (2018–2025), a need for openers and closers, and multi-book coverage, the final step is selecting the architectural direction that best fits the workflow.

### **The Unified Dataset Approach**

For researchers whose primary focus is strictly algorithm development and feature engineering, purchasing a single, unified dataset is the most efficient route. Providers like Scottfree Analytics offer machine-learning-ready CSVs that eliminate hundreds of hours of data engineering. The inclusion of standardized entity names, pre-calculated target variables, and accurate final odds provides an immediate foundation for training models in Python or R.12 This approach requires supplemental scraping only if specific intra-day line movement data is desired, but provides absolute stability for immediate backtesting.

### **The Reproducible Pipeline Approach**

For operations that require ongoing, automated data ingestion, live deployment, and granular analysis of line movement, a programmatic pipeline is mandatory. This involves purchasing a commercial API subscription—such as The Odds API's 20K or 100K tier—to access historical snapshots dating back to 2020\.6 The pipeline utilizes Python or oddsapiR to pull specific temporal snapshots, storing them in a localized SQL database.23 Simultaneously, the pipeline executes nightly cron jobs to pull advanced statistical features via hoopR to maintain the feature space.27 While this requires significant upfront engineering to resolve team name discrepancies, it results in an autonomous infrastructure that seamlessly transitions from historical backtesting to live betting execution.

### **The Hybrid Approach**

A pragmatic middle ground involves purchasing legacy CSV dumps or crowdsourcing data from Discord/Reddit to cover the highly fragmented 2018–2020 period. This historical base is then merged with a lightweight, live scraper pipeline targeting consensus closers via TeamRankings and real-time APIs. Given the deprecation of the Pinnacle API 20, relying entirely on automated scraping for historical sharp lines is increasingly fragile. Archival dumps fill these temporal gaps, allowing the developer to focus their scraping efforts purely on modern retail bookmakers and current market consensus.

Ultimately, the architecture of an NCAAB odds database is a rigorous exercise in data normalization. The inherent chaos of college basketball requires a disciplined approach to data engineering—merging the stability of academic datasets with the volatility of commercial APIs—before profitable predictive modeling can begin.

#### **Works cited**

1. NCAA Basketball Odds | FantasyData, accessed March 8, 2026, [https://fantasydata.com/ncaa-basketball/odds](https://fantasydata.com/ncaa-basketball/odds)
2. FantasyData.com API Pricing, Review and Data \- SportsAPI.com, accessed March 8, 2026, [https://sportsapi.com/api-directory/fantasydata/](https://sportsapi.com/api-directory/fantasydata/)
3. BettingData.com API Pricing, Review and Data \- SportsAPI.com, accessed March 8, 2026, [https://sportsapi.com/api-directory/bettingdata/](https://sportsapi.com/api-directory/bettingdata/)
4. Historical Odds \- SportsDataIO, accessed March 8, 2026, [https://sportsdata.io/historical-odds](https://sportsdata.io/historical-odds)
5. Historical Data Guide \- SportsDataIO, accessed March 8, 2026, [https://support.sportsdata.io/hc/en-us/articles/4405005816215-Historical-Data](https://support.sportsdata.io/hc/en-us/articles/4405005816215-Historical-Data)
6. Historical Sports Odds Data API, accessed March 8, 2026, [https://the-odds-api.com/historical-odds-data/](https://the-odds-api.com/historical-odds-data/)
7. The Odds API: Sports Odds API, accessed March 8, 2026, [https://the-odds-api.com/](https://the-odds-api.com/)
8. NCAA Basketball Odds & Line History \- Win-Loss \+ Spread Records, accessed March 8, 2026, [https://betiq.teamrankings.com/college-basketball/betting-trends/by-closing-line/win-loss-and-spread-records/](https://betiq.teamrankings.com/college-basketball/betting-trends/by-closing-line/win-loss-and-spread-records/)
9. NCAA Basketball Odds & Line History on TeamRankings.com, accessed March 8, 2026, [https://www.teamrankings.com/ncb/odds-history/spread-and-over-under/](https://www.teamrankings.com/ncb/odds-history/spread-and-over-under/)
10. Scraping data from TeamRankings.com \- python \- Stack Overflow, accessed March 8, 2026, [https://stackoverflow.com/questions/74997100/scraping-data-from-teamrankings-com](https://stackoverflow.com/questions/74997100/scraping-data-from-teamrankings-com)
11. Shop \- Scottfree Analytics, accessed March 8, 2026, [https://www.scottfreellc.com/shop](https://www.scottfreellc.com/shop)
12. NBA Historical Odds and Lines Data in CSV Format, accessed March 8, 2026, [https://www.scottfreellc.com/shop/p/nba-historical-odds-data](https://www.scottfreellc.com/shop/p/nba-historical-odds-data)
13. Free Historical Odds Sample Data \- Scottfree Analytics, accessed March 8, 2026, [https://www.scottfreellc.com/shop/p/historical-odds-sample-data](https://www.scottfreellc.com/shop/p/historical-odds-sample-data)
14. College Basketball Dataset \- Kaggle, accessed March 8, 2026, [https://www.kaggle.com/andrewsundberg/college-basketball-dataset/activity](https://www.kaggle.com/andrewsundberg/college-basketball-dataset/activity)
15. College Basketball Dataset \- Kaggle, accessed March 8, 2026, [https://www.kaggle.com/datasets/andrewsundberg/college-basketball-dataset](https://www.kaggle.com/datasets/andrewsundberg/college-basketball-dataset)
16. March Madness Historical DataSet (2002 to 2025\) \- Kaggle, accessed March 8, 2026, [https://www.kaggle.com/datasets/jonathanpilafas/2024-march-madness-statistical-analysis/data](https://www.kaggle.com/datasets/jonathanpilafas/2024-march-madness-statistical-analysis/data)
17. Basketball-odds-history \- Kaggle, accessed March 8, 2026, [https://www.kaggle.com/datasets/zachht/wnba-odds-history](https://www.kaggle.com/datasets/zachht/wnba-odds-history)
18. MatejFrnka/ScalableML-project \- GitHub, accessed March 8, 2026, [https://github.com/MatejFrnka/ScalableML-project](https://github.com/MatejFrnka/ScalableML-project)
19. (PDF) Multifactorial analysis of factors influencing elite Australian, accessed March 8, 2026, [https://www.researchgate.net/publication/337978625\_Multifactorial\_analysis\_of\_factors\_influencing\_elite\_Australian\_football\_match\_outcomes\_a\_machine\_learning\_approach](https://www.researchgate.net/publication/337978625_Multifactorial_analysis_of_factors_influencing_elite_Australian_football_match_outcomes_a_machine_learning_approach)
20. pinnacleapi/pinnacleapi-documentation: Pinnacle API Documentation, accessed March 8, 2026, [https://github.com/pinnacleapi/pinnacleapi-documentation](https://github.com/pinnacleapi/pinnacleapi-documentation)
21. Austerius/Pinnacle-Scraper: Scrapping esport betting ... \- GitHub, accessed March 8, 2026, [https://github.com/Austerius/Pinnacle-Scraper](https://github.com/Austerius/Pinnacle-Scraper)
22. Sports-betting/sportsbetting/bookmakers/pinnacle.py at master, accessed March 8, 2026, [https://github.com/pretrehr/Sports-betting/blob/master/sportsbetting/bookmakers/pinnacle.py](https://github.com/pretrehr/Sports-betting/blob/master/sportsbetting/bookmakers/pinnacle.py)
23. Building a Database for Historical Sports Betting Spreads with the, accessed March 8, 2026, [https://medium.com/@bentodd\_46499/building-a-database-for-historical-sports-betting-spreads-with-the-odds-api-5575fb87d650](https://medium.com/@bentodd_46499/building-a-database-for-historical-sports-betting-spreads-with-the-odds-api-5575fb87d650)
24. NFL Stats \- Apify, accessed March 8, 2026, [https://apify.com/payai/nfl-stats](https://apify.com/payai/nfl-stats)
25. hoopR package \- RDocumentation, accessed March 8, 2026, [https://www.rdocumentation.org/packages/hoopR/versions/2.1.0](https://www.rdocumentation.org/packages/hoopR/versions/2.1.0)
26. hoopR • Data and Tools for Men's Basketball • hoopR, accessed March 8, 2026, [https://hoopr.sportsdataverse.org/](https://hoopr.sportsdataverse.org/)
27. Package index \- hoopR \- SportsDataverse, accessed March 8, 2026, [https://hoopr.sportsdataverse.org/reference/index.html](https://hoopr.sportsdataverse.org/reference/index.html)
28. Load hoopR men's college basketball play-by-play — load\_mbb\_pbp, accessed March 8, 2026, [https://hoopr.sportsdataverse.org/reference/load\_mbb\_pbp.html](https://hoopr.sportsdataverse.org/reference/load_mbb_pbp.html)
29. hoopR documentation \- rdrr.io, accessed March 8, 2026, [https://rdrr.io/cran/hoopR/man/](https://rdrr.io/cran/hoopR/man/)
30. Help for package oddsapiR, accessed March 8, 2026, [https://cran.r-project.org/web/packages/oddsapiR/refman/oddsapiR.html](https://cran.r-project.org/web/packages/oddsapiR/refman/oddsapiR.html)
31. Function reference \- oddsapiR \- SportsDataverse, accessed March 8, 2026, [https://oddsapir.sportsdataverse.org/reference/index.html](https://oddsapir.sportsdataverse.org/reference/index.html)
32. oddsapiR • oddsapiR, accessed March 8, 2026, [https://oddsapir.sportsdataverse.org/](https://oddsapir.sportsdataverse.org/)
33. sports-betting · GitHub Topics, accessed March 8, 2026, [https://github.com/topics/sports-betting](https://github.com/topics/sports-betting)
34. Betting lines from pinnacle for data research \- GitHub, accessed March 8, 2026, [https://github.com/marcoblume/pinnacle.data](https://github.com/marcoblume/pinnacle.data)
35. pinnacle.data/DESCRIPTION at master · marcoblume ... \- GitHub, accessed March 8, 2026, [https://github.com/marcoblume/pinnacle.data/blob/master/DESCRIPTION](https://github.com/marcoblume/pinnacle.data/blob/master/DESCRIPTION)
36. where to get ncaa basketball game by game data? : r/algobetting, accessed March 8, 2026, [https://www.reddit.com/r/algobetting/comments/1rgudb5/where\_to\_get\_ncaa\_basketball\_game\_by\_game\_data/](https://www.reddit.com/r/algobetting/comments/1rgudb5/where_to_get_ncaa_basketball_game_by_game_data/)
37. Free Odds API : r/algobetting \- Reddit, accessed March 8, 2026, [https://www.reddit.com/r/algobetting/comments/1gfu1hx/free\_odds\_api/](https://www.reddit.com/r/algobetting/comments/1gfu1hx/free_odds_api/)
38. NCAA Basketball Odds API, accessed March 8, 2026, [https://the-odds-api.com/sports/ncaab-odds.html](https://the-odds-api.com/sports/ncaab-odds.html)
39. Brad’s Bet Tracker, [https://drive.google.com/open?id=1BoE63NoS21p8ppYLt88M1fwdD68Ha\_4R4zBCVADh2gQ](https://drive.google.com/open?id=1BoE63NoS21p8ppYLt88M1fwdD68Ha_4R4zBCVADh2gQ)
40. Wrong Team Favored in This Friday Game, [https://accounts.google.com/AccountChooser?Email=Msenfleben03%40gmail.com\&continue=https://mail.google.com/mail/\#all/%23thread-f:1685813844231497185|msg-f:1685813844231497185](https://accounts.google.com/AccountChooser?Email=Msenfleben03@gmail.com&continue=https://mail.google.com/mail/#all/%23thread-f:1685813844231497185|msg-f:1685813844231497185)

[image1]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAA8AAAAYCAYAAAAlBadpAAAA0klEQVR4XmNgGPKAA4jLoHg2FtwNxaZAzAjVAwcUaQYJiEBxNRC/AGJ7IJaC4ggofg7E5VD1WMFcID4JxILoEkCwCIhvArEEugQfFB8E4gUMqKZzQ/FuBhyataD4GRBnosnpQjHIOxMZsDg7AIrfALE5kjg/EC+F4m1ALIAkBwftUPwJiA8D8T4GiBcOAXEMFHPCVSMBmH9AeAsDJOqIBhRpVgbiR1BcgyZHELgxQPwKwiA2SQBkG8xmkCuIAiFAfA+IvwLxbyh+AMSpSGpGwdAGAFGtMxd/yqMcAAAAAElFTkSuQmCC>

[image2]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAAXCAYAAAAGAx/kAAAA40lEQVR4XmNgGDEgAIpno2EjIOYA4jIsct5gnWiAF4rVgfgkEL8CYgcgZgViRiA2BeLbUNwMVQeyAC/IA+I/QBwF5YMMmwjEIVBMNKCaQUpAfA+ItwOxABBXM5BoAAyAXLAciD8C8SYGSECDwoks4AnEP4B4KQMFhoBAKBB/BeLLQCyBJkc0MAfiWUBcx4Aa6CQBLSCewwAJZORA50RWhA8oQPEaKA0CyIFuBRXDC9QYILEDwiA2MoAF+lQGSKBjDfgsIH7CAAkHGF4NxFxQeVDaeQPE/4H4NxA/gOJUqPwoGAUAdGQww4GdxsQAAAAASUVORK5CYII=>

[image3]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADUAAAAYCAYAAABa1LWYAAACA0lEQVR4Xu2WMUgcQRSGnwRBg6IiQgoLCcEQUQRBlCBiYSMhRENSJCBcoYUWKigiiGlEEDsLG7UNKQwEAiKIiJYpQ2yCIBZWwRQpBCEB/X/fW2532du93bsTI/vBx+7Nzt3Nm5n3ZkVSUu4Mg+aGzw5YAWcDnr24+ebtUw174RPzgfdxlnsZFDvSp/Ab/AX7YDksg53w2Fy0fgz2NuE4MvAQDsNl8wuszXYLZgL+g+/tMwNbhW/MfHkoIbOYgFb4HbbZZwZJ10THx/ucPIYncEd0BuYlXjAOPXAbvhOdmEKZE91Fdb72MfgTPvK1e+AAPsE/8KtoPoXOQghcqSG4B0dgpfdx3vD/P8J90TRx8wr+Fk2RUAbgpegPJQ3IDYPjynH1F8waT49wGAgDyhUU0yWycL2FF/CHRCxrTDhB7SYTfAXWe3oEExXUlV1z0gXX4QfxFoxS8Ex09ZYkPO/SoPy0wE3RqueugkkTPAinFMfZgokKRZP52a7EXQWfW1shcGDdopPkFIw4xYIlnedUg699WvSloNHd2Cxauinv3ThVkAecM8NxYeXrh7twClaZceGhe2RX4j58nfHJODwTzRvHLdE3AcID91x0v/6Fp+aoPY/COaN4AGek8C3MQc/AA9GtNmnyDPSsUil5DV9KcV+VCI8Y5hHznxb791NSUlL+M64B7KBsgIzsiy0AAAAASUVORK5CYII=>

[image4]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAFkAAAAXCAYAAABgWeOzAAADA0lEQVR4Xu2ZTahNURTHlyRfUUQhAzHwMVAGPqJMSCIfAxnIM5AXGTBAnvJRJspISSmKXr0MKBMpKXkzioQxA/kqMVDKwMD6tde659x9z7nvnt7pvXvOu//69fZd+9zXPf+7917rrCsycTRXmR7FFhiblGmp+GRllcG4pxG0WbmtfFTWpuInlRPGQuWuskaZpdxRNhiMiUFPbbRIeS2JyfOVx8piA+1TrivbJBg+yWBMDEpRv3KrDaclfOCqKTaZv7wm7vezR3mqXFQGLYYYnzJK0Rxlu/FLuSbJB1kuwehvynp/Q0XUqcnPlEvSavKAUZr6jL/SukXYWpxtD5QpRhUUm8zZ+8ri8Uo+J60ml7qSUc/kMTCZwx8w05OCiw/5U6pvMonvibLMQCwsT3z3JLk/xqUmvtnKsPFImmtHRLnzR9kbxbtZO5Uh5YfyUEJyR1QTJDlYrdxUlkgw9qqyW9mlXLFYaQuK4vurcT4Vp5Sh3vwiocLgdTuRQH0rdsJ41aBe//JAkjaR+5tnjHSvhcW3+894IyHbwgsJ9eLKxpXtRRG/vwCspAkjzqRPhp9V3SK2r2/vCznE8/46jucRXz8atkqG2OIvJWRYmNk8Pe7C5MMVItNkP4856GE0oqD/UIAz4W31V5+Es5hsDN0uEtIxSR75D0hIYockOeuJsUOLihIvnQjpxOV15uJ4Ztduh4TV9FuCyZ8Nyp4Zqeu6VcclHHNeCbAruCfIumHKVMgSif++8l6ShxS+ODpxeZ25OO5ztRLl11vloHJUWdc83SJ6MJCndF8DeVcOsjpzcdznaqWeyWOky8p36aw7WNRkum+DhosxvQyfS8d9rlZiBZ2V0JrdGM1lqSyTvf0Zx32uNsLgIxKSDo2cGxZLi9/1qJa84uBnJ0g/cdI/n2rXxyazKrNM9s5cHK/VSk4bjFjFVAVLG1dkq+hK9q4cUNYBYz+T47jPVVZ+M5g7rLxTVliMUo5z+bmyxchSO5P7JXTq6NgNSdgB/G+6cnmduTjucw39B3JW6Arbn2mmAAAAAElFTkSuQmCC>

[image5]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADUAAAAYCAYAAABa1LWYAAAB8UlEQVR4Xu2WMShFYRTHj0SIYlAGgyRKpJSUJAODDCgGogwMJBRJKYvFarBglYFSDCKJjVEsUjKYxGBQiuL/f9+5vXtv77773uU90v3Vr/ved+99vvN955yPSEjIn6FbXXdZD3PgXIx7nZE3008BbIEVaqbzdpR/GRQfpFXwAj7CVpgFM2ADvFWX9DkGm044j2F4BofgsroLC6OPxWYSfsAB/c7AVmCvmgoSWaAaeAlr9TuDpKti5sfPnpTDO3ggZgUWJDXBMG2a4T4cE7N48ZgXk0VFrnG+ewNLXOMO+ONb8AXuiamnuKuQBAykRz2GIzDX8URs+Pc34YmYMrHTBZ/FlEhcOuCbmB/6iYC4UP1iJsUr9dsZOwyE73oFxXLxbVx98BVeic+2+sBd4G5wV7g7np3KB7+gPvXqSSNcg4vibBjJMgjPYbsED8YiDMpNNdwQ0/XsXTCRYnaTD6fhEWyT7wUWqFGUqTt6JfYu2KRjQYhVV0ECZEvnOVXsGp8R809BqX2wUkzrpvxsx+qCPOCswy4oVgc8VJPtgDx0r/VK7IevNT8Zhw9i6sZyG+aZdyIH7pOYfH2H9+qo3g+KtVNMSaYmU5Sp6gcnPQtPxaTalMoMcOzSb8OJ1sEJmO265wWPGNYR658GSeWQkJCQf8QXOl9shz07LEMAAAAASUVORK5CYII=>

[image6]: <data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAGAAAAAdCAYAAABVJGknAAADPElEQVR4Xu2ZS8hNURiGP4lIckm5l0tRBn+US1FEkkv6DYTIRBkwYPIPjBQTlwG5DJSSTChmiqTMyWVABi4TSQYYMKEMfE/rW84+66x9LvvY5+x97LeeVmev/Z+O9a79fXu9RP4/jVVGGVk0LrxQqTNtUCYaXjuUq8ZRZbyyR9ll7FPm2r3DNlbKqJgBaJPyTllknzHgoDHG3ySVAV0rzQB2/X3lpLhFTlvotOuV2lSaAWiv8l3ZHU4kVBnQpSoD+qxmBrDwGIARacrVgLPKR+O3uB/z3nihvFQOiGtKycZUJqUZsF3ZJq4H0AvoCTHlagBaa/xQDgVzG5VvyohRRsUMYPFZWM4GC8RttNWJ+aRyN+CY8VVZEcwtVD4oD40J9dOlUNIAFvOuuH/TepvnTMAT/0pq54DRNodyNYCycsd4rEypn5Ytyk/lnFFGxZ6ATpSrAXOUt8alYG6yuF2PMdwHZVShDeA0yA6H81J7BE+Ja8I06Ul/745rmnJLedQmNLylRi9Ebad0Zi2frFFuYqE/G+uUWcZ0qa+D/dBh4/mAMCQRVQb0jiEJRE2kJFDjYw2436L0DRp1WqJ8Etd8wwbciXrVA7Lm8jzJhTxI8v77y0YouoaDz8lMP5br+0yfkrrcyCK+c2pwjTdEoMEzJjVDWSNuw0Q3zVZxB48v4uIHH0VcE/e/R0VVaADymX4s1/c7vpUBaa/Xs5UTymtxB1Uvfsdpg8Vm9L+NTXBEmalcN5bZXOkVM8Bn+s1y/VYGhPeHuiE1A9jRN5VVBmLkGkbesxHtNLop74VS2kKRZDaLlf+lAXzXM3GRjY9tGJ8om22Oe5DfDGWNcBqUtlAserNYuRcGcI3SHjOAF4+sp/BCKbZQpJpEys1i5dAA3v78iR847Sc/g+8nKGkANZ/dHhrANZLjp9JowMA+AclIuVmsHBoQKvzeUGEPuC21CB8xco3a/0Bcgoz2GwPbAyoDeiy/UIxhpo/CXN9HKVkNmK9cVN6IKzFnxKUFvPVcNhYrF5SV9je89RwXFztcMebZXOmVtlCt1MoAmmen8ocsvjs8bNFw6RWFPH13o7wMqNSmsubyJLuUhIY0sh/6AxEgDh8GPLJFAAAAAElFTkSuQmCC>
