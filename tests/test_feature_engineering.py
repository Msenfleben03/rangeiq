"""Tests for feature engineering utilities and NCAAB feature engine.

Tests cover:
- safe_rolling applies shift(1) correctly
- exponential_weighted_rolling lag behavior
- opponent_quality_weight neutrality at mean Elo
- rest_days computation accuracy
- validate_no_leakage catches intentional leakage
- NCABBFeatureEngine.compute_all produces correct shape
- Feature differentials for matchup prediction
- A/B framework: identical configs produce identical results
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from features.engineering import (
    compute_rest_days,
    exponential_weighted_rolling,
    opponent_quality_weight,
    safe_rolling,
    validate_no_leakage,
)
from features.sport_specific.ncaab.advanced_features import (
    ALL_FEATURE_NAMES,
    NCABBFeatureEngine,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def team_game_log() -> pd.DataFrame:
    """Create a realistic single-team game log for testing."""
    np.random.seed(42)
    n_games = 30
    dates = pd.date_range("2025-11-04", periods=n_games, freq="3D")
    point_diffs = np.random.randint(-20, 25, size=n_games)
    opp_elos = np.random.normal(1500, 100, size=n_games).astype(int)

    return pd.DataFrame(
        {
            "date": dates,
            "team_id": "team_a",
            "point_diff": point_diffs,
            "opp_elo": opp_elos,
        }
    )


@pytest.fixture
def two_team_log() -> pd.DataFrame:
    """Create interleaved game logs for two teams."""
    np.random.seed(42)
    rows = []
    for i in range(20):
        game_date = pd.Timestamp("2025-11-04") + pd.Timedelta(days=i * 2)
        rows.append(
            {
                "date": game_date,
                "team_id": "team_a",
                "point_diff": np.random.randint(-15, 20),
                "opp_elo": 1500 + np.random.randint(-200, 200),
            }
        )
        rows.append(
            {
                "date": game_date,
                "team_id": "team_b",
                "point_diff": np.random.randint(-15, 20),
                "opp_elo": 1500 + np.random.randint(-200, 200),
            }
        )
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


# =============================================================================
# SAFE ROLLING TESTS
# =============================================================================


class TestSafeRolling:
    """Tests for safe_rolling with mandatory shift(1)."""

    def test_shift_is_applied(self, team_game_log: pd.DataFrame) -> None:
        """Value at index i must NOT include game i's data."""
        series = team_game_log["point_diff"]
        result = safe_rolling(series, window=5, func="mean")

        # Row 5 (0-indexed) should be the mean of rows 0-4, NOT rows 1-5
        expected = series.iloc[0:5].mean()
        assert result.iloc[5] == pytest.approx(expected, abs=0.01)

    def test_first_window_rows_are_nan(self, team_game_log: pd.DataFrame) -> None:
        """First window+shift rows must be NaN (insufficient history)."""
        result = safe_rolling(team_game_log["point_diff"], window=5, func="mean")
        # Rows 0-4 need NaN: rows 0-4 for rolling + 1 for shift
        assert result.iloc[:5].isna().all()

    def test_window_5_mean_correctness(self) -> None:
        """Verify exact values for a known series."""
        series = pd.Series([10, 20, 30, 40, 50, 60, 70])
        result = safe_rolling(series, window=5, func="mean")

        # After shift(1): index 5 = mean(0:5) = mean(10,20,30,40,50) = 30
        assert result.iloc[5] == pytest.approx(30.0)
        # Index 6 = mean(1:6) = mean(20,30,40,50,60) = 40
        assert result.iloc[6] == pytest.approx(40.0)

    def test_std_function(self, team_game_log: pd.DataFrame) -> None:
        """Rolling std should produce non-negative, non-zero values."""
        result = safe_rolling(team_game_log["point_diff"], window=5, func="std")
        valid = result.dropna()
        assert (valid >= 0).all()
        assert valid.mean() > 0  # Not all zeros

    def test_invalid_window_raises(self) -> None:
        """Window < 2 should raise ValueError."""
        with pytest.raises(ValueError, match="Window must be >= 2"):
            safe_rolling(pd.Series([1, 2, 3]), window=1, func="mean")

    def test_invalid_func_raises(self) -> None:
        """Unsupported function should raise ValueError."""
        with pytest.raises(ValueError, match="Unsupported func"):
            safe_rolling(pd.Series([1, 2, 3, 4, 5]), window=2, func="median")

    def test_returns_new_series(self, team_game_log: pd.DataFrame) -> None:
        """safe_rolling must return a NEW series (immutability)."""
        original = team_game_log["point_diff"].copy()
        result = safe_rolling(team_game_log["point_diff"], window=5, func="mean")
        assert result is not team_game_log["point_diff"]
        pd.testing.assert_series_equal(team_game_log["point_diff"], original)


