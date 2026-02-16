# KenPom College Basketball Data Research Report

**Research Date:** 2026-02-13
**Purpose:** Evaluate KenPom data access options for Python sports betting model
**Focus:** Historical data (2020-2025), point-in-time ratings, Python integration

---

## Executive Summary

KenPom ratings are the gold standard for college basketball analytics, but accessing the data requires either a paid
subscription ($24.95/year) or web scraping (unreliable). **Recommendation: Purchase KenPom API subscription for
$24.95/year** - the cost is negligible compared to development time, and the data quality is unmatched.

For free alternatives, **Barttorvik (T-Rank)** provides nearly identical metrics via the `toRvik` R package (accessible
from Python via `rpy2`). ESPN BPI is also free but less granular.

The best approach for this project: **Start with KenPom subscription + add Four Factors features from ESPN box scores.**

---

## 1. KenPom Data Access

### Official API

| Attribute | Details |
|-----------|---------|
| **Available** | YES |
| **Cost** | $24.95/year |
| **Registration** | https://kenpom.com/register-api.php |
| **Authentication** | API key (provided after purchase) |
| **Payment** | Stripe |
| **Documentation** | Provided via link after API key issued |

Terms of Service:

- Annual subscription, non-recurring (must renew yearly)
- Limited to fixed number of machines/simultaneous logins
- Full terms: https://kenpom.com/terms.php

### CSV Export

No direct CSV export available. Must use API or web scraping.

### Historical Data Availability

| Data Type | Availability | Notes |
|-----------|--------------|-------|
| **Full statistics** | 2002-present | Complete team stats for all D-I teams |
| **Daily snapshots** | 2011-12 season onward | CRITICAL: Point-in-time ratings before games |
| **Archive access** | Via API or web archive pages | Example: ratings as of 2018-11-22 |
| **WayBack Machine** | 2007-present | Variable reliability |

**Key for Betting Models:** Daily snapshots allow you to get ratings as they were BEFORE each game, preventing
look-ahead bias. This is essential for backtesting.

---

## 2. KenPom Metrics Explained

### Core Metrics

#### AdjO (Adjusted Offensive Efficiency)

- **Definition:** Points scored per 100 possessions, adjusted for opponent defense quality
- **Interpretation:** Higher is better
- **Predictive Value:** HIGH - core predictor of offensive performance
- **Typical Range:** 90-120 (100 = average D-I offense)

#### AdjD (Adjusted Defensive Efficiency)

- **Definition:** Points allowed per 100 possessions, adjusted for opponent offense quality
- **Interpretation:** Lower is better
- **Predictive Value:** HIGH - core predictor of defensive performance
- **Typical Range:** 90-120 (100 = average D-I defense)

#### AdjEM (Adjusted Efficiency Margin)

- **Definition:** AdjO minus AdjD
- **Formula:** `AdjEM = AdjO - AdjD`
- **Interpretation:** Expected point margin vs average D-I team over 100 possessions
- **Predictive Value:** VERY HIGH - single best team strength metric
- **Typical Range:** -30 to +30 (top teams: +20 to +30, bottom teams: -20 to -30)
- **Advantage:** Linear measure - easy to compare teams and predict point spreads

#### AdjT (Adjusted Tempo)

- **Definition:** Possessions per 40 minutes, adjusted for opponent
- **Interpretation:** Pace of play indicator
- **Predictive Value:** MEDIUM - important for totals betting
- **Typical Range:** 60-75 possessions per game

### Calculation Methodology

KenPom uses **least squares regression** on 706 variables to determine adjusted ratings:

1. Calculate raw efficiency for each team in each game
2. Set up system of equations accounting for opponent strength
3. Solve using least squares to minimize prediction error
4. Apply **recency weighting** (more recent games weighted higher - exact formula proprietary)
5. Update daily during season

**Key Insight:** The adjustment accounts for opponent strength, so beating a top-10 team by 10 points is worth more than
beating a bottom-10 team by 10 points.

---

## 3. Dean Oliver's Four Factors

These are the fundamental components of basketball efficiency, used by both KenPom and Barttorvik.

### Importance Weights

1. **eFG% (Effective Field Goal %)** - 40% importance
2. **TOV% (Turnover Rate)** - 25% importance
3. **ORB% (Offensive Rebound Rate)** - 20% importance
4. **FTR (Free Throw Rate)** - 15% importance

