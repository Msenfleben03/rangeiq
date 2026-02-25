# Understanding Platt Calibration in the Betting Pipeline

> **Purpose**: This document explains why raw model probabilities cannot be trusted directly
> for bet sizing, how Platt scaling corrects systematic overconfidence, and how the two-stage
> calibration-then-Kelly pipeline determines every dollar wagered.
>
> **Audience**: Experienced users who understand basic probability and want to reason about
> how the system decides bet sizes, not just that it does.
>
> **Prerequisite Knowledge**: Familiarity with probabilities, expected value, and the basic
> idea that betting systems require an edge over the market to be profitable.

[Interactive Platt Calibration Explorer](platt-calibration-explorer.html)

---

## The Big Picture

Every bet this system places passes through a two-stage pipeline:

```text
Elo + Barttorvik ensemble
        |
        v
  [ model_prob ]          -- raw win probability, e.g. 0.62
        |
        v
  [ Platt Calibration ]   -- logistic regression corrects overconfidence
        |
        v
  [ cal_prob ]            -- corrected probability, e.g. 0.57
        |
        v
  [ Kelly Criterion ]     -- converts edge over market into dollar stake
        |
        v
  [ $stake ]              -- quarter Kelly, capped at 5% of bankroll
```

Understanding why this two-stage structure exists, and what happens when either stage is
broken, is the key to understanding the system's bet-sizing behavior.

---

## Historical Context

### Why Probability Calibration Became Necessary

When the Kelly criterion was first formalized by J. L. Kelly Jr. at Bell Labs in 1956,
he described the optimal bet fraction for a gambler who knows the true win probability
exactly. The formula is elegant precisely because it assumes certainty about that input.

Real prediction models do not produce true probabilities. They produce scores. A logistic
regression trained on Elo rating differentials and Barttorvik efficiency margins will output
a number between 0 and 1, but that number reflects the model's internal scoring function,
not a calibrated probability of a real-world outcome.

The gap between model scores and true probabilities is called **calibration error**. It has
been studied extensively in machine learning, weather forecasting, and medical diagnosis.
The consistent finding is that most models are **overconfident** -- they assign probabilities
closer to 0 and 1 than the data warrants.

Platt scaling, introduced by John Platt at Microsoft Research in 1999, was originally
designed to fix this problem for support vector machines, which produce scores with no
probabilistic interpretation at all. The insight generalized: fit a logistic regression
on top of any model's raw scores, mapping them to calibrated probabilities. The same
technique works here, applied to Elo-based win probabilities before they enter the Kelly
formula.

---

## Understanding Model Overconfidence

### What Overconfidence Looks Like in Practice

Imagine you have a weather model that says "70% chance of rain" for a particular class of
days. If you look back at all the days it said 70%, and it rained on only 55% of them,
the model is overconfident: it said 70% when the true rate was 55%.

The NCAAB Elo + Barttorvik ensemble shows exactly this pattern. From 3,710 historical
backtest bets across six seasons (2020-2025), the measured overconfidence is roughly
5-10 percentage points depending on the probability range:

| Model Predicts | Actually Wins | Overconfidence |
|----------------|---------------|----------------|
| 50-60%         | 45.2%         | ~10pp          |
| 60-70%         | 60.6%         | ~5pp           |
| 70-80%         | 72.1%         | ~3pp           |
| 80-90%         | 80.1%         | ~5pp           |
| 90-100%        | 89.7%         | ~5pp           |

The model consistently believes in its predictions slightly more than reality warrants.
This is not a sign of a bad model -- it is the normal behavior of discriminative classifiers.
The model was optimized to rank games correctly (high score when home team wins, low score
when they lose), not to produce perfectly calibrated probabilities.

### Why Overconfidence Matters for Bet Sizing

A 5-10 percentage point overconfidence sounds modest, but its effect on Kelly bet sizing
is disproportionate. Kelly is nonlinear: small probability differences near the break-even
point produce large changes in recommended stake.

Consider a game where the market implies 50% probability (even money, +100). Your model
says 58%. The true calibrated probability is actually 52%.

- With raw model_prob (58%): Kelly f*= (1.0* 0.58 - 0.42) / 1.0 = 0.16. Quarter Kelly
  recommends 4% of bankroll ($200 on a $5,000 roll).
- With calibrated cal_prob (52%): Kelly f*= (1.0* 0.52 - 0.48) / 1.0 = 0.04. Quarter
  Kelly recommends 1% of bankroll ($50).

