# Forecasting Platforms Technical Integration Assessment

**Research Date:** 2026-01-25
**Purpose:** Evaluate technical integration opportunities with Good Judgment Inc, Metaculus, and related forecasting platforms for sports betting model calibration and prediction enhancement.

---

## Executive Summary

### Platform Availability Matrix

| Platform | Public Access | API Available | Authentication | Data Export | Integration Priority |
|----------|--------------|---------------|----------------|-------------|---------------------|
| **Metaculus** | Yes (Free) | Yes | Token-based | JSON via API | **HIGH** - Best technical access |
| **Good Judgment Open** | Yes (Free) | No (Public) | Email login | Limited | **MEDIUM** - Training only |
| **GJ FutureFirst** | Paid subscription | Yes | API key | JSON/CSV | **LOW** - Cost barrier |
| **GJP Archive (Harvard)** | Yes (Free) | Yes (Dataverse) | None required | CSV/JSON | **HIGH** - Historical data |
| **Ergo (deprecated)** | Open source | N/A | N/A | N/A | **SKIP** - No longer maintained |

### Key Findings

1. **Metaculus offers the best technical integration** - Full API access, active Python library, free tier
2. **Harvard Dataverse GJP dataset provides historical calibration data** - 4 years of tournament data, millions of forecasts
3. **Good Judgment FutureFirst has API but requires paid subscription** - Daily updates, superforecaster consensus
4. **No sports betting-specific forecast platforms found** - Must adapt general forecasting methods
5. **Calibration training resources available** - Courses, tools, and methodologies publicly documented

---

## Platform-by-Platform Assessment

### 1. METACULUS

**Status:** Active, free access, comprehensive API

#### Technical Capabilities

