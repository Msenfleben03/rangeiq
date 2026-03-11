"""Late-season loss features for NCAAB tournament research.

Captures late-season performance deterioration signals that may predict
tournament underperformance. All features use game-count windows and
apply .shift(1) for look-ahead bias prevention.

Features:
- late_loss_count_5g / 10g: Rolling loss count
- loss_margin_mean_10g: Mean margin of defeat for losses only
- weighted_quality_loss_10g: Loss count weighted by opponent barthag
- bad_loss_weighted_10g: Loss count weighted by (1 - opponent barthag)
- home_loss_rate_10g: Home losses / home games in window

CRITICAL: Every rolling feature uses .shift(1) — value at row i
reflects ONLY games BEFORE game i. No look-ahead bias is possible.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Feature column names (canonical)
_LOSS_COUNT_5 = "late_loss_count_5g"
_LOSS_COUNT_10 = "late_loss_count_10g"
_LOSS_MARGIN_MEAN_10 = "loss_margin_mean_10g"
_WEIGHTED_QUALITY_LOSS_10 = "weighted_quality_loss_10g"
_BAD_LOSS_WEIGHTED_10 = "bad_loss_weighted_10g"
_HOME_LOSS_RATE_10 = "home_loss_rate_10g"

ALL_LOSS_FEATURE_NAMES: tuple[str, ...] = (
    _LOSS_COUNT_5,
    _LOSS_COUNT_10,
    _LOSS_MARGIN_MEAN_10,
    _WEIGHTED_QUALITY_LOSS_10,
    _BAD_LOSS_WEIGHTED_10,
    _HOME_LOSS_RATE_10,
)


def compute_loss_count(team_games: pd.DataFrame, window: int) -> pd.DataFrame:
    """Count losses in a rolling game window with shift(1).

    Args:
        team_games: Single-team game log sorted by date.
            Must have ``result`` column with 'W'/'L' values.
        window: Number of games in the rolling window.

    Returns:
        DataFrame with single column ``late_loss_count_{window}g``.
    """
    is_loss = (team_games["result"] == "L").astype(float)
    col_name = f"late_loss_count_{window}g"

    rolled = is_loss.rolling(window=window, min_periods=window).sum()
    # CRITICAL: shift(1) prevents leakage
    result = rolled.shift(1)

    return pd.DataFrame({col_name: result}, index=team_games.index)


def compute_loss_margin_mean(team_games: pd.DataFrame, window: int) -> pd.DataFrame:
    """Mean margin of defeat for losses only in a rolling window.

    For each position, looks at the last ``window`` games (shifted by 1),
    filters to losses only, and computes mean (pts_against - pts_for).
    Returns 0.0 if no losses in window.

    Args:
        team_games: Single-team game log sorted by date.
            Must have ``result``, ``points_for``, ``points_against`` columns.
        window: Number of games in the rolling window.

    Returns:
        DataFrame with single column ``loss_margin_mean_{window}g``.
    """
    col_name = f"loss_margin_mean_{window}g"
    n = len(team_games)

    is_loss = team_games["result"].values == "L"
    margin = team_games["points_against"].values - team_games["points_for"].values

    values = np.full(n, np.nan)
    for i in range(window, n):
        # shift(1): use rows [i-window, i) — excludes row i
        start = i - window
        end = i
        window_losses = is_loss[start:end]
        window_margins = margin[start:end]

        loss_margins = window_margins[window_losses]
        if len(loss_margins) == 0:
            values[i] = 0.0
        else:
            values[i] = float(np.mean(loss_margins))

    return pd.DataFrame({col_name: values}, index=team_games.index)


def compute_weighted_quality_loss(
    team_games: pd.DataFrame,
    opp_barthag: pd.Series,
    window: int,
) -> pd.DataFrame:
    """Loss count weighted by opponent barthag in rolling window.

    For each loss in the window, add the opponent's PIT barthag.
    Divide the sum by total games in window (not just losses).

    Args:
        team_games: Single-team game log sorted by date.
            Must have ``result`` column.
        opp_barthag: Opponent barthag values, aligned with team_games index.
        window: Number of games in the rolling window.

    Returns:
        DataFrame with single column ``weighted_quality_loss_{window}g``.
    """
    col_name = f"weighted_quality_loss_{window}g"
    n = len(team_games)

    is_loss = team_games["result"].values == "L"
    barthag_vals = opp_barthag.values

    values = np.full(n, np.nan)
    for i in range(window, n):
        # shift(1): use rows [i-window, i)
        start = i - window
        end = i
        window_losses = is_loss[start:end]
        window_barthag = barthag_vals[start:end]

        weighted_sum = float(np.sum(window_barthag[window_losses]))
        values[i] = weighted_sum / window

    return pd.DataFrame({col_name: values}, index=team_games.index)


def compute_bad_loss_weighted(
    team_games: pd.DataFrame,
    opp_barthag: pd.Series,
    window: int,
) -> pd.DataFrame:
    """Loss count weighted by (1 - opponent barthag) in rolling window.

    Higher values indicate more losses to weak opponents (bad losses).
    Divide sum by total games in window.

    Args:
        team_games: Single-team game log sorted by date.
            Must have ``result`` column.
        opp_barthag: Opponent barthag values, aligned with team_games index.
        window: Number of games in the rolling window.

    Returns:
        DataFrame with single column ``bad_loss_weighted_{window}g``.
    """
    col_name = f"bad_loss_weighted_{window}g"
    n = len(team_games)

    is_loss = team_games["result"].values == "L"
    inv_barthag = 1.0 - opp_barthag.values

    values = np.full(n, np.nan)
    for i in range(window, n):
        # shift(1): use rows [i-window, i)
        start = i - window
        end = i
        window_losses = is_loss[start:end]
        window_inv = inv_barthag[start:end]

        weighted_sum = float(np.sum(window_inv[window_losses]))
        values[i] = weighted_sum / window

    return pd.DataFrame({col_name: values}, index=team_games.index)


def compute_home_loss_rate(team_games: pd.DataFrame, window: int) -> pd.DataFrame:
    """Home losses / home games in rolling window, excluding neutral site.

    Returns NaN if no home games in window.

    Args:
        team_games: Single-team game log sorted by date.
            Must have ``result``, ``location`` columns.
        window: Number of games in the rolling window.

    Returns:
        DataFrame with single column ``home_loss_rate_{window}g``.
    """
    col_name = f"home_loss_rate_{window}g"
    n = len(team_games)

    is_home = team_games["location"].values == "Home"
    is_loss = team_games["result"].values == "L"

    values = np.full(n, np.nan)
    for i in range(window, n):
        # shift(1): use rows [i-window, i)
        start = i - window
        end = i
        home_mask = is_home[start:end]
        loss_mask = is_loss[start:end]

        home_count = int(np.sum(home_mask))
        if home_count == 0:
            values[i] = np.nan
        else:
            home_losses = int(np.sum(home_mask & loss_mask))
            values[i] = home_losses / home_count

    return pd.DataFrame({col_name: values}, index=team_games.index)


def compute_all_loss_features(
    team_games: pd.DataFrame,
    opp_barthag: pd.Series | None = None,
) -> pd.DataFrame:
    """Compute all late-season loss features for a single team.

    Args:
        team_games: Single-team game log sorted by date. Required columns:
            date, team_id, result (W/L), points_for, points_against,
            point_diff, location (Home/Away/Neutral), opponent_id.
        opp_barthag: Optional opponent barthag series. If None, skips
            weighted_quality_loss and bad_loss_weighted features.

    Returns:
        DataFrame with all computed feature columns, aligned with input index.
    """
    result = pd.DataFrame(index=team_games.index)

    # Loss counts (5 and 10 game windows)
    lc5 = compute_loss_count(team_games, window=5)
    lc10 = compute_loss_count(team_games, window=10)
    result[_LOSS_COUNT_5] = lc5[_LOSS_COUNT_5]
    result[_LOSS_COUNT_10] = lc10[_LOSS_COUNT_10]

    # Loss margin mean (10 game window)
    lmm = compute_loss_margin_mean(team_games, window=10)
    result[_LOSS_MARGIN_MEAN_10] = lmm[_LOSS_MARGIN_MEAN_10]

    # Barthag-weighted features (only if opp_barthag provided)
    if opp_barthag is not None:
        wql = compute_weighted_quality_loss(team_games, opp_barthag, window=10)
        result[_WEIGHTED_QUALITY_LOSS_10] = wql[_WEIGHTED_QUALITY_LOSS_10]

        blw = compute_bad_loss_weighted(team_games, opp_barthag, window=10)
        result[_BAD_LOSS_WEIGHTED_10] = blw[_BAD_LOSS_WEIGHTED_10]

    # Home loss rate (10 game window)
    hlr = compute_home_loss_rate(team_games, window=10)
    result[_HOME_LOSS_RATE_10] = hlr[_HOME_LOSS_RATE_10]

    return result
