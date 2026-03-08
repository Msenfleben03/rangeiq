# Poisson regression: from counting theory to baseball betting edge

Poisson regression is the foundational statistical tool for modeling count data — discrete, non-negative events like runs scored, strikeouts, or customer arrivals — and it has become a cornerstone of both sabermetric analysis and quantitative sports betting. **The single most important thing to understand is that a Poisson model treats each team's run-scoring as an independent random process governed by a rate parameter λ**, then uses the resulting probability distributions to price every major MLB bet type: totals, moneylines, run lines, and first-five-innings markets. While the model is demonstrably imperfect for baseball (run-scoring variance is roughly **2.2× the mean**, violating Poisson's core assumption), it remains the industry-standard starting framework because of its simplicity, interpretability, and surprisingly serviceable approximation of real outcomes. This report covers the statistical foundations for beginners, documents how MLB front offices deploy Poisson-family models, and provides a detailed technical guide to building, validating, and profitably applying Poisson-based betting models.

---

## Part I: The statistical foundations

### What the Poisson distribution actually describes

The Poisson distribution answers a deceptively simple question: if events happen at an average rate of λ per interval, what is the probability of observing exactly *k* events? It applies whenever you are counting discrete occurrences — emails per hour, car accidents per month, typos per page, or runs per baseball game.

The probability mass function is:

**P(Y = k) = e^(−λ) · λ^k / k!**

Each component has an intuitive role. λ (lambda) is the average rate — the single parameter that defines the entire distribution. The term e^(−λ) acts as a normalizing discount that ensures all probabilities sum to one. The numerator λ^k captures how the likelihood of *k* events grows with the rate, while *k!* in the denominator corrects for the number of orderings among identical events. The distribution is defined only for non-negative integers (0, 1, 2, 3, ...) and is right-skewed when λ is small, becoming approximately bell-shaped when λ exceeds about 20.

A concrete example clarifies the mechanics. If an intersection averages **λ = 3 accidents per month**, then P(exactly 0) = 5.0%, P(1) = 14.9%, P(2) = 22.4%, P(3) = 22.4%, P(4) = 16.8%, and P(5) = 10.1%. The classic historical example is Ladislaus Bortkiewicz's 1898 study of Prussian cavalry deaths by horse kick, which found λ = 0.61 deaths per corps per year — and the Poisson fit was remarkably accurate.

The critical property of the Poisson distribution is **equidispersion**: the mean and the variance are both equal to λ. This elegant constraint makes the model tractable but also creates its biggest practical limitation, as we will see.

### Why ordinary regression breaks down for count data

Count data violates nearly every assumption of ordinary least squares regression. Counts are non-negative integers, often right-skewed, and their variance scales with their mean — three properties that shatter OLS's requirements of continuous outcomes, normally distributed residuals, and constant variance (homoscedasticity).

The most damaging failure is that a linear model will inevitably predict negative counts for some covariate values. If your model estimates *runs = 8 − 0.5 × (pitcher quality score)*, then any pitcher with a quality score above 16 yields a nonsensical negative run prediction. The common workaround of log-transforming the response variable creates its own problem: log(0) is undefined, so every zero-count observation is lost. As UCLA's Statistical Consulting Group notes, this approach produces "loss of data due to undefined values and biased estimates."

Poisson regression solves these problems through its **log link function**:

**log(λ) = β₀ + β₁X₁ + β₂X₂ + ... + βₖXₖ**

Or equivalently: **λ = exp(β₀ + β₁X₁ + ... + βₖXₖ)**

The exponential function guarantees that predicted counts are always positive, regardless of covariate values. This is not just a mathematical convenience — it arises naturally from the Poisson distribution's membership in the exponential family of distributions, making the log link the "canonical" choice.

### Interpreting lambda and the multiplicative logic of coefficients

Lambda (λ) is the expected count — the model's prediction for how many events will occur given a specific set of predictor values. In a baseball context, λ might represent the expected runs a team will score against a particular pitcher in a particular park.

