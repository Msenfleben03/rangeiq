# MLB Model Measurement Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix vig-inflated CLV and edge calculations in the MLB backtest by de-vigging both sides of the market.

**Architecture:** Add a `devig_prob()` utility to `betting/odds_converter.py`, then update `scripts/mlb_backtest.py` to use de-vigged fair probabilities for both edge and CLV. Two-way markets sum raw implied probs > 1.0; dividing each side by the total gives the fair (no-vig) probability.

**Tech Stack:** Python 3.11+, pandas, no new dependencies.

---

## Task 1: Add `devig_prob` utility

**Files:**
- Modify: `betting/odds_converter.py` (add function after `calculate_clv`)
- Create: `tests/test_odds_converter.py`

### Step 1: Write failing tests

```python
# tests/test_odds_converter.py
"""Tests for betting/odds_converter.py."""
import pytest
from betting.odds_converter import (
    american_to_implied_prob,
    devig_prob,
)


def test_devig_prob_symmetric_market():
    """Standard -110/-110 market → both sides = 50%."""
    result = devig_prob(-110, -110)
    assert abs(result - 0.5) < 1e-6


def test_devig_prob_sums_to_one():
    """De-vigged home + de-vigged away = 1.0."""
    home = devig_prob(-120, +105)
    away = devig_prob(+105, -120)
    assert abs(home + away - 1.0) < 1e-6


def test_devig_prob_favorite_above_half():
    """-120 favorite de-vigs above 50%."""
    result = devig_prob(-120, +105)
    assert result > 0.5


def test_devig_prob_underdog_below_half():
    """+105 underdog de-vigs below 50%."""
    result = devig_prob(+105, -120)
    assert result < 0.5


def test_devig_prob_lower_than_raw():
    """De-vigged prob is always lower than raw implied prob (vig removed)."""
    raw = american_to_implied_prob(-110)
    fair = devig_prob(-110, -110)
    assert fair < raw


def test_devig_prob_invalid_zero():
    """american=0 should raise ValueError."""
    with pytest.raises(ValueError):
        devig_prob(0, -110)
```

### Step 2: Run to confirm tests fail

```bash
cd C:\Users\msenf\sports-betting && venv/Scripts/python.exe -m pytest tests/test_odds_converter.py -v
```

Expected: `ImportError: cannot import name 'devig_prob'`

### Step 3: Implement `devig_prob`

In `betting/odds_converter.py`, add after the `calculate_clv` function (after line 141):

```python
def devig_prob(american_side: int, american_other: int) -> float:
    """De-vig one side of a two-way market using multiplicative normalization.

    Divides each side's raw implied probability by the sum of both sides,
    yielding the fair (no-vig) probability. Industry standard (Pinnacle method).

    Args:
        american_side: American odds for the side to de-vig.
        american_other: American odds for the opposing side.

    Returns:
        Fair probability for american_side (0 to 1).

    Raises:
        ValueError: If either odds value is 0, or the total is non-positive.

    Examples:
        >>> devig_prob(-110, -110)
        0.5
        >>> devig_prob(-120, +105)  # favorite side
        0.5279...
    """
    raw_side = american_to_implied_prob(american_side)
    raw_other = american_to_implied_prob(american_other)
    total = raw_side + raw_other
    if total <= 0:
        raise ValueError(f"Sum of raw probabilities must be positive, got {total}")
    return raw_side / total
```

### Step 4: Run tests to confirm they pass

```bash
cd C:\Users\msenf\sports-betting && venv/Scripts/python.exe -m pytest tests/test_odds_converter.py -v
```

Expected: 6 passed

### Step 5: Run ruff

```bash
cd C:\Users\msenf\sports-betting && venv/Scripts/python.exe -m ruff check betting/odds_converter.py && venv/Scripts/python.exe -m ruff format betting/odds_converter.py
```

### Step 6: Commit

```bash
git add betting/odds_converter.py tests/test_odds_converter.py
git commit -m "feat(betting): add devig_prob() for multiplicative de-vig of two-way markets"
```

---

## Task 2: Fix edge calculation in `mlb_backtest.py`

**Files:**
- Modify: `scripts/mlb_backtest.py:24` (add import) and `scripts/mlb_backtest.py:333-345` (edge block)

### Step 1: Update the import line at the top

Current line 24:
```python
from betting.odds_converter import american_to_decimal, american_to_implied_prob
```

Replace with:
```python
from betting.odds_converter import american_to_decimal, american_to_implied_prob, devig_prob
```

### Step 2: Replace the edge calculation block

Current block (lines 333–345):
```python
        if home_ml_close is not None:
            try:
                implied_home_close = american_to_implied_prob(int(home_ml_close))
                edge_home = cal_prob - implied_home_close
            except (ValueError, TypeError):
                pass

        if away_ml_close is not None:
            try:
                implied_away_close = american_to_implied_prob(int(away_ml_close))
                edge_away = (1 - cal_prob) - implied_away_close
            except (ValueError, TypeError):
                pass
```

Replace with (de-vig both sides together when available, fall back to single-sided):
```python
        if home_ml_close is not None and away_ml_close is not None:
            try:
                fair_home_close = devig_prob(int(home_ml_close), int(away_ml_close))
                fair_away_close = 1.0 - fair_home_close
                edge_home = cal_prob - fair_home_close
                edge_away = (1 - cal_prob) - fair_away_close
            except (ValueError, TypeError):
                pass
        elif home_ml_close is not None:
            try:
                edge_home = cal_prob - american_to_implied_prob(int(home_ml_close))
            except (ValueError, TypeError):
                pass
        elif away_ml_close is not None:
            try:
                edge_away = (1 - cal_prob) - american_to_implied_prob(int(away_ml_close))
            except (ValueError, TypeError):
                pass
```

