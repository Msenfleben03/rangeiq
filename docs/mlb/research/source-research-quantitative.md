# **Quantitative Methodologies and Predictive Modeling Frameworks in Major League Baseball Wagering Markets**

The contemporary landscape of Major League Baseball wagering represents a sophisticated convergence of classical sabermetrics, high-frequency telemetry, and advanced computational modeling. As the sport has transitioned into the Statcast era, the ability to isolate individual player skill from the inherent noise of environmental variance has become the primary differentiator between recreational speculation and professional-grade origination. This report provides an exhaustive examination of the methodologies employed by industry-leading practitioners, the essential components of predictive models, and the technical resources required to navigate these increasingly efficient markets.

## **Progenitors of the Modern Betting Paradigm**

The evolution of professional baseball betting is inextricably linked to a small cohort of analysts who pioneered the application of economic and psychological principles to sports markets. These experts have transitioned from using rudimentary statistical models to complex, multi-layered systems that account for everything from umpire strike-zone bias to the microscopic fatigue units of a relief pitcher's forearm.

### **The Intellectual Foundation of Rufus Peabody**

Rufus Peabody, a graduate of Yale University, remains one of the most significant figures in the professional betting sphere. His entry into the industry was catalyzed by a senior thesis at Yale that investigated psychological inefficiencies in the performance evaluation of the Major League Baseball betting market. This research focused on how market participants—both bettors and oddsmakers—often fail to accurately price players due to cognitive biases and an overreliance on traditional, results-oriented metrics. Peabody’s subsequent career, which included a tenure at Las Vegas Sports Consultants, was defined by the transition of these academic findings into a functional modeling process.
Peabody’s process is characterized by a "bottom-up" approach, frequently referred to in his work as the "pie" methodology. This involves divvying up the fundamental components of a game—player usage, snap counts in football, or plate appearance distributions in baseball—to form a foundation that informs the final projection. In the context of baseball, this means projecting the exact number of plate appearances each hitter will receive and the specific pitchers they will face. His success in 2009, where a month of betting returns matched his yearly salary, underscored the potency of using modeling to exploit market inefficiencies before they became public knowledge. However, Peabody has frequently noted that the market has become significantly more efficient since the 2010 season. A model that generated massive returns a decade ago would likely be unprofitable today because the data that once provided an edge is now integrated into the market price almost instantly.
\#\#\# Top-Down Modeling and the Unabated Philosophy
Captain Jack Andrews, a co-founder of the Unabated platform, provides a complementary perspective that categorizes the betting landscape into "top-down" and "bottom-up" strategies. A top-down approach does not involve predicting the outcome of the game through statistical modeling; instead, it relies on the information provided by "market-making" sportsbooks. These books, such as Pinnacle or Circa, are known for their high limits and their willingness to move lines based on sharp action. By monitoring these books, a bettor can identify "stale" lines at recreational books that have not yet adjusted to the new market consensus.
Conversely, the "originating" or bottom-up bettor builds their own independent models. Andrews emphasizes that the 162-game MLB schedule is not a monolithic entity but rather three distinct seasons: the early season (April–May), the mid-season (June–July 30), and the late season (July 31–September). Each phase requires different modeling adjustments. In the early season, pitchers often hold an advantage as hitters adjust to live velocity and cooler temperatures. By late summer, fatigue becomes a dominant variable, and roster expansions—though now limited to 28 players—introduce uncertainty that models must account for by adjusting performance baselines.

### **The Contextual Integration of Sean Zerillo**

Sean Zerillo, a prominent analyst for the Action Network, represents the vanguard of contextual modeling. His process, often detailed on the "Payoff Pitch" podcast, is notable for its integration of "soft" variables into a quantitative framework. Zerillo’s models focus heavily on the relationship between starting pitcher metrics—specifically strikeout-to-walk ratios (K-BB%)—and the specific environment of the game, including umpire tendencies and weather conditions. Zerillo’s methodology demonstrates that a model’s value is often found in the "derivatives" or secondary markets, such as strikeout props or first-five-innings lines, where the market is less efficient than the full-game moneyline.

