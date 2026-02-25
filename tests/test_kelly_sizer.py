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
    """Test Platt scaling calibration on model_prob."""

    @pytest.fixture()
    def calibration_data(self):
        """Synthetic data: higher model_prob -> higher win rate."""
        rng = np.random.RandomState(42)
        n = 2000
        model_probs = rng.uniform(0.20, 0.95, n)
        true_probs = 1 / (1 + np.exp(-6 * (model_probs - 0.55)))
        wins = (rng.random(n) < true_probs).astype(int)
        return pd.DataFrame({"model_prob": model_probs, "won": wins})

    def test_calibrate_fits_model(self, calibration_data):
        sizer = KellySizer()
        sizer.calibrate(calibration_data["model_prob"].values, calibration_data["won"].values)
        assert sizer.is_calibrated

    def test_calibrated_prob_increases_with_model_prob(self, calibration_data):
        sizer = KellySizer()
        sizer.calibrate(calibration_data["model_prob"].values, calibration_data["won"].values)
        p_low = sizer.calibrated_win_prob(0.30)
        p_mid = sizer.calibrated_win_prob(0.60)
        p_high = sizer.calibrated_win_prob(0.90)
        assert p_low < p_mid < p_high

    def test_calibrated_prob_bounded_0_1(self, calibration_data):
        sizer = KellySizer()
        sizer.calibrate(calibration_data["model_prob"].values, calibration_data["won"].values)
        for mp in [0.10, 0.50, 0.95]:
            p = sizer.calibrated_win_prob(mp)
            assert 0 < p < 1

    def test_uncalibrated_falls_back_to_model_prob(self):
        sizer = KellySizer()
        assert sizer.calibrated_win_prob(0.65) is None


class TestSizeBet:
    """Test the main size_bet() method."""

    @pytest.fixture()
    def calibrated_sizer(self):
        """KellySizer calibrated on realistic model_prob data."""
        rng = np.random.RandomState(42)
        n = 2000
        model_probs = rng.uniform(0.20, 0.95, n)
        true_probs = 1 / (1 + np.exp(-6 * (model_probs - 0.55)))
        wins = (rng.random(n) < true_probs).astype(int)
        sizer = KellySizer(kelly_fraction=0.25, max_bet_fraction=0.05, bankroll=5000)
        sizer.calibrate(model_probs, wins)
        return sizer

    def test_higher_model_prob_gets_larger_stake(self, calibrated_sizer):
        stake_low = calibrated_sizer.size_bet(model_prob=0.55, edge=0.08, american_odds=120)
        stake_high = calibrated_sizer.size_bet(model_prob=0.80, edge=0.30, american_odds=120)
        assert stake_high > stake_low

    def test_respects_max_bet(self, calibrated_sizer):
        stake = calibrated_sizer.size_bet(model_prob=0.95, edge=0.80, american_odds=500)
        max_dollars = calibrated_sizer.bankroll * calibrated_sizer.max_bet_fraction
        assert stake <= max_dollars + 0.01

    def test_low_model_prob_returns_zero(self, calibrated_sizer):
        stake = calibrated_sizer.size_bet(model_prob=0.30, edge=0.0, american_odds=-110)
        assert stake == 0.0

    def test_negative_kelly_returns_zero(self, calibrated_sizer):
        stake = calibrated_sizer.size_bet(model_prob=0.30, edge=0.01, american_odds=-200)
        assert stake == 0.0

    def test_uncalibrated_uses_model_prob(self):
        """Without calibration, falls back to raw model_prob for Kelly."""
        sizer = KellySizer(kelly_fraction=0.25, max_bet_fraction=0.05, bankroll=5000)
        stake = sizer.size_bet(model_prob=0.60, edge=0.10, american_odds=150)
        dec = american_to_decimal(150)
        raw_frac = fractional_kelly(0.60, dec, fraction=0.25, max_bet=0.05)
        expected = 5000 * raw_frac
        assert abs(stake - expected) < 0.01

    def test_min_bet_threshold(self, calibrated_sizer):
        """Stakes below $10 should be rounded to 0."""
        stake = calibrated_sizer.size_bet(model_prob=0.52, edge=0.075, american_odds=-105)
        assert stake == 0.0 or stake >= 10.0

    def test_stakes_vary_with_edge_size(self, calibrated_sizer):
        """Verify dynamic Kelly produces different stakes for different edges."""
        # Moderate confidence: model_prob near break-even
        stake_small = calibrated_sizer.size_bet(model_prob=0.58, edge=0.05, american_odds=110)
        # High confidence: model_prob well above break-even
        stake_large = calibrated_sizer.size_bet(model_prob=0.85, edge=0.25, american_odds=-200)
        # At least one should be > 0, and they should differ
        assert stake_large > 0
        assert stake_large >= stake_small


class TestBuildCalibrationData:
    """Test calibration data loader."""

    def test_loads_from_parquet_files(self, tmp_path):
        from betting.odds_converter import build_calibration_data

        df = pd.DataFrame(
            {
                "model_prob": [0.60, 0.55, 0.70],
                "result": ["win", "loss", "win"],
            }
        )
        df.to_parquet(tmp_path / "ncaab_elo_backtest_2025.parquet", index=False)

        model_probs, outcomes = build_calibration_data(tmp_path)
        assert len(model_probs) == 3
        assert list(outcomes) == [1, 0, 1]
        np.testing.assert_allclose(model_probs, [0.60, 0.55, 0.70])

    def test_combines_multiple_seasons(self, tmp_path):
        from betting.odds_converter import build_calibration_data

        for season in [2024, 2025]:
            df = pd.DataFrame(
                {
                    "model_prob": [0.60, 0.70],
                    "result": ["win", "loss"],
                }
            )
            df.to_parquet(tmp_path / f"ncaab_elo_backtest_{season}.parquet", index=False)

        model_probs, outcomes = build_calibration_data(tmp_path)
        assert len(model_probs) == 4

    def test_empty_directory_raises(self, tmp_path):
        from betting.odds_converter import build_calibration_data

        with pytest.raises(FileNotFoundError):
            build_calibration_data(tmp_path)
