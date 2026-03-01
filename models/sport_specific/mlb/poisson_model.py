"""Poisson run distribution model for MLB game predictions.

Core model that projects expected runs (lambda) per team and derives:
- Moneyline win probabilities
- Run line probabilities (+/-1.5)
- Total (over/under) probabilities

Architecture:
    1. Fit iterative team attack/defense strengths from historical game data
    2. Compute lambda_home and lambda_away from team strengths + HFA + park factor
    3. Build Poisson score matrix (0-0 through max_score-max_score)
    4. Sum matrix cells for each market type

References:
    - Research doc: docs/mlb/MODEL_ARCHITECTURE.md
    - Poisson approach: docs/mlb/research/market-strategies.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import poisson

logger = logging.getLogger(__name__)


# =============================================================================
# Pure Math Functions (stateless)
# =============================================================================


def build_score_matrix(
    lambda_home: float,
    lambda_away: float,
    max_score: int = 15,
) -> np.ndarray:
    """Build a joint probability matrix from two Poisson distributions.

    Matrix[i][j] = P(home scores i AND away scores j), assuming independence.

    Args:
        lambda_home: Expected runs for the home team (clamped to >= 1e-10).
        lambda_away: Expected runs for the away team (clamped to >= 1e-10).
        max_score: Maximum score to consider (inclusive). Matrix shape is
            (max_score + 1, max_score + 1).

    Returns:
        2D numpy array of joint probabilities. Sums to ~1.0 (truncation
        error for extreme lambdas).
    """
    lambda_home = max(lambda_home, 1e-10)
    lambda_away = max(lambda_away, 1e-10)

    scores = np.arange(max_score + 1)
    pmf_home = poisson.pmf(scores, lambda_home)
    pmf_away = poisson.pmf(scores, lambda_away)

    return np.outer(pmf_home, pmf_away)


def moneyline_prob(matrix: np.ndarray) -> float:
    """Extract home-win probability from a score matrix.

    Ties are excluded (baseball has no ties), so probabilities are normalized
    to P(home win) + P(away win) = 1.0.

    Args:
        matrix: Score matrix from build_score_matrix().

    Returns:
        Probability that the home team wins (0 to 1).
    """
    n = matrix.shape[0]
    home_win = 0.0
    away_win = 0.0

    for i in range(n):
        for j in range(n):
            if i > j:
                home_win += matrix[i, j]
            elif j > i:
                away_win += matrix[i, j]

    total = home_win + away_win
    if total == 0:
        return 0.5
    return home_win / total


def run_line_prob(matrix: np.ndarray, line: float = -1.5) -> float:
    """Extract run-line probability from a score matrix.

    Computes P(home_score - away_score > -line). For the standard home
    run line of -1.5, this means the home team must win by 2 or more.

    Args:
        matrix: Score matrix from build_score_matrix().
        line: Run line from the home team's perspective. Negative means
            the home team is favored (must win by more than |line|).

    Returns:
        Probability that the home team covers the run line (0 to 1).
    """
    n = matrix.shape[0]
    threshold = -line  # e.g., line=-1.5 -> need margin > 1.5
    covers = 0.0

    for i in range(n):
        for j in range(n):
            if (i - j) > threshold:
                covers += matrix[i, j]

    return float(covers)


def total_prob(matrix: np.ndarray, total: float = 8.5) -> float:
    """Extract over probability from a score matrix.

    Computes P(home_score + away_score > total).

    Args:
        matrix: Score matrix from build_score_matrix().
        total: The total line. Standard MLB totals are 7.5-10.5.

    Returns:
        Probability that the combined score goes over the total (0 to 1).
    """
    n = matrix.shape[0]
    over = 0.0

    for i in range(n):
        for j in range(n):
            if (i + j) > total:
                over += matrix[i, j]

    return float(over)


def compute_pitcher_adj(
    xfip: float | None,
    league_avg_xfip: float,
    ip: float,
    stabilization_ip: float = 50.0,
    clamp_low: float = 2.0,
    clamp_high: float = 7.0,
) -> float:
    """Compute a multiplicative lambda modifier from a pitcher's xFIP.

    The adjustment is the ratio of the pitcher's clamped xFIP to the league
    average, dampened toward 1.0 for low-IP pitchers.

    Args:
        xfip: Pitcher's xFIP from the prior season. None for unknown pitchers.
        league_avg_xfip: League-average xFIP for the prior season.
        ip: Innings pitched by the pitcher in the prior season.
        stabilization_ip: IP threshold for full weight (no dampening).
        clamp_low: Minimum allowed xFIP value (prevents unrealistic outliers).
        clamp_high: Maximum allowed xFIP value.

    Returns:
        Multiplicative adjustment factor. 1.0 means no effect, <1.0 means
        the pitcher suppresses runs, >1.0 means allows more runs.
    """
    if xfip is None or league_avg_xfip <= 0:
        return 1.0
    clamped = max(clamp_low, min(clamp_high, xfip))
    raw = clamped / league_avg_xfip
    weight = min(ip / stabilization_ip, 1.0) if stabilization_ip > 0 else 1.0
    return 1.0 + (raw - 1.0) * weight


# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class TeamStrength:
    """Offensive and defensive strength ratings for a single team.

    Attributes:
        attack: Offensive strength multiplier. >1.0 means scores more than
            the league average; <1.0 means scores less.
        defense: Defensive strength multiplier. >1.0 means allows more runs
            than average (bad defense); <1.0 means allows fewer (good defense).
        games: Number of games used to estimate these ratings.
    """

    attack: float = 1.0
    defense: float = 1.0
    games: int = 0


# =============================================================================
# PoissonModel
# =============================================================================


class PoissonModel:
    """Poisson-based MLB game prediction model.

    Estimates team-level attack and defense strengths from historical game
    results using an iterative algorithm (similar to Dixon-Coles without
    the correlation term). Produces lambda (expected runs) for each team
    and derives moneyline, run line, and total probabilities.

    Attributes:
        team_ratings: Mapping from team_id to TeamStrength.
        league_avg: Average runs scored per team per game.
        home_advantage: Home field advantage multiplier (typically ~1.03-1.05).
    """

    def __init__(self, hfa: float = 1.04, n_iter: int = 50) -> None:
        """Initialize the Poisson model.

        Args:
            hfa: Initial home field advantage multiplier. Overridden by
                the value computed from data in fit().
            n_iter: Number of iterations for the team strength estimation
                algorithm. 50 is typically sufficient for convergence.
        """
        self._default_hfa = hfa
        self._n_iter = n_iter
        self.team_ratings: dict[int, TeamStrength] = {}
        self.league_avg: float = 0.0
        self.home_advantage: float = hfa

    def fit(self, games: pd.DataFrame) -> None:
        """Estimate team strengths from historical game data.

        Uses an iterative algorithm:
        1. Compute league-wide average runs per team per game.
        2. Compute home field advantage from home vs away run rates.
        3. Iteratively update attack and defense ratings for each team,
           normalizing after each iteration so mean(attack) = mean(defense) = 1.0.

        Args:
            games: DataFrame with columns: game_pk, home_team_id, away_team_id,
                home_score, away_score. Each row is one completed game.

        Raises:
            ValueError: If the DataFrame is empty or missing required columns.
        """
        required_cols = {"home_team_id", "away_team_id", "home_score", "away_score"}
        missing = required_cols - set(games.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        if len(games) == 0:
            raise ValueError("Cannot fit on an empty DataFrame")

        # Compute league averages
        total_runs = games["home_score"].sum() + games["away_score"].sum()
        n_games = len(games)
        self.league_avg = total_runs / (2 * n_games)

        # Compute home field advantage from data
        home_rpg = games["home_score"].mean()
        away_rpg = games["away_score"].mean()
        if away_rpg > 0:
            self.home_advantage = home_rpg / away_rpg
        else:
            self.home_advantage = self._default_hfa

        # Identify all teams
        all_teams = set(games["home_team_id"].unique()) | set(games["away_team_id"].unique())

        # Build per-team game lists for efficient iteration
        team_home_games: dict[int, list[dict]] = {t: [] for t in all_teams}
        team_away_games: dict[int, list[dict]] = {t: [] for t in all_teams}

        for _, row in games.iterrows():
            ht = row["home_team_id"]
            at = row["away_team_id"]
            game_info = {
                "home_team_id": ht,
                "away_team_id": at,
                "home_score": row["home_score"],
                "away_score": row["away_score"],
            }
            team_home_games[ht].append(game_info)
            team_away_games[at].append(game_info)

        # Initialize ratings
        ratings: dict[int, TeamStrength] = {}
        for t in all_teams:
            n = len(team_home_games[t]) + len(team_away_games[t])
            ratings[t] = TeamStrength(attack=1.0, defense=1.0, games=n)

        hfa = self.home_advantage
        la = self.league_avg

        # Iterative estimation
        for _iteration in range(self._n_iter):
            new_attack: dict[int, float] = {}
            new_defense: dict[int, float] = {}

            for team in all_teams:
                # --- Attack estimation ---
                total_scored = 0.0
                expected_scored = 0.0

                for g in team_home_games[team]:
                    opp = g["away_team_id"]
                    total_scored += g["home_score"]
                    expected_scored += la * ratings[opp].defense * hfa

                for g in team_away_games[team]:
                    opp = g["home_team_id"]
                    total_scored += g["away_score"]
                    expected_scored += la * ratings[opp].defense / hfa

                if expected_scored > 0:
                    new_attack[team] = total_scored / expected_scored
                else:
                    new_attack[team] = 1.0

                # --- Defense estimation ---
                total_allowed = 0.0
                expected_allowed = 0.0

                for g in team_home_games[team]:
                    opp = g["away_team_id"]
                    total_allowed += g["away_score"]
                    # Opponent is away, so they get /HFA adjustment
                    expected_allowed += la * ratings[opp].attack / hfa

                for g in team_away_games[team]:
                    opp = g["home_team_id"]
                    total_allowed += g["home_score"]
                    # Opponent is home, so they get *HFA adjustment
                    expected_allowed += la * ratings[opp].attack * hfa

                if expected_allowed > 0:
                    new_defense[team] = total_allowed / expected_allowed
                else:
                    new_defense[team] = 1.0

            # Normalize so mean(attack) = 1.0 and mean(defense) = 1.0
            mean_att = np.mean(list(new_attack.values()))
            mean_def = np.mean(list(new_defense.values()))

            if mean_att > 0 and mean_def > 0:
                for team in all_teams:
                    ratings[team] = TeamStrength(
                        attack=new_attack[team] / mean_att,
                        defense=new_defense[team] / mean_def,
                        games=ratings[team].games,
                    )

        self.team_ratings = ratings
        logger.info(
            "Fitted Poisson model: %d teams, league_avg=%.2f, HFA=%.3f",
            len(ratings),
            self.league_avg,
            self.home_advantage,
        )

    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        park_factor: float = 1.0,
        total_line: float = 8.5,
        run_line: float = -1.5,
    ) -> dict:
        """Predict game outcome probabilities.

        Computes expected runs for each team and derives market probabilities
        from the Poisson score matrix.

        Args:
            home_team_id: ID of the home team (must exist in team_ratings).
            away_team_id: ID of the away team (must exist in team_ratings).
            park_factor: Park factor multiplier. >1.0 = hitter-friendly,
                <1.0 = pitcher-friendly. Applied equally to both teams.
            total_line: The total (over/under) line. Default 8.5.
            run_line: The run line from home perspective. Default -1.5.

        Returns:
            Dictionary with keys:
                - lambda_home: Expected home runs
                - lambda_away: Expected away runs
                - moneyline_home: P(home wins)
                - run_line_home: P(home covers run_line)
                - total_over: P(total > total_line)

        Raises:
            KeyError: If either team is not in team_ratings.
        """
        if home_team_id not in self.team_ratings:
            raise KeyError(f"Home team {home_team_id} not found in team_ratings")
        if away_team_id not in self.team_ratings:
            raise KeyError(f"Away team {away_team_id} not found in team_ratings")

        home = self.team_ratings[home_team_id]
        away = self.team_ratings[away_team_id]

        lambda_home = (
            self.league_avg * home.attack * away.defense * self.home_advantage * park_factor
        )
        lambda_away = (
            self.league_avg * away.attack * home.defense / self.home_advantage * park_factor
        )

        matrix = build_score_matrix(lambda_home, lambda_away)

        return {
            "lambda_home": lambda_home,
            "lambda_away": lambda_away,
            "moneyline_home": moneyline_prob(matrix),
            "run_line_home": run_line_prob(matrix, line=run_line),
            "total_over": total_prob(matrix, total=total_line),
        }

    @classmethod
    def from_db(
        cls,
        db_path: str = "data/mlb_data.db",
        seasons: list[int] | None = None,
    ) -> "PoissonModel":
        """Create and fit a model from the MLB database.

        Args:
            db_path: Path to mlb_data.db.
            seasons: List of seasons to include. None = all.

        Returns:
            Fitted PoissonModel instance.
        """
        import sqlite3

        conn = sqlite3.connect(db_path)
        query = (
            "SELECT game_pk, game_date, season, home_team_id, away_team_id, "
            "home_score, away_score FROM games WHERE status = 'final'"
        )
        if seasons:
            placeholders = ",".join("?" for _ in seasons)
            query += f" AND season IN ({placeholders})"
            df = pd.read_sql_query(query, conn, params=seasons)
        else:
            df = pd.read_sql_query(query, conn)
        conn.close()

        logger.info("Loaded %d games from %s", len(df), db_path)

        model = cls()
        model.fit(df)
        return model