| Expert/Source | Analytical Persona | Primary Methodology | Key Contribution to the Field |
| :---- | :---- | :---- | :---- |
| Rufus Peabody | The Economist | Bottom-Up Modeling | Psychological Inefficiency Analysis |
| Jack Andrews | The Market Analyst | Top-Down Logic | Three-Season Cycle Theory |
| Sean Zerillo | The Contextualist | Derivative Market Focus | Umpire and Weather Integration |
| Jonathan Bales | The GTO Strategist | Expected Edge | Vig-Free Line Comparison |
| Steve Makinen | The Systems Expert | Situational Trends | Travel and Rest Power Ratings |

## **Essential Modeling Components for Starting Pitching**

Starting pitching is the primary anchor for any MLB betting model. The transition from traditional stats like Earned Run Average (ERA) to skill-based metrics is now a prerequisite for professional handicapping. ERA is a backward-looking metric that is heavily influenced by team defense, ballpark factors, and sequencing luck; therefore, it is a poor predictor of future performance.

### **The Dominance of Skill-Interactive ERA (SIERA)**

Skill-Interactive ERA (SIERA) represents the current gold standard for pitcher evaluation in betting models. Unlike Fielding Independent Pitching (FIP), which only considers strikeouts, walks, and home runs, SIERA recognizes that the ability to generate weak contact is a repeatable skill. SIERA’s complexity allows it to model how high-strikeout pitchers also tend to allow lower batting averages on balls in play (BABIP). For example, a pitcher with a high strikeout rate is less likely to have runners on base when they do allow a hit, which SIERA captures more effectively than its predecessors.
In modeling, SIERA is often used as the "true" talent level of a pitcher. If a pitcher’s actual ERA is 4.50 but their SIERA is 3.75, they are a prime candidate for positive regression. Conversely, a pitcher with an ERA of 3.00 and a SIERA of 4.20 is likely "overvalued" by the public, creating an opportunity for the bettor to fade them.

### **The Predictive Power of K-BB%**

While SIERA provides a comprehensive view, many professional originators prioritize strikeout-to-walk ratio (K-BB%) as the single most important skill signal. This metric strips away the variance of the long ball and the luck of balls in play, focusing purely on a pitcher’s ability to dominate the strike zone. A pitcher who strikes out 25% of batters and walks only 5% (a 20% K-BB%) is fundamentally elite. Models that weight K-BB% heavily are less likely to overreact to a game where a pitcher allowed several "bloop" hits that inflated their ERA.

### **Normalizing Performance with xFIP and xERA**

Expected FIP (xFIP) and Expected ERA (xERA) are critical for identifying environmental outliers. xFIP normalizes a pitcher’s home run rate by using the league-average home-run-to-fly-ball (HR/FB) ratio. This is vital when evaluating pitchers who play in "hitter’s havens" like Cincinnati or Colorado, where the stadium's geometry might unfairly penalize their raw stats. xERA, derived from Statcast data, uses the exit velocity and launch angle of every ball put in play to determine what the pitcher’s ERA "should" have been. By comparing xERA to actual ERA, modelers can identify pitchers who are benefitting from elite defense or, conversely, being punished by a poor one.

## **Offensive Modeling and the Platoon Advantage**

Predicting offensive output requires a shift from team-level batting averages to player-level expected weighted on-base average (xwOBA) and weighted runs created plus (wRC+). These metrics are significantly more stable and predictive because they account for the quality of contact and the specific league and park environment.

### **The Platoon Edge and Sample Size Regression**

The advantage of a left-handed hitter facing a right-handed pitcher is one of the most consistent trends in baseball. On average, this "platoon advantage" provides an 8% boost to offensive performance. However, modelers must be careful when dealing with "split" data. A player may have an incredible.400 average against lefties over 50 plate appearances, but this is a statistically insignificant sample. Professional models use Bayesian regression to pull these small-sample splits back toward the player's overall career mean, ensuring the model doesn't overvalue a temporary hot streak.
\#\#\# Identifying Offensive Inefficiencies through xwOBA
xwOBA is the offensive counterpart to xERA. By analyzing the launch angle and exit velocity of a hitter’s batted balls, modelers can identify players who are making "hard contact" but aren't seeing results due to high-quality defensive positioning or park effects. A team with a high aggregate xwOBA that is currently struggling to score runs is a "buy-low" candidate for "Over" bettors, as run production is likely to regress toward their contact quality.

## **The Critical Influence of the Bullpen and Relief Fatigue**