The coefficients in Poisson regression have a **multiplicative interpretation**, fundamentally different from the additive effects in OLS. When β₁ = 0.3, a one-unit increase in X₁ multiplies the expected count by exp(0.3) ≈ **1.35 — a 35% increase**. When β₁ = −0.5, the multiplier is exp(−0.5) ≈ 0.61, representing a 39% decrease. When β₁ = 0.693, the expected count exactly doubles. These multiplicative effects are reported as **incidence rate ratios (IRRs)**: IRR = exp(β).

The model learns its parameters through **maximum likelihood estimation (MLE)**, which asks: what coefficient values make the observed data most probable? Unlike OLS, which has a closed-form solution via the normal equations, the Poisson log-likelihood must be maximized numerically using iteratively reweighted least squares (IRLS). The algorithm starts with initial guesses, computes predicted counts, assigns weights proportional to each observation's predicted mean, solves a weighted regression, and iterates until convergence — typically in 3–6 cycles. The log-likelihood is convex, guaranteeing a unique global maximum.

### Overdispersion is the Achilles' heel

The Poisson model's most restrictive assumption — that variance equals the mean — is violated in the vast majority of real-world datasets, including baseball. **Overdispersion** occurs when the observed variance exceeds the mean, and it is detected by computing the ratio of residual deviance to degrees of freedom (or the Pearson chi-squared statistic divided by df). A ratio near 1 confirms equidispersion; values substantially above 1 signal trouble.

Ignoring overdispersion does not bias coefficient estimates, but it **underestimates standard errors**, inflates test statistics, and produces false positives — you may conclude a predictor is significant when it is not. Two primary remedies exist. **Quasi-Poisson regression** retains the Poisson structure but estimates a dispersion parameter φ that inflates standard errors by √φ. **Negative Binomial regression** adds a parameter θ that allows variance to exceed the mean: Var(Y) = μ + μ²/θ. As θ approaches infinity, the NB converges to Poisson. For data with excessive zeros beyond what either model predicts, **zero-inflated Poisson (ZIP)** or **zero-inflated negative binomial (ZINB)** models are appropriate.

The practical decision tree is straightforward: if variance ≈ mean, use Poisson; if variance >> mean, use Negative Binomial; if excess zeros are present, use zero-inflated variants; if observations are clustered or correlated, use mixed-effects models.

---

## Part II: How MLB front offices use Poisson models

### Run scoring follows a Poisson-like process, but not perfectly

The intuitive case for Poisson in baseball is compelling: runs are discrete, non-negative, relatively rare events that accumulate over a fixed interval (9 innings). But the empirical fit is systematically flawed. Analysis of **188,189 MLB games from 1901–2015** by Min-Yi Shen found a mean of 4.44 runs per team per game with a variance of **9.71 — roughly 2.19× the mean**. Sean Dolinar's analysis of 2011–2013 American League data found 0.483 runs per half-inning with variance 1.014, confirming the pattern even at the inning level. The Poisson model bunches too much probability around the mean, underestimates both shutouts and blowouts, and overestimates moderate-scoring games.

The **negative binomial distribution** with parameters r = 3.741 and p = 0.542 provides a far superior fit to historical MLB run distributions. Other alternatives that researchers have explored include the three-parameter Weibull distribution (which proved theoretically critical for deriving the Pythagorean winning percentage formula), the Tango Distribution developed by sabermetrician Tom Tango (which models runs per inning and convolves nine innings to produce game-level distributions), and the Conway-Maxwell-Poisson distribution, which adds a flexible dispersion parameter. A 2024 paper by Florez, Guindani, and Vannucci in the *Journal of Quantitative Analysis in Sports* demonstrated that the Bayesian bivariate Conway-Maxwell-Poisson model outperforms both standard Poisson and negative binomial for MLB game scores.

### The Pythagorean connection and win probability

