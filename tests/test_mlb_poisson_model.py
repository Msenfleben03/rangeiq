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
        assert "lambda_f5_home" in pred
        assert "lambda_f5_away" in pred
        assert "f5_moneyline_home" in pred
        assert 0 < pred["f5_moneyline_home"] < 1

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

    def test_predict_with_pitcher_adj_good_away_pitcher(self):
        """Good away pitcher (adj 0.8) reduces lambda_home."""
        pred_base = self.model.predict(self.team_ids[0], self.team_ids[1])
        pred_adj = self.model.predict(self.team_ids[0], self.team_ids[1], away_pitcher_adj=0.8)
        assert pred_adj["lambda_home"] < pred_base["lambda_home"]
        assert pred_adj["lambda_away"] == pytest.approx(pred_base["lambda_away"], abs=1e-6)

    def test_predict_with_pitcher_adj_bad_home_pitcher(self):
        """Bad home pitcher (adj 1.3) increases lambda_away."""
        pred_base = self.model.predict(self.team_ids[0], self.team_ids[1])
        pred_adj = self.model.predict(self.team_ids[0], self.team_ids[1], home_pitcher_adj=1.3)
        assert pred_adj["lambda_away"] > pred_base["lambda_away"]
        assert pred_adj["lambda_home"] == pytest.approx(pred_base["lambda_home"], abs=1e-6)

    def test_predict_with_both_pitcher_adjs(self):
        """Both adjustments applied simultaneously."""
        pred_base = self.model.predict(self.team_ids[0], self.team_ids[1])
        pred_adj = self.model.predict(
            self.team_ids[0],
            self.team_ids[1],
            home_pitcher_adj=1.2,
            away_pitcher_adj=0.9,
        )
        assert pred_adj["lambda_home"] < pred_base["lambda_home"]  # away pitcher good
        assert pred_adj["lambda_away"] > pred_base["lambda_away"]  # home pitcher bad

    def test_predict_pitcher_adj_one_means_no_change(self):
        """Pitcher adj 1.0 produces identical results to no adjustment."""
        pred_base = self.model.predict(self.team_ids[0], self.team_ids[1])
        pred_adj = self.model.predict(
            self.team_ids[0],
            self.team_ids[1],
            home_pitcher_adj=1.0,
            away_pitcher_adj=1.0,
        )
        assert pred_adj["lambda_home"] == pytest.approx(pred_base["lambda_home"], abs=1e-10)
        assert pred_adj["lambda_away"] == pytest.approx(pred_base["lambda_away"], abs=1e-10)

    def test_f5_lambda_is_scaled_from_full_game(self):
        """lambda_f5 = lambda_full * F5_SCALE (≈ 0.567)."""
        from models.sport_specific.mlb.poisson_model import _F5_SCALE

        result = self.model.predict(self.team_ids[0], self.team_ids[1])

        assert abs(result["lambda_f5_home"] - result["lambda_home"] * _F5_SCALE) < 1e-9
        assert abs(result["lambda_f5_away"] - result["lambda_away"] * _F5_SCALE) < 1e-9

    def test_f5_prob_closer_to_half_than_full_game(self):
        """F5 probability is closer to 0.5 than full-game (smaller expected scoring gap)."""
        result = self.model.predict(self.team_ids[0], self.team_ids[1])

        full_game_dist = abs(result["moneyline_home"] - 0.5)
        f5_dist = abs(result["f5_moneyline_home"] - 0.5)
        assert f5_dist <= full_game_dist

    def test_f5_prob_within_valid_range(self):
        """f5_moneyline_home is a valid probability."""
        result = self.model.predict(self.team_ids[0], self.team_ids[1])

        assert 0.0 < result["f5_moneyline_home"] < 1.0

    def test_f5_prob_independent_of_total_line_param(self):
        """f5_moneyline_home is not affected by total_line parameter (moneyline market)."""
        r1 = self.model.predict(self.team_ids[0], self.team_ids[1], total_line=8.5)
        r2 = self.model.predict(self.team_ids[0], self.team_ids[1], total_line=10.5)

        assert r1["f5_moneyline_home"] == r2["f5_moneyline_home"]


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

    def test_calibrated_backtest_runs(self):
        """Calibrated backtest completes and returns valid probabilities."""
        from scripts.mlb_backtest import run_backtest

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
                        "home_starter_id": None,
                        "away_starter_id": None,
                    }
                )
        df = pd.DataFrame(games)

        results = run_backtest(df, test_season=2024, calibrated=True)
        assert len(results) > 0
        assert "pred_home_prob" in results.columns
        assert "pred_home_prob_raw" in results.columns
        # Calibrated probs should still be valid probabilities
        assert results["pred_home_prob"].between(0, 1).all()
        assert results["pred_home_prob_raw"].between(0, 1).all()


