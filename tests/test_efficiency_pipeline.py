"""Tests for NCAAB efficiency model data pipeline — TDD step 1 (RED)."""

from pathlib import Path

import pytest

CROSSWALK_PATH = Path("data/reference/espn_barttorvik_crosswalk.csv")
BARTTORVIK_PATH = Path("data/external/barttorvik")
GAMES_PATH = Path("data/raw/ncaab")

# Skip all tests if data files don't exist (CI environment)
pytestmark = pytest.mark.skipif(
    not CROSSWALK_PATH.exists() or not BARTTORVIK_PATH.exists() or not GAMES_PATH.exists(),
    reason="Required data files not found — run on local machine with full data",
)


def test_build_pit_dataset_no_leakage():
    """Feature snapshot must always predate the game."""
    from scripts.train_ncaab_efficiency_model import build_pit_dataset, validate_no_leakage

    df = build_pit_dataset(seasons=[2023])
    validate_no_leakage(df)  # raises AssertionError if any leakage found


def test_build_pit_dataset_has_required_columns():
    from scripts.train_ncaab_efficiency_model import build_pit_dataset

    df = build_pit_dataset(seasons=[2023])
    required = [
        "game_id",
        "game_date",
        "season",
        "home_team_id",
        "away_team_id",
        "home_win",
        "neutral_site",
        "home_snapshot_date",
        "away_snapshot_date",
        "adj_o_diff",
        "adj_d_diff",
        "barthag_diff",
        "adj_tempo_diff",
        "wab_diff",
        "home_flag",
    ]
    for col in required:
        assert col in df.columns, f"Missing column: {col}"


def test_build_pit_dataset_no_nulls_in_features():
    from scripts.train_ncaab_efficiency_model import build_pit_dataset

    df = build_pit_dataset(seasons=[2023])
    feature_cols = ["adj_o_diff", "adj_d_diff", "barthag_diff", "adj_tempo_diff", "wab_diff"]
    null_counts = df[feature_cols].isnull().sum()
    assert null_counts.sum() == 0, f"Null features found: {null_counts[null_counts > 0]}"


def test_home_flag_zero_on_neutral_games():
    from scripts.train_ncaab_efficiency_model import build_pit_dataset

    df = build_pit_dataset(seasons=[2023])
    neutral = df[df["neutral_site"] == True]  # noqa: E712
    assert (neutral["home_flag"] == 0).all(), "home_flag must be 0 for all neutral site games"


def test_home_flag_one_on_home_games():
    from scripts.train_ncaab_efficiency_model import build_pit_dataset

    df = build_pit_dataset(seasons=[2023])
    home = df[df["neutral_site"] == False]  # noqa: E712
    assert (home["home_flag"] == 1).all(), "home_flag must be 1 for all non-neutral games"


def test_build_pit_dataset_reasonable_row_count():
    """2023 season should have at least 3000 games after PIT join."""
    from scripts.train_ncaab_efficiency_model import build_pit_dataset

    df = build_pit_dataset(seasons=[2023])
    assert len(df) >= 3000, f"Expected >= 3000 games, got {len(df)}"
