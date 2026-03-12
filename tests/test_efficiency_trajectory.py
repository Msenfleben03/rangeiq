"""Tests for efficiency trajectory feature computation.

Verifies OLS slopes, sign flipping, delta calculations, and edge cases
for the 6 efficiency trajectory features derived from Barttorvik snapshots.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from features.sport_specific.ncaab.efficiency_trajectory import (
    MIN_SLOPE_POINTS,
    compute_all_trajectory_features,
    compute_barthag_delta,
    compute_net_efficiency_slope,
    compute_ols_slope,
    compute_rank_change,
)


def _make_snapshots(n: int = 15, **overrides: list) -> pd.DataFrame:
    """Create synthetic single-team Barttorvik snapshots.

    By default generates linearly increasing adj_o and decreasing adj_d
    (both improving), with barthag rising and rank dropping.
    """
    dates = pd.date_range("2024-01-01", periods=n, freq="3D")
    data = {
        "date": dates,
        "team": ["TeamA"] * n,
        "adj_o": overrides.get("adj_o", [100 + i * 0.5 for i in range(n)]),
        "adj_d": overrides.get("adj_d", [100 - i * 0.3 for i in range(n)]),
        "barthag": overrides.get("barthag", [0.5 + i * 0.02 for i in range(n)]),
        "rank": overrides.get("rank", [200 - i * 5 for i in range(n)]),
    }
    return pd.DataFrame(data)


class TestComputeOlsSlope:
    """Tests for compute_ols_slope."""

    def test_positive_trend_produces_positive_slope(self):
        """Increasing adj_o should produce a positive slope."""
        snaps = _make_snapshots(12)
        result = compute_ols_slope(snaps, "adj_o", n_snapshots=10)
        col = "adj_o_slope_10s"
        assert col in result.columns
        # Last row should have a valid positive slope
        last_val = result[col].iloc[-1]
        assert not np.isnan(last_val)
        assert last_val > 0

    def test_adj_d_sign_flip(self):
        """adj_d slope should be sign-flipped so positive = defense improving."""
        # adj_d decreasing (improving defense) -> raw slope negative -> flipped positive
        snaps = _make_snapshots(12)
        result = compute_ols_slope(snaps, "adj_d", n_snapshots=10, flip_sign=True)
        col = "adj_d_slope_10s"
        last_val = result[col].iloc[-1]
        assert not np.isnan(last_val)
        assert last_val > 0, "Decreasing adj_d should give positive slope after flip"

    def test_nan_for_insufficient_data(self):
        """Fewer than MIN_SLOPE_POINTS data points should produce NaN."""
        snaps = _make_snapshots(4)  # Only 4 points, below MIN_SLOPE_POINTS=5
        result = compute_ols_slope(snaps, "adj_o", n_snapshots=10)
        col = "adj_o_slope_10s"
        assert result[col].isna().all()

    def test_exactly_min_points_is_valid(self):
        """Exactly MIN_SLOPE_POINTS data points should produce a valid slope."""
        snaps = _make_snapshots(MIN_SLOPE_POINTS)
        result = compute_ols_slope(snaps, "adj_o", n_snapshots=10)
        col = "adj_o_slope_10s"
        # The last row should have a valid slope (5 points available)
        assert not np.isnan(result[col].iloc[-1])


class TestComputeNetEfficiencySlope:
    """Tests for compute_net_efficiency_slope."""

    def test_improving_net_gives_positive_slope(self):
        """When adj_o rises and adj_d falls, net efficiency slope should be positive."""
        snaps = _make_snapshots(12)
        result = compute_net_efficiency_slope(snaps, n_snapshots=10)
        col = "net_efficiency_slope_10s"
        assert col in result.columns
        last_val = result[col].iloc[-1]
        assert last_val > 0


class TestComputeBarthagDelta:
    """Tests for compute_barthag_delta."""

    def test_improving_barthag_positive_delta(self):
        """Rising barthag should produce a positive delta."""
        snaps = _make_snapshots(15)
        result = compute_barthag_delta(snaps, n_snapshots=10)
        col = "barthag_delta_10s"
        assert col in result.columns
        last_val = result[col].iloc[-1]
        assert last_val > 0

    def test_nan_when_insufficient_history(self):
        """barthag_delta_20s should be NaN when fewer than 20 snapshots available."""
        snaps = _make_snapshots(15)
        result = compute_barthag_delta(snaps, n_snapshots=20)
        col = "barthag_delta_20s"
        assert result[col].isna().all()


class TestComputeRankChange:
    """Tests for compute_rank_change."""

    def test_improving_rank_positive_change(self):
        """Team rising in rankings (rank decreasing) should give positive rank_change."""
        snaps = _make_snapshots(25)
        result = compute_rank_change(snaps, n_snapshots=20)
        col = "rank_change_20s"
        assert col in result.columns
        last_val = result[col].iloc[-1]
        assert last_val > 0, "Rank dropping (improving) should give positive change"


class TestComputeAllTrajectoryFeatures:
    """Tests for compute_all_trajectory_features."""

    def test_output_has_all_six_columns(self):
        """Output should contain all 6 expected feature columns."""
        snaps = _make_snapshots(25)
        result = compute_all_trajectory_features(snaps)
        expected_cols = {
            "adj_o_slope_10s",
            "adj_d_slope_10s",
            "net_efficiency_slope_10s",
            "barthag_delta_10s",
            "barthag_delta_20s",
            "rank_change_20s",
        }
        assert expected_cols == set(result.columns)

    def test_output_length_matches_input(self):
        """Output DataFrame should have same number of rows as input."""
        snaps = _make_snapshots(20)
        result = compute_all_trajectory_features(snaps)
        assert len(result) == len(snaps)

    def test_flat_data_produces_zero_slopes(self):
        """Constant values should produce zero (or near-zero) slopes."""
        n = 15
        snaps = _make_snapshots(
            n,
            adj_o=[100.0] * n,
            adj_d=[95.0] * n,
            barthag=[0.7] * n,
            rank=[50] * n,
        )
        result = compute_all_trajectory_features(snaps)
        # Slopes should be ~0 for constant data
        assert abs(result["adj_o_slope_10s"].iloc[-1]) < 1e-10
        assert abs(result["adj_d_slope_10s"].iloc[-1]) < 1e-10
        assert abs(result["net_efficiency_slope_10s"].iloc[-1]) < 1e-10
        # Deltas should be exactly 0
        assert result["barthag_delta_10s"].iloc[-1] == 0.0
