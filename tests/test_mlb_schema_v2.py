"""Tests for MLB schema v2 — bets, prop_bets, odds_snapshots, game_umpire, linescore."""

import sqlite3
import tempfile
from pathlib import Path


def _init_db(tmp: str) -> Path:
    from scripts.mlb_init_db import init_schema

    db_path = Path(tmp) / "mlb_test.db"
    init_schema(db_path)
    return db_path


def test_new_tables_exist():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _init_db(tmp)
        conn = sqlite3.connect(str(db_path))
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()
        assert "bets" in tables
        assert "prop_bets" in tables
        assert "odds_snapshots" in tables
        assert "game_umpire" in tables
        assert "linescore" in tables


def test_odds_snapshots_has_market_type():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _init_db(tmp)
        conn = sqlite3.connect(str(db_path))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(odds_snapshots)").fetchall()]
        conn.close()
        assert "market_type" in cols
        assert "snapshot_type" in cols


def test_bets_has_mlb_specific_columns():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _init_db(tmp)
        conn = sqlite3.connect(str(db_path))
        cols = [r[1] for r in conn.execute("PRAGMA table_info(bets)").fetchall()]
        conn.close()
        assert "pitcher_adj_home" in cols
        assert "devig_prob_placed" in cols
        assert "market_type" in cols


def test_schema_version_is_2():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _init_db(tmp)
        conn = sqlite3.connect(str(db_path))
        version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
        conn.close()
        assert version == 2


def test_existing_tables_still_present():
    """Regression: original 13 tables must still exist after schema v2."""
    with tempfile.TemporaryDirectory() as tmp:
        db_path = _init_db(tmp)
        conn = sqlite3.connect(str(db_path))
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()
        for t in [
            "teams",
            "players",
            "games",
            "pitcher_game_logs",
            "odds",
            "park_factors",
            "bullpen_usage",
        ]:
            assert t in tables, f"Original table missing: {t}"