The most elegant theoretical application of Poisson-family distributions in baseball is the derivation of the **Pythagorean winning percentage formula**: Win% ≈ RS^γ / (RS^γ + RA^γ). Steven J. Miller of Williams College proved in a 2007 *Chance Magazine* paper that if runs scored and runs allowed follow independent Weibull distributions with the same shape parameter γ, the Pythagorean formula emerges directly, with the optimal exponent for baseball being approximately **1.83** (close to Bill James's original guess of 2).

If we model each team's game-level scoring as Poisson, the **run differential follows a Skellam distribution** — the distribution of the difference of two independent Poisson random variables, first described by J.G. Skellam in 1946. This directly yields win probabilities: P(Team A wins) equals the probability that the Skellam variable exceeds zero. Jack Werner's Poisson Maximum Likelihood (PML) model at Model284.com operationalized this approach, assigning each MLB team an offensive score and each pitcher a defensive score, then modeling runs as Poisson(team offense × pitcher defense). Testing against 1998–2016 data revealed the model was useful for **ranking and evaluation** but somewhat overconfident in direct prediction — a consequence of the overdispersion problem.

### Rare events are where Poisson truly excels in baseball

The strongest validated application of Poisson processes in baseball is modeling genuinely rare events. Huber and Glen published a 2007 paper in the *Journal of Statistics Education* confirming that no-hitters (206 from 1901–2004), hitting for the cycle (225 occurrences), and triple plays (511 occurrences) all follow Poisson processes with memoryless inter-arrival times. A follow-up paper by Huber and Sturdivant in the *Annals of Applied Statistics* (2010) modeled games with 20+ runs as a Poisson process, finding era-specific rates: roughly one per 400 games in the "Lively Ball" era versus one per 650 games in the Integration era.

SABR's simulation of perfect games and no-hitters used Poisson process assumptions to generate 2,000 alternate baseball histories, finding an average of **15.9 perfect games per history** (actual: 17) and 243 no-hitters (actual: 250) — both within one standard deviation of the model predictions. For rare counting events like hit-by-pitches, wild pitches, and balks, Poisson regression remains the appropriate and standard tool.

### What Statcast and WAR calculations actually use

Neither Statcast's expected statistics (xBA, xwOBA, xSLG) nor WAR component calculations use Poisson distributions directly. Statcast metrics are built on k-nearest-neighbor algorithms applied to exit velocity, launch angle, and sprint speed data — entirely empirical and machine-learning-based. WAR calculations rely on linear weights (wOBA, wRAA) derived from the empirical run values of offensive events. FIP, the fielding-independent pitching metric used in fWAR, treats strikeouts, walks, HBP, and home runs as rate statistics but combines them through a linear formula, not a distributional model. The Poisson framework connects to WAR indirectly through the Pythagorean expectation, which validates the approximately **10 runs = 1 win** conversion factor that WAR relies on.

---

## Part III: Poisson models for MLB sports betting

### Building the core model: two independent Poisson processes

The foundational betting model treats each team's run scoring as an independent Poisson random variable: **Team A ~ Poisson(λ_A) and Team B ~ Poisson(λ_B)**. The estimation of λ for each team follows an attack-strength × defense-weakness framework adapted from the Dixon-Coles methodology originally developed for soccer.

The estimation procedure works as follows. First, compute league-average runs per game (split by home and away). Then calculate each team's **attack strength** (team's average runs scored ÷ league average) and the opposing pitcher or team's **defense strength** (average runs allowed ÷ league average). Finally, λ = attack strength × defense strength × league average. For example, if the MLB league average is 4.5 runs per game and Team A scores 5.0 R/G (attack strength = 1.111) while facing a pitcher whose team allows 5.2 R/G (defense strength = 1.156), then λ_A = 1.111 × 1.156 × 4.5 ≈ **5.78 expected runs**.

More sophisticated models, like Werner's PML approach, assign each team an offensive score and each pitcher a separate defensive score, then fit all parameters simultaneously via maximum likelihood across an entire season's worth of games. The 2024 Carnegie Mellon statistics capstone team built a Bayesian multilevel Poisson model with fixed effects for home/away and FIP, plus random effects for teams and pitchers, achieving **56.13% accuracy** on first-inning scoring predictions.

### Pricing over/unders through the Poisson probability table

The sum of two independent Poisson random variables is itself Poisson: if λ_A = 4.2 and λ_B = 3.8, then total runs follow Poisson(λ_total = 8.0). To price an over/under of 8.5, calculate P(total ≥ 9) = 1 − P(total ≤ 8).

