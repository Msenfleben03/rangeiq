"""Tests for research utility functions."""

import numpy as np
import pandas as pd
import pytest

from features.sport_specific.ncaab.research_utils import (
    VALID_SEASONS,
    filter_covid_gaps,
    load_barttorvik_snapshots,
    load_season_games,
    pit_opponent_barthag,
)


class TestLoadSeasonGames:
    def test_loads_parquet_and_adds_point_diff(self):
        df = load_season_games(2025)
        assert "point_diff" in df.columns
        assert (df["point_diff"] == df["points_for"] - df["points_against"]).all()

    def test_excludes_2020(self):
        assert 2020 not in VALID_SEASONS

    def test_sorts_by_date(self):
        df = load_season_games(2025)
        dates = pd.to_datetime(df["date"])
        assert dates.is_monotonic_increasing


class TestLoadBarttovikSnapshots:
    def test_loads_and_sorts(self):
        df = load_barttorvik_snapshots(2025)
        assert "date" in df.columns
        assert "team" in df.columns
        assert len(df) > 0


class TestFilterCovidGaps:
    def test_flags_large_gaps(self):
        dates = pd.to_datetime(
            [
                "2021-01-01",
                "2021-01-03",
                "2021-01-20",
                "2021-01-22",
            ]
        )
        df = pd.DataFrame(
            {
                "date": dates,
                "team_id": ["A"] * 4,
                "result": ["W", "L", "W", "L"],
            }
        )
        result = filter_covid_gaps(df, max_gap_days=10)
        assert bool(result["covid_gap"].iloc[2]) is True

    def test_no_gaps_returns_all_false(self):
        dates = pd.to_datetime(["2022-01-01", "2022-01-03", "2022-01-06"])
        df = pd.DataFrame(
            {
                "date": dates,
                "team_id": ["A"] * 3,
                "result": ["W", "L", "W"],
            }
        )
        result = filter_covid_gaps(df, max_gap_days=10)
        assert not result["covid_gap"].any()


class TestPitOpponentBarthag:
    def test_returns_barthag_before_game_date(self):
        bart_df = pd.DataFrame(
            {
                "team": ["OPP", "OPP", "OPP"],
                "date": pd.to_datetime(["2025-01-01", "2025-01-05", "2025-01-10"]),
                "barthag": [0.8, 0.85, 0.9],
            }
        )
        result = pit_opponent_barthag(bart_df, "OPP", pd.Timestamp("2025-01-07"))
        assert result == pytest.approx(0.85)

    def test_returns_nan_if_no_data(self):
        bart_df = pd.DataFrame(
            {
                "team": ["OTHER"],
                "date": pd.to_datetime(["2025-01-01"]),
                "barthag": [0.5],
            }
        )
        result = pit_opponent_barthag(bart_df, "OPP", pd.Timestamp("2025-01-07"))
        assert np.isnan(result)

    def test_strict_less_than(self):
        bart_df = pd.DataFrame(
            {
                "team": ["OPP", "OPP"],
                "date": pd.to_datetime(["2025-01-05", "2025-01-10"]),
                "barthag": [0.85, 0.9],
            }
        )
        result = pit_opponent_barthag(bart_df, "OPP", pd.Timestamp("2025-01-10"))
        assert result == pytest.approx(0.85)
