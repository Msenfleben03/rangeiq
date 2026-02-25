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
        stake_low = calibrated_sizer.size_bet(model_prob=0.55, edge=0.08, american_odds=120)
        stake_high = calibrated_sizer.size_bet(model_prob=0.70, edge=0.30, american_odds=300)
        assert stake_high > stake_low

    def test_respects_max_bet(self, calibrated_sizer):
        stake = calibrated_sizer.size_bet(model_prob=0.95, edge=0.80, american_odds=500)
        max_dollars = calibrated_sizer.bankroll * calibrated_sizer.max_bet_fraction
        assert stake <= max_dollars + 0.01

    def test_zero_edge_returns_zero(self, calibrated_sizer):
        stake = calibrated_sizer.size_bet(model_prob=0.50, edge=0.0, american_odds=-110)
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
