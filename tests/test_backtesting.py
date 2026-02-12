"""Tests for the backtesting framework.

Tests cover:
    - Walk-forward validation (temporal integrity)
    - Metrics calculations (CLV, ROI, Brier, etc.)
    - Monte Carlo simulation
    - Data leakage detection

CRITICAL: These tests verify that the framework prevents look-ahead bias,
which is the #1 cause of inflated backtest performance.
"""

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backtesting.walk_forward import (  # noqa: E402
    WalkForwardValidator,
    WalkForwardWindow,
    SeasonalWalkForwardValidator,
    create_lagged_features,
)
from backtesting.metrics import (  # noqa: E402
    calculate_roi,
    calculate_clv_metrics,
    calculate_brier_score,
    calculate_calibration_error,
    calculate_sharpe_ratio,
    calculate_drawdown_metrics,
    calculate_streak_metrics,
    compute_all_metrics,
    BettingMetrics,
)
from backtesting.simulation import (  # noqa: E402
    MonteCarloSimulator,
    SimulationConfig,
    run_drawdown_analysis,
    calculate_risk_of_ruin,
    validate_kelly_fraction,
    calculate_confidence_intervals,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def sample_betting_df():
    """Create sample betting data for testing."""
    np.random.seed(42)
    n_bets = 100

    dates = pd.date_range("2024-01-01", periods=n_bets, freq="D")

    return pd.DataFrame(
        {
            "game_date": dates,
            "game_id": [f"game_{i}" for i in range(n_bets)],
            "stake": np.full(n_bets, 100.0),
            "odds_placed": np.random.choice([-110, -105, +100, +105], n_bets),
            "odds_closing": np.random.choice([-115, -110, -105, +100], n_bets),
            "model_probability": np.random.uniform(0.5, 0.6, n_bets),
            "result": np.random.choice(["win", "loss"], n_bets, p=[0.52, 0.48]),
            "profit_loss": np.where(
                np.random.random(n_bets) < 0.52,
                np.random.uniform(80, 100, n_bets),
                -100,
            ),
        }
    )


@pytest.fixture
def time_series_df():
    """Create time-series data for walk-forward testing."""
    np.random.seed(42)
    n_samples = 500

    dates = pd.date_range("2022-01-01", periods=n_samples, freq="D")

    return pd.DataFrame(
        {
            "game_date": dates,
            "feature_1": np.random.randn(n_samples),
            "feature_2": np.random.randn(n_samples),
            "target": np.random.randint(0, 2, n_samples),
        }
    ).sort_values("game_date")


@pytest.fixture
def seasonal_df():
    """Create multi-season data for seasonal walk-forward testing."""
    np.random.seed(42)

    dfs = []
    for season in [2020, 2021, 2022, 2023, 2024]:
        n_games = 100
        start_date = date(season, 1, 1)
        dates = [start_date + timedelta(days=i) for i in range(n_games)]

        df = pd.DataFrame(
            {
                "game_date": dates,
                "season": season,
                "feature_1": np.random.randn(n_games),
                "target": np.random.randint(0, 2, n_games),
            }
        )
        dfs.append(df)

    return pd.concat(dfs, ignore_index=True).sort_values("game_date")


# =============================================================================
# WALK-FORWARD VALIDATION TESTS
# =============================================================================


class TestWalkForwardValidator:
    """Tests for WalkForwardValidator."""

    def test_init_valid_params(self):
        """Test initialization with valid parameters."""
        validator = WalkForwardValidator(
            train_window_days=180,
            test_window_days=30,
            step_days=30,
        )
        assert validator.train_window_days == 180
        assert validator.test_window_days == 30
        assert validator.step_days == 30

    def test_init_invalid_params(self):
        """Test initialization rejects invalid parameters."""
        with pytest.raises(ValueError):
            WalkForwardValidator(train_window_days=0)

        with pytest.raises(ValueError):
            WalkForwardValidator(test_window_days=-1)

        with pytest.raises(ValueError):
            WalkForwardValidator(gap_days=-1)

    def test_split_generates_windows(self, time_series_df):
        """Test that split generates valid windows."""
        validator = WalkForwardValidator(
            train_window_days=100,
            test_window_days=30,
            step_days=30,
            min_train_samples=10,
            min_test_samples=5,
        )

        windows = list(validator.split(time_series_df, date_column="game_date"))

        assert len(windows) > 0
        for window in windows:
            assert isinstance(window, WalkForwardWindow)
            assert window.n_train > 0
            assert window.n_test > 0

    def test_no_temporal_overlap(self, time_series_df):
        """CRITICAL: Verify train and test periods never overlap."""
        validator = WalkForwardValidator(
            train_window_days=100,
            test_window_days=30,
            step_days=30,
            gap_days=1,
        )

        for window in validator.split(time_series_df, date_column="game_date"):
            # Training must end before test starts
            assert window.train_end < window.test_start

            # Verify indices don't overlap
            train_set = set(window.train_indices)
            test_set = set(window.test_indices)
            assert len(train_set & test_set) == 0, "Train and test indices must not overlap!"

            # Verify dates don't overlap
            train_dates = time_series_df.iloc[window.train_indices]["game_date"]
            test_dates = time_series_df.iloc[window.test_indices]["game_date"]

            assert train_dates.max() < test_dates.min(), "Train dates must precede test dates!"

    def test_gap_days_respected(self, time_series_df):
        """Test that gap between train and test is respected."""
        gap = 5
        validator = WalkForwardValidator(
            train_window_days=100,
            test_window_days=30,
            step_days=30,
            gap_days=gap,
        )

        for window in validator.split(time_series_df, date_column="game_date"):
            days_between = (window.test_start - window.train_end).days
            assert days_between >= gap, f"Gap should be at least {gap} days"

    def test_requires_sorted_data(self, time_series_df):
        """Test that unsorted data raises error."""
        validator = WalkForwardValidator()

        # Shuffle the data
        shuffled = time_series_df.sample(frac=1, random_state=42)

        with pytest.raises(ValueError, match="sorted"):
            list(validator.split(shuffled, date_column="game_date"))

    def test_expanding_window(self, time_series_df):
        """Test expanding window mode includes all prior data."""
        validator = WalkForwardValidator(
            train_window_days=100,
            test_window_days=30,
            step_days=60,
            expanding_window=True,
        )

        windows = list(validator.split(time_series_df, date_column="game_date"))

        # In expanding mode, training set should grow
        train_sizes = [w.n_train for w in windows]

        # Later windows should have more training data
        assert train_sizes[-1] > train_sizes[0], "Expanding window should grow train set"

    def test_get_n_splits(self, time_series_df):
        """Test get_n_splits returns correct count."""
        validator = WalkForwardValidator(
            train_window_days=100,
            test_window_days=30,
            step_days=30,
        )

        n_splits = validator.get_n_splits(time_series_df, date_column="game_date")
        actual_splits = len(list(validator.split(time_series_df, date_column="game_date")))

        assert n_splits == actual_splits


class TestSeasonalWalkForwardValidator:
    """Tests for SeasonalWalkForwardValidator."""

    def test_respects_season_boundaries(self, seasonal_df):
        """Test that seasons are not mixed in train/test."""
        validator = SeasonalWalkForwardValidator(
            min_training_seasons=2,
            test_seasons=1,
        )

        for window in validator.split(seasonal_df, date_column="game_date", season_column="season"):
            train_seasons = set(seasonal_df.iloc[window.train_indices]["season"])
            test_seasons = set(seasonal_df.iloc[window.test_indices]["season"])

            # No overlap in seasons
            assert len(train_seasons & test_seasons) == 0

            # Test seasons are later than train seasons
            assert min(test_seasons) > max(train_seasons)

    def test_insufficient_seasons_raises(self, seasonal_df):
        """Test that insufficient seasons raises error."""
        validator = SeasonalWalkForwardValidator(
            min_training_seasons=10,  # More than we have
            test_seasons=1,
        )

        with pytest.raises(ValueError, match="Not enough seasons"):
            list(validator.split(seasonal_df, date_column="game_date", season_column="season"))


class TestLaggedFeatures:
    """Tests for data leakage prevention utilities."""

    def test_create_lagged_features(self):
        """Test lagged feature creation."""
        df = pd.DataFrame(
            {
                "game_date": pd.date_range("2024-01-01", periods=10),
                "value": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            }
        )

        result = create_lagged_features(df, ["value"], lag=1, date_column="game_date")

        assert "value_lag1" in result.columns
        # First value should be NaN (no prior data)
        assert pd.isna(result["value_lag1"].iloc[0])
        # Second value should be the first original value
        assert result["value_lag1"].iloc[1] == 1

    def test_lagged_features_with_groups(self):
        """Test lagged features respect grouping."""
        df = pd.DataFrame(
            {
                "game_date": pd.date_range("2024-01-01", periods=6),
                "team_id": ["A", "A", "A", "B", "B", "B"],
                "points": [10, 20, 30, 100, 200, 300],
            }
        )

        result = create_lagged_features(
            df, ["points"], lag=1, date_column="game_date", group_column="team_id"
        )

        # Check team A's lag
        team_a = result[result["team_id"] == "A"]
        assert pd.isna(team_a["points_lag1"].iloc[0])
        assert team_a["points_lag1"].iloc[1] == 10

        # Check team B's lag (should not include team A's values)
        team_b = result[result["team_id"] == "B"]
        assert pd.isna(team_b["points_lag1"].iloc[0])
        assert team_b["points_lag1"].iloc[1] == 100


# =============================================================================
# METRICS TESTS
# =============================================================================


class TestROI:
    """Tests for ROI calculation."""

    def test_basic_roi(self):
        """Test basic ROI calculation."""
        stakes = np.array([100, 100, 100])
        profits = np.array([90, 90, -100])  # 2 wins at -110, 1 loss

        roi = calculate_roi(stakes, profits)

        expected = (90 + 90 - 100) / 300
        assert abs(roi - expected) < 0.001

    def test_zero_stakes(self):
        """Test ROI with zero stakes returns zero."""
        roi = calculate_roi(np.array([]), np.array([]))
        assert roi == 0.0

    def test_negative_roi(self):
        """Test negative ROI calculation."""
        stakes = np.array([100, 100])
        profits = np.array([-100, -100])

        roi = calculate_roi(stakes, profits)
        assert roi == -1.0  # Lost everything


class TestCLVMetrics:
    """Tests for CLV (Closing Line Value) calculations."""

    def test_positive_clv(self):
        """Test positive CLV when getting better odds."""
        # Bet placed at -105, closed at -110
        # -105 implies ~51.2%, -110 implies ~52.4%
        # Getting -105 when it closed at -110 is positive CLV
        placed = np.array([-105])
        closing = np.array([-110])

        metrics = calculate_clv_metrics(placed, closing)

        assert metrics["avg_clv"] > 0, "Better odds should give positive CLV"

    def test_negative_clv(self):
        """Test negative CLV when getting worse odds."""
        # Bet placed at -115, closed at -110
        placed = np.array([-115])
        closing = np.array([-110])

        metrics = calculate_clv_metrics(placed, closing)

        assert metrics["avg_clv"] < 0, "Worse odds should give negative CLV"

    def test_clv_positive_rate(self):
        """Test CLV positive rate calculation."""
        placed = np.array([-105, -110, -115])  # 1 good, 1 even, 1 bad
        closing = np.array([-110, -110, -110])

        metrics = calculate_clv_metrics(placed, closing)

        # Only the first bet has positive CLV
        assert metrics["clv_positive_rate"] == pytest.approx(1 / 3, rel=0.01)

    def test_empty_arrays(self):
        """Test handling of empty arrays."""
        metrics = calculate_clv_metrics(np.array([]), np.array([]))
        assert metrics["avg_clv"] == 0.0


class TestBrierScore:
    """Tests for Brier score calculation."""

    def test_perfect_predictions(self):
        """Test Brier score with perfect predictions."""
        probs = np.array([1.0, 0.0, 1.0, 0.0])
        outcomes = np.array([1, 0, 1, 0])

        score = calculate_brier_score(probs, outcomes)

        assert score == pytest.approx(0.0, abs=0.001)

    def test_random_predictions(self):
        """Test Brier score with random (0.5) predictions."""
        probs = np.array([0.5, 0.5, 0.5, 0.5])
        outcomes = np.array([1, 0, 1, 0])

        score = calculate_brier_score(probs, outcomes)

        assert score == pytest.approx(0.25, rel=0.01)

    def test_good_calibration(self):
        """Test Brier score with well-calibrated predictions."""
        np.random.seed(42)
        n = 1000
        probs = np.random.uniform(0.3, 0.7, n)
        outcomes = (np.random.random(n) < probs).astype(int)

        score = calculate_brier_score(probs, outcomes)

        # Well-calibrated predictions should have low Brier score
        assert score < 0.25  # Better than random


class TestCalibrationError:
    """Tests for calibration error calculation."""

    def test_perfect_calibration(self):
        """Test calibration with perfectly calibrated predictions."""
        np.random.seed(42)
        n = 10000

        # Generate perfectly calibrated predictions
        probs = np.random.uniform(0, 1, n)
        outcomes = (np.random.random(n) < probs).astype(int)

        error, cal_df = calculate_calibration_error(probs, outcomes, n_bins=10)

        # Should have low calibration error
        assert error < 0.05

    def test_calibration_df_structure(self):
        """Test calibration DataFrame has correct structure."""
        probs = np.array([0.1, 0.3, 0.5, 0.7, 0.9])
        outcomes = np.array([0, 0, 1, 1, 1])

        _, cal_df = calculate_calibration_error(probs, outcomes, n_bins=5)

        assert "bin_lower" in cal_df.columns
        assert "bin_upper" in cal_df.columns
        assert "predicted" in cal_df.columns
        assert "actual" in cal_df.columns
        assert "count" in cal_df.columns
        assert "error" in cal_df.columns


class TestSharpeRatio:
    """Tests for Sharpe ratio calculation."""

    def test_positive_sharpe(self):
        """Test positive Sharpe ratio with profitable returns."""
        # Consistent positive returns
        returns = np.array([0.01, 0.02, 0.01, 0.015, 0.01])

        sharpe = calculate_sharpe_ratio(returns)

        assert sharpe > 0

    def test_negative_sharpe(self):
        """Test negative Sharpe ratio with losing returns."""
        returns = np.array([-0.01, -0.02, -0.01, -0.015, -0.01])

        sharpe = calculate_sharpe_ratio(returns)

        assert sharpe < 0

    def test_zero_variance(self):
        """Test Sharpe with zero variance returns zero."""
        returns = np.array([0.01, 0.01, 0.01])

        sharpe = calculate_sharpe_ratio(returns)

        assert sharpe == 0.0


class TestDrawdownMetrics:
    """Tests for drawdown calculations."""

    def test_max_drawdown(self):
        """Test max drawdown calculation."""
        # Start at 100, peak at 150, drop to 80, recover to 140
        cumulative_pnl = np.array([100, 120, 150, 130, 80, 100, 140])

        metrics = calculate_drawdown_metrics(cumulative_pnl)

        # Max drawdown = (150 - 80) / 150 = 46.7%
        expected_dd = (150 - 80) / 150
        assert metrics["max_drawdown"] == pytest.approx(expected_dd, rel=0.01)

    def test_no_drawdown(self):
        """Test with monotonically increasing equity."""
        cumulative_pnl = np.array([100, 110, 120, 130, 140])

        metrics = calculate_drawdown_metrics(cumulative_pnl)

        assert metrics["max_drawdown"] == 0.0


class TestStreakMetrics:
    """Tests for streak calculations."""

    def test_winning_streak(self):
        """Test longest winning streak detection."""
        results = np.array([1, 1, 1, 0, 1, 1])

        metrics = calculate_streak_metrics(results)

        assert metrics["longest_winning_streak"] == 3

    def test_losing_streak(self):
        """Test longest losing streak detection."""
        results = np.array([0, 0, 0, 0, 1, 0])

        metrics = calculate_streak_metrics(results)

        assert metrics["longest_losing_streak"] == 4

    def test_pushes_excluded(self):
        """Test that pushes are excluded from streaks."""
        results = np.array([1, 0.5, 1, 1])  # 0.5 = push

        metrics = calculate_streak_metrics(results)

        # Push should not break the streak
        assert metrics["longest_winning_streak"] == 3


class TestComputeAllMetrics:
    """Tests for comprehensive metrics computation."""

    def test_computes_all_fields(self, sample_betting_df):
        """Test that all metrics fields are computed."""
        metrics = compute_all_metrics(sample_betting_df)

        assert isinstance(metrics, BettingMetrics)
        assert metrics.n_bets > 0
        assert metrics.win_rate >= 0
        assert -1 <= metrics.roi <= 10  # Reasonable bounds

    def test_handles_missing_columns(self):
        """Test graceful handling of missing optional columns."""
        df = pd.DataFrame(
            {
                "stake": [100, 100],
                "profit_loss": [90, -100],
                "result": ["win", "loss"],
            }
        )

        # Should not raise even without odds columns
        metrics = compute_all_metrics(df)
        assert metrics.n_bets == 2


# =============================================================================
# SIMULATION TESTS
# =============================================================================


class TestMonteCarloSimulator:
    """Tests for Monte Carlo simulation."""

    def test_simulation_runs(self):
        """Test basic simulation execution."""
        config = SimulationConfig(
            n_simulations=100,
            n_bets=50,
            initial_bankroll=1000,
            random_seed=42,
        )

        simulator = MonteCarloSimulator(
            win_probability=0.54,
            avg_odds=-110,
            config=config,
        )

        result = simulator.run()

        assert len(result.final_bankrolls) == 100
        assert result.expected_value > 0
        assert 0 <= result.bust_rate <= 1
        assert 0 <= result.profit_rate <= 1

    def test_profitable_edge_grows_bankroll(self):
        """Test that positive edge leads to bankroll growth on average."""
        config = SimulationConfig(
            n_simulations=1000,
            n_bets=200,
            initial_bankroll=1000,
            random_seed=42,
        )

        # Strong positive edge
        simulator = MonteCarloSimulator(
            win_probability=0.57,  # ~5% edge over -110
            avg_odds=-110,
            config=config,
        )

        result = simulator.run()

        # With positive edge, expected value should exceed initial
        assert result.expected_value > config.initial_bankroll

    def test_no_edge_fluctuates(self):
        """Test that no edge leads to roughly break-even."""
        config = SimulationConfig(
            n_simulations=1000,
            n_bets=100,
            initial_bankroll=1000,
            random_seed=42,
        )

        # Break-even probability for -110
        simulator = MonteCarloSimulator(
            win_probability=0.5238,
            avg_odds=-110,
            config=config,
        )

        result = simulator.run()

        # Expected value should be close to initial (within 10%)
        assert abs(result.expected_value - 1000) < 100

    def test_percentiles_ordered(self):
        """Test that percentiles are in correct order."""
        config = SimulationConfig(n_simulations=500, n_bets=100)
        simulator = MonteCarloSimulator(0.54, -110, config)
        result = simulator.run()

        percentiles = sorted(result.percentiles.keys())
        values = [result.percentiles[p] for p in percentiles]

        # Each higher percentile should have higher value
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1]


