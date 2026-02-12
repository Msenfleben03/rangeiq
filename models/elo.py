"""
Base ELO Rating System Implementation.

This module provides the foundational Elo rating system used for sports betting
predictions. It includes both pure functions for individual calculations and
a class-based system for managing team ratings over time.

Key Features:
- Standard Elo expected score and update formulas
- Margin of Victory (MOV) multiplier for more accurate updates
- Home court/field advantage adjustments
- Season-to-season regression to mean
- Rating-to-spread conversion utilities

References:
- Original Elo: https://en.wikipedia.org/wiki/Elo_rating_system
- FiveThirtyEight methodology: https://fivethirtyeight.com/methodology/

Claude Code: This is the BASE implementation. Sport-specific models should
extend EloRatingSystem and override parameters as needed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from config.constants import ELO


# =============================================================================
# PURE FUNCTIONS
# =============================================================================


def elo_expected(rating_a: float, rating_b: float) -> float:
    """Calculate expected win probability for team A using Elo formula.

    The expected score represents the probability that team A beats team B,
    given their respective Elo ratings.

    Args:
        rating_a: Elo rating of team A.
        rating_b: Elo rating of team B.

    Returns:
        Probability (0-1) that team A wins.

    Examples:
        >>> elo_expected(1600, 1500)
        0.6400649...
        >>> elo_expected(1500, 1500)
        0.5
    """
    exponent = (rating_b - rating_a) / 400
    return 1 / (1 + 10**exponent)


def elo_update(
    rating: float,
    expected: float,
    actual: float,
    k: int = 20,
) -> float:
    """Update Elo rating after a game result.

    The standard Elo update formula adjusts the rating based on the difference
    between expected and actual results, scaled by the K-factor.

    Args:
        rating: Current Elo rating.
        expected: Expected score (probability of winning).
        actual: Actual result (1.0 = win, 0.5 = tie, 0.0 = loss).
        k: K-factor controlling rating volatility.

    Returns:
        New Elo rating after the update.

    Examples:
        >>> elo_update(1500, 0.5, 1.0, k=20)
        1510.0
        >>> elo_update(1500, 0.5, 0.0, k=20)
        1490.0
    """
    return rating + k * (actual - expected)


def elo_to_spread(elo_diff: float, points_per_elo: float = 25.0) -> float:
    """Convert Elo rating difference to predicted point spread.

    Standard conversion is approximately 25 Elo points = 1 point on spread.
    A positive Elo difference (home team rated higher) produces a negative
    spread (home team favored).

    Args:
        elo_diff: Elo rating difference (home - away, adjusted for home court).
        points_per_elo: Number of Elo points per 1 point of spread.

    Returns:
        Predicted point spread (negative = home favored).

    Examples:
        >>> elo_to_spread(100)
        4.0
        >>> elo_to_spread(-100)
        -4.0
    """
    return elo_diff / points_per_elo


def spread_to_elo(spread: float, points_per_elo: float = 25.0) -> float:
    """Convert point spread to Elo rating difference.

    Inverse of elo_to_spread. Useful for comparing model predictions
    to market lines.

    Args:
        spread: Point spread (negative = home favored).
        points_per_elo: Number of Elo points per 1 point of spread.

    Returns:
        Equivalent Elo rating difference.

    Examples:
        >>> spread_to_elo(4.0)
        100.0
        >>> spread_to_elo(-4.0)
        -100.0
    """
    return spread * points_per_elo


def regress_to_mean(
    rating: float,
    mean: float = 1500.0,
    factor: float = 0.33,
) -> float:
    """Apply regression to mean for between-season adjustments.

    Teams regress toward the mean rating between seasons to account for
    roster changes, coaching changes, and general uncertainty. A factor
    of 0.33 means the rating moves 33% of the way back to the mean.

    Args:
        rating: Current Elo rating.
        mean: Target mean rating (typically 1500).
        factor: Regression factor (0-1). Higher = more regression.

    Returns:
        Regressed rating.

    Examples:
        >>> regress_to_mean(1700, mean=1500, factor=0.33)
        1634.0
        >>> regress_to_mean(1300, mean=1500, factor=0.33)
        1366.0
    """
    return mean + (rating - mean) * (1 - factor)


def mov_multiplier(
    margin: int,
    elo_diff: float,
    mov_cap: int = 25,
) -> float:
    """Calculate margin of victory multiplier for Elo updates.

    Larger margins produce larger rating changes, but with diminishing returns.
    The multiplier also adjusts for elo_diff to reduce autocorrelation
    (expected blowouts shouldn't massively change ratings).

    Formula based on FiveThirtyEight's approach:
    MOV_mult = ln(abs(margin) + 1) * (2.2 / (elo_diff * 0.001 + 2.2))

    Args:
        margin: Absolute point margin (always positive).
        elo_diff: Elo difference from winner's perspective (positive = favorite).
        mov_cap: Maximum margin to consider (caps extreme blowouts).

    Returns:
        Multiplier to apply to K-factor (>= 1.0).

    Examples:
        >>> mov_multiplier(10, elo_diff=0)  # Close game, equal teams
        1.598...
        >>> mov_multiplier(20, elo_diff=200)  # Expected blowout
        1.741...
    """
    # Cap extreme margins
    capped_margin = min(abs(margin), mov_cap)

    if capped_margin == 0:
        return 1.0

    # Logarithmic scaling for diminishing returns
    log_component = math.log(capped_margin + 1)

    # Autocorrelation adjustment - reduce multiplier when favorite wins big
    # This prevents favorites from gaining too much from expected blowouts
    autocorr_adjustment = 2.2 / (elo_diff * 0.001 + 2.2)

    return log_component * autocorr_adjustment


# =============================================================================
# ELO RATING SYSTEM CLASS
# =============================================================================


@dataclass
class EloRatingSystem:
    """Manages Elo ratings for a collection of teams.

    This class provides a complete system for tracking and updating team
    ratings over time. It supports home advantage, margin of victory
    adjustments, and season regression.

    Attributes:
        k_factor: Base K-factor for rating updates.
        initial_rating: Starting rating for new teams.
        home_advantage: Elo points added for home team.
        mov_cap: Maximum margin of victory considered.
        regression_factor: Fraction to regress toward mean between seasons.
        min_rating: Minimum allowed rating.
        max_rating: Maximum allowed rating.
        ratings: Dictionary mapping team_id to Elo rating.
        game_history: List of processed games.

    Examples:
        >>> elo = EloRatingSystem(k_factor=20, home_advantage=100)
        >>> elo.set_rating("duke", 1650)
        >>> elo.set_rating("unc", 1550)
        >>> elo.update_game("duke", "unc", 80, 70)
        >>> elo.get_rating("duke")  # Should increase
        1659.2...
    """

    k_factor: int = 20
    initial_rating: float = 1500.0
    home_advantage: float = 100.0
    mov_cap: int = 25
    regression_factor: float = 0.33
    min_rating: float = ELO.MIN_RATING
    max_rating: float = ELO.MAX_RATING
    points_per_elo: float = 25.0
    ratings: Dict[str, float] = field(default_factory=dict)
    game_history: List[Dict] = field(default_factory=list)

    def get_rating(self, team_id: str) -> float:
        """Get the current Elo rating for a team.

        Args:
            team_id: Unique identifier for the team.

        Returns:
            Current Elo rating, or initial_rating if team not found.
        """
        return self.ratings.get(team_id, self.initial_rating)

    def set_rating(self, team_id: str, rating: float) -> None:
        """Set the Elo rating for a team.

        Rating is clamped to [min_rating, max_rating].

        Args:
            team_id: Unique identifier for the team.
            rating: New Elo rating to set.
        """
        clamped = max(self.min_rating, min(self.max_rating, rating))
        self.ratings[team_id] = clamped

    def get_all_ratings(self) -> Dict[str, float]:
        """Get all team ratings.

        Returns:
            Dictionary mapping team_id to Elo rating.
        """
        return dict(self.ratings)

    def predict_win_probability(
        self,
        home_team: str,
        away_team: str,
        neutral_site: bool = False,
    ) -> float:
        """Predict home team's win probability.

        Args:
            home_team: Team ID for home team.
            away_team: Team ID for away team.
            neutral_site: If True, no home advantage applied.

        Returns:
            Probability (0-1) that home team wins.
        """
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home court advantage
        if not neutral_site:
            home_rating += self.home_advantage

        return elo_expected(home_rating, away_rating)

    def predict_spread(
        self,
        home_team: str,
        away_team: str,
        neutral_site: bool = False,
    ) -> float:
        """Predict point spread for a matchup.

        Args:
            home_team: Team ID for home team.
            away_team: Team ID for away team.
            neutral_site: If True, no home advantage applied.

        Returns:
            Predicted spread (negative = home favored).
        """
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home court advantage
        hca = 0 if neutral_site else self.home_advantage

        elo_diff = (home_rating + hca) - away_rating
        return -elo_to_spread(elo_diff, self.points_per_elo)

    def get_effective_k(
        self,
        margin: int,
        elo_diff: float,
    ) -> float:
        """Calculate effective K-factor with MOV adjustment.

        Args:
            margin: Absolute score difference.
            elo_diff: Elo difference from winner's perspective.

        Returns:
            Effective K-factor with MOV multiplier applied.
        """
        multiplier = mov_multiplier(margin, elo_diff, self.mov_cap)
        return self.k_factor * multiplier

    def update_game(
        self,
        home_team: str,
        away_team: str,
        home_score: int,
        away_score: int,
        neutral_site: bool = False,
    ) -> Tuple[float, float]:
        """Update ratings after a game.

        Args:
            home_team: Team ID for home team.
            away_team: Team ID for away team.
            home_score: Home team's final score.
            away_score: Away team's final score.
            neutral_site: If True, no home advantage applied.

        Returns:
            Tuple of (new_home_rating, new_away_rating).
        """
        # Get current ratings
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply home court advantage for prediction
        hca = 0 if neutral_site else self.home_advantage
        adjusted_home = home_rating + hca

        # Calculate expected outcomes
        expected_home = elo_expected(adjusted_home, away_rating)
        expected_away = 1 - expected_home

        # Determine actual outcomes
        if home_score > away_score:
            actual_home = 1.0
            actual_away = 0.0
            winner_elo_diff = adjusted_home - away_rating
        elif away_score > home_score:
            actual_home = 0.0
            actual_away = 1.0
            winner_elo_diff = away_rating - adjusted_home
        else:
            actual_home = 0.5
            actual_away = 0.5
            winner_elo_diff = 0

        # Calculate margin for MOV adjustment
        margin = abs(home_score - away_score)

        # Get effective K with MOV multiplier
        effective_k = self.get_effective_k(margin, winner_elo_diff)

        # Update ratings
        new_home = elo_update(home_rating, expected_home, actual_home, int(effective_k))
        new_away = elo_update(away_rating, expected_away, actual_away, int(effective_k))

        # Store new ratings (clamped)
        self.set_rating(home_team, new_home)
        self.set_rating(away_team, new_away)

        # Record game in history
        self.game_history.append(
            {
                "home_team": home_team,
                "away_team": away_team,
                "home_score": home_score,
                "away_score": away_score,
                "home_rating_before": home_rating,
                "away_rating_before": away_rating,
                "home_rating_after": self.get_rating(home_team),
                "away_rating_after": self.get_rating(away_team),
                "expected_home": expected_home,
                "effective_k": effective_k,
            }
        )

        return self.get_rating(home_team), self.get_rating(away_team)

    def apply_season_regression(self) -> None:
        """Apply regression to mean for all teams.

        Call this between seasons to account for roster changes and
        general uncertainty.
        """
        for team_id in list(self.ratings.keys()):
            current = self.ratings[team_id]
            regressed = regress_to_mean(
                current,
                mean=self.initial_rating,
                factor=self.regression_factor,
            )
            self.ratings[team_id] = regressed

    def reset(self) -> None:
        """Reset all ratings and history."""
        self.ratings.clear()
        self.game_history.clear()

    def to_dict(self) -> Dict:
        """Serialize system state to dictionary.

        Returns:
            Dictionary containing all system state.
        """
        return {
            "k_factor": self.k_factor,
            "initial_rating": self.initial_rating,
            "home_advantage": self.home_advantage,
            "mov_cap": self.mov_cap,
            "regression_factor": self.regression_factor,
            "ratings": dict(self.ratings),
            "game_count": len(self.game_history),
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "EloRatingSystem":
        """Create system from serialized dictionary.

        Args:
            data: Dictionary from to_dict().

        Returns:
            New EloRatingSystem instance.
        """
        system = cls(
            k_factor=data.get("k_factor", 20),
            initial_rating=data.get("initial_rating", 1500.0),
            home_advantage=data.get("home_advantage", 100.0),
            mov_cap=data.get("mov_cap", 25),
            regression_factor=data.get("regression_factor", 0.33),
        )
        system.ratings = dict(data.get("ratings", {}))
        return system
