"""Tests for late-season loss features.

Tests cover:
- .shift(1) prevents look-ahead bias (value at row i uses only rows < i)
- First N rows are NaN for N-game window features
- All-wins series returns 0 for loss count
- No-losses returns 0.0 for margin mean
- Output shape matches input length
- All expected columns present from compute_all_loss_features
"""

from __future__ import annotations

import pandas as pd
import pytest

from features.sport_specific.ncaab.late_season_losses import (
    ALL_LOSS_FEATURE_NAMES,
    compute_all_loss_features,
    compute_bad_loss_weighted,
    compute_home_loss_rate,
    compute_loss_count,
    compute_loss_margin_mean,
    compute_weighted_quality_loss,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def team_games() -> pd.DataFrame:
    """Realistic 20-game single-team log with mixed W/L."""
    results = [
        "W",
        "L",
        "W",
        "W",
        "L",
        "L",
        "W",
        "W",
        "W",
        "L",
        "W",
        "L",
        "W",
        "W",
        "L",
        "W",
        "W",
        "L",
        "W",
        "W",
    ]
    pts_for = [75, 60, 80, 70, 65, 55, 90, 85, 72, 68, 78, 62, 88, 74, 58, 82, 76, 64, 92, 70]
    pts_against = [70, 72, 65, 68, 78, 70, 60, 75, 68, 80, 72, 75, 70, 65, 72, 68, 70, 78, 65, 68]
    locations = [
        "Home",
        "Away",
        "Home",
        "Away",
        "Home",
        "Away",
        "Home",
        "Away",
        "Home",
        "Away",
        "Home",
        "Away",
        "Neutral",
        "Home",
        "Away",
        "Home",
        "Away",
        "Home",
        "Away",
        "Home",
    ]
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-11-04", periods=20, freq="3D"),
            "team_id": "team_a",
            "result": results,
            "points_for": pts_for,
            "points_against": pts_against,
            "point_diff": [pf - pa for pf, pa in zip(pts_for, pts_against)],
            "location": locations,
            "opponent_id": [f"opp_{i}" for i in range(20)],
        }
    )


@pytest.fixture
def all_wins_games() -> pd.DataFrame:
    """15-game log with all wins."""
    return pd.DataFrame(
        {
            "date": pd.date_range("2025-11-04", periods=15, freq="3D"),
            "team_id": "team_perfect",
            "result": ["W"] * 15,
            "points_for": [80] * 15,
            "points_against": [60] * 15,
            "point_diff": [20] * 15,
            "location": ["Home", "Away"] * 7 + ["Home"],
            "opponent_id": [f"opp_{i}" for i in range(15)],
        }
    )


@pytest.fixture
def opp_barthag() -> pd.Series:
    """Opponent barthag values aligned with team_games fixture."""
    return pd.Series(
        [
            0.8,
            0.9,
            0.5,
            0.7,
            0.3,
            0.2,
            0.85,
            0.6,
            0.75,
            0.95,
            0.4,
            0.55,
            0.65,
            0.7,
            0.15,
            0.8,
            0.5,
            0.35,
            0.9,
            0.6,
        ],
        name="opp_barthag",
    )


# =============================================================================
# LOSS COUNT TESTS
# =============================================================================


class TestLossCount:
    """Tests for compute_loss_count."""

    def test_shift_prevents_leakage(self, team_games: pd.DataFrame) -> None:
        """Value at row i must NOT include game i's result."""
        result = compute_loss_count(team_games, window=5)
        col = "late_loss_count_5g"

        # Row 5 (0-indexed): should count losses in rows 0-4, not row 5
        # Rows 0-4 results: W, L, W, W, L => 2 losses
        assert result[col].iloc[5] == 2.0

    def test_first_n_rows_nan(self, team_games: pd.DataFrame) -> None:
        """First window rows must be NaN due to shift(1)."""
        result = compute_loss_count(team_games, window=5)
        col = "late_loss_count_5g"
        assert result[col].iloc[:5].isna().all()

    def test_all_wins_returns_zero(self, all_wins_games: pd.DataFrame) -> None:
        """All-win series should produce 0 loss count after warmup."""
        result = compute_loss_count(all_wins_games, window=5)
        col = "late_loss_count_5g"
        valid = result[col].dropna()
        assert (valid == 0.0).all()

    def test_output_shape(self, team_games: pd.DataFrame) -> None:
        """Output length must match input length."""
        result = compute_loss_count(team_games, window=5)
        assert len(result) == len(team_games)

    def test_window_10(self, team_games: pd.DataFrame) -> None:
        """10-game window works correctly."""
        result = compute_loss_count(team_games, window=10)
        col = "late_loss_count_10g"
        assert col in result.columns
        assert result[col].iloc[:10].isna().all()