class TestDrawdownAnalysis:
    """Tests for drawdown analysis functions."""

    def test_drawdown_analysis_runs(self):
        """Test drawdown analysis execution."""
        stats = run_drawdown_analysis(
            win_probability=0.54,
            avg_odds=-110,
            bankroll=1000,
            n_bets=100,
            n_simulations=500,
        )

        assert "expected_max_dd" in stats
        assert "prob_dd_over_20pct" in stats
        assert 0 <= stats["expected_max_dd"] <= 1


class TestRiskOfRuin:
    """Tests for risk of ruin calculation."""

    def test_risk_of_ruin_with_edge(self):
        """Test risk of ruin with positive edge."""
        risk = calculate_risk_of_ruin(
            win_probability=0.57,
            avg_odds=-110,
            bankroll=1000,
            bet_size=50,
            n_bets=200,
            n_simulations=500,
        )

        # With good edge and reasonable sizing, ruin should be low
        assert risk["risk_of_ruin"] < 0.5

    def test_risk_of_ruin_high_variance(self):
        """Test risk of ruin with large bet sizes."""
        risk = calculate_risk_of_ruin(
            win_probability=0.52,  # Small edge
            avg_odds=-110,
            bankroll=1000,
            bet_size=200,  # 20% of bankroll - very aggressive
            n_bets=100,
            n_simulations=500,
        )

        # High variance should increase ruin probability
        assert risk["risk_of_ruin"] > 0.1


