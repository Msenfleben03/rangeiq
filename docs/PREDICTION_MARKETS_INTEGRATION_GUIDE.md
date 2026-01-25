# Prediction Markets Technical Integration Guide

**Research Date:** 2026-01-25
**Target Platform:** Python-based Sports Betting Model (sports-betting project)
**Researcher:** Technical Researcher Agent

---

## Executive Summary

Prediction markets present a compelling alternative data source and potential betting venue for sports modeling. This technical assessment evaluates five major platforms (Polymarket, Kalshi, PredictIt, Metaculus, Manifold Markets) across API accessibility, Python library maturity, data availability, and integration complexity.

**Key Finding:** Polymarket and Kalshi offer the most robust technical infrastructure for sports betting integration, with official Python clients, comprehensive APIs, and significant sports market coverage. However, legal uncertainty around sports prediction markets creates implementation risk.

---

## Platform-by-Platform API Summary

| Platform | API Type | Auth Required | Rate Limit (Free) | Historical Data | Sports Coverage | Complexity |
|----------|----------|---------------|-------------------|-----------------|-----------------|------------|
| **Polymarket** | REST + WebSocket | No (read-only) | 100 req/min | Yes (timeseries) | NFL, NBA, MLB, Props | 2/5 |
| **Kalshi** | REST | Yes (token) | Tier-based | Yes (portfolio) | NFL, NBA, MLB, NCAAB | 3/5 |
| **PredictIt** | REST | No | Not specified | CSV only (manual) | Limited | 2/5 |
| **Metaculus** | REST | Yes (token) | Not specified | Yes (forecasts) | Minimal | 3/5 |
| **Manifold** | REST | No (read-only) | Not specified | Yes (dumps) | Minimal | 2/5 |

### Complexity Rating Scale

- **1/5**: Simple REST API, minimal setup
- **2/5**: Standard REST API, straightforward authentication
- **3/5**: Multiple auth steps, tier management, or token rotation
- **4/5**: Blockchain wallet integration or complex credential setup
- **5/5**: Multi-step onboarding, KYC, or significant infrastructure

---

## Recommended Python Libraries

### 1. Polymarket - py-clob-client (RECOMMENDED FOR SPORTS)

**Installation:**

```bash
pip install py-clob-client
```

**Pros:**

- Official Polymarket client (actively maintained)
- No authentication for read-only market data
- WebSocket support for real-time updates
- Historical price data via /prices-history endpoint
- Comprehensive sports coverage (NFL, NBA, MLB, props)

**Cons:**

- Requires Python 3.9+
- Complex wallet setup for trading (blockchain-based)
- Some reported issues with historical data API

**Basic Usage:**

```python
from py_clob_client.client import ClobClient

# Read-only client (no auth)
client = ClobClient("https://clob.polymarket.com")

# Get all markets
markets = client.get_simplified_markets()

# Get current price for a token
token_id = "21742633143463906290569050155826241533067272736897614950488156847949938836455"
mid_price = client.get_midpoint(token_id)
buy_price = client.get_price(token_id, side="BUY")

# Get historical prices
# Intervals: "max", "1w", "1d", "6h", "1h"
history = client.get_price_history_with_interval(token_id, interval="1d")

# Get order book
order_book = client.get_order_book(token_id)

# Get last trade price
last_trade = client.get_last_trade_price(token_id)
```

**Sports Market Discovery:**

```python
# Filter for sports markets
all_markets = client.get_simplified_markets()
sports_markets = [m for m in all_markets['data']
                  if 'sports' in m.get('category', '').lower()]

# Search for specific games
nba_markets = [m for m in sports_markets
               if 'NBA' in m.get('question', '')]
```

---

### 2. Kalshi - kalshi-python (RECOMMENDED FOR US REGULATED)

**Installation:**

```bash
pip install kalshi-python
# For async version:
pip install kalshi-python-async
```

**Pros:**

- Official Kalshi SDK
- CFTC-regulated (legal clarity for US users)
- USD settlements (no crypto)
- Good documentation
- Growing sports market coverage

**Cons:**

- Requires authentication (API key + private key)
- Tokens expire every 30 minutes
- Rate limits vary by tier
- Premium tiers require significant trading volume

