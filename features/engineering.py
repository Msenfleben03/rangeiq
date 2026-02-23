"""Core Feature Engineering Utilities.

Safe, leak-proof primitives for computing rolling features, time-decay
weighting, opponent-quality adjustments, and rest-day calculations.

CRITICAL DESIGN PRINCIPLE: Every rolling function applies .shift(1) internally
so callers NEVER need to remember. This prevents look-ahead bias by construction.

All functions return NEW objects (immutable pattern) — inputs are never mutated.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def safe_rolling(
    series: pd.Series,
    window: int,
    func: str = "mean",
    min_periods: int | None = None,
) -> pd.Series:
    """Compute a rolling statistic with mandatory 1-game lag.

    The result is shifted by 1 position so that the value at row i
    reflects ONLY games BEFORE game i. This prevents look-ahead bias.

    Args:
        series: Input time series (must be sorted chronologically).
        window: Number of observations in the rolling window.
        func: Aggregation function name — "mean", "std", "sum", "min", "max".
        min_periods: Minimum observations required. Defaults to window.

    Returns:
        New Series with lagged rolling statistic. First ``window`` rows
        will be NaN (insufficient history).

    Raises:
        ValueError: If window < 2 or func is unsupported.
    """
    if window < 2:
        raise ValueError(f"Window must be >= 2, got {window}")

    valid_funcs = {"mean", "std", "sum", "min", "max"}
    if func not in valid_funcs:
        raise ValueError(f"Unsupported func '{func}'. Choose from {valid_funcs}")

    if min_periods is None:
        min_periods = window

    roller = series.rolling(window=window, min_periods=min_periods)
    result = getattr(roller, func)()

    # CRITICAL: shift(1) ensures no leakage — value at row i uses only rows < i
    return result.shift(1)


def exponential_weighted_rolling(
    series: pd.Series,
    window: int,
    half_life_games: int = 8,
) -> pd.Series:
    """Compute exponentially-weighted rolling mean with mandatory lag.

    More recent games receive higher weight, with the weight halving every
    ``half_life_games`` observations. Uses pandas EWM with span derived
    from the half-life.

    Args:
        series: Input time series (chronologically sorted).
        window: Effective window size for min_periods.
        half_life_games: Number of games for weight to halve.

    Returns:
        New Series with lagged exponentially-weighted mean.

    Raises:
        ValueError: If half_life_games < 1.
    """
    if half_life_games < 1:
        raise ValueError(f"half_life_games must be >= 1, got {half_life_games}")

    result = series.ewm(halflife=half_life_games, min_periods=window).mean()

    # CRITICAL: shift(1) prevents leakage
    return result.shift(1)


def opponent_quality_weight(
    stat: pd.Series,
    opp_elo: pd.Series,
    mean_elo: float = 1500.0,
) -> pd.Series:
    """Weight a statistic by opponent quality relative to average.

    A margin of +10 against a 1700-rated opponent counts more than +10
    against a 1300-rated opponent. When opponent is exactly average
    (1500 Elo), the weight is 1.0 (neutral).

    Args:
        stat: Raw statistic to weight (e.g., point differential).
        opp_elo: Opponent's Elo rating at the time of the game.
        mean_elo: League average Elo (default 1500).

    Returns:
        New Series with opponent-quality-weighted statistic.

    Raises:
        ValueError: If mean_elo <= 0.
    """
    if mean_elo <= 0:
        raise ValueError(f"mean_elo must be positive, got {mean_elo}")

    weight = opp_elo / mean_elo
    return stat * weight


def compute_rest_days(
    dates: pd.Series,
    team_id_col: pd.Series,
) -> pd.DataFrame:
    """Compute rest days and back-to-back flags per team.

    For each game, calculates the number of calendar days since the
    team's PREVIOUS game. First game of season gets NaN.

    Args:
        dates: Game dates (datetime-like), one per row.
        team_id_col: Team identifier for each row.

    Returns:
        DataFrame with columns:
        - ``rest_days``: Days since team's last game (NaN for first game).
        - ``is_back_to_back``: True if rest_days <= 1.
    """
    dates = pd.to_datetime(dates)

    rest = pd.Series(np.nan, index=dates.index, dtype=float)
    b2b = pd.Series(False, index=dates.index, dtype=bool)

    # Track last game date per team
    last_game: dict[str, pd.Timestamp] = {}

    for idx in dates.index:
        team = team_id_col.loc[idx]
        game_date = dates.loc[idx]

        if team in last_game:
            delta = (game_date - last_game[team]).days
            rest.loc[idx] = delta
            b2b.loc[idx] = delta <= 1

        last_game[team] = game_date

    return pd.DataFrame({"rest_days": rest, "is_back_to_back": b2b})


def validate_no_leakage(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    date_col: str,
) -> dict[str, bool | list[str]]:
    """Quick leakage check: correlate features with future target values.

    For each feature, computes the correlation between the feature value
    at time t and the target at time t. A suspiciously high correlation
    (> 0.5) may indicate the feature contains information from game t
    (i.e., it was not properly lagged).

    This is a FAST heuristic — not a replacement for the full
    TemporalValidator, but useful during development.

    Args:
        df: DataFrame with features, target, and date columns.
        feature_cols: Feature column names to check.
        target_col: Target variable column name.
        date_col: Date column name (used for sorting check).

    Returns:
        Dict with:
        - ``passed``: True if no suspicious correlations found.
        - ``suspicious_features``: List of features with |corr| > 0.5.
        - ``correlations``: Dict of feature -> correlation value.
    """
    sorted_df = df.sort_values(date_col).copy()

    suspicious: list[str] = []
    correlations: dict[str, float] = {}

    for col in feature_cols:
        if col not in sorted_df.columns:
            continue
        valid = sorted_df[[col, target_col]].dropna()
        if len(valid) < 10:
            continue

        corr = valid[col].corr(valid[target_col])
        correlations[col] = corr

        if abs(corr) > 0.5:
            suspicious.append(col)

    return {
        "passed": len(suspicious) == 0,
        "suspicious_features": suspicious,
        "correlations": correlations,
    }
