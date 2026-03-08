# MLB Poisson Model v1 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a team-strength Poisson model that estimates expected runs per team and derives moneyline, run line, and total probabilities from a score matrix.

**Architecture:** Iterative team strength estimation (attack/defense ratings per team, inspired by Dixon-Coles) trained on historical game results. Lambda for each team = `league_avg × attack × opp_defense × home_adj × park_factor`. Score matrix is the outer product of two Poisson PMFs, and market probabilities are sums over matrix regions.

**Tech Stack:** Python 3.11+, numpy, scipy.stats.poisson, pandas, sqlite3, pytest

---

## Data Available

- `data/mlb_data.db` — 7,511 games (2023-2025) with `home_score`, `away_score`, `home_team_id`, `away_team_id`
- 30 teams in `teams` table, 360 park factors in `park_factors` table (all default 1.0 for now)
- No starter IDs — team-level model only (pitcher adjustments are Phase 2)
- Avg ~4.48 runs/team/game, home win rate ~52-54%

## Constants

- `MLB_HFA = 1.04` — home teams score ~4% more runs (from ~52.8% home win rate)
- `MAX_SCORE = 15` — score matrix dimension (covers 99.9%+ of outcomes)
- `CONVERGENCE_ITER = 50` — iterations for attack/defense convergence
- `MIN_GAMES = 20` — minimum games for a team to have valid ratings

---

### Task 1: Poisson Math Layer — Score Matrix and Probability Extraction

Pure functions, no DB or state. The core math that everything else builds on.

**Files:**
- Create: `models/sport_specific/mlb/poisson_model.py` (replace skeleton)
- Create: `tests/test_mlb_poisson_model.py` (replace skeleton)

**Step 1: Write failing tests for score matrix and probability functions**