Using the Poisson CDF with λ = 8.0: P(0) through P(8) sum to approximately **0.593**, so P(Over 8.5) ≈ 40.7% and P(Under 8.5) ≈ 59.3%. The fair odds would be Over 8.5 at roughly +145 and Under 8.5 at −145. If a sportsbook offers Over 8.5 at −110 (implying 52.4%), the Under represents substantial value — your model gives approximately **7 percentage points of edge**.

A practical example discussed on the SBR Handicapper Think Tank illustrates the workflow: a bettor projected a game total at 5.91 runs, with the book offering Over/Under 6.5 at −110. The Poisson calculation showed a 62% chance of staying under, equivalent to fair odds of −164. The bettor's threshold required a 5% minimum edge (equivalent to 67% probability or −133) before placing the wager.

### Converting Poisson probabilities to moneyline odds

The score matrix method is the workhorse calculation for moneyline pricing. Given λ_A and λ_B, construct a matrix where each cell (i, j) contains P(A scores i) × P(B scores j), using the independence assumption. Then sum all cells where i > j to get P(A wins), all cells where j > i for P(B wins), and the diagonal for P(tie).

Since baseball has no ties (extra innings resolve them), the tie probability must be redistributed: **P(A wins, adjusted) = P(A wins) / [P(A wins) + P(B wins)]**.

Working through the example with λ_A = 4.2 and λ_B = 3.8 (truncating the matrix at 10 runs per side):

- P(A wins) ≈ 0.432
- P(B wins) ≈ 0.366
- P(Tie) ≈ 0.203
- **P(A wins, adjusted) = 0.432 / 0.798 ≈ 54.1%**

This translates to a fair moneyline of approximately **−118 for Team A** and +118 for Team B. A 1994 paper in *The American Statistician* formally proved the elegant result that ∂P(λ, μ)/∂λ — the rate of change of win probability with respect to scoring rate — equals exactly the probability of a tie.

### Run line pricing: why ±1.5 is its own market

The MLB run line is fixed at ±1.5 (unlike the variable point spreads in football and basketball), and approximately **28–30% of MLB games are decided by exactly one run**, making the 1.5-run threshold extremely consequential. Using the same score matrix, P(Team A wins by 2+) is the sum of all cells where i − j ≥ 2.

For our λ_A = 4.2, λ_B = 3.8 example, P(A wins by 2+) ≈ **30.7%**, translating to fair odds of approximately +226. This is dramatically different from the 54.1% moneyline probability — a crucial distinction that casual bettors often misunderstand. Historical data confirms that underdogs cover the +1.5 run line approximately **56–61% of the time** (61% at home, 56% on the road), which is why run line underdogs are priced as heavy favorites with juice ranging from −170 to −200.

An important strategic insight: when the game total is higher, multi-run victories become more probable, making the −1.5 run line more attractive for favorites. Road favorites have an additional structural advantage — they bat in the top of the ninth even when ahead, creating more opportunities to extend the margin.

### First-five-innings betting isolates pitcher quality

F5 betting — settling wagers based on the score after five complete innings — is a favorite tool of sharp bettors because it eliminates bullpen variance, the least predictable element of a baseball game. As the Betstamp MLB betting guide notes: "Your edge is maximized during the innings when those elite (or notably weak) starters are on the mound, before unpredictable bullpens enter the mix."

F5 Poisson models use pitcher-specific λ values calculated over 5 innings rather than 9. A simple conversion takes the full-game λ and multiplies by 5/9, adjusted upward slightly for the well-documented first-inning scoring bump (first innings average roughly **0.6 runs**, higher than the 0.48 overall per-inning average). F5 totals are typically set around 4.5 versus full-game totals of 7.5–8.5, and the F5 run line is ±0.5 rather than ±1.5.

The F5 market exploits times-through-the-order data particularly well. Many starters dominate the first two times through the lineup but deteriorate sharply the third time. Outlier.bet documented that Julio Urías allowed opposing batters to hit .191 the first time through and .165 the second time, but **.279 the third time** — making F5 under bets on his starts far more reliable than full-game unders. Sharp bettors target elite starters with unreliable bullpens for F5 unders, and fade teams with weak early-inning offenses (the 2025 Pittsburgh Pirates averaged just 1.72 F5 runs).

