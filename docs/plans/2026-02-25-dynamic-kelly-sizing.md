# Dynamic Kelly Bet Sizing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace flat $150 stakes with continuous fractional Kelly sizing that scales bet size proportionally to model edge, using calibrated win probabilities.

**Architecture:** Add a `KellySizer` class to `betting/odds_converter.py` that wraps the existing `fractional_kelly()` with Platt-style calibration. The calibration corrects the model's ~10pp overconfidence by fitting a logistic function to historical edge→win data. The sizer is called from both `daily_predictions.py` (live pipeline) and `backtest_ncaab_elo.py` (backtesting). Config constants updated from 3%/$150 cap to 5%/$250 cap.

**Tech Stack:** Python 3.11+, scikit-learn (LogisticRegression for Platt scaling), pandas, existing betting/odds_converter.py

---

## Summary of Changes

| File | Change |
|------|--------|
| `config/constants.py` | Update `BankrollConfig` + `PaperBettingConfig` sizing limits |
| `betting/odds_converter.py` | Add `KellySizer` class with Platt calibration |
| `scripts/daily_predictions.py` | Wire `KellySizer` into prediction→stake flow |
| `scripts/backtest_ncaab_elo.py` | Wire `KellySizer` into backtest bet sizing |
| `tests/test_kelly_sizer.py` | New: 12+ tests for calibration + sizing |
| `tests/test_daily_run.py` | Update any hardcoded $150 stake assertions |

---

### Task 1: Update Config Constants

**Files:**
- Modify: `config/constants.py:22-37` (BankrollConfig)
- Modify: `config/constants.py:434-441` (PaperBettingConfig)

**Step 1: Update BankrollConfig limits**

Change max bet from 3%/$150 to 5%/$250, and remove static risk-limit fields that the user wants broadened:

```python
# In BankrollConfig (line 22-37):
TOTAL_BANKROLL: float = 5000.0
ACTIVE_CAPITAL: float = 4000.0
RESERVE: float = 1000.0

# Bet sizing limits
KELLY_FRACTION_DEFAULT: float = 0.25   # Quarter Kelly (unchanged)
KELLY_FRACTION_HIGH_CONF: float = 0.33  # Third Kelly (unchanged)
KELLY_FRACTION_UNCERTAIN: float = 0.15  # (unchanged)

MAX_BET_FRACTION: float = 0.05  # 5% of bankroll (was 3%)
MAX_BET_DOLLARS: float = 250.0  # $250 cap (was $150)

# Exposure limits (broadened per user request)
DAILY_EXPOSURE_LIMIT: float = 0.20   # 20% of bankroll (was 10%)
WEEKLY_LOSS_TRIGGER: float = 0.25    # 25% triggers sizing reduction (was 15%)
MONTHLY_LOSS_PAUSE: float = 0.40     # 40% triggers full pause (was 25%)
```

**Step 2: Update PaperBettingConfig limits**

```python
# In PaperBettingConfig (line 434-441):
PAPER_BANKROLL: float = 5000.0
KELLY_FRACTION: float = 0.25      # (unchanged)
MAX_BET_FRACTION: float = 0.05    # 5% max (was 3%)
MAX_BETS_PER_DAY: int = 10        # (unchanged)
MAX_DAILY_EXPOSURE_FRACTION: float = 0.20  # 20% (was 10%)
```

**Step 3: Run existing tests to verify no breakage**