# =============================================================================
# EXPONENTIAL WEIGHTED ROLLING TESTS
# =============================================================================


class TestExponentialWeightedRolling:
    """Tests for exponential_weighted_rolling."""

    def test_shift_is_applied(self, team_game_log: pd.DataFrame) -> None:
        """EWM result must be lagged by 1."""
        series = team_game_log["point_diff"]
        result = exponential_weighted_rolling(series, window=5, half_life_games=8)

        # First 5 rows should be NaN (min_periods=5, then shift)
        assert result.iloc[:5].isna().all()
        # Row 5 should be non-NaN
        assert pd.notna(result.iloc[5])

    def test_invalid_half_life_raises(self) -> None:
        """half_life_games < 1 should raise ValueError."""
        with pytest.raises(ValueError, match="half_life_games must be >= 1"):
            exponential_weighted_rolling(pd.Series([1, 2, 3, 4, 5, 6]), window=3, half_life_games=0)

    def test_recent_games_weighted_more(self) -> None:
        """EWM reacts faster to regime changes than simple rolling mean.

        Right after a jump from low to high values, EWM should be higher
        than simple mean because it weights recent observations more.
        """
        # Series: 5 low values then 5 high values
        series = pd.Series([1, 1, 1, 1, 1, 10, 10, 10, 10, 10])
        ewm_result = exponential_weighted_rolling(series, window=3, half_life_games=3)
        simple_mean = safe_rolling(series, window=5, func="mean")

        # At position 6 (just after jump), EWM should react faster
        # EWM at 6 uses up to index 5 with decay => ~3.48 (captures the 10)
        # Simple mean at 6 uses indices 1-5 => mean(1,1,1,1,10) = 2.8
        idx = 6
        assert pd.notna(ewm_result.iloc[idx]) and pd.notna(simple_mean.iloc[idx])
        assert ewm_result.iloc[idx] > simple_mean.iloc[idx]


# =============================================================================
# OPPONENT QUALITY WEIGHT TESTS
# =============================================================================


class TestOpponentQualityWeight:
    """Tests for opponent_quality_weight."""

    def test_neutral_at_mean_elo(self) -> None:
        """Weight should be 1.0 (neutral) when opponent is exactly average."""
        stat = pd.Series([10.0, -5.0, 15.0])
        opp_elo = pd.Series([1500.0, 1500.0, 1500.0])
        result = opponent_quality_weight(stat, opp_elo, mean_elo=1500.0)
        pd.testing.assert_series_equal(result, stat)

    def test_strong_opponent_amplifies(self) -> None:
        """Beating a strong opponent should amplify the margin."""
        stat = pd.Series([10.0])
        opp_elo = pd.Series([1800.0])
        result = opponent_quality_weight(stat, opp_elo, mean_elo=1500.0)
        assert result.iloc[0] == pytest.approx(10.0 * 1800 / 1500)
        assert result.iloc[0] > 10.0

    def test_weak_opponent_diminishes(self) -> None:
        """Beating a weak opponent should diminish the margin."""
        stat = pd.Series([10.0])
        opp_elo = pd.Series([1200.0])
        result = opponent_quality_weight(stat, opp_elo, mean_elo=1500.0)
        assert result.iloc[0] == pytest.approx(10.0 * 1200 / 1500)
        assert result.iloc[0] < 10.0

    def test_negative_margin_preserved(self) -> None:
        """Losing to a strong opponent should produce a more negative weighted margin."""
        stat = pd.Series([-10.0])
        opp_elo = pd.Series([1800.0])
        result = opponent_quality_weight(stat, opp_elo, mean_elo=1500.0)
        assert result.iloc[0] < -10.0  # More negative

    def test_invalid_mean_elo_raises(self) -> None:
        """mean_elo <= 0 should raise ValueError."""
        with pytest.raises(ValueError, match="mean_elo must be positive"):
            opponent_quality_weight(pd.Series([1.0]), pd.Series([1500.0]), mean_elo=0)


