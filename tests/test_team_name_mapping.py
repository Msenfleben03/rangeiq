"""Tests for ESPN <-> Barttorvik team name mapping."""

from __future__ import annotations

import pytest


class TestStripMascot:
    def test_simple_mascot(self):
        from pipelines.team_name_mapping import _strip_mascot

        bart_names = {"Houston", "Duke", "Alabama"}
        assert _strip_mascot("Houston Cougars", bart_names) == "Houston"

    def test_two_word_mascot(self):
        from pipelines.team_name_mapping import _strip_mascot

        bart_names = {"North Carolina", "Duke"}
        assert _strip_mascot("North Carolina Tar Heels", bart_names) == "North Carolina"

    def test_state_to_st_substitution(self):
        from pipelines.team_name_mapping import _strip_mascot

        bart_names = {"Alabama St.", "San Diego St."}
        assert _strip_mascot("Alabama State Hornets", bart_names) == "Alabama St."

    def test_no_match_returns_none(self):
        from pipelines.team_name_mapping import _strip_mascot

        bart_names = {"Houston", "Duke"}
        assert _strip_mascot("Nonexistent Team Mascots", bart_names) is None


class TestManualOverrides:
    def test_known_overrides_are_valid(self):
        """All manual overrides should map to real Barttorvik team names."""
        import pandas as pd
        from pathlib import Path

        from pipelines.team_name_mapping import MANUAL_OVERRIDES

        # Load actual Barttorvik names if data exists
        bart_dir = Path("data/external/barttorvik")
        bart_files = sorted(bart_dir.glob("barttorvik_ratings_*.parquet"))
        if not bart_files:
            pytest.skip("No Barttorvik data cached")

        bart_df = pd.read_parquet(bart_files[-1])
        bart_names = set(bart_df["team"].unique())

        invalid = {k: v for k, v in MANUAL_OVERRIDES.items() if v not in bart_names}
        if invalid:
            pytest.fail(f"Invalid manual overrides (not in Barttorvik): {invalid}")


class TestTeamNameMapping:
    def test_espn_id_to_barttorvik_name(self):
        from pipelines.team_name_mapping import build_espn_barttorvik_mapping

        mapping = build_espn_barttorvik_mapping()
        # Houston Cougars
        assert mapping.get("HOU") == "Houston"

    def test_duke_mapping(self):
        from pipelines.team_name_mapping import build_espn_barttorvik_mapping

        mapping = build_espn_barttorvik_mapping()
        assert mapping.get("DUKE") == "Duke"

    def test_unknown_id_not_in_mapping(self):
        from pipelines.team_name_mapping import build_espn_barttorvik_mapping

        mapping = build_espn_barttorvik_mapping()
        assert "ZZZZZ" not in mapping

    def test_build_mapping_has_sufficient_coverage(self):
        from pipelines.team_name_mapping import build_espn_barttorvik_mapping

        mapping = build_espn_barttorvik_mapping()
        assert len(mapping) > 300  # D1 has ~360 teams

    def test_espn_id_to_barttorvik_function(self):
        from pipelines.team_name_mapping import espn_id_to_barttorvik

        assert espn_id_to_barttorvik("HOU") == "Houston"
        assert espn_id_to_barttorvik("999999") is None

    def test_manual_override_teams_mapped(self):
        from pipelines.team_name_mapping import build_espn_barttorvik_mapping

        mapping = build_espn_barttorvik_mapping()
        # These are known manual override cases
        assert mapping.get("CONN") == "Connecticut"
        assert mapping.get("MIA") == "Miami FL"
        assert mapping.get("NCSU") == "N.C. State"

    def test_louisville_and_manhattan_mapped(self):
        from pipelines.team_name_mapping import build_espn_barttorvik_mapping

        mapping = build_espn_barttorvik_mapping()
        assert mapping.get("LOU") == "Louisville"
        assert mapping.get("MAN") == "Manhattan"


class TestCrosswalkCSV:
    def test_crosswalk_covers_all_d1_teams(self):
        """Crosswalk CSV must cover every ESPN team_id that appears in game data."""
        import pandas as pd
        from pathlib import Path

        crosswalk_path = Path("data/reference/espn_barttorvik_crosswalk.csv")
        if not crosswalk_path.exists():
            pytest.skip("Crosswalk CSV not generated yet")

        crosswalk = pd.read_csv(crosswalk_path)
        crosswalk_ids = set(crosswalk["espn_id"])

        # Collect all D1 team_ids (teams that have game rows, not just opponents)
        d1_team_ids = set()
        for f in sorted(Path("data/raw/ncaab").glob("ncaab_games_*.parquet")):
            df = pd.read_parquet(f)
            d1_team_ids.update(df["team_id"].unique())

        missing = sorted(d1_team_ids - crosswalk_ids)
        assert not missing, f"D1 teams missing from crosswalk: {missing}"

    def test_crosswalk_values_are_valid_barttorvik_names(self):
        """All barttorvik_name values in crosswalk should exist in Barttorvik data."""
        import pandas as pd
        from pathlib import Path

        crosswalk_path = Path("data/reference/espn_barttorvik_crosswalk.csv")
        if not crosswalk_path.exists():
            pytest.skip("Crosswalk CSV not generated yet")

        bart_dir = Path("data/external/barttorvik")
        bart_files = sorted(bart_dir.glob("barttorvik_ratings_*.parquet"))
        if not bart_files:
            pytest.skip("No Barttorvik data cached")

        # Collect all Barttorvik names across all seasons
        bart_names = set()
        for f in bart_files:
            df = pd.read_parquet(f)
            bart_names.update(df["team"].unique())

        crosswalk = pd.read_csv(crosswalk_path)
        invalid = sorted(set(crosswalk["barttorvik_name"]) - bart_names)
        assert not invalid, f"Crosswalk names not in Barttorvik: {invalid}"

    def test_load_team_crosswalk_returns_dict(self):
        """load_team_crosswalk should return a non-empty dict."""
        from pathlib import Path

        if not Path("data/reference/espn_barttorvik_crosswalk.csv").exists():
            pytest.skip("Crosswalk CSV not generated yet")

        from features.sport_specific.ncaab.research_utils import load_team_crosswalk

        result = load_team_crosswalk()
        assert isinstance(result, dict)
        assert len(result) > 300
        assert result["DUKE"] == "Duke"