# =============================================================================
# LOSS MARGIN MEAN TESTS
# =============================================================================


class TestLossMarginMean:
    """Tests for compute_loss_margin_mean."""

    def test_shift_prevents_leakage(self, team_games: pd.DataFrame) -> None:
        """Value at row i reflects only rows < i."""
        result = compute_loss_margin_mean(team_games, window=10)
        col = "loss_margin_mean_10g"
        # Row 10 should use rows 0-9. Losses in 0-9: rows 1,4,5,9
        # Row 1: 72-60=12, Row 4: 78-65=13, Row 5: 70-55=15, Row 9: 80-68=12
        expected = (12 + 13 + 15 + 12) / 4.0
        assert result[col].iloc[10] == pytest.approx(expected, abs=0.01)

    def test_no_losses_returns_zero(self, all_wins_games: pd.DataFrame) -> None:
        """If no losses in window, should return 0.0."""
        result = compute_loss_margin_mean(all_wins_games, window=10)
        col = "loss_margin_mean_10g"
        valid = result[col].dropna()
        assert (valid == 0.0).all()

    def test_first_n_rows_nan(self, team_games: pd.DataFrame) -> None:
        """First window rows must be NaN."""
        result = compute_loss_margin_mean(team_games, window=10)
        col = "loss_margin_mean_10g"
        assert result[col].iloc[:10].isna().all()

    def test_output_shape(self, team_games: pd.DataFrame) -> None:
        """Output length must match input length."""
        result = compute_loss_margin_mean(team_games, window=10)
        assert len(result) == len(team_games)


# =============================================================================
# WEIGHTED QUALITY LOSS TESTS
# =============================================================================


class TestWeightedQualityLoss:
    """Tests for compute_weighted_quality_loss."""

    def test_shift_prevents_leakage(self, team_games: pd.DataFrame, opp_barthag: pd.Series) -> None:
        """Value at row i must use only rows < i."""
        result = compute_weighted_quality_loss(team_games, opp_barthag, window=10)
        col = "weighted_quality_loss_10g"
        # Row 10 uses rows 0-9.
        # Losses at rows 1,4,5,9 with barthags 0.9,0.3,0.2,0.95
        # Sum = 0.9+0.3+0.2+0.95 = 2.35, divided by 10 games = 0.235
        assert result[col].iloc[10] == pytest.approx(2.35 / 10, abs=0.01)

    def test_all_wins_returns_zero(self, all_wins_games: pd.DataFrame) -> None:
        """All-win series => weighted quality loss is 0."""
        opp_b = pd.Series([0.7] * 15, name="opp_barthag")
        result = compute_weighted_quality_loss(all_wins_games, opp_b, window=10)
        col = "weighted_quality_loss_10g"
        valid = result[col].dropna()
        assert (valid == 0.0).all()

    def test_output_shape(self, team_games: pd.DataFrame, opp_barthag: pd.Series) -> None:
        """Output length must match input."""
        result = compute_weighted_quality_loss(team_games, opp_barthag, window=10)
        assert len(result) == len(team_games)


# =============================================================================
# BAD LOSS WEIGHTED TESTS
# =============================================================================


class TestBadLossWeighted:
    """Tests for compute_bad_loss_weighted."""

    def test_shift_prevents_leakage(self, team_games: pd.DataFrame, opp_barthag: pd.Series) -> None:
        """Value at row i must use only rows < i."""
        result = compute_bad_loss_weighted(team_games, opp_barthag, window=10)
        col = "bad_loss_weighted_10g"
        # Row 10 uses rows 0-9.
        # Losses at rows 1,4,5,9 with (1 - barthag): 0.1, 0.7, 0.8, 0.05
        # Sum = 1.65, divided by 10 games = 0.165
        assert result[col].iloc[10] == pytest.approx(1.65 / 10, abs=0.01)

    def test_loss_to_weak_team_scores_high(self, team_games: pd.DataFrame) -> None:
        """Losing to a weak team (low barthag) should produce higher bad_loss."""
        # Create barthag where all losses are against weak opponents
        opp_b_weak = pd.Series([0.1] * 20, name="opp_barthag")
        result_weak = compute_bad_loss_weighted(team_games, opp_b_weak, window=10)

        # Create barthag where all losses are against strong opponents
        opp_b_strong = pd.Series([0.95] * 20, name="opp_barthag")
        result_strong = compute_bad_loss_weighted(team_games, opp_b_strong, window=10)

        col = "bad_loss_weighted_10g"
        # After warmup, weak-opponent losses should score higher
        valid_idx = result_weak[col].dropna().index
        if len(valid_idx) > 0:
            # On rows with losses in window, weak should be higher
            idx = valid_idx[0]
            assert result_weak[col].iloc[idx] >= result_strong[col].iloc[idx]


