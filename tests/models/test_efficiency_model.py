"""Tests for NCAABEfficiencyModel — TDD step 1 (RED)."""

import numpy as np
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from models.sport_specific.ncaab.efficiency_model import NCAABEfficiencyModel


@pytest.fixture
def mock_ratings():
    return {
        "Duke": {"adj_o": 120.5, "adj_d": 90.1, "barthag": 0.95, "adj_tempo": 70.2, "wab": 8.5},
        "Kentucky": {"adj_o": 115.0, "adj_d": 93.5, "barthag": 0.88, "adj_tempo": 68.0, "wab": 5.2},
    }


@pytest.fixture
def mock_crosswalk():
    return {"DUKE": "Duke", "UK": "Kentucky"}


@pytest.fixture
def fitted_model(mock_ratings, mock_crosswalk):
    """A model with fitted sklearn components."""
    lr = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
    scaler = StandardScaler()
    platt = LogisticRegression(C=1.0, max_iter=1000, random_state=42)

    X = np.array(
        [
            [1, 1, 0.1, 2, 3, 1],
            [-1, -1, -0.1, -2, -3, 0],
            [2, 2, 0.2, 1, 4, 1],
            [-2, -2, -0.2, -1, -4, 0],
        ]
    )
    y = np.array([1, 0, 1, 0])
    X_scaled = scaler.fit_transform(X)
    lr.fit(X_scaled, y)
    raw_probs = lr.predict_proba(X_scaled)[:, 1]
    platt.fit(raw_probs.reshape(-1, 1), y)

    return NCAABEfficiencyModel(
        lr=lr,
        scaler=scaler,
        platt=platt,
        crosswalk=mock_crosswalk,
        ratings=mock_ratings,
    )


def test_predict_win_probability_home_advantage(fitted_model):
    """Better team at home should have higher win prob than neutral site."""
    prob_home = fitted_model.predict_win_probability("DUKE", "UK", neutral_site=False)
    prob_neutral = fitted_model.predict_win_probability("DUKE", "UK", neutral_site=True)
    assert prob_home > prob_neutral


def test_predict_win_probability_in_valid_range(fitted_model):
    prob = fitted_model.predict_win_probability("DUKE", "UK", neutral_site=False)
    assert 0.0 < prob < 1.0


def test_neutral_site_zeroes_home_flag(fitted_model):
    """On neutral site, home_flag=0 — probability closer to 0.5 than home game."""
    prob_neutral = fitted_model.predict_win_probability("DUKE", "UK", neutral_site=True)
    assert 0.0 < prob_neutral < 1.0
    prob_home = fitted_model.predict_win_probability("DUKE", "UK", neutral_site=False)
    assert abs(prob_neutral - 0.5) < abs(prob_home - 0.5)


def test_unknown_team_raises(fitted_model):
    """Unknown ESPN ID raises KeyError with helpful message."""
    with pytest.raises(KeyError, match="UNKN"):
        fitted_model.predict_win_probability("UNKN", "DUKE", neutral_site=False)


def test_predict_spread_not_implemented(fitted_model):
    with pytest.raises(NotImplementedError):
        fitted_model.predict_spread("DUKE", "UK", neutral_site=False)


def test_load_barttorvik_snapshot(fitted_model):
    """load_barttorvik_snapshot replaces ratings dict from DataFrame."""
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "team": "Duke",
                "adj_o": 121.0,
                "adj_d": 89.0,
                "barthag": 0.96,
                "adj_tempo": 71.0,
                "wab": 9.0,
            }
        ]
    )
    fitted_model.load_barttorvik_snapshot(df)
    assert fitted_model.ratings["Duke"]["adj_o"] == 121.0
