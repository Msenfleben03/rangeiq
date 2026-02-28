"""Tests for divergence analysis."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


class TestComputeDivergence:
    """Tests for divergence computation between model and ESPN probabilities."""

    def test_home_bet_divergence(self):
        """Home bet: model_prob IS home_prob directly."""
        from scripts.analyze_divergence import compute_divergence

        row = {"bet_side": "home", "model_prob": 0.65}
        result = compute_divergence(row, espn_home_prob=0.72)
        assert result["home_prob"] == pytest.approx(0.65)
        assert result["divergence"] == pytest.approx(-0.07)
        assert result["abs_divergence"] == pytest.approx(0.07)
        assert result["direction"] == "model_lower"

    def test_away_bet_divergence(self):
        """Away bet: home_prob = 1 - model_prob."""
        from scripts.analyze_divergence import compute_divergence

        # bet_side="away", model_prob=0.40 means P(away win)=0.40
        # so home_prob = 1 - 0.40 = 0.60
        row = {"bet_side": "away", "model_prob": 0.40}
        result = compute_divergence(row, espn_home_prob=0.55)
        assert result["home_prob"] == pytest.approx(0.60)
        assert result["divergence"] == pytest.approx(0.05)
        assert result["direction"] == "model_higher"

    def test_handles_none_espn_prob(self):
        """None ESPN prob should produce NaN divergence."""
        from scripts.analyze_divergence import compute_divergence

        row = {"bet_side": "home", "model_prob": 0.65}
        result = compute_divergence(row, espn_home_prob=None)
        assert np.isnan(result["divergence"])


class TestAssignBucket:
    """Tests for divergence bucket assignment."""

    @pytest.mark.parametrize(
        "abs_div, expected",
        [
            (0.03, "0-5pp"),
            (0.07, "5-10pp"),
            (0.12, "10-15pp"),
            (0.17, "15-20pp"),
            (0.25, "20pp+"),
            (0.0, "0-5pp"),
            (0.05, "5-10pp"),  # boundary: 5pp goes to 5-10
        ],
    )
    def test_bucket_assignment(self, abs_div, expected):
        """Bucket boundaries should be [0,5), [5,10), [10,15), [15,20), [20,+inf)."""
        from scripts.analyze_divergence import assign_bucket

        assert assign_bucket(abs_div) == expected


class TestBucketAnalysis:
    """Tests for bucketed performance analysis."""

    def _make_df(self):
        """Synthetic data: 3 bets in 0-5pp bucket, 2 in 15-20pp."""
        return pd.DataFrame(
            {
                "result": ["win", "win", "loss", "loss", "loss"],
                "profit_loss": [100.0, 80.0, -100.0, -100.0, -100.0],
                "stake": [100.0, 100.0, 100.0, 100.0, 100.0],
                "clv": [0.02, 0.03, 0.01, -0.01, -0.02],
                "abs_divergence": [0.03, 0.04, 0.02, 0.16, 0.18],
                "divergence_bucket": ["0-5pp", "0-5pp", "0-5pp", "15-20pp", "15-20pp"],
                "edge": [0.08, 0.09, 0.07, 0.12, 0.14],
            }
        )

    def test_roi_per_bucket(self):
        """ROI = sum(profit_loss) / sum(stake)."""
        from scripts.analyze_divergence import analyze_buckets

        df = self._make_df()
        result = analyze_buckets(df)
        # 0-5pp bucket: (100 + 80 - 100) / (3 * 100) = 26.7%
        low = result[result["bucket"] == "0-5pp"].iloc[0]
        assert low["roi"] == pytest.approx(80 / 300, abs=0.01)

    def test_win_rate_per_bucket(self):
        """Win rate = wins / total in bucket."""
        from scripts.analyze_divergence import analyze_buckets

        df = self._make_df()
        result = analyze_buckets(df)
        low = result[result["bucket"] == "0-5pp"].iloc[0]
        assert low["win_rate"] == pytest.approx(2 / 3, abs=0.01)
        high = result[result["bucket"] == "15-20pp"].iloc[0]
        assert high["win_rate"] == pytest.approx(0.0)
