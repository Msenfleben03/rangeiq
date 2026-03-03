"""Tests for F5 score backfill: DB migration and score population."""

import sqlite3
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def tmp_db(tmp_path):
    """Minimal mlb_data.db with games table (no F5 columns yet)."""
    db = tmp_path / "mlb_data.db"
    conn = sqlite3.connect(str(db))
    conn.execute(
        """
        CREATE TABLE games (
            game_pk INTEGER PRIMARY KEY,
            game_date DATE NOT NULL,
            season INTEGER NOT NULL,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_score INTEGER,
            away_score INTEGER,
            status TEXT DEFAULT 'scheduled'
        )
    """
    )
    conn.execute("INSERT INTO games VALUES (745001, '2025-04-01', 2025, 1, 2, 5, 3, 'final')")
    conn.commit()
    conn.close()
    return db


def test_migration_adds_f5_columns(tmp_db):
    """migrate_f5_columns() adds home_f5_score and away_f5_score."""
    from scripts.mlb_backfill_f5_scores import migrate_f5_columns

    migrate_f5_columns(str(tmp_db))

    conn = sqlite3.connect(str(tmp_db))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(games)")}
    conn.close()
    assert "home_f5_score" in cols
    assert "away_f5_score" in cols


def test_migration_is_idempotent(tmp_db):
    """Running migrate_f5_columns() twice does not raise."""
    from scripts.mlb_backfill_f5_scores import migrate_f5_columns

    migrate_f5_columns(str(tmp_db))
    migrate_f5_columns(str(tmp_db))  # second call must not raise


LINESCORE_9_INNINGS = {
    "innings": [
        {
            "num": i,
            "home": {"runs": [0, 2, 0, 1, 0, 0, 0, 0, 2][i - 1]},
            "away": {"runs": [1, 0, 0, 0, 1, 0, 0, 0, 0][i - 1]},
        }
        for i in range(1, 10)
    ]
}
# home F5: 0+2+0+1+0 = 3, away F5: 1+0+0+0+1 = 2


def test_fetch_f5_scores_sums_first_five_innings():
    """fetch_f5_scores returns sum of first 5 innings only."""
    from scripts.mlb_backfill_f5_scores import fetch_f5_scores

    mock_resp = MagicMock()
    mock_resp.json.return_value = LINESCORE_9_INNINGS
    mock_resp.raise_for_status.return_value = None

    with patch("scripts.mlb_backfill_f5_scores.requests.get", return_value=mock_resp):
        result = fetch_f5_scores(745001)

    assert result == (3, 2)


def test_fetch_f5_scores_handles_tie():
    """fetch_f5_scores returns tuple even when F5 scores are tied."""
    from scripts.mlb_backfill_f5_scores import fetch_f5_scores

    tied = {"innings": [{"num": i, "home": {"runs": 1}, "away": {"runs": 1}} for i in range(1, 6)]}
    mock_resp = MagicMock()
    mock_resp.json.return_value = tied
    mock_resp.raise_for_status.return_value = None

    with patch("scripts.mlb_backfill_f5_scores.requests.get", return_value=mock_resp):
        result = fetch_f5_scores(745001)

    assert result == (5, 5)


def test_fetch_f5_scores_handles_short_game():
    """fetch_f5_scores sums only available innings (< 5 due to rain etc)."""
    from scripts.mlb_backfill_f5_scores import fetch_f5_scores

    short = {
        "innings": [
            {"num": 1, "home": {"runs": 2}, "away": {"runs": 0}},
            {"num": 2, "home": {"runs": 0}, "away": {"runs": 1}},
            # game ended after 2 innings
        ]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = short
    mock_resp.raise_for_status.return_value = None

    with patch("scripts.mlb_backfill_f5_scores.requests.get", return_value=mock_resp):
        result = fetch_f5_scores(745001)

    assert result == (2, 1)


def test_fetch_f5_scores_returns_none_on_api_error():
    """fetch_f5_scores returns None when request fails."""
    from scripts.mlb_backfill_f5_scores import fetch_f5_scores

    with patch(
        "scripts.mlb_backfill_f5_scores.requests.get",
        side_effect=Exception("timeout"),
    ):
        result = fetch_f5_scores(745001)

    assert result is None


def test_backfill_populates_db(tmp_db):
    """backfill() writes F5 scores to games table."""
    from scripts.mlb_backfill_f5_scores import backfill

    mock_resp = MagicMock()
    mock_resp.json.return_value = LINESCORE_9_INNINGS
    mock_resp.raise_for_status.return_value = None

    with patch("scripts.mlb_backfill_f5_scores.requests.get", return_value=mock_resp):
        stats = backfill(str(tmp_db))

    assert stats["updated"] == 1
    assert stats["failed"] == 0

    conn = sqlite3.connect(str(tmp_db))
    row = conn.execute(
        "SELECT home_f5_score, away_f5_score FROM games WHERE game_pk = 745001"
    ).fetchone()
    conn.close()
    assert row == (3, 2)


def test_backfill_skips_already_populated(tmp_db):
    """backfill() does not overwrite existing F5 scores."""
    from scripts.mlb_backfill_f5_scores import backfill, migrate_f5_columns

    # Pre-populate
    migrate_f5_columns(str(tmp_db))
    conn = sqlite3.connect(str(tmp_db))
    conn.execute("UPDATE games SET home_f5_score = 1, away_f5_score = 0 WHERE game_pk = 745001")
    conn.commit()
    conn.close()

    with patch("scripts.mlb_backfill_f5_scores.requests.get") as mock_get:
        stats = backfill(str(tmp_db))

    mock_get.assert_not_called()
    assert stats["total"] == 0