**Setup Requirements:**

1. Create Kalshi account
2. Generate API credentials at kalshi.com
3. Manage token refresh (30-min expiry)

**Documentation:** https://docs.kalshi.com/welcome

**Note:** See official docs for authentication examples. API provides access to:

- Market data and order books
- Portfolio and trade history
- Order placement and management
- Sports markets (NFL, NBA, MLB, college basketball)

---

### 3. PredictIt - predictit_markets

**Installation:**

```bash
# Install from GitHub (not on PyPI)
git clone https://github.com/tuttlepower/predictit_markets
cd predictit_markets
pip install -e .
```

**Pros:**

- Simple Python interface
- Returns Pandas DataFrame
- No authentication required
- Public API endpoint

**Cons:**

- API only shows OPEN markets (no closed markets)
- Limited historical data (90 days max via script)
- Historical requires manual CSV download per contract
- Non-commercial use only
- Minimal sports coverage compared to Polymarket/Kalshi

**Basic Usage:**

```python
import requests
import pandas as pd

# Public API endpoint
response = requests.get("https://www.predictit.org/api/marketdata/all/")
data = response.json()

# Convert to DataFrame
markets_df = pd.DataFrame(data['markets'])

# For historical data, must download CSV manually from:
# https://www.predictit.org/markets/[market-id]
```

**Historical Data Limitation:** Closed markets disappear from API. Must download CSV files individually from PredictIt website before markets close.

---

### 4. Metaculus - forecasting-tools

**Installation:**

```bash
pip install forecasting-tools  # If available on PyPI
# Or from source:
git clone https://github.com/Metaculus/forecasting-tools
```

**Pros:**

- Official Metaculus framework
- Excellent for forecasting research
- Historical forecast data with timestamps
- AI bot templates
- Active maintenance

**Cons:**

- Not a trading platform (forecasting only)
- Minimal sports coverage
- Requires API token
- Learning curve for bot framework

**Use Case:** Probability calibration research, crowd wisdom aggregation, not direct betting.

**API Access:**

- Create token at https://metaculus.com/aib
- API docs: https://www.metaculus.com/api/

---

### 5. Manifold Markets - PyManifold

**Installation:**

```bash
# Not yet on PyPI, install from source
git clone https://github.com/bcongdon/PyManifold
cd PyManifold
pip install -e .
```

**Pros:**

- Simple Python interface
- Play money (safe for testing)
- Kelly criterion calculator included
- No authentication for read-only

**Cons:**

- Play money only (not real betting)
- Not published to PyPI
- Minimal maintenance
- Limited sports coverage

**Basic Usage:**

```python
from pymanifold import ManifoldClient
from pymanifold.utils import kelly_calc

client = ManifoldClient()

# List markets
markets = client.list_markets()

# Get specific market
market = client.get_market_by_slug("market-slug")

# Calculate Kelly bet sizing
kelly_fraction = kelly_calc(
    market_probability=0.65,
    subjective_probability=0.70,
    balance=1000
)
```

**Use Case:** Model testing and development without real money risk.

---

## Data Availability Matrix

| Platform | Real-Time Prices | Historical Prices | Trade History | Volume Data | Resolution Data | Max History |
|----------|------------------|-------------------|---------------|-------------|-----------------|-------------|
| **Polymarket** | Yes (WebSocket) | Yes (API) | Yes | Yes | Yes | Varies by market |
| **Kalshi** | Yes (REST) | Yes (portfolio) | Yes (own trades) | Yes | Yes | Account history |
| **PredictIt** | Yes (REST) | CSV only | No (API) | Limited | Yes | 90 days (script) |
| **Metaculus** | Yes (REST) | Yes (forecasts) | N/A | N/A | Yes | Full history |
| **Manifold** | Yes (REST) | Yes (data dumps) | Yes | Yes | Yes | Full history |

### Data Quality Assessment

**Polymarket:**

- **Liquidity:** High for major sports (NFL Super Bowl $682M volume)
- **Update Frequency:** Real-time via WebSocket
- **Historical Depth:** API endpoint supports custom intervals (1h, 6h, 1d, 1w, max)
- **Market Coverage:** NFL, NBA, MLB games and props
- **Data Format:** JSON (REST), structured events (WebSocket)