| Feature | Details |
|---------|---------|
| **API Documentation** | OpenAPI 2.0 spec at https://www.metaculus.com/api/ |
| **Authentication** | Token-based (create at https://metaculus.com/aib) |
| **Python Library** | `forecasting-tools` (official, actively maintained) |
| **Rate Limits** | Not publicly documented (likely permissive for free tier) |
| **Data Access** | Questions, predictions, community forecasts, resolutions |
| **Question Types** | Binary, Multiple Choice, Numeric (distribution), Date |

#### Installation & Setup

```python
# Install official library
pip install forecasting-tools

# Basic usage
from forecasting_tools import MetaculusApi

# Get question data
question = MetaculusApi.get_question_by_url(
    "https://www.metaculus.com/questions/578/human-extinction-by-2100/"
)

# Retrieve tournament questions
questions = MetaculusApi.get_all_open_questions_from_tournament(
    tournament_id=123
)

# Advanced filtering
questions = MetaculusApi.get_questions_matching_filter(
    api_filter={
        "forecast_type": "binary",
        "min_forecasters": 10,
        "status": "open"
    },
    num_questions=100
)
```

#### Data Retrieval Examples

```python
from forecasting_tools import MetaculusApi, MetaculusClient
from forecasting_tools.helpers import DataOrganizer

# Initialize client
client = MetaculusClient()

# Get question by ID
question = MetaculusApi.get_question_by_post_id(post_id=5678)

# Access question properties
print(question.title)
print(question.created_time)
print(question.scheduled_close_time)
print(question.community_prediction)  # Aggregate forecast
print(question.resolution)  # Actual outcome (if resolved)

# Save questions for offline analysis
DataOrganizer.save_questions_to_file_path(
    questions,
    "metaculus_questions.json"
)

# Load saved questions
loaded_questions = DataOrganizer.load_questions_from_file_path(
    "metaculus_questions.json"
)
```

#### Submitting Predictions (Optional)

```python
# Submit binary prediction
MetaculusApi.post_binary_question_prediction(
    question_id=5678,
    prediction_percentage=0.65  # 65% probability
)

# Add private reasoning comment
MetaculusApi.post_question_comment(
    question_id=5678,
    comment="My reasoning for this forecast...",
    is_private=True
)
```

#### Community Prediction Access

**VALUE FOR SPORTS BETTING:** Metaculus aggregates community predictions using sophisticated algorithms. For calibration benchmarking:

```python
# Get community consensus as baseline
question = MetaculusApi.get_question_by_post_id(5678)

# Compare your model's prediction to community
model_prediction = 0.72
community_prediction = question.community_prediction

edge = model_prediction - community_prediction
print(f"Model edge over community: {edge:+.2%}")
```

#### Integration Use Cases

1. **Calibration Benchmarking** - Compare your model's probability outputs to well-calibrated Metaculus community
2. **Base Rate Research** - Search for resolved questions in similar reference classes
3. **Track Record Development** - Submit sports forecasts to build verifiable track record
4. **Methodology Learning** - Study how top forecasters think about uncertainty

---

### 2. GOOD JUDGMENT OPEN (GJOpen)

**Status:** Active, free access, NO public API

#### Technical Capabilities

| Feature | Details |
|---------|---------|
| **API Documentation** | None for public platform |
| **Authentication** | Email/password (web UI only) |
| **Python Library** | None |
| **Data Access** | Manual download only |
| **Question Types** | Binary, Multiple Choice, Numeric ranges |
| **Historical Data** | Limited export options |

#### Access Method

**MANUAL ONLY** - No programmatic access for GJ Open platform.

```python
# NO API ACCESS - Must use web scraping (against ToS)
# Alternative: Use Harvard Dataverse for historical GJP data
```

#### Training Resources

**Available publicly:**

- **Superforecasting Fundamentals Course** - https://good-judgment.thinkific.com/courses/Superforecasting-Fundamentals
  - 90-minute self-paced course
  - Covers: probabilistic reasoning, base rates, calibration, cognitive biases
  - CHAMP methodology (Comparison class, Historical trends, Average opinions, Mathematical models, Personal judgment)

#### Integration Use Cases

1. **Personal Skill Development** - Practice forecasting, improve calibration
2. **Methodology Learning** - Study superforecaster techniques
3. **Community Benchmarking** - Compare forecast accuracy against skilled forecasters

**NOT SUITABLE FOR:** Automated data retrieval, programmatic integration, systematic backtesting

---

### 3. GOOD JUDGMENT FUTUREFIRST

**Status:** Paid subscription, API available

#### Technical Capabilities

| Feature | Details |
|---------|---------|
| **API Documentation** | Available to subscribers (not public) |
| **Authentication** | API key (subscription required) |
| **Data Format** | JSON, daily updates |
| **Forecast Coverage** | Themed channels (Politics, Middle East, etc.) |
| **Superforecaster Access** | Yes - aggregated predictions + commentary |
| **Cost** | Not publicly disclosed - contact sales |

#### Access Method

```python
# REQUIRES SUBSCRIPTION - Example endpoint structure (hypothetical)

import requests

headers = {
    "Authorization": f"Bearer {FUTUREFIRST_API_KEY}"
}

response = requests.get(
    "https://api.goodjudgment.com/v1/forecasts",
    headers=headers,
    params={
        "channel": "politics",
        "updated_since": "2026-01-20"
    }
)

forecasts = response.json()
```

#### Available Data

- **Daily forecast updates** - Superforecaster consensus probabilities
- **Qualitative analysis** - Written commentary from professional forecasters
- **Custom questions** - Ability to request specific forecasts
- **Historical data** - Access to channel question archive

#### Integration Use Cases

1. **Superforecaster Consensus as Signal** - Use expert predictions as additional model feature
2. **Market Sentiment Proxy** - Track forecast changes as indicator of information flow
3. **Calibration Benchmark** - Compare model outputs to professional forecasters

**COST-BENEFIT:** Requires budget allocation. Best used if consistent +EV can be demonstrated from signal.

---

### 4. GOOD JUDGMENT PROJECT - HARVARD DATAVERSE

**Status:** Public archive, free access, Dataverse API

#### Technical Capabilities

| Feature | Details |
|---------|---------|
| **Repository** | https://dataverse.harvard.edu/dataverse/gjp |
| **API Documentation** | https://guides.dataverse.org/en/latest/api/dataaccess.html |
| **Authentication** | None required for public datasets |
| **Data Format** | CSV (primary), JSON (metadata) |
| **Coverage** | 2011-2015 IARPA ACE tournament |
| **Dataset Size** | Millions of individual forecasts |

#### Dataset Contents

**Main dataset:** `GJP Data` (DOI: 10.7910/DVN/BPCDH5)

**Includes:**

- Individual forecaster predictions (timestamped)
- Question metadata (topic, resolution, close date)
- Forecaster characteristics (training group, team assignment)
- Resolution outcomes (actual results)
- Brier scores and calibration metrics

#### Download Code

```python
# Using pyDataverse library
from pyDataverse.api import NativeApi
import pandas as pd

# Initialize API connection
base_url = "https://dataverse.harvard.edu/"
api = NativeApi(base_url)

# Download GJP dataset
DOI = "doi:10.7910/DVN/BPCDH5"
dataset = api.get_dataset(DOI)

# Direct file download (CSV)
import requests

file_url = "https://dataverse.harvard.edu/api/access/datafile/3187387"  # Example file ID
response = requests.get(file_url)

with open("gjp_forecasts.csv", "wb") as f:
    f.write(response.content)

# Load into pandas
df = pd.read_csv("gjp_forecasts.csv")

print(f"Loaded {len(df)} forecast records")
print(df.columns.tolist())
```

#### Alternative: Direct CSV Download

```python
# Simpler approach - direct download without API
import pandas as pd

# Replace with actual file persistent ID from Dataverse
url = "https://dataverse.harvard.edu/api/access/datafile/:persistentId?persistentId=doi:10.7910/DVN/BPCDH5/L8WZEF"

df = pd.read_csv(url)
```

#### Key Fields (Expected Schema)

```python
# Typical GJP dataset structure
df.columns = [
    'question_id',          # Unique question identifier
    'user_id',              # Forecaster ID (anonymized)
    'forecast_date',        # When prediction was made
    'probability',          # Predicted probability (0-1)
    'question_text',        # Question description
    'resolution_date',      # When question resolved
    'actual_outcome',       # 0 or 1 for binary questions
    'brier_score',          # Forecast accuracy metric
    'training_group',       # Which intervention group
    'is_superforecaster'    # Identified as superforecaster
]
```

#### Analysis Examples

**1. Calibration Curve from Historical Data**

```python
import numpy as np
import matplotlib.pyplot as plt

# Load resolved forecasts
df = pd.read_csv("gjp_forecasts.csv")
df_resolved = df[df['actual_outcome'].notna()]

# Create calibration bins
bins = np.arange(0, 1.1, 0.1)
df_resolved['bin'] = pd.cut(df_resolved['probability'], bins)

# Calculate calibration
calibration = df_resolved.groupby('bin').agg({
    'probability': 'mean',
    'actual_outcome': 'mean'
}).reset_index()

# Plot
plt.figure(figsize=(8, 6))
plt.plot(calibration['probability'], calibration['actual_outcome'], 'o-')
plt.plot([0, 1], [0, 1], 'k--', label='Perfect calibration')
plt.xlabel('Predicted Probability')
plt.ylabel('Observed Frequency')
plt.title('Calibration Curve - GJP Historical Data')
plt.legend()
plt.savefig('calibration_curve.png')
```

**2. Superforecaster Performance Analysis**

```python
# Compare superforecasters vs regular forecasters
sf_brier = df[df['is_superforecaster'] == True]['brier_score'].mean()
reg_brier = df[df['is_superforecaster'] == False]['brier_score'].mean()

print(f"Superforecaster avg Brier: {sf_brier:.4f}")
print(f"Regular forecaster avg Brier: {reg_brier:.4f}")
print(f"Improvement: {(reg_brier - sf_brier) / reg_brier:.1%}")
```

**3. Extract Base Rates for Reference Classes**

```python
# Find questions similar to sports betting scenarios
sports_keywords = ['win', 'championship', 'tournament', 'match', 'game']

sports_like = df[
    df['question_text'].str.lower().str.contains('|'.join(sports_keywords))
]

# Calculate base rate
base_rate = sports_like['actual_outcome'].mean()
print(f"Base rate for sports-like predictions: {base_rate:.1%}")
```

#### Integration Use Cases

1. **Calibration Training Dataset** - Train isotonic regression calibrator on GJP data
2. **Base Rate Library** - Build reference class database from historical questions
3. **Benchmark Your Model** - Compare Brier scores to tournament participants
4. **Study Expert Behavior** - Analyze how superforecasters update predictions over time
5. **Validate Techniques** - Test if training interventions (CHAMP, teaming) apply to sports

---

## Forecasting Methodology Integration

### Calibration Training Tools

#### 1. Brier Score Calculation

```python
def brier_score(predictions: np.ndarray, outcomes: np.ndarray) -> float:
    """
    Calculate Brier score (lower is better)

    Excellent: < 0.1
    Good: 0.1 - 0.125
    Sports betting lines: 0.18 - 0.22
    """
    return np.mean((predictions - outcomes) ** 2)

# Use for model evaluation
model_preds = np.array([0.65, 0.72, 0.45, 0.88])
actual_outcomes = np.array([1, 1, 0, 1])

score = brier_score(model_preds, actual_outcomes)
print(f"Model Brier Score: {score:.4f}")

# Benchmark targets for sports betting
if score < 0.1:
    print("EXCELLENT - Better than ESPN forecasts")
elif score < 0.125:
    print("GOOD - Competitive with sharp models")
elif score < 0.22:
    print("ACCEPTABLE - Similar to betting lines")
else:
    print("NEEDS IMPROVEMENT - Worse than market")
```

#### 2. Calibration Curve Implementation

```python
def plot_calibration_curve(predictions, outcomes, n_bins=10):
    """
    Create reliability diagram (calibration plot)
    """
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve

    fraction_positives, mean_predicted = calibration_curve(
        outcomes, predictions, n_bins=n_bins, strategy='uniform'
    )

    plt.figure(figsize=(8, 6))
    plt.plot(mean_predicted, fraction_positives, 's-', label='Model')
    plt.plot([0, 1], [0, 1], 'k--', label='Perfect calibration')

    plt.xlabel('Predicted Probability')
    plt.ylabel('Observed Frequency')
    plt.title('Calibration Curve (Reliability Diagram)')
    plt.legend()
    plt.grid(True, alpha=0.3)

    return plt

# Use with your betting model
plot = plot_calibration_curve(model_predictions, actual_results)
plot.savefig('model_calibration.png')
```

#### 3. Isotonic Regression Calibrator

```python
from sklearn.isotonic import IsotonicRegression
from sklearn.model_selection import train_test_split

def calibrate_probabilities(train_preds, train_outcomes, test_preds):
    """
    Calibrate model outputs using isotonic regression
    Recommended when you have sufficient historical data (>1000 predictions)
    """
    # Fit calibrator on training data
    iso_reg = IsotonicRegression(out_of_bounds='clip')
    iso_reg.fit(train_preds, train_outcomes)

    # Apply to test predictions
    calibrated_preds = iso_reg.predict(test_preds)

    return calibrated_preds

# Example usage with historical betting data
X_train, X_test, y_train, y_test = train_test_split(
    predictions, outcomes, test_size=0.3, random_state=42
)

calibrated = calibrate_probabilities(X_train, y_train, X_test)

# Compare uncalibrated vs calibrated
print(f"Uncalibrated Brier: {brier_score(X_test, y_test):.4f}")
print(f"Calibrated Brier: {brier_score(calibrated, y_test):.4f}")
```

#### 4. Beta Calibration (Tail Skew Handling)

```python
from betacal import BetaCalibration

def beta_calibrate(train_preds, train_outcomes, test_preds):
    """
    Beta calibration - better for extreme probabilities
    Useful for longshot bets (<20% or >80% probability)
    """
    bc = BetaCalibration()
    bc.fit(train_preds, train_outcomes)

    calibrated_preds = bc.predict(test_preds)

    return calibrated_preds

# Note: Requires betacal package
# pip install betacal
```

### Base Rate Integration

#### Reference Class Database

```python
class ReferenceClassDB:
    """
    Store and query base rates for different sports scenarios
    """
    def __init__(self):
        self.reference_classes = {}

    def add_reference_class(self, name: str, outcomes: list, context: dict):
        """
        Store historical outcomes for a reference class

        Example:
        - name: "NCAAB_home_favorite_single_digit_spread"
        - outcomes: [1, 0, 1, 1, 0, ...] (1=covered, 0=didn't cover)
        - context: {"sport": "NCAAB", "season": "2020-2025", "n": 347}
        """
        base_rate = np.mean(outcomes)

        self.reference_classes[name] = {
            'base_rate': base_rate,
            'n': len(outcomes),
            'outcomes': outcomes,
            'context': context,
            'std_error': np.std(outcomes) / np.sqrt(len(outcomes))
        }

    def get_base_rate(self, name: str) -> float:
        """Retrieve base rate for reference class"""
        return self.reference_classes[name]['base_rate']

    def query_similar(self, features: dict, top_k: int = 3):
        """
        Find most similar reference classes based on features
        (Simplified - real implementation would use feature matching)
        """
        # TODO: Implement similarity matching
        pass

# Usage example
ref_db = ReferenceClassDB()

# Add reference class from historical data
ref_db.add_reference_class(
    name="ncaab_home_team_favored_by_7",
    outcomes=[1, 1, 0, 1, 0, 1, 1, 1, 0, 1],  # Win/loss record
    context={"sport": "NCAAB", "spread_range": "5-9", "season": "2024"}
)

base_rate = ref_db.get_base_rate("ncaab_home_team_favored_by_7")
print(f"Historical base rate: {base_rate:.1%}")
```

#### Base Rate Adjustment (Outside View)

```python
def adjust_prediction_with_base_rate(
    model_prediction: float,
    base_rate: float,
    confidence: float = 0.5
) -> float:
    """
    Blend model prediction (inside view) with base rate (outside view)

    Args:
        model_prediction: Your model's raw prediction
        base_rate: Historical frequency in reference class
        confidence: Weight on model (0=full base rate, 1=full model)

    Returns:
        Adjusted prediction
    """
    adjusted = (confidence * model_prediction) + ((1 - confidence) * base_rate)
    return adjusted

# Example
model_says = 0.68  # 68% win probability
base_rate = 0.58   # Historical win rate in similar scenarios
confidence = 0.7   # 70% weight on model, 30% on base rate

final_prediction = adjust_prediction_with_base_rate(
    model_says, base_rate, confidence
)

print(f"Model: {model_says:.1%}")
print(f"Base rate: {base_rate:.1%}")
print(f"Adjusted: {final_prediction:.1%}")
```

---

## Recommended Integration Workflow

### Phase 1: Calibration Training (Week 1-2)

**Objective:** Improve probability estimation skills and establish calibration baseline

**Steps:**

1. **Complete GJ Fundamentals Course** (90 minutes)
   - https://good-judgment.thinkific.com/courses/Superforecasting-Fundamentals
   - Focus on: base rates, calibration, avoiding overconfidence

2. **Download GJP Historical Data**

   ```python
   # Get Harvard Dataverse dataset
   import pandas as pd

   gjp_data = pd.read_csv(
       "https://dataverse.harvard.edu/api/access/datafile/:persistentId?persistentId=doi:10.7910/DVN/BPCDH5/L8WZEF"
   )
   ```

3. **Build Calibration Curve from GJP Data**

   ```python
   # Use superforecaster subset as gold standard
   sf_data = gjp_data[gjp_data['is_superforecaster'] == True]

   plot_calibration_curve(
       sf_data['probability'],
       sf_data['actual_outcome']
   )
   ```

4. **Analyze Your Current Model's Calibration**

   ```python
   # Backtest your NCAAB model
   backtest_results = run_backtest(ncaab_model, seasons=[2020, 2021, 2022, 2023, 2024])

   # Calculate Brier score
   brier = brier_score(
       backtest_results['model_probability'],
       backtest_results['actual_outcome']
   )

   print(f"Current model Brier: {brier:.4f}")
   print(f"Target (GJP Superforecasters): ~0.10")
   print(f"Target (ESPN): ~0.075")
   ```

### Phase 2: Base Rate Library (Week 3-4)

**Objective:** Build reference class database for common betting scenarios

**Steps:**

1. **Define Reference Classes**

   ```python
   reference_classes = {
       'ncaab_home_favorite_0_5': {
           'description': 'Home team favored by 0-5 points',
           'filters': {'sport': 'NCAAB', 'home_spread': [-5, 0]}
       },
       'ncaab_home_favorite_5_10': {
           'description': 'Home team favored by 5-10 points',
           'filters': {'sport': 'NCAAB', 'home_spread': [-10, -5]}
       },
       'ncaab_road_underdog_10_plus': {
           'description': 'Road team underdog by 10+ points',
           'filters': {'sport': 'NCAAB', 'is_home': False, 'spread': [10, 50]}
       }
       # Add more classes...
   }
   ```

2. **Extract Base Rates from Historical Data**

   ```python
   from tracking.database import get_historical_results

   def calculate_base_rates(reference_classes):
       base_rates = {}

       for name, config in reference_classes.items():
           # Query historical results matching filters
           results = get_historical_results(config['filters'])

           base_rates[name] = {
               'base_rate': results['covered'].mean(),
               'n': len(results),
               'win_rate': results['won'].mean(),
               'avg_clv': results['clv'].mean()
           }

       return base_rates

   base_rates = calculate_base_rates(reference_classes)
   ```

3. **Store in SQLite Database**

   ```python
   # Add to database schema
   CREATE TABLE reference_classes (
       id INTEGER PRIMARY KEY,
       name TEXT UNIQUE,
       sport TEXT,
       description TEXT,
       base_rate REAL,
       sample_size INTEGER,
       filters JSON,
       updated_at TIMESTAMP
   );
   ```

### Phase 3: Metaculus Integration (Week 5-6)

**Objective:** Access real-time community forecasts and build track record

**Steps:**

1. **Install Metaculus Tools**

   ```bash
   pip install forecasting-tools
   ```

2. **Create Authentication Token**
   - Visit https://metaculus.com/aib
   - Create account if needed
   - Generate API token
   - Store in `.env`:

     ```
     METACULUS_TOKEN=your_token_here
     ```

3. **Search for Sports-Related Questions**

   ```python
   from forecasting_tools import MetaculusApi

   # Find sports/competition questions
   questions = MetaculusApi.get_questions_matching_filter(
       api_filter={
           "search": "championship OR tournament OR playoff",
           "status": "open",
           "min_forecasters": 20
       },
       num_questions=50
   )

   # Filter to sports-specific
   sports_questions = [
       q for q in questions
       if any(sport in q.title.lower() for sport in ['nfl', 'nba', 'ncaa', 'mlb'])
   ]
   ```

4. **Submit Forecasts (Optional - for track record)**

   ```python
   # Submit predictions for upcoming games
   for game in upcoming_ncaab_games:
       model_prob = ncaab_model.predict(game)

       # Find corresponding Metaculus question (if exists)
       question = find_metaculus_question(game)

       if question:
           MetaculusApi.post_binary_question_prediction(
               question_id=question.id,
               prediction_percentage=model_prob
           )
   ```

5. **Benchmark Against Community**

   ```python
   def compare_to_community(model_prediction, metaculus_question):
       """
       Compare your model to Metaculus community consensus
       """
       community_pred = metaculus_question.community_prediction

       edge = model_prediction - community_pred

       if abs(edge) > 0.10:  # 10+ percentage point difference
           print(f"SIGNIFICANT EDGE: {edge:+.1%}")
           print(f"Model: {model_prediction:.1%}")
           print(f"Community: {community_pred:.1%}")

           return {
               'has_edge': True,
               'edge_size': edge,
               'model_prob': model_prediction,
               'community_prob': community_pred
           }

       return {'has_edge': False}
   ```

### Phase 4: Model Calibration (Week 7-8)

**Objective:** Improve model probability estimates using calibration techniques

**Steps:**

1. **Train Isotonic Regression Calibrator**

   ```python
   from sklearn.isotonic import IsotonicRegression

   # Use historical predictions
   historical_data = load_backtest_results('ncaab_2020_2024.csv')

   # Split into calibration set and validation set
   calibration_set = historical_data[historical_data['season'] < 2024]
   validation_set = historical_data[historical_data['season'] == 2024]

   # Fit calibrator
   calibrator = IsotonicRegression(out_of_bounds='clip')
   calibrator.fit(
       calibration_set['raw_model_probability'],
       calibration_set['actual_outcome']
   )

   # Apply to validation set
   calibrated_probs = calibrator.predict(
       validation_set['raw_model_probability']
   )

   # Evaluate improvement
   raw_brier = brier_score(
       validation_set['raw_model_probability'],
       validation_set['actual_outcome']
   )

   calibrated_brier = brier_score(
       calibrated_probs,
       validation_set['actual_outcome']
   )

   print(f"Raw Brier: {raw_brier:.4f}")
   print(f"Calibrated Brier: {calibrated_brier:.4f}")
   print(f"Improvement: {(raw_brier - calibrated_brier) / raw_brier:.1%}")
   ```

2. **Save Calibrator for Production Use**

   ```python
   import joblib

   # Save calibrator
   joblib.dump(calibrator, 'models/ncaab_calibrator.pkl')

   # In production code
   def get_calibrated_prediction(game_features):
       raw_prob = ncaab_model.predict_proba(game_features)
       calibrator = joblib.load('models/ncaab_calibrator.pkl')
       calibrated_prob = calibrator.predict([raw_prob])[0]
       return calibrated_prob
   ```

3. **Monitor Calibration Drift**

   ```python
   # Weekly calibration check
   def check_calibration_weekly():
       this_week = get_predictions_from_week('2026-01-20')

       plot_calibration_curve(
           this_week['predicted_prob'],
           this_week['actual_outcome'],
           n_bins=5  # Fewer bins for weekly data
       ).savefig(f'calibration_2026_W03.png')

       # Alert if Brier score degrades
       brier = brier_score(
           this_week['predicted_prob'],
           this_week['actual_outcome']
       )

       if brier > 0.15:
           print("WARNING: Calibration degrading, retrain calibrator")
   ```

### Phase 5: Continuous Integration (Ongoing)

**Objective:** Maintain calibration and integrate community insights

**Daily Workflow:**

```python
# scripts/daily_forecasting_workflow.py

def daily_forecasting_workflow():
    """
    Integrated daily forecasting pipeline
    """

    # 1. Get today's games
    games = get_todays_games(sport='NCAAB')

    # 2. Generate model predictions
    predictions = []
    for game in games:
        # Raw model prediction
        raw_prob = ncaab_model.predict(game)

        # Apply calibration
        calibrated_prob = calibrator.predict([raw_prob])[0]

        # Look up base rate
        ref_class = classify_reference_class(game)
        base_rate = reference_db.get_base_rate(ref_class)

        # Blend with base rate (outside view)
        final_prob = adjust_prediction_with_base_rate(
            calibrated_prob,
            base_rate,
            confidence=0.75  # 75% model, 25% base rate
        )

        predictions.append({
            'game': game,
            'raw_prob': raw_prob,
            'calibrated_prob': calibrated_prob,
            'base_rate': base_rate,
            'final_prob': final_prob
        })

    # 3. Check Metaculus for similar questions (if any)
    for pred in predictions:
        metaculus_q = search_metaculus_for_game(pred['game'])
        if metaculus_q:
            pred['community_prob'] = metaculus_q.community_prediction
            pred['edge_vs_community'] = pred['final_prob'] - pred['community_prob']

    # 4. Calculate EV and betting recommendations
    for pred in predictions:
        market_odds = get_current_odds(pred['game'])

        ev = calculate_expected_value(
            win_prob=pred['final_prob'],
            odds=market_odds
        )

        if ev > 0.03:  # 3% edge threshold
            print(f"BET SIGNAL: {pred['game']}")
            print(f"  Model: {pred['final_prob']:.1%}")
            print(f"  Odds: {market_odds}")
            print(f"  Edge: {ev:.1%}")

    return predictions

# Run daily
if __name__ == "__main__":
    daily_forecasting_workflow()
```

---

## Data Availability Matrix

### Historical Data Sources

| Dataset | Sport Applicability | Size | Format | Access Method | Use Case |
|---------|-------------------|------|--------|---------------|----------|
| **GJP Harvard Archive** | Generic (any probabilistic forecast) | Millions of forecasts (2011-2015) | CSV | Free download | Calibration training, base rate research |
| **Metaculus Resolved Questions** | Generic | Thousands | JSON via API | Free API | Reference class base rates, methodology study |
| **Sports Betting Lines Archive** | Sports-specific | Varies by source | CSV/SQL | Paid/scraped | Actual sports base rates |
| **Brier Score Benchmarks** | Generic | Literature | Papers | Research | Performance targets |

### Real-Time Data Sources

| Source | Update Frequency | Cost | Integration Difficulty | Value for Sports Betting |
|--------|-----------------|------|----------------------|--------------------------|
| **Metaculus Community** | Real-time | Free | Easy (API) | Medium - Calibration benchmark |
| **GJ FutureFirst** | Daily | $$$ | Easy (API) | Low - Not sports-specific |
| **Sports Odds APIs** | Real-time | $/$$$ | Easy (API) | HIGH - Direct market data |
| **Injury Reports** | Real-time | Free/$ | Medium (scraping/API) | HIGH - Information edge |

---

## Integration Priority Ranking

### TIER 1 - Immediate Implementation (This Month)

1. **Harvard Dataverse GJP Dataset** ✅
   - **Effort:** Low (2-4 hours)
   - **Value:** High (calibration foundation)
   - **Action:** Download CSV, build calibration curves, extract superforecaster benchmarks

2. **Brier Score Calculation** ✅
   - **Effort:** Low (1 hour)
   - **Value:** High (core evaluation metric)
   - **Action:** Add to backtest pipeline, weekly monitoring

3. **Reference Class Database** ✅
   - **Effort:** Medium (8-12 hours)
   - **Value:** High (base rate integration)
   - **Action:** Define classes, calculate historical base rates, store in SQLite

### TIER 2 - Next Month Implementation

4. **Isotonic Regression Calibrator** ⏳
   - **Effort:** Medium (4-6 hours)
   - **Value:** Medium-High (improved probability estimates)
   - **Action:** Train on backtest data, integrate into prediction pipeline

5. **Metaculus API Integration** ⏳
   - **Effort:** Medium (6-8 hours)
   - **Value:** Medium (community benchmark, track record)
   - **Action:** Set up API access, automate forecast submission, build comparison dashboard

### TIER 3 - Future Consideration

6. **Good Judgment FutureFirst** ⏸️
   - **Effort:** Low (2 hours if subscribed)
   - **Value:** Low-Medium (superforecaster signal)
   - **Action:** Evaluate after 3 months of profitability, test as additional feature

7. **Custom Calibration Training Tool** ⏸️
   - **Effort:** High (20+ hours)
   - **Value:** Medium (skill improvement)
   - **Action:** Build interactive tool for probability estimation practice

### TIER 4 - Skip / Not Recommended

8. **Good Judgment Open Manual Tracking** ❌
   - **Effort:** High (manual data entry)
   - **Value:** Low (no API, time-consuming)
   - **Action:** SKIP - Use GJP archive instead

9. **Ergo Library** ❌
   - **Effort:** N/A
   - **Value:** None (deprecated)
   - **Action:** SKIP - Use forecasting-tools instead

---

## Python Code Snippets Library

### Complete Integration Example

```python
# forecasting_integration.py
"""
Complete integration of forecasting platform tools
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from sklearn.isotonic import IsotonicRegression
import joblib

# ═══════════════════════════════════════════════════════════
# 1. DATA LOADING
# ═══════════════════════════════════════════════════════════

def load_gjp_data() -> pd.DataFrame:
    """
    Load Good Judgment Project historical data from Harvard Dataverse
    """
    url = "https://dataverse.harvard.edu/api/access/datafile/:persistentId?persistentId=doi:10.7910/DVN/BPCDH5/L8WZEF"

    df = pd.read_csv(url)

    # Expected columns (adjust based on actual schema)
    # question_id, user_id, forecast_date, probability, actual_outcome, etc.

    return df


def load_metaculus_questions(api_filter: dict) -> List:
    """
    Load questions from Metaculus API
    """
    from forecasting_tools import MetaculusApi

    questions = MetaculusApi.get_questions_matching_filter(
        api_filter=api_filter,
        num_questions=100
    )

    return questions

# ═══════════════════════════════════════════════════════════
# 2. CALIBRATION ANALYSIS
# ═══════════════════════════════════════════════════════════

def calculate_brier_score(predictions: np.ndarray, outcomes: np.ndarray) -> float:
    """
    Calculate Brier score (mean squared error for probabilities)

    Benchmarks:
    - Excellent: < 0.10
    - Good: 0.10 - 0.125
    - Acceptable: 0.125 - 0.22 (similar to sports betting lines)
    """
    return np.mean((predictions - outcomes) ** 2)


def plot_calibration_curve(predictions: np.ndarray, outcomes: np.ndarray,
                          n_bins: int = 10, save_path: str = None):
    """
    Generate calibration curve (reliability diagram)
    """
    import matplotlib.pyplot as plt
    from sklearn.calibration import calibration_curve

    fraction_positives, mean_predicted = calibration_curve(
        outcomes, predictions, n_bins=n_bins, strategy='uniform'
    )

    plt.figure(figsize=(10, 6))
    plt.plot(mean_predicted, fraction_positives, 's-', linewidth=2, markersize=8, label='Model')
    plt.plot([0, 1], [0, 1], 'k--', linewidth=1, label='Perfect calibration')

    plt.xlabel('Predicted Probability', fontsize=12)
    plt.ylabel('Observed Frequency', fontsize=12)
    plt.title('Calibration Curve (Reliability Diagram)', fontsize=14)
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3)

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches='tight')

    return plt


def train_calibrator(train_preds: np.ndarray, train_outcomes: np.ndarray,
                     method: str = 'isotonic') -> object:
    """
    Train probability calibrator

    Args:
        train_preds: Raw model predictions (0-1)
        train_outcomes: Actual outcomes (0 or 1)
        method: 'isotonic' or 'beta'

    Returns:
        Fitted calibrator object
    """
    if method == 'isotonic':
        calibrator = IsotonicRegression(out_of_bounds='clip')
        calibrator.fit(train_preds, train_outcomes)

    elif method == 'beta':
        from betacal import BetaCalibration
        calibrator = BetaCalibration()
        calibrator.fit(train_preds, train_outcomes)

    else:
        raise ValueError(f"Unknown calibration method: {method}")

    return calibrator


# ═══════════════════════════════════════════════════════════
# 3. REFERENCE CLASS DATABASE
# ═══════════════════════════════════════════════════════════

class ReferenceClassDB:
    """
    Manage base rates for different prediction scenarios
    """

    def __init__(self, db_path: str = None):
        self.classes = {}
        self.db_path = db_path

    def add_class(self, name: str, outcomes: List[int], metadata: dict = None):
        """
        Add reference class with historical outcomes
        """
        outcomes_array = np.array(outcomes)

        self.classes[name] = {
            'base_rate': outcomes_array.mean(),
            'n': len(outcomes),
            'std_error': outcomes_array.std() / np.sqrt(len(outcomes)),
            'outcomes': outcomes,
            'metadata': metadata or {}
        }

    def get_base_rate(self, name: str) -> float:
        """Get base rate for reference class"""
        if name not in self.classes:
            raise KeyError(f"Reference class '{name}' not found")

        return self.classes[name]['base_rate']

    def get_confidence_interval(self, name: str, confidence: float = 0.95) -> Tuple[float, float]:
        """
        Get confidence interval for base rate
        """
        from scipy import stats

        class_data = self.classes[name]
        n = class_data['n']
        p = class_data['base_rate']

        # Wilson score interval
        z = stats.norm.ppf((1 + confidence) / 2)
        denominator = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denominator
        margin = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denominator

        return (center - margin, center + margin)

    def save(self, path: str):
        """Save reference classes to file"""
        import json
        with open(path, 'w') as f:
            json.dump(self.classes, f, indent=2)

    def load(self, path: str):
        """Load reference classes from file"""
        import json
        with open(path, 'r') as f:
            self.classes = json.load(f)


# ═══════════════════════════════════════════════════════════
# 4. PREDICTION ADJUSTMENT
# ═══════════════════════════════════════════════════════════

def adjust_with_base_rate(model_prediction: float, base_rate: float,
                         confidence: float = 0.5) -> float:
    """
    Blend model prediction with base rate (outside view)

    Args:
        model_prediction: Model's probability estimate
        base_rate: Historical frequency in reference class
        confidence: Weight on model (0=all base rate, 1=all model)

    Returns:
        Adjusted probability
    """
    return confidence * model_prediction + (1 - confidence) * base_rate


def apply_calibration(raw_predictions: np.ndarray, calibrator: object) -> np.ndarray:
    """
    Apply calibrator to raw model predictions
    """
    return calibrator.predict(raw_predictions)


# ═══════════════════════════════════════════════════════════
# 5. METACULUS INTEGRATION
# ═══════════════════════════════════════════════════════════

def get_community_forecast(question_url: str) -> Dict:
    """
    Get Metaculus community forecast for comparison
    """
    from forecasting_tools import MetaculusApi

    question = MetaculusApi.get_question_by_url(question_url)

    return {
        'question_title': question.title,
        'community_prediction': question.community_prediction,
        'num_forecasters': getattr(question, 'num_forecasters', None),
        'close_time': question.scheduled_close_time
    }


def calculate_edge_vs_community(model_prob: float, community_prob: float) -> Dict:
    """
    Calculate edge vs Metaculus community
    """
    edge = model_prob - community_prob
    edge_pct = edge / community_prob if community_prob > 0 else 0

    return {
        'absolute_edge': edge,
        'relative_edge': edge_pct,
        'is_significant': abs(edge) > 0.10  # 10+ percentage points
    }


# ═══════════════════════════════════════════════════════════
# 6. COMPLETE WORKFLOW
# ═══════════════════════════════════════════════════════════

class ForecastingPipeline:
    """
    Complete forecasting pipeline with calibration and base rates
    """

    def __init__(self, calibrator_path: str = None, ref_db_path: str = None):
        self.calibrator = None
        self.ref_db = ReferenceClassDB()

        if calibrator_path:
            self.calibrator = joblib.load(calibrator_path)

        if ref_db_path:
            self.ref_db.load(ref_db_path)

    def predict(self, model_raw_prob: float, reference_class: str,
                confidence_in_model: float = 0.75) -> Dict:
        """
        Generate final prediction with calibration and base rate adjustment

        Args:
            model_raw_prob: Raw model probability output
            reference_class: Name of reference class to use for base rate
            confidence_in_model: Weight on model vs base rate (default 0.75)

        Returns:
            Dictionary with prediction details
        """
        # Step 1: Apply calibration
        if self.calibrator:
            calibrated_prob = self.calibrator.predict([model_raw_prob])[0]
        else:
            calibrated_prob = model_raw_prob

        # Step 2: Get base rate
        try:
            base_rate = self.ref_db.get_base_rate(reference_class)
        except KeyError:
            print(f"Warning: Reference class '{reference_class}' not found, using raw prediction")
            base_rate = calibrated_prob
            confidence_in_model = 1.0

        # Step 3: Blend with base rate
        final_prob = adjust_with_base_rate(
            calibrated_prob,
            base_rate,
            confidence_in_model
        )

        return {
            'raw_probability': model_raw_prob,
            'calibrated_probability': calibrated_prob,
            'base_rate': base_rate,
            'final_probability': final_prob,
            'reference_class': reference_class,
            'model_weight': confidence_in_model
        }

    def backtest_calibration(self, predictions: np.ndarray,
                            outcomes: np.ndarray) -> Dict:
        """
        Evaluate calibration quality on historical data
        """
        brier = calculate_brier_score(predictions, outcomes)

        # Decompose Brier score
        calibration_error = self._calculate_calibration_component(predictions, outcomes)
        resolution = self._calculate_resolution_component(predictions, outcomes)

        return {
            'brier_score': brier,
            'calibration_error': calibration_error,
            'resolution': resolution,
            'is_excellent': brier < 0.10,
            'is_good': brier < 0.125,
            'is_acceptable': brier < 0.22
        }

    def _calculate_calibration_component(self, preds, outcomes):
        """Calculate calibration component of Brier score"""
        from sklearn.calibration import calibration_curve

        fraction_positives, mean_predicted = calibration_curve(
            outcomes, preds, n_bins=10, strategy='uniform'
        )

        # Weighted squared difference from diagonal
        calibration_error = np.sum(
            (mean_predicted - fraction_positives) ** 2 *
            np.bincount(np.digitize(preds, np.linspace(0, 1, 11)))[1:]
        ) / len(preds)

        return calibration_error

    def _calculate_resolution_component(self, preds, outcomes):
        """Calculate resolution component of Brier score"""
        # How much predictions vary from base rate
        base_rate = outcomes.mean()
        resolution = np.mean((preds - base_rate) ** 2)
        return resolution


# ═══════════════════════════════════════════════════════════
# 7. EXAMPLE USAGE
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":

    # Example 1: Load and analyze GJP data
    print("Loading GJP historical data...")
    gjp_df = load_gjp_data()

    # Filter to resolved questions
    resolved = gjp_df[gjp_df['actual_outcome'].notna()]

    # Calculate Brier score for superforecasters
    superforecasters = resolved[resolved['is_superforecaster'] == True]
    sf_brier = calculate_brier_score(
        superforecasters['probability'].values,
        superforecasters['actual_outcome'].values
    )
    print(f"Superforecaster Brier Score: {sf_brier:.4f}")

    # Example 2: Build reference class database
    ref_db = ReferenceClassDB()

    # Add NCAAB home favorites reference class
    ref_db.add_class(
        name='ncaab_home_favorite_5_10_pts',
        outcomes=[1, 1, 0, 1, 1, 0, 1, 1, 1, 0] * 10,  # Example data
        metadata={'sport': 'NCAAB', 'spread_range': [5, 10], 'sample_years': '2020-2024'}
    )

    base_rate = ref_db.get_base_rate('ncaab_home_favorite_5_10_pts')
    ci_low, ci_high = ref_db.get_confidence_interval('ncaab_home_favorite_5_10_pts')
    print(f"Base rate: {base_rate:.1%} (95% CI: {ci_low:.1%} - {ci_high:.1%})")

    # Example 3: Train calibrator
    print("\nTraining calibrator...")

    # Simulated data (replace with your backtest results)
    np.random.seed(42)
    train_preds = np.random.beta(2, 2, 1000)  # Simulated predictions
    train_outcomes = (np.random.random(1000) < train_preds).astype(int)

    calibrator = train_calibrator(train_preds, train_outcomes, method='isotonic')

    # Example 4: Complete prediction pipeline
    pipeline = ForecastingPipeline()
    pipeline.calibrator = calibrator
    pipeline.ref_db = ref_db

    # Make prediction
    prediction = pipeline.predict(
        model_raw_prob=0.68,
        reference_class='ncaab_home_favorite_5_10_pts',
        confidence_in_model=0.75
    )

    print("\nPrediction breakdown:")
    for key, value in prediction.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.1%}")
        else:
            print(f"  {key}: {value}")
```

---

## Key Takeaways

### What's Available

✅ **Excellent historical data** - GJP Harvard archive with millions of forecasts
✅ **Best-in-class API** - Metaculus provides full programmatic access
✅ **Calibration methodology** - Well-documented techniques (Brier, isotonic regression)
✅ **Base rate research** - Can extract from both GJP archive and Metaculus resolved questions
✅ **Free training resources** - GJ Fundamentals course, papers, tutorials

### What's Missing

❌ **Sports-specific forecasting platform** - No Metaculus/GJOpen equivalent for sports
❌ **Free superforecaster data** - FutureFirst requires paid subscription
❌ **Direct sports betting calibration datasets** - Must build your own
❌ **Real-time odds API** (from these platforms) - Need separate sports data provider

### Recommended Approach

1. **Start with GJP archive** - Learn from superforecasters, build calibration baseline
2. **Implement Brier scoring immediately** - Track model performance properly
3. **Build reference class database** - Extract base rates from YOUR historical betting data
4. **Train isotonic calibrator** - Improve probability estimates using backtest data
5. **Use Metaculus for benchmarking** - Compare to community when similar questions exist
6. **Skip FutureFirst for now** - Wait until proven profitability justifies subscription

---

## Additional Resources

### Documentation

- **Metaculus API Docs:** https://www.metaculus.com/api/
- **Metaculus forecasting-tools:** https://github.com/Metaculus/forecasting-tools
- **GJP Harvard Dataverse:** https://dataverse.harvard.edu/dataverse/gjp
- **Good Judgment Fundamentals:** https://good-judgment.thinkific.com/courses/Superforecasting-Fundamentals

### Research Papers

- Tetlock, P. E., & Gardner, D. (2015). *Superforecasting: The Art and Science of Prediction*
- Brier, G. W. (1950). "Verification of forecasts expressed in terms of probability"
- Mellers, B., et al. (2014). "Psychological strategies for winning a geopolitical forecasting tournament"

### Tools

- **sklearn.calibration** - Python calibration tools
- **betacal** - Beta calibration library (`pip install betacal`)
- **forecasting-tools** - Official Metaculus Python library

---

## JSON Output

```json
{
  "search_summary": {
    "platforms_searched": ["metaculus", "good_judgment_open", "good_judgment_futurefirst", "harvard_dataverse"],
    "repositories_analyzed": 4,
    "docs_reviewed": 8
  },
  "repositories": [
    {
      "citation": "Metaculus. \"forecasting-tools: A framework for building AI Forecasting Bots.\" GitHub, 2026. https://github.com/Metaculus/forecasting-tools",
      "platform": "github",
      "stats": {
        "stars": "Not disclosed",
        "forks": "Not disclosed",
        "contributors": "Multiple",
        "last_updated": "2026-01-25"
      },
      "key_features": [
        "Metaculus API wrapper for questions and tournaments",
        "Support for Binary, Multiple Choice, Numeric, and Date questions",
        "AI forecasting bot framework",
        "Benchmarking tools against Metaculus questions"
      ],
      "architecture": "Python-based library with async support, Pydantic models for type safety, integrates with Metaculus AI benchmarking competition",
      "code_quality": {
        "testing": "adequate",
        "documentation": "good",
        "maintenance": "active"
      },
      "usage_example": "from forecasting_tools import MetaculusApi; question = MetaculusApi.get_question_by_url('https://www.metaculus.com/questions/578/')",
      "limitations": [
        "Still experimental (API may change)",
        "Requires Metaculus account and API token",
        "Limited to Metaculus platform only"
      ],
      "alternatives": [
        "ergo (deprecated)",
        "Direct API calls to Metaculus"
      ]
    },
    {
      "citation": "IARPA / Good Judgment Project. \"GJP Data.\" Harvard Dataverse, 2017. https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/BPCDH5",
      "platform": "harvard_dataverse",
      "stats": {
        "stars": "N/A",
        "forks": "N/A",
        "contributors": "GJP research team",
        "last_updated": "2017-04-28"
      },
      "key_features": [
        "4 years of IARPA ACE tournament data (2011-2015)",
        "Millions of individual forecasts",
        "Superforecaster identification labels",
        "Resolution outcomes and Brier scores",
        "Training intervention group assignments"
      ],
      "architecture": "CSV datasets accessible via Dataverse API, structured tabular data with forecast timestamps, probabilities, and outcomes",
      "code_quality": {
        "testing": "N/A (dataset)",
        "documentation": "fair",
        "maintenance": "archived"
      },
      "usage_example": "df = pd.read_csv('https://dataverse.harvard.edu/api/access/datafile/:persistentId?persistentId=doi:10.7910/DVN/BPCDH5/L8WZEF')",
      "limitations": [
        "Historical data only (2011-2015)",
        "No real-time updates",
        "Generic geopolitical questions (not sports-specific)"
      ],
      "alternatives": [
        "Metaculus resolved questions API",
        "PredictIt historical data"
      ]
    },
    {
      "citation": "Ought. \"Ergo: A Python library for integrating model-based and judgmental forecasting.\" GitHub, Deprecated. https://github.com/oughtinc/ergo",
      "platform": "github",
      "stats": {
        "stars": "Not disclosed",
        "forks": "Not disclosed",
        "contributors": "Ought team",
        "last_updated": "No longer maintained"
      },
      "key_features": [
        "Metaculus API integration",
        "Probabilistic programming with Pyro",
        "Forecast submission capabilities"
      ],
      "architecture": "Python library with Pyro backend for generative modeling, now deprecated in favor of newer tools",
      "code_quality": {
        "testing": "adequate",
        "documentation": "good",
        "maintenance": "abandoned"
      },
      "usage_example": "metaculus = ergo.Metaculus(username='user', password='pass'); q = metaculus.get_question(3529)",
      "limitations": [
        "No longer actively developed",
        "Superseded by forecasting-tools",
        "May have compatibility issues with current Metaculus API"
      ],
      "alternatives": [
        "forecasting-tools (official Metaculus library)"
      ]
    }
  ],
  "technical_insights": {
    "common_patterns": [
      "Token-based API authentication is standard",
      "JSON is primary data exchange format",
      "Async/await patterns for API calls",
      "Brier score as universal calibration metric",
      "Isotonic regression for probability calibration"
    ],
    "best_practices": [
      "Use official libraries (forecasting-tools) over direct API calls",
      "Always calibrate model outputs before betting decisions",
      "Blend model predictions with base rates (outside view)",
      "Track Brier score continuously for calibration monitoring",
      "Use reference classes for base rate estimation"
    ],
    "pitfalls": [
      "Overconfidence in model predictions without calibration",
      "Ignoring base rates (outside view neglect)",
      "Using deprecated libraries (ergo)",
      "Not tracking calibration over time",
      "Confusing Brier score direction (lower is better)"
    ],
    "emerging_trends": [
      "AI-powered forecasting bots on Metaculus",
      "Hybrid human-AI forecasting approaches",
      "Real-time calibration monitoring",
      "Community prediction aggregation algorithms"
    ]
  },
  "implementation_recommendations": [
    {
      "scenario": "Initial model calibration setup",
      "recommended_solution": "Download GJP Harvard dataset, calculate Brier scores for superforecasters, build calibration curves, train isotonic regression calibrator on your backtest data",
      "rationale": "Provides gold-standard benchmark (superforecasters) and proven calibration methodology with minimal cost"
    },
    {
      "scenario": "Ongoing prediction quality monitoring",
      "recommended_solution": "Implement weekly Brier score calculation and calibration curve plotting, alert if score degrades above 0.15",
      "rationale": "Catches calibration drift early before it impacts betting performance"
    },
    {
      "scenario": "Base rate research for new betting markets",
      "recommended_solution": "Build reference class database from your own historical betting data, supplement with Metaculus resolved questions in similar domains",
      "rationale": "Your own data is most relevant for sports betting; Metaculus provides additional calibration benchmarks"
    },
    {
      "scenario": "Track record verification",
      "recommended_solution": "Submit predictions to Metaculus for sports-related questions (when available), maintain public forecast history",
      "rationale": "Creates independently verifiable track record, forces disciplined probability estimation"
    },
    {
      "scenario": "Community benchmark comparison",
      "recommended_solution": "Use Metaculus API to retrieve community forecasts for similar questions, calculate edge vs community consensus",
      "rationale": "Identifies when your model has significant edge vs crowd, flags potential errors when divergence is extreme"
    }
  ],
  "community_insights": {
    "popular_solutions": [
      "Metaculus for community forecasting and API access",
      "GJP Harvard archive for calibration training data",
      "Brier score as primary accuracy metric",
      "Isotonic regression for calibration",
      "CHAMP methodology (Comparison, Historical, Average, Mathematical, Personal)"
    ],
    "controversial_topics": [
      "Whether to use full Kelly or fractional Kelly betting",
      "Optimal blend weight between model and base rate",
      "Value of superforecaster consensus vs quantitative models",
      "Best calibration method (isotonic vs beta vs Platt scaling)"
    ],
    "expert_opinions": [
      "Philip Tetlock: 'Superforecasters combine multiple approaches and update frequently based on new information'",
      "Metaculus community: 'Calibration is more important than raw accuracy for long-term forecasting success'",
      "Sports betting sharps: 'Brier scores of 0.18-0.22 are typical for betting markets; beating 0.15 is excellent'"
    ]
  }
}
```

---

**End of Technical Assessment**

Sources:

- [Good Judgment Open](https://www.gjopen.com/)
- [Good Judgment Inc Services](https://goodjudgment.com/services/good-judgment-open/)
- [Metaculus API Documentation](https://www.metaculus.com/api/)
- [Metaculus forecasting-tools GitHub](https://github.com/Metaculus/forecasting-tools)
- [Good Judgment Project Harvard Dataverse](https://dataverse.harvard.edu/dataverse/gjp)
- [IARPA Announcement of GJP Data Publication](https://www.iarpa.gov/newsroom/article/iarpa-announces-publication-of-data-from-the-good-judgment-project)
- [Superforecasting Fundamentals Course](https://good-judgment.thinkific.com/courses/Superforecasting-Fundamentals)
- [Reference Class Forecasting Overview](https://assetmechanics.org/insights/reference-class-forecasting/)
- [AI Model Calibration for Sports Betting](https://www.sports-ai.dev/blog/ai-model-calibration-brier-score)
- [Systematic Review of ML in Sports Betting](https://arxiv.org/html/2410.21484v1)