class TestKellyValidation:
    """Tests for Kelly criterion validation."""

    def test_kelly_comparison_runs(self):
        """Test Kelly fraction comparison."""
        df = validate_kelly_fraction(
            win_probability=0.54,
            avg_odds=-110,
            bankroll=1000,
            kelly_fractions=[0.25, 0.5, 1.0],
            n_bets=100,
            n_simulations=500,
        )

        assert len(df) == 3
        assert "kelly_fraction" in df.columns
        assert "expected_value" in df.columns
        assert "bust_rate" in df.columns

    def test_full_kelly_higher_variance(self):
        """Test that full Kelly has higher variance than fractional."""
        df = validate_kelly_fraction(
            win_probability=0.54,
            avg_odds=-110,
            bankroll=1000,
            kelly_fractions=[0.25, 1.0],
            n_bets=100,
            n_simulations=1000,
        )

        quarter_kelly = df[df["kelly_fraction"] == 0.25].iloc[0]
        full_kelly = df[df["kelly_fraction"] == 1.0].iloc[0]

        # Full Kelly should have higher max drawdown
        assert full_kelly["avg_max_drawdown"] > quarter_kelly["avg_max_drawdown"]


class TestConfidenceIntervals:
    """Tests for confidence interval calculation."""

    def test_confidence_intervals_structure(self):
        """Test confidence interval calculation."""
        ci = calculate_confidence_intervals(
            win_probability=0.54,
            avg_odds=-110,
            bankroll=1000,
            n_bets=100,
            n_simulations=1000,
        )

        assert 0.95 in ci
        lower, upper = ci[0.95]
        assert lower < upper

    def test_wider_intervals_lower_confidence(self):
        """Test that lower confidence gives narrower intervals."""
        ci = calculate_confidence_intervals(
            win_probability=0.54,
            avg_odds=-110,
            n_simulations=1000,
            confidence_levels=[0.50, 0.95],
        )

        width_50 = ci[0.50][1] - ci[0.50][0]
        width_95 = ci[0.95][1] - ci[0.95][0]

        assert width_95 > width_50


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestBacktestingIntegration:
    """Integration tests for the full backtesting workflow."""

    def test_walk_forward_with_metrics(self, time_series_df):
        """Test full walk-forward workflow with metric computation."""
        validator = WalkForwardValidator(
            train_window_days=100,
            test_window_days=50,
            step_days=50,
            min_train_samples=10,
            min_test_samples=5,
        )

        all_predictions = []
        all_actuals = []

        for window in validator.split(time_series_df, date_column="game_date"):
            # Simple model: predict majority class from training
            train = time_series_df.iloc[window.train_indices]
            test = time_series_df.iloc[window.test_indices]

            majority = train["target"].mode()[0]
            predictions = [majority] * len(test)

            all_predictions.extend(predictions)
            all_actuals.extend(test["target"].values)

        # Can compute Brier score on combined results
        probs = np.array([0.5] * len(all_predictions))  # Baseline
        outcomes = np.array(all_actuals)

        brier = calculate_brier_score(probs, outcomes)
        assert 0 <= brier <= 1

    def test_simulation_from_backtest_distribution(self, sample_betting_df):
        """Test simulation using actual backtest distribution."""
        # Skip if not enough data
        if len(sample_betting_df) < 10:
            pytest.skip("Not enough sample data")

        from backtesting.simulation import simulate_from_backtest

        result = simulate_from_backtest(
            sample_betting_df,
            bankroll=1000,
            n_simulations=100,
        )

        assert result.expected_value > 0
        assert len(result.final_bankrolls) == 100


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        df = pd.DataFrame(columns=["game_date", "feature", "target"])

        validator = WalkForwardValidator()

        # Should generate no windows
        windows = list(validator.split(df, date_column="game_date"))
        assert len(windows) == 0

    def test_single_row_dataframe(self):
        """Test handling of single-row DataFrame."""
        df = pd.DataFrame(
            {
                "game_date": [date(2024, 1, 1)],
                "feature": [1.0],
                "target": [1],
            }
        )

        validator = WalkForwardValidator(min_train_samples=1, min_test_samples=1)

        # Not enough data for train + test
        windows = list(validator.split(df, date_column="game_date"))
        assert len(windows) == 0

    def test_all_same_date(self):
        """Test handling of all same date (no time series)."""
        df = pd.DataFrame(
            {
                "game_date": [date(2024, 1, 1)] * 100,
                "feature": np.random.randn(100),
                "target": np.random.randint(0, 2, 100),
            }
        )

        validator = WalkForwardValidator()

        # All same date, can't do time-series split
        windows = list(validator.split(df, date_column="game_date"))
        assert len(windows) == 0

    def test_extreme_odds(self):
        """Test CLV calculation with extreme odds."""
        placed = np.array([-500, +500])
        closing = np.array([-450, +550])

        # Should not raise
        metrics = calculate_clv_metrics(placed, closing)
        assert "avg_clv" in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
