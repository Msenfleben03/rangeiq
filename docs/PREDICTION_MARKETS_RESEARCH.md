# Prediction Markets: Modeling Opportunities & CLV Integration

**Research Synthesis for Sports Betting Framework**
**Date:** January 25, 2026
**Focus:** Known inefficiencies, modeling approaches, and CLV adaptation strategies

---

## Executive Summary

Prediction markets present significant opportunities for profitable trading when integrated with a systematic CLV-focused approach. This research identifies:

1. **Key Inefficiencies**: Favorite-longshot bias, liquidity gaps, delayed news pricing, and calendar effects create exploitable edges
2. **Superior Accuracy**: Prediction markets (67% accuracy) rival or exceed traditional sportsbooks (66%) while offering different liquidity profiles
3. **Critical Risks**: Platform/counterparty risk, settlement disputes, and regulatory uncertainty require careful position sizing
4. **CLV Adaptation Required**: Markets don't "close" traditionally - volume-weighted pricing and time-decay models needed
5. **Recommended Entry**: Start with political/regulatory events using 0.15-0.25x Kelly, max 2% position sizes

**Priority Rating: MEDIUM-HIGH** - Complementary to sports betting with uncorrelated returns, but requires platform risk management and modified CLV tracking.

---

## 1. KNOWN MARKET INEFFICIENCIES (Priority-Ranked)

### 1.1 Favorite-Longshot Bias (HIGHEST PRIORITY)

**Description**: Systematic mispricing where longshots are overvalued and favorites are undervalued.

**Evidence**:

- Fixed-odds betting markets show persistent favorite-longshot bias even in competitive environments
- Research shows "longshot bias is a psychological phenomenon that occurs when traders overpay for underdogs, hoping for a larger payoff with lower investment"
- **Exploitable Pattern**: Bet favorites in binary markets; avoid longshots priced >30% implied probability

**Academic Support**:

- Whelan (2024): Risk aversion and favorite-longshot bias in competitive fixed-odds betting
- Green, Lee & Rothschild: "The Favorite-Longshot Bias" comprehensive analysis
- NBER Working Paper w15923: Behavioral explanations for systematic mispricing

**Quantified Edge**:

- Favorites consistently outperform implied probabilities by 1-3%
- Longshots underperform by 2-5% on average
- More pronounced in low-liquidity markets

### 1.2 Liquidity-Driven Mispricings (HIGH PRIORITY)

**Description**: Thin markets create wide spreads and difficulty exiting positions.

**Evidence**:

- "78% of arbitrage opportunities in low-volume markets failed due to execution inefficiencies" (2025 study)
- Best liquidity at market creation when outcome prices are even
- Liquidity paradox: Higher liquidity can worsen forecast resolution due to noise traders

**Exploitable Patterns**:

- Enter positions early when spreads are tight (at creation time)
- Focus on high-volume markets (>$1M traded) for easy exits
- Avoid illiquid markets unless planning to hold to resolution
- Market-make in derivative markets with inventory controls

**Risk Mitigation**:

- Check order depth before entry
- Set maximum spread tolerance (e.g., 2% bid-ask)
- Use limit orders to avoid moving thin markets

### 1.3 Delayed News Incorporation (HIGH PRIORITY)

**Description**: Markets lag in pricing breaking news compared to real-time information flow.

**Evidence**:

- "Evidence of delay in fully integrating news into asset prices" despite market efficiency
- "Prices underreact to news events and display short-term momentum"
- Prediction markets react faster than polls but slower than sharp sportsbooks

**Exploitable Patterns**:

- Monitor high-impact news sources (debates, scandals, regulatory announcements)
- Act within minutes of major events before market fully reprices
- Use automated news scraping + sentiment analysis for speed advantage
- Focus on markets where you have information edge (e.g., niche political events)

**Implementation Strategy**:

```python
# Pseudo-code for news-based trading
if major_news_event_detected():
    current_price = get_market_price()
    expected_new_price = bayesian_update(current_price, news_impact)
    if abs(expected_new_price - current_price) > 5%:
        place_order(side="YES" if expected_new_price > current_price else "NO")
```

### 1.4 Calendar Effects & Event Cycles (MEDIUM PRIORITY)

**Description**: Systematic pricing patterns around election cycles, earnings dates, and seasonal events.

**Evidence**:

- "For events further in the future (>1 year), prices are biased towards 50% due to traders' preferences not to lock funds"
- Election markets show predictable volatility around debates, primaries, and polling releases
- Weekly trading volume peaked at $2.3B during October 2025 election period

**Exploitable Patterns**:

- Fade extreme moves immediately after debates (mean reversion)
- Buy underpriced favorites in long-dated contracts (>6 months out)
- Increase liquidity provision during high-volatility events
- Harvest volatility premium by selling options on prediction markets (where available)

### 1.5 Cross-Platform Arbitrage (MEDIUM PRIORITY - EXECUTION RISK)

**Description**: Price discrepancies between Polymarket, Kalshi, PredictIt, and Robinhood.

**Evidence**:

- Over $40M in arbitrage profits extracted from Polymarket alone (April 2024 - April 2025)
- "Arbitrage opportunities typically offer returns between 0.5% and 3%"
- Most opportunities close within seconds due to bot competition

**Key Challenges**:

- "Combined fees of 5%+ mean spreads under 5% are unprofitable"
- Resolution risk: "Polymarket resolved to YES despite no actual shutdown while Kalshi resolved to NO"
- Regulatory arbitrage: Different platforms have different legal jurisdictions
- Non-atomic execution: 62% of combinatorial arbitrage attempts fail

**Recommended Approach**:

- Only pursue arbitrage >3% spread after fees
- Verify resolution criteria are IDENTICAL across platforms
- Pre-fund accounts to enable instant execution
- Use automated tools for speed (human reaction too slow)

### 1.6 Retail Trader Behavioral Patterns (MEDIUM PRIORITY)

**Description**: Predictable biases from non-professional market participants.

**Evidence**:

- Risk-lovers create distortionary effects: herding, persistent contrariness, skewed profit distributions
- Noise traders exhibit "illusion of control" and "myopic loss aversion"
- Markets can create self-reinforcing environments where traders anchor to current odds

**Exploitable Patterns**:

- Fade retail panic (buy when markets overreact to bad news)
- Contrarian positions in markets with extreme sentiment
- Bet against recency bias (traders overweight latest poll/news)
- Identify "whale" positions and bet against forced exits

---

## 2. ACADEMIC RESEARCH SYNTHESIS

### 2.1 Market Efficiency Literature

**Core Findings**:

1. **Prediction markets are efficient at information aggregation BUT systematic biases persist**
   - Tetlock (2008): Liquidity improves efficiency in sports/financial markets but noise traders can derail benefits
   - Franck et al. (2010): Betting exchanges show higher predictive power than traditional bookmakers
   - "Forecasting resolution of market prices actually worsens with increases in liquidity" (counterintuitive)

2. **Prediction Markets vs. Traditional Forecasting**
   - Polymarket: 67% accuracy (2024-25 NBA season)
   - OddsPortal sportsbooks: 66% accuracy
   - Prediction markets had significantly better Brier scores than polling aggregates in 2024 election

3. **Information Incorporation Speed**
   - Markets demonstrate "near-instantaneous probability assessments"
   - BUT "evident delay in fully integrating news into asset prices"
   - Faster than polls, competitive with sharp sportsbooks

**Key Papers**:

- **Explaining the Favorite-Longshot Bias** (Journal of Political Economy, 2010)
- **Prediction accuracy of different market structures** (Int'l Journal of Forecasting, 2010)
- **The Wisdom of the Crowd and Prediction Markets** (ScienceDirect, 2024)
- **Application of the Kelly Criterion to Prediction Markets** (arXiv:2412.14144, December 2024)

### 2.2 Wisdom of Crowds vs. Elite Forecasters

**Surprising Finding**: Aggregation method matters more than forecaster quality.

**Evidence**:

- "Prediction markets' greater accuracy lies largely in superior aggregation methods rather than superior quality of responses"
- Team prediction polls outperformed prediction markets when using temporal decay + differential weighting + recalibration
- Metaculus superforecasters achieve 0.01 calibration (average error just 1%)

**Implications for Modeling**:

- Don't just track market price - build custom aggregation algorithms
- Weight recent information higher (temporal decay)
- Recalibrate using historical accuracy data
- Consider ensemble of market price + fundamentals model

### 2.3 Market Manipulation & Settlement Risk

**Critical Findings**:

- "Polymarket has previously faced criticism over handling of manipulation issues"
- Resolution disputes create total loss scenarios (e.g., government shutdown case)
- Thin trading + reluctance to short undermines forecasting utility

**Risk Management Implications**:

- Diversify across platforms (reduce single-platform risk)
- Verify resolution criteria before entering positions
- Monitor for whale manipulation (sudden large orders)
- Exit positions before expiry if resolution criteria are ambiguous

---

## 3. MODELING APPROACHES (Ranked by Effectiveness)

### 3.1 Fundamental Models - Polling Aggregation (TIER 1)

**Approach**: Bayesian synthesis of polls, economic indicators, and historical base rates.

**Key Methodologies**:

- **Nate Silver / FiveThirtyEight Model**:
  - Combines fundamentals (incumbency, economic indicators) with polling data
  - Uses Bayesian updating with time-series model
  - Accounts for polling error correlation across states
  - Silver's 2024 model: "98% the same as 2020 methodology"

- **Economist Dynamic Bayesian Model** (Linzer 2013):
  - Partially pools fundamentals forecast + state/national polls
  - Evidence synthesis approach rather than regression
  - Time-varying uncertainty bands

- **Lock & Gelman Hybrid**:
  - Combine fundamentals and trial-heat polls using Bayesian methods
  - Account for forecast uncertainty over time horizon

**Implementation Strategy**:

```python
# Bayesian aggregation framework
class PredictionMarketModel:
    def __init__(self):
        self.prior = self.calculate_fundamental_prior()
        self.polls = self.fetch_latest_polls()

    def calculate_fundamental_prior(self):
        """Base rate from historical data + economic indicators"""
        return bayesian_prior(
            incumbency_advantage=0.05,
            economic_indicators={'gdp_growth': 0.02, 'unemployment': 0.045},
            historical_base_rate=0.52
        )

    def bayesian_update(self, poll_result):
        """Update probability with new poll"""
        likelihood = poll_result.probability
        self.prior = (self.prior * likelihood) / marginal_probability

    def get_fair_price(self):
        """Current probability estimate"""
        return self.prior
```

**Data Requirements**:

- Historical polling databases (FiveThirtyEight, RealClearPolitics)
- Economic indicators (Fed data, BLS)
- Election fundamentals (incumbency, approval ratings)
- Polling methodology metadata (sample size, methodology, house effects)

### 3.2 Technical Analysis - Price Patterns (TIER 2)

**Approach**: Exploit momentum, mean reversion, and volume signals.

**Evidence-Based Patterns**:

1. **Short-term momentum**: "Prices underreact to news events and display short-term momentum"
2. **Mean reversion after shocks**: Extreme moves post-debates tend to reverse
3. **Volume spikes**: Indicate information arrival or manipulation

**Signal Types**:

```python
# Technical signals for prediction markets
def calculate_signals(market_history):
    signals = {
        'momentum_5d': calculate_momentum(prices, window=5),
        'mean_reversion': distance_from_moving_average(prices, window=20),
        'volume_spike': volume_zscore(volumes, window=10),
        'volatility': rolling_std(returns, window=10),
        'bid_ask_spread': current_bid - current_ask  # Liquidity indicator
    }
    return signals
```

**Limitations**:

- Less effective than fundamentals for long-term positions
- Risk of overfitting to limited historical data
- High turnover can incur excessive fees

### 3.3 Sentiment Analysis (TIER 2)

**Approach**: Extract signals from news, social media, and prediction market comments.

**Implementation**:

- LLM-based news sentiment scoring
- Twitter/X sentiment tracking for political figures
- Polymarket comment section analysis
- Google Trends correlation with outcome probabilities

**Evidence**:

- "Ensemble of 12 LLM models achieved forecasting accuracy statistically indistinguishable from human crowd"
- News-event driven traders react quickly to debates, scandals, endorsements

**Caution**: Sentiment can be noisy and manipulated. Use as supplementary signal, not primary.

### 3.4 Ensemble Methods (TIER 1 - RECOMMENDED)

**Approach**: Combine multiple signals using weighted averages or machine learning.

**Architecture**:

```
Final_Probability = w1*Fundamental_Model + w2*Market_Price + w3*Sentiment + w4*Technical

Where weights are optimized based on historical accuracy
```

**Advantages**:

- Diversifies model risk
- Captures different information types
- More robust to individual model failures

**Metaculus Approach**:

- Aggregate individual forecasts using temporal decay
- Differential weighting based on past forecaster performance
- Recalibration using historical accuracy

**Implementation**:

```python
class EnsemblePredictor:
    def __init__(self):
        self.models = {
            'fundamental': FundamentalModel(),
            'technical': TechnicalModel(),
            'sentiment': SentimentModel(),
            'market_price': MarketPriceModel()
        }
        self.weights = self.optimize_weights()  # Historical backtest

    def predict(self, event):
        predictions = {
            name: model.predict(event)
            for name, model in self.models.items()
        }
        return weighted_average(predictions, self.weights)
```

### 3.5 Superforecaster Methodology (TIER 1 - PROCESS)

**Key Techniques** (from Good Judgment Project):

1. **Bayesian Reasoning**
   - Make many small updates vs. few large jumps
   - Explicitly calculate prior × likelihood
   - Update incrementally with new information

2. **Reference Class Forecasting**
   - Start with base rate from similar historical events
   - Adjust for specific factors unique to current situation
   - Example: "How often has an incumbent won with this approval rating?"

3. **Team Collaboration**
   - Superforecaster teams outperform individuals
   - Share reasoning, not just predictions
   - Devil's advocate review of forecasts

4. **Calibration Training**
   - Track historical accuracy religiously
   - Use calibration tools (OpenPhilanthropy interactive tutorial)
   - Aim for Brier score <0.15, ideally <0.10

5. **Metacognition**
   - Be aware of cognitive biases (anchoring, recency, confirmation)
   - Actively seek disconfirming evidence
   - "What would change my mind?"

**Metaculus Best Practices**:

- Average log-score >0.2 suggests overconfidence
- Compare personal calibration to community
- Focus on resolution rate + calibration, not just Brier score

---

## 4. CLV ADAPTATION FOR PREDICTION MARKETS

### 4.1 Challenge: Markets Don't "Close" Traditionally

**Problem**: Unlike sportsbooks, prediction markets remain open until event resolution. There's no single "closing line" to benchmark against.

**Proposed Solutions**:

#### Option A: Volume-Weighted Average Price (VWAP) - Final Hour

```python
def calculate_prediction_market_clv(entry_price, market_history):
    """
    Calculate CLV using volume-weighted price in final hour before resolution
    """
    final_hour_trades = market_history[-60:]  # Last 60 minutes

    vwap = sum(trade.price * trade.volume for trade in final_hour_trades) / \
           sum(trade.volume for trade in final_hour_trades)

    clv = (vwap - entry_price) / entry_price
    return clv
```

**Rationale**: Final hour represents most informed pricing, analogous to closing line in sports.

#### Option B: Resolution-Minus-N-Hours Snapshot

```python
def snapshot_clv(entry_price, resolution_time, hours_before=1):
    """
    Use price snapshot N hours before resolution as "closing line"
    """
    snapshot_time = resolution_time - timedelta(hours=hours_before)
    closing_price = get_price_at_time(snapshot_time)

    clv = (closing_price - entry_price) / entry_price
    return clv
```

**Rationale**: Avoids last-minute manipulation, gives market time to incorporate all information.

#### Option C: Time-Decay Weighted CLV

```python
def time_decay_clv(entry_price, entry_time, resolution_time, market_history):
    """
    Weight later prices more heavily using exponential decay
    """
    time_weights = []
    prices = []

    for timestamp, price in market_history:
        time_to_resolution = (resolution_time - timestamp).total_seconds()
        weight = np.exp(-time_to_resolution / DECAY_CONSTANT)
        time_weights.append(weight)
        prices.append(price)

    weighted_closing_price = np.average(prices, weights=time_weights)
    clv = (weighted_closing_price - entry_price) / entry_price
    return clv
```

**Rationale**: Incorporates information from entire price history with recency bias.

### 4.2 Recommended Hybrid Approach

**Combine VWAP + Snapshot for robustness**:

```python
def calculate_pm_clv(entry_price, entry_time, resolution_time, market_history):
    """
    Hybrid CLV calculation for prediction markets
    """
    # Method 1: VWAP in final hour
    vwap_clv = vwap_method(entry_price, market_history)

    # Method 2: Snapshot 1 hour before resolution
    snapshot_clv = snapshot_method(entry_price, resolution_time, hours=1)

    # Average the two methods
    hybrid_clv = (vwap_clv + snapshot_clv) / 2

    return {
        'clv': hybrid_clv,
        'vwap_clv': vwap_clv,
        'snapshot_clv': snapshot_clv,
        'entry_price': entry_price,
        'entry_time': entry_time
    }
```

### 4.3 Database Schema Extension

Add to existing `bets` table:

```sql
ALTER TABLE bets ADD COLUMN market_type TEXT;  -- 'sportsbook' or 'prediction_market'
ALTER TABLE bets ADD COLUMN platform TEXT;  -- 'Polymarket', 'Kalshi', etc.
ALTER TABLE bets ADD COLUMN vwap_price REAL;  -- VWAP in final hour
ALTER TABLE bets ADD COLUMN snapshot_price REAL;  -- Price 1hr before resolution
ALTER TABLE bets ADD COLUMN time_to_resolution INTEGER;  -- Hours between entry and resolution
ALTER TABLE bets ADD COLUMN contract_address TEXT;  -- For blockchain markets
```

### 4.4 Performance Tracking Differences

**Key Metrics for Prediction Markets**:

| Metric | Sportsbook | Prediction Market |
|--------|------------|-------------------|
| **CLV** | vs. closing line | vs. VWAP/snapshot |
| **Hold Time** | ~2 hours | Days to months |
| **Liquidity Risk** | None (pre-game bets) | High (thin markets) |
| **Exit Flexibility** | Can't exit | Can trade out early |
| **Edge Decay** | Minimal | Significant over time |

**Additional Tracking**:

```python
class PredictionMarketMetrics:
    def track_performance(self, position):
        return {
            'clv': calculate_pm_clv(position),
            'hold_time': position.exit_time - position.entry_time,
            'exit_slippage': position.exit_price - position.target_exit_price,
            'unrealized_pnl': self.mark_to_market(position),
            'platform_fees': calculate_total_fees(position),
            'counterparty_risk_days': days_until_resolution(position)
        }
```

---

## 5. RISK MANAGEMENT FRAMEWORK MODIFICATIONS

### 5.1 Platform/Counterparty Risk (CRITICAL)

**New Risk Types Not Present in Sportsbooks**:

1. **Platform Insolvency Risk**
   - Polymarket: Decentralized on Polygon blockchain (lower risk)
   - Kalshi: CFTC-regulated, centralized (regulatory risk but operational clarity)
   - PredictIt: Limited to $850/contract, academic exemption (regulatory uncertainty)

2. **Smart Contract Risk**
   - Bugs in code could lead to losses
   - Audit reports required before depositing funds
   - Diversify across platforms

3. **Regulatory Risk**
   - "Kalshi, Robinhood and Crypto.com battling more than 20 lawsuits"
   - State cease-and-desist orders (Nevada, Connecticut)
   - Platform could be forced to close mid-position

**Mitigation Strategies**:

```python
PLATFORM_RISK_LIMITS = {
    'Polymarket': {
        'max_exposure': 0.25,  # 25% of total bankroll
        'max_single_position': 0.05,  # 5% per contract
        'regulatory_jurisdiction': 'Offshore (US blocked)',
        'risk_rating': 'MEDIUM-HIGH'
    },
    'Kalshi': {
        'max_exposure': 0.40,  # 40% of bankroll
        'max_single_position': 0.08,
        'regulatory_jurisdiction': 'CFTC-regulated (US)',
        'risk_rating': 'MEDIUM'
    },
    'PredictIt': {
        'max_exposure': 0.10,  # Only 10% due to limits
        'max_single_position': 0.02,
        'regulatory_jurisdiction': 'Academic exemption (uncertain)',
        'risk_rating': 'HIGH'
    }
}
```

### 5.2 Settlement/Resolution Risk (CRITICAL)

**Problem**: "Polymarket resolved to YES despite no actual shutdown while Kalshi resolved to NO"

**Mitigation**:

1. **Read Resolution Criteria Carefully**
   - Screenshot criteria at entry time
   - Look for ambiguous language
   - Check historical dispute rate for market creator

2. **Diversify Resolution Risk**
   - Don't hold opposite positions on different platforms
   - If arbitraging, ensure IDENTICAL resolution criteria
   - Exit before expiry if criteria are unclear

3. **Monitor Dispute Mechanisms**
   - Polymarket: UMA oracle with 2-hour dispute window
   - Kalshi: Centralized adjudication by exchange
   - PredictIt: Academic panel review

### 5.3 Liquidity Risk (HIGH IMPACT)

**Problem**: "78% of arbitrage opportunities in low-volume markets failed due to execution inefficiencies"

**New Risk Parameters**:

```python
LIQUIDITY_REQUIREMENTS = {
    'min_total_volume': 100000,  # $100k minimum market volume
    'max_spread': 0.02,  # 2% maximum bid-ask spread
    'min_depth_at_touch': 5000,  # $5k minimum at best bid/offer
    'position_size_limit': lambda depth: min(depth * 0.1, max_position)
}

def check_liquidity(market):
    """Only enter positions in liquid markets"""
    if market.volume < LIQUIDITY_REQUIREMENTS['min_total_volume']:
        return False
    if market.spread > LIQUIDITY_REQUIREMENTS['max_spread']:
        return False
    if market.depth_at_touch < LIQUIDITY_REQUIREMENTS['min_depth_at_touch']:
        return False
    return True
```

### 5.4 Correlation with Sports Betting Portfolio (NEW CONSIDERATION)

**Question**: Do prediction market returns correlate with sports betting?

**Analysis**:

- **Low correlation expected**: Political events independent of sports outcomes
- **Potential correlation**: Major news (war, pandemic) affects both markets
- **Diversification benefit**: Uncorrelated returns smooth equity curve

**Recommendation**:

```python
# Maximum combined exposure accounting for correlation
def calculate_total_exposure(sports_positions, pm_positions):
    sports_exposure = sum(p.risk for p in sports_positions)
    pm_exposure = sum(p.risk for p in pm_positions)

    # Assume 0.2 correlation between markets
    correlation = 0.2

    # Portfolio variance formula
    total_risk = sqrt(
        sports_exposure**2 +
        pm_exposure**2 +
        2 * correlation * sports_exposure * pm_exposure
    )

    # Don't exceed 15% total portfolio risk
    assert total_risk <= 0.15 * TOTAL_BANKROLL
```

### 5.5 Modified Kelly Criterion for Prediction Markets

**Adjustments Required**:

1. **Lower Kelly Fraction** (due to higher uncertainty)
   - Sports betting: 0.25x Kelly
   - Prediction markets: 0.15-0.20x Kelly (more conservative)

2. **Platform Risk Adjustment**

   ```python
   def prediction_market_kelly(win_prob, odds, platform_risk_factor=0.8):
       """
       Reduce Kelly size by platform risk factor
       """
       base_kelly = (odds * win_prob - (1 - win_prob)) / odds
       fractional_kelly = base_kelly * 0.20  # More conservative than sports
       risk_adjusted = fractional_kelly * platform_risk_factor

       return min(risk_adjusted, 0.02)  # Max 2% per position
   ```

3. **Time-Based Adjustments**

   ```python
   def time_decay_kelly(base_kelly, days_to_resolution):
       """
       Reduce position size for long-dated contracts (higher uncertainty)
       """
       if days_to_resolution > 180:  # 6+ months
           return base_kelly * 0.5
       elif days_to_resolution > 90:  # 3-6 months
           return base_kelly * 0.7
       elif days_to_resolution > 30:  # 1-3 months
           return base_kelly * 0.85
       else:  # <30 days
           return base_kelly * 1.0
   ```

### 5.6 Updated Risk Limits Table

| Risk Type | Sports Betting | Prediction Markets |
|-----------|---------------|-------------------|
| **Max Single Position** | 3% | 2% |
| **Kelly Fraction** | 0.25x | 0.15-0.20x |
| **Daily Exposure** | 10% | 5% |
| **Platform Concentration** | N/A | Max 25% per platform |
| **Liquidity Requirement** | None | Min $100k volume |
| **Max Spread Tolerance** | N/A | 2% bid-ask |
| **Hold Time Limit** | <2 hours | <6 months (prefer <3mo) |

---

## 6. EXISTING TOOLS & MODELS

### 6.1 Nate Silver / Silver Bulletin

**Background**:

- Joined Polymarket as advisor (July 2024) - "The Nate Silver Effect"
- Released independent 2024 election model after leaving FiveThirtyEight
- Methodology: "98% the same as 2020" combining fundamentals + polls

**Key Insights**:

- Prediction markets had better Brier scores than polling aggregates in 2024
- Markets priced Trump at 60% while polls showed 50/50 toss-up
- Markets were more accurate (closer to actual outcome)

**Application**:

- Use Silver's aggregation methodology as baseline
- Compare model predictions to both market prices AND Silver's model
- Trade discrepancies >5% between Silver model and market price

### 6.2 Metaculus Platform & Methodology

**Superforecaster Techniques**:

- Calibration training via OpenPhilanthropy tutorial
- Average log-score >0.2 = overconfidence warning
- Median Brier scores ~0.1 for top forecasters

**Key Features**:

- Track record comparison vs. community
- Temporal decay weighting of forecasts
- Differential weighting by past performance
- Recalibration algorithms

**Integration Strategy**:

```python
class MetaculusIntegration:
    def get_community_forecast(self, event_id):
        """Fetch Metaculus community prediction as benchmark"""
        return metaculus_api.get_prediction(event_id)

    def calculate_edge_vs_metaculus(self, my_prediction, event_id):
        """Compare model to superforecaster consensus"""
        community_pred = self.get_community_forecast(event_id)
        market_price = get_polymarket_price(event_id)

        # Edge exists if model + Metaculus both diverge from market
        if abs(my_prediction - community_pred) < 0.05:  # Agreement
            if abs(market_price - my_prediction) > 0.05:  # Market diverges
                return True, my_prediction - market_price
        return False, 0
```

### 6.3 Manifold Calibration Data

**Use Case**: Historical calibration benchmarking

**Key Metrics**:

- Track historical accuracy of market prices
- Compare early prices vs. final resolution
- Identify systematic biases by event type

**Implementation**:

```python
def calibration_analysis(historical_markets):
    """
    Analyze how well market prices predicted outcomes
    """
    results = []
    for market in historical_markets:
        price_buckets = bin_prices(market.prices, bins=10)

        for bucket in price_buckets:
            predicted_prob = bucket.avg_price
            actual_rate = bucket.resolution_rate
            calibration_error = abs(predicted_prob - actual_rate)

            results.append({
                'bucket': bucket.range,
                'predicted': predicted_prob,
                'actual': actual_rate,
                'error': calibration_error,
                'n': bucket.count
            })

    return calibration_report(results)
```

### 6.4 Good Judgment Project / Superforecasting

**Core Principles to Implement**:

1. **Fermi Estimation**
   - Break complex questions into estimable components
   - Example: "Will candidate X win?" → Decompose by state probabilities

2. **Reference Class Forecasting**

   ```python
   def reference_class_forecast(current_event, historical_events):
       """
       Start with base rate, adjust for specifics
       """
       similar_events = filter_similar(historical_events, current_event)
       base_rate = sum(e.outcome for e in similar_events) / len(similar_events)

       # Adjust for unique factors
       adjustments = calculate_adjustments(current_event, similar_events)

       return bayesian_update(base_rate, adjustments)
   ```

3. **Granular Probabilistic Thinking**
   - Avoid round numbers (50%, 75%)
   - Use precise probabilities (52%, 73%)
   - Research shows superforecaster accuracy decreases when rounded

4. **Active Open-Mindedness**
   - Seek disconfirming evidence
   - "What would change my prediction by 10%?"
   - Update frequently with small increments

---

## 7. ACTIONABLE NEXT STEPS FOR MODEL DEVELOPMENT

### Phase 1: Infrastructure Setup (Week 1-2)

**Priority: HIGH**

1. **Platform Accounts & APIs**
   - [ ] Open Kalshi account (CFTC-regulated, lowest regulatory risk)
   - [ ] Get Polymarket API access (higher volume, better liquidity)
   - [ ] Set up data pipelines for historical price/volume data
   - [ ] Implement position tracking in existing database

2. **Database Schema Extension**

   ```sql
   -- Add prediction market specific tables
   CREATE TABLE prediction_market_positions (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       platform TEXT NOT NULL,  -- Kalshi, Polymarket, etc.
       market_id TEXT NOT NULL,
       contract_address TEXT,

       -- Position details
       entry_price REAL NOT NULL,
       entry_time TIMESTAMP NOT NULL,
       quantity INTEGER NOT NULL,
       side TEXT NOT NULL,  -- YES or NO

       -- Exit details
       exit_price REAL,
       exit_time TIMESTAMP,
       vwap_price REAL,
       snapshot_price REAL,

       -- Risk tracking
       platform_fees REAL,
       unrealized_pnl REAL,
       realized_pnl REAL,
       clv REAL,
       time_to_resolution INTEGER,

       -- Resolution
       resolution_result BOOLEAN,
       resolution_time TIMESTAMP,
       resolution_disputed BOOLEAN DEFAULT FALSE,

       UNIQUE(platform, market_id, entry_time)
   );
   ```

3. **Risk Management Module**

   ```python
   # betting/prediction_markets.py

   class PredictionMarketRiskManager:
       def __init__(self, config):
           self.platform_limits = config.PLATFORM_RISK_LIMITS
           self.liquidity_reqs = config.LIQUIDITY_REQUIREMENTS

       def check_position_allowed(self, platform, market, size):
           """Validate position against all risk limits"""
           # Check platform exposure
           current_exposure = self.get_platform_exposure(platform)
           if current_exposure + size > self.platform_limits[platform]['max_exposure']:
               return False, "Platform exposure limit exceeded"

           # Check liquidity
           if not self.check_liquidity(market):
               return False, "Insufficient market liquidity"

           # Check single position size
           if size > self.platform_limits[platform]['max_single_position']:
               return False, "Position size exceeds limit"

           return True, "Position allowed"
   ```

### Phase 2: Data Collection & Analysis (Week 3-4)

**Priority: HIGH**

1. **Historical Data Acquisition**
   - [ ] Scrape 6+ months of Polymarket price history
   - [ ] Download Kalshi historical market data
   - [ ] Compile resolution outcomes for calibration analysis
   - [ ] Build database of polling data (FiveThirtyEight, RealClearPolitics)

2. **Inefficiency Analysis**

   ```python
   # Research script: analyze_inefficiencies.py

   def analyze_favorite_longshot_bias(historical_markets):
       """Quantify favorite-longshot bias in prediction markets"""
       favorites = [m for m in historical_markets if m.avg_price < 0.30]
       longshots = [m for m in historical_markets if m.avg_price > 0.70]

       favorite_roi = calculate_roi(favorites)
       longshot_roi = calculate_roi(longshots)

       print(f"Favorite ROI: {favorite_roi:.2%}")
       print(f"Longshot ROI: {longshot_roi:.2%}")
       print(f"Edge from backing favorites: {favorite_roi - longshot_roi:.2%}")
   ```

3. **Calibration Study**
   - Analyze: Do 60% market prices resolve YES 60% of the time?
   - Identify systematic overpricing/underpricing by probability bucket
   - Break down by market type (political, economic, sports, crypto)

### Phase 3: Model Development (Week 5-8)

**Priority: MEDIUM-HIGH**

1. **Fundamental Model - Political Elections**

   ```python
   # models/prediction_market/political_model.py

   class PoliticalElectionModel:
       def __init__(self):
           self.poll_aggregator = PollAggregator()
           self.fundamentals = FundamentalsModel()

       def predict(self, election):
           # Base rate from fundamentals
           prior = self.fundamentals.calculate_prior(
               incumbency=election.is_incumbent,
               approval_rating=election.approval,
               economic_indicators=self.get_economic_data()
           )

           # Update with polls
           polls = self.poll_aggregator.get_recent_polls(election, days=30)
           posterior = self.bayesian_update(prior, polls)

           return posterior
   ```

2. **Ensemble Model**

   ```python
   class EnsemblePredictor:
       def __init__(self):
           self.models = {
               'fundamental': PoliticalElectionModel(),
               'market_price': MarketPriceModel(),
               'metaculus': MetaculusIntegration(),
               'technical': TechnicalAnalysisModel()
           }

       def predict_with_confidence(self, event):
           predictions = {}
           for name, model in self.models.items():
               predictions[name] = model.predict(event)

           # If models disagree significantly, reduce confidence
           disagreement = np.std(list(predictions.values()))

           ensemble_pred = np.mean(list(predictions.values()))
           confidence = 1 / (1 + disagreement)  # Lower confidence if high disagreement

           return ensemble_pred, confidence
   ```

3. **Backtesting Framework**

   ```python
   # backtesting/prediction_market_backtest.py

   def backtest_strategy(model, historical_markets, strategy):
       """
       Walk-forward backtest on historical prediction markets
       """
       positions = []

       for market in historical_markets:
           # Get model prediction at market creation time
           model_pred = model.predict(market, as_of=market.creation_time)
           market_price = market.get_price(market.creation_time)

           # Check if edge exists
           edge = model_pred - market_price

           if abs(edge) > 0.05:  # 5% minimum edge
               position = strategy.enter_position(
                   market=market,
                   side='YES' if edge > 0 else 'NO',
                   size=calculate_kelly_size(edge, model_pred)
               )
               positions.append(position)

       # Calculate performance
       results = calculate_backtest_metrics(positions)
       return results
   ```

### Phase 4: Paper Trading (Week 9-12)

**Priority: MEDIUM**

1. **Live Paper Trading**
   - Track model predictions vs. actual market prices daily
   - Log hypothetical positions in database
   - Calculate CLV using VWAP + snapshot methods
   - Monitor for platform risks and liquidity issues

2. **Performance Metrics**

   ```python
   def generate_paper_trading_report(positions):
       return {
           'total_positions': len(positions),
           'win_rate': calculate_win_rate(positions),
           'avg_clv': np.mean([p.clv for p in positions]),
           'roi': calculate_roi(positions),
           'sharpe_ratio': calculate_sharpe(positions),
           'max_drawdown': calculate_max_drawdown(positions),
           'avg_hold_time': np.mean([p.hold_time for p in positions]),
           'liquidity_issues': count_liquidity_failures(positions),
           'platform_breakdown': breakdown_by_platform(positions)
       }
   ```

3. **Calibration Tracking**
   - For each prediction, track: predicted probability vs. actual outcome
   - Calculate running Brier score
   - Target: Brier score <0.15 (good), <0.10 (excellent)

### Phase 5: Live Deployment (Week 13+)

**Priority: LOW (pending paper trading success)**

**Deployment Criteria** (all must be met):

- [ ] Paper trading ROI >5% over 50+ positions
- [ ] Average CLV >1%
- [ ] Brier score <0.15
- [ ] No major liquidity issues encountered
- [ ] Platform stability confirmed (no regulatory issues)

**Initial Live Parameters**:

```python
LIVE_DEPLOYMENT_CONFIG = {
    'initial_allocation': 500,  # $500 initial capital (10% of reserve)
    'max_position_size': 0.02,  # 2% of allocation
    'kelly_fraction': 0.15,  # Conservative 15% of Kelly
    'platforms': ['Kalshi'],  # Start with CFTC-regulated only
    'markets': ['political', 'economic'],  # Avoid crypto/sports initially
    'min_edge': 0.05,  # 5% minimum edge required
    'max_concurrent_positions': 5,
    'review_frequency': 'weekly'
}
```

---

## 8. INTEGRATION WITH EXISTING SPORTS BETTING FRAMEWORK

### 8.1 Code Reuse Opportunities

**Existing Modules to Leverage**:

1. **betting/odds_converter.py** → Extend for prediction market prices

   ```python
   # Add to odds_converter.py

   def binary_price_to_probability(price: float) -> float:
       """
       Convert prediction market price (YES share price) to probability
       Price is typically $0-$1, representing probability directly
       """
       return price

   def probability_to_binary_price(prob: float) -> float:
       """Inverse conversion"""
       return max(0.01, min(0.99, prob))  # Bounded to avoid 0/1

   def calculate_pm_clv(entry_price: float, vwap_price: float) -> float:
       """
       Prediction market CLV calculation
       Similar to sports betting CLV but using VWAP
       """
       return (vwap_price - entry_price) / entry_price
   ```

2. **betting/kelly.py** → Modify for PM risk adjustments

   ```python
   # Add to kelly.py

   def prediction_market_kelly(
       win_prob: float,
       market_price: float,
       fraction: float = 0.15,  # More conservative
       max_bet: float = 0.02,  # 2% max
       platform_risk_factor: float = 0.8  # Adjust for platform risk
   ) -> float:
       """Kelly sizing for prediction markets with risk adjustments"""

       # For binary markets: edge = true_prob - market_price
       edge = win_prob - market_price

       if edge <= 0:
           return 0.0

       # Kelly formula for binary outcome
       kelly = edge / (1 - market_price)

       # Apply fractional Kelly and risk adjustments
       recommended = kelly * fraction * platform_risk_factor

       return min(recommended, max_bet)
   ```

3. **tracking/database.py** → Extend schema

   ```python
   # Add to database.py

   class PredictionMarketPosition:
       __tablename__ = 'pm_positions'

       id = Column(Integer, primary_key=True)
       platform = Column(String, nullable=False)
       market_id = Column(String, nullable=False)
       entry_price = Column(Float, nullable=False)
       entry_time = Column(DateTime, nullable=False)
       # ... (full schema from Phase 1)

       def calculate_clv(self):
           """Calculate CLV using hybrid VWAP + snapshot method"""
           return calculate_pm_clv(self.entry_price, self.vwap_price)
   ```

### 8.2 Unified Reporting Dashboard

```python
# tracking/reports.py - extend existing module

def unified_performance_report(start_date, end_date):
    """
    Combined report for sports betting + prediction markets
    """
    # Sports betting performance
    sports_bets = get_sports_bets(start_date, end_date)
    sports_metrics = calculate_sports_metrics(sports_bets)

    # Prediction market performance
    pm_positions = get_pm_positions(start_date, end_date)
    pm_metrics = calculate_pm_metrics(pm_positions)

    # Combined metrics
    total_roi = (sports_metrics['roi'] + pm_metrics['roi']) / 2
    correlation = calculate_correlation(sports_bets, pm_positions)

    return {
        'sports_betting': sports_metrics,
        'prediction_markets': pm_metrics,
        'combined': {
            'total_roi': total_roi,
            'total_clv': (sports_metrics['clv'] + pm_metrics['clv']) / 2,
            'correlation': correlation,
            'diversification_benefit': calculate_diversification_benefit(correlation)
        }
    }
```

### 8.3 Risk Management Integration

**Unified exposure tracking**:

```python
# betting/risk_manager.py - new unified module

class UnifiedRiskManager:
    def __init__(self, config):
        self.sports_rm = SportsRiskManager(config)
        self.pm_rm = PredictionMarketRiskManager(config)

    def check_total_exposure(self):
        """Ensure combined exposure doesn't exceed limits"""
        sports_exposure = self.sports_rm.get_total_exposure()
        pm_exposure = self.pm_rm.get_total_exposure()

        # Account for correlation (assume 0.2)
        total_risk = calculate_portfolio_risk(
            sports_exposure,
            pm_exposure,
            correlation=0.2
        )

        assert total_risk <= 0.15 * TOTAL_BANKROLL, "Total exposure too high"

    def allocate_capital(self):
        """Dynamic capital allocation between sports and PM"""
        # Allocate based on recent performance + opportunity set
        sports_opportunities = self.sports_rm.count_opportunities()
        pm_opportunities = self.pm_rm.count_opportunities()

        sports_recent_roi = self.sports_rm.get_recent_roi(days=30)
        pm_recent_roi = self.pm_rm.get_recent_roi(days=30)

        # Weight by opportunities * recent performance
        sports_weight = sports_opportunities * (1 + sports_recent_roi)
        pm_weight = pm_opportunities * (1 + pm_recent_roi)

        total_weight = sports_weight + pm_weight

        return {
            'sports': ACTIVE_CAPITAL * (sports_weight / total_weight),
            'prediction_markets': ACTIVE_CAPITAL * (pm_weight / total_weight)
        }
```

---

## 9. RECOMMENDED IMPLEMENTATION TIMELINE

### Month 1: Research & Infrastructure

- **Week 1-2**: Platform accounts, API access, database schema
- **Week 3-4**: Historical data collection, inefficiency analysis

**Deliverables**:

- Kalshi + Polymarket accounts funded ($500 initial)
- 6+ months historical price data downloaded
- Calibration analysis report
- Extended database schema deployed

### Month 2: Model Development

- **Week 5-6**: Build fundamental model (polling aggregation)
- **Week 7-8**: Build ensemble model, backtest framework

**Deliverables**:

- Working political election model
- Ensemble predictor combining 3+ signals
- Backtested results on historical markets
- Performance metrics: ROI, CLV, Brier score

### Month 3: Paper Trading

- **Week 9-12**: Live paper trading, daily tracking

**Success Criteria**:

- ROI >5% on 50+ paper positions
- Avg CLV >1%
- Brier score <0.15
- <10% liquidity issues

### Month 4+: Conditional Live Deployment

- **Only if paper trading succeeds**
- Start with $500 allocation
- Max $10 position sizes (2%)
- Weekly review and adjustment

**Kill Criteria** (stop if any occur):

- ROI <0% after 25 positions
- Average CLV <0%
- Brier score >0.20
- Platform regulatory issues
- >20% liquidity failures

---

## 10. SOURCES & REFERENCES

### Academic Papers

1. [Explaining the Favorite-Longshot Bias](https://www.journals.uchicago.edu/doi/abs/10.1086/655844) - Journal of Political Economy, 2010
2. [Risk aversion and favourite–longshot bias in a competitive fixed‐odds betting market](https://onlinelibrary.wiley.com/doi/10.1111/ecca.12500) - Whelan, 2024
3. [Prediction accuracy of different market structures](https://www.sciencedirect.com/science/article/abs/pii/S0169207010000105) - Franck et al., 2010
4. [The wisdom of the crowd and prediction markets](https://www.sciencedirect.com/science/article/abs/pii/S0304407620302062) - ScienceDirect, 2024
5. [Application of the Kelly Criterion to Prediction Markets](https://arxiv.org/html/2412.14144v1) - arXiv, December 2024
6. [Price formation in field prediction markets: The wisdom in the crowd](https://www.sciencedirect.com/science/article/pii/S1386418123000794) - 2024

### Industry Analysis

7. [Systematic Edges in Prediction Markets](https://quantpedia.com/systematic-edges-in-prediction-markets/) - QuantPedia
8. [Forecasting Accuracy in NBA Game Outcomes](https://polymarketanalytics.com/research/nba-sportsbooks-vs-prediction-markets) - Polymarket Research
9. [Polymarket vs Kalshi: Which Prediction Market Wins Your Trust?](https://phemex.com/blogs/polymarket-vs-kalshi-prediction-markets-analysis)
10. [The Nate Silver Effect: How Prediction Markets Unseated the Pollsters in 2024](https://markets.financialcontent.com/stocks/article/predictstreet-2026-1-18-the-nate-silver-effect-how-prediction-markets-unseated-the-pollsters-in-2024)

### Platform Resources

11. [Metaculus Prediction Resources](https://www.metaculus.com/help/prediction-resources/)
12. [How does forecast quantity impact forecast quality on Metaculus?](https://forum.effectivealtruism.org/posts/xF8EWBouJRZpRgFgu/how-does-forecast-quantity-impact-forecast-quality-on-1)
13. [Evidence on good forecasting practices from the Good Judgment Project](https://aiimpacts.org/evidence-on-good-forecasting-practices-from-the-good-judgment-project/)

### Technical Guides

14. [The Math of Prediction Markets: Binary Options, Kelly Criterion, and CLOB Pricing Mechanics](https://navnoorbawa.substack.com/p/the-math-of-prediction-markets-binary)
15. [Market Making on Prediction Markets: Complete 2026 Guide](https://newyorkcityservers.com/blog/prediction-market-making-guide)
16. [Liquidity and Prediction Market Efficiency](https://business.columbia.edu/sites/default/files-efs/pubfiles/3098/Tetlock_SSRN_Liquidity_and_Efficiency.pdf) - Tetlock, 2008

### Regulatory & Risk

17. [Prediction Market Regulation: Legal Compliance Guide](https://heitnerlegal.com/2025/10/22/prediction-market-regulation-legal-compliance-guide-for-polymarket-kalshi-and-event-contract-startups/)
18. [Why Polymarket Has Avoided Legal Pushback](https://frontofficesports.com/polymarket-avoided-legal-pushback-kalshi-sports-betting/)
19. [Prediction markets explode in 2025: Inside the Kalshi-Polymarket duopoly](https://www.theblock.co/post/383733/prediction-markets-kalshi-polymarket-duopoly-2025)

### Market Efficiency Studies

20. [Informational efficiency and behaviour within in-play prediction markets](https://www.sciencedirect.com/science/article/abs/pii/S0169207021000996)
21. [Distilling the Wisdom of Crowds: Prediction Markets vs. Prediction Polls](https://pubsonline.informs.org/doi/10.1287/mnsc.2015.2374) - Management Science
22. [Betting market efficiency and prediction in binary choice models](https://link.springer.com/article/10.1007/s10479-022-04722-3)

---

## CONCLUSION

Prediction markets offer a complementary opportunity to sports betting with uncorrelated returns and exploitable inefficiencies. The favorite-longshot bias, liquidity gaps, and delayed news pricing create systematic edges for disciplined traders.

**Key Recommendations**:

1. **Start conservatively**: Kalshi only, $500 allocation, 2% max positions
2. **Focus on favorite bias**: Back favorites <30% implied probability
3. **Build fundamental models**: Polling aggregation + Bayesian updating
4. **Adapt CLV tracking**: Use VWAP + snapshot hybrid method
5. **Manage platform risk**: Diversify across platforms, monitor regulatory developments
6. **Paper trade first**: Require 50+ positions with ROI >5% before going live

The integration with existing sports betting infrastructure is straightforward - extend existing modules for odds conversion, Kelly sizing, and risk management while adding prediction market-specific tracking.

**Next Action**: Begin Phase 1 (Infrastructure Setup) if approved to proceed with prediction market integration.