The difference between 58% and 52% -- six percentage points of overconfidence -- translates
to a 4x difference in recommended stake. Without calibration, the system would systematically
overbet marginal edges, increasing drawdown risk without increasing expected returns.

---

## How Platt Scaling Works

### The Logistic Regression Approach

Platt scaling fits a logistic regression model with a single feature: the raw model_prob.
The calibrated probability is:

```text
cal_prob = 1 / (1 + exp(-(A * model_prob + B)))
```

where `A` and `B` are learned from historical data. The fitted coefficients from six
seasons of NCAAB backtests are:

```text
cal_prob = 1 / (1 + exp(-(6.4558 * model_prob - 3.8831)))
```

The logistic function ensures the output is always bounded between 0 and 1. The learned
parameters `A = 6.4558` and `B = -3.8831` represent the logistic regression's learned
transformation from model score space to probability space.

To build intuition for what these numbers mean: when model_prob = 0.60, the calibrated
output is:

```text
exponent = -(6.4558 * 0.60 - 3.8831) = -(3.8735 - 3.8831) = 0.0096
cal_prob = 1 / (1 + exp(0.0096)) ≈ 0.498
```

The model's 60% confidence gets corrected to approximately 50% -- close to even money,
which makes sense given the 45-60% empirical win rate in that bucket. The model said it
had meaningful edge; calibration reveals the edge is much smaller.

### Why Logistic Regression Is Appropriate Here

Platt scaling uses logistic regression rather than isotonic regression or histogram binning
for several reasons:

**Smoothness**: Logistic regression produces a smooth monotonic mapping. If model_prob A
is greater than model_prob B, cal_prob A will always be greater than cal_prob B. This
preserves the ranking signal from the Elo model while correcting the absolute probability
values.

**Sample efficiency**: Logistic regression can fit meaningfully with a few hundred samples.
The 3,710 backtest bets (distributed across six seasons) are sufficient for stable parameter
estimation. Histogram binning would require far more data to avoid noisy bin estimates.

**Extrapolation**: The logistic function extrapolates sensibly to extreme probabilities.
A model_prob of 0.95 does not get mapped to an absurd value; it gets a smooth, bounded
correction.

The practical trade-off is that logistic regression assumes the mapping from model_prob
to true probability follows a logistic curve -- which holds when the model's scores are
approximately linearly related to log-odds. This is a reasonable assumption for Elo-based
models, which are themselves derived from log-odds transformations.

### Where the Training Data Comes From

The calibration is trained on `data/backtests/ncaab_elo_backtest_YYYY.parquet` files,
one per season. Each row is one bet recommendation from the walk-forward backtest:

- `model_prob`: the ensemble's predicted win probability at the time of the bet
- `result`: "win" or "loss" -- the actual outcome

The `build_calibration_data()` function loads all available seasons, concatenates them,
and returns `(model_probs, outcomes)` arrays ready for `sklearn.linear_model.LogisticRegression`.
The calibrator is refitted every time `daily_run.py` starts, using all available historical
data. This means the calibration improves as more paper bets accumulate.

---

## The Calibration-Kelly Connection

### How the Two Stages Interact

Kelly's formula is:

```text
f* = (b * p - q) / b
```

where:

- `b` = decimal_odds - 1 (the profit per dollar risked if the bet wins)
- `p` = win probability (this is where calibration intervenes)
- `q` = 1 - p (loss probability)

The formula tells you the exact fraction of your bankroll that maximizes long-run
geometric growth, given perfect knowledge of `p`. When `p` is overestimated, Kelly
recommends a bet larger than optimal. The excess sizing is pure variance risk, not
extra expected return.

Quarter Kelly (fraction = 0.25) partially compensates for this by halving the overconfidence
penalty: overbetting by 4x raw Kelly becomes overbetting by 1x when multiplied by 0.25.
But the right fix is to make `p` accurate in the first place, not to rely on Kelly fraction
dampening alone.

### The Sensitivity of Kelly to Small Probability Differences

Kelly's nonlinearity is most extreme near the break-even point. At even money (+100 odds),
the break-even win rate is exactly 50%. Consider what happens as calibrated probability
varies around that threshold:

| cal_prob | Kelly f* (full) | Quarter Kelly | $Stake on $5,000 bankroll |
|----------|-----------------|---------------|---------------------------|
| 0.48     | -0.04           | $0 (no bet)   | $0                        |
| 0.50     | 0.00            | $0 (no bet)   | $0                        |
| 0.52     | 0.04            | 1.0%          | $50                       |
| 0.55     | 0.10            | 2.5%          | $125                      |
| 0.60     | 0.20            | 5.0%          | $250 (capped)             |
| 0.65     | 0.30            | 5.0%          | $250 (capped)             |

