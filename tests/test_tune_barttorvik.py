"""Tests for Barttorvik weight tuning and related changes."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.backtest_ncaab_elo import BarttovikCoeffs, summarize_backtest  # noqa: E402
from scripts.tune_barttorvik_weights import (  # noqa: E402
    FULL_BARTHAG_COEFFS,
    FULL_NET_COEFFS,
    FULL_WEIGHTS,
    QUICK_BARTHAG_COEFFS,
    QUICK_NET_COEFFS,
    QUICK_WEIGHTS,
    GridPoint,
    build_grid,
)


class TestBarttovikCoeffs:
    """Tests for BarttovikCoeffs dataclass."""

    def test_defaults(self):
        coeffs = BarttovikCoeffs()
        assert coeffs.net_diff_coeff == 0.003
        assert coeffs.barthag_diff_coeff == 0.1

    def test_custom_values(self):
        coeffs = BarttovikCoeffs(net_diff_coeff=0.005, barthag_diff_coeff=0.2)
        assert coeffs.net_diff_coeff == 0.005
        assert coeffs.barthag_diff_coeff == 0.2

    def test_computation(self):
        """Verify the math matches what backtest uses."""
        coeffs = BarttovikCoeffs(net_diff_coeff=0.003, barthag_diff_coeff=0.1)
        net_diff = 10.0  # typical
        barthag_diff = 0.2
        expected = 10.0 * 0.003 + 0.2 * 0.1  # 0.03 + 0.02 = 0.05
        actual = net_diff * coeffs.net_diff_coeff + barthag_diff * coeffs.barthag_diff_coeff
        assert abs(actual - expected) < 1e-10


class TestSummarizeBacktestFlatROI:
    """Tests for flat_roi in summarize_backtest."""

    def _make_results_df(self, pnls, stakes):
        """Helper to build a minimal results DataFrame."""
        n = len(pnls)
        return pd.DataFrame(
            {
                "profit_loss": pnls,
                "stake": stakes,
                "result": ["win" if p > 0 else "loss" for p in pnls],
                "date": pd.date_range("2025-01-01", periods=n, freq="D"),
                "bankroll": np.cumsum(pnls) + 5000,
                "edge": [0.05] * n,
                "clv": [0.01] * n,
            }
        )

    def test_flat_roi_present(self):
        df = self._make_results_df([100, -50, 75], [100, 100, 100])
        summary = summarize_backtest(df)
        assert "flat_roi" in summary

    def test_flat_roi_value(self):
        """flat_roi = mean(pnl/stake) for each bet."""
        df = self._make_results_df([100, -100, 50], [100, 100, 100])
        summary = summarize_backtest(df)
        expected = np.mean([100 / 100, -100 / 100, 50 / 100])
        assert abs(summary["flat_roi"] - expected) < 1e-10

    def test_flat_roi_different_stakes(self):
        """flat_roi treats each bet equally regardless of stake."""
        df = self._make_results_df([200, -50], [200, 100])
        summary = summarize_backtest(df)
        # Per-bet returns: 200/200=1.0, -50/100=-0.5 -> mean=0.25
        expected = np.mean([1.0, -0.5])
        assert abs(summary["flat_roi"] - expected) < 1e-10

    def test_flat_roi_vs_kelly_roi(self):
        """flat_roi and roi should differ when stakes vary."""
        df = self._make_results_df([200, -50], [200, 100])
        summary = summarize_backtest(df)
        # Kelly ROI = total_pnl/total_staked = 150/300 = 0.5
        # Flat ROI = mean([1.0, -0.5]) = 0.25
        assert abs(summary["roi"] - 0.5) < 1e-10
        assert abs(summary["flat_roi"] - 0.25) < 1e-10
        assert summary["flat_roi"] != summary["roi"]

    def test_empty_df(self):
        summary = summarize_backtest(pd.DataFrame())
        assert "error" in summary


class TestBuildGrid:
    """Tests for grid construction."""

    def test_full_grid_size(self):
        grid = build_grid(quick=False)
        expected = len(FULL_WEIGHTS) * len(FULL_NET_COEFFS) * len(FULL_BARTHAG_COEFFS)
        assert len(grid) == expected
        assert len(grid) == 80

    def test_quick_grid_size(self):
        grid = build_grid(quick=True)
        expected = len(QUICK_WEIGHTS) * len(QUICK_NET_COEFFS) * len(QUICK_BARTHAG_COEFFS)
        assert len(grid) == expected
        assert len(grid) == 12

    def test_grid_contains_tuples(self):
        grid = build_grid(quick=True)
        for point in grid:
            assert len(point) == 3
            weight, net_c, bart_c = point
            assert isinstance(weight, float)
            assert isinstance(net_c, float)
            assert isinstance(bart_c, float)

    def test_full_grid_contains_defaults(self):
        """Default coefficients (0.003, 0.1) should be in the full grid."""
        grid = build_grid(quick=False)
        has_default = any(abs(nc - 0.003) < 1e-10 and abs(bc - 0.1) < 1e-10 for _, nc, bc in grid)
        assert has_default

    def test_no_duplicates(self):
        grid = build_grid(quick=False)
        assert len(grid) == len(set(grid))


class TestGridPoint:
    """Tests for GridPoint dataclass."""

    def test_creation(self):
        gp = GridPoint(
            barttorvik_weight=1.0,
            net_diff_coeff=0.003,
            barthag_diff_coeff=0.1,
            seasons_tested=[2024, 2025],
            flat_roi_per_season={2024: 0.065, 2025: 0.101},
            pooled_flat_roi=0.083,
            pooled_bets=4047,
            pooled_sharpe=0.7,
            t_stat=2.5,
            p_value=0.05,
        )
        assert gp.barttorvik_weight == 1.0
        assert gp.pooled_flat_roi == 0.083
        assert len(gp.seasons_tested) == 2