### Formulas

| Factor | Formula | Definition |
|--------|---------|------------|
| **eFG%** | `(FGM + 0.5 * 3PM) / FGA` | Field goal % adjusted for 3-pointers |
| **TOV%** | `TOV / Possessions` | % of possessions ending in turnover |
| **ORB%** | `ORB / (ORB + Opp_DRB)` | % of available offensive rebounds grabbed |
| **FTR** | `FTA / FGA` | Free throw attempts per field goal attempt |

### Possessions Formula

College Basketball Consensus:

```text
Possessions = (FGA - OR) + TO + (0.475 * FTA)
```

Dean Oliver's Original (NBA):

```text
Possessions = (FGA - OR) + TO + (0.44 * FTA)
```

Use 0.475 for college basketball.

### Application

These factors apply to both offense and defense, creating **8 total factors**:

- Offensive eFG%, TOV%, ORB%, FTR
- Defensive eFG%, TOV%, DRB%, FTR

**Why They Matter:** These are the building blocks of efficiency. A team that shoots well (eFG%), doesn't turn it over
(TOV%), grabs offensive rebounds (ORB%), and gets to the free throw line (FTR) will score efficiently.

---

## 4. Python Packages

### kenpompy (Web Scraper)

| Attribute | Details |
|-----------|---------|
| **GitHub** | https://github.com/j-andrews7/kenpompy |
| **Install** | `pip install kenpompy` |
| **Version** | 0.3.5 (latest) |
| **Requires KenPom Subscription** | YES |
| **Method** | Web scraper (not official API) |

Status in 2026: NOT RECOMMENDED

Major Issues:

1. **Cloudflare Blocking:** AWS/Azure/VPN IPs are blocked - frequent failures
2. **Login Failures:** Authentication issues (Issues #24, #33 on GitHub)
3. **Pandas Deprecation:** FutureWarning with pandas 2.1.0+
4. **Maintenance:** No major updates in 12+ months

**Verdict:** Too unreliable for production use. Use official API instead if paying for subscription.

### hoopR-py (ESPN Data)

| Attribute | Details |
|-----------|---------|
| **GitHub** | https://github.com/saiemgilani/hoopR-py |
| **Install** | `pip install hoopR-py` |
| **Data Source** | ESPN API |
| **KenPom Data** | NO |

What It Does:

- Play-by-play data
- Box scores
- Schedules
- Live game data

**Note:** Does NOT provide KenPom ratings, but excellent for raw game data (which you already have via
`espn_ncaab_fetcher.py`).

### sportsdataverse-py

| Attribute | Details |
|-----------|---------|
| **Website** | https://sportsdataverse-py.sportsdataverse.org/ |
| **Install** | `pip install sportsdataverse-py` |
| **Data Source** | ESPN API + others |
| **KenPom Data** | NO |

Broader sports coverage than hoopR, but no KenPom data.

### CBBpy (NCAA Scraper)

| Attribute | Details |
|-----------|---------|
| **PyPI** | https://pypi.org/project/CBBpy/ |
| **Install** | `pip install CBBpy` |
| **Data Source** | NCAA.org |
| **KenPom Data** | NO |

Scrapes NCAA.org for raw stats. Useful for box scores but no efficiency ratings.

---

## 5. Free Alternatives to KenPom

### Barttorvik T-Rank

**Website:** https://barttorvik.com/
**Cost:** $22/year subscription (but free R package access exists)

#### Data Access via R Packages

##### toRvik (R Package)

| Attribute | Details |
|-----------|---------|
| **GitHub** | https://github.com/andreweatherman/toRvik |
| **Install** | `install.packages('toRvik')` (in R) |
| **Language** | R |
| **Cost** | FREE |
| **API Key** | Not required |

Data Available:

- Player game-by-game stats (70,000+ games back to 2008)
- Team ratings and efficiency metrics (AdjO, AdjD, AdjEM, AdjT)
- Game results and schedules
- Advanced metric splits
- Play-by-play shooting data
- Transfer and recruiting histories
- Game predictions

**Functions:** Nearly 30 functions
**Historical Data:** Back to 2007-08 season
**Status:** ACTIVE and maintained

##### cbbdata (R Package - Newer, Faster)

| Attribute | Details |
|-----------|---------|
| **GitHub** | https://github.com/andreweatherman/cbbdata |
| **Website** | https://cbbdata.aweatherman.com/ |
| **Install** | `remotes::install_github('andreweatherman/cbbdata')` |
| **Language** | R (Flask + Python backend) |
| **Cost** | FREE |
| **API Key** | Required (FREE) |

Data Available:

- Game-by-game player box scores and advanced metrics (back to 2008)
- Daily updated NET rankings
- Game predictions powered by Barttorvik
- Team efficiency ratings
- Comprehensive player logs

**Functions:** 26 functions
**Status:** ACTIVE - replaced toRvik in May 2023
**Note:** Faster and more efficient than toRvik

#### Comparison to KenPom

Similarities:

- Adjusted efficiency metrics (AdjO, AdjD, AdjEM, AdjT)
- Tempo-free statistics
- Opponent-adjusted ratings
- Four Factors breakdowns
- Game predictions

Differences:

- **Recency bias:** Barttorvik games lose 1% emphasis after 40 days, fully aged out at 80 days
- **Women's basketball:** Barttorvik covers women's CBB; KenPom is men's only
- **Player data:** Barttorvik has more granular player-level data
- **Methodology:** Slightly different calculation approach

**Correlation:** VERY HIGH - ratings typically within 1-2 points for most teams

**Betting Value:** Equivalent to KenPom for most purposes

#### Python Access from R Packages

Option 1: rpy2 (R-Python Bridge)

```python
import rpy2.robjects.packages as rpackages
toRvik = rpackages.importr('toRvik')

# Fetch Barttorvik ratings
ratings = toRvik.bart_ratings(year=2025)
```

Option 2: HTTP Requests to cbbdata API

```python
import requests

API_KEY = "your_free_api_key"  # pragma: allowlist secret
url = f"https://cbbdata.aweatherman.com/api/ratings?year=2025&key={API_KEY}"
response = requests.get(url)
ratings = response.json()
```

**Estimated Effort:** 8-12 hours (includes R setup and integration)

---

### ESPN BPI (Basketball Power Index)

**Website:** https://www.espn.com/mens-college-basketball/bpi
**Cost:** FREE

#### Data Available

- Team strength ratings (BPI score)
- Offensive and defensive ratings
- Strength of schedule
- Projected wins
- Tournament probabilities
- Game predictions with win probabilities

#### API Access

**Official API:** No
**Hidden API:** YES

Endpoint Example:

```text
.../events/{eventId}/competitions/{eventId}/probabilities
```

**Auth Required:** No
**Rate Limit:** Unknown - use 2 req/sec to be safe

#### Methodology

- **Purpose:** Best predictor of team performance going forward
- **Factors:** Opponent strength, pace, site, travel distance, rest days, altitude
- **Simulations:** 10,000 simulations per season for projections
- **Updates:** Daily

#### Comparison to KenPom

Advantages:

- FREE and no subscription required
- Includes game predictions and win probabilities
- Forward-looking projections
- Easy web access

Disadvantages:

- Less granular than KenPom (no Four Factors)
- Methodology not fully transparent
- No historical archives beyond current season
- API is undocumented and may change

**Correlation:** HIGH - BPI correlates strongly with KenPom AdjEM

**Betting Value:** Good for quick assessments, less detail than KenPom

**Python Access:** ESPN Core API via `hoopR-py` or direct HTTP requests (you already have `espn_ncaab_fetcher.py`
implemented)

---

### NCAA Stats API (Community)

**Cost:** FREE
**Official:** No (community-maintained scrapers)

#### ncaa-api by henrygd

| Attribute | Details |
|-----------|---------|
| **GitHub** | https://github.com/henrygd/ncaa-api |
| **API URL** | https://ncaa-api.henrygd.me/openapi |
| **Language** | JavaScript (API server) |
| **Rate Limit** | 5 requests/second per IP |

Data Available:

- Live scores
- Box scores
- Play-by-play
- Team stats
- Rankings
- Standings
- Schedules
- Historical data
- Team logos

**Method:** REST API - scrapes NCAA.org
**Reliability:** GOOD - actively maintained

#### NCAA-API by dwillis

| Attribute | Details |
|-----------|---------|
| **GitHub** | https://github.com/dwillis/NCAA-API |
| **Language** | Python |
| **Method** | Python application to turn NCAA web stats into API |

Limitations:

- No efficiency ratings (just raw stats)
- No opponent adjustments
- Must calculate advanced metrics yourself

**Use Case:** Raw box score data for computing your own efficiency metrics

---

## 6. Computing Custom Pomeroy-Style Metrics

**Feasibility:** YES - Possible to calculate adjusted efficiency from raw data
**Difficulty:** MEDIUM-HIGH
**Estimated Effort:** 20-30 hours for simplified version, 40-60 hours for full implementation

### Required Data

- Game-by-game box scores
- Field goals made/attempted (2pt and 3pt separate)
- Free throws made/attempted
- Offensive and defensive rebounds
- Turnovers
- Personal fouls
- Final scores
- Game dates (for chronological ordering)

**Good News:** You already have this via `espn_ncaab_fetcher.py`!

### Calculation Steps

#### Step 1: Calculate Possessions

```python
def calculate_possessions(fga, oreb, tov, fta):
    """College basketball consensus formula"""
    return (fga - oreb) + tov + (0.475 * fta)
```

#### Step 2: Calculate Raw Efficiency

```python
def offensive_efficiency(points, possessions):
    """Points per 100 possessions"""
    return (points / possessions) * 100

def defensive_efficiency(points_allowed, possessions):
    """Points allowed per 100 possessions"""
    return (points_allowed / possessions) * 100
```

#### Step 3: Adjust for Opponent Strength

Simple Iterative Approach:

```python
def adjust_for_opponents(games_df, iterations=10):
    """
    Iteratively adjust ratings for opponent strength

    games_df should have columns:
    - team_id
    - opponent_id
    - offensive_efficiency (raw)
    - defensive_efficiency (raw)
    """
    # Initialize ratings as raw efficiency averages
    ratings = games_df.groupby('team_id').agg({
        'offensive_efficiency': 'mean',
        'defensive_efficiency': 'mean'
    })

    for i in range(iterations):
        # Adjust each game's rating for opponent quality
        games_df['adj_offense'] = games_df['offensive_efficiency'] - \
            games_df['opponent_id'].map(ratings['defensive_efficiency']) + 100

        games_df['adj_defense'] = games_df['defensive_efficiency'] - \
            games_df['opponent_id'].map(ratings['offensive_efficiency']) + 100

        # Update ratings
        ratings = games_df.groupby('team_id').agg({
            'adj_offense': 'mean',
            'adj_defense': 'mean'
        })

    return ratings
```

Advanced Least Squares Approach:

```python
from scipy.optimize import least_squares

def adjusted_efficiency_least_squares(games_df):
    """
    Full least squares regression for adjusted efficiency
    Similar to KenPom methodology
    """
    teams = games_df['team_id'].unique()
    n_teams = len(teams)

    # Initial guess: all teams are average (100)
    x0 = np.full(n_teams * 2, 100)

    def residuals(x):
        """
        Calculate residuals between predicted and actual efficiency
        x contains: [offense_1, offense_2, ..., offense_n, defense_1, ..., defense_n]
        """
        offense_ratings = x[:n_teams]
        defense_ratings = x[n_teams:]

        errors = []
        for _, game in games_df.iterrows():
            team_idx = np.where(teams == game['team_id'])[0][0]
            opp_idx = np.where(teams == game['opponent_id'])[0][0]

            predicted_offense = offense_ratings[team_idx] + \
                (100 - defense_ratings[opp_idx])

            predicted_defense = defense_ratings[team_idx] + \
                (100 - offense_ratings[opp_idx])

            errors.append(game['offensive_efficiency'] - predicted_offense)
            errors.append(game['defensive_efficiency'] - predicted_defense)

        return errors

    result = least_squares(residuals, x0)

    offense_ratings = result.x[:n_teams]
    defense_ratings = result.x[n_teams:]

    return pd.DataFrame({
        'team_id': teams,
        'adj_offense': offense_ratings,
        'adj_defense': defense_ratings,
        'adj_em': offense_ratings - defense_ratings
    })
```

#### Step 4: Calculate Four Factors

```python
def calculate_four_factors(box_score):
    """
    Calculate Dean Oliver's Four Factors from box score
    """
    # Effective Field Goal %
    efg = (box_score['fgm'] + 0.5 * box_score['fg3m']) / box_score['fga']

    # Turnover Rate
    possessions = calculate_possessions(
        box_score['fga'],
        box_score['oreb'],
        box_score['tov'],
        box_score['fta']
    )
    tov_rate = box_score['tov'] / possessions

    # Offensive Rebound Rate
    orb_rate = box_score['oreb'] / (box_score['oreb'] + box_score['opp_dreb'])

    # Free Throw Rate
    ftr = box_score['fta'] / box_score['fga']

    return {
        'efg': efg,
        'tov_rate': tov_rate,
        'orb_rate': orb_rate,
        'ftr': ftr
    }
```

### Implementation Complexity Levels

#### Simple Version (LOW difficulty)

- **What:** Raw efficiency without opponent adjustment
- **Effort:** 2-4 hours
- **Accuracy:** ~0.70 correlation with KenPom
- **Use Case:** Quick baseline, not suitable for betting

#### Intermediate Version (MEDIUM difficulty)

- **What:** Opponent-adjusted efficiency using iterative method
- **Effort:** 8-12 hours
- **Accuracy:** ~0.85-0.90 correlation with KenPom
- **Use Case:** Reasonable approximation for betting

#### Advanced Version (HIGH difficulty)

- **What:** Full least squares with recency weights and home court adjustment
- **Effort:** 40-60 hours (development + testing + validation)
- **Accuracy:** ~0.95+ correlation with KenPom
- **Use Case:** Production betting model, full independence from external services

---

## 7. Implementation Recommendations

### Scenario 1: Need KenPom Data with Minimal Development Effort

**Recommended Solution:** Purchase KenPom API subscription ($24.95/year)

Rationale:

- Official API is most reliable
- Cost is negligible for betting project ($24.95 << potential profits)
- Saves 20+ hours development time
- Get official historical archives back to 2011-12 season
- Daily updates during season

Implementation Steps:

1. Register at kenpom.com/register-api.php
2. Receive API key and documentation link
3. Build simple Python wrapper for API endpoints
4. Fetch historical archives (2020-2025)
5. Store in SQLite database (`team_ratings` table)
6. Update daily during season via scheduled script

**Estimated Effort:** 4-6 hours

Code Structure:

```python
# pipelines/kenpom_fetcher.py
class KenPomAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://kenpom.com/api"  # Replace with actual endpoint

    def fetch_ratings(self, date=None):
        """Fetch ratings for specific date (point-in-time)"""
        pass

    def fetch_historical(self, season):
        """Fetch full season of daily snapshots"""
        pass

    def fetch_four_factors(self, team_id, season):
        """Fetch Four Factors breakdown"""
        pass
```

---

### Scenario 2: Want Free Alternative with Similar Predictive Power

**Recommended Solution:** Use Barttorvik via toRvik (R) + rpy2 (Python bridge)

Rationale:

- FREE (no subscription cost)
- Actively maintained
- Correlates highly with KenPom (~0.95+)
- Extensive historical data (back to 2008)
- 30+ functions for various metrics

Implementation Steps:

1. Install R: https://cran.r-project.org/
2. Install toRvik package: `install.packages('toRvik')`
3. Install rpy2 in Python: `pip install rpy2`
4. Write Python wrapper to call R functions
5. Fetch Barttorvik ratings via toRvik
6. Convert to pandas DataFrames
7. Store in SQLite database

**Estimated Effort:** 8-12 hours (includes R setup)

Code Structure:

```python
# pipelines/barttorvik_fetcher.py
import rpy2.robjects.packages as rpackages
import rpy2.robjects as robjects
import pandas as pd

class BarttovikFetcher:
    def __init__(self):
        self.toRvik = rpackages.importr('toRvik')

    def fetch_ratings(self, season=2025):
        """Fetch T-Rank ratings for season"""
        ratings_r = self.toRvik.bart_ratings(year=season)
        ratings_df = self._r_to_pandas(ratings_r)
        return ratings_df

    def fetch_player_stats(self, season=2025):
        """Fetch player game logs"""
        stats_r = self.toRvik.bart_player_game(year=season)
        stats_df = self._r_to_pandas(stats_r)
        return stats_df

    def _r_to_pandas(self, r_df):
        """Convert R dataframe to pandas"""
        with robjects.conversion.localconverter(
            robjects.default_converter + robjects.pandas2ri.converter
        ):
            pd_df = robjects.conversion.rpy2py(r_df)
        return pd_df
```

**Alternative:** Use cbbdata R package with free API key (easier than toRvik)

---

### Scenario 3: Want to Compute Custom Efficiency Metrics

**Recommended Solution:** Use ESPN box scores + implement simplified adjusted efficiency

Rationale:

- Already fetching ESPN data (`espn_ncaab_fetcher.py` in place)
- Full control over methodology
- Educational value - understand mechanics
- Can experiment with modifications (different recency weights, etc.)
- Complete independence from external services

Implementation Steps:

1. Extend `espn_ncaab_fetcher.py` to pull full box scores (may already have this)
2. Calculate possessions for each game
3. Calculate raw offensive/defensive efficiency
4. Implement iterative opponent adjustment (intermediate version)
5. Add Four Factors calculations
6. Validate against KenPom/Barttorvik (correlation check)
7. If correlation < 0.85, implement least squares version

**Estimated Effort:** 20-30 hours (intermediate version)

Code Structure:

```python
# models/efficiency_calculator.py
class EfficiencyCalculator:
    def __init__(self, games_df):
        self.games_df = games_df
        self.ratings = None

    def calculate_raw_efficiency(self):
        """Step 1: Calculate raw efficiency for all games"""
        pass

    def adjust_for_opponents(self, iterations=10):
        """Step 2: Iteratively adjust for opponent strength"""
        pass

    def calculate_four_factors(self):
        """Step 3: Add Four Factors for each team"""
        pass

    def export_to_db(self, db_path):
        """Save to team_ratings table"""
        pass
```

Validation:

```python
# After computing custom ratings, validate against KenPom
import scipy.stats as stats

correlation = stats.pearsonr(
    custom_ratings['adj_em'],
    kenpom_ratings['AdjEM']
)

print(f"Correlation with KenPom: {correlation[0]:.3f}")
# Target: > 0.85 for production use
```

---

### Scenario 4: Want Best of Both Worlds (Free + Reliable)

**Recommended Solution:** Use ESPN BPI + Barttorvik + Four Factors as ensemble

Rationale:

- Diversifies data sources (reduces single-point-of-failure risk)
- Combines free ratings with custom features
- Ensemble models often outperform single sources
- Free and maintainable long-term

Implementation Steps:

1. Fetch ESPN BPI ratings via Core API (already have ESPN fetcher)
2. Fetch Barttorvik ratings via toRvik/cbbdata
3. Compute Four Factors from ESPN box scores
4. Create ensemble features:
   - BPI_rating
   - Barttorvik_AdjEM
   - Elo_rating (already have)
   - Four_Factors (eFG%, TOV%, ORB%, FTR)
5. Train model on ensemble features
6. Backtest and validate with Gatekeeper

**Estimated Effort:** 15-20 hours

Feature Engineering:

```python
# features/ensemble_ratings.py
def create_ensemble_features(game_id):
    """
    Combine multiple rating systems for single game
    """
    # Team A features
    features = {
        'team_a_elo': get_elo_rating(team_a_id, game_date),
        'team_a_bpi': get_bpi_rating(team_a_id, game_date),
        'team_a_torvik_adjEM': get_torvik_rating(team_a_id, game_date),
        'team_a_efg': get_four_factor(team_a_id, 'efg', game_date),
        'team_a_tov': get_four_factor(team_a_id, 'tov', game_date),
        'team_a_orb': get_four_factor(team_a_id, 'orb', game_date),
        'team_a_ftr': get_four_factor(team_a_id, 'ftr', game_date),
    }

    # Team B features (opponent)
    features.update({
        'team_b_elo': get_elo_rating(team_b_id, game_date),
        'team_b_bpi': get_bpi_rating(team_b_id, game_date),
        # ... etc
    })

    # Differential features
    features['elo_diff'] = features['team_a_elo'] - features['team_b_elo']
    features['bpi_diff'] = features['team_a_bpi'] - features['team_b_bpi']
    features['torvik_diff'] = features['team_a_torvik_adjEM'] - features['team_b_torvik_adjEM']

    return features
```

---

## 8. Final Recommendation for This Project

### Phase 1: IMMEDIATE (This Week)

**Action:** Purchase KenPom API subscription ($24.95)

Justification:

- Fastest path to high-quality data
- Cost is minimal (less than 1 unit bet)
- Saves 20-40 hours development time
- Get point-in-time historical ratings (critical for backtest)
- Can re-run backtest with real KenPom features

**Priority:** HIGH
**Timeline:** 1-2 days to implement
Deliverables:

- `pipelines/kenpom_fetcher.py` - API wrapper
- Historical data in `data/processed/kenpom_ratings_2020_2025.parquet`
- Updated `team_ratings` table in SQLite

---

### Phase 2: SHORT-TERM (Next 1-2 Weeks)

**Action:** Add Four Factors as features to existing Elo model

Justification:

- Already have ESPN box score capability
- Four Factors are proven predictors (40% + 25% + 20% + 15% = 100%)
- Low effort, high reward
- Can combine with Elo for ensemble approach

**Priority:** MEDIUM
**Timeline:** 1 week
Deliverables:

- `features/four_factors.py` - Calculate eFG%, TOV%, ORB%, FTR
- Updated model with 12 new features (4 factors × 2 teams × offense/defense)
- Re-run backtest and Gatekeeper validation

Expected Impact:

- Improve Sharpe ratio (target: -0.86 → 0.5+)
- Improve CLV (target: 0.57% → 1.5%+)
- Reduce false positives (currently 3,813 bets is too many)

---

### Phase 3: MEDIUM-TERM (Next 2-4 Weeks)

**Action:** Implement Barttorvik data fetcher via toRvik as free backup

Justification:

- Reduces dependence on KenPom (single point of failure)
- Provides validation dataset (compare KenPom vs Barttorvik predictions)
- Free long-term solution
- Can sell/share model more easily (no KenPom subscription required by users)

**Priority:** MEDIUM
**Timeline:** 2 weeks
Deliverables:

- `pipelines/barttorvik_fetcher.py` - R bridge via rpy2
- Correlation analysis (KenPom vs Barttorvik ratings)
- Ensemble model (KenPom + Barttorvik + Elo)

---

### Phase 4: LONG-TERM (Future Research Project)

**Action:** Build custom adjusted efficiency calculator for full control

Justification:

- Educational value (deep understanding of efficiency metrics)
- Complete independence from external services
- Can experiment with modifications (e.g., different recency weights for live betting)
- Potential IP/publication if results are novel

**Priority:** LOW
**Timeline:** 1 month (background research project)
Deliverables:

- `models/custom_efficiency.py` - Full least squares implementation
- Research paper comparing custom vs KenPom methodology
- Open-source contribution to sports analytics community

---

## 9. Key Takeaways

1. **KenPom subscription ($24.95/year) is worth it** - minimal cost, maximum data quality
2. **Barttorvik is excellent free alternative** - correlates 0.95+ with KenPom via toRvik R package
3. **Four Factors are low-hanging fruit** - already have ESPN data, proven predictors
4. **kenpompy package is broken in 2026** - Cloudflare issues make it unreliable
5. **Computing custom efficiency is feasible** but 20-60 hours effort depending on complexity
6. **Ensemble approach is best** - combine KenPom + Barttorvik + Elo + Four Factors
7. **Point-in-time ratings are critical** - must use ratings BEFORE game to avoid look-ahead bias
8. **Daily updates matter** - ratings change significantly game-to-game, especially mid-season

---

## Sources

- [KenPom API Access](https://kenpom.com/register-api.php)
- [KenPom Ratings Glossary](https://kenpom.com/blog/ratings-glossary/)
- [kenpompy GitHub Repository](https://github.com/j-andrews7/kenpompy)
- [Barttorvik T-Rank](https://barttorvik.com/)
- [toRvik R Package](https://github.com/andreweatherman/toRvik)
- [cbbdata R Package](https://github.com/andreweatherman/cbbdata)
- [hoopR-py GitHub](https://github.com/saiemgilani/hoopR-py)
- [ESPN Men's College Basketball BPI](https://www.espn.com/mens-college-basketball/bpi)
- [Basketball Reference - Four Factors](https://www.basketball-reference.com/about/factors.html)
- [Dean Oliver's Four Factors Revisited (arXiv)](https://arxiv.org/abs/2305.13032)
- [NCAA API by henrygd](https://github.com/henrygd/ncaa-api)
- [KenPom Terms of Service](https://kenpom.com/terms.php)
- [Odds Shark - KenPom Guide](https://www.oddsshark.com/ncaab/what-are-kenpom-ratings)
- [KenPom Cloudflare Issue #33](https://github.com/j-andrews7/kenpompy/issues/33)

---

Next Steps:

1. Purchase KenPom API subscription today
2. Implement `kenpom_fetcher.py` this week
3. Add Four Factors to model next week
4. Re-run backtest with new features
5. Run Gatekeeper validation - target PASS decision
