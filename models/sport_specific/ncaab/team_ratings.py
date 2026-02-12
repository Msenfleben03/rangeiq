"""
NCAAB (NCAA Basketball) Elo Rating Model.

This module extends the base Elo rating system with NCAAB-specific features
including:
- Conference strength adjustments
- Tournament seeding correlation
- Early season uncertainty handling
- Tournament-specific K-factors
- Historical matchup tracking

Claude Code: This is the primary model for NCAAB betting predictions.
Use this for generating spreads and moneyline probabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from config.constants import ELO
from models.elo import EloRatingSystem, elo_expected, elo_to_spread


# =============================================================================
# CONFERENCE STRENGTH TIERS
# =============================================================================

# Conference strength adjustments in Elo points
# Positive = teams in this conference are underrated by raw Elo
# These are applied when teams play out-of-conference
CONFERENCE_ADJUSTMENTS: Dict[str, float] = {
    # Power conferences (top tier)
    "Big Ten": 50.0,
    "Big 12": 50.0,
    "SEC": 45.0,
    "ACC": 40.0,
    "Big East": 40.0,
    # Strong mid-majors
    "AAC": 20.0,
    "A-10": 15.0,
    "MWC": 15.0,
    "WCC": 15.0,
    "Missouri Valley": 10.0,
    # Mid-majors
    "MAC": 0.0,
    "Sun Belt": 0.0,
    "C-USA": 0.0,
    "CAA": 0.0,
    "Horizon": 0.0,
    "Ivy": 0.0,
    "WAC": -5.0,
    "Big West": -5.0,
    "Summit": -10.0,
    "America East": -10.0,
    "MAAC": -10.0,
    "Patriot": -10.0,
    "Southern": -10.0,
    "Big South": -15.0,
    "Ohio Valley": -15.0,
    "Southland": -15.0,
    "Atlantic Sun": -20.0,
    "Northeast": -20.0,
    "MEAC": -25.0,
    "SWAC": -25.0,
}

# Tournament seed to expected Elo rating
# Based on historical performance of seeds in the NCAA tournament
SEED_TO_ELO: Dict[int, float] = {
    1: 1750,
    2: 1700,
    3: 1665,
    4: 1635,
    5: 1610,
    6: 1590,
    7: 1570,
    8: 1555,
    9: 1545,
    10: 1530,
    11: 1510,
    12: 1490,
    13: 1460,
    14: 1430,
    15: 1390,
    16: 1350,
}


# =============================================================================
# NCAAB ELO MODEL
# =============================================================================


@dataclass
class NCAABEloModel(EloRatingSystem):
    """NCAAB-specific Elo rating model.

    Extends EloRatingSystem with NCAA basketball-specific features:
    - Conference strength adjustments for non-conference games
    - Tournament K-factor boost
    - Early season rating stabilization
    - Tournament seeding correlation utilities
    - Historical matchup tracking

    Attributes:
        tournament_k_factor: K-factor used for tournament games.
        early_season_games: Number of games considered "early season".
        early_season_k_reduction: Fraction to reduce K during early season.
        conferences: Mapping of team_id to conference name.
        matchup_history: Historical head-to-head results.
        games_played: Count of games played per team.

    Examples:
        >>> model = NCAABEloModel()
        >>> model.set_rating("duke", 1650)
        >>> model.predict_spread("duke", "unc")
        -6.0
    """

    # NCAAB-specific defaults from constants
    k_factor: int = ELO.K_FACTOR_NCAAB
    home_advantage: float = ELO.HOME_ADVANTAGE_NCAAB
    mov_cap: int = ELO.MOV_CAP_NCAAB
    regression_factor: float = ELO.REGRESSION_FACTOR_NCAAB
    points_per_elo: float = ELO.ELO_TO_POINTS_NCAAB

    # NCAAB-specific attributes
    tournament_k_factor: int = 32  # Higher K for tournament games
    early_season_games: int = 5
    early_season_k_reduction: float = 0.7  # 70% of normal K early season

    # Team metadata
    conferences: Dict[str, str] = field(default_factory=dict)
    games_played: Dict[str, int] = field(default_factory=dict)
    matchup_history: Dict[str, Dict[str, Dict[str, int]]] = field(default_factory=dict)

    def get_k_factor(
        self,
        is_tournament: bool = False,
        games_played: Optional[int] = None,
    ) -> int:
        """Get appropriate K-factor based on game context.

        Args:
            is_tournament: Whether this is a tournament game.
            games_played: Number of games team has played this season.

        Returns:
            Appropriate K-factor for the game type.
        """
        if is_tournament:
            return self.tournament_k_factor

        base_k = self.k_factor

        # Reduce K early in season (more uncertainty)
        if games_played is not None and games_played < self.early_season_games:
            return int(base_k * self.early_season_k_reduction)

        return base_k

    def get_conference_adjustment(self, conference: str) -> float:
        """Get Elo adjustment for a conference.

        Args:
            conference: Conference name.

        Returns:
            Elo point adjustment for the conference.
        """
        return CONFERENCE_ADJUSTMENTS.get(conference, 0.0)

    def set_conference(self, team_id: str, conference: str) -> None:
        """Set conference affiliation for a team.

        Args:
            team_id: Unique team identifier.
            conference: Conference name.
        """
        self.conferences[team_id] = conference

    def get_conference(self, team_id: str) -> Optional[str]:
        """Get conference affiliation for a team.

        Args:
            team_id: Unique team identifier.

        Returns:
            Conference name or None if not set.
        """
        return self.conferences.get(team_id)

    def predict_win_probability(
        self,
        home_team: str,
        away_team: str,
        neutral_site: bool = False,
        apply_conference_adj: bool = False,
    ) -> float:
        """Predict home team's win probability.

        Overrides base to support conference adjustments for non-conference
        games.

        Args:
            home_team: Team ID for home team.
            away_team: Team ID for away team.
            neutral_site: If True, no home advantage applied.
            apply_conference_adj: If True, apply conference strength adjustments.

        Returns:
            Probability (0-1) that home team wins.
        """
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply conference adjustments if requested (for non-conference games)
        if apply_conference_adj:
            home_conf = self.get_conference(home_team)
            away_conf = self.get_conference(away_team)

            if home_conf and away_conf and home_conf != away_conf:
                home_rating += self.get_conference_adjustment(home_conf)
                away_rating += self.get_conference_adjustment(away_conf)

        # Apply home court advantage
        if not neutral_site:
            home_rating += self.home_advantage

        return elo_expected(home_rating, away_rating)

    def predict_spread(
        self,
        home_team: str,
        away_team: str,
        neutral_site: bool = False,
        apply_conference_adj: bool = False,
    ) -> float:
        """Predict point spread for a matchup.

        Args:
            home_team: Team ID for home team.
            away_team: Team ID for away team.
            neutral_site: If True, no home advantage applied.
            apply_conference_adj: If True, apply conference strength adjustments.

        Returns:
            Predicted spread (negative = home favored).
        """
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)

        # Apply conference adjustments if requested
        if apply_conference_adj:
            home_conf = self.get_conference(home_team)
            away_conf = self.get_conference(away_team)

            if home_conf and away_conf and home_conf != away_conf:
                home_rating += self.get_conference_adjustment(home_conf)
                away_rating += self.get_conference_adjustment(away_conf)

        # Apply home court advantage
        hca = 0 if neutral_site else self.home_advantage

        elo_diff = (home_rating + hca) - away_rating
        return -elo_to_spread(elo_diff, self.points_per_elo)

    def seed_to_elo_estimate(self, seed: int) -> float:
        """Estimate Elo rating from tournament seed.

        Useful for initializing ratings based on seeding when Elo
        history is unavailable.

        Args:
            seed: Tournament seed (1-16).

        Returns:
            Estimated Elo rating for that seed.
        """
        if seed < 1:
            seed = 1
        if seed > 16:
            seed = 16
        return SEED_TO_ELO.get(seed, 1500.0)

    def update_game(
        self,
        home_team: str,
        away_team: str,
        home_score: int,
        away_score: int,
        neutral_site: bool = False,
        is_tournament: bool = False,
    ) -> tuple[float, float]:
        """Update ratings after a game.

        Overrides base to track games played and matchup history.

        Args:
            home_team: Team ID for home team.
            away_team: Team ID for away team.
            home_score: Home team's final score.
            away_score: Away team's final score.
            neutral_site: If True, no home advantage applied.
            is_tournament: If True, use tournament K-factor.

        Returns:
            Tuple of (new_home_rating, new_away_rating).
        """
        # Track games played
        self.games_played[home_team] = self.games_played.get(home_team, 0) + 1
        self.games_played[away_team] = self.games_played.get(away_team, 0) + 1

        # Get appropriate K-factor
        min_games = min(self.games_played[home_team], self.games_played[away_team])
        original_k = self.k_factor
        self.k_factor = self.get_k_factor(is_tournament=is_tournament, games_played=min_games)

        # Call parent update
        result = super().update_game(home_team, away_team, home_score, away_score, neutral_site)

        # Restore original K
        self.k_factor = original_k

        # Update matchup history
        self._record_matchup(home_team, away_team, home_score, away_score)

        return result

    def _record_matchup(
        self,
        home_team: str,
        away_team: str,
        home_score: int,
        away_score: int,
    ) -> None:
        """Record a game in matchup history.

        Args:
            home_team: Team ID for home team.
            away_team: Team ID for away team.
            home_score: Home team's final score.
            away_score: Away team's final score.
        """
        # Create matchup key (alphabetically ordered for consistency)
        team_a, team_b = sorted([home_team, away_team])

        if team_a not in self.matchup_history:
            self.matchup_history[team_a] = {}
        if team_b not in self.matchup_history[team_a]:
            self.matchup_history[team_a][team_b] = {
                "total_games": 0,
                f"{team_a}_wins": 0,
                f"{team_b}_wins": 0,
            }

        history = self.matchup_history[team_a][team_b]
        history["total_games"] += 1

        # Determine winner
        if home_score > away_score:
            history[f"{home_team}_wins"] = history.get(f"{home_team}_wins", 0) + 1
        else:
            history[f"{away_team}_wins"] = history.get(f"{away_team}_wins", 0) + 1

    def get_matchup_history(self, team_a: str, team_b: str) -> Dict[str, int]:
        """Get historical head-to-head record.

        Args:
            team_a: First team ID.
            team_b: Second team ID.

        Returns:
            Dictionary with total_games, team_a_wins, team_b_wins.
        """
        # Normalize key order
        key_a, key_b = sorted([team_a, team_b])

        if key_a in self.matchup_history:
            if key_b in self.matchup_history[key_a]:
                history = self.matchup_history[key_a][key_b]
                return {
                    "total_games": history.get("total_games", 0),
                    f"{team_a}_wins": history.get(f"{team_a}_wins", 0),
                    f"{team_b}_wins": history.get(f"{team_b}_wins", 0),
                }

        return {
            "total_games": 0,
            f"{team_a}_wins": 0,
            f"{team_b}_wins": 0,
        }

    def process_games(
        self,
        games: List[Dict[str, Any]],
        date_key: str = "date",
        home_key: str = "home",
        away_key: str = "away",
        home_score_key: str = "home_score",
        away_score_key: str = "away_score",
    ) -> None:
        """Process a list of games in chronological order.

        Args:
            games: List of game dictionaries.
            date_key: Key for game date in dictionary.
            home_key: Key for home team ID.
            away_key: Key for away team ID.
            home_score_key: Key for home team score.
            away_score_key: Key for away team score.
        """
        # Sort by date to ensure chronological processing
        sorted_games = sorted(games, key=lambda g: g.get(date_key, date.min))

        for game in sorted_games:
            self.update_game(
                home_team=game[home_key],
                away_team=game[away_key],
                home_score=game[home_score_key],
                away_score=game[away_score_key],
            )

    def to_dataframe(self) -> pd.DataFrame:
        """Export ratings to a pandas DataFrame.

        Returns:
            DataFrame with team_id, elo_rating, conference, games_played.
        """
        data = []
        for team_id, rating in self.ratings.items():
            data.append(
                {
                    "team_id": team_id,
                    "elo_rating": rating,
                    "conference": self.conferences.get(team_id, "Unknown"),
                    "games_played": self.games_played.get(team_id, 0),
                }
            )

        df = pd.DataFrame(data)
        if not df.empty:
            df = df.sort_values("elo_rating", ascending=False).reset_index(drop=True)
        return df

    def apply_season_regression(self) -> None:
        """Apply regression to mean and reset game counts.

        Overrides parent to also reset games_played counters and
        optionally clear matchup history.
        """
        super().apply_season_regression()

        # Reset games played for new season
        self.games_played.clear()

    def reset(self) -> None:
        """Reset all state including NCAAB-specific data."""
        super().reset()
        self.conferences.clear()
        self.games_played.clear()
        self.matchup_history.clear()

    def to_dict(self) -> Dict:
        """Serialize system state to dictionary.

        Returns:
            Dictionary containing all system state.
        """
        base = super().to_dict()
        base.update(
            {
                "tournament_k_factor": self.tournament_k_factor,
                "conferences": dict(self.conferences),
                "games_played": dict(self.games_played),
                "matchup_history": self.matchup_history,
            }
        )
        return base

    @classmethod
    def from_dict(cls, data: Dict) -> "NCAABEloModel":
        """Create model from serialized dictionary.

        Args:
            data: Dictionary from to_dict().

        Returns:
            New NCAABEloModel instance.
        """
        model = cls(
            k_factor=data.get("k_factor", ELO.K_FACTOR_NCAAB),
            initial_rating=data.get("initial_rating", 1500.0),
            home_advantage=data.get("home_advantage", ELO.HOME_ADVANTAGE_NCAAB),
            mov_cap=data.get("mov_cap", ELO.MOV_CAP_NCAAB),
            regression_factor=data.get("regression_factor", ELO.REGRESSION_FACTOR_NCAAB),
            tournament_k_factor=data.get("tournament_k_factor", 32),
        )
        model.ratings = dict(data.get("ratings", {}))
        model.conferences = dict(data.get("conferences", {}))
        model.games_played = dict(data.get("games_played", {}))
        model.matchup_history = data.get("matchup_history", {})
        return model


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def load_team_conferences(filepath: str) -> Dict[str, str]:
    """Load team conference mappings from a file.

    Args:
        filepath: Path to CSV with team_id, conference columns.

    Returns:
        Dictionary mapping team_id to conference.
    """
    df = pd.read_csv(filepath)
    return dict(zip(df["team_id"], df["conference"]))


def initialize_from_previous_season(
    model: NCAABEloModel,
    previous_ratings: Dict[str, float],
) -> None:
    """Initialize model from previous season's final ratings.

    Applies regression to mean and sets ratings.

    Args:
        model: NCAABEloModel to initialize.
        previous_ratings: Dictionary of team_id -> final Elo rating.
    """
    for team_id, rating in previous_ratings.items():
        regressed = rating - (rating - model.initial_rating) * model.regression_factor
        model.set_rating(team_id, regressed)