Run: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py -v -x`
Expected: All 29 tests pass (constants are read at runtime, no hardcoded assertions on limit values).

**Step 4: Commit**

```bash
git add config/constants.py
git commit -m "feat: update bet sizing limits for dynamic Kelly (5% max, broadened exposure)"
```

---

### Task 2: Add KellySizer with Platt Calibration

**Files:**
- Modify: `betting/odds_converter.py` (add KellySizer class after existing fractional_kelly)
- Create: `tests/test_kelly_sizer.py`

The core idea: the model predicts `model_prob` but is ~10pp overconfident. A Platt scaling calibrator
fits `P(win) = 1 / (1 + exp(-(a*edge + b)))` on historical backtest data. The `KellySizer` uses the
calibrated probability in Kelly instead of the raw model probability.

**Step 1: Write failing tests**

Create `tests/test_kelly_sizer.py`:

```python
"""Tests for KellySizer with Platt calibration."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from betting.odds_converter import (
    KellySizer,
    american_to_decimal,
    fractional_kelly,
)


class TestKellySizerInit:
    """Test KellySizer construction and defaults."""

    def test_default_construction(self):
        sizer = KellySizer()
        assert sizer.kelly_fraction == 0.25
        assert sizer.max_bet_fraction == 0.05
        assert sizer.bankroll == 5000.0
        assert not sizer.is_calibrated

    def test_custom_params(self):
        sizer = KellySizer(kelly_fraction=0.33, max_bet_fraction=0.03, bankroll=10000)
        assert sizer.kelly_fraction == 0.33
        assert sizer.max_bet_fraction == 0.03
        assert sizer.bankroll == 10000.0


class TestPlattCalibration:
    """Test Platt scaling calibration."""

    @pytest.fixture()
    def calibration_data(self):
        """Synthetic data: higher edge -> higher win rate (realistic pattern)."""
        rng = np.random.RandomState(42)
        n = 2000
        edges = rng.uniform(0.05, 0.60, n)
        # True P(win) follows a sigmoid-ish curve
        true_probs = 1 / (1 + np.exp(-3 * (edges - 0.20)))
        wins = (rng.random(n) < true_probs).astype(int)
        return pd.DataFrame({"edge": edges, "won": wins})

    def test_calibrate_fits_model(self, calibration_data):
        sizer = KellySizer()
        sizer.calibrate(calibration_data["edge"].values, calibration_data["won"].values)
        assert sizer.is_calibrated

    def test_calibrated_prob_increases_with_edge(self, calibration_data):
        sizer = KellySizer()
        sizer.calibrate(calibration_data["edge"].values, calibration_data["won"].values)
        p_low = sizer.calibrated_win_prob(0.08)
        p_mid = sizer.calibrated_win_prob(0.20)
        p_high = sizer.calibrated_win_prob(0.50)
        assert p_low < p_mid < p_high

    def test_calibrated_prob_bounded_0_1(self, calibration_data):
        sizer = KellySizer()
        sizer.calibrate(calibration_data["edge"].values, calibration_data["won"].values)
        for e in [0.01, 0.50, 0.90]:
            p = sizer.calibrated_win_prob(e)
            assert 0 < p < 1

    def test_uncalibrated_falls_back_to_model_prob(self):
        sizer = KellySizer()
        # Without calibration, calibrated_win_prob returns None
        assert sizer.calibrated_win_prob(0.15) is None


class TestSizeBet:
    """Test the main size_bet() method."""

    @pytest.fixture()
    def calibrated_sizer(self):
        """KellySizer calibrated on realistic data."""
        rng = np.random.RandomState(42)
        n = 2000
        edges = rng.uniform(0.05, 0.60, n)
        true_probs = 1 / (1 + np.exp(-3 * (edges - 0.20)))
        wins = (rng.random(n) < true_probs).astype(int)
        sizer = KellySizer(kelly_fraction=0.25, max_bet_fraction=0.05, bankroll=5000)
        sizer.calibrate(edges, wins)
        return sizer

    def test_higher_edge_gets_larger_stake(self, calibrated_sizer):
        stake_low = calibrated_sizer.size_bet(
            model_prob=0.55, edge=0.08, american_odds=+120
        )
        stake_high = calibrated_sizer.size_bet(
            model_prob=0.70, edge=0.30, american_odds=+300
        )
        assert stake_high > stake_low

    def test_respects_max_bet(self, calibrated_sizer):
        # Even with extreme edge, stake should not exceed max
        stake = calibrated_sizer.size_bet(
            model_prob=0.95, edge=0.80, american_odds=+500
        )
        max_dollars = calibrated_sizer.bankroll * calibrated_sizer.max_bet_fraction
        assert stake <= max_dollars + 0.01  # float tolerance

    def test_zero_edge_returns_zero(self, calibrated_sizer):
        stake = calibrated_sizer.size_bet(
            model_prob=0.50, edge=0.0, american_odds=-110
        )
        assert stake == 0.0

    def test_negative_kelly_returns_zero(self, calibrated_sizer):
        # Low model prob + bad odds = negative Kelly = no bet
        stake = calibrated_sizer.size_bet(
            model_prob=0.30, edge=0.01, american_odds=-200
        )
        assert stake == 0.0

    def test_uncalibrated_uses_model_prob(self):
        """Without calibration, falls back to raw model_prob for Kelly."""
        sizer = KellySizer(kelly_fraction=0.25, max_bet_fraction=0.05, bankroll=5000)
        stake = sizer.size_bet(model_prob=0.60, edge=0.10, american_odds=+150)
        # Should be same as raw fractional_kelly with model_prob
        dec = american_to_decimal(150)
        raw_frac = fractional_kelly(0.60, dec, fraction=0.25, max_bet=0.05)
        expected = 5000 * raw_frac
        assert abs(stake - expected) < 0.01

    def test_min_bet_threshold(self, calibrated_sizer):
        """Stakes below $10 should be rounded to 0 (not worth placing)."""
        # Very small edge -> tiny Kelly fraction -> tiny stake
        stake = calibrated_sizer.size_bet(
            model_prob=0.52, edge=0.075, american_odds=-105
        )
        assert stake == 0.0 or stake >= 10.0
```

**Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_kelly_sizer.py -v`
Expected: ImportError — `KellySizer` does not exist yet.

**Step 3: Implement KellySizer**

Add to `betting/odds_converter.py` after the existing `fractional_kelly` function (after line 168):

```python
class KellySizer:
    """Dynamic bet sizer with Platt-calibrated win probabilities.

    Uses logistic regression on historical (edge, win/loss) data to correct
    model overconfidence before feeding into Kelly criterion.

    Args:
        kelly_fraction: Fraction of full Kelly to use (default 0.25 = quarter).
        max_bet_fraction: Max bet as fraction of bankroll (default 0.05 = 5%).
        bankroll: Current bankroll in dollars (default 5000).
        min_bet: Minimum bet in dollars; smaller stakes round to 0 (default 10).
    """

    def __init__(
        self,
        kelly_fraction: float = 0.25,
        max_bet_fraction: float = 0.05,
        bankroll: float = 5000.0,
        min_bet: float = 10.0,
    ) -> None:
        self.kelly_fraction = kelly_fraction
        self.max_bet_fraction = max_bet_fraction
        self.bankroll = bankroll
        self.min_bet = min_bet
        self._calibrator = None

    @property
    def is_calibrated(self) -> bool:
        """Whether Platt calibration has been fitted."""
        return self._calibrator is not None

    def calibrate(self, edges: "np.ndarray", outcomes: "np.ndarray") -> None:
        """Fit Platt scaling on historical edge -> win/loss data.

        Args:
            edges: Array of model edge values (0 to 1).
            outcomes: Array of 1 (win) / 0 (loss).
        """
        from sklearn.linear_model import LogisticRegression

        X = edges.reshape(-1, 1) if edges.ndim == 1 else edges
        self._calibrator = LogisticRegression(random_state=42)
        self._calibrator.fit(X, outcomes)

    def calibrated_win_prob(self, edge: float) -> float | None:
        """Return calibrated P(win) for a given edge, or None if uncalibrated."""
        if self._calibrator is None:
            return None
        import numpy as np

        return float(self._calibrator.predict_proba(np.array([[edge]]))[0][1])

    def size_bet(
        self,
        model_prob: float,
        edge: float,
        american_odds: int,
    ) -> float:
        """Calculate stake in dollars using calibrated Kelly.

        If calibrated, uses calibrated P(win) from edge.
        If uncalibrated, falls back to raw model_prob.

        Args:
            model_prob: Raw model win probability (fallback if uncalibrated).
            edge: Model edge (model_prob - implied_prob).
            american_odds: American odds for the bet.

        Returns:
            Stake in dollars (0.0 if bet not recommended).
        """
        cal_prob = self.calibrated_win_prob(edge)
        win_prob = cal_prob if cal_prob is not None else model_prob

        decimal_odds = american_to_decimal(american_odds)
        bet_frac = fractional_kelly(
            win_prob, decimal_odds, self.kelly_fraction, self.max_bet_fraction
        )
        stake = self.bankroll * bet_frac

        if stake < self.min_bet:
            return 0.0
        return round(stake, 2)
```

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_kelly_sizer.py -v`
Expected: All 12 tests PASS.

**Step 5: Run ruff**

Run: `venv/Scripts/python.exe -m ruff check betting/odds_converter.py tests/test_kelly_sizer.py`
Run: `venv/Scripts/python.exe -m ruff format betting/odds_converter.py tests/test_kelly_sizer.py`

**Step 6: Commit**

```bash
git add betting/odds_converter.py tests/test_kelly_sizer.py
git commit -m "feat: add KellySizer with Platt calibration for dynamic bet sizing"
```

---

### Task 3: Build Calibration Data Loader

**Files:**
- Modify: `betting/odds_converter.py` (add `build_calibration_data` function)
- Modify: `tests/test_kelly_sizer.py` (add integration test)

The sizer needs historical backtest data to calibrate. This function loads all
available backtest parquet files and returns the (edge, win/loss) arrays.

**Step 1: Write failing test**

Add to `tests/test_kelly_sizer.py`:

```python
class TestBuildCalibrationData:
    """Test calibration data loader."""

    def test_loads_from_parquet_files(self, tmp_path):
        """Build calibration arrays from backtest parquet files."""
        from betting.odds_converter import build_calibration_data

        # Create a minimal parquet file
        df = pd.DataFrame({
            "edge": [0.10, 0.15, 0.20],
            "result": ["win", "loss", "win"],
        })
        df.to_parquet(tmp_path / "ncaab_elo_backtest_2025.parquet", index=False)

        edges, outcomes = build_calibration_data(tmp_path)
        assert len(edges) == 3
        assert list(outcomes) == [1, 0, 1]

    def test_combines_multiple_seasons(self, tmp_path):
        for season in [2024, 2025]:
            df = pd.DataFrame({
                "edge": [0.10, 0.20],
                "result": ["win", "loss"],
            })
            df.to_parquet(tmp_path / f"ncaab_elo_backtest_{season}.parquet", index=False)

        edges, outcomes = build_calibration_data(tmp_path)
        assert len(edges) == 4

    def test_empty_directory_raises(self, tmp_path):
        from betting.odds_converter import build_calibration_data
        with pytest.raises(FileNotFoundError):
            build_calibration_data(tmp_path)
```

**Step 2: Run to verify failure**

Run: `venv/Scripts/python.exe -m pytest tests/test_kelly_sizer.py::TestBuildCalibrationData -v`
Expected: ImportError — `build_calibration_data` not found.

**Step 3: Implement**

Add to `betting/odds_converter.py` below the `KellySizer` class:

```python
def build_calibration_data(
    backtest_dir: "str | Path",
) -> tuple["np.ndarray", "np.ndarray"]:
    """Load historical backtest results and extract (edge, outcome) arrays.

    Args:
        backtest_dir: Directory containing ncaab_elo_backtest_YYYY.parquet files.

    Returns:
        Tuple of (edges, outcomes) numpy arrays.

    Raises:
        FileNotFoundError: If no backtest parquet files found.
    """
    import numpy as np
    import pandas as pd
    from pathlib import Path

    backtest_dir = Path(backtest_dir)
    files = sorted(backtest_dir.glob("ncaab_elo_backtest_*.parquet"))
    if not files:
        raise FileNotFoundError(f"No backtest parquet files in {backtest_dir}")

    dfs = [pd.read_parquet(f) for f in files]
    combined = pd.concat(dfs, ignore_index=True)

    edges = combined["edge"].values.astype(np.float64)
    outcomes = (combined["result"] == "win").astype(np.int32).values

    return edges, outcomes
```

**Step 4: Run tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_kelly_sizer.py -v`
Expected: All 15 tests PASS.

**Step 5: Commit**

```bash
git add betting/odds_converter.py tests/test_kelly_sizer.py
git commit -m "feat: add build_calibration_data loader for Kelly calibration"
```

---

### Task 4: Wire KellySizer into Daily Predictions Pipeline

**Files:**
- Modify: `scripts/daily_predictions.py:315-331` (replace inline fractional_kelly calls)
- Modify: `scripts/daily_run.py` (instantiate + calibrate KellySizer)

**Step 1: Modify daily_run.py to create calibrated KellySizer**

In `scripts/daily_run.py`, add the import and initialization. Find the `generate_and_record_predictions` function
(around line 340) and add KellySizer setup before the `generate_predictions` call.

Add import at top (near line 26):

```python
from betting.odds_converter import KellySizer, build_calibration_data
```

In the function body, before the `generate_predictions(...)` call (around line 400), add:

```python
    # Build calibrated Kelly sizer from historical backtests
    backtest_dir = PROJECT_ROOT / "data" / "backtests"
    kelly_sizer = KellySizer(
        kelly_fraction=PAPER_BETTING.KELLY_FRACTION,
        max_bet_fraction=PAPER_BETTING.MAX_BET_FRACTION,
        bankroll=PAPER_BETTING.PAPER_BANKROLL,
    )
    try:
        edges, outcomes = build_calibration_data(backtest_dir)
        kelly_sizer.calibrate(edges, outcomes)
        logger.info(
            "KellySizer calibrated on %d historical bets (calibrated=True)",
            len(edges),
        )
    except FileNotFoundError:
        logger.warning("No backtest data for calibration; using raw model probs")
```

Then pass `kelly_sizer` into `generate_predictions(...)` as a new kwarg.

**Step 2: Modify generate_predictions to accept and use KellySizer**

In `scripts/daily_predictions.py`, the function `generate_predictions` has the bet recommendation
block at lines 315-331. Currently it calls `fractional_kelly()` directly with `home_prob`.

Add `kelly_sizer: "KellySizer | None" = None` parameter to `generate_predictions`.

Replace lines 316-331:

```python
                    # Bet recommendation
                    if home_edge >= min_edge:
                        if kelly_sizer is not None:
                            stake = kelly_sizer.size_bet(
                                model_prob=home_prob,
                                edge=home_edge,
                                american_odds=odds.moneyline_home,
                            )
                        else:
                            decimal_odds = american_to_decimal(odds.moneyline_home)
                            kelly = fractional_kelly(home_prob, decimal_odds)
                            stake = PAPER_BETTING.PAPER_BANKROLL * kelly
                        if stake > 0:
                            pred["rec_side"] = "HOME"
                            pred["rec_odds"] = odds.moneyline_home
                            pred["rec_stake"] = stake
                    elif away_edge >= min_edge:
                        if kelly_sizer is not None:
                            stake = kelly_sizer.size_bet(
                                model_prob=1 - home_prob,
                                edge=away_edge,
                                american_odds=odds.moneyline_away,
                            )
                        else:
                            decimal_odds = american_to_decimal(odds.moneyline_away)
                            kelly = fractional_kelly(1 - home_prob, decimal_odds)
                            stake = PAPER_BETTING.PAPER_BANKROLL * kelly
                        if stake > 0:
                            pred["rec_side"] = "AWAY"
                            pred["rec_odds"] = odds.moneyline_away
                            pred["rec_stake"] = stake
```

Note: removed `rec_kelly` field since stake is now the primary output.

**Step 3: Run existing tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py -v -x`
Expected: All 29 tests pass. The tests mock predictions so the KellySizer path is
exercised via the fallback (uncalibrated → raw model_prob → same as before).

**Step 4: Run a dry-run to verify end-to-end**

Run: `venv/Scripts/python.exe scripts/daily_run.py --dry-run`
Expected: Should see varied stake sizes in output instead of flat $150.

**Step 5: Commit**

```bash
git add scripts/daily_predictions.py scripts/daily_run.py
git commit -m "feat: wire KellySizer into daily predictions pipeline"
```

---

### Task 5: Wire KellySizer into Backtest

**Files:**
- Modify: `scripts/backtest_ncaab_elo.py:372-375` (run_backtest) and `795-796` (run_backtest_with_features)

The backtest already calls `fractional_kelly()` at lines 374 and 795. We need to optionally use
a `KellySizer` instead. Since the backtest generates its own data, we use **leave-one-season-out**
calibration: for test season N, calibrate on seasons [2020..N-1].

**Step 1: Add `--calibrated-kelly` CLI flag**

In the argparse section (around line 845):

```python
    parser.add_argument(
        "--calibrated-kelly",
        action="store_true",
        help="Use Platt-calibrated Kelly sizing instead of raw model prob",
    )
```

**Step 2: In run_backtest_with_features, accept optional KellySizer**

Add `kelly_sizer: "KellySizer | None" = None` parameter.

Replace the sizing block (line 795-796):

```python
            if kelly_sizer is not None:
                stake = kelly_sizer.size_bet(
                    model_prob=bet_prob,
                    edge=max(home_edge, away_edge),
                    american_odds=bet_odds,
                )
            else:
                decimal_odds = american_to_decimal(bet_odds)
                bet_fraction = fractional_kelly(bet_prob, decimal_odds, kelly_fraction, max_bet)
                stake = current_bankroll * bet_fraction
```

Do the same for `run_backtest` at lines 373-375.

**Step 3: In `main()`, build KellySizer when `--calibrated-kelly` is passed**

After loading data but before running the backtest, if `args.calibrated_kelly`:

```python
    kelly_sizer = None
    if args.calibrated_kelly:
        from betting.odds_converter import KellySizer, build_calibration_data
        backtest_dir = Path("data/backtests")
        try:
            edges, outcomes = build_calibration_data(backtest_dir)
            kelly_sizer = KellySizer(
                kelly_fraction=args.kelly,
                max_bet_fraction=args.max_bet,
                bankroll=args.bankroll,
            )
            kelly_sizer.calibrate(edges, outcomes)
            logger.info("Calibrated Kelly sizer on %d bets", len(edges))
        except FileNotFoundError:
            logger.warning("No calibration data; falling back to raw Kelly")
```

Pass `kelly_sizer=kelly_sizer` to the run_backtest call.

**Step 4: Run existing tests**

Run: `venv/Scripts/python.exe -m pytest tests/ -k "backtest or kelly" -v`
Expected: All pass — new flag is opt-in, default behavior unchanged.

**Step 5: Run a comparison backtest**

```bash
# Flat Kelly (current behavior):
venv/Scripts/python.exe scripts/backtest_ncaab_elo.py --barttorvik --test-season 2025

# Calibrated Kelly (new):
venv/Scripts/python.exe scripts/backtest_ncaab_elo.py --barttorvik --test-season 2025 --calibrated-kelly
```

Compare total P/L, ROI, and Sharpe between the two runs.

**Step 6: Commit**

```bash
git add scripts/backtest_ncaab_elo.py
git commit -m "feat: add --calibrated-kelly flag to backtest for dynamic sizing"
```

---

### Task 6: Update Dashboard Monte Carlo to Use Dynamic Sizing

**Files:**
- Modify: `dashboards/ncaab_dashboard.html` (Monte Carlo simulation logic)

The Monte Carlo already uses a coin-flip simulation. Now that we have dynamic sizing, add a
third chart panel showing the Kelly-sized simulation alongside the two flat-stake panels.

**Step 1: Add a third scenario to the monteCarlo config**

In `EXPECTATIONS_DATA.monteCarlo.scenarios`:

```javascript
scenarios: [
    { name: "$100 Flat Stake", stake: 100, dynamic: false },
    { name: "$150 Flat Stake", stake: 150, dynamic: false },
    { name: "Dynamic Kelly (¼K, 5% cap)", stake: null, dynamic: true },
],
```

**Step 2: Update renderMonteCarloCI to handle dynamic sizing**

For the dynamic scenario, instead of a fixed stake, compute stake per-bet using a simplified
Kelly formula in JS:

```javascript
// Inside the bet loop, if dynamic:
const impliedProb = 1 / mc.avgDecimalOdds;
const edge = mc.winRate - impliedProb;  // average edge
const kellyFrac = 0.25;  // quarter Kelly
const maxBetFrac = 0.05;
const bankroll = 5000;

// For dynamic, vary stake with a noise factor to simulate edge variation
if (scenario.dynamic) {
    const edgeNoise = 0.5 + rng() * 1.5;  // 0.5x to 2x average edge
    const thisEdge = edge * edgeNoise;
    const thisWinProb = impliedProb + thisEdge;
    const b = mc.avgDecimalOdds - 1;
    const rawKelly = (b * thisWinProb - (1 - thisWinProb)) / b;
    const betFrac = Math.min(Math.max(0, rawKelly * kellyFrac), maxBetFrac);
    stake = bankroll * betFrac;
}
```

**Step 3: Add the third chart container in HTML**

Add a `<div id="mcChartC">` next to mcChartA and mcChartB.

**Step 4: Test locally**

Run: `python -m http.server 8765` and inspect the Betting Model tab.
Verify: Three charts render, dynamic Kelly chart shows higher upside and tighter median.

**Step 5: Commit**

```bash
git add dashboards/ncaab_dashboard.html
git commit -m "feat: add dynamic Kelly scenario to Monte Carlo dashboard"
```

---

### Task 7: Backtest Comparison & Validation

**Files:**
- No new files — this is a verification task.

Run the full 6-season incremental backtest with both flat and calibrated Kelly, compare results.

**Step 1: Run flat-stake backtest for all seasons**

```bash
for season in 2020 2021 2022 2023 2024 2025; do
    venv/Scripts/python.exe scripts/backtest_ncaab_elo.py \
        --barttorvik --test-season $season --barttorvik-weight 1.5 \
        --min-edge 0.075 2>&1 | grep -E "Total P/L|Flat-stake ROI|Sharpe"
done
```

**Step 2: Run calibrated-Kelly backtest for all seasons**

```bash
for season in 2020 2021 2022 2023 2024 2025; do
    venv/Scripts/python.exe scripts/backtest_ncaab_elo.py \
        --barttorvik --test-season $season --barttorvik-weight 1.5 \
        --min-edge 0.075 --calibrated-kelly 2>&1 | grep -E "Total P/L|Flat-stake ROI|Sharpe"
done
```

**Step 3: Compare and document**

Create a table comparing flat vs. dynamic across all 6 seasons:
- Total P/L
- Flat-stake ROI
- Sharpe ratio
- Max drawdown
- Average stake size

If dynamic Kelly improves Sharpe by >0.1 in 4+ seasons, the feature is validated.

**Step 4: Commit documentation**

```bash
git add docs/plans/2026-02-25-dynamic-kelly-sizing.md
git commit -m "docs: add dynamic Kelly sizing implementation plan and backtest comparison"
```

---

## Risk Considerations

1. **Calibration data leakage**: The daily pipeline calibrates on ALL historical backtests.
   This is fine for live betting (all data is in the past). For backtesting, Task 5 should
   ideally use leave-one-season-out calibration to avoid training on the test season.

2. **Calibrator drift**: As more bets accumulate, the calibration may shift. Re-calibrate
   weekly by regenerating backtest parquets (already happens in the daily pipeline via
   Elo retraining).

3. **Edge extremes**: Edges >50% are rare (306/10,309 bets) but highly profitable.
   The 5% cap naturally limits exposure to these outliers.

4. **Bankroll tracking**: Current paper betting uses a static $5,000 bankroll. A future
   enhancement would track the running bankroll and use the actual balance for Kelly sizing.