Notice that the transition from "don't bet" to "bet $250" spans only 10 percentage points
of calibrated probability (0.50 to 0.60). This is the range where calibration matters
most. Systematic overconfidence of 5-10pp in this region would result in every borderline
bet being sized at $125-250 when the correct size is $0-50.

The 5% bankroll cap (currently $250) is not just a safety rail; it is the system's acknowledgment
that even calibrated Kelly is working with imperfect probability estimates. The cap prevents
a single overconfident prediction from causing a damaging loss.

---

## The Edge-vs-ModelProb Bug: A Case Study

### What Went Wrong

The original implementation of `KellySizer.calibrate()` used `edge` as the calibration
feature instead of `model_prob`. Edge is defined as:

```text
edge = model_prob - american_to_implied_prob(american_odds)
```

This seems intuitive: larger edge should mean larger bet. But it is fundamentally wrong
as a calibration feature, for a reason that reveals something important about probability
calibration.

### Why Edge is the Wrong Feature

Consider two bets, both with an edge of +10%:

- **Bet A**: model_prob = 0.90, market implies 0.80 (heavy favorite, -400 odds)
- **Bet B**: model_prob = 0.40, market implies 0.30 (underdog, +233 odds)

Both have a 10% edge. But their win probabilities are completely different: Bet A wins
9 times out of 10, Bet B wins 4 times out of 10. A calibrator that sees only the edge
cannot distinguish these cases. It cannot tell the logistic regression "this is a 90%
bet" versus "this is a 40% bet."

What the calibrator actually learned from this feature was the **overall win rate**. Among
the 3,710 backtest bets, 31.4% were winners (many are longshot underdogs). A logistic
regression with edge as the single feature converges to mapping all edges to approximately
0.314 -- the base rate -- because edge alone provides no meaningful signal about whether
a given bet will win.

The result was that a -410 favorite got a calibrated probability of 18.7%. Kelly on 18.7%
at -410 odds is negative (the market implies 80.4%, and 18.7% is far below break-even),
so the recommended stake is $0. Every single bet -- favorite and underdog alike -- returned
$0 from Kelly. The system silently fell back to flat $150 from the pre-Kelly code path,
making dynamic sizing completely inoperative for weeks.

### Why model_prob Is the Right Feature

`model_prob` carries the base rate information that `edge` lacks. A model_prob of 0.90
is always a near-certain prediction, regardless of what the market implies. The logistic
regression can learn that when the model says 0.90, the true rate is about 0.87 -- a
calibration correction of about 3pp. And when the model says 0.40, the true rate is about
0.35 -- a correction of about 5pp.

The market odds are already accounted for separately in the Kelly formula through the
variable `b` (the payout ratio). Calibration's job is only to correct model_prob. The
formula naturally combines calibrated probability with payout ratio to produce a correctly
sized bet.

This separation of concerns -- calibrate probabilities independently of odds, then combine
in Kelly -- is standard Platt scaling. The bug was in conflating these two steps.

---

## Distribution of Bets and What It Implies for Calibration

### The Longshot Skew

The system primarily finds value on underdogs in small-conference NCAAB games. From the
6-season backtest:

- 52% of bets are on underdogs (model_prob < 0.50 for the bet side)
- The overall win rate is 31.4%
- Many bets are longshots (+200 to +500 American odds)

This distribution has two implications for calibration:

**The training data is imbalanced toward losses.** A calibrator trained on this data must
learn to map most model_prob inputs to probabilities below 0.50. This is correct behavior --
most of these bets will lose. The system is profitable not because it wins often, but
because the wins pay more than the losses cost.

**Calibration quality degrades at the extremes.** The calibrator has few examples of bets
where model_prob > 0.70, because the system rarely has strong edges on heavy favorites.
The fitted logistic curve at the extremes is extrapolation, not interpolation. This is
one reason the 5% bankroll cap is important: it limits damage if the calibration
overestimates probability on a rare high-model_prob bet.

### Why Low Win Rate Does Not Mean the System Is Broken

A 31.4% win rate sounds alarming until you consider the payout structure. At +300 odds,
a $100 bet on an underdog returns $300 profit if it wins. Breaking even requires only
a 25% win rate at those odds. If the system wins 30% of its +300 bets, it has a 5%
edge. Over hundreds of bets, that edge compounds.