# =============================================================================
# TestComputePitcherAdj
# =============================================================================


class TestComputePitcherAdj:
    """Tests for compute_pitcher_adj() pure function."""

    def test_league_average_pitcher_returns_one(self):
        """xFIP == league avg => adj == 1.0."""
        from models.sport_specific.mlb.poisson_model import compute_pitcher_adj

        result = compute_pitcher_adj(xfip=4.2, league_avg_xfip=4.2, ip=100.0)
        assert result == pytest.approx(1.0, abs=1e-6)

    def test_elite_pitcher_below_one(self):
        """xFIP 3.0, avg 4.2 => adj < 1.0 (reduces opposing runs)."""
        from models.sport_specific.mlb.poisson_model import compute_pitcher_adj

        result = compute_pitcher_adj(xfip=3.0, league_avg_xfip=4.2, ip=100.0)
        assert result == pytest.approx(3.0 / 4.2, abs=1e-6)

    def test_bad_pitcher_above_one(self):
        """xFIP 5.5, avg 4.2 => adj > 1.0 (increases opposing runs)."""
        from models.sport_specific.mlb.poisson_model import compute_pitcher_adj

        result = compute_pitcher_adj(xfip=5.5, league_avg_xfip=4.2, ip=100.0)
        assert result == pytest.approx(5.5 / 4.2, abs=1e-6)

    def test_low_ip_dampened_toward_one(self):
        """25 IP / 50 stab = 50% weight toward 1.0."""
        from models.sport_specific.mlb.poisson_model import compute_pitcher_adj

        result = compute_pitcher_adj(xfip=3.0, league_avg_xfip=4.2, ip=25.0)
        raw = 3.0 / 4.2
        expected = 1.0 + (raw - 1.0) * 0.5  # 50% dampening
        assert result == pytest.approx(expected, abs=1e-6)

    def test_zero_ip_returns_one(self):
        """0 IP => full dampening => adj == 1.0."""
        from models.sport_specific.mlb.poisson_model import compute_pitcher_adj

        result = compute_pitcher_adj(xfip=3.0, league_avg_xfip=4.2, ip=0.0)
        assert result == pytest.approx(1.0, abs=1e-6)

    def test_none_xfip_returns_one(self):
        """Unknown pitcher (None xFIP) => adj == 1.0."""
        from models.sport_specific.mlb.poisson_model import compute_pitcher_adj

        result = compute_pitcher_adj(xfip=None, league_avg_xfip=4.2, ip=100.0)
        assert result == pytest.approx(1.0, abs=1e-6)

    def test_xfip_clamped_low(self):
        """xFIP 0.5 clamped to 2.0."""
        from models.sport_specific.mlb.poisson_model import compute_pitcher_adj

        result = compute_pitcher_adj(xfip=0.5, league_avg_xfip=4.2, ip=100.0)
        assert result == pytest.approx(2.0 / 4.2, abs=1e-6)

    def test_xfip_clamped_high(self):
        """xFIP 12.0 clamped to 7.0."""
        from models.sport_specific.mlb.poisson_model import compute_pitcher_adj

        result = compute_pitcher_adj(xfip=12.0, league_avg_xfip=4.2, ip=100.0)
        assert result == pytest.approx(7.0 / 4.2, abs=1e-6)

    def test_above_stabilization_ip_full_weight(self):
        """50 IP and 200 IP should both give full weight (no dampening)."""
        from models.sport_specific.mlb.poisson_model import compute_pitcher_adj

        result_50 = compute_pitcher_adj(xfip=3.0, league_avg_xfip=4.2, ip=50.0)
        result_200 = compute_pitcher_adj(xfip=3.0, league_avg_xfip=4.2, ip=200.0)
        assert result_50 == pytest.approx(result_200, abs=1e-6)

    def test_league_avg_zero_returns_one(self):
        """Edge case: league avg xFIP = 0 => adj == 1.0."""
        from models.sport_specific.mlb.poisson_model import compute_pitcher_adj

        result = compute_pitcher_adj(xfip=3.0, league_avg_xfip=0.0, ip=100.0)
        assert result == pytest.approx(1.0, abs=1e-6)


# =============================================================================
# TestPlattCalibration
# =============================================================================