```python
# tests/test_mlb_poisson_model.py
"""Tests for MLB Poisson run distribution model."""

import numpy as np
import pytest


class TestScoreMatrix:
    """Tests for build_score_matrix()."""

    def test_sums_to_one(self):
        from models.sport_specific.mlb.poisson_model import build_score_matrix

        matrix = build_score_matrix(4.5, 4.0)
        assert abs(matrix.sum() - 1.0) < 1e-6

    def test_shape(self):
        from models.sport_specific.mlb.poisson_model import build_score_matrix

        matrix = build_score_matrix(4.5, 4.0, max_score=15)
        assert matrix.shape == (16, 16)  # 0..15 inclusive

    def test_symmetric_lambdas(self):
        from models.sport_specific.mlb.poisson_model import build_score_matrix

        matrix = build_score_matrix(4.0, 4.0)
        # P(home=i, away=j) == P(home=j, away=i)
        np.testing.assert_array_almost_equal(matrix, matrix.T)

    def test_higher_lambda_shifts_mass(self):
        from models.sport_specific.mlb.poisson_model import build_score_matrix

        m1 = build_score_matrix(3.0, 4.0)
        m2 = build_score_matrix(5.0, 4.0)
        # Higher home lambda → more mass on higher home scores
        home_mean_1 = sum(i * m1[i, :].sum() for i in range(m1.shape[0]))
        home_mean_2 = sum(i * m2[i, :].sum() for i in range(m2.shape[0]))
        assert home_mean_2 > home_mean_1

    def test_zero_lambda_all_mass_at_zero(self):
        from models.sport_specific.mlb.poisson_model import build_score_matrix

        matrix = build_score_matrix(0.001, 4.0)  # near-zero, not exactly 0
        # Almost all home score mass at 0
        assert matrix[0, :].sum() > 0.99


class TestMoneylineProb:
    """Tests for moneyline_prob()."""

    def test_symmetric_gives_50_50(self):
        from models.sport_specific.mlb.poisson_model import (
            build_score_matrix,
            moneyline_prob,
        )

        matrix = build_score_matrix(4.0, 4.0)
        prob = moneyline_prob(matrix)
        assert abs(prob - 0.5) < 0.01  # Within 1% of 50/50

    def test_higher_home_lambda_favors_home(self):
        from models.sport_specific.mlb.poisson_model import (
            build_score_matrix,
            moneyline_prob,
        )

        matrix = build_score_matrix(5.0, 3.5)
        prob = moneyline_prob(matrix)
        assert prob > 0.5

    def test_prob_between_0_and_1(self):
        from models.sport_specific.mlb.poisson_model import (
            build_score_matrix,
            moneyline_prob,
        )

        for lh, la in [(2.0, 6.0), (6.0, 2.0), (4.5, 4.5)]:
            matrix = build_score_matrix(lh, la)
            prob = moneyline_prob(matrix)
            assert 0 < prob < 1

    def test_excludes_ties(self):
        from models.sport_specific.mlb.poisson_model import (
            build_score_matrix,
            moneyline_prob,
        )

        matrix = build_score_matrix(4.0, 4.0)
        prob = moneyline_prob(matrix)
        # Moneyline excludes ties, so P(home) + P(away) should be < 1
        # before normalization. After normalization, should be ~0.5.
        # The function should normalize out ties.
        assert 0.49 < prob < 0.51


class TestRunLineProb:
    """Tests for run_line_prob()."""

    def test_favorite_covers_less_than_ml(self):
        from models.sport_specific.mlb.poisson_model import (
            build_score_matrix,
            moneyline_prob,
            run_line_prob,
        )

        matrix = build_score_matrix(5.0, 3.5)
        ml_prob = moneyline_prob(matrix)
        rl_prob = run_line_prob(matrix, line=-1.5)  # home -1.5
        assert rl_prob < ml_prob

    def test_underdog_covers_more_than_ml(self):
        from models.sport_specific.mlb.poisson_model import (
            build_score_matrix,
            moneyline_prob,
            run_line_prob,
        )

        matrix = build_score_matrix(3.5, 5.0)
        ml_prob = moneyline_prob(matrix)
        rl_prob = run_line_prob(matrix, line=1.5)  # home +1.5
        assert rl_prob > ml_prob

    def test_prob_between_0_and_1(self):
        from models.sport_specific.mlb.poisson_model import (
            build_score_matrix,
            run_line_prob,
        )

        matrix = build_score_matrix(4.5, 4.0)
        prob = run_line_prob(matrix, line=-1.5)
        assert 0 < prob < 1


class TestTotalProb:
    """Tests for total_prob()."""

    def test_high_total_favors_over(self):
        from models.sport_specific.mlb.poisson_model import (
            build_score_matrix,
            total_prob,
        )

        matrix = build_score_matrix(6.0, 5.5)  # ~11.5 expected
        prob = total_prob(matrix, total=8.5)
        assert prob > 0.8  # Over should be very likely

    def test_low_total_favors_under(self):
        from models.sport_specific.mlb.poisson_model import (
            build_score_matrix,
            total_prob,
        )

        matrix = build_score_matrix(3.0, 3.0)  # ~6.0 expected
        prob = total_prob(matrix, total=9.5)
        assert prob < 0.2  # Over should be unlikely

    def test_prob_between_0_and_1(self):
        from models.sport_specific.mlb.poisson_model import (
            build_score_matrix,
            total_prob,
        )

        matrix = build_score_matrix(4.5, 4.0)
        prob = total_prob(matrix, total=8.5)
        assert 0 < prob < 1

    def test_returns_over_probability(self):
        from models.sport_specific.mlb.poisson_model import (
            build_score_matrix,
            total_prob,
        )

        # With expected total ~9, P(over 8.5) should be > 50%
        matrix = build_score_matrix(4.5, 4.5)
        prob = total_prob(matrix, total=8.5)
        assert prob > 0.5
```

**Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_score_matrix'`

**Step 3: Implement the math functions**

