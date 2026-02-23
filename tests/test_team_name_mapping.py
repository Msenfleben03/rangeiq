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