**Kalshi:**

- **Liquidity:** Growing ($5.8B volume Nov 2025)
- **Update Frequency:** Real-time REST API
- **Historical Depth:** Portfolio history available
- **Market Coverage:** NFL, NBA, MLB, NCAAB, college football
- **Data Format:** JSON REST API with OpenAPI spec

**PredictIt:**

- **Liquidity:** Lower than Polymarket/Kalshi
- **Update Frequency:** REST API updated regularly
- **Historical Depth:** CSV download per contract (limited automation)
- **Market Coverage:** Minimal sports (politics-focused)
- **Data Format:** JSON (current), CSV (historical)

---

## Integration Complexity Ratings

### Polymarket - 2/5 (Read-Only) | 4/5 (Trading)

**Read-Only Integration:**

```python
# Dead simple - no auth required
from py_clob_client.client import ClobClient

client = ClobClient("https://clob.polymarket.com")
markets = client.get_simplified_markets()
# Done!
```

**Complexity Factors:**

- No authentication for market data (EASY)
- Standard Python package installation
- Well-documented API
- Trading requires Polygon wallet setup (COMPLEX)

**Setup Time:** 15 minutes (read-only) | 2+ hours (trading)

---

### Kalshi - 3/5

**Authentication Flow:**

```python
# 1. Get API credentials from kalshi.com
# 2. Authenticate and get token (expires 30 min)
# 3. Refresh token periodically

# See docs.kalshi.com for detailed examples
```

**Complexity Factors:**

- API key + private key authentication
- Token rotation every 30 minutes
- Tier-based rate limits
- Premium tiers require trading volume thresholds

**Setup Time:** 30-60 minutes

---

### PredictIt - 2/5

**Simple API Access:**

```python
import requests

response = requests.get("https://www.predictit.org/api/marketdata/all/")
data = response.json()
# That's it for current data
```

**Complexity Factors:**

- No authentication (EASY)
- Manual CSV downloads for history (TEDIOUS)
- Limited API features

**Setup Time:** 10 minutes (API) | 30+ min (historical data collection)

---

### Metaculus - 3/5

**Complexity Factors:**

- Requires API token from metaculus.com
- Framework-based approach (learning curve)
- Good for research, not trading

**Setup Time:** 45-90 minutes

---

### Manifold Markets - 2/5

**Complexity Factors:**

- No authentication for read-only (EASY)
- Not on PyPI (install from source)
- Play money only

**Setup Time:** 20 minutes

---

## Code Snippets for Basic Data Retrieval

### Polymarket: Real-Time Sports Odds Monitor

```python
from py_clob_client.client import ClobClient
import pandas as pd
from datetime import datetime

class PolymarketSportsMonitor:
    def __init__(self):
        self.client = ClobClient("https://clob.polymarket.com")

    def get_nfl_markets(self):
        """Fetch all active NFL markets"""
        markets = self.client.get_simplified_markets()

        nfl_markets = [
            {
                'market_id': m.get('id'),
                'question': m.get('question'),
                'end_date': m.get('endDate'),
                'volume': m.get('volume'),
                'tokens': m.get('tokens', [])
            }
            for m in markets.get('data', [])
            if 'NFL' in m.get('question', '') or
               'nfl' in m.get('category', '').lower()
        ]

        return pd.DataFrame(nfl_markets)

    def get_current_odds(self, token_id):
        """Get current betting odds for a token"""
        try:
            mid = self.client.get_midpoint(token_id)
            buy = self.client.get_price(token_id, side="BUY")
            sell = self.client.get_price(token_id, side="SELL")

            return {
                'timestamp': datetime.now(),
                'token_id': token_id,
                'mid_price': mid,
                'buy_price': buy,
                'sell_price': sell,
                'spread': sell - buy if sell and buy else None
            }
        except Exception as e:
            print(f"Error fetching odds for {token_id}: {e}")
            return None

    def get_historical_prices(self, token_id, interval="1d"):
        """Fetch historical price data"""
        try:
            history = self.client.get_price_history_with_interval(
                token_id,
                interval=interval
            )
            return pd.DataFrame(history)
        except Exception as e:
            print(f"Error fetching history for {token_id}: {e}")
            return None

    def monitor_market(self, token_id, update_interval=60):
        """Monitor a market and track price changes"""
        import time

        prices = []

        while True:
            odds = self.get_current_odds(token_id)
            if odds:
                prices.append(odds)
                print(f"[{odds['timestamp']}] Mid: {odds['mid_price']:.4f}, "
                      f"Spread: {odds['spread']:.4f}")

            time.sleep(update_interval)

# Usage
monitor = PolymarketSportsMonitor()

# Get all NFL markets
nfl_markets = monitor.get_nfl_markets()
print(nfl_markets.head())

# Monitor specific token
# token_id = "your-token-id-here"
# current_odds = monitor.get_current_odds(token_id)
# historical = monitor.get_historical_prices(token_id, interval="1h")
```