class TestPlattCalibration:
    """Tests for PoissonModel Platt calibration methods."""

    def test_uncalibrated_returns_raw(self):
        """calibrate_prob() returns raw prob when uncalibrated."""
        model, team_ids = _fit_model()
        pred = model.predict(team_ids[0], team_ids[1])
        raw = pred["moneyline_home"]
        assert model.calibrate_prob(raw) == raw

    def test_is_calibrated_default_false(self):
        """New model is not calibrated."""
        model = PoissonModel()
        assert model.is_calibrated is False

    def test_calibrate_sets_is_calibrated(self):
        """After calibrate(), is_calibrated is True."""
        model, _ = _fit_model()
        probs = np.array([0.4, 0.5, 0.6, 0.7])
        outcomes = np.array([0, 0, 1, 1])
        model.calibrate(probs, outcomes)
        assert model.is_calibrated is True

    def test_calibrate_changes_probabilities(self):
        """Calibrated prob differs from raw prob for non-trivial input."""
        model, _ = _fit_model()
        # Create biased training data: model says 0.7 but actual win rate is ~50%
        probs = np.array([0.7] * 50 + [0.3] * 50)
        outcomes = np.array([1] * 25 + [0] * 25 + [1] * 25 + [0] * 25)
        model.calibrate(probs, outcomes)
        # 0.7 should be pulled toward 0.5
        calibrated = model.calibrate_prob(0.7)
        assert calibrated != pytest.approx(0.7, abs=0.01)
        assert 0.0 < calibrated < 1.0

    def test_calibrate_preserves_ordering(self):
        """Calibration preserves probability ordering (monotonic)."""
        model, _ = _fit_model()
        rng = np.random.RandomState(99)
        probs = rng.uniform(0.3, 0.7, 200)
        outcomes = (rng.random(200) < probs).astype(int)
        model.calibrate(probs, outcomes)
        cal_low = model.calibrate_prob(0.35)
        cal_mid = model.calibrate_prob(0.50)
        cal_high = model.calibrate_prob(0.65)
        assert cal_low < cal_mid < cal_high

    def test_calibrate_improves_log_loss(self):
        """Calibration should improve log loss on miscalibrated predictions."""
        model, _ = _fit_model()
        rng = np.random.RandomState(42)
        n = 1000
        raw_probs = rng.uniform(0.3, 0.7, n)
        # Bias: inflate probs by 10pp (simulates model overconfidence)
        biased_probs = np.clip(raw_probs + 0.10, 0.01, 0.99)
        outcomes = (rng.random(n) < raw_probs).astype(int)

        # Log loss before calibration
        eps = 1e-10
        ll_before = -(
            outcomes * np.log(biased_probs + eps) + (1 - outcomes) * np.log(1 - biased_probs + eps)
        ).mean()

        # Calibrate and compute log loss after
        model.calibrate(biased_probs, outcomes)
        cal_probs = np.array([model.calibrate_prob(p) for p in biased_probs])
        ll_after = -(
            outcomes * np.log(cal_probs + eps) + (1 - outcomes) * np.log(1 - cal_probs + eps)
        ).mean()

        assert ll_after < ll_before


# =============================================================================
# TestBacktestHelpers (integration, requires real data)
# =============================================================================


@pytest.mark.slow
class TestBacktestHelpers:
    """Tests for backtest pitcher helper functions."""

    def test_load_pitcher_stats_returns_dict(self):
        """load_pitcher_stats returns dict keyed by (player_id, season) with xfip/ip."""
        if not MLB_DB_PATH.exists():
            pytest.skip("mlb_data.db not found")

        from scripts.mlb_backtest import load_pitcher_stats

        stats = load_pitcher_stats(MLB_DB_PATH)
        assert len(stats) > 100
        # Check structure of a random entry
        key, val = next(iter(stats.items()))
        assert isinstance(key, tuple) and len(key) == 2  # (player_id, season)
        assert "xfip" in val
        assert "ip" in val
        assert "games_started" in val

    def test_league_avg_xfip_reasonable(self):
        """League avg xFIP should be in [3.5, 5.5] for each season."""
        if not MLB_DB_PATH.exists():
            pytest.skip("mlb_data.db not found")

        from scripts.mlb_backtest import compute_league_avg_xfip, load_pitcher_stats

        stats = load_pitcher_stats(MLB_DB_PATH)
        for season in [2023, 2024, 2025]:
            avg = compute_league_avg_xfip(stats, season)
            assert 3.5 <= avg <= 5.5, f"Season {season} avg xFIP = {avg}"
