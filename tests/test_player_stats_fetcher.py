"""Tests for player stats fetcher pipeline.

Tests cover:
- API response parsing (Parquet format, mocked)
- Team rotation extraction
- Season caching to parquet
- Error handling (no API key, empty data)
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# --- Fixtures ---

SAMPLE_PLAYER_DATA = [
    # Houston rotation
    {
        "player": "LJ Cryer",
        "pos": "Combo G",
        "team": "Houston",
        "conf": "Big 12",
        "g": 30.0,
        "min": 981.0,
        "mpg": 32.7,
        "usg": 22.3,
        "dbpm": 2.976,
        "obpm": 3.1,
        "bpm": 6.1,
        "spg": 1.2,
        "bpg": 0.1,
        "stl": 2.5,
        "blk": 0.5,
        "stops": 120.0,
        "drtg": 95.0,
        "adj_de": 92.0,
        "year": 2025,
    },
    {
        "player": "J'Wan Roberts",
        "pos": "C",
        "team": "Houston",
        "conf": "Big 12",
        "g": 30.0,
        "min": 909.0,
        "mpg": 30.3,
        "usg": 21.7,
        "dbpm": 3.987,
        "obpm": 1.5,
        "bpm": 5.5,
        "spg": 0.8,
        "bpg": 1.5,
        "stl": 1.8,
        "blk": 3.2,
        "stops": 140.0,
        "drtg": 90.0,
        "adj_de": 88.0,
        "year": 2025,
    },
    {
        "player": "Milos Uzan",
        "pos": "Scoring PG",
        "team": "Houston",
        "conf": "Big 12",
        "g": 30.0,
        "min": 945.0,
        "mpg": 31.5,
        "usg": 20.1,
        "dbpm": 3.577,
        "obpm": 2.0,
        "bpm": 5.6,
        "spg": 1.5,
        "bpg": 0.2,
        "stl": 3.0,
        "blk": 0.8,
        "stops": 130.0,
        "drtg": 93.0,
        "adj_de": 90.0,
        "year": 2025,
    },
    {
        "player": "Emanuel Sharp",
        "pos": "Combo G",
        "team": "Houston",
        "conf": "Big 12",
        "g": 30.0,
        "min": 819.0,
        "mpg": 27.3,
        "usg": 20.2,
        "dbpm": 4.858,
        "obpm": 1.8,
        "bpm": 6.7,
        "spg": 0.9,
        "bpg": 0.3,
        "stl": 2.0,
        "blk": 0.9,
        "stops": 115.0,
        "drtg": 92.0,
        "adj_de": 89.0,
        "year": 2025,
    },
    {
        "player": "Mylik Wilson",
        "pos": "Wing G",
        "team": "Houston",
        "conf": "Big 12",
        "g": 28.0,
        "min": 490.0,
        "mpg": 17.5,
        "usg": 20.2,
        "dbpm": 6.422,
        "obpm": 0.5,
        "bpm": 6.9,
        "spg": 1.0,
        "bpg": 0.4,
        "stl": 2.8,
        "blk": 1.2,
        "stops": 95.0,
        "drtg": 88.0,
        "adj_de": 86.0,
        "year": 2025,
    },
    # Duke rotation (2 players for minimal testing)
    {
        "player": "Cooper Flagg",
        "pos": "Stretch 4",
        "team": "Duke",
        "conf": "ACC",
        "g": 30.0,
        "min": 1020.0,
        "mpg": 34.0,
        "usg": 28.5,
        "dbpm": 5.2,
        "obpm": 8.0,
        "bpm": 13.2,
        "spg": 1.8,
        "bpg": 1.5,
        "stl": 3.5,
        "blk": 3.0,
        "stops": 150.0,
        "drtg": 88.0,
        "adj_de": 85.0,
        "year": 2025,
    },
    {
        "player": "Tyrese Proctor",
        "pos": "Combo G",
        "team": "Duke",
        "conf": "ACC",
        "g": 30.0,
        "min": 900.0,
        "mpg": 30.0,
        "usg": 18.0,
        "dbpm": 2.1,
        "obpm": 2.5,
        "bpm": 4.6,
        "spg": 1.0,
        "bpg": 0.1,
        "stl": 2.0,
        "blk": 0.3,
        "stops": 100.0,
        "drtg": 94.0,
        "adj_de": 91.0,
        "year": 2025,
    },
    {
        "player": "Kon Knueppel",
        "pos": "Wing G",
        "team": "Duke",
        "conf": "ACC",
        "g": 30.0,
        "min": 840.0,
        "mpg": 28.0,
        "usg": 19.5,
        "dbpm": 1.5,
        "obpm": 3.0,
        "bpm": 4.5,
        "spg": 0.7,
        "bpg": 0.2,
        "stl": 1.5,
        "blk": 0.5,
        "stops": 90.0,
        "drtg": 96.0,
        "adj_de": 93.0,
        "year": 2025,
    },
]


@pytest.fixture
def sample_player_df():
    """Create a sample player DataFrame."""
    return pd.DataFrame(SAMPLE_PLAYER_DATA)


@pytest.fixture
def sample_parquet_bytes(sample_player_df):
    """Create Parquet bytes mimicking API response."""
    buf = io.BytesIO()
    sample_player_df.to_parquet(buf, index=False)
    return buf.getvalue()


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache = tmp_path / "barttorvik"
    cache.mkdir()
    return cache


# --- Test: Response Parsing ---


class TestParsePlayerResponse:
    """Test parsing raw Parquet response into DataFrame."""

    def test_parse_valid_parquet(self, sample_parquet_bytes):
        from pipelines.player_stats_fetcher import parse_player_response

        df = parse_player_response(sample_parquet_bytes, season=2025)
        assert len(df) == 8
        assert "player" in df.columns
        assert "usg" in df.columns
        assert "dbpm" in df.columns
        assert "pos" in df.columns
        assert "mpg" in df.columns

    def test_parse_empty_bytes_returns_empty(self):
        from pipelines.player_stats_fetcher import parse_player_response

        df = parse_player_response(b"", season=2025)
        assert len(df) == 0

    def test_parse_coerces_numeric_columns(self, sample_parquet_bytes):
        from pipelines.player_stats_fetcher import parse_player_response

        df = parse_player_response(sample_parquet_bytes, season=2025)
        assert df["usg"].dtype in (np.float64, np.float32)
        assert df["dbpm"].dtype in (np.float64, np.float32)
        assert df["mpg"].dtype in (np.float64, np.float32)

    def test_parse_sorted_by_team_and_usg(self, sample_parquet_bytes):
        from pipelines.player_stats_fetcher import parse_player_response

        df = parse_player_response(sample_parquet_bytes, season=2025)
        # Duke should come before Houston (alphabetical)
        duke_idx = df[df["team"] == "Duke"].index[0]
        houston_idx = df[df["team"] == "Houston"].index[0]
        assert duke_idx < houston_idx


# --- Test: Team Rotation ---


class TestTeamRotation:
    """Test extracting a team's rotation players."""

    def test_get_houston_rotation(self, sample_player_df):
        from pipelines.player_stats_fetcher import get_team_rotation

        rotation = get_team_rotation(sample_player_df, "Houston", rotation_size=8)
        assert len(rotation) == 5  # Only 5 Houston players in sample
        # Sorted by mpg descending
        assert rotation["mpg"].iloc[0] >= rotation["mpg"].iloc[-1]

    def test_rotation_size_limit(self, sample_player_df):
        from pipelines.player_stats_fetcher import get_team_rotation

        rotation = get_team_rotation(sample_player_df, "Houston", rotation_size=3)
        assert len(rotation) == 3

    def test_min_minutes_filter(self, sample_player_df):
        from pipelines.player_stats_fetcher import get_team_rotation

        rotation = get_team_rotation(sample_player_df, "Houston", rotation_size=8, min_minutes=25.0)
        assert all(rotation["mpg"] >= 25.0)

    def test_unknown_team_returns_empty(self, sample_player_df):
        from pipelines.player_stats_fetcher import get_team_rotation

        rotation = get_team_rotation(sample_player_df, "Nonexistent U")
        assert len(rotation) == 0

    def test_empty_df_returns_empty(self):
        from pipelines.player_stats_fetcher import get_team_rotation

        rotation = get_team_rotation(pd.DataFrame(), "Houston")
        assert len(rotation) == 0