---

### Kalshi: Sports Market Data Collection

```python
# Note: Requires authentication setup - see docs.kalshi.com
# This is a conceptual example

import requests
import pandas as pd

class KalshiSportsAPI:
    """
    Kalshi API wrapper for sports markets
    Requires: API key from kalshi.com
    """

    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.kalshi.com/v1"
        self.token = None
        self.authenticate()

    def authenticate(self):
        """Get authentication token (expires in 30 min)"""
        # Implementation per Kalshi docs
        pass

    def get_sports_markets(self, sport="NFL"):
        """Fetch markets for specific sport"""
        # Implementation per Kalshi docs
        pass

    def get_market_orderbook(self, market_id):
        """Get current orderbook for a market"""
        # Implementation per Kalshi docs
        pass

# Usage would require Kalshi account and API credentials
```

---

### PredictIt: Simple Market Scraper

```python
import requests
import pandas as pd

def get_predictit_markets():
    """Fetch all current PredictIt markets"""
    url = "https://www.predictit.org/api/marketdata/all/"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        markets = []
        for market in data.get('markets', []):
            for contract in market.get('contracts', []):
                markets.append({
                    'market_id': market['id'],
                    'market_name': market['name'],
                    'contract_id': contract['id'],
                    'contract_name': contract['name'],
                    'last_trade_price': contract.get('lastTradePrice'),
                    'best_buy_yes': contract.get('bestBuyYesCost'),
                    'best_sell_yes': contract.get('bestSellYesCost'),
                    'last_close_price': contract.get('lastClosePrice'),
                })

        return pd.DataFrame(markets)

    except requests.exceptions.RequestException as e:
        print(f"Error fetching PredictIt data: {e}")
        return None

# Usage
markets_df = get_predictit_markets()
print(markets_df.head())

# Filter for sports if any
sports_markets = markets_df[
    markets_df['market_name'].str.contains('NFL|NBA|MLB', case=False, na=False)
]
```

---

## Integration with Sports Betting Platform

### Recommended Architecture

