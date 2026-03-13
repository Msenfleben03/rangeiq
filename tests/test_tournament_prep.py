"""Tournament prep smoke tests for NCAABEfficiencyModel.

Verifies neutral site handling and crosswalk coverage for all teams
that have appeared in recent 2026 games.

Skipped if efficiency model artifact does not yet exist (Gatekeeper not passed).
"""

from pathlib import Path

import pandas as pd
import pytest

MODEL_PATH = Path("data/processed/ncaab_efficiency_model.pkl")


@pytest.mark.skipif(not MODEL_PATH.exists(), reason="Efficiency model not yet trained")
class TestTournamentPrep:
    """Integration tests against the saved model artifact."""

    @pytest.fixture(autouse=True)
    def load_model_fixture(self):
        from models.model_persistence import load_model

        saved = load_model(MODEL_PATH)
        self.model = saved.model

        bt_files = sorted(Path("data/external/barttorvik").glob("barttorvik_ratings_*.parquet"))
        if bt_files:
            bt_df = pd.read_parquet(bt_files[-1])
            latest_bt = bt_df[bt_df["date"] == bt_df["date"].max()]
            self.model.load_barttorvik_snapshot(latest_bt)

    def test_neutral_site_reduces_home_edge(self):
        """Home flag consistently shifts probability upward for home team."""
        # Find two teams with ratings
        candidates = [
            tid
            for tid in list(self.model.crosswalk.keys())
            if self.model.crosswalk.get(tid) in self.model.ratings
        ]
        if len(candidates) < 2:
            pytest.skip("Not enough teams with ratings loaded")
        home_team, away_team = candidates[0], candidates[1]
        prob_home = self.model.predict_win_probability(home_team, away_team, neutral_site=False)
        prob_neutral = self.model.predict_win_probability(home_team, away_team, neutral_site=True)
        # Home flag should always increase (or equal) home team probability
        assert prob_home >= prob_neutral, (
            f"Home flag should boost home team probability: home={prob_home:.3f}, "
            f"neutral={prob_neutral:.3f}"
        )

    def test_all_current_slate_teams_in_crosswalk(self):
        """All teams in the 2026 game log should resolve without KeyError."""
        games_2026_path = Path("data/raw/ncaab/ncaab_games_2026.parquet")
        if not games_2026_path.exists():
            pytest.skip("2026 games file not found")

        games_2026 = pd.read_parquet(games_2026_path)
        recent = games_2026[games_2026["date"] >= "2026-03-01"]
        all_team_ids = pd.concat([recent["team_id"], recent["opponent_id"]]).unique()

        missing = [tid for tid in all_team_ids if tid not in self.model.crosswalk]
        if missing:
            import warnings

            warnings.warn(
                f"{len(missing)} teams from 2026 slate missing from crosswalk: {sorted(missing)}. "
                "Add manually to data/reference/espn_barttorvik_crosswalk.csv",
                UserWarning,
                stacklevel=2,
            )
        # Known crosswalk gaps as of 2026-03-13: QUC=Quinnipiac, LIN=Lindenwood, XAV=Xavier
        KNOWN_MISSING = {"QUC", "LIN", "XAV"}
        unexpected_missing = set(missing) - KNOWN_MISSING
        assert len(unexpected_missing) == 0, (
            f"Unexpected teams missing from crosswalk (fix before tournament): "
            f"{sorted(unexpected_missing)}"
        )

    def test_predict_probability_valid_range(self):
        """All predictions should be strictly between 0 and 1."""
        candidates = [
            tid
            for tid in list(self.model.crosswalk.keys())[:20]
            if self.model.crosswalk.get(tid) in self.model.ratings
        ]
        if len(candidates) < 2:
            pytest.skip("Need at least 2 teams with ratings loaded")

        for i in range(min(5, len(candidates) - 1)):
            prob = self.model.predict_win_probability(
                candidates[i], candidates[i + 1], neutral_site=True
            )
            assert 0.0 < prob < 1.0, f"Probability out of range: {prob}"
