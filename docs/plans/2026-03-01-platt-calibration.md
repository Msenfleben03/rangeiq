# Platt Calibration for MLB Poisson Model

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Platt scaling (logistic regression) to `PoissonModel` so the pitcher-adjusted probabilities are well-calibrated, fixing the +0.025 log loss regression.

**Architecture:** After `model.fit(train)`, predict all training games to collect `(raw_prob, outcome)` pairs, fit a 2-parameter logistic regression (Platt scaler), then apply it to all test-set predictions. The scaler lives on `PoissonModel` as `calibrate()` / `calibrate_prob()` methods. The backtest script gets a `--calibrated` flag orthogonal to `--pitcher-adj`.

**Tech Stack:** scikit-learn `LogisticRegression`, numpy, existing PoissonModel infrastructure

---

### Task 1: Add calibration methods to PoissonModel (tests)

**Files:**
- Modify: `tests/test_mlb_poisson_model.py`

**Step 1: Write failing tests for calibrate() and calibrate_prob()**

Add a new test class `TestPlattCalibration` at the end of the file (before the `TestBacktestHelpers` class):

```python
# =============================================================================
# TestPlattCalibration
# =============================================================================


class TestPlattCalibration:
    """Tests for PoissonModel Platt calibration methods."""

    def test_uncalibrated_returns_raw(self):
        """calibrate_prob() returns raw prob when uncalibrated."""
        model, team_ids = _fit_model()
        pred = model.predict(team_ids[0], team_ids[1])
        raw = pred["moneyline_home"]
        assert model.calibrate_prob(raw) == raw

    def test_is_calibrated_default_false(self):
        """New model is not calibrated."""
        model = PoissonModel()
        assert model.is_calibrated is False

    def test_calibrate_sets_is_calibrated(self):
        """After calibrate(), is_calibrated is True."""
        model, team_ids = _fit_model()
        probs = np.array([0.4, 0.5, 0.6, 0.7])
        outcomes = np.array([0, 0, 1, 1])
        model.calibrate(probs, outcomes)
        assert model.is_calibrated is True

    def test_calibrate_changes_probabilities(self):
        """Calibrated prob differs from raw prob for non-trivial input."""
        model, team_ids = _fit_model()
        # Create biased training data: model says 0.7 but actual win rate is ~50%
        probs = np.array([0.7] * 50 + [0.3] * 50)
        outcomes = np.array([1] * 25 + [0] * 25 + [1] * 25 + [0] * 25)
        model.calibrate(probs, outcomes)
        # 0.7 should be pulled toward 0.5
        calibrated = model.calibrate_prob(0.7)
        assert calibrated != pytest.approx(0.7, abs=0.01)
        assert 0.0 < calibrated < 1.0

    def test_calibrate_preserves_ordering(self):
        """Calibration preserves probability ordering (monotonic)."""
        model, _ = _fit_model()
        rng = np.random.RandomState(99)
        probs = rng.uniform(0.3, 0.7, 200)
        outcomes = (rng.random(200) < probs).astype(int)
        model.calibrate(probs, outcomes)
        cal_low = model.calibrate_prob(0.35)
        cal_mid = model.calibrate_prob(0.50)
        cal_high = model.calibrate_prob(0.65)
        assert cal_low < cal_mid < cal_high

    def test_calibrate_improves_log_loss(self):
        """Calibration should improve log loss on miscalibrated predictions."""
        model, team_ids = _fit_model()
        # Generate predictions on training data
        rng = np.random.RandomState(42)
        n = 500
        raw_probs = rng.uniform(0.35, 0.65, n)
        # Bias: inflate probs by 5pp (simulates model overconfidence)
        biased_probs = np.clip(raw_probs + 0.05, 0.01, 0.99)
        outcomes = (rng.random(n) < raw_probs).astype(int)

        # Log loss before calibration
        eps = 1e-10
        ll_before = -(
            outcomes * np.log(biased_probs + eps)
            + (1 - outcomes) * np.log(1 - biased_probs + eps)
        ).mean()

        # Calibrate and compute log loss after
        model.calibrate(biased_probs, outcomes)
        cal_probs = np.array([model.calibrate_prob(p) for p in biased_probs])
        ll_after = -(
            outcomes * np.log(cal_probs + eps)
            + (1 - outcomes) * np.log(1 - cal_probs + eps)
        ).mean()

        assert ll_after < ll_before
```