The Kelly criterion captures this mathematically: a small probability edge on a high-payout
bet produces the same recommended stake as a small probability edge on a low-payout bet,
all else equal. Calibration ensures the "small probability edge" is measured accurately
in both cases.

---

## Common Misconceptions

### Misconception: Calibration is Optional if You Use Fractional Kelly

**Reality**: Fractional Kelly reduces the harm from overconfidence but does not eliminate
it. Quarter Kelly on an overconfident 0.62 probability is still 4x larger than quarter
Kelly on the correct 0.52 probability. The fractional multiplier scales the error, not
corrects it.

**Why the confusion**: Fractional Kelly is sometimes described as a "safety margin" that
accounts for model uncertainty. This is true in a loose sense -- it reduces variance. But
it is not a substitute for accurate probability estimation. A calibrated model with full
Kelly can outperform an uncalibrated model with quarter Kelly.

### Misconception: Higher Edge Always Means a Bigger Bet

**Reality**: Edge (model_prob minus implied_prob) is not what Kelly uses directly. Kelly
uses the absolute win probability `p` and the payout ratio `b`. A 10% edge on a +500
underdog (model_prob ≈ 0.27, market implies 0.17) produces a smaller Kelly fraction than
a 10% edge on a -110 favorite (model_prob ≈ 0.62, market implies 0.52), because the
underdog has a lower absolute probability of winning.

This is counterintuitive because edge is often used as a proxy for bet quality. It is
a reasonable proxy when comparing bets at similar odds levels, but breaks down when
comparing bets across very different odds.

### Misconception: Calibration Makes the Model More Accurate

**Reality**: Calibration does not change what the model predicts; it changes how to
interpret those predictions. The Elo + Barttorvik ensemble assigns the same probability
scores before and after calibration. Calibration only adjusts the mapping from score to
stated probability. The ranking of games by predicted win probability is unchanged.

What calibration makes more accurate is the relationship between stated probability and
actual observed frequency. A well-calibrated model's "60%" predictions should come true
about 60% of the time -- not 65% or 55%.

### Misconception: The Calibration Is Fixed and Cannot Improve

**Reality**: The calibrator is refitted every morning when `daily_run.py` starts. As more
paper bets are recorded and settled, they accumulate as additional rows in the backtest
parquet files. Each run incorporates all available historical data, so calibration quality
improves with sample size. The fitted coefficients will shift slightly over time as the
training set grows.

---

## Practical Implications

### What Calibration Means for Day-to-Day Betting Decisions

When the system recommends a $120 bet on a +200 underdog, that number reflects:

1. The Elo + Barttorvik ensemble's raw probability (e.g., 0.41)
2. A calibration correction that brings it to approximately 0.36
3. A Kelly calculation: f*= (2.0* 0.36 - 0.64) / 2.0 = 0.04; quarter Kelly = 1%; $50
4. Actually it gets capped at... wait -- if the model says 0.41 and correction is to 0.36,
   at +200 (decimal 3.0, b=2.0): f*= (2.0* 0.36 - 0.64) / 2.0 = 0.04, quarter Kelly = 1%,
   $50, which rounds to $50. If you see $120, the raw probability was higher.

The point is that each stake represents a complete chain of inference. When two games look
equally compelling based on edge alone, the system may size them very differently because
their absolute probabilities -- and therefore their payout-adjusted Kelly fractions -- differ.

### Stakes Scale with Confidence, Not with Edge

Because Kelly uses absolute win probability rather than edge, a bet on a 60% favorite with
a 5% edge gets sized larger than a bet on a 35% underdog with a 5% edge. This reflects the
lower variance of the favorite's outcome: you can bet more on an event that wins 60% of the
time than on one that wins 35% of the time, even if the EV per dollar is identical.

Bettors accustomed to flat-stake betting often find this counterintuitive. Flat staking treats
all bets as equally risky; Kelly treats them as having different variance profiles. Both
approaches can be profitable with genuine edge, but Kelly is theoretically optimal for
bankroll growth when probabilities are accurate -- which is exactly why calibration matters.

### Limitations to Keep in Mind

Calibration is only as good as the training data. Six seasons of NCAAB backtests provide
a reasonable sample, but there are structural concerns:

- **Distribution shift**: The model's performance characteristics could change if the NCAAB
  landscape shifts significantly (rule changes, conference realignment, player development
  patterns).
- **Out-of-distribution bets**: The calibration is well-estimated for the range of model_prob
  values commonly seen (0.30 to 0.70). Bets at the extremes extrapolate the logistic curve.