### Step 3: Run ruff

```bash
cd C:\Users\msenf\sports-betting && venv/Scripts/python.exe -m ruff check scripts/mlb_backtest.py && venv/Scripts/python.exe -m ruff format scripts/mlb_backtest.py
```

### Step 4: Smoke test — verify script still runs

```bash
cd C:\Users\msenf\sports-betting && venv/Scripts/python.exe scripts/mlb_backtest.py --pitcher-adj --calibrated --odds --test-season 2025 2>&1 | head -30
```

Expected: no import errors, backtest starts loading data.

### Step 5: Commit edge fix

```bash
git add scripts/mlb_backtest.py
git commit -m "fix(mlb-backtest): de-vig edge calculation against fair close probabilities"
```

---

## Task 3: Fix CLV calculation in `mlb_backtest.py`

**Files:**
- Modify: `scripts/mlb_backtest.py:384-400` (CLV block)

### Step 1: Replace the CLV calculation block

Current block (lines 384–400):
```python
        # CLV: compare opening to closing (if opening available)
        if bet_side == "home" and home_ml_open is not None and home_ml_close is not None:
            try:
                imp_open = american_to_implied_prob(int(home_ml_open))
                imp_close = american_to_implied_prob(int(home_ml_close))
                if imp_open > 0:
                    clv = (imp_close - imp_open) / imp_open
            except (ValueError, TypeError):
                pass
        elif bet_side == "away" and away_ml_open is not None and away_ml_close is not None:
            try:
                imp_open = american_to_implied_prob(int(away_ml_open))
                imp_close = american_to_implied_prob(int(away_ml_close))
                if imp_open > 0:
                    clv = (imp_close - imp_open) / imp_open
            except (ValueError, TypeError):
                pass
```

Replace with (requires all 4 odds for de-vig; skips CLV if any are missing):
```python
        # CLV: de-vigged open vs de-vigged close (requires all 4 odds)
        has_all_four = all(
            x is not None for x in [home_ml_open, away_ml_open, home_ml_close, away_ml_close]
        )
        if bet_side == "home" and has_all_four:
            try:
                fair_home_open = devig_prob(int(home_ml_open), int(away_ml_open))
                fair_home_close = devig_prob(int(home_ml_close), int(away_ml_close))
                if fair_home_open > 0:
                    clv = (fair_home_close - fair_home_open) / fair_home_open
            except (ValueError, TypeError):
                pass
        elif bet_side == "away" and has_all_four:
            try:
                fair_away_open = devig_prob(int(away_ml_open), int(home_ml_open))
                fair_away_close = devig_prob(int(away_ml_close), int(home_ml_close))
                if fair_away_open > 0:
                    clv = (fair_away_close - fair_away_open) / fair_away_open
            except (ValueError, TypeError):
                pass
```

### Step 2: Run ruff

```bash
cd C:\Users\msenf\sports-betting && venv/Scripts/python.exe -m ruff check scripts/mlb_backtest.py && venv/Scripts/python.exe -m ruff format scripts/mlb_backtest.py
```

### Step 3: Commit CLV fix

```bash
git add scripts/mlb_backtest.py
git commit -m "fix(mlb-backtest): de-vig CLV calculation using all 4 odds (open + close, both sides)"
```

---

## Task 4: Run corrected backtests + update memory

### Step 1: Run 2024 test

```bash
cd C:\Users\msenf\sports-betting && venv/Scripts/python.exe scripts/mlb_backtest.py --pitcher-adj --calibrated --odds --test-season 2024
```

Record: new Avg CLV and Avg positive edge values.

### Step 2: Run 2025 test

```bash
cd C:\Users\msenf\sports-betting && venv/Scripts/python.exe scripts/mlb_backtest.py --pitcher-adj --calibrated --odds --test-season 2025
```

Record: new Avg CLV and Avg positive edge values.

### Step 3: Verify CLV improved (got more negative) and edge got higher

Expected changes vs old results:
- Avg CLV should be ~2pp more negative (e.g., -1.23% → ~-3%)
- Avg positive edge should be ~2pp higher (e.g., +8.15% → ~+10%)
- ROI should be unchanged or near-unchanged

If CLV got MORE NEGATIVE and edge got HIGHER: fix is working as expected.
If CLV is unchanged: check that the `devig_prob` import is actually being called.

### Step 4: Update MEMORY.md with corrected numbers

Update the `MLB Backtest 4-Cell Results` table in `memory/MEMORY.md` with new de-vigged CLV and edge values.

### Step 5: Final test suite run

```bash
cd C:\Users\msenf\sports-betting && venv/Scripts/python.exe -m pytest tests/test_odds_converter.py tests/test_mlb_backfill_odds.py tests/test_mlb_poisson_model.py -v
```

Expected: all pass (no regressions).

### Step 6: Final commit (memory update)

```bash
git add memory/MEMORY.md
git commit -m "chore: update MLB backtest results with de-vigged CLV/edge numbers"
```

---

## Sanity Checks

| Check | How |
|-------|-----|
| `devig_prob(-110, -110) == 0.5` | `test_devig_prob_symmetric_market` |
| De-vigged probs sum to 1.0 | `test_devig_prob_sums_to_one` |
| CLV is ~2pp more negative | Compare printed Avg CLV before/after |
| Edge is ~2pp higher | Compare printed Avg positive edge before/after |
| ROI is similar | Same P&L math, so ROI should barely change |
| No regressions | pytest on 3 test files |

## What This Does NOT Fix

- ROI is still negative (model has no CLV yet — that's the next sprint)
- Away favorites still look bad (structural market issue)
- Bet volume may increase slightly — monitor but don't tune threshold yet
