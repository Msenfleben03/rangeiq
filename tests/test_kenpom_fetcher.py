"""Tests for KenPom efficiency rating fetcher pipeline.

Tests cover:
- DataFrame normalization (kenpompy format -> our standard format)
- Point-in-time rating lookup
- Matchup differential computation
- Team name mapping (Barttorvik <-> KenPom)
- Cache load/save round-trip
- Cache append idempotency
- Fetcher class (mocked kenpompy calls)
"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from pipelines.kenpom_fetcher import (
    KenPomFetcher,
    append_to_cache,
    compute_kenpom_differentials,
    load_cached_season,
    lookup_team_ratings,
    normalize_kenpom_df,
    save_season_cache,
)
from pipelines.team_name_mapping import (
    barttorvik_to_kenpom,
    kenpom_to_barttorvik,
)


# ---------------------------------------------------------------------------
# Fixtures — mimic kenpompy get_pomeroy_ratings output
# ---------------------------------------------------------------------------

SAMPLE_KENPOMPY_RAW = pd.DataFrame(
    {
        "Rk": ["1", "2", "3"],
        "Team": ["Michigan", "Duke", "Arizona"],
        "Conf": ["B10", "ACC", "B12"],
        "W-L": ["25-1", "24-2", "23-2"],
        "AdjEM": ["+39.45", "+36.62", "+35.69"],
        "AdjO": ["127.7", "126.2", "125.4"],
        "AdjO.Rank": ["1", "2", "3"],
        "AdjD": ["88.2", "89.5", "89.7"],
        "AdjD.Rank": ["1", "2", "3"],
        "AdjT": ["72.1", "65.6", "70.8"],
        "AdjT.Rank": ["10", "250", "26"],
        "Luck": ["+.042", "-.015", "+.028"],
        "Luck.Rank": ["50", "200", "100"],
        "SOS-AdjEM": ["+8.50", "+9.10", "+7.80"],
        "SOS-AdjEM.Rank": ["10", "5", "15"],
        "SOS-OppO": ["108.5", "109.1", "107.8"],
        "SOS-OppO.Rank": ["10", "5", "15"],
        "SOS-OppD": ["100.0", "100.0", "100.0"],
        "SOS-OppD.Rank": ["10", "5", "15"],
        "NCSOS-AdjEM": ["+5.00", "+4.50", "+6.20"],
        "NCSOS-AdjEM.Rank": ["20", "30", "10"],
        "Seed": ["1", "1", "2"],
    }
)


# ---------------------------------------------------------------------------
# Tests: DataFrame Normalization
# ---------------------------------------------------------------------------


class TestNormalizeKenpomDf:
    """Test normalize_kenpom_df."""

    def test_correct_columns(self):
        """Output contains all core columns plus preserved raw columns."""
        df = normalize_kenpom_df(SAMPLE_KENPOMPY_RAW, 2026)
        # Core columns that downstream consumers rely on
        core_expected = {
            "rank",
            "team",
            "conf",
            "adj_em",
            "adj_o",
            "adj_d",
            "adj_t",
            "sos_adj_em",
            "luck",
            "year",
            "date",
        }
        assert core_expected.issubset(set(df.columns))
        # All raw kenpompy columns should also be preserved (renamed to snake_case)
        raw_preserved = {
            "w_l",
            "adj_o_rk",
            "adj_d_rk",
            "adj_t_rk",
            "luck_rk",
            "sos_adj_em_rk",
            "sos_opp_o",
            "sos_opp_o_rk",
            "sos_opp_d",
            "sos_opp_d_rk",
            "ncsos_adj_em",
            "ncsos_adj_em_rk",
            "seed",
        }
        assert raw_preserved.issubset(set(df.columns))

    def test_correct_team_count(self):
        df = normalize_kenpom_df(SAMPLE_KENPOMPY_RAW, 2026)
        assert len(df) == 3

    def test_adj_em_parsed(self):
        """AdjEM with + prefix is parsed to float."""
        df = normalize_kenpom_df(SAMPLE_KENPOMPY_RAW, 2026)
        michigan = df[df["team"] == "Michigan"].iloc[0]
        assert michigan["adj_em"] == pytest.approx(39.45, abs=0.01)

    def test_adj_o_parsed(self):
        df = normalize_kenpom_df(SAMPLE_KENPOMPY_RAW, 2026)
        michigan = df[df["team"] == "Michigan"].iloc[0]
        assert michigan["adj_o"] == pytest.approx(127.7, abs=0.1)

    def test_adj_d_parsed(self):
        df = normalize_kenpom_df(SAMPLE_KENPOMPY_RAW, 2026)
        michigan = df[df["team"] == "Michigan"].iloc[0]
        assert michigan["adj_d"] == pytest.approx(88.2, abs=0.1)

    def test_adj_t_parsed(self):
        df = normalize_kenpom_df(SAMPLE_KENPOMPY_RAW, 2026)
        michigan = df[df["team"] == "Michigan"].iloc[0]
        assert michigan["adj_t"] == pytest.approx(72.1, abs=0.1)

    def test_sos_parsed(self):
        df = normalize_kenpom_df(SAMPLE_KENPOMPY_RAW, 2026)
        michigan = df[df["team"] == "Michigan"].iloc[0]
        assert michigan["sos_adj_em"] == pytest.approx(8.50, abs=0.01)

    def test_year_column(self):
        df = normalize_kenpom_df(SAMPLE_KENPOMPY_RAW, 2025)
        assert (df["year"] == 2025).all()

    def test_rank_is_integer(self):
        df = normalize_kenpom_df(SAMPLE_KENPOMPY_RAW, 2026)
        assert df["rank"].dtype.name == "Int64"

    def test_empty_input(self):
        df = normalize_kenpom_df(pd.DataFrame(), 2026)
        assert df.empty


# ---------------------------------------------------------------------------
# Tests: Point-in-Time Lookup
# ---------------------------------------------------------------------------


class TestLookupTeamRatings:
    """Test lookup_team_ratings."""

    @pytest.fixture()
    def sample_df(self):
        return pd.DataFrame(
            {
                "team": ["Houston", "Houston", "Duke", "Duke"],
                "adj_em": [35.0, 36.0, 33.0, 34.0],
                "adj_o": [125.0, 126.0, 124.0, 125.0],
                "adj_d": [90.0, 90.0, 91.0, 91.0],
                "adj_t": [63.0, 63.0, 66.0, 66.0],
                "sos_adj_em": [8.0, 8.5, 9.0, 9.5],
                "luck": [0.04, 0.03, -0.01, -0.02],
                "rank": [1, 1, 2, 2],
                "conf": ["B12", "B12", "ACC", "ACC"],
                "year": [2026, 2026, 2026, 2026],
                "date": pd.to_datetime(["2026-01-15", "2026-02-01", "2026-01-15", "2026-02-01"]),
            }
        )

    def test_returns_most_recent_before_date(self, sample_df):
        result = lookup_team_ratings(sample_df, "Houston", date(2026, 1, 20))
        assert result is not None
        assert result["adj_em"] == pytest.approx(35.0)

    def test_returns_exact_date(self, sample_df):
        result = lookup_team_ratings(sample_df, "Houston", date(2026, 2, 1))
        assert result is not None
        assert result["adj_em"] == pytest.approx(36.0)

    def test_returns_none_before_any_data(self, sample_df):
        result = lookup_team_ratings(sample_df, "Houston", date(2026, 1, 1))
        assert result is None

    def test_returns_none_for_unknown_team(self, sample_df):
        result = lookup_team_ratings(sample_df, "Unknown", date(2026, 2, 1))
        assert result is None

    def test_empty_df_returns_none(self):
        result = lookup_team_ratings(pd.DataFrame(), "Houston", date(2026, 2, 1))
        assert result is None


# ---------------------------------------------------------------------------
# Tests: Differentials
# ---------------------------------------------------------------------------


class TestComputeKenpomDifferentials:
    """Test compute_kenpom_differentials."""

    @pytest.fixture()
    def sample_df(self):
        return pd.DataFrame(
            {
                "team": ["Houston", "Duke"],
                "adj_em": [36.0, 34.0],
                "adj_o": [126.0, 125.0],
                "adj_d": [90.0, 91.0],
                "adj_t": [63.0, 66.0],
                "sos_adj_em": [8.5, 9.5],
                "luck": [0.03, -0.02],
                "rank": [1, 2],
                "conf": ["B12", "ACC"],
                "year": [2026, 2026],
                "date": pd.to_datetime(["2026-02-01", "2026-02-01"]),
            }
        )

    def test_adj_em_diff(self, sample_df):
        diffs = compute_kenpom_differentials(sample_df, "Houston", "Duke", date(2026, 2, 1))
        assert diffs is not None
        assert diffs["adj_em_diff"] == pytest.approx(2.0)

    def test_adj_o_diff(self, sample_df):
        diffs = compute_kenpom_differentials(sample_df, "Houston", "Duke", date(2026, 2, 1))
        assert diffs["adj_o_diff"] == pytest.approx(1.0)

    def test_returns_none_when_team_missing(self, sample_df):
        diffs = compute_kenpom_differentials(sample_df, "Houston", "Unknown", date(2026, 2, 1))
        assert diffs is None


# ---------------------------------------------------------------------------
# Tests: Team Name Mapping
# ---------------------------------------------------------------------------


class TestKenpomTeamMapping:
    """Test Barttorvik <-> KenPom name conversion."""

    def test_barttorvik_to_kenpom_override(self):
        assert barttorvik_to_kenpom("McNeese St.") == "McNeese"

    def test_barttorvik_to_kenpom_passthrough(self):
        assert barttorvik_to_kenpom("Houston") == "Houston"

    def test_kenpom_to_barttorvik_override(self):
        assert kenpom_to_barttorvik("CSUN") == "Cal St. Northridge"

    def test_kenpom_to_barttorvik_passthrough(self):
        assert kenpom_to_barttorvik("Duke") == "Duke"

    def test_all_overrides_are_bidirectional(self):
        """Every override has a working reverse mapping."""
        from pipelines.team_name_mapping import (
            BARTTORVIK_TO_KENPOM_OVERRIDES,
        )

        for bart, kp in BARTTORVIK_TO_KENPOM_OVERRIDES.items():
            assert kenpom_to_barttorvik(kp) == bart
            assert barttorvik_to_kenpom(bart) == kp


# ---------------------------------------------------------------------------
# Tests: Cache Management
# ---------------------------------------------------------------------------


class TestCacheManagement:
    """Test save/load/append cache operations."""

    def _make_df(self, date_str: str = "2026-02-17"):
        return pd.DataFrame(
            {
                "rank": [1, 2],
                "team": ["Houston", "Duke"],
                "conf": ["B12", "ACC"],
                "adj_em": [36.0, 34.0],
                "adj_o": [126.0, 125.0],
                "adj_d": [90.0, 91.0],
                "adj_t": [63.0, 66.0],
                "sos_adj_em": [8.5, 9.5],
                "luck": [0.03, -0.02],
                "year": [2026, 2026],
                "date": pd.to_datetime([date_str, date_str]),
            }
        )

    def test_save_and_load_round_trip(self, tmp_path):
        df = self._make_df()
        save_season_cache(df, 2026, tmp_path)
        loaded = load_cached_season(2026, tmp_path)
        assert loaded is not None
        assert len(loaded) == 2
        assert set(loaded["team"]) == {"Houston", "Duke"}

    def test_load_missing_returns_none(self, tmp_path):
        assert load_cached_season(2026, tmp_path) is None

    def test_append_is_idempotent(self, tmp_path):
        df = self._make_df()
        append_to_cache(df, 2026, tmp_path)
        append_to_cache(df, 2026, tmp_path)
        result = pd.read_parquet(tmp_path / "kenpom_ratings_2026.parquet")
        assert len(result) == 2  # No duplicates

    def test_append_adds_new_dates(self, tmp_path):
        df1 = self._make_df("2026-02-17")
        df2 = self._make_df("2026-02-18")
        append_to_cache(df1, 2026, tmp_path)
        append_to_cache(df2, 2026, tmp_path)
        result = pd.read_parquet(tmp_path / "kenpom_ratings_2026.parquet")
        assert len(result) == 4  # 2 teams × 2 dates


# ---------------------------------------------------------------------------
# Tests: KenPomFetcher Class
# ---------------------------------------------------------------------------


class TestKenPomFetcher:
    """Test KenPomFetcher with mocked kenpompy."""

    @patch("pipelines.kenpom_fetcher.KenPomFetcher._login")
    @patch("kenpompy.misc.get_pomeroy_ratings")
    def test_fetch_season_returns_normalized(self, mock_get, mock_login, tmp_path):
        mock_get.return_value = SAMPLE_KENPOMPY_RAW
        fetcher = KenPomFetcher("test@test.com", "pass", cache_dir=tmp_path)
        fetcher._browser = MagicMock()  # skip actual login

        df = fetcher.fetch_season_ratings(2026, use_cache=False)
        assert len(df) == 3
        assert "adj_em" in df.columns

    @patch("pipelines.kenpom_fetcher.KenPomFetcher._login")
    @patch("kenpompy.misc.get_pomeroy_ratings")
    def test_fetch_uses_cache(self, mock_get, mock_login, tmp_path):
        """Second call uses cache, doesn't hit kenpompy."""
        mock_get.return_value = SAMPLE_KENPOMPY_RAW
        fetcher = KenPomFetcher("test@test.com", "pass", cache_dir=tmp_path)
        fetcher._browser = MagicMock()

        # First call
        fetcher.fetch_season_ratings(2026, use_cache=False)
        # Second call should use cache
        df = fetcher.fetch_season_ratings(2026, use_cache=True)
        assert len(df) == 3
        # get_pomeroy_ratings should only be called once (first fetch)
        assert mock_get.call_count == 1