# =============================================================================
# REST DAYS TESTS
# =============================================================================


class TestComputeRestDays:
    """Tests for compute_rest_days."""

    def test_first_game_is_nan(self) -> None:
        """First game for a team should have NaN rest days."""
        dates = pd.Series(pd.to_datetime(["2025-01-01", "2025-01-03"]))
        teams = pd.Series(["team_a", "team_a"])
        result = compute_rest_days(dates, teams)
        assert pd.isna(result["rest_days"].iloc[0])

    def test_correct_rest_days(self) -> None:
        """Rest days should match actual calendar days between games."""
        dates = pd.Series(pd.to_datetime(["2025-01-01", "2025-01-04", "2025-01-05"]))
        teams = pd.Series(["team_a", "team_a", "team_a"])
        result = compute_rest_days(dates, teams)

        assert result["rest_days"].iloc[1] == 3  # Jan 1 -> Jan 4
        assert result["rest_days"].iloc[2] == 1  # Jan 4 -> Jan 5

    def test_back_to_back_detection(self) -> None:
        """Games on consecutive days should be flagged as back-to-back."""
        dates = pd.Series(pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-05"]))
        teams = pd.Series(["team_a", "team_a", "team_a"])
        result = compute_rest_days(dates, teams)

        assert bool(result["is_back_to_back"].iloc[1]) is True  # 1 day rest
        assert bool(result["is_back_to_back"].iloc[2]) is False  # 3 days rest

    def test_multi_team_isolation(self) -> None:
        """Rest days should be computed independently per team."""
        dates = pd.Series(pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-03", "2025-01-05"]))
        teams = pd.Series(["team_a", "team_b", "team_a", "team_b"])
        result = compute_rest_days(dates, teams)

        # team_a: Jan 1 -> Jan 3 = 2 days
        assert result["rest_days"].iloc[2] == 2
        # team_b: Jan 1 -> Jan 5 = 4 days
        assert result["rest_days"].iloc[3] == 4


# =============================================================================
# VALIDATE NO LEAKAGE TESTS
# =============================================================================


class TestValidateNoLeakage:
    """Tests for validate_no_leakage quick check."""

    def test_clean_features_pass(self) -> None:
        """Properly lagged features should pass."""
        np.random.seed(42)
        n = 100
        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=n),
                "target": np.random.choice([0, 1], size=n),
                "random_feature": np.random.randn(n),
            }
        )
        result = validate_no_leakage(df, ["random_feature"], "target", "date")
        assert result["passed"] is True

    def test_leaky_feature_detected(self) -> None:
        """A feature that IS the target should be caught."""
        n = 100
        targets = np.random.choice([0, 1], size=n)
        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=n),
                "target": targets,
                "leaky": targets.astype(float),  # Perfect copy of target
            }
        )
        result = validate_no_leakage(df, ["leaky"], "target", "date")
        assert result["passed"] is False
        assert "leaky" in result["suspicious_features"]

    def test_handles_nan_gracefully(self) -> None:
        """Should not crash on features with NaN values."""
        n = 50
        feature = np.random.randn(n)
        feature[:10] = np.nan
        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=n),
                "target": np.random.choice([0, 1], size=n),
                "feature_with_nans": feature,
            }
        )
        result = validate_no_leakage(df, ["feature_with_nans"], "target", "date")
        assert "passed" in result


# =============================================================================
# NCAAB FEATURE ENGINE TESTS
# =============================================================================


