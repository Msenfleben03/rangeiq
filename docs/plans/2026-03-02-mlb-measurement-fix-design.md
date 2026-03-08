# MLB Model Measurement Fix — Design Document

> **Status:** Approved for implementation (Session 38/39)
> **Approved Option:** Option A — Fix CLV + edge de-vigging together in a single commit

## Problem

The MLB backtest reports two metrics that are biased by sportsbook vig:

1. **Edge**: `cal_prob - raw_implied_close`
   - Raw implied prob includes vig (e.g., -110/-110 → 52.38%/52.38%, sums to 104.76%)
   - True "fair" market for -110/-110 is 50%/50%, not 52.38%/52.38%
   - Effect: stated edge of +8.15% is ~2.4pp vig-inflated → true edge ≈ 5.75%

2. **CLV**: `(raw_implied_close - raw_implied_open) / raw_implied_open`
   - Same vig distortion on both sides
   - Effect: stated -1.23% avg CLV is approximately -3% to -4% true CLV

These biases make the model look better than it is. The current measurements give a false sense
of edge, and the bet filter at `EDGE_THRESHOLD = 3%` is too permissive against de-vigged market.

## Solution

**Multiplicative de-vig (Pinnacle standard):**

```python
# De-vig one side of a two-way market
raw_home = american_to_implied_prob(home_ml)   # e.g. 0.5238 for -110
raw_away = american_to_implied_prob(away_ml)   # e.g. 0.5238 for -110
total = raw_home + raw_away                    # e.g. 1.0476
fair_home = raw_home / total                   # e.g. 0.5000
fair_away = raw_away / total                   # e.g. 0.5000 = 1 - fair_home
```

**Updated Edge:**
```python
edge_home = cal_prob - fair_home_close
edge_away = (1 - cal_prob) - fair_away_close
```

**Updated CLV:**
```python
fair_home_open  = devig_prob(home_ml_open, away_ml_open)
fair_home_close = devig_prob(home_ml_close, away_ml_close)
clv = (fair_home_close - fair_home_open) / fair_home_open
```

## What Changes Behaviorally

| Metric | Before | After |
|--------|--------|-------|
| Edge per bet | ~2.4pp inflated | True edge |
| Avg CLV | ~2pp inflated | True CLV |
| Bet volume at 3% threshold | Baseline | May increase (de-vigged edges are naturally higher) |

Note: Because de-vigged fair probs are LOWER than raw implied probs, `cal_prob - fair_prob` will
be LARGER than `cal_prob - raw_implied_prob` for the same game. At a fixed 3% threshold, more
bets may be placed. Monitor and potentially raise threshold in a follow-up sprint.

## What Does NOT Change

- Prediction accuracy (56.1%) — model probabilities unchanged
- Log loss — model probabilities unchanged
- ROI calculation — stake × (decimal_odds - 1) unchanged
- Kelly stake calculation — already uses model prob + decimal odds
- `calculate_clv()` in `betting/odds_converter.py` — used by NCAAB, not MLB

## Files Changed

| File | Change |
|------|--------|
| `betting/odds_converter.py` | Add `devig_prob(american_side, american_other) -> float` |
| `scripts/mlb_backtest.py` | Replace raw edge + raw CLV with de-vigged versions |
| `tests/test_odds_converter.py` | New file — tests for `devig_prob` |

## Success Criteria

- `devig_prob(-110, -110)` returns exactly 0.5
- De-vigged CLV ≈ 2pp lower than raw CLV (more negative)
- De-vigged edge ≈ 2pp higher than raw edge for same game
- Backtest still runs to completion without errors
