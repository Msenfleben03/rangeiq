"""Tests for MLB Poisson run distribution model.

Covers:
- Score matrix construction (Poisson PMF outer product)
- Moneyline, run line, and total probability extraction
- TeamStrength dataclass defaults
- PoissonModel fit() with iterative team strength estimation
- PoissonModel predict() for all market types
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pathlib import Path

from models.sport_specific.mlb.poisson_model import (
    PoissonModel,
    build_score_matrix,
    moneyline_prob,
    run_line_prob,
    total_prob,
)

MLB_DB_PATH = Path(__file__).parent.parent / "data" / "mlb_data.db"


# =============================================================================
# Helpers
# =============================================================================


def _make_games_df() -> pd.DataFrame:
    """Create a synthetic 4-team, 24-game DataFrame for team-strength tests.

    Teams:
        100 — strong offense (6 rpg scored), ok defense (allows 4)
        101 — average (4.5 scored, allows 4.5)
        102 — weak offense (3 scored), good defense (allows 3)
        103 — average-ish (4 scored, allows 5)

    Each pair plays once home, once away (4 choose 2 = 6 pairs x 2 = 12 games).
    We duplicate the schedule to get 24 games for more stability.
    """
    rng = np.random.RandomState(42)
    teams = [100, 101, 102, 103]
    # Target offensive strength (runs scored per game)
    # Defensive quality is implicit: 100 allows 4, 101 allows 4.5, 102 allows 3, 103 allows 5
    team_off = {100: 6.0, 101: 4.5, 102: 3.0, 103: 4.0}

    rows = []
    game_pk = 700000
    for _rep in range(2):  # duplicate schedule
        for i, home in enumerate(teams):
            for away in teams:
                if home == away:
                    continue
                game_pk += 1
                # Add +0.3 home bonus so HFA > 1.0
                home_runs = max(0, int(round(team_off[home] + 0.3 + rng.normal(0, 0.5))))
                away_runs = max(0, int(round(team_off[away] + rng.normal(0, 0.5))))
                rows.append(
                    {
                        "game_pk": game_pk,
                        "game_date": pd.Timestamp("2024-06-01") + pd.Timedelta(days=len(rows)),
                        "home_team_id": home,
                        "away_team_id": away,
                        "home_score": home_runs,
                        "away_score": away_runs,
                    }
                )
    return pd.DataFrame(rows)


def _fit_model() -> tuple[PoissonModel, list[int]]:
    """Generate 30 synthetic teams with 1000 random Poisson games and fit a model.

    Returns the fitted model and the list of team IDs.
    """
    rng = np.random.RandomState(42)
    n_teams = 30
    team_ids = list(range(1, n_teams + 1))

    # Generate random attack/defense strengths
    true_attack = rng.uniform(0.7, 1.3, n_teams)
    true_defense = rng.uniform(0.7, 1.3, n_teams)
    league_avg = 4.5

    rows = []
    game_pk = 800000
    for _ in range(1000):
        home_idx = rng.randint(0, n_teams)
        away_idx = rng.randint(0, n_teams)
        while away_idx == home_idx:
            away_idx = rng.randint(0, n_teams)

        lam_h = league_avg * true_attack[home_idx] * true_defense[away_idx] * 1.04
        lam_a = league_avg * true_attack[away_idx] * true_defense[home_idx] / 1.04
        home_runs = rng.poisson(lam_h)
        away_runs = rng.poisson(lam_a)

        game_pk += 1
        rows.append(
            {
                "game_pk": game_pk,
                "game_date": pd.Timestamp("2024-04-01") + pd.Timedelta(days=len(rows)),
                "home_team_id": team_ids[home_idx],
                "away_team_id": team_ids[away_idx],
                "home_score": home_runs,
                "away_score": away_runs,
            }
        )

    df = pd.DataFrame(rows)
    model = PoissonModel(n_iter=50)
    model.fit(df)
    return model, team_ids


# =============================================================================
# TestScoreMatrix
# =============================================================================


class TestScoreMatrix:
    """Tests for build_score_matrix() pure math function."""

    def test_sums_to_one(self):
        """Score matrix probabilities sum to ~1.0."""
        matrix = build_score_matrix(4.5, 4.0)
        assert matrix.sum() == pytest.approx(1.0, abs=1e-4)

    def test_shape(self):
        """Matrix has shape (max_score+1, max_score+1)."""
        matrix = build_score_matrix(4.5, 4.0, max_score=15)
        assert matrix.shape == (16, 16)

    def test_symmetric_lambdas(self):
        """Equal lambdas produce a symmetric matrix."""
        matrix = build_score_matrix(4.0, 4.0)
        np.testing.assert_allclose(matrix, matrix.T, atol=1e-10)

    def test_higher_lambda_shifts_mass(self):
        """Higher lambda shifts probability mass toward higher scores."""
        matrix_low = build_score_matrix(2.0, 4.0)
        matrix_high = build_score_matrix(6.0, 4.0)

        # Mean home score should be higher with higher home lambda
        scores = np.arange(matrix_low.shape[0])
        mean_low = (matrix_low.sum(axis=1) * scores).sum()
        mean_high = (matrix_high.sum(axis=1) * scores).sum()
        assert mean_high > mean_low

    def test_zero_lambda_all_mass_at_zero(self):
        """Near-zero lambda concentrates 99%+ mass at score 0."""
        matrix = build_score_matrix(1e-12, 4.0)
        # Almost all mass in row 0 (home scores 0)
        assert matrix[0, :].sum() > 0.99


# =============================================================================
# TestMoneylineProb
# =============================================================================


class TestMoneylineProb:
    """Tests for moneyline_prob() extraction from score matrix."""

    def test_symmetric_gives_50_50(self):
        """Equal lambdas produce ~50% moneyline probability."""
        matrix = build_score_matrix(4.5, 4.5)
        prob = moneyline_prob(matrix)
        assert prob == pytest.approx(0.5, abs=0.01)

    def test_higher_home_lambda_favors_home(self):
        """Higher home lambda gives home win prob > 50%."""
        matrix = build_score_matrix(5.5, 3.5)
        prob = moneyline_prob(matrix)
        assert prob > 0.5

    def test_prob_between_0_and_1(self):
        """Moneyline probability is always in (0, 1)."""
        for lh, la in [(2.0, 6.0), (5.0, 5.0), (7.0, 3.0), (1.0, 1.0)]:
            matrix = build_score_matrix(lh, la)
            prob = moneyline_prob(matrix)
            assert 0 < prob < 1, f"Failed for lambdas ({lh}, {la}): prob={prob}"

    def test_excludes_ties(self):
        """Symmetric lambdas give ~50% because ties are excluded."""
        matrix = build_score_matrix(4.0, 4.0)
        prob = moneyline_prob(matrix)
        # With ties excluded, symmetric should be exactly 0.5
        assert prob == pytest.approx(0.5, abs=0.001)


# =============================================================================
# TestRunLineProb
# =============================================================================


class TestRunLineProb:
    """Tests for run_line_prob() extraction from score matrix."""

    def test_favorite_covers_less_than_ml(self):
        """Run line -1.5 probability is less than moneyline probability."""
        matrix = build_score_matrix(5.5, 3.5)
        ml = moneyline_prob(matrix)
        rl = run_line_prob(matrix, line=-1.5)
        assert rl < ml

    def test_underdog_covers_more_than_ml(self):
        """Run line +1.5 for underdog: P(home margin > 1.5) > ML prob."""
        matrix = build_score_matrix(3.5, 5.5)
        ml = moneyline_prob(matrix)
        rl = run_line_prob(matrix, line=1.5)
        assert rl > ml

    def test_prob_between_0_and_1(self):
        """Run line probability is always in (0, 1)."""
        for lh, la in [(3.0, 5.0), (5.0, 3.0), (4.5, 4.5)]:
            matrix = build_score_matrix(lh, la)
            prob = run_line_prob(matrix, line=-1.5)
            assert 0 < prob < 1, f"Failed for lambdas ({lh}, {la}): prob={prob}"


# =============================================================================
# TestTotalProb
# =============================================================================


class TestTotalProb:
    """Tests for total_prob() extraction from score matrix."""

    def test_high_total_favors_over(self):
        """High lambdas with low total line gives over > 80%."""
        matrix = build_score_matrix(6.0, 6.0)
        prob = total_prob(matrix, total=6.5)
        assert prob > 0.8

    def test_low_total_favors_under(self):
        """Low lambdas with high total line gives over < 20%."""
        matrix = build_score_matrix(2.0, 2.0)
        prob = total_prob(matrix, total=9.5)
        assert prob < 0.2

    def test_prob_between_0_and_1(self):
        """Total probability is always in (0, 1)."""
        for lh, la in [(3.0, 5.0), (5.0, 3.0), (4.5, 4.5)]:
            matrix = build_score_matrix(lh, la)
            prob = total_prob(matrix, total=8.5)
            assert 0 < prob < 1, f"Failed for lambdas ({lh}, {la}): prob={prob}"

    def test_returns_over_probability(self):
        """Expected total ~9 means over 8.5 should be > 50%."""
        matrix = build_score_matrix(4.5, 4.5)
        prob = total_prob(matrix, total=8.5)
        assert prob > 0.5


# =============================================================================
# TestTeamStrength
# =============================================================================


class TestTeamStrength:
    """Tests for PoissonModel.fit() iterative team strength estimation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Fit model on synthetic 4-team data."""
        self.df = _make_games_df()
        self.model = PoissonModel(n_iter=50)
        self.model.fit(self.df)

    def test_fit_returns_ratings_for_all_teams(self):
        """All 4 teams should have ratings after fit()."""
        assert len(self.model.team_ratings) == 4
        for tid in [100, 101, 102, 103]:
            assert tid in self.model.team_ratings

    def test_strong_offense_has_high_attack(self):
        """Team 100 (6 rpg) should have the highest attack rating."""
        attacks = {tid: ts.attack for tid, ts in self.model.team_ratings.items()}
        assert attacks[100] == max(attacks.values())

    def test_ratings_centered_near_one(self):
        """Mean attack and mean defense should be ~1.0 after normalization."""
        attacks = [ts.attack for ts in self.model.team_ratings.values()]
        defenses = [ts.defense for ts in self.model.team_ratings.values()]
        assert np.mean(attacks) == pytest.approx(1.0, abs=0.01)
        assert np.mean(defenses) == pytest.approx(1.0, abs=0.01)

    def test_home_advantage_positive(self):
        """Home field advantage should be > 1.0."""
        assert self.model.home_advantage > 1.0

    def test_league_avg_matches_data(self):
        """League average should approximate actual avg runs per team per game."""
        total_runs = self.df["home_score"].sum() + self.df["away_score"].sum()
        n_games = len(self.df)
        actual_avg = total_runs / (2 * n_games)
        assert self.model.league_avg == pytest.approx(actual_avg, abs=0.01)


# =============================================================================
# TestPoissonModelPredict
# =============================================================================


class TestPoissonModelPredict:
    """Tests for PoissonModel.predict() method."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Fit model on large synthetic dataset."""
        self.model, self.team_ids = _fit_model()

    def test_predict_returns_all_markets(self):
        """Prediction dict contains all expected keys."""
        pred = self.model.predict(self.team_ids[0], self.team_ids[1])
        expected_keys = {
            "lambda_home",
            "lambda_away",
            "moneyline_home",
            "run_line_home",
            "total_over",
        }
        assert expected_keys.issubset(pred.keys())

    def test_predict_moneyline_valid_range(self):
        """Moneyline probability is between 0 and 1."""
        pred = self.model.predict(self.team_ids[0], self.team_ids[1])
        assert 0 < pred["moneyline_home"] < 1

    def test_predict_with_park_factor(self):
        """Higher park factor increases both lambdas."""
        pred_neutral = self.model.predict(self.team_ids[0], self.team_ids[1], park_factor=1.0)
        pred_hitter = self.model.predict(self.team_ids[0], self.team_ids[1], park_factor=1.10)
        assert pred_hitter["lambda_home"] > pred_neutral["lambda_home"]
        assert pred_hitter["lambda_away"] > pred_neutral["lambda_away"]

    def test_predict_equal_teams_near_50(self):
        """Same team vs itself should give ~50-60% (HFA included)."""
        tid = self.team_ids[0]
        pred = self.model.predict(tid, tid)
        assert 0.45 < pred["moneyline_home"] < 0.65

    def test_predict_total_line(self):
        """Total over probability is between 0 and 1."""
        pred = self.model.predict(self.team_ids[0], self.team_ids[1], total_line=8.5)
        assert 0 < pred["total_over"] < 1

    def test_predict_run_line(self):
        """Run line probability is between 0 and 1."""
        pred = self.model.predict(self.team_ids[0], self.team_ids[1], run_line=-1.5)
        assert 0 < pred["run_line_home"] < 1