As the role of the starting pitcher has diminished—with relief pitchers now accounting for a record number of appearances—modeling the bullpen has become a primary driver of betting value. The challenge for the bettor is that bullpen performance is highly volatile and subject to extreme fatigue effects.

### **Quantifying the "Toxin" of Pitcher Fatigue**

Professional modeling treats every pitch thrown as a fatigue-inducing "toxin" administered to the pitcher's arm. Research using Bayesian hierarchical models has established a clear dose-response relationship between pitch count and future effectiveness. When a reliever throws more than 15 pitches, they suffer small, short-term decreases in velocity. Once they cross the 20-pitch threshold, the dip in performance is amplified.
Modelers must track the "rolling" workload of a bullpen over a 3-to-5-day window. If several key relievers have thrown over 30 pitches in the last three days (PC L3) and have zero days of rest, they are either unavailable for the upcoming game or will perform significantly worse if forced to pitch.

| Fatigue Metric | Threshold for Concern | Strategic Adjustment |
| :---- | :---- | :---- |
| PC L3 (Pitch Count Last 3 Days) | \>30-40 pitches | Fade the team in full-game moneylines |
| Consecutive Days Worked | 2+ days | High risk of velocity loss and command issues |
| Days of Rest Since Last App | 0 days | Multiplier applied to expected runs allowed |
| High-Leverage Innings | Any in last 2 days | Likely unavailability of the closer/setup man |

\#\#\# The Cascading Effect of the "Times Through the Order" Penalty
The "Times Through the Order Penalty" (TTOP) describes the phenomenon where a starting pitcher’s effectiveness drops significantly each time they face the same hitter in a game. OPS-against typically climbs from.705 the first time through to.771 the third time through.
This penalty has forced managers to pull starters earlier, which in turn places a higher burden on the bullpen. A model that correctly identifies a starter likely to struggle the second or third time through the order can predict when a "gassed" bullpen will be forced into the game. This creates a massive edge in the "Over" market and in late-inning live betting.

## **Contextual Variables: Parks, Weather, and Umpires**

MLB is unique in that the dimensions and atmosphere of the venue change with every game. These variables are not merely "noise"; they are fundamental drivers of run expectancy.

### **Park Factors and Ballpark Pal’s Machine Learning**

Ballpark Pal uses a machine learning model trained on over 1 million batted balls and 20,000 games to generate park factors. These factors are not static; they are "hitter-level specific," meaning the model analyzes how a specific stadium’s dimensions (e.g., the "Green Monster" in Boston) interact with a specific hitter’s spray chart. This level of granularity is essential for predicting home run props. A stadium with a \+30% boost for home runs is expected to produce roughly 0.67 more home runs than a typical MLB game—an effect that must be factored into the model’s run distribution.

### **Atmospheric Physics and the "Wind Out" Edge**

Temperature and wind direction are highly correlated with run scoring. Hot air is less dense, allowing the ball to travel further, while high humidity actually reduces air density further (contrary to popular belief). The "wind out" scenario at Wrigley Field is the most famous example of this; a strong breeze blowing toward the outfield can move a total from 8.5 to 11.5 within hours. Sharp bettors monitor these conditions and place bets before the market fully incorporates the weather data.

### **The Human Element: Umpire Bias and Blind Spots**

The home plate umpire's strike zone remains a significant source of inefficiency. A 2019 Boston University study found that umpires made over 34,000 incorrect calls in a single season.

1. **Two-Strike Bias:** Umpires are twice as likely to call a true "ball" as a strike when the hitter has two strikes, unfairly penalizing batters and helping "Under" bettors.
2. **Strike Zone Blind Spots:** There is a persistent blind spot at the top of the strike zone, where pitches are called incorrectly nearly 27% of the time.
3. **The "Big Zone" Edge:** Some umpires have a "liberal" strike zone that can be 26% larger than the smallest zones. A pitcher with elite command who faces a large-zone umpire is a prime candidate for "Over" strikeouts or "Under" total runs.

| Umpire Metric | Impact on Scoring | Betting Lean |
| :---- | :---- | :---- |
| High BCR (Bad Call Ratio) | Increased variance and walks | Over |
| Large kzone50 Area | Advantage to pitchers on the corners | Under / Pitcher Strikeout Over |
| Two-Strike Bias | Suppressed batting averages | Under |
| Small kzone50 Area | Forces pitchers into the heart of the zone | Over |