```python
# models/sport_specific/mlb/poisson_model.py
"""Poisson run distribution model for MLB game predictions.

Core model that projects expected runs (lambda) per team and derives:
- Moneyline win probabilities
- Run line probabilities (+/- 1.5)
- Total (over/under) probabilities

Architecture:
    1. Compute lambda_home and lambda_away from team strength + context
    2. Build Poisson score matrix (0-0 through 15-15)
    3. Sum matrix cells for each market type
"""

from __future__ import annotations

import numpy as np
from scipy.stats import poisson

# Default max score for the matrix (0..MAX_SCORE inclusive)
MAX_SCORE = 15


def build_score_matrix(
    lambda_home: float,
    lambda_away: float,
    max_score: int = MAX_SCORE,
) -> np.ndarray:
    """Build joint probability matrix P(home=i, away=j).

    Args:
        lambda_home: Expected runs for home team.
        lambda_away: Expected runs for away team.
        max_score: Maximum score to model (inclusive). Matrix is (max_score+1)^2.

    Returns:
        2D numpy array of shape (max_score+1, max_score+1).
        matrix[i][j] = P(home scores i AND away scores j).
    """
    scores = np.arange(max_score + 1)
    home_pmf = poisson.pmf(scores, mu=max(lambda_home, 1e-10))
    away_pmf = poisson.pmf(scores, mu=max(lambda_away, 1e-10))
    return np.outer(home_pmf, away_pmf)


def moneyline_prob(matrix: np.ndarray) -> float:
    """Calculate home win probability from score matrix.

    Ties are excluded and probability is normalized (baseball has no ties).

    Args:
        matrix: Score matrix from build_score_matrix().

    Returns:
        P(home wins), normalized to exclude ties.
    """
    n = matrix.shape[0]
    home_win = sum(
        matrix[i, j] for i in range(n) for j in range(n) if i > j
    )
    away_win = sum(
        matrix[i, j] for i in range(n) for j in range(n) if i < j
    )
    total = home_win + away_win
    if total == 0:
        return 0.5
    return home_win / total


def run_line_prob(matrix: np.ndarray, line: float = -1.5) -> float:
    """Calculate probability of covering a run line.

    Args:
        matrix: Score matrix from build_score_matrix().
        line: Run line for home team. Negative = home favored.
            -1.5 means home must win by 2+.
            +1.5 means home can lose by 1 and still cover.

    Returns:
        P(home_score - away_score > -line) i.e. P(home covers).
    """
    n = matrix.shape[0]
    covers = sum(
        matrix[i, j]
        for i in range(n)
        for j in range(n)
        if (i - j) > -line  # home margin exceeds the line
    )
    return float(covers)


def total_prob(matrix: np.ndarray, total: float) -> float:
    """Calculate probability that combined score goes OVER a total.

    Args:
        matrix: Score matrix from build_score_matrix().
        total: The total line (e.g. 8.5).

    Returns:
        P(home_score + away_score > total).
    """
    n = matrix.shape[0]
    over = sum(
        matrix[i, j]
        for i in range(n)
        for j in range(n)
        if (i + j) > total
    )
    return float(over)
```

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py -v`
Expected: All 15 tests PASS

**Step 5: Commit**

```bash
git add models/sport_specific/mlb/poisson_model.py tests/test_mlb_poisson_model.py
git commit -m "feat(mlb): add Poisson score matrix and market probability functions"
```

---

### Task 2: Team Strength Estimation — Iterative Attack/Defense Ratings

Iterative method: each team gets attack (offensive) and defense ratings.
Lambda = `league_avg × team_attack × opponent_defense × HFA × park_factor`.
Ratings converge in ~20-50 iterations.

**Files:**
- Modify: `models/sport_specific/mlb/poisson_model.py`
- Modify: `tests/test_mlb_poisson_model.py`

**Step 1: Write failing tests for team strength estimation**

Add to `tests/test_mlb_poisson_model.py`:

```python
class TestTeamStrength:
    """Tests for iterative team strength estimation."""

    def _make_games_df(self):
        """Create a small synthetic games DataFrame."""
        import pandas as pd

        # 4 teams, 24 games (each pair plays ~4 games)
        games = []
        teams = [100, 101, 102, 103]
        # Team 100: strong offense (scores 6), ok defense (allows 4)
        # Team 101: avg (scores 4.5, allows 4.5)
        # Team 102: weak offense (scores 3), good defense (allows 3)
        # Team 103: avg (scores 4, allows 5)
        matchups = [
            (100, 101, 6, 4), (100, 102, 5, 3), (100, 103, 7, 4),
            (101, 100, 4, 5), (101, 102, 5, 2), (101, 103, 4, 4),
            (102, 100, 3, 6), (102, 101, 3, 5), (102, 103, 3, 4),
            (103, 100, 4, 7), (103, 101, 5, 4), (103, 102, 4, 2),
            # Repeat with slight variation
            (100, 101, 5, 5), (100, 102, 6, 2), (100, 103, 6, 5),
            (101, 100, 5, 6), (101, 102, 4, 3), (101, 103, 5, 3),
            (102, 100, 2, 5), (102, 101, 2, 4), (102, 103, 4, 5),
            (103, 100, 3, 6), (103, 101, 4, 5), (103, 102, 5, 3),
        ]
        for i, (h, a, hs, aws) in enumerate(matchups):
            games.append({
                "game_pk": 1000 + i,
                "game_date": f"2024-05-{(i % 28) + 1:02d}",
                "season": 2024,
                "home_team_id": h,
                "away_team_id": a,
                "home_score": hs,
                "away_score": aws,
            })
        return pd.DataFrame(games)

    def test_fit_returns_ratings_for_all_teams(self):
        from models.sport_specific.mlb.poisson_model import PoissonModel

        model = PoissonModel()
        df = self._make_games_df()
        model.fit(df)
        assert len(model.team_ratings) == 4
        for tid in [100, 101, 102, 103]:
            assert tid in model.team_ratings

    def test_strong_offense_has_high_attack(self):
        from models.sport_specific.mlb.poisson_model import PoissonModel

        model = PoissonModel()
        df = self._make_games_df()
        model.fit(df)
        # Team 100 scores the most → highest attack rating
        attacks = {tid: r.attack for tid, r in model.team_ratings.items()}
        assert attacks[100] == max(attacks.values())

    def test_ratings_centered_near_one(self):
        from models.sport_specific.mlb.poisson_model import PoissonModel

        model = PoissonModel()
        df = self._make_games_df()
        model.fit(df)
        attacks = [r.attack for r in model.team_ratings.values()]
        defenses = [r.defense for r in model.team_ratings.values()]
        # Average attack and defense should be near 1.0
        assert abs(np.mean(attacks) - 1.0) < 0.05
        assert abs(np.mean(defenses) - 1.0) < 0.05

    def test_home_advantage_positive(self):
        from models.sport_specific.mlb.poisson_model import PoissonModel

        model = PoissonModel()
        df = self._make_games_df()
        model.fit(df)
        assert model.home_advantage > 1.0

    def test_league_avg_matches_data(self):
        from models.sport_specific.mlb.poisson_model import PoissonModel

        model = PoissonModel()
        df = self._make_games_df()
        model.fit(df)
        expected_avg = (df["home_score"].sum() + df["away_score"].sum()) / (2 * len(df))
        assert abs(model.league_avg - expected_avg) < 0.01