### Starting pitcher quality as the primary model input

The starting pitcher is the single most important variable in a Poisson betting model. The key metrics used to estimate pitcher-specific λ values, ranked by predictive power:

- **SIERA** (Skill-Interactive ERA): The most complex and most predictive metric, incorporating ground ball/fly ball/popup splits and K/BB interactions
- **xFIP** (Expected FIP): FIP with a normalized home run to fly ball rate of ~10.5%, removing HR luck
- **FIP** (Fielding Independent Pitching): ((13×HR + 3×(BB+HBP) − 2×K) / IP) + constant (~3.10). A better predictor of future ERA than ERA itself
- **xERA**: Statcast-derived expected ERA using exit velocity and launch angle
- **ERA**: Descriptive of what happened but includes substantial noise from defense and sequencing luck

The conversion from pitcher metrics to λ is straightforward. A pitcher with a **3.50 FIP** allows approximately 3.50 earned runs per 9 innings, or 0.389 runs per inning. Over 5 innings (for F5 modeling), λ ≈ 1.94 runs allowed. Werner's PML model demonstrated the magnitude of pitcher effects vividly: in 2016, the White Sox allowed an average of **6.0 runs in James Shields starts versus 3.1 runs in José Quintana starts** — a nearly 2:1 ratio from a single roster.

### Park factors and weather create exploitable adjustments

Park factors quantify how much a ballpark amplifies or suppresses scoring relative to league average (100 = neutral). **Coors Field carries a park factor of approximately 125–138**, meaning it produces 25–38% more runs than average. At 5,280 feet of elevation, reduced air density causes balls to travel farther and breaking pitches to break less — a curveball that moves 18 inches at Fenway only breaks 14–15 inches at Coors. At the other extreme, T-Mobile Park in Seattle (park factor ~91) and Petco Park in San Diego suppress scoring significantly.

The adjustment is multiplicative: if λ_base = 4.0 and the park factor is 125, then λ_adjusted = 4.0 × 1.25 = **5.0**. This single adjustment can swing a total line by a full run or more.

Temperature effects are meaningful and well-documented. Scoring averages climb from approximately **4.2 R/G below 60°F to 4.7+ R/G above 80°F**. A Dartmouth study found rising temperatures contributed to over 500 additional home runs since 2010. Wind direction is especially impactful at Wrigley Field, where wind blowing out toward the lake significantly inflates home run rates. Swish Analytics provides game-specific weather factors showing the percent change from historical park averages. A practical rule of thumb: warm day games with wind blowing out might add 5–10% to scoring expectations, pushing a total line up by 0.4–0.8 runs in your model.

### How sharp bettors identify and exploit edges

The edge-finding process is mechanical: build your Poisson model, generate λ_A and λ_B for every game, compute probabilities for all bet types, then compare to market-implied probabilities. **The edge equals the difference between your model's probability and the market's implied probability.** If your model projects a total of 8.7 runs and the market line is Over/Under 8.0 at −110 (implied 52.4%), your Poisson calculation might yield P(Over 8.0) ≈ 57–58%, representing 5–6 percentage points of edge.

**Closing Line Value (CLV)** is the single most validated metric for assessing whether a bettor has genuine skill. CLV measures the difference between the odds at which you placed your bet and the final closing odds. Professional bettors use CLV as their primary success metric because persistent CLV profit correlates almost perfectly with long-term profitability — more so than win-loss records, which are dominated by variance over short samples. One OddsJam tracker showed a sharp bettor beating the closing line on **75.6% of bets**.

Multiple sharp-bettor consensus sources emphasize that **totals often offer more edge than sides** in MLB. Totals can be mispriced due to weather, park dimensions, or umpire tendencies that the public underweights. Line shopping across sportsbooks is essential — "soft books" like FanDuel may keep mispriced lines available for hours after sharp books like Pinnacle have moved. Experienced bettors on the SBR forum recommend avoiding extreme posted totals (very high or very low), where books are sharpest, and focusing on mid-range totals (7.5–9.5) where inefficiencies are most exploitable.

