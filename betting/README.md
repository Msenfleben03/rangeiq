# Betting Module

## Purpose

The betting module handles all betting logic, calculations, and decision-making for the sports betting system. It converts model predictions into actionable bets by calculating expected value (EV), Closing Line Value (CLV), and optimal bet sizing using the Kelly criterion. This module is the bridge between predictive models and actual betting decisions.

**Core Principle**: CLV (Closing Line Value) is the primary success metric. Consistently beating the closing line predicts long-term profitability, even through losing streaks.

## Quick Start

```python
# Example: Evaluate a betting opportunity
from betting.ev import calculate_ev, calculate_edge
from betting.kelly import fractional_kelly
from betting.odds_converter import american_to_decimal, american_to_implied_prob

# Model says Duke has 58% chance to win
model_prob = 0.58

# Market odds: Duke -110 (American)
market_odds = -110
market_prob = american_to_implied_prob(market_odds)  # 52.38%

# Calculate edge
edge = calculate_edge(model_prob, market_odds)  # 5.62%

# Calculate expected value (EV) for $100 bet
decimal_odds = american_to_decimal(market_odds)  # 1.909
ev = calculate_ev(model_prob, decimal_odds, stake=100)  # $5.41

# Calculate Kelly bet size (using quarter Kelly)
kelly_fraction = fractional_kelly(
    win_prob=model_prob,
    decimal_odds=decimal_odds,
    fraction=0.25,  # Quarter Kelly for safety
    max_bet=0.03    # Never bet more than 3% of bankroll
)

print(f"Edge: {edge:.2%}")           # Edge: 5.62%
print(f"Expected Value: ${ev:.2f}")  # Expected Value: $5.41
print(f"Bet Size: {kelly_fraction:.2%} of bankroll")  # Bet Size: 1.47% of bankroll

# Decision: Bet if EV > 0 and edge > 1%
if ev > 0 and edge > 0.01:
    print("PLACE BET")
else:
    print("PASS")
```

## Installation

All dependencies included in main requirements.txt:

```bash
pip install -r requirements.txt
```

No additional packages required for betting calculations (pure Python + numpy/pandas).

## Components

### Expected Value (EV)

#### `ev.py` (Planned)

**Purpose**: Calculate expected value of bets to determine profitability

**Key Functions**:

- `calculate_ev(win_prob, decimal_odds, stake)`: Core EV calculation
- `calculate_edge(model_prob, market_odds)`: Your edge over the market
- `kelly_optimal_ev(win_prob, odds)`: EV-optimal Kelly bet size

**Usage**:

```python
from betting.ev import calculate_ev

# EV = (win_prob × profit) - (lose_prob × stake)
ev = calculate_ev(
    win_prob=0.55,           # 55% chance to win
    decimal_odds=1.91,       # -110 American odds
    stake=100.0              # $100 bet
)
# Returns: $4.05 (positive EV, profitable bet)
```

**Formulas**:

```python
# Expected Value
EV = (p × profit) - (q × stake)
where:
    p = win probability
    q = 1 - p (lose probability)
    profit = (decimal_odds - 1) × stake

# Edge over market
edge = model_prob - implied_market_prob
```

**Gotchas**:

- Small edges (1-3%) are normal and profitable long-term
- Need large sample size (100+ bets) to see EV materialize
- Variance can be brutal short-term even with +EV

---

### Closing Line Value (CLV)

#### `clv.py` (Planned)

**Purpose**: Calculate and track CLV - the #1 predictor of long-term success

**Key Functions**:

- `calculate_clv(odds_placed, odds_closing, stake)`: Single bet CLV
- `track_clv_history(bets_df)`: Aggregate CLV tracking
- `clv_to_roi(avg_clv, num_bets)`: Estimate ROI from CLV

**Usage**:

```python
from betting.clv import calculate_clv

# You bet Duke -105, line closed at Duke -110
clv = calculate_clv(
    odds_placed=-105,    # Your odds
    odds_closing=-110,   # Closing odds
    stake=100.0
)
# Returns: {'clv_percent': 0.95%, 'dollar_value': $0.95, 'would_bet': True}

# Positive CLV means you got better odds than the sharp closing line
```

**CLV Benchmarks**:

- **+0.5% CLV**: Profitable long-term
- **+1.0% CLV**: Very good, worth ~$1000 per 1000 bets
- **+2.0% CLV**: Excellent, professional level
- **Negative CLV**: Losing long-term, even if winning short-term

**Why CLV Matters More Than Win Rate**:

```python
# Scenario A: 60% win rate, -1% CLV
# Result: Losing long-term (betting stale lines, closing against you)

# Scenario B: 52% win rate, +1.5% CLV
# Result: Profitable long-term (beating the market consistently)

# The market is efficient - if closing line moves against you,
# you're likely betting bad numbers even if you're winning
```

---

### Kelly Criterion

#### `kelly.py` (Planned)

**Purpose**: Optimal bet sizing to maximize bankroll growth

**Key Functions**:

- `fractional_kelly(win_prob, decimal_odds, fraction=0.25)`: Safe Kelly sizing
- `full_kelly(win_prob, decimal_odds)`: Aggressive full Kelly (not recommended)
- `kelly_with_max(win_prob, decimal_odds, max_pct=0.03)`: Kelly with cap

**Usage**:

```python
from betting.kelly import fractional_kelly

# Quarter Kelly: Conservative, recommended
bet_size = fractional_kelly(
    win_prob=0.55,
    decimal_odds=1.91,
    fraction=0.25,       # Quarter Kelly
    max_bet=0.03         # Never exceed 3% of bankroll
)
# Returns: 0.0147 (bet 1.47% of bankroll)

# With $5000 bankroll
bankroll = 5000
bet_amount = bankroll * bet_size  # $73.50
```

**Kelly Fractions by Risk Tolerance**:
| Fraction | Name | Risk Level | Recommended For |
|----------|------|------------|-----------------|
| 0.10-0.15 | Deci/Eighth Kelly | Very Conservative | Beginners, <$1k bankroll |
| 0.20-0.25 | Quarter Kelly | Conservative | Standard (recommended) |
| 0.30-0.35 | Third Kelly | Moderate | Experienced, high confidence |
| 0.50 | Half Kelly | Aggressive | High risk tolerance |
| 1.00 | Full Kelly | Very Aggressive | Not recommended (huge variance) |

**Formulas**:

```python
# Full Kelly formula
f = (b × p - q) / b
where:
    f = fraction of bankroll to bet
    b = decimal_odds - 1 (profit per dollar bet)
    p = win probability
    q = 1 - p (lose probability)

# Fractional Kelly
bet_size = min(f × kelly_fraction, max_bet_pct)
```

**Critical Rules**:

- NEVER use full Kelly (variance destroys bankroll)
- ALWAYS cap max bet (3-5% recommended)
- Recalculate bankroll weekly, not after each bet
- Use worst-case odds if uncertain about model probability

---

### Odds Conversion

#### `odds_converter.py` (Planned)

**Purpose**: Convert between American, decimal, and implied probability formats

**Key Functions**:

- `american_to_decimal(american)`: Convert to decimal odds
- `decimal_to_american(decimal)`: Convert to American odds
- `american_to_implied_prob(american)`: Convert to probability
- `implied_prob_to_american(prob)`: Convert probability to American odds

**Usage**:

```python
from betting.odds_converter import (
    american_to_decimal,
    american_to_implied_prob,
    decimal_to_american
)

# American to decimal
decimal = american_to_decimal(-110)  # 1.909
decimal = american_to_decimal(+150)  # 2.50

# American to probability
prob = american_to_implied_prob(-110)  # 0.5238 (52.38%)
prob = american_to_implied_prob(+150)  # 0.4000 (40.00%)

# Decimal to American
american = decimal_to_american(1.91)  # -110
american = decimal_to_american(2.50)  # +150
```

**Common Odds Reference**:
| American | Decimal | Implied Prob | Break-Even |
|----------|---------|--------------|------------|
| -110 | 1.909 | 52.38% | 52.38% |
| -105 | 1.952 | 51.22% | 51.22% |
| +100 (Even) | 2.000 | 50.00% | 50.00% |
| +150 | 2.500 | 40.00% | 40.00% |
| -200 | 1.500 | 66.67% | 66.67% |

**Gotchas**:

- American odds jump from -101 to +100 (no odds between)
- Implied prob from American odds includes vig/juice
- Decimal odds include stake (1.91 = 0.91 profit + 1.00 stake)

---

### Line Shopping

#### `line_shopping.py` (Planned)

**Purpose**: Compare odds across multiple sportsbooks to find best value

**Key Functions**:

- `find_best_line(game_id, bet_type, sportsbooks)`: Get best available odds
- `calculate_vig(odds_home, odds_away)`: Calculate book's juice
- `arbitrage_opportunities(all_odds)`: Find risk-free arb opportunities

**Usage**:

```python
from betting.line_shopping import find_best_line

# Compare odds across books for Duke vs UNC
best_line = find_best_line(
    game_id='ncaab_20260125_duke_unc',
    bet_type='moneyline',
    selection='duke',
    sportsbooks=['draftkings', 'fanduel', 'betmgm', 'caesars']
)
# Returns: {'book': 'fanduel', 'odds': -105, 'timestamp': '2026-01-25T10:30:00Z'}

# Line shopping can gain 0.5-1% CLV vs single book
```

**Line Shopping Value**:

- **Single book**: Average -110 odds = 52.38% implied prob
- **Best of 4 books**: Average -107 odds = 51.69% implied prob
- **CLV Gain**: ~0.7% just from shopping

---

## Architecture Decisions

This module implements the following design decisions:

- **[ADR-003: Why CLV as Primary Metric](../docs/DECISIONS.md#adr-003)** — CLV predicts profitability better than win rate
- **[ADR-005: Fractional Kelly Sizing](../docs/DECISIONS.md#adr-005)** — Quarter Kelly balances growth and safety
- **[ADR-006: Line Shopping Required](../docs/DECISIONS.md#adr-006)** — Multi-book approach maximizes CLV

## Common Patterns

### Pattern 1: Complete Bet Evaluation Flow

```python
from betting.ev import calculate_ev, calculate_edge
from betting.kelly import fractional_kelly
from betting.odds_converter import american_to_decimal, american_to_implied_prob
from betting.clv import calculate_clv

def evaluate_bet(model_prob, market_odds, closing_odds=None, bankroll=5000):
    """
    Complete bet evaluation with EV, edge, Kelly sizing, and CLV.

    Returns:
        dict: Bet decision with all metrics
    """
    # Convert odds
    decimal_odds = american_to_decimal(market_odds)
    market_prob = american_to_implied_prob(market_odds)

    # Calculate edge and EV
    edge = calculate_edge(model_prob, market_odds)
    ev = calculate_ev(model_prob, decimal_odds, stake=100)

    # Kelly bet sizing
    kelly_pct = fractional_kelly(model_prob, decimal_odds, fraction=0.25, max_bet=0.03)
    bet_amount = bankroll * kelly_pct

    # CLV if closing odds available
    clv = None
    if closing_odds:
        clv = calculate_clv(market_odds, closing_odds)

    # Decision logic
    should_bet = (
        ev > 0 and           # Positive expected value
        edge > 0.01 and      # At least 1% edge
        kelly_pct > 0.01     # At least 1% Kelly recommendation
    )

    return {
        'should_bet': should_bet,
        'edge': edge,
        'ev': ev,
        'kelly_pct': kelly_pct,
        'bet_amount': bet_amount,
        'clv': clv
    }

# Use it
result = evaluate_bet(
    model_prob=0.58,
    market_odds=-110,
    closing_odds=-115,
    bankroll=5000
)

if result['should_bet']:
    print(f"BET ${result['bet_amount']:.2f}")
    print(f"Edge: {result['edge']:.2%}, EV: ${result['ev']:.2f}")
```

### Pattern 2: Bankroll Management

```python
# CORRECT: Update bankroll weekly, not per bet
weekly_bankroll = get_current_bankroll()  # Check once per week
bet_size = weekly_bankroll * kelly_fraction

# ❌ WRONG: Updating after every bet causes over-betting
# Don't do this - Kelly was designed for fixed periodic rebalancing
for game in games:
    bet_size = get_current_bankroll() * kelly_fraction  # TOO VOLATILE
```

### Pattern 3: Handling Uncertainty in Model Probabilities

```python
# When model gives 56% but you're uncertain, use worst-case
model_prob = 0.56
uncertainty = 0.03  # ±3% uncertainty

# Conservative approach: Use lower bound
conservative_prob = model_prob - uncertainty  # 0.53
bet_size = fractional_kelly(conservative_prob, decimal_odds)

# This prevents over-betting on uncertain predictions
```

### Pattern 4: Vig/Juice Removal

```python
from betting.odds_converter import american_to_implied_prob

# Market has -110 both sides (total = 104.76%, 4.76% vig)
home_prob = american_to_implied_prob(-110)  # 52.38%
away_prob = american_to_implied_prob(-110)  # 52.38%

# Remove vig to get true probabilities
def remove_vig(prob_a, prob_b):
    total = prob_a + prob_b
    return prob_a / total, prob_b / total

true_home, true_away = remove_vig(home_prob, away_prob)
# Returns: (0.50, 0.50) - fair 50/50 line
```

## Testing

Run tests for betting module:

```bash
# All betting tests
pytest tests/test_betting.py -v

# Specific calculations
pytest tests/test_betting.py::test_calculate_ev -v
pytest tests/test_betting.py::test_kelly_criterion -v
pytest tests/test_betting.py::test_clv_calculation -v

# With coverage
pytest tests/test_betting.py --cov=betting --cov-report=html
```

## Performance Considerations

- **Speed**: All calculations are O(1), extremely fast
- **Memory**: Minimal (just storing calculation results)
- **Scaling**: Can evaluate thousands of bets per second

**No optimization needed** - betting calculations are trivial computationally.

## Examples

### Example 1: Daily Betting Workflow

```python
"""
Evaluate all today's games and generate bet recommendations
"""
from models.elo import EloRating
from betting.ev import calculate_ev
from betting.kelly import fractional_kelly
from data.odds import fetch_current_odds

# Load model predictions
elo = EloRating()
elo.load('models/saved/ncaab_elo.pkl')

# Fetch current odds from all books
games = fetch_current_odds(sport='ncaab', date='2026-01-25')

recommendations = []

for game in games:
    # Get model prediction
    model_prob = elo.predict_game(game['home_team'], game['away_team'])

    # Get best available odds (line shopping)
    best_odds = max(game['odds'], key=lambda x: x['value'])

    # Evaluate bet
    ev = calculate_ev(model_prob, best_odds['decimal'])
    kelly = fractional_kelly(model_prob, best_odds['decimal'])

    if ev > 0 and kelly > 0.01:
        recommendations.append({
            'game': f"{game['away_team']} @ {game['home_team']}",
            'bet': game['home_team'],
            'odds': best_odds['american'],
            'book': best_odds['sportsbook'],
            'ev': ev,
            'kelly_pct': kelly,
            'model_prob': model_prob
        })

# Sort by EV (highest first)
recommendations.sort(key=lambda x: x['ev'], reverse=True)

# Display top 10
for i, rec in enumerate(recommendations[:10], 1):
    print(f"{i}. {rec['game']}")
    print(f"   Bet {rec['bet']} @ {rec['odds']} ({rec['book']})")
    print(f"   EV: ${rec['ev']:.2f}, Kelly: {rec['kelly_pct']:.2%}")
```

### Example 2: CLV Tracking and Analysis

```python
"""
Track CLV over last 100 bets to validate model performance
"""
import pandas as pd
from betting.clv import calculate_clv

# Load bet history from database
bets = pd.read_sql("SELECT * FROM bets WHERE result IS NOT NULL ORDER BY created_at DESC LIMIT 100", conn)

clv_results = []

for _, bet in bets.iterrows():
    clv = calculate_clv(
        odds_placed=bet['odds_placed'],
        odds_closing=bet['odds_closing']
    )
    clv_results.append(clv['clv_percent'])

# Calculate statistics
avg_clv = np.mean(clv_results)
std_clv = np.std(clv_results)
positive_clv_rate = sum(1 for clv in clv_results if clv > 0) / len(clv_results)

print(f"Last 100 Bets CLV Analysis:")
print(f"  Average CLV: {avg_clv:.2%}")
print(f"  Std Dev: {std_clv:.2%}")
print(f"  Positive CLV Rate: {positive_clv_rate:.1%}")

# Decision: If avg CLV < 0, stop betting and fix model
if avg_clv < 0:
    print("⚠️  WARNING: Negative CLV - model needs improvement")
elif avg_clv > 0.005:
    print("✅ Model is profitable long-term")
```

## Error Handling

Common errors and solutions:

### Error: Kelly recommends >10% of bankroll

```python
# Error: Kelly formula can suggest huge bets on high-edge opportunities
kelly_pct = full_kelly(0.70, 2.00)  # Could return 0.40 (40%!)

# Solution: Always use fractional Kelly with max bet cap
kelly_pct = fractional_kelly(
    win_prob=0.70,
    decimal_odds=2.00,
    fraction=0.25,    # Quarter Kelly
    max_bet=0.03      # Never exceed 3%
)
# Returns: 0.03 (capped at 3%)
```

### Error: Odds conversion gives probability >1.0

```python
# Error: Invalid American odds input
try:
    prob = american_to_implied_prob(0)  # 0 is invalid
except ValueError as e:
    print(f"Invalid odds: {e}")

# Solution: Validate odds before conversion
def validate_american_odds(odds):
    if odds == 0:
        raise ValueError("Odds cannot be 0")
    if abs(odds) > 10000:
        raise ValueError("Odds seem unrealistic")
    return odds
```

### Error: Negative EV but model says to bet

```python
# Error: Model probability might be wrong or vig is too high
model_prob = 0.52
market_odds = -110
ev = calculate_ev(model_prob, american_to_decimal(market_odds))

if ev < 0:
    # Solution: Check if edge is truly there
    market_prob = american_to_implied_prob(market_odds)
    print(f"Model: {model_prob:.2%}, Market: {market_prob:.2%}")

    # If model prob < market prob + 1%, edge is too small
    if model_prob < market_prob + 0.01:
        print("Edge too small or non-existent - PASS")
```

## References

### Related Modules

- `models/` — Generates win probabilities for bet evaluation
- `tracking/` — Stores bet history for CLV analysis
- `data/odds/` — Fetches current market odds

### External Documentation

- Kelly Criterion: https://en.wikipedia.org/wiki/Kelly_criterion
- Expected Value: https://www.investopedia.com/terms/e/expectedvalue.asp
- Closing Line Value: https://www.pinnacle.com/en/betting-articles/educational/closing-line-value

### Domain Knowledge

- [CLAUDE.md: Betting Formulas](../CLAUDE.md#key-formulas)
- [CLAUDE.md: Bankroll Management](../CLAUDE.md#bankroll--risk-management)
- [docs/RISK_MANAGEMENT_COMPACT.md](../docs/RISK_MANAGEMENT_COMPACT.md)

## Contributing

When modifying this module:

1. **Update docstrings** for any changed functions (Google style)
2. **Add tests** for new calculations (>90% coverage required for betting logic)
3. **Update this README** if new components added
4. **Create ADR** for changes to bet sizing or evaluation logic
5. **Validate formulas** against known examples (e.g., Kelly calculator)

**Validation Checklist**:

- [ ] Kelly formula matches academic sources
- [ ] EV calculation verified with hand calculations
- [ ] CLV correctly handles positive/negative odds
- [ ] Odds conversions are reversible (american → decimal → american)
- [ ] No edge cases produce NaN or infinity

## Roadmap

### Phase 1: Foundation (Week 2) - Current

- [ ] Implement `odds_converter.py` with all conversion functions
- [ ] Implement `ev.py` with EV and edge calculations
- [ ] Implement `clv.py` with CLV tracking

### Phase 2: Advanced Sizing (Week 3)

- [ ] Implement `kelly.py` with fractional Kelly
- [ ] Add Kelly with correlation adjustment for parlays
- [ ] Implement bankroll tracking and updates

### Phase 3: Line Shopping (Week 4)

- [ ] Implement `line_shopping.py` multi-book comparison
- [ ] Add arbitrage detection
- [ ] Create odds aggregation pipeline

### Phase 4: Continuous Improvement (Ongoing)

- [ ] Track CLV by sport, bet type, model
- [ ] Optimize Kelly fraction based on historical variance
- [ ] Integrate with live betting (in-game odds)

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2026-01-24 | Initial README with comprehensive betting logic documentation |

## Troubleshooting

### Issue 1: Consistent Negative CLV

**Symptom**: Average CLV over 50+ bets is negative

**Cause**: Betting stale lines or model is not predictive

**Solution**:

1. Check odds timestamp - bet closer to game time
2. Use line shopping to get best available odds
3. Validate model on out-of-sample data
4. Stop betting until model improves

### Issue 2: Kelly Recommends Unrealistic Bets

**Symptom**: Kelly suggests 20%+ of bankroll

**Cause**: Model probability is overconfident or odds are mispriced

**Solution**:

```python
# Add uncertainty buffer
adjusted_prob = model_prob - 0.03  # Subtract 3% for uncertainty
kelly_pct = fractional_kelly(adjusted_prob, decimal_odds, fraction=0.25)

# Or use stricter max bet
kelly_pct = min(kelly_pct, 0.02)  # Never exceed 2%
```

### Issue 3: EV Positive But Still Losing

**Symptom**: +EV bets but bankroll decreasing

**Cause**: Sample size too small (variance), bad bankroll management, or model edge disappeared

**Solution**:

1. Check sample size (need 100+ bets to see edge)
2. Verify CLV is still positive
3. Reduce bet sizing during downswing
4. Re-validate model on recent data

---

**Maintained by**: Betting Strategy Team
**Last Updated**: 2026-02-12
**Status**: Active - Foundation Phase