## **Technical Implementation: Data Acquisition and Model Verification**

Building a profitable MLB model requires a robust technical pipeline. The era of manual entry is over; automation via Python and the use of specialized APIs is now standard.

### **Accumulating Data with pybaseball and Statcast**

The pybaseball library is the foundational tool for most independent originators. It allows for the direct scraping of FanGraphs, Baseball Reference, and Baseball Savant into Python.

* **Statcast Queries:** The statcast() function retrieves pitch-level data, including exit velocity and launch angle, which is essential for calculating xERA and xwOBA.
* **Historical Results:** schedule\_and\_record() provides game-by-game results for any team in history, which is vital for backtesting.
* **Standings and Trends:** The standings() function offers a snapshot of league-wide trends at any point in the season.

For those seeking real-time odds data, "The Odds API" and "MLB-StatsAPI" provide structured JSON feeds that can be integrated into automated betting scripts.

### **Verification and the Trap of Data Leakage**

The most common error in model building is "data leakage"—using future information to predict a past event during the backtesting phase. For example, if a model uses a player's season-ending 2024 WAR to predict a game in May 2024, it is cheating. Professional originators use "rolling" totals and cumsum formulas to ensure that only the data available *before* the game is used in the prediction.

### **Performance Metrics: Brier Score and CLV**

A model is verified through its Brier score and its ability to generate Closing Line Value (CLV).

* **Brier Score:** This measures the accuracy of the model's win probabilities. A score of 0.2452 (as seen in some Random Forest models) is considered competitive with bookmaker accuracy.
* **Closing Line Value (CLV):** If you bet a team at \-120 and the line closes at \-140, you have generated significant CLV. Over thousands of games, CLV is a more reliable indicator of profitability than actual ROI, as it proves the model is consistently beating the market's final consensus.

## **The Psychology of the Market: Anchoring and DFS Spillovers**

Jonathan Bales, co-founder of Fantasy Labs and co-CEO of Gambly, has written extensively on the cognitive biases that plague even sophisticated bettors. Understanding these is critical for identifying when a line is "inflated" by public sentiment.

### **Anchoring and the Starting Point**

Bales identifies "Anchoring" as a major hurdle in betting. This is the tendency to rely too heavily on the first piece of information received—such as a pitcher's high-profile debut or a team's preseason win total—even when new data suggests that baseline is wrong. Models help overcome this by weighing all pieces of information objectively through a regression framework.

### **The Gambler's Fallacy and Regression to the Mean**

Many bettors believe a team is "due" to win after a losing streak, which Bales identifies as the "Gambler's Fallacy". In a sport with 162 games, variance is extreme. A model that understands a team's "long-term ROI" and true talent level can capitalize on these market overreactions to short-term streaks.

## **Beginner Steps for Research and Model Building**

For the aspiring bettor, the transition from a fan to a quantitative analyst should be incremental. The goal is to build a process that is "auditable and strong".

### **Step 1: Market Selection and Specialization**

Do not attempt to model every game and every market. Narrow your focus to a specific niche where the house is vulnerable.

* **First 5 Innings (F5):** This is the ideal starting point for a model. It isolates the starters and significantly reduces the noise introduced by bullpen fatigue and manager decisions.
* **Player Strikeout Props:** These are often priced based on season averages. A model that incorporates the specific opponent's strikeout rate (K%) and the umpire's strike zone can find significant edges.

### **Step 2: The Spreadsheet Foundation (Excel/Google Sheets)**

Before writing Python code, build a simple model in a spreadsheet. This forces you to understand the mathematical relationships between the variables.

1. **The Poisson Distribution:** Baseball scoring can be modeled using a Poisson distribution because runs are discrete, independent events.
2. **Calculating Lambda (\\lambda):** Your model’s goal is to find the "expected runs" (\\lambda) for each team. Start with league-average runs and adjust based on the pitcher's SIERA and the team's wRC+.
3. **Win Probability Matrix:** Use the Poisson probabilities to build a matrix of all possible scores (0-0, 1-0, 0-1, etc.). The sum of all cells where Team A's score is greater than Team B's is your win probability.

### **Step 3: Integrating Third-Party Tools**