### Kelly criterion turns probabilities into optimal bet sizes

Once your Poisson model identifies a +EV opportunity, the Kelly criterion determines optimal stake sizing:

**f* = (bp − q) / b**

Where p is your Poisson-derived probability, q = 1 − p, and b is the decimal odds minus 1. If your model says P(Under 8.5) = 59.3% and the book offers −110 (decimal 1.909, so b = 0.909), then f* = (0.909 × 0.593 − 0.407) / 0.909 = **14.6% of bankroll**.

Full Kelly is mathematically optimal for long-run growth but practically too aggressive — drawdowns can be devastating when model error is factored in. **The industry standard is ¼ to ½ Kelly** with hard caps of 2–5% of bankroll per individual wager. The analytics.bet blog (by a Canadian actuary) describes building a first sports betting model using Poisson + Kelly specifically for finding +EV opportunities against soft bookmakers, using Pinnacle's implied odds as anchors for "true" probabilities.

### The overdispersion problem is real but manageable

The most honest assessment of Poisson for MLB betting acknowledges that run scoring is substantially overdispersed. The **variance-to-mean ratio of approximately 2.2:1** for runs per game means the Poisson model systematically underestimates the probability of both shutouts and blowouts while overestimating moderate-scoring outcomes. The Walk Like a Sabermetrician blog performed chi-squared tests on 1981–96 data and found the Poisson χ² statistic was **91,996** versus just 371 for the superior Adams distribution.

For bettors, overdispersion means the tails of the score distribution are fatter than Poisson predicts. This has specific implications: your model will slightly misprice extreme totals (very low and very high), underestimate the frequency of one-run games, and be somewhat overconfident in its probability estimates. The negative binomial distribution with its extra dispersion parameter provides meaningfully better calibration. However, many practitioners stick with Poisson and apply post-hoc adjustments or simply accept the approximation error as part of their model uncertainty budget.

A more fundamental concern is the independence assumption. While baseball teams' run scoring is approximately independent (more so than in soccer, where game state strongly affects both teams' strategies), correlations exist through shared weather conditions, umpire tendencies, and bullpen-management dynamics in blowouts. Karlis and Ntzoufras's 2003 bivariate Poisson framework addressed this by introducing a covariance parameter λ₃, finding that even small positive correlation significantly affects draw (tie) probabilities. For baseball, where ties are resolved through extra innings, this effect is less critical but not negligible.

### Validating your model before risking real money

Model validation is non-negotiable. The key metrics for evaluating a Poisson betting model are:

**Brier Score**: BS = (1/N) × Σ(yᵢ − pᵢ)², where yᵢ is the actual outcome (0 or 1) and pᵢ is the predicted probability. Lower is better; a random model scores ~0.25 for binary outcomes. **Log Loss** penalizes overconfident mispredictions more severely: −mean(y·log(p) + (1−y)·log(1−p)). A random model scores ~0.693. **Calibration curves** — plotting predicted probabilities against actual frequencies in decile bins — reveal systematic biases. The ideal calibration curve is a 45-degree diagonal; Werner's PML model, for instance, was found to be overconfident (predicted extremes were too extreme).

Walk-forward validation is essential: train on seasons N−2 through N−1, test on season N, then roll forward. Never include post-game information when predicting that game. Walsh and Joshi (2024) demonstrated that calibration-optimized models generate **69.86% higher returns** than accuracy-optimized models in sports betting — a finding that underscores why Brier score and calibration matter more than raw win-loss percentage.

### Monte Carlo simulation bridges single-game and season-level analysis

Monte Carlo simulation extends the Poisson framework from individual game probabilities to full distributional analysis. The process is straightforward: estimate λ_A and λ_B, then sample runs_A from Poisson(λ_A) and runs_B from Poisson(λ_B) across **10,000+ iterations**. Count the frequencies of every outcome — wins, losses, exact scores, run-line covers, total runs — and convert to probabilities.