class TestPoissonModelPredict:
    """Tests for PoissonModel.predict()."""

    def _fit_model(self):
        import pandas as pd
        from models.sport_specific.mlb.poisson_model import PoissonModel

        games = []
        np.random.seed(42)
        teams = list(range(100, 130))  # 30 teams
        for season in [2023, 2024]:
            for _ in range(500):
                h, a = np.random.choice(teams, 2, replace=False)
                hs = np.random.poisson(4.5)
                aws = np.random.poisson(4.3)
                games.append({
                    "game_pk": len(games),
                    "game_date": f"{season}-06-15",
                    "season": season,
                    "home_team_id": int(h),
                    "away_team_id": int(a),
                    "home_score": int(hs),
                    "away_score": int(aws),
                })
        model = PoissonModel()
        model.fit(pd.DataFrame(games))
        return model, teams

    def test_predict_returns_all_markets(self):
        model, teams = self._fit_model()
        result = model.predict(teams[0], teams[1])
        assert "moneyline_home" in result
        assert "run_line_home" in result
        assert "total_over" in result
        assert "lambda_home" in result
        assert "lambda_away" in result

    def test_predict_moneyline_valid_range(self):
        model, teams = self._fit_model()
        result = model.predict(teams[0], teams[1])
        assert 0 < result["moneyline_home"] < 1

    def test_predict_with_park_factor(self):
        model, teams = self._fit_model()
        r1 = model.predict(teams[0], teams[1], park_factor=1.0)
        r2 = model.predict(teams[0], teams[1], park_factor=1.2)
        # Higher park factor → more runs
        assert r2["lambda_home"] > r1["lambda_home"]
        assert r2["lambda_away"] > r1["lambda_away"]

    def test_predict_equal_teams_near_50(self):
        model, teams = self._fit_model()
        # Same team vs itself → should be close to 50%
        result = model.predict(teams[0], teams[0])
        # HFA gives home slight edge
        assert 0.45 < result["moneyline_home"] < 0.60

    def test_predict_total_line(self):
        model, teams = self._fit_model()
        result = model.predict(teams[0], teams[1], total_line=8.5)
        assert "total_over" in result
        assert 0 < result["total_over"] < 1

    def test_predict_run_line(self):
        model, teams = self._fit_model()
        result = model.predict(teams[0], teams[1], run_line=-1.5)
        assert "run_line_home" in result
        assert 0 < result["run_line_home"] < 1
```

**Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py::TestTeamStrength -v`
Expected: FAIL — `ImportError: cannot import name 'PoissonModel'`

**Step 3: Implement PoissonModel with iterative team strength**

Add to `models/sport_specific/mlb/poisson_model.py`:

```python
import logging
from dataclasses import dataclass
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Model defaults
DEFAULT_HFA = 1.04  # ~54% home win rate in MLB
CONVERGENCE_ITER = 50
MIN_GAMES = 20


@dataclass
class TeamStrength:
    """Attack and defense ratings for a team."""

    attack: float = 1.0   # >1 = scores more than average
    defense: float = 1.0  # >1 = allows more than average (bad defense)
    games: int = 0


class PoissonModel:
    """Team-strength Poisson model for MLB game predictions.

    Estimates per-team attack/defense ratings from historical results
    using iterative convergence. Generates win probabilities and
    market-specific probabilities via Poisson score matrix.

    Attributes:
        team_ratings: Dict mapping team_id to TeamStrength.
        league_avg: Average runs per team per game.
        home_advantage: Multiplicative HFA (>1 = home boost).
    """

    def __init__(self, hfa: float = DEFAULT_HFA, n_iter: int = CONVERGENCE_ITER):
        self.team_ratings: Dict[int, TeamStrength] = {}
        self.league_avg: float = 4.5
        self.home_advantage: float = hfa
        self._n_iter = n_iter

    def fit(self, games: pd.DataFrame) -> None:
        """Estimate team attack/defense ratings from game results.

        Uses iterative method: each iteration recomputes attack and defense
        relative to opponent strength, until convergence.

        Args:
            games: DataFrame with columns: home_team_id, away_team_id,
                   home_score, away_score. One row per game.
        """
        total_runs = games["home_score"].sum() + games["away_score"].sum()
        n_games = len(games)
        self.league_avg = total_runs / (2 * n_games)

        # Compute HFA from data
        home_rpg = games["home_score"].mean()
        away_rpg = games["away_score"].mean()
        if away_rpg > 0:
            self.home_advantage = home_rpg / away_rpg

        # Collect all team IDs
        team_ids = set(games["home_team_id"].unique()) | set(
            games["away_team_id"].unique()
        )

        # Initialize ratings
        for tid in team_ids:
            self.team_ratings[tid] = TeamStrength()

        # Count games per team
        for tid in team_ids:
            mask = (games["home_team_id"] == tid) | (games["away_team_id"] == tid)
            self.team_ratings[tid].games = int(mask.sum())

        # Iterative convergence
        for _ in range(self._n_iter):
            new_attack = {}
            new_defense = {}

            for tid in team_ids:
                # Games where this team is home
                home_mask = games["home_team_id"] == tid
                home_games = games[home_mask]
                # Games where this team is away
                away_mask = games["away_team_id"] == tid
                away_games = games[away_mask]

                # Attack: runs scored adjusted for opponent defense
                scored_home = home_games["home_score"].sum()
                scored_away = away_games["away_score"].sum()
                total_scored = scored_home + scored_away

                # Expected scoring based on opponent defense
                opp_def_home = sum(
                    self.team_ratings[opp].defense
                    for opp in home_games["away_team_id"]
                )
                opp_def_away = sum(
                    self.team_ratings[opp].defense
                    for opp in away_games["home_team_id"]
                )

                n_team_games = len(home_games) + len(away_games)
                if n_team_games == 0:
                    new_attack[tid] = 1.0
                    new_defense[tid] = 1.0
                    continue

                # Expected runs scored if average team vs these opponents
                expected_scored = self.league_avg * (
                    opp_def_home * self.home_advantage
                    + opp_def_away / self.home_advantage
                )

                if expected_scored > 0:
                    new_attack[tid] = total_scored / expected_scored
                else:
                    new_attack[tid] = 1.0

                # Defense: runs allowed adjusted for opponent attack
                allowed_home = home_games["away_score"].sum()
                allowed_away = away_games["home_score"].sum()
                total_allowed = allowed_home + allowed_away

                opp_att_home = sum(
                    self.team_ratings[opp].attack
                    for opp in home_games["away_team_id"]
                )
                opp_att_away = sum(
                    self.team_ratings[opp].attack
                    for opp in away_games["home_team_id"]
                )

                expected_allowed = self.league_avg * (
                    opp_att_home / self.home_advantage
                    + opp_att_away * self.home_advantage
                )

                if expected_allowed > 0:
                    new_defense[tid] = total_allowed / expected_allowed
                else:
                    new_defense[tid] = 1.0

            # Normalize so mean attack = 1.0 and mean defense = 1.0
            mean_att = np.mean(list(new_attack.values()))
            mean_def = np.mean(list(new_defense.values()))

            for tid in team_ids:
                self.team_ratings[tid].attack = new_attack[tid] / mean_att
                self.team_ratings[tid].defense = new_defense[tid] / mean_def

    def predict(
        self,
        home_team_id: int,
        away_team_id: int,
        park_factor: float = 1.0,
        total_line: float = 8.5,
        run_line: float = -1.5,
    ) -> Dict[str, float]:
        """Generate predictions for a game.

        Args:
            home_team_id: Home team ID.
            away_team_id: Away team ID.
            park_factor: Park run factor (1.0 = neutral).
            total_line: Total line for over/under (default 8.5).
            run_line: Run line for home team (default -1.5).

        Returns:
            Dict with keys: lambda_home, lambda_away, moneyline_home,
            run_line_home, total_over.
        """
        home_r = self.team_ratings.get(home_team_id, TeamStrength())
        away_r = self.team_ratings.get(away_team_id, TeamStrength())

        lambda_home = (
            self.league_avg
            * home_r.attack
            * away_r.defense
            * self.home_advantage
            * park_factor
        )
        lambda_away = (
            self.league_avg
            * away_r.attack
            * home_r.defense
            / self.home_advantage
            * park_factor
        )

        matrix = build_score_matrix(lambda_home, lambda_away)

        return {
            "lambda_home": lambda_home,
            "lambda_away": lambda_away,
            "moneyline_home": moneyline_prob(matrix),
            "run_line_home": run_line_prob(matrix, line=run_line),
            "total_over": total_prob(matrix, total=total_line),
        }
```

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py -v`
Expected: All tests PASS (math tests + team strength + predict)

**Step 5: Run ruff**

Run: `venv/Scripts/python.exe -m ruff check models/sport_specific/mlb/poisson_model.py tests/test_mlb_poisson_model.py --fix`
Run: `venv/Scripts/python.exe -m ruff format models/sport_specific/mlb/poisson_model.py tests/test_mlb_poisson_model.py`

**Step 6: Commit**

```bash
git add models/sport_specific/mlb/poisson_model.py tests/test_mlb_poisson_model.py
git commit -m "feat(mlb): add PoissonModel with team-strength estimation"
```

---

### Task 3: Config Constants + DB Integration Helper

Add MLB config to constants.py and a helper to load games from mlb_data.db.

**Files:**
- Modify: `config/constants.py` (add MLBModelConfig)
- Modify: `models/sport_specific/mlb/poisson_model.py` (add `from_db` classmethod)
- Modify: `tests/test_mlb_poisson_model.py` (add DB integration test)

**Step 1: Add MLB config constants**

Add to bottom of `config/constants.py`:

```python
# =============================================================================
# MLB POISSON MODEL CONFIGURATION
# =============================================================================