# =============================================================================
# TestFromDB (integration, requires real data)
# =============================================================================


@pytest.mark.slow
class TestFromDB:
    """Integration test with real mlb_data.db."""

    def test_from_db_loads_and_fits(self):
        """Load games from mlb_data.db and verify model fits 30 teams."""
        if not MLB_DB_PATH.exists():
            pytest.skip("mlb_data.db not found")

        model = PoissonModel.from_db(str(MLB_DB_PATH))
        assert len(model.team_ratings) == 30
        assert model.league_avg > 3.0

    def test_from_db_predict_nyy_vs_bos(self):
        """Predict NYY (147) vs BOS (111) — should be reasonable."""
        if not MLB_DB_PATH.exists():
            pytest.skip("mlb_data.db not found")

        model = PoissonModel.from_db(str(MLB_DB_PATH))
        result = model.predict(147, 111)
        assert 0.3 < result["moneyline_home"] < 0.7
        assert result["lambda_home"] > 2.0
        assert result["lambda_away"] > 2.0

    def test_from_db_single_season(self):
        """Fit on single season (2024 only)."""
        if not MLB_DB_PATH.exists():
            pytest.skip("mlb_data.db not found")

        model = PoissonModel.from_db(str(MLB_DB_PATH), seasons=[2024])
        assert len(model.team_ratings) == 30