Lloyd Danzig of Sharp Alpha published a detailed Excel walkthrough using a Yankees-versus-Red Sox example, simulating thousands of game outcomes with Poisson-derived scoring rates and optimizing bet sizing against bet365 odds using Solver. Buchdahl's book *Monte Carlo or Bust: Simple Simulations for Aspiring Sports Bettors* provides the most comprehensive publicly available guide to these techniques. For season-level analysis, Monte Carlo enables pricing of futures markets — simulating all 162 games for every team, thousands of times, to generate probability distributions for division winners, playoff qualifiers, and over/under season win totals.

Monte Carlo is particularly valuable for exotic or parlay markets where analytical solutions are intractable. Rather than attempting to calculate the joint probability of three specific game outcomes algebraically, you simply simulate all three games 100,000 times and count the frequency of the desired combination.

---

## Key research and resources for practitioners

The academic and practitioner literature on Poisson models in sports is extensive. The seminal paper is **Dixon and Coles (1997)**, "Modelling Association Football Scores and Inefficiencies in the Football Betting Market" in *Applied Statistics*, which introduced the attack/defense parameter framework with a correction factor for low-scoring outcomes and time-decay weighting. Though developed for soccer, its methodology has been directly adapted for baseball. **Karlis and Ntzoufras (2003)** extended this to bivariate Poisson in the *Journal of the Royal Statistical Society*. **Koopman and Lit (2012)** at the Tinbergen Institute demonstrated a dynamic bivariate Poisson with time-varying parameters that generated profitable betting returns on the English Premier League.

For baseball specifically, **Miller's 2007 derivation** of the Pythagorean formula via Weibull distributions (arXiv:math/0509698) is the key theoretical contribution. **Huber and Glen (2007)** and **Huber and Sturdivant (2010)** validated Poisson processes for rare baseball events. The **Florez, Guindani, and Vannucci (2024)** paper on Bayesian bivariate Conway-Maxwell-Poisson for MLB represents the current state of the art.

Pinnacle's betting resources section hosts the most widely cited Poisson betting tutorial ("Poisson Distribution: Predict the Score in Soccer Betting"), along with Buchdahl's 60+ articles on value betting, Monte Carlo methods, and the favorite-longshot bias. The dashee87.github.io tutorial provides complete Python code using statsmodels for Poisson regression with attack/defense parameters. The penaltyblog Python library offers production-quality implementations of Dixon-Coles and bivariate Poisson models. For R users, a February 2026 R-bloggers post provides full code for Bayesian probabilities, expected value calculation, Kelly criterion, and reliability curves with Brier score evaluation.

---

## Conclusion: a flawed but indispensable framework

Poisson regression occupies a peculiar position in baseball analytics and betting: everyone who uses it knows it is wrong, yet nearly everyone uses it anyway. The overdispersion problem (variance ≈ 2.2× the mean for MLB run scoring) is well-documented and uncontroversial. The negative binomial distribution fits historical data substantially better. The Conway-Maxwell-Poisson and bivariate models capture features — dispersion flexibility, score correlation — that basic Poisson ignores entirely.

Yet Poisson endures because of three practical advantages. First, **its single-parameter simplicity makes it uniquely transparent** — every probability can be computed by hand or in a spreadsheet cell, making it easy to audit and debug. Second, the independence and additivity properties (the sum of independent Poissons is Poisson; the difference follows a Skellam) enable clean analytical solutions for totals, moneylines, and run lines without requiring simulation. Third, for betting purposes, the goal is not perfect probability estimation but rather identifying when your imperfect model diverges sufficiently from the market's imperfect model — and Poisson is accurate enough to detect genuine edges.

The most profitable deployment of Poisson in MLB betting combines the base model with domain-specific adjustments: pitcher-specific λ values derived from FIP/xFIP/SIERA, park factor multipliers, weather corrections, and times-through-the-order splits for F5 markets. The resulting probabilities feed into Kelly criterion position sizing (at ¼ to ½ Kelly), with rigorous walk-forward backtesting and calibration analysis ensuring the model performs in live markets. The practitioners who profit are not those with the most sophisticated distributional assumptions, but those who most accurately estimate λ — the expected runs — and most discipline themselves to bet only when their edge exceeds their uncertainty.