**Step 2: Run tests to verify they fail**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py::TestPlattCalibration -v`
Expected: FAIL — `PoissonModel` has no `calibrate` / `calibrate_prob` / `is_calibrated`

---

### Task 2: Implement calibration methods on PoissonModel

**Files:**
- Modify: `models/sport_specific/mlb/poisson_model.py`

**Step 3: Add `calibrate()`, `calibrate_prob()`, and `is_calibrated` to PoissonModel**

In `__init__`, add `self._calibrator = None`.

Add an `is_calibrated` property:

```python
@property
def is_calibrated(self) -> bool:
    """Whether Platt calibration has been fitted."""
    return self._calibrator is not None
```

Add the `calibrate()` method:

```python
def calibrate(self, raw_probs: np.ndarray, outcomes: np.ndarray) -> None:
    """Fit Platt scaling on raw model probabilities vs actual outcomes.

    Uses logistic regression (2 parameters) to map raw moneyline
    probabilities to calibrated win probabilities.

    Args:
        raw_probs: Array of raw moneyline_home probabilities from predict().
        outcomes: Array of 1 (home won) / 0 (home lost).
    """
    from sklearn.linear_model import LogisticRegression

    X = raw_probs.reshape(-1, 1) if raw_probs.ndim == 1 else raw_probs
    self._calibrator = LogisticRegression(random_state=42)
    self._calibrator.fit(X, outcomes)
    logger.info(
        "Platt calibration fitted on %d games (coef=%.4f, intercept=%.4f)",
        len(outcomes),
        self._calibrator.coef_[0][0],
        self._calibrator.intercept_[0],
    )
```

Add the `calibrate_prob()` method:

```python
def calibrate_prob(self, raw_prob: float) -> float:
    """Return calibrated probability, or raw if uncalibrated.

    Args:
        raw_prob: Raw moneyline probability from predict().

    Returns:
        Calibrated probability if calibrate() has been called,
        otherwise returns raw_prob unchanged.
    """
    if self._calibrator is None:
        return raw_prob
    return float(self._calibrator.predict_proba(np.array([[raw_prob]]))[0][1])
```

**Step 4: Run tests to verify they pass**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py::TestPlattCalibration -v`
Expected: all 6 PASS

**Step 5: Run full test suite to check no regressions**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py -v`
Expected: 48/48 PASS (42 existing + 6 new)

**Step 6: Lint**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m ruff check models/sport_specific/mlb/poisson_model.py tests/test_mlb_poisson_model.py && venv/Scripts/python.exe -m ruff format models/sport_specific/mlb/poisson_model.py tests/test_mlb_poisson_model.py`

**Step 7: Commit**

```bash
git add models/sport_specific/mlb/poisson_model.py tests/test_mlb_poisson_model.py
git commit -m "feat(mlb): add Platt calibration to PoissonModel

calibrate() fits 2-param logistic regression on (raw_prob, outcome).
calibrate_prob() maps raw moneyline probability to calibrated value.
6 new tests covering ordering, log loss improvement, and edge cases."
```

---

### Task 3: Add `--calibrated` flag to backtest script (tests)

**Files:**
- Modify: `tests/test_mlb_poisson_model.py`

**Step 8: Write failing test for calibrated backtest**

Add to `TestWalkForward` class:

```python
def test_calibrated_backtest_runs(self):
    """Calibrated backtest completes and returns valid probabilities."""
    from scripts.mlb_backtest import run_backtest

    rng = np.random.RandomState(42)
    games = []
    teams = list(range(100, 110))
    for season in [2023, 2024]:
        for i in range(200):
            h, a = rng.choice(teams, 2, replace=False)
            games.append(
                {
                    "game_pk": season * 1000 + i,
                    "game_date": f"{season}-06-15",
                    "season": season,
                    "home_team_id": int(h),
                    "away_team_id": int(a),
                    "home_score": int(rng.poisson(4.5)),
                    "away_score": int(rng.poisson(4.3)),
                    "home_starter_id": None,
                    "away_starter_id": None,
                }
            )
    df = pd.DataFrame(games)

    results = run_backtest(df, test_season=2024, calibrated=True)
    assert len(results) > 0
    assert "pred_home_prob" in results.columns
    assert "pred_home_prob_raw" in results.columns
    # Calibrated probs should still be valid probabilities
    assert results["pred_home_prob"].between(0, 1).all()
    assert results["pred_home_prob_raw"].between(0, 1).all()
```