# =============================================================================
# TestWalkForward
# =============================================================================


class TestWalkForward:
    """Test walk-forward backtesting logic."""

    def test_train_predict_split(self):
        """Train on season 1, predict season 2 -- accuracy should be 40-65%."""
        rng = np.random.RandomState(42)
        games = []
        teams = list(range(100, 110))
        for season in [2023, 2024]:
            for i in range(200):
                h, a = rng.choice(teams, 2, replace=False)
                games.append(
                    {
                        "game_pk": season * 1000 + i,
                        "game_date": f"{season}-06-15",
                        "season": season,
                        "home_team_id": int(h),
                        "away_team_id": int(a),
                        "home_score": int(rng.poisson(4.5)),
                        "away_score": int(rng.poisson(4.3)),
                    }
                )
        df = pd.DataFrame(games)

        train = df[df["season"] == 2023]
        model = PoissonModel()
        model.fit(train)

        test = df[df["season"] == 2024]
        correct = 0
        total = 0
        for _, row in test.iterrows():
            if row["home_score"] == row["away_score"]:
                continue
            result = model.predict(row["home_team_id"], row["away_team_id"])
            pred_home = result["moneyline_home"] > 0.5
            actual_home = row["home_score"] > row["away_score"]
            if pred_home == actual_home:
                correct += 1
            total += 1

        accuracy = correct / total if total > 0 else 0
        assert 0.40 < accuracy < 0.65