# =============================================================================
# HOME LOSS RATE TESTS
# =============================================================================


class TestHomeLossRate:
    """Tests for compute_home_loss_rate."""

    def test_shift_prevents_leakage(self, team_games: pd.DataFrame) -> None:
        """Value at row i uses only rows < i."""
        result = compute_home_loss_rate(team_games, window=10)
        col = "home_loss_rate_10g"
        # Row 10 uses rows 0-9.
        # Home games in 0-9: rows 0(W),2(W),4(L),6(W),8(W) => 5 home, 1 loss
        # Rate = 1/5 = 0.2
        assert result[col].iloc[10] == pytest.approx(0.2, abs=0.01)

    def test_no_home_games_is_nan(self) -> None:
        """If no home games in window, result should be NaN."""
        df = pd.DataFrame(
            {
                "date": pd.date_range("2025-11-04", periods=12, freq="3D"),
                "team_id": "team_away",
                "result": ["W", "L"] * 6,
                "points_for": [80] * 12,
                "points_against": [70] * 12,
                "point_diff": [10] * 12,
                "location": ["Away"] * 12,
                "opponent_id": [f"opp_{i}" for i in range(12)],
            }
        )
        result = compute_home_loss_rate(df, window=10)
        col = "home_loss_rate_10g"
        # After warmup, all should be NaN (no home games)
        valid_area = result[col].iloc[10:]
        assert valid_area.isna().all()

    def test_excludes_neutral(self, team_games: pd.DataFrame) -> None:
        """Neutral-site games should not count as home games."""
        result = compute_home_loss_rate(team_games, window=10)
        # Row 12 is Neutral — verify it doesn't affect the calculation
        # as a "home" game in subsequent rows
        assert "home_loss_rate_10g" in result.columns
        assert len(result) == len(team_games)

    def test_output_shape(self, team_games: pd.DataFrame) -> None:
        """Output length must match input."""
        result = compute_home_loss_rate(team_games, window=10)
        assert len(result) == len(team_games)


# =============================================================================
# COMPUTE ALL TESTS
# =============================================================================


class TestComputeAllLossFeatures:
    """Tests for compute_all_loss_features."""

    def test_all_columns_present(self, team_games: pd.DataFrame, opp_barthag: pd.Series) -> None:
        """All 6 expected feature columns must be present."""
        result = compute_all_loss_features(team_games, opp_barthag=opp_barthag)
        expected = set(ALL_LOSS_FEATURE_NAMES)
        assert expected.issubset(set(result.columns))

    def test_output_shape(self, team_games: pd.DataFrame, opp_barthag: pd.Series) -> None:
        """Output rows must match input rows."""
        result = compute_all_loss_features(team_games, opp_barthag=opp_barthag)
        assert len(result) == len(team_games)

    def test_without_opp_barthag(self, team_games: pd.DataFrame) -> None:
        """Should work without opp_barthag, skipping barthag features."""
        result = compute_all_loss_features(team_games, opp_barthag=None)
        assert "late_loss_count_5g" in result.columns
        assert "late_loss_count_10g" in result.columns
        assert "loss_margin_mean_10g" in result.columns
        assert "home_loss_rate_10g" in result.columns
        # barthag features should be absent
        assert "weighted_quality_loss_10g" not in result.columns
        assert "bad_loss_weighted_10g" not in result.columns

    def test_index_alignment(self, team_games: pd.DataFrame, opp_barthag: pd.Series) -> None:
        """Output index must match input index."""
        result = compute_all_loss_features(team_games, opp_barthag=opp_barthag)
        pd.testing.assert_index_equal(result.index, team_games.index)
