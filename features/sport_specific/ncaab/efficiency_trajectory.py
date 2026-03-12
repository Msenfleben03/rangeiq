"""Efficiency Trajectory Features from Barttorvik Snapshots.

Computes 6 trajectory features from point-in-time Barttorvik rating snapshots:
1. adj_o_slope_10s   — OLS slope of offensive efficiency (last 10 snapshots)
2. adj_d_slope_10s   — OLS slope of defensive efficiency, sign-flipped
3. net_efficiency_slope_10s — OLS slope of (adj_o - adj_d) net efficiency
4. barthag_delta_10s — Simple difference in barthag vs 10 snapshots ago
5. barthag_delta_20s — Simple difference in barthag vs 20 snapshots ago
6. rank_change_20s   — Rank improvement over 20 snapshots (positive = improving)

All features use snapshot-count windows (not calendar days).
OLS slopes require a minimum of MIN_SLOPE_POINTS data points.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import linregress

# Minimum data points required for a valid OLS slope
MIN_SLOPE_POINTS = 5


def compute_ols_slope(
    snapshots: pd.DataFrame,
    column: str,
    n_snapshots: int,
    flip_sign: bool | None = None,
) -> pd.DataFrame:
    """Compute rolling OLS slope of a column over the last n snapshots.

    For each row i, takes values[max(0, i-n+1):i+1] and fits a linear
    regression if the window has >= MIN_SLOPE_POINTS data points.

    Args:
        snapshots: Single-team Barttorvik snapshots sorted by date.
        column: Column name to compute slope for (e.g., 'adj_o').
        n_snapshots: Window size in number of snapshots.
        flip_sign: If True, multiply slope by -1. Useful for adj_d where
            lower values are better. Defaults to None (no flip).

    Returns:
        DataFrame with a single column '{column}_slope_{n}s'.
    """
    col_name = f"{column}_slope_{n_snapshots}s"
    values = snapshots[column].values
    slopes = np.full(len(values), np.nan)

    for i in range(len(values)):
        start = max(0, i - n_snapshots + 1)
        window = values[start : i + 1]
        if len(window) < MIN_SLOPE_POINTS:
            continue
        x = np.arange(len(window))
        slope = linregress(x, window).slope
        if flip_sign:
            slope = -slope
        slopes[i] = slope

    return pd.DataFrame({col_name: slopes}, index=snapshots.index)


def compute_net_efficiency_slope(
    snapshots: pd.DataFrame,
    n_snapshots: int,
) -> pd.DataFrame:
    """Compute OLS slope of net efficiency (adj_o - adj_d) over n snapshots.

    Computed on the net series directly, NOT as adj_o_slope - adj_d_slope.

    Args:
        snapshots: Single-team Barttorvik snapshots sorted by date.
        n_snapshots: Window size in number of snapshots.

    Returns:
        DataFrame with column 'net_efficiency_slope_{n}s'.
    """
    col_name = f"net_efficiency_slope_{n_snapshots}s"
    net = (snapshots["adj_o"] - snapshots["adj_d"]).values
    slopes = np.full(len(net), np.nan)

    for i in range(len(net)):
        start = max(0, i - n_snapshots + 1)
        window = net[start : i + 1]
        if len(window) < MIN_SLOPE_POINTS:
            continue
        x = np.arange(len(window))
        slopes[i] = linregress(x, window).slope

    return pd.DataFrame({col_name: slopes}, index=snapshots.index)


def compute_barthag_delta(
    snapshots: pd.DataFrame,
    n_snapshots: int,
) -> pd.DataFrame:
    """Compute simple difference in barthag vs n snapshots ago.

    delta = barthag[current] - barthag[n snapshots ago]

    Args:
        snapshots: Single-team Barttorvik snapshots sorted by date.
        n_snapshots: Number of snapshots to look back.

    Returns:
        DataFrame with column 'barthag_delta_{n}s'.
    """
    col_name = f"barthag_delta_{n_snapshots}s"
    values = snapshots["barthag"].values
    deltas = np.full(len(values), np.nan)

    for i in range(len(values)):
        if i >= n_snapshots:
            deltas[i] = values[i] - values[i - n_snapshots]

    return pd.DataFrame({col_name: deltas}, index=snapshots.index)


def compute_rank_change(
    snapshots: pd.DataFrame,
    n_snapshots: int,
) -> pd.DataFrame:
    """Compute rank change over n snapshots.

    change = rank[n snapshots ago] - rank[current]
    Positive = improving (rank decreased, which is better).

    Args:
        snapshots: Single-team Barttorvik snapshots sorted by date.
        n_snapshots: Number of snapshots to look back.

    Returns:
        DataFrame with column 'rank_change_{n}s'.
    """
    col_name = f"rank_change_{n_snapshots}s"
    values = snapshots["rank"].values
    changes = np.full(len(values), np.nan)

    for i in range(len(values)):
        if i >= n_snapshots:
            changes[i] = values[i - n_snapshots] - values[i]

    return pd.DataFrame({col_name: changes}, index=snapshots.index)


def compute_all_trajectory_features(
    snapshots: pd.DataFrame,
) -> pd.DataFrame:
    """Compute all 6 trajectory features for a single team's snapshots.

    Args:
        snapshots: Single-team Barttorvik snapshots sorted by date.
            Required columns: date, team, adj_o, adj_d, barthag, rank.

    Returns:
        DataFrame with 6 columns, same length as input.
    """
    parts = [
        compute_ols_slope(snapshots, "adj_o", n_snapshots=10),
        compute_ols_slope(snapshots, "adj_d", n_snapshots=10, flip_sign=True),
        compute_net_efficiency_slope(snapshots, n_snapshots=10),
        compute_barthag_delta(snapshots, n_snapshots=10),
        compute_barthag_delta(snapshots, n_snapshots=20),
        compute_rank_change(snapshots, n_snapshots=20),
    ]
    return pd.concat(parts, axis=1)