Leverage existing platforms to verify your findings and streamline your workflow.

* **Rithmm:** Allows users to build personalized, data-driven models using intuitive sliders. It pulls in Statcast data automatically, making it an excellent bridge between spreadsheet modeling and advanced automation.
* **Outlier:** Provides a comprehensive breakdown of bullpen health and relief pitcher usage, which is often the hardest data for a beginner to collect manually.
* **BettorEdge:** A peer-to-peer betting platform that allows you to bet against other users without paying the "vig" or house edge found at traditional sportsbooks.

## **Conclusion: The Path to Sustainable Edge**

Sustainable profitability in the Major League Baseball betting market is not found in "picking winners" but in the accurate estimation of probabilities. The professional bettor acts as a quantitative auditor, identifying instances where the market's price deviates from the statistical reality of the game. This requires a commitment to a numbers-first approach that prioritizes skill-based metrics over traditional results, quantifies the environmental impact of ballparks and weather, and rigorously tracks bullpen fatigue and umpire bias.
The integration of tools like pybaseball and the implementation of Poisson-based distributions provide the technical foundation, while an understanding of cognitive biases and market efficiency prevents the analyst from falling into the traps of public sentiment. In a sport defined by the "grind" of a 162-game season, the ability to maintain a consistent, automated, and objective modeling process is the only proven path to a long-term mathematical edge. As the market continues to evolve toward total efficiency, the value will increasingly reside in the ability to process granular, real-time data—such as reliever pitch counts and umpire BCR—faster and more accurately than the consensus.

#### **Works cited**

