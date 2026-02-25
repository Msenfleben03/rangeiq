"""Tests for KenPom SQLite storage (kenpom_ratings table)."""

from __future__ import annotations


import pandas as pd
import pytest

from pipelines.kenpom_fetcher import store_snapshot_to_db
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


class TestStoreSnapshotToDb:
    """Test store_snapshot_to_db function."""

    def _make_snapshot_df(self, date_str="2026-02-25"):
        """Create a minimal KenPom snapshot DataFrame matching normalize output."""
        return pd.DataFrame(
            {
                "rank": pd.array([1, 2, 3], dtype="Int64"),
                "team": ["Houston", "Duke", "Arizona"],
                "conf": ["B12", "ACC", "B12"],
                "w_l": ["25-1", "24-2", "23-2"],
                "adj_em": [36.0, 34.0, 33.0],
                "adj_o": [126.0, 125.0, 124.0],
                "adj_o_rk": pd.array([1, 2, 3], dtype="Int64"),
                "adj_d": [90.0, 91.0, 91.5],
                "adj_d_rk": pd.array([1, 2, 3], dtype="Int64"),
                "adj_t": [63.0, 66.0, 70.0],
                "adj_t_rk": pd.array([10, 250, 26], dtype="Int64"),
                "luck": [0.042, -0.015, 0.028],
                "luck_rk": pd.array([50, 200, 100], dtype="Int64"),
                "sos_adj_em": [8.50, 9.10, 7.80],
                "sos_adj_em_rk": pd.array([10, 5, 15], dtype="Int64"),
                "sos_opp_o": [108.5, 109.1, 107.8],
                "sos_opp_o_rk": pd.array([10, 5, 15], dtype="Int64"),
                "sos_opp_d": [100.0, 100.0, 100.0],
                "sos_opp_d_rk": pd.array([10, 5, 15], dtype="Int64"),
                "ncsos_adj_em": [5.0, 4.5, 6.2],
                "ncsos_adj_em_rk": pd.array([20, 30, 10], dtype="Int64"),
                "seed": ["1", "1", "2"],
                "year": [2026, 2026, 2026],
                "date": pd.to_datetime([date_str] * 3),
            }
        )

    def test_stores_all_teams(self, db):
        """All teams from snapshot are stored in DB."""
        df = self._make_snapshot_df()
        count = store_snapshot_to_db(df, 2026, str(db.db_path))
        assert count == 3

    def test_data_matches(self, db):
        """Stored values match input DataFrame."""
        df = self._make_snapshot_df()
        store_snapshot_to_db(df, 2026, str(db.db_path))
        rows = db.execute_query("SELECT * FROM kenpom_ratings WHERE team = 'Houston'")
        assert len(rows) == 1
        assert rows[0]["adj_em"] == pytest.approx(36.0)
        assert rows[0]["adj_o"] == pytest.approx(126.0)
        assert rows[0]["snapshot_date"] == "2026-02-25"
        assert rows[0]["season"] == 2026

    def test_idempotent_upsert(self, db):
        """Running twice on same date doesn't create duplicates."""
        df = self._make_snapshot_df()
        store_snapshot_to_db(df, 2026, str(db.db_path))
        count = store_snapshot_to_db(df, 2026, str(db.db_path))
        assert count == 3  # 3 upserted (replaced), not 6
        rows = db.execute_query("SELECT COUNT(*) as n FROM kenpom_ratings")
        assert rows[0]["n"] == 3

    def test_different_dates_accumulate(self, db):
        """Snapshots from different dates accumulate."""
        df1 = self._make_snapshot_df("2026-02-25")
        df2 = self._make_snapshot_df("2026-02-26")
        store_snapshot_to_db(df1, 2026, str(db.db_path))
        store_snapshot_to_db(df2, 2026, str(db.db_path))
        rows = db.execute_query("SELECT COUNT(*) as n FROM kenpom_ratings")
        assert rows[0]["n"] == 6  # 3 teams x 2 dates

    def test_empty_df_returns_zero(self, db):
        """Empty DataFrame stores nothing, returns 0."""
        df = pd.DataFrame()
        count = store_snapshot_to_db(df, 2026, str(db.db_path))
        assert count == 0
