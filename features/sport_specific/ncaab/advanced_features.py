"""NCAAB Advanced Feature Engine.

Computes advanced features for the NCAAB Elo betting model. All features
are orthogonal to (or complementary to) base Elo ratings and are designed
to capture second-moment information that Elo ignores.

Features implemented:
- Rolling volatility (scoring consistency)
- Opponent-quality-weighted margin
- Rest days / back-to-back detection
- Decay-weighted rolling margin (recency-emphasized form)

CRITICAL: All rolling features use safe_rolling() which applies .shift(1)
internally. No look-ahead bias is possible by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from features.engineering import (
    compute_rest_days,
    exponential_weighted_rolling,
    opponent_quality_weight,
    safe_rolling,
)


# Feature column names (canonical)
_VOL_5 = "vol_5"
_VOL_10 = "vol_10"
_OQ_MARGIN_10 = "oq_margin_10"
_REST_DAYS = "rest_days"
_IS_BACK_TO_BACK = "is_back_to_back"
_DECAY_MARGIN_10 = "decay_margin_10"

ALL_FEATURE_NAMES: tuple[str, ...] = (
    _VOL_5,
    _VOL_10,
    _OQ_MARGIN_10,
    _REST_DAYS,
    _IS_BACK_TO_BACK,
    _DECAY_MARGIN_10,
)


@dataclass(frozen=True)
class FeatureConfig:
    """Configuration for NCAAB feature computation."""

    volatility_windows: tuple[int, ...] = (5, 10)
    oq_window: int = 10
    oq_mean_elo: float = 1500.0
    decay_window: int = 10
    decay_half_life: int = 8
    back_to_back_threshold: int = 1


DEFAULT_CONFIG = FeatureConfig()


class NCABBFeatureEngine:
    """Compute advanced features for NCAAB games.

    All methods are stateless — they take a DataFrame of team game logs
    (sorted chronologically per team) and return new columns.

    The input DataFrame must have at minimum:
    - ``point_diff``: Points scored minus points allowed.
    - ``date``: Game date (datetime-like).
    - ``team_id``: Team identifier.

    For opponent-quality weighting:
    - ``opp_elo``: Opponent Elo rating at game time.
    """

    def __init__(self, config: FeatureConfig | None = None) -> None:
        """Initialize with optional feature configuration."""
        self.config = config or DEFAULT_CONFIG

    def compute_rolling_volatility(
        self,
        team_games: pd.DataFrame,
        windows: tuple[int, ...] | None = None,
    ) -> pd.DataFrame:
        """Compute rolling standard deviation of point differential.

        Captures scoring consistency — a team with high volatility is
        less predictable than one with low volatility, independent of
        their Elo rating.

        Args:
            team_games: Single-team game log sorted by date.
                Must have ``point_diff`` column.
            windows: Tuple of window sizes. Defaults to config.

        Returns:
            DataFrame with volatility columns (e.g., vol_5, vol_10).
        """
        if windows is None:
            windows = self.config.volatility_windows

        result = pd.DataFrame(index=team_games.index)
        for w in windows:
            col_name = f"vol_{w}"
            result[col_name] = safe_rolling(team_games["point_diff"], window=w, func="std")
        return result

    def compute_opponent_weighted_margin(
        self,
        team_games: pd.DataFrame,
        window: int | None = None,
    ) -> pd.Series:
        """Compute rolling mean of opponent-quality-weighted margin.

        Beating a 1700-rated team by 10 produces a higher weighted margin
        than beating a 1300-rated team by 10. The rolling mean of this
        weighted margin captures "quality-adjusted form".

        Args:
            team_games: Single-team game log sorted by date.
                Must have ``point_diff`` and ``opp_elo`` columns.
            window: Rolling window size. Defaults to config.

        Returns:
            Series with rolling opponent-weighted margin.
        """
        if window is None:
            window = self.config.oq_window

        weighted = opponent_quality_weight(
            team_games["point_diff"],
            team_games["opp_elo"],
            mean_elo=self.config.oq_mean_elo,
        )
        return safe_rolling(weighted, window=window, func="mean")

    def compute_rest_days(self, team_games: pd.DataFrame) -> pd.DataFrame:
        """Compute rest days and back-to-back flags.

        Args:
            team_games: Single-team game log sorted by date.
                Must have ``date`` and ``team_id`` columns.

        Returns:
            DataFrame with ``rest_days`` and ``is_back_to_back`` columns.
        """
        return compute_rest_days(team_games["date"], team_games["team_id"])

    def compute_decay_weighted_margin(
        self,
        team_games: pd.DataFrame,
        window: int | None = None,
        half_life: int | None = None,
    ) -> pd.Series:
        """Compute exponentially-weighted rolling point differential.

        More recent games contribute more to the rolling mean. This
        captures short-term form changes faster than a simple rolling
        mean, complementing the Elo K-factor mechanism.

        Args:
            team_games: Single-team game log sorted by date.
                Must have ``point_diff`` column.
            window: Minimum periods for EWM. Defaults to config.
            half_life: Games for weight to halve. Defaults to config.

        Returns:
            Series with decay-weighted rolling margin.
        """
        if window is None:
            window = self.config.decay_window
        if half_life is None:
            half_life = self.config.decay_half_life

        return exponential_weighted_rolling(
            team_games["point_diff"],
            window=window,
            half_life_games=half_life,
        )

    def compute_all(
        self,
        team_games: pd.DataFrame,
    ) -> pd.DataFrame:
        """Compute all features for a single team's game log.

        This is the primary entry point. Computes every available feature
        and returns them as a single DataFrame aligned with the input index.

        Args:
            team_games: Single-team game log, sorted chronologically.
                Required columns: ``point_diff``, ``date``, ``team_id``.
                Optional columns: ``opp_elo`` (for quality weighting).

        Returns:
            DataFrame with all feature columns. NaN values in early rows
            are expected (insufficient history for rolling windows).
        """
        result = pd.DataFrame(index=team_games.index)

        # Rolling volatility
        vol_df = self.compute_rolling_volatility(team_games)
        for col in vol_df.columns:
            result[col] = vol_df[col]

        # Rest days
        rest_df = self.compute_rest_days(team_games)
        result[_REST_DAYS] = rest_df["rest_days"]
        result[_IS_BACK_TO_BACK] = rest_df["is_back_to_back"]

        # Decay-weighted margin
        result[_DECAY_MARGIN_10] = self.compute_decay_weighted_margin(team_games)

        # Opponent-quality-weighted margin (only if opp_elo available)
        if "opp_elo" in team_games.columns:
            result[_OQ_MARGIN_10] = self.compute_opponent_weighted_margin(team_games)

        return result

    @staticmethod
    def get_feature_names() -> list[str]:
        """Return canonical feature column names for temporal validator audit."""
        return list(ALL_FEATURE_NAMES)

    @staticmethod
    def compute_matchup_differentials(
        home_features: pd.Series,
        away_features: pd.Series,
        feature_names: list[str] | None = None,
    ) -> dict[str, float]:
        """Compute home - away feature differentials for a single matchup.

        Used at prediction time: given pre-computed features for both teams,
        returns the differential for each feature.

        Args:
            home_features: Feature values for the home team (latest row).
            away_features: Feature values for the away team (latest row).
            feature_names: Features to difference. Defaults to all numeric.

        Returns:
            Dict mapping ``{feature}_diff`` -> home_value - away_value.
        """
        if feature_names is None:
            feature_names = [
                _VOL_5,
                _VOL_10,
                _OQ_MARGIN_10,
                _REST_DAYS,
                _DECAY_MARGIN_10,
            ]

        diffs: dict[str, float] = {}
        for name in feature_names:
            h = home_features.get(name, np.nan)
            a = away_features.get(name, np.nan)
            if pd.notna(h) and pd.notna(a):
                diffs[f"{name}_diff"] = float(h - a)
            else:
                diffs[f"{name}_diff"] = np.nan

        # Back-to-back is binary — express as advantage flags
        h_b2b = home_features.get(_IS_BACK_TO_BACK, False)
        a_b2b = away_features.get(_IS_BACK_TO_BACK, False)
        diffs["home_b2b"] = float(bool(h_b2b))
        diffs["away_b2b"] = float(bool(a_b2b))

        return diffs