**Step 9: Run test to verify it fails**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py::TestWalkForward::test_calibrated_backtest_runs -v`
Expected: FAIL — `run_backtest` has no `calibrated` parameter

---

### Task 4: Implement `--calibrated` in backtest script

**Files:**
- Modify: `scripts/mlb_backtest.py`

**Step 10: Add `calibrated` parameter to `run_backtest()`**

Update function signature:

```python
def run_backtest(
    games: pd.DataFrame,
    test_season: int,
    pitcher_adj: bool = False,
    pitcher_stats: dict[tuple[int, int], dict] | None = None,
    calibrated: bool = False,
) -> pd.DataFrame:
```

After `model.fit(train)` and before the test prediction loop, add the calibration block:

```python
    # Platt calibration on training set predictions
    if calibrated:
        logger.info("Calibrating on %d training games...", len(train))
        train_probs = []
        train_outcomes = []
        for _, trow in train.iterrows():
            h_id = int(trow["home_team_id"])
            a_id = int(trow["away_team_id"])
            if h_id not in model.team_ratings or a_id not in model.team_ratings:
                continue
            if trow["home_score"] == trow["away_score"]:
                continue
            tpred = model.predict(h_id, a_id)
            train_probs.append(tpred["moneyline_home"])
            train_outcomes.append(1 if trow["home_score"] > trow["away_score"] else 0)
        model.calibrate(np.array(train_probs), np.array(train_outcomes))
```

In the test loop, after computing `pred`, apply calibration and store both raw and calibrated:

```python
        raw_prob = pred["moneyline_home"]
        cal_prob = model.calibrate_prob(raw_prob) if calibrated else raw_prob

        results.append(
            {
                "game_pk": row["game_pk"],
                "game_date": row["game_date"],
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_score": row["home_score"],
                "away_score": row["away_score"],
                "pred_home_prob": cal_prob,
                "pred_home_prob_raw": raw_prob,
                "pred_lambda_home": pred["lambda_home"],
                "pred_lambda_away": pred["lambda_away"],
                "home_won": home_won,
                "correct": (cal_prob > 0.5) == home_won,
                "home_pitcher_adj": home_padj,
                "away_pitcher_adj": away_padj,
            }
        )
```

Add the CLI flag in `main()`:

```python
    parser.add_argument(
        "--calibrated",
        action="store_true",
        default=False,
        help="Apply Platt calibration on training set predictions",
    )
```

And pass it through:

```python
    results = run_backtest(
        games,
        args.test_season,
        pitcher_adj=args.pitcher_adj,
        pitcher_stats=pitcher_stats,
        calibrated=args.calibrated,
    )
```

Update output filename suffix:

```python
    suffix = ""
    if args.pitcher_adj:
        suffix += "_pitcher"
    if args.calibrated:
        suffix += "_calibrated"
```

**Step 11: Run the failing test again**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py::TestWalkForward::test_calibrated_backtest_runs -v`
Expected: PASS

**Step 12: Run full test suite**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py -v`
Expected: 49/49 PASS

**Step 13: Lint**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m ruff check scripts/mlb_backtest.py tests/test_mlb_poisson_model.py && venv/Scripts/python.exe -m ruff format scripts/mlb_backtest.py tests/test_mlb_poisson_model.py`

**Step 14: Commit**

```bash
git add scripts/mlb_backtest.py tests/test_mlb_poisson_model.py
git commit -m "feat(mlb): add --calibrated flag to walk-forward backtest

Platt calibration fits on training set predictions before test evaluation.
Stores both raw and calibrated probs in results parquet.
Orthogonal to --pitcher-adj (can use either or both)."
```

---

### Task 5: Run comparison backtests and verify improvement

**Step 15: Run 4 backtest variants on 2025**

```bash
cd /c/Users/msenf/sports-betting
# Baseline
venv/Scripts/python.exe scripts/mlb_backtest.py --test-season 2025
# Pitcher only
venv/Scripts/python.exe scripts/mlb_backtest.py --test-season 2025 --pitcher-adj
# Calibrated only
venv/Scripts/python.exe scripts/mlb_backtest.py --test-season 2025 --calibrated
# Both
venv/Scripts/python.exe scripts/mlb_backtest.py --test-season 2025 --pitcher-adj --calibrated
```

**Expected outcome:** `--pitcher-adj --calibrated` should show:
- Accuracy >= baseline (55%+ range)
- Log loss IMPROVED over pitcher-only (< 0.7219, ideally < 0.700)
- Calibration bins should show predicted vs actual within 5% per bin

**Step 16: Record results in session-state.md and commit any adjustments**
