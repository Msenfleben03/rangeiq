"""Tests for MLB odds backfill script."""

from __future__ import annotations

import sqlite3

from scripts.mlb_backfill_odds import (
    ESPN_TO_MLBAM,
    MLBAM_TO_ESPN,
    insert_odds,
    match_espn_to_mlbam,
)


class TestTeamMapping:
    """Tests for MLBAM <-> ESPN team ID mapping."""

    def test_mapping_has_30_teams(self):
        """Both mappings should have 30 entries."""
        assert len(MLBAM_TO_ESPN) == 30
        assert len(ESPN_TO_MLBAM) == 30

    def test_mapping_is_invertible(self):
        """MLBAM->ESPN and ESPN->MLBAM are inverses."""
        for mlbam_id, espn_id in MLBAM_TO_ESPN.items():
            assert ESPN_TO_MLBAM[espn_id] == mlbam_id

    def test_known_mappings(self):
        """Spot-check known team IDs."""
        assert MLBAM_TO_ESPN[147] == 10  # NYY
        assert MLBAM_TO_ESPN[111] == 2  # BOS
        assert MLBAM_TO_ESPN[119] == 19  # LAD
        assert ESPN_TO_MLBAM[10] == 147  # NYY


class TestMatchEspnToMlbam:
    """Tests for matching ESPN events to MLBAM game_pks."""

    def test_match_by_home_and_away(self):
        """Match ESPN event to game_pk via team IDs."""
        games = {
            (108, 147): 776001,  # LAA @ NYY
            (111, 119): 776002,  # BOS @ LAD
        }
        result = match_espn_to_mlbam(espn_home_id=10, espn_away_id=3, games_by_teams=games)
        assert result == 776001

    def test_no_match_returns_none(self):
        """Unknown team combo returns None."""
        games = {(108, 147): 776001}
        result = match_espn_to_mlbam(espn_home_id=99, espn_away_id=99, games_by_teams=games)
        assert result is None


class TestInsertOdds:
    """Tests for inserting odds into mlb_data.db."""

    def test_insert_and_retrieve(self, tmp_path):
        """Insert odds row and read it back."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE odds ("
            "game_pk INTEGER NOT NULL, provider TEXT NOT NULL, "
            "home_ml_open INTEGER, away_ml_open INTEGER, "
            "home_ml_close INTEGER, away_ml_close INTEGER, "
            "total_open REAL, total_close REAL, "
            "fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY (game_pk, provider))"
        )
        insert_odds(conn, 776001, "espn_bet", -150, 130, -145, 125, 8.5, 8.0)
        conn.commit()

        row = conn.execute("SELECT * FROM odds WHERE game_pk=776001").fetchone()
        assert row is not None
        assert row[0] == 776001  # game_pk
        assert row[2] == -150  # home_ml_open
        assert row[4] == -145  # home_ml_close
        conn.close()

    def test_upsert_on_duplicate(self, tmp_path):
        """Second insert for same game+provider updates values."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE odds ("
            "game_pk INTEGER NOT NULL, provider TEXT NOT NULL, "
            "home_ml_open INTEGER, away_ml_open INTEGER, "
            "home_ml_close INTEGER, away_ml_close INTEGER, "
            "total_open REAL, total_close REAL, "
            "fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY (game_pk, provider))"
        )
        insert_odds(conn, 776001, "espn_bet", -150, 130, None, None, None, None)
        insert_odds(conn, 776001, "espn_bet", -150, 130, -145, 125, 8.5, 8.0)
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM odds WHERE game_pk=776001").fetchone()[0]
        assert count == 1
        row = conn.execute("SELECT home_ml_close FROM odds WHERE game_pk=776001").fetchone()
        assert row[0] == -145
        conn.close()