```python
# sports_betting/prediction_markets/base.py

from abc import ABC, abstractmethod
import pandas as pd

class PredictionMarketAPI(ABC):
    """Base class for prediction market integrations"""

    @abstractmethod
    def get_markets(self, sport=None):
        """Fetch available markets, optionally filtered by sport"""
        pass

    @abstractmethod
    def get_current_odds(self, market_id):
        """Get current odds/prices for a market"""
        pass

    @abstractmethod
    def get_historical_data(self, market_id, start_date=None, end_date=None):
        """Fetch historical price data"""
        pass

    def calculate_implied_probability(self, price):
        """
        Convert prediction market price to implied probability
        Polymarket/Kalshi: price is already probability (0-1 or 0-100)
        """
        if price > 1:
            return price / 100  # Convert percentage to decimal
        return price

    def calculate_edge(self, market_price, model_probability):
        """Calculate edge: model probability - market probability"""
        market_prob = self.calculate_implied_probability(market_price)
        return model_probability - market_prob


# sports_betting/prediction_markets/polymarket.py

from py_clob_client.client import ClobClient
from .base import PredictionMarketAPI

class PolymarketAPI(PredictionMarketAPI):
    """Polymarket integration for sports betting platform"""

    def __init__(self):
        self.client = ClobClient("https://clob.polymarket.com")

    def get_markets(self, sport=None):
        markets = self.client.get_simplified_markets()

        if sport:
            return [m for m in markets['data']
                   if sport.upper() in m.get('question', '').upper()]

        return markets['data']

    def get_current_odds(self, token_id):
        return {
            'mid': self.client.get_midpoint(token_id),
            'buy': self.client.get_price(token_id, side="BUY"),
            'sell': self.client.get_price(token_id, side="SELL")
        }

    def get_historical_data(self, token_id, start_date=None, end_date=None):
        # Use interval-based or timestamp-based history
        return self.client.get_price_history_with_interval(
            token_id,
            interval="1d"
        )


# sports_betting/pipelines/prediction_market_pipeline.py

from prediction_markets.polymarket import PolymarketAPI
from betting.clv import calculate_clv
import pandas as pd

class PredictionMarketPipeline:
    """
    Pipeline for integrating prediction market data with betting models
    """

    def __init__(self):
        self.polymarket = PolymarketAPI()

    def fetch_nfl_markets(self):
        """Get current NFL markets from Polymarket"""
        markets = self.polymarket.get_markets(sport="NFL")
        return pd.DataFrame(markets)

    def compare_to_model(self, market_id, token_id, model_probability):
        """
        Compare model prediction to market price
        Calculate edge and expected value
        """
        odds = self.polymarket.get_current_odds(token_id)
        market_prob = odds['mid']  # Polymarket prices are probabilities

        edge = model_probability - market_prob

        return {
            'market_id': market_id,
            'model_probability': model_probability,
            'market_probability': market_prob,
            'edge': edge,
            'ev_positive': edge > 0,
            'buy_price': odds['buy'],
            'sell_price': odds['sell']
        }

    def track_clv(self, token_id, entry_price):
        """
        Track closing line value for prediction market bets
        """
        current_odds = self.polymarket.get_current_odds(token_id)
        closing_price = current_odds['mid']

        # CLV calculation for prediction markets
        clv = (closing_price - entry_price) / entry_price

        return clv
```

---

## Cost Considerations

### Free Tier Access

| Platform | Free Tier | Limitations | Paid Tiers |
|----------|-----------|-------------|------------|
| **Polymarket** | Yes | 100 req/min, 30-day history | $99/mo (WebSocket, extended history) |
| **Kalshi** | Yes (Standard) | Tier-based rate limits | Premier/Prime (requires volume) |
| **PredictIt** | Yes | Non-commercial use, attribution required | N/A (trading account fees) |
| **Metaculus** | Yes | Not specified | N/A |
| **Manifold** | Yes | Play money only | N/A |

### Hidden Costs

1. **Polymarket Trading:**
   - Gas fees on Polygon (typically $0.01-0.10 per transaction)
   - USDC approval transactions (one-time setup)
   - Spread costs (difference between buy/sell prices)

2. **Kalshi Trading:**
   - No gas fees (USD-based)
   - Exchange fees on trades (check kalshi.com for fee structure)
   - Higher rate limits require trading volume thresholds

3. **Data Storage:**
   - Historical data can be large (consider local database)
   - API rate limits may require caching strategies

---

## Sports Market Coverage Comparison

### Polymarket (Best Sports Coverage)

**NFL:**

- Super Bowl Champion 2026 ($682M volume)
- Individual game moneylines
- Player props (TDs, yards, etc.)
- Futures markets

**NBA:**

- 2026 NBA Champion ($171M volume)
- Game-by-game moneylines
- Player props
- Season-long futures

**MLB:**

- Regular season games
- Player props
- Playoff markets
- Futures

**Coverage Rating:** 5/5

---

### Kalshi (Growing Sports Coverage)

**NFL:**

- Single-game moneylines
- Season futures

**NBA:**

- Single-game moneylines (recently launched)
- Season futures

**NCAAB:**

- College basketball games
- March Madness markets
- Tournament futures

**MLB:**

- Games and futures

**Coverage Rating:** 4/5 (Growing rapidly, CFTC-regulated)

---

### PredictIt (Minimal Sports)

**Coverage:** Politics-focused, minimal sports markets

**Coverage Rating:** 1/5

---

### Metaculus (Minimal Sports)

**Coverage:** Forecasting-focused, occasional sports tournaments