1\. Rufus Peabody Biography | Booking Info for Speaking Engagements, https://www.allamericanspeakers.com/celebritytalentbios/Rufus+Peabody/452580 2\. Rufus Peabody | Keynote Speaker | AAE Speakers Bureau, https://www.aaespeakers.com/keynote-speakers/rufus-peabody 3\. Professional Sports Betting: From $450 Apartment To $1M Run, https://www.thelines.com/professional-sports-betting-journey-bettor-rufus-peabody-2022/ 4\. Pie For Dinner: Rufus Peabody's NFL Player Prop Process \- Unabated, https://unabated.com/articles/pie-for-dinner-rufus-peabodys-nfl-player-prop-process 5\. Learn The Basics Of Bottom-Up Betting, Or Originating \- Unabated, https://unabated.com/articles/learn-the-basics-of-bottom-up-betting-or-originating 6\. How Does Gambly Calculate a Bet's Edge? \- Gambly, https://dev.gambly.com/blog/how-does-gambly-calculate-a-bets-edge 7\. How Does Gambly Calculate a Bet's Edge?, https://www.gambly.com/blog/how-does-gambly-calculate-a-bets-edge 8\. MLB Betting Is Three Seasons \- Unabated, https://unabated.com/articles/mlb-betting-is-three-seasons 9\. Payoff Pitch Podcast \- Action Network, https://www.actionnetwork.com/podcasts/payoff-pitch 10\. Baseball Odds, News, Analysis & MLB Betting Picks \- Action Network, https://www.actionnetwork.com/mlb 11\. Professional Sports Bettor REVEALS How He Made an MLB Betting, https://www.youtube.com/watch?v=bm9MraKCB8w 12\. Sean Zerillo \- Expert Sports Betting & DFS “Taeks”, https://taeks.com/experts/sean-zerillo 13\. MLB Betting: How to Use Pitching Matchups to Your Advantage, https://www.bettoredge.com/post/mlb-betting-how-to-use-pitching-matchups-to-your-advantage 14\. Sabermetrics Library \- SIERA, https://library.fangraphs.com/pitching/siera/ 15\. MLB Betting Model (2025 Guide): Build, Price & Validate MLB ..., https://www.underdogchance.com/mlb-betting-model/ 16\. Fun fact: The best predictor of future ERA is not FIP, xFIP, SIERA or, https://www.reddit.com/r/baseball/comments/zngku4/fun\_fact\_the\_best\_predictor\_of\_future\_era\_is\_not/ 17\. MLB Betting Model: How to Make Smarter Baseball Predictions, https://www.rithmm.com/post/how-to-build-an-mlb-betting-model 18\. Modeling the Outcome of MLB Games Using R | by Jacksonroberts, https://medium.com/@jacksonroberts23/modeling-the-outcome-of-mlb-games-using-r-5fa163f73690 19\. 5 bullpen usage trends to know \- MLB.com, https://www.mlb.com/news/bullpen-use-has-changed-greatly-over-time-c216982016 20\. Out of gas: quantifying fatigue in MLB relievers \- IDEAS/RePEc, https://ideas.repec.org/a/bpj/jqsprt/v14y2018i2p57-64n4.html 21\. How to Use Bullpen Data in Your MLB Betting Strategy, https://help.outlier.bet/en/articles/11906728-how-to-use-bullpen-data-in-your-mlb-betting-strategy 22\. How to Use Bullpen Fatigue in MLB Betting, https://www.coresportsbetting.com/how-to-use-bullpen-fatigue-in-mlb-betting/ 23\. Third Time Through the Order Penalty | Glossary \- MLB.com, https://www.mlb.com/glossary/miscellaneous/third-time-through-the-order-penalty 24\. Managers on the Third Time Through the Order | FanGraphs Baseball, https://blogs.fangraphs.com/managers-on-the-third-time-through-the-order/ 25\. MLB Betting Guide \- VSiN, https://vsin.com/mlb-guide/ 26\. MLB Totals Betting Guide: How Over/Under Lines Work \- BettorEdge, https://www.bettoredge.com/post/beginner-s-guide-to-betting-mlb-totals-how-over-under-lines-are-set 27\. MLB Umpires Missed 34294 Pitch Calls in 2018\. Time for Robo-umps?, https://www.bu.edu/articles/2019/mlb-umpires-strike-zone-accuracy/ 28\. (PDF) Approximating strike zone size and shape for baseball, https://www.researchgate.net/publication/339266150\_Approximating\_strike\_zone\_size\_and\_shape\_for\_baseball\_umpires\_under\_different\_conditions 29\. How to handicap MLB umpire betting stats \- Covers.com, https://www.covers.com/mlb/how-to-handicap-mlb-umpire-betting-stats 30\. jldbc/pybaseball: Pull current and historical baseball ... \- GitHub, https://github.com/jldbc/pybaseball 31\. schorrm/pybaseball: I'm maintaining the original repo now ... \- GitHub, https://github.com/schorrm/pybaseball 32\. MLB Statcast Search \- Baseball Savant, https://baseballsavant.mlb.com/statcast\_search 33\. MLB Odds API, https://the-odds-api.com/sports-odds-data/mlb-odds.html 34\. Top 10 Best Sports Betting Algorithms Software of 2026 \- Gitnux, https://gitnux.org/best/sports-betting-algorithms-software/ 35\. Accessing MLB statistics using python | by Adrien Peltzer \- Medium, https://medium.com/@adrienpeltzer\_17089/accessing-mlb-statistics-using-python-e5b539985a96 36\. Forrest31/Baseball-Betting-Model: Predictive machine ... \- GitHub, https://github.com/Forrest31/Baseball-Betting-Model 37\. Sports Prediction and Betting Model \- GitHub, https://github.com/Ali-m89/Sports\_Prediction\_and\_Betting\_Model 38\. How are you testing and backtesting your betting models? \- Reddit, https://www.reddit.com/r/algobetting/comments/1m518va/how\_are\_you\_testing\_and\_backtesting\_your\_betting/ 39\. How to Build a Sports Betting Model in Excel | OddsJam, https://oddsjam.com/betting-education/how-to-build-a-sports-betting-model-in-excel 40\. Bales: How to Overcome & Exploit Endowment Effect and Gambler's, https://www.actionnetwork.com/education/jonathan-bales-endowment-effect-gamblers-fallacy-betting-fantasy-sports 41\. Bales: How to Overcome and Exploit Anchoring in Betting, Fantasy, https://www.actionnetwork.com/education/jonathan-bales-how-to-deal-with-anchoring-in-sports-betting-and-daily-fantasy-sports 42\. An Intro to Quantitative Modeling for Sports Bettors (in Excel) \- Medium, https://medium.com/@lloyddanzig/an-intro-to-quantitative-modeling-for-sports-bettors-in-excel-6976e1ceaf0f 43\. Regression-Modeling-using-MLB-Statistics/README.md at main, https://github.com/clayton8090/Regression-Modeling-using-MLB-Statistics/blob/main/README.md
