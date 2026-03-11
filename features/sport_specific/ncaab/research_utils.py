"""Research utilities for tournament feature engineering.

Shared data loading, COVID gap filtering, and point-in-time Barttorvik
lookups used by both Late-Season Losses and Efficiency Trajectory research.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "ncaab"
BART_DIR = PROJECT_ROOT / "data" / "external" / "barttorvik"

# 2020 excluded (cancelled tournament). 2021 included with COVID flag.
VALID_SEASONS: tuple[int, ...] = (2021, 2022, 2023, 2024, 2025)


def load_season_games(season: int) -> pd.DataFrame:
    """Load game data for a season, sorted by date with point_diff added."""
    path = RAW_DIR / f"ncaab_games_{season}.parquet"
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["point_diff"] = df["points_for"] - df["points_against"]
    return df


def load_barttorvik_snapshots(season: int) -> pd.DataFrame:
    """Load Barttorvik point-in-time snapshots for a season."""
    path = BART_DIR / f"barttorvik_ratings_{season}.parquet"
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["team", "date"]).reset_index(drop=True)


def filter_covid_gaps(
    team_games: pd.DataFrame,
    max_gap_days: int = 10,
) -> pd.DataFrame:
    """Add covid_gap column flagging games after large schedule gaps.

    A game is flagged if the gap from the previous game for the same team
    exceeds max_gap_days. Flagged games are excluded from rolling windows.
    """
    result = team_games.copy()
    result["covid_gap"] = False
    dates = pd.to_datetime(result["date"])
    gap = dates.diff()
    result.loc[gap.dt.days > max_gap_days, "covid_gap"] = True
    return result


def pit_opponent_barthag(
    bart_df: pd.DataFrame,
    opponent: str,
    game_date: pd.Timestamp,
) -> float:
    """Get opponent's barthag from most recent snapshot strictly before game_date.

    Returns np.nan if no data available.
    """
    mask = (bart_df["team"] == opponent) & (bart_df["date"] < game_date)
    filtered = bart_df.loc[mask]
    if filtered.empty:
        return np.nan
    return float(filtered.sort_values("date").iloc[-1]["barthag"])