@dataclass
class MLBModelConfig:
    """MLB Poisson model configuration."""

    # Home field advantage multiplier (~54% home win rate)
    HFA: float = 1.04

    # Iterative convergence parameters
    CONVERGENCE_ITERATIONS: int = 50
    MIN_GAMES_FOR_RATING: int = 20

    # Score matrix dimension (0..MAX_SCORE inclusive)
    MAX_SCORE: int = 15

    # Minimum edge for paper betting
    MIN_EDGE: float = 0.05  # 5% — more liquid market than NCAAB

    # Default total line when none provided
    DEFAULT_TOTAL_LINE: float = 8.5

    # Default run line
    DEFAULT_RUN_LINE: float = -1.5

    # Database path
    DB_PATH: str = "data/mlb_data.db"


MLB_MODEL = MLBModelConfig()
```

**Step 2: Add from_db classmethod**

Add to `PoissonModel` in `models/sport_specific/mlb/poisson_model.py`:

```python
@classmethod
def from_db(
    cls,
    db_path: str = "data/mlb_data.db",
    seasons: Optional[list[int]] = None,
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
    query = "SELECT game_pk, game_date, season, home_team_id, away_team_id, home_score, away_score FROM games WHERE status = 'final'"
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
```

**Step 3: Write integration test (marked slow)**

Add to `tests/test_mlb_poisson_model.py`:

```python
@pytest.mark.slow
class TestFromDB:
    """Integration test with real mlb_data.db."""

    def test_from_db_loads_and_fits(self):
        from pathlib import Path
        from models.sport_specific.mlb.poisson_model import PoissonModel

        db_path = Path(__file__).parent.parent / "data" / "mlb_data.db"
        if not db_path.exists():
            pytest.skip("mlb_data.db not found")

        model = PoissonModel.from_db(str(db_path))
        assert len(model.team_ratings) == 30
        assert model.league_avg > 3.0

        # Predict NYY vs BOS
        result = model.predict(147, 111)
        assert 0.3 < result["moneyline_home"] < 0.7
```

**Step 4: Run tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py -v` (fast tests only)
Run: `venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py -v --runslow` (include DB test)

**Step 5: Ruff + Commit**

```bash
ruff check config/constants.py models/sport_specific/mlb/poisson_model.py --fix
ruff format config/constants.py models/sport_specific/mlb/poisson_model.py
git add config/constants.py models/sport_specific/mlb/poisson_model.py tests/test_mlb_poisson_model.py
git commit -m "feat(mlb): add MLB config constants and DB integration"
```

---

### Task 4: Walk-Forward Backtest Script

Train on season N, predict season N+1. Calculate moneyline accuracy and log-loss.
No odds comparison yet (MLB odds not fetched) — just model quality metrics.

**Files:**
- Modify: `scripts/mlb_backtest.py` (replace skeleton)
- Modify: `tests/test_mlb_poisson_model.py` (add walk-forward test)

**Step 1: Write walk-forward test**

Add to `tests/test_mlb_poisson_model.py`:

```python
class TestWalkForward:
    """Test walk-forward backtesting logic."""

    def test_train_predict_split(self):
        """Train on 2023, predict 2024 games."""
        import pandas as pd
        from models.sport_specific.mlb.poisson_model import PoissonModel

        np.random.seed(42)
        games = []
        teams = list(range(100, 110))
        for season in [2023, 2024]:
            for i in range(200):
                h, a = np.random.choice(teams, 2, replace=False)
                games.append({
                    "game_pk": season * 1000 + i,
                    "game_date": f"{season}-06-15",
                    "season": season,
                    "home_team_id": int(h),
                    "away_team_id": int(a),
                    "home_score": int(np.random.poisson(4.5)),
                    "away_score": int(np.random.poisson(4.3)),
                })
        df = pd.DataFrame(games)

        # Train on 2023
        train = df[df["season"] == 2023]
        model = PoissonModel()
        model.fit(train)

        # Predict 2024
        test = df[df["season"] == 2024]
        correct = 0
        total = 0
        for _, row in test.iterrows():
            result = model.predict(row["home_team_id"], row["away_team_id"])
            pred_home = result["moneyline_home"] > 0.5
            actual_home = row["home_score"] > row["away_score"]
            if row["home_score"] != row["away_score"]:
                if pred_home == actual_home:
                    correct += 1
                total += 1

        # With random data, accuracy should be ~50-55% (HFA gives slight edge)
        accuracy = correct / total if total > 0 else 0
        assert 0.40 < accuracy < 0.65
```

**Step 2: Implement backtest script**

```python
# scripts/mlb_backtest.py
"""Walk-forward backtesting for MLB Poisson model.

Usage:
    python scripts/mlb_backtest.py                    # Train 2023-2024, test 2025
    python scripts/mlb_backtest.py --test-season 2024 # Train 2023, test 2024
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.sport_specific.mlb.poisson_model import PoissonModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "mlb_data.db"


def load_games(db_path: Path) -> pd.DataFrame:
    """Load all final games from the database."""
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql_query(
        "SELECT game_pk, game_date, season, home_team_id, away_team_id, "
        "home_score, away_score FROM games WHERE status = 'final'",
        conn,
    )
    conn.close()
    return df


def run_backtest(games: pd.DataFrame, test_season: int) -> pd.DataFrame:
    """Run walk-forward backtest: train on all seasons before test_season.

    Args:
        games: All games DataFrame.
        test_season: Season to test on.

    Returns:
        DataFrame with predictions and results for test season.
    """
    train = games[games["season"] < test_season]
    test = games[games["season"] == test_season].copy()

    if len(train) == 0:
        logger.error("No training data for test season %d", test_season)
        return pd.DataFrame()

    logger.info(
        "Training on %d games (%s), testing on %d games (%d)",
        len(train),
        sorted(train["season"].unique()),
        len(test),
        test_season,
    )

    model = PoissonModel()
    model.fit(train)

    results = []
    for _, row in test.iterrows():
        pred = model.predict(
            int(row["home_team_id"]),
            int(row["away_team_id"]),
        )

        home_won = row["home_score"] > row["away_score"]
        if row["home_score"] == row["away_score"]:
            continue  # Skip ties (shouldn't exist in MLB)

        results.append({
            "game_pk": row["game_pk"],
            "game_date": row["game_date"],
            "home_team_id": row["home_team_id"],
            "away_team_id": row["away_team_id"],
            "home_score": row["home_score"],
            "away_score": row["away_score"],
            "pred_home_prob": pred["moneyline_home"],
            "pred_lambda_home": pred["lambda_home"],
            "pred_lambda_away": pred["lambda_away"],
            "home_won": home_won,
            "correct": (pred["moneyline_home"] > 0.5) == home_won,
        })

    return pd.DataFrame(results)


def print_report(results: pd.DataFrame, test_season: int) -> None:
    """Print backtest summary statistics."""
    if results.empty:
        print(f"No results for season {test_season}")
        return

    n = len(results)
    correct = results["correct"].sum()
    accuracy = correct / n

    # Log loss
    eps = 1e-10
    probs = results["pred_home_prob"].clip(eps, 1 - eps)
    actuals = results["home_won"].astype(float)
    log_loss = -(actuals * np.log(probs) + (1 - actuals) * np.log(1 - probs)).mean()

    # Calibration: bin predictions and compare to actual win rate
    results["prob_bin"] = pd.cut(results["pred_home_prob"], bins=10)
    cal = results.groupby("prob_bin", observed=True).agg(
        pred_avg=("pred_home_prob", "mean"),
        actual_avg=("home_won", "mean"),
        count=("home_won", "count"),
    )

    print(f"\n{'='*60}")
    print(f"MLB Poisson Model v1 — Backtest {test_season}")
    print(f"{'='*60}")
    print(f"Games:      {n}")
    print(f"Accuracy:   {accuracy:.1%} ({correct}/{n})")
    print(f"Log Loss:   {log_loss:.4f}")
    print(f"\nCalibration:")
    print(f"{'Predicted':>12} {'Actual':>10} {'Count':>8}")
    print(f"{'-'*32}")
    for _, row in cal.iterrows():
        print(f"{row['pred_avg']:>12.1%} {row['actual_avg']:>10.1%} {int(row['count']):>8}")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="MLB Poisson model walk-forward backtest")
    parser.add_argument(
        "--test-season", type=int, default=2025,
        help="Season to test on (trains on all prior seasons)",
    )
    parser.add_argument(
        "--db-path", type=str, default=str(DB_PATH),
        help="Path to mlb_data.db",
    )
    args = parser.parse_args()

    games = load_games(Path(args.db_path))
    logger.info("Loaded %d games across seasons %s", len(games), sorted(games["season"].unique()))

    results = run_backtest(games, args.test_season)
    print_report(results, args.test_season)

    # Save results
    out_dir = PROJECT_ROOT / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"mlb_backtest_{args.test_season}.parquet"
    results.to_parquet(out_path, index=False)
    logger.info("Saved results to %s", out_path)


if __name__ == "__main__":
    main()
```

**Step 3: Run tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py -v`
Expected: All tests PASS

**Step 4: Run backtest on real data**

Run: `venv/Scripts/python.exe scripts/mlb_backtest.py --test-season 2025`
Expected: Accuracy ~53-56%, log loss ~0.68-0.69 (team-strength-only, no pitcher info)

**Step 5: Ruff + Commit**

```bash
ruff check scripts/mlb_backtest.py --fix && ruff format scripts/mlb_backtest.py
git add scripts/mlb_backtest.py tests/test_mlb_poisson_model.py
git commit -m "feat(mlb): add walk-forward backtest script for Poisson model"
```

---

### Task 5: Run Full Validation and Update Session State

**Step 1: Run full test suite**

Run: `venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py -v --runslow`
Expected: All tests PASS

**Step 2: Run backtest for all test seasons**

```bash
venv/Scripts/python.exe scripts/mlb_backtest.py --test-season 2024
venv/Scripts/python.exe scripts/mlb_backtest.py --test-season 2025
```

Record accuracy and log loss for each season.

**Step 3: Update session state**

Update `.claude/session-state.md` with results and next steps.

**Step 4: Final commit**

If any changes remain, commit them.

---

## Expected Outcomes

- **Accuracy**: ~53-56% moneyline accuracy (team-strength-only baseline)
- **Log loss**: ~0.68-0.69 (Poisson should beat coin flip 0.693)
- **Calibration**: Predicted probabilities should roughly match actual win rates per bin
- **Test count**: ~25+ tests in `test_mlb_poisson_model.py`

## Next Steps (Not in This Plan)

- Backfill starter IDs on games (MLB Stats API boxscore endpoint)
- Add pitcher adjustment to lambda (pitcher quality vs league avg)
- Fetch MLB odds for CLV comparison
- Extend to F5 innings (requires starter/bullpen split)
- Weather enrichment for totals market