**Coverage Rating:** 1/5

---

### Manifold Markets (Minimal Sports)

**Coverage:** User-created markets, sporadic sports coverage

**Coverage Rating:** 2/5 (Play money, testing purposes)

---

## Regulatory Considerations

### Legal Landscape (2026)

**KEY ISSUE:** Prediction markets claiming CFTC jurisdiction are facing state-level challenges for sports betting.

**Polymarket:**

- Not available to US users for trading (can view markets)
- Operates on Polygon blockchain
- No US state licensing conflicts (geo-blocked)

**Kalshi:**

- CFTC-regulated as derivatives exchange
- Argues federal law preempts state gambling statutes
- Facing lawsuits from Nevada, New Jersey, Maryland
- Legal resolution expected 2027+ (potentially Supreme Court)

**Risk Assessment:**

- Using APIs for **data collection**: LOW RISK
- Using platforms for **real trading**: MEDIUM-HIGH RISK (legal uncertainty)
- Integration for **model comparison**: LOW RISK

**Recommendation:** Use prediction market data for model validation and CLV tracking, but consult legal counsel before using as primary betting venue.

---

## Implementation Roadmap

### Phase 1: Data Collection (Week 1-2)

```bash
# Install required packages
pip install py-clob-client pandas requests

# Test Polymarket API
python scripts/test_polymarket_api.py

# Build sports market scraper
python pipelines/polymarket_scraper.py --sport NFL
```

### Phase 2: Historical Analysis (Week 3-4)

```bash
# Fetch historical data for key markets
python pipelines/fetch_polymarket_history.py --start-date 2024-09-01

# Compare prediction market prices to model probabilities
python analysis/prediction_market_analysis.py
```

### Phase 3: Live Monitoring (Week 5-6)

```bash
# Set up real-time monitoring
python monitoring/polymarket_monitor.py --sport NFL --update-interval 300

# Track CLV for prediction markets vs sportsbooks
python tracking/clv_comparison.py
```

### Phase 4: Integration (Week 7-8)

```bash
# Integrate with betting workflow
python pipelines/betting_workflow.py --include-prediction-markets

# Generate daily reports comparing sportsbook vs prediction market odds
python reports/odds_comparison.py
```

---

## Sample Integration Test

Create `scripts/test_polymarket_api.py`:

```python
from py_clob_client.client import ClobClient
import pandas as pd
from datetime import datetime

def test_polymarket_integration():
    """Test Polymarket API integration"""

    print("="*60)
    print("POLYMARKET API INTEGRATION TEST")
    print("="*60)

    # Initialize client
    client = ClobClient("https://clob.polymarket.com")

    # Test 1: API health check
    print("\n[TEST 1] API Health Check")
    try:
        ok = client.get_ok()
        server_time = client.get_server_time()
        print(f"Status: {ok}")
        print(f"Server Time: {datetime.fromtimestamp(server_time)}")
        print("PASSED")
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    # Test 2: Fetch markets
    print("\n[TEST 2] Fetch Markets")
    try:
        markets = client.get_simplified_markets()
        total_markets = len(markets.get('data', []))
        print(f"Total markets: {total_markets}")
        print("PASSED")
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    # Test 3: Filter sports markets
    print("\n[TEST 3] Filter Sports Markets")
    try:
        sports_keywords = ['NFL', 'NBA', 'MLB', 'NHL']
        sports_markets = [
            m for m in markets['data']
            if any(kw in m.get('question', '').upper() for kw in sports_keywords)
        ]
        print(f"Sports markets found: {len(sports_markets)}")

        # Show sample
        if sports_markets:
            sample = sports_markets[0]
            print(f"\nSample Market:")
            print(f"  Question: {sample.get('question')}")
            print(f"  Category: {sample.get('category')}")
            print(f"  Volume: ${sample.get('volume', 0):,.2f}")
            print(f"  End Date: {sample.get('endDate')}")

        print("PASSED")
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    # Test 4: Get current odds (if sports market exists)
    print("\n[TEST 4] Fetch Current Odds")
    try:
        if sports_markets and sports_markets[0].get('tokens'):
            token = sports_markets[0]['tokens'][0]
            token_id = token.get('token_id')

            if token_id:
                mid = client.get_midpoint(token_id)
                buy = client.get_price(token_id, side="BUY")
                sell = client.get_price(token_id, side="SELL")

                print(f"Token: {token.get('outcome')}")
                print(f"  Mid Price: {mid}")
                print(f"  Buy Price: {buy}")
                print(f"  Sell Price: {sell}")
                print(f"  Spread: {sell - buy if sell and buy else 'N/A'}")
                print("PASSED")
            else:
                print("SKIPPED: No token_id available")
        else:
            print("SKIPPED: No sports markets with tokens")
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    print("\n" + "="*60)
    print("ALL TESTS PASSED")
    print("="*60)

    return True

if __name__ == "__main__":
    success = test_polymarket_integration()
    exit(0 if success else 1)
```

