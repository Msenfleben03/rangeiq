"""Tests for Barttorvik T-Rank fetcher pipeline.

Tests cover:
- API response parsing (Parquet format, mocked)
- Point-in-time rating lookup
- Season caching to parquet
- Team name matching
- Matchup differentials
- Error handling (no API key, network errors, bad data)
"""

from __future__ import annotations

import io
from datetime import date
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# --- Fixtures ---

SAMPLE_RATINGS_DATA = [
    {
        "rank": 1,
        "team": "Houston",
        "conf": "Big 12",
        "barthag": 0.9744,
        "adj_o": 120.5,
        "adj_d": 85.3,
        "adj_tempo": 67.2,
        "wab": 9.8,
        "year": 2025,
        "date": "2025-01-15",
    },
    {
        "rank": 2,
        "team": "Duke",
        "conf": "ACC",
        "barthag": 0.9650,
        "adj_o": 122.1,
        "adj_d": 88.0,
        "adj_tempo": 70.5,
        "wab": 8.5,
        "year": 2025,
        "date": "2025-01-15",
    },
    {
        "rank": 1,
        "team": "Houston",
        "conf": "Big 12",
        "barthag": 0.9750,
        "adj_o": 121.0,
        "adj_d": 85.0,
        "adj_tempo": 67.5,
        "wab": 10.0,
        "year": 2025,
        "date": "2025-01-20",
    },
    {
        "rank": 3,
        "team": "Duke",
        "conf": "ACC",
        "barthag": 0.9600,
        "adj_o": 121.5,
        "adj_d": 89.0,
        "adj_tempo": 70.2,
        "wab": 8.0,
        "year": 2025,
        "date": "2025-01-20",
    },
]


@pytest.fixture
def sample_ratings_df():
    """Create a sample ratings DataFrame matching API structure."""
    df = pd.DataFrame(SAMPLE_RATINGS_DATA)
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture
def sample_parquet_bytes(sample_ratings_df):
    """Create Parquet bytes mimicking API response."""
    buf = io.BytesIO()
    sample_ratings_df.to_parquet(buf, index=False)
    return buf.getvalue()


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache = tmp_path / "barttorvik"
    cache.mkdir()
    return cache


# --- Test: API Response Parsing ---


class TestParseParquetResponse:
    """Test parsing raw Parquet response bytes into DataFrame."""

    def test_parse_valid_parquet(self, sample_parquet_bytes):
        from pipelines.barttorvik_fetcher import parse_ratings_response

        df = parse_ratings_response(sample_parquet_bytes, season=2025)
        assert len(df) == 4
        assert "team" in df.columns
        assert "adj_o" in df.columns
        assert "adj_d" in df.columns
        assert "adj_tempo" in df.columns
        assert "barthag" in df.columns
        assert "date" in df.columns

    def test_parse_empty_bytes_returns_empty(self):
        from pipelines.barttorvik_fetcher import parse_ratings_response

        df = parse_ratings_response(b"", season=2025)
        assert len(df) == 0

    def test_parse_coerces_date_to_datetime(self, sample_parquet_bytes):
        from pipelines.barttorvik_fetcher import parse_ratings_response

        df = parse_ratings_response(sample_parquet_bytes, season=2025)
        assert pd.api.types.is_datetime64_any_dtype(df["date"])

    def test_parse_coerces_numeric_columns(self, sample_parquet_bytes):
        from pipelines.barttorvik_fetcher import parse_ratings_response

        df = parse_ratings_response(sample_parquet_bytes, season=2025)
        assert df["adj_o"].dtype in (np.float64, np.float32)
        assert df["adj_d"].dtype in (np.float64, np.float32)
        assert df["barthag"].dtype in (np.float64, np.float32)


# --- Test: Point-in-Time Lookup ---