# --- Test: Cache Management ---


class TestPlayerCache:
    """Test saving/loading player stats to parquet cache."""

    def test_save_and_load(self, sample_player_df, tmp_cache_dir):
        from pipelines.player_stats_fetcher import (
            load_cached_players,
            save_player_cache,
        )

        save_player_cache(sample_player_df, season=2025, cache_dir=tmp_cache_dir)
        loaded = load_cached_players(season=2025, cache_dir=tmp_cache_dir)
        assert loaded is not None
        assert len(loaded) == 8

    def test_load_missing_returns_none(self, tmp_cache_dir):
        from pipelines.player_stats_fetcher import load_cached_players

        result = load_cached_players(season=2099, cache_dir=tmp_cache_dir)
        assert result is None


# --- Test: Fetcher Class ---


class TestPlayerStatsFetcher:
    """Test the main fetcher class."""

    @patch("pipelines.player_stats_fetcher.requests.Session")
    def test_fetch_season_success(self, mock_session_cls, sample_parquet_bytes, tmp_cache_dir):
        from pipelines.player_stats_fetcher import PlayerStatsFetcher

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = sample_parquet_bytes
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        fetcher = PlayerStatsFetcher(api_key="test_key", cache_dir=tmp_cache_dir)
        df = fetcher.fetch_season(2025, use_cache=False)
        assert df is not None
        assert len(df) == 8

    @patch("pipelines.player_stats_fetcher.requests.Session")
    def test_fetch_season_401_raises(self, mock_session_cls, tmp_cache_dir):
        from pipelines.player_stats_fetcher import PlayerStatsFetcher

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        fetcher = PlayerStatsFetcher(api_key="bad_key", cache_dir=tmp_cache_dir)
        with pytest.raises(Exception):
            fetcher.fetch_season(2025, use_cache=False)

    def test_no_api_key_raises(self):
        from pipelines.player_stats_fetcher import PlayerStatsFetcher

        with pytest.raises(ValueError, match="API key"):
            PlayerStatsFetcher(api_key="")

    @patch("pipelines.player_stats_fetcher.requests.Session")
    def test_fetch_uses_cache_when_available(
        self, mock_session_cls, sample_player_df, tmp_cache_dir
    ):
        from pipelines.player_stats_fetcher import (
            PlayerStatsFetcher,
            save_player_cache,
        )

        # Pre-populate cache
        save_player_cache(sample_player_df, season=2025, cache_dir=tmp_cache_dir)

        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        fetcher = PlayerStatsFetcher(api_key="test_key", cache_dir=tmp_cache_dir)
        df = fetcher.fetch_season(2025, use_cache=True)

        # Should NOT have called the API
        mock_session.get.assert_not_called()
        assert len(df) == 8