class TestNCABBFeatureEngine:
    """Tests for the NCAAB feature engine."""

    def test_compute_all_shape(self, team_game_log: pd.DataFrame) -> None:
        """compute_all should return same number of rows as input."""
        engine = NCABBFeatureEngine()
        result = engine.compute_all(team_game_log)
        assert len(result) == len(team_game_log)

    def test_compute_all_columns(self, team_game_log: pd.DataFrame) -> None:
        """compute_all should produce all expected feature columns."""
        engine = NCABBFeatureEngine()
        result = engine.compute_all(team_game_log)
        expected_cols = {
            "vol_5",
            "vol_10",
            "rest_days",
            "is_back_to_back",
            "decay_margin_10",
            "oq_margin_10",
        }
        assert expected_cols.issubset(set(result.columns))

    def test_no_nan_after_warmup(self, team_game_log: pd.DataFrame) -> None:
        """After sufficient warmup games, features should not be NaN."""
        engine = NCABBFeatureEngine()
        result = engine.compute_all(team_game_log)

        # After 11 rows (window=10 + shift=1), rolling features should be valid
        warmup = 11
        numeric_cols = result.select_dtypes(include=[np.number]).columns
        late_rows = result.iloc[warmup:]
        for col in numeric_cols:
            if col == "rest_days":
                continue  # rest_days only needs 1 prior game
            nan_count = late_rows[col].isna().sum()
            assert nan_count == 0, f"Column {col} has {nan_count} NaNs after warmup"

    def test_get_feature_names(self) -> None:
        """get_feature_names should return all canonical names."""
        names = NCABBFeatureEngine.get_feature_names()
        assert isinstance(names, list)
        assert len(names) == len(ALL_FEATURE_NAMES)
        assert "vol_5" in names
        assert "rest_days" in names

    def test_compute_matchup_differentials(self) -> None:
        """Differentials should correctly subtract away from home."""
        home = pd.Series(
            {
                "vol_5": 10.0,
                "vol_10": 8.0,
                "rest_days": 3.0,
                "oq_margin_10": 5.0,
                "decay_margin_10": 4.0,
                "is_back_to_back": False,
            }
        )
        away = pd.Series(
            {
                "vol_5": 12.0,
                "vol_10": 9.0,
                "rest_days": 1.0,
                "oq_margin_10": -2.0,
                "decay_margin_10": 1.0,
                "is_back_to_back": True,
            }
        )

        diffs = NCABBFeatureEngine.compute_matchup_differentials(home, away)

        assert diffs["vol_5_diff"] == pytest.approx(-2.0)  # 10 - 12
        assert diffs["rest_days_diff"] == pytest.approx(2.0)  # 3 - 1
        assert diffs["oq_margin_10_diff"] == pytest.approx(7.0)  # 5 - (-2)
        assert diffs["home_b2b"] == 0.0
        assert diffs["away_b2b"] == 1.0

    def test_without_opp_elo(self) -> None:
        """Engine should work without opp_elo column (skip oq_margin)."""
        np.random.seed(42)
        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=20, freq="2D"),
                "team_id": "team_x",
                "point_diff": np.random.randint(-15, 20, size=20),
            }
        )
        engine = NCABBFeatureEngine()
        result = engine.compute_all(df)
        assert "vol_5" in result.columns
        assert "oq_margin_10" not in result.columns  # Skipped


# =============================================================================
# ROLLING VOLATILITY SPECIFIC TESTS
# =============================================================================


class TestRollingVolatility:
    """Specific tests for rolling volatility computation."""

    def test_constant_series_zero_volatility(self) -> None:
        """A constant series should produce zero volatility."""
        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=15, freq="2D"),
                "team_id": "team_const",
                "point_diff": [5] * 15,
                "opp_elo": [1500] * 15,
            }
        )
        engine = NCABBFeatureEngine()
        result = engine.compute_rolling_volatility(df, windows=(5,))
        valid = result["vol_5"].dropna()
        assert (valid == 0.0).all()

    def test_high_variance_series(self) -> None:
        """A highly variable series should produce high volatility."""
        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-01-01", periods=15, freq="2D"),
                "team_id": "team_wild",
                "point_diff": [-20, 20, -20, 20, -20, 20, -20, 20, -20, 20, -20, 20, -20, 20, -20],
                "opp_elo": [1500] * 15,
            }
        )
        engine = NCABBFeatureEngine()
        result = engine.compute_rolling_volatility(df, windows=(5,))
        valid = result["vol_5"].dropna()
        assert valid.mean() > 15  # High volatility for +-20 swings