class TestPointInTimeLookup:
    """Test looking up a team's ratings on or before a specific date."""

    def test_lookup_exact_date(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import lookup_team_ratings

        result = lookup_team_ratings(sample_ratings_df, team="Houston", game_date=date(2025, 1, 15))
        assert result is not None
        assert result["adj_o"] == pytest.approx(120.5)
        assert result["barthag"] == pytest.approx(0.9744)

    def test_lookup_between_dates_uses_earlier(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import lookup_team_ratings

        # Game on Jan 18 -- should use Jan 15 ratings (not Jan 20)
        result = lookup_team_ratings(sample_ratings_df, team="Houston", game_date=date(2025, 1, 18))
        assert result is not None
        assert result["adj_o"] == pytest.approx(120.5)

    def test_lookup_after_latest_uses_latest(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import lookup_team_ratings

        result = lookup_team_ratings(sample_ratings_df, team="Houston", game_date=date(2025, 2, 1))
        assert result is not None
        assert result["adj_o"] == pytest.approx(121.0)  # Jan 20 value

    def test_lookup_before_earliest_returns_none(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import lookup_team_ratings

        result = lookup_team_ratings(sample_ratings_df, team="Houston", game_date=date(2024, 10, 1))
        assert result is None

    def test_lookup_unknown_team_returns_none(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import lookup_team_ratings

        result = lookup_team_ratings(
            sample_ratings_df, team="Nonexistent U", game_date=date(2025, 1, 15)
        )
        assert result is None


# --- Test: Cache Management ---


class TestCacheManagement:
    """Test saving/loading ratings to parquet cache."""

    def test_save_and_load_season(self, sample_ratings_df, tmp_cache_dir):
        from pipelines.barttorvik_fetcher import (
            load_cached_season,
            save_season_cache,
        )

        save_season_cache(sample_ratings_df, season=2025, cache_dir=tmp_cache_dir)
        loaded = load_cached_season(season=2025, cache_dir=tmp_cache_dir)
        assert loaded is not None
        assert len(loaded) == 4

    def test_load_missing_cache_returns_none(self, tmp_cache_dir):
        from pipelines.barttorvik_fetcher import load_cached_season

        result = load_cached_season(season=2099, cache_dir=tmp_cache_dir)
        assert result is None


# --- Test: Matchup Ratings Extraction ---


class TestMatchupRatings:
    """Test extracting Barttorvik differentials for a matchup."""

    def test_compute_matchup_differentials(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import compute_barttorvik_differentials

        diffs = compute_barttorvik_differentials(
            ratings_df=sample_ratings_df,
            home_team="Houston",
            away_team="Duke",
            game_date=date(2025, 1, 15),
        )
        assert diffs is not None
        # Houston AdjO=120.5, Duke AdjO=122.1 -> diff = -1.6
        assert "adj_o_diff" in diffs
        assert diffs["adj_o_diff"] == pytest.approx(120.5 - 122.1)
        # Houston AdjD=85.3, Duke AdjD=88.0 -> diff = -2.7 (lower = better)
        assert "adj_d_diff" in diffs
        assert diffs["adj_d_diff"] == pytest.approx(85.3 - 88.0)
        assert "barthag_diff" in diffs
        assert "adj_tempo_diff" in diffs

    def test_differentials_missing_one_team_returns_none(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import compute_barttorvik_differentials

        diffs = compute_barttorvik_differentials(
            ratings_df=sample_ratings_df,
            home_team="Houston",
            away_team="Nonexistent U",
            game_date=date(2025, 1, 15),
        )
        assert diffs is None


# --- Test: Fetcher Class ---


class TestBarttovikFetcher:
    """Test the main fetcher class."""

    @patch("pipelines.barttorvik_fetcher.requests.Session")
    def test_fetch_season_success(self, mock_session_cls, sample_parquet_bytes, tmp_cache_dir):
        from pipelines.barttorvik_fetcher import BarttovikFetcher

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = sample_parquet_bytes
        mock_response.headers = {"Content-Type": "application/octet-stream"}
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        fetcher = BarttovikFetcher(api_key="test_key", cache_dir=tmp_cache_dir)
        df = fetcher.fetch_season(2025, use_cache=False)
        assert df is not None
        assert len(df) == 4

    @patch("pipelines.barttorvik_fetcher.requests.Session")
    def test_fetch_season_401_raises(self, mock_session_cls, tmp_cache_dir):
        from pipelines.barttorvik_fetcher import BarttovikFetcher

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        fetcher = BarttovikFetcher(api_key="bad_key", cache_dir=tmp_cache_dir)
        with pytest.raises(Exception):
            fetcher.fetch_season(2025, use_cache=False)

    def test_fetcher_no_api_key_raises(self):
        from pipelines.barttorvik_fetcher import BarttovikFetcher

        with pytest.raises(ValueError, match="API key"):
            BarttovikFetcher(api_key="")


# --- Test: Efficiency Feature Computation ---


class TestEfficiencyFeatures:
    """Test deriving betting features from raw Barttorvik ratings."""

    def test_net_rating_computed(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import compute_barttorvik_differentials

        diffs = compute_barttorvik_differentials(
            ratings_df=sample_ratings_df,
            home_team="Houston",
            away_team="Duke",
            game_date=date(2025, 1, 15),
        )
        # Net rating = AdjO - AdjD
        # Houston: 120.5 - 85.3 = 35.2
        # Duke: 122.1 - 88.0 = 34.1
        # Diff = 35.2 - 34.1 = 1.1
        assert "net_rating_diff" in diffs
        assert diffs["net_rating_diff"] == pytest.approx(1.1, abs=0.01)

    def test_tempo_differential(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import compute_barttorvik_differentials

        diffs = compute_barttorvik_differentials(
            ratings_df=sample_ratings_df,
            home_team="Houston",
            away_team="Duke",
            game_date=date(2025, 1, 15),
        )
        # Houston tempo=67.2, Duke tempo=70.5
        assert "adj_tempo_diff" in diffs
        assert diffs["adj_tempo_diff"] == pytest.approx(67.2 - 70.5)