Run test:

```bash
python scripts/test_polymarket_api.py
```

---

## Conclusion

### Recommended Platform for Sports Betting Integration

**PRIMARY:** Polymarket (py-clob-client)

- Most comprehensive sports coverage
- Mature Python client
- No authentication for read-only data
- Historical price API
- Real-time WebSocket support

**SECONDARY:** Kalshi (kalshi-python)

- CFTC-regulated (legal clarity)
- USD-based (no crypto friction)
- Growing sports market coverage
- Good for US-based users concerned about regulation

**TESTING:** Manifold Markets (PyManifold)

- Play money platform
- Safe for model testing
- No real money risk

### Integration Priority

1. **Immediate:** Set up Polymarket read-only API for data collection
2. **Week 1-2:** Build historical data pipeline
3. **Week 3-4:** Compare prediction market prices to model probabilities
4. **Week 5-6:** Track CLV differences between sportsbooks and prediction markets
5. **Future:** Consider Kalshi integration if legal clarity improves

### Data Usage Recommendations

- Use prediction market prices as **alternative probability estimates**
- Track **CLV** on prediction markets vs traditional sportsbooks
- Identify **market inefficiencies** where prediction markets and sportsbooks diverge
- Validate **model calibration** against crowd-sourced probabilities
- Monitor **sharp money movement** via volume and price changes

---

## Sources

1. [Polymarket py-clob-client GitHub](https://github.com/Polymarket/py-clob-client)
2. [Polymarket Developer Quickstart](https://docs.polymarket.com/quickstart/overview)
3. [polymarket-apis PyPI](https://pypi.org/project/polymarket-apis/)
4. [Polymarket Documentation](https://docs.polymarket.com/)
5. [Polymarket API Rate Limits](https://docs.polymarket.com/quickstart/introduction/rate-limits)
6. [Polymarket Historical Timeseries Data](https://docs.polymarket.com/developers/CLOB/timeseries)
7. [Kalshi API Documentation](https://docs.kalshi.com/welcome)
8. [kalshi-python PyPI](https://pypi.org/project/kalshi-python/)
9. [Kalshi API | Help Center](https://help.kalshi.com/kalshi-api)
10. [Kalshi API Rate Limits](https://docs.kalshi.com/getting_started/rate_limits)
11. [PredictIt API Documentation](https://predictit.freshdesk.com/support/solutions/articles/12000001878)
12. [predictit_markets GitHub](https://github.com/tuttlepower/predictit_markets)
13. [Metaculus forecasting-tools GitHub](https://github.com/Metaculus/forecasting-tools)
14. [Metaculus API](https://www.metaculus.com/api/)
15. [PyManifold GitHub](https://github.com/bcongdon/PyManifold)
16. [Manifold API Documentation](https://docs.manifold.markets/api)
17. [Prediction-Markets-Data GitHub](https://github.com/arbbets/Prediction-Markets-Data)
18. [poly_data GitHub](https://github.com/warproxxx/poly_data)
19. [Polymarket Sports Markets](https://polymarket.com/search/sports)
20. [Kalshi Sports Markets](https://kalshi.com/sports)
21. [Legal Sports Report: Prediction Markets 2026](https://www.legalsportsreport.com/249858/what-could-2026-bring-for-sports-prediction-markets/)
22. [Prediction Markets vs Sports Betting | Arch](https://archlending.com/blog/prediction-markets-vs-sports-betting)

---

**End of Technical Integration Guide**
