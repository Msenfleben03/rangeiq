"""Tests for KenPom weight tuning grid search."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.backtest_ncaab_elo import KenPomCoeffs  # noqa: E402
from scripts.tune_kenpom_weights import (  # noqa: E402
    FULL_NET_COEFFS,
    FULL_SOS_COEFFS,
    FULL_WEIGHTS,
    QUICK_NET_COEFFS,
    QUICK_SOS_COEFFS,
    QUICK_WEIGHTS,
    KenPomGridPoint,
    build_kenpom_grid,
)


class TestKenPomCoeffs:
    """Tests for KenPomCoeffs dataclass."""

    def test_defaults(self):
        coeffs = KenPomCoeffs()
        assert coeffs.net_diff_coeff == 0.005
        assert coeffs.sos_coeff == 0.0

    def test_custom_values(self):
        coeffs = KenPomCoeffs(net_diff_coeff=0.008, sos_coeff=0.01)
        assert coeffs.net_diff_coeff == 0.008
        assert coeffs.sos_coeff == 0.01

    def test_computation(self):
        """Verify the math matches what backtest uses."""
        coeffs = KenPomCoeffs(net_diff_coeff=0.005, sos_coeff=0.002)
        adj_em_diff = 8.0  # typical
        sos_diff = 3.0
        expected = 8.0 * 0.005 + 3.0 * 0.002  # 0.04 + 0.006 = 0.046
        actual = adj_em_diff * coeffs.net_diff_coeff + sos_diff * coeffs.sos_coeff
        assert abs(actual - expected) < 1e-10


class TestBuildKenPomGrid:
    """Tests for KenPom grid construction."""

    def test_full_grid_size(self):
        grid = build_kenpom_grid(quick=False)
        expected = len(FULL_WEIGHTS) * len(FULL_NET_COEFFS) * len(FULL_SOS_COEFFS)
        assert len(grid) == expected
        assert len(grid) == 80

    def test_quick_grid_size(self):
        grid = build_kenpom_grid(quick=True)
        expected = len(QUICK_WEIGHTS) * len(QUICK_NET_COEFFS) * len(QUICK_SOS_COEFFS)
        assert len(grid) == expected
        assert len(grid) == 12

    def test_grid_contains_tuples(self):
        grid = build_kenpom_grid(quick=True)
        for point in grid:
            assert len(point) == 3
            weight, net_c, sos_c = point
            assert isinstance(weight, float)
            assert isinstance(net_c, float)
            assert isinstance(sos_c, float)

    def test_full_grid_contains_defaults(self):
        """Default coefficient (0.005) should be in the full grid."""
        grid = build_kenpom_grid(quick=False)
        has_default = any(abs(nc - 0.005) < 1e-10 for _, nc, _ in grid)
        assert has_default

    def test_sos_zero_in_grid(self):
        """SOS=0.0 (disabled) should be in both grids."""
        full_grid = build_kenpom_grid(quick=False)
        quick_grid = build_kenpom_grid(quick=True)
        assert any(abs(sc) < 1e-10 for _, _, sc in full_grid)
        assert any(abs(sc) < 1e-10 for _, _, sc in quick_grid)

    def test_no_duplicates(self):
        grid = build_kenpom_grid(quick=False)
        assert len(grid) == len(set(grid))


class TestKenPomGridPoint:
    """Tests for KenPomGridPoint dataclass."""

    def test_creation(self):
        gp = KenPomGridPoint(
            kenpom_weight=1.0,
            net_diff_coeff=0.005,
            sos_coeff=0.002,
            combined_mode=False,
            seasons_tested=[2024, 2025],
            flat_roi_per_season={2024: 0.065, 2025: 0.101},
            pooled_flat_roi=0.083,
            pooled_bets=4047,
            pooled_sharpe=0.7,
            t_stat=2.5,
            p_value=0.05,
        )
        assert gp.kenpom_weight == 1.0
        assert gp.pooled_flat_roi == 0.083
        assert len(gp.seasons_tested) == 2
        assert not gp.combined_mode

    def test_combined_mode(self):
        gp = KenPomGridPoint(
            kenpom_weight=0.5,
            net_diff_coeff=0.003,
            sos_coeff=0.005,
            combined_mode=True,
            seasons_tested=[2020, 2021, 2022],
            flat_roi_per_season={2020: 0.10, 2021: 0.05, 2022: 0.08},
            pooled_flat_roi=0.0767,
            pooled_bets=6000,
            pooled_sharpe=0.8,
            t_stat=3.1,
            p_value=0.01,
        )
        assert gp.combined_mode
        assert gp.sos_coeff == 0.005
        assert len(gp.flat_roi_per_season) == 3
