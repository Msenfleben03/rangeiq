"""Tests for KenPom SQLite storage (kenpom_ratings table)."""

from __future__ import annotations


import pytest

from tracking.database import BettingDatabase


@pytest.fixture()
def db(tmp_path):
    """Fresh database in temp directory."""
    db_path = tmp_path / "test_betting.db"
    return BettingDatabase(str(db_path))


class TestKenpomRatingsTable:
    """Test kenpom_ratings table creation and constraints."""

    def test_table_exists(self, db):
        """kenpom_ratings table is created on init."""
        rows = db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='kenpom_ratings'"
        )
        assert len(rows) == 1

    def test_insert_rating(self, db):
        """Can insert a KenPom rating row."""
        with db.get_cursor() as cursor:
            cursor.execute(
                """INSERT INTO kenpom_ratings
                   (team, conf, season, snapshot_date, rank, adj_em, adj_o, adj_d, adj_t,
                    luck, sos_adj_em, sos_opp_o, sos_opp_d, ncsos_adj_em, w_l, seed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    "Houston",
                    "B12",
                    2026,
                    "2026-02-25",
                    1,
                    36.0,
                    126.0,
                    90.0,
                    63.0,
                    0.03,
                    8.5,
                    108.5,
                    100.0,
                    5.0,
                    "25-1",
                    "1",
                ),
            )
        rows = db.execute_query("SELECT * FROM kenpom_ratings WHERE team = 'Houston'")
        assert len(rows) == 1
        assert rows[0]["adj_em"] == pytest.approx(36.0)

    def test_unique_constraint_prevents_duplicates(self, db):
        """Duplicate (team, season, snapshot_date) raises IntegrityError."""
        insert_sql = """INSERT INTO kenpom_ratings
            (team, conf, season, snapshot_date, rank, adj_em, adj_o, adj_d, adj_t)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        params = ("Houston", "B12", 2026, "2026-02-25", 1, 36.0, 126.0, 90.0, 63.0)
        with db.get_cursor() as cursor:
            cursor.execute(insert_sql, params)
        with pytest.raises(Exception):
            with db.get_cursor() as cursor:
                cursor.execute(insert_sql, params)

    def test_different_dates_allowed(self, db):
        """Same team on different dates inserts as separate rows."""
        insert_sql = """INSERT INTO kenpom_ratings
            (team, conf, season, snapshot_date, rank, adj_em, adj_o, adj_d, adj_t)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        with db.get_cursor() as cursor:
            cursor.execute(
                insert_sql,
                ("Houston", "B12", 2026, "2026-02-25", 1, 36.0, 126.0, 90.0, 63.0),
            )
        with db.get_cursor() as cursor:
            cursor.execute(
                insert_sql,
                ("Houston", "B12", 2026, "2026-02-26", 1, 36.5, 126.5, 89.5, 63.0),
            )
        rows = db.execute_query("SELECT * FROM kenpom_ratings WHERE team = 'Houston'")
        assert len(rows) == 2
