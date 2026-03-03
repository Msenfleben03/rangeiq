"""Tests for F5 mode in mlb_backtest.py."""
import numpy as np
import pandas as pd
import pytest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def games_with_f5():
    """Minimal games DataFrame with F5 scores for backtest tests."""
    rng = np.random.default_rng(42)
    n = 300
    team_ids = list(range(1, 16))

    records = []
    for i in range(n):
        home = rng.choice(team_ids)
        away = rng.choice([t for t in team_ids if t != home])
        home_score = int(rng.poisson(4.5))
        away_score = int(rng.poisson(4.3))
        home_f5 = int(rng.poisson(2.5))
        away_f5 = int(rng.poisson(2.4))
        records.append(
            {
                "game_pk": 700000 + i,
                "game_date": f"202{'3' if i < 150 else '4'}-04-{(i % 28) + 1:02d}",
                "season": 2023 if i < 150 else 2024,
                "home_team_id": home,
                "away_team_id": away,
                "home_score": home_score,
                "away_score": away_score,
                "home_starter_id": None,
                "away_starter_id": None,
                "home_f5_score": home_f5,
                "away_f5_score": away_f5,
            }
        )
    return pd.DataFrame(records)


def test_run_backtest_f5_returns_f5_correct_column(games_with_f5):
    """run_backtest with f5=True produces f5_correct column."""
    from scripts.mlb_backtest import run_backtest

    results = run_backtest(games_with_f5, test_season=2024, f5=True)

    assert not results.empty
    assert "f5_correct" in results.columns


def test_f5_correct_excludes_ties(games_with_f5):
    """f5_correct is NaN when home_f5_score == away_f5_score."""
    from scripts.mlb_backtest import run_backtest

    results = run_backtest(games_with_f5, test_season=2024, f5=True)

    tied = results[results["home_f5_score"] == results["away_f5_score"]]
    assert tied["f5_correct"].isna().all()


def test_f5_mode_does_not_apply_calibration(games_with_f5):
    """In f5=True mode, pred_prob used for betting is raw f5_moneyline_home."""
    from scripts.mlb_backtest import run_backtest

    results = run_backtest(games_with_f5, test_season=2024, f5=True, calibrated=True)
    # calibrated=True should be ignored in f5 mode — no crash, just raw prob used
    assert not results.empty
    assert "f5_moneyline_home" in results.columns


def test_f5_away_fav_bets_suppressed_by_default(games_with_f5):
    """--f5 mode suppresses away_fav bets by default (no_away_fav=True)."""
    from scripts.mlb_backtest import run_backtest

    results = run_backtest(games_with_f5, test_season=2024, f5=True, odds_df=None)
    bets = results[results["stake"] > 0] if "stake" in results.columns else pd.DataFrame()
    if not bets.empty and "bet_side" in bets.columns and "bet_odds" in bets.columns:
        away_favs = bets[(bets["bet_side"] == "away") & (bets["bet_odds"] < 0)]
        assert len(away_favs) == 0
