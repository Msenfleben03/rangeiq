"""Tests for ESPN divergence data fetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ── Mock API responses ──────────────────────────────────────────────

MOCK_WITH_WP = {
    "winprobability": [
        {"homeWinPercentage": 0.72, "tiePercentage": 0.0, "playId": "123"},
        {"homeWinPercentage": 0.75, "tiePercentage": 0.0, "playId": "124"},
    ],
}
MOCK_NO_WP = {"winprobability": []}
MOCK_MISSING_KEY = {"header": {}}


# ── fetch_single_game_prob ──────────────────────────────────────────


class TestFetchSingleGameProb:
    """Tests for fetching a single game's ESPN pre-game probability."""

    @patch("scripts.fetch_espn_divergence.requests.get")
    def test_extracts_home_win_percentage(self, mock_get):
        """First entry in winprobability is pre-game prob."""
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = MOCK_WITH_WP
        mock_get.return_value.raise_for_status = MagicMock()

        from scripts.fetch_espn_divergence import fetch_single_game_prob

        result = fetch_single_game_prob("401712993")
        assert result["espn_home_prob"] == pytest.approx(0.72)
        assert result["fetch_success"] is True

    @patch("scripts.fetch_espn_divergence.requests.get")
    def test_returns_none_when_empty_wp(self, mock_get):
        """Empty winprobability array means no data available."""
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = MOCK_NO_WP
        mock_get.return_value.raise_for_status = MagicMock()

        from scripts.fetch_espn_divergence import fetch_single_game_prob

        result = fetch_single_game_prob("401712993")
        assert result["espn_home_prob"] is None
        assert result["fetch_success"] is True

    @patch("scripts.fetch_espn_divergence.requests.get")
    def test_returns_none_when_key_missing(self, mock_get):
        """Missing winprobability key in response."""
        mock_get.return_value = MagicMock(status_code=200)
        mock_get.return_value.json.return_value = MOCK_MISSING_KEY
        mock_get.return_value.raise_for_status = MagicMock()

        from scripts.fetch_espn_divergence import fetch_single_game_prob

        result = fetch_single_game_prob("401712993")
        assert result["espn_home_prob"] is None
        assert result["fetch_success"] is True

    @patch("scripts.fetch_espn_divergence.requests.get")
    def test_returns_failure_on_api_error(self, mock_get):
        """Network errors should be caught gracefully."""
        import requests as req

        mock_get.side_effect = req.RequestException("timeout")

        from scripts.fetch_espn_divergence import fetch_single_game_prob

        result = fetch_single_game_prob("401712993")
        assert result["fetch_success"] is False
        assert result["espn_home_prob"] is None


# ── Checkpoint ──────────────────────────────────────────────────────


class TestCheckpoint:
    """Tests for checkpoint save/load."""

    def test_save_and_load_roundtrip(self, tmp_path):
        """Checkpoint file should roundtrip correctly."""
        from scripts.fetch_espn_divergence import load_checkpoint, save_checkpoint

        cp = tmp_path / "checkpoint.txt"
        save_checkpoint(cp, {"abc", "def", "ghi"})
        loaded = load_checkpoint(cp)
        assert loaded == {"abc", "def", "ghi"}

    def test_load_nonexistent_returns_empty(self, tmp_path):
        """Missing checkpoint file should return empty set."""
        from scripts.fetch_espn_divergence import load_checkpoint

        assert load_checkpoint(tmp_path / "nope.txt") == set()


# ── load_backtest_game_ids ──────────────────────────────────────────


class TestLoadBacktestGameIds:
    """Tests for loading game IDs from backtest parquets."""

    def test_loads_unique_ids_with_season(self, tmp_path):
        """Should deduplicate game_ids across seasons."""
        from scripts.fetch_espn_divergence import load_backtest_game_ids

        df1 = pd.DataFrame({"game_id": ["A", "B", "C"], "model_prob": [0.5] * 3})
        df2 = pd.DataFrame({"game_id": ["B", "D"], "model_prob": [0.5] * 2})
        df1.to_parquet(tmp_path / "ncaab_elo_backtest_2023.parquet")
        df2.to_parquet(tmp_path / "ncaab_elo_backtest_2024.parquet")

        result = load_backtest_game_ids(tmp_path, [2023, 2024])
        ids = {r["game_id"] for r in result}
        assert ids == {"A", "B", "C", "D"}

    def test_returns_empty_on_missing_dir(self, tmp_path):
        """Missing directory should not crash."""
        from scripts.fetch_espn_divergence import load_backtest_game_ids

        result = load_backtest_game_ids(tmp_path / "nope", [2023])
        assert result == []