- **Selection bias**: The backtest bets are not a random sample of NCAAB games -- they are
  games where the model found an edge above the minimum threshold. This selection effect could
  cause the calibrated probabilities to be slightly optimistic if edges are systematically
  overestimated.

The 5% bankroll cap and the quarter Kelly fraction together create a conservative margin that
partially absorbs these uncertainties. The system is not betting as if its calibration were
perfect; it is betting as if calibration reduced but did not eliminate model uncertainty.

---

## Connecting to Broader Concepts

### The Relationship Between Calibration and CLV

Closing Line Value (CLV) measures whether you got better odds than the market eventually
offered at game time. A model with excellent calibration should consistently produce positive
CLV -- but calibration alone does not guarantee it.

CLV depends on whether the model identifies value before the market converges to the true
probability. Calibration ensures the model's probabilities are on the right scale, but the
market must not have already priced in the same information. These are related but distinct
requirements.

If the calibrated model consistently finds bets with positive expected value but negative CLV,
this suggests the model is capturing information already in the closing line -- perhaps from
the same publicly available sources (Barttorvik, ESPN) that sharps use to move the line.
Positive CLV at bet placement is evidence of genuine information advantage.

### Calibration in the Broader ML Ecosystem

Probability calibration is an active area of research in machine learning, particularly for
high-stakes applications: medical diagnosis, financial risk modeling, and weather forecasting.
The techniques used here -- Platt scaling and isotonic regression -- are the two most widely
used approaches. They are appropriate for different situations:

- **Platt scaling** (logistic regression on raw scores): Best when the score-to-probability
  mapping is approximately sigmoid-shaped. Works well with limited data. Assumes the existing
  model's discrimination is correct and only the probability scale needs adjustment.
- **Isotonic regression**: Nonparametric; can fit any monotonic transformation. Requires more
  data to avoid overfitting. Better when the shape of the calibration curve is unknown.

This system uses Platt scaling because the Elo model's scores are derived from log-odds
transformations, making a sigmoid mapping the natural correct form. With 3,710 training
examples, Platt scaling is more reliable than isotonic regression, which would require
several thousand examples per probability bin to be stable.

---

## Summary: The Mental Model

Think of the calibration-Kelly pipeline as a two-lens telescope:

The **first lens (Elo + Barttorvik)** gives you directional signal: which team is more
likely to win, and by roughly how much. It is discriminative but systematically claims more
certainty than the data warrants.

The **second lens (Platt calibration)** corrects the focal length: it adjusts the stated
probabilities so they match observed frequencies. A model that said 60% but won only 50% of
the time is recalibrated so "60%" becomes approximately "50%."

The **Kelly formula** then converts the calibrated probability and the market payout into a
bet size that maximizes long-run geometric bankroll growth, subject to the quarter-Kelly
fraction and the 5% cap that hedge against remaining uncertainty.

Without calibration, the telescope is systematically out of focus. You see the right teams
winning -- the ranking signal is preserved -- but you bet too aggressively on every game
because the model overstates its confidence. Over hundreds of bets, that systematic
overbetting increases variance without increasing expected return.

Key insights to carry forward:

1. **Model probabilities are scores, not frequencies.** They must be calibrated against
   historical outcomes before they can be trusted as inputs to Kelly.

2. **Calibrate on model_prob, not on edge.** Edge conflates the probability estimate with
   the market price. Calibration's job is to fix the probability; Kelly's job is to combine
   it with the price.

3. **Kelly is exquisitely sensitive to small probability errors near the break-even point.**
   Five percentage points of overconfidence can quadruple the recommended stake. Calibration
   does the most work precisely where it matters most.

---

## Further Exploration

- **To implement calibrated bet sizing**: See the `KellySizer` class in
  `betting/odds_converter.py` and the `build_calibration_data()` function.
- **For complete API reference**: Check the docstrings in `betting/odds_converter.py`.
- **For backtest results that generated the training data**: See `data/backtests/` and
  `memory/backtest-results.md`.
- **To understand the Kelly criterion formally**: Kelly, J. L. (1956). "A New Interpretation
  of Information Rate." Bell System Technical Journal, 35(4), 917-926.
- **On probability calibration in machine learning**: Platt, J. (1999). "Probabilistic
  Outputs for Support Vector Machines and Comparisons to Regularized Likelihood Methods."
  Advances in Large Margin Classifiers, MIT Press.
- **On fractional Kelly and the rationale for conservative sizing**: Thorp, E. O. (2006).
  "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market." Handbook of
  Asset and Liability Management.
