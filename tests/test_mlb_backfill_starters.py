"""Tests for MLB starter ID backfill script."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Must mock statsapi before importing the script
import sys

mock_statsapi = MagicMock()
sys.modules.setdefault("statsapi", mock_statsapi)

from scripts.mlb_backfill_starters import (  # noqa: E402
    get_games_needing_starters,
    load_checkpoint,
    save_checkpoint,
    update_starters_batch,
    upsert_players_if_missing,
    backfill,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE teams (
    team_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    abbreviation TEXT NOT NULL DEFAULT '',
    city TEXT NOT NULL DEFAULT '',
    stadium TEXT NOT NULL DEFAULT '',
    league TEXT NOT NULL DEFAULT 'AL',
    division TEXT NOT NULL DEFAULT 'East'
);

CREATE TABLE players (
    player_id INTEGER PRIMARY KEY,
    full_name TEXT NOT NULL,
    position TEXT,
    bats TEXT,
    throws TEXT
);

CREATE TABLE games (
    game_pk INTEGER PRIMARY KEY,
    game_date DATE NOT NULL,
    season INTEGER NOT NULL,
    home_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    home_score INTEGER,
    away_score INTEGER,
    status TEXT NOT NULL DEFAULT 'scheduled',
    home_starter_id INTEGER REFERENCES players(player_id),
    away_starter_id INTEGER REFERENCES players(player_id),
    venue TEXT,
    game_time_utc TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Create a temporary mlb_data.db with schema and sample data."""
    db = tmp_path / "mlb_data.db"
    conn = sqlite3.connect(str(db))
    conn.executescript(SCHEMA_SQL)
    conn.execute("PRAGMA foreign_keys=ON")

    # Seed teams
    conn.execute(
        "INSERT INTO teams (team_id, name, abbreviation, city, stadium, league, division) "
        "VALUES (147, 'New York Yankees', 'NYY', 'New York', 'Yankee Stadium', 'AL', 'East')"
    )
    conn.execute(
        "INSERT INTO teams (team_id, name, abbreviation, city, stadium, league, division) "
        "VALUES (111, 'Boston Red Sox', 'BOS', 'Boston', 'Fenway Park', 'AL', 'East')"
    )

    # Insert games with NULL starters
    conn.execute(
        "INSERT INTO games (game_pk, game_date, season, home_team_id, away_team_id, "
        "home_score, away_score, status) VALUES (100001, '2023-04-10', 2023, 147, 111, 5, 3, 'final')"
    )
    conn.execute(
        "INSERT INTO games (game_pk, game_date, season, home_team_id, away_team_id, "
        "home_score, away_score, status) VALUES (100002, '2023-04-11', 2023, 111, 147, 2, 7, 'final')"
    )
    conn.execute(
        "INSERT INTO games (game_pk, game_date, season, home_team_id, away_team_id, "
        "home_score, away_score, status) VALUES (100003, '2024-04-10', 2024, 147, 111, 4, 1, 'final')"
    )
    # Non-final game (should be excluded)
    conn.execute(
        "INSERT INTO games (game_pk, game_date, season, home_team_id, away_team_id, "
        "status) VALUES (100004, '2024-04-11', 2024, 147, 111, 'scheduled')"
    )
    # Game with starters already set (should be excluded)
    conn.execute("INSERT INTO players (player_id, full_name) VALUES (999, 'Existing Pitcher')")
    conn.execute("INSERT INTO players (player_id, full_name) VALUES (998, 'Other Pitcher')")
    conn.execute(
        "INSERT INTO games (game_pk, game_date, season, home_team_id, away_team_id, "
        "home_score, away_score, status, home_starter_id, away_starter_id) "
        "VALUES (100005, '2024-04-12', 2024, 147, 111, 3, 2, 'final', 999, 998)"
    )
    conn.commit()
    conn.close()
    return db


@pytest.fixture()
def checkpoint_path(tmp_path: Path) -> Path:
    """Return a temp path for the checkpoint file."""
    return tmp_path / "checkpoint.json"


# ---------------------------------------------------------------------------
# Tests: get_games_needing_starters
# ---------------------------------------------------------------------------


def test_gets_all_null_starter_games(db_path: Path):
    """Returns only final games with NULL starters."""
    game_pks = get_games_needing_starters(db_path)
    assert set(game_pks) == {100001, 100002, 100003}


def test_excludes_non_final_games(db_path: Path):
    """Scheduled games are not returned."""
    game_pks = get_games_needing_starters(db_path)
    assert 100004 not in game_pks


def test_excludes_games_with_starters(db_path: Path):
    """Games that already have both starters are excluded."""
    game_pks = get_games_needing_starters(db_path)
    assert 100005 not in game_pks


def test_season_filter(db_path: Path):
    """Season filter restricts to that season only."""
    game_pks = get_games_needing_starters(db_path, season=2023)
    assert set(game_pks) == {100001, 100002}


def test_season_filter_2024(db_path: Path):
    """Season 2024 returns only 2024 games needing starters."""
    game_pks = get_games_needing_starters(db_path, season=2024)
    assert set(game_pks) == {100003}


def test_returns_sorted(db_path: Path):
    """Results are sorted by game_pk."""
    game_pks = get_games_needing_starters(db_path)
    assert game_pks == sorted(game_pks)


# ---------------------------------------------------------------------------
# Tests: checkpoint
# ---------------------------------------------------------------------------


def test_load_checkpoint_empty(checkpoint_path: Path):
    """Returns empty set when no checkpoint file exists."""
    assert load_checkpoint(checkpoint_path) == set()


def test_save_and_load_checkpoint(checkpoint_path: Path):
    """Round-trip save/load preserves game_pks."""
    processed = {100001, 100002, 100003}
    save_checkpoint(checkpoint_path, processed)
    loaded = load_checkpoint(checkpoint_path)
    assert loaded == processed


def test_checkpoint_json_structure(checkpoint_path: Path):
    """Checkpoint JSON has expected keys."""
    save_checkpoint(checkpoint_path, {1, 2, 3})
    with open(checkpoint_path, encoding="utf-8") as f:
        data = json.load(f)
    assert "processed_game_pks" in data
    assert "count" in data
    assert data["count"] == 3
    assert data["processed_game_pks"] == [1, 2, 3]  # sorted


# ---------------------------------------------------------------------------
# Tests: upsert_players_if_missing
# ---------------------------------------------------------------------------


def test_upsert_new_players(db_path: Path):
    """New player IDs are inserted with placeholder names."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    upsert_players_if_missing(conn, {660271, 608566})
    conn.commit()

    rows = conn.execute(
        "SELECT player_id, full_name FROM players WHERE player_id IN (660271, 608566)"
    ).fetchall()
    conn.close()

    assert len(rows) == 2
    names = {r[1] for r in rows}
    assert "Player 660271" in names
    assert "Player 608566" in names


def test_upsert_ignores_existing(db_path: Path):
    """Existing player IDs are not overwritten."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys=ON")
    upsert_players_if_missing(conn, {999})  # already exists
    conn.commit()

    name = conn.execute("SELECT full_name FROM players WHERE player_id = 999").fetchone()[0]
    conn.close()
    assert name == "Existing Pitcher"  # not overwritten


def test_upsert_empty_set(db_path: Path):
    """Empty set does nothing."""
    conn = sqlite3.connect(str(db_path))
    result = upsert_players_if_missing(conn, set())
    conn.close()
    assert result == 0


# ---------------------------------------------------------------------------
# Tests: update_starters_batch
# ---------------------------------------------------------------------------


def test_update_starters_writes_ids(db_path: Path):
    """Batch update correctly sets home/away starter IDs."""
    updates = [(660271, 608566, 100001)]
    n_updated, n_players = update_starters_batch(db_path, updates)

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT home_starter_id, away_starter_id FROM games WHERE game_pk = 100001"
    ).fetchone()
    conn.close()

    assert n_updated == 1
    assert row[0] == 660271
    assert row[1] == 608566


def test_update_starters_creates_players(db_path: Path):
    """New player IDs are inserted into players table as part of batch update."""
    updates = [(770001, 770002, 100001)]
    _n_updated, n_players = update_starters_batch(db_path, updates)

    conn = sqlite3.connect(str(db_path))
    count = conn.execute(
        "SELECT COUNT(*) FROM players WHERE player_id IN (770001, 770002)"
    ).fetchone()[0]
    conn.close()

    assert n_players >= 1  # at least some were new
    assert count == 2


def test_update_starters_handles_none(db_path: Path):
    """None starter IDs are written as NULL (no crash)."""
    updates = [(None, 608566, 100001)]
    n_updated, _ = update_starters_batch(db_path, updates)

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT home_starter_id, away_starter_id FROM games WHERE game_pk = 100001"
    ).fetchone()
    conn.close()

    assert n_updated == 1
    assert row[0] is None
    assert row[1] == 608566


def test_update_starters_empty_list(db_path: Path):
    """Empty update list returns zeros."""
    n_updated, n_players = update_starters_batch(db_path, [])
    assert n_updated == 0
    assert n_players == 0


def test_update_preserves_other_columns(db_path: Path):
    """UPDATE only touches starter columns, not scores/status/etc."""
    updates = [(660271, 608566, 100001)]
    update_starters_batch(db_path, updates)

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT home_score, away_score, status, venue FROM games WHERE game_pk = 100001"
    ).fetchone()
    conn.close()

    assert row[0] == 5  # home_score preserved
    assert row[1] == 3  # away_score preserved
    assert row[2] == "final"  # status preserved


# ---------------------------------------------------------------------------
# Tests: backfill (integration with mocked API)
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_game_result():
    """Create a mock MLBGameResult."""
    result = MagicMock()
    result.home_starter_id = 660271
    result.away_starter_id = 608566
    return result


def test_backfill_dry_run(db_path: Path, checkpoint_path: Path):
    """Dry run reports counts but makes no DB changes."""
    with patch("pipelines.mlb_stats_api.MLBStatsAPIClient") as MockClient:
        summary = backfill(
            db_path=db_path,
            checkpoint_path=checkpoint_path,
            dry_run=True,
        )

    # No API calls made
    MockClient.assert_not_called()

    # DB unchanged — starters still NULL
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT home_starter_id FROM games WHERE game_pk = 100001").fetchone()
    conn.close()
    assert row[0] is None

    assert summary["remaining"] == 3


def test_backfill_updates_games(db_path: Path, checkpoint_path: Path, mock_game_result: MagicMock):
    """Full backfill updates starter IDs and creates checkpoint."""
    with patch("pipelines.mlb_stats_api.MLBStatsAPIClient") as MockClient:
        instance = MockClient.return_value
        instance.fetch_game_result.return_value = mock_game_result

        summary = backfill(
            db_path=db_path,
            checkpoint_path=checkpoint_path,
            batch_size=10,
        )

    assert summary["updated"] == 3
    assert summary["both_found"] == 3

    # Verify DB was updated
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT home_starter_id, away_starter_id FROM games WHERE game_pk = 100001"
    ).fetchone()
    conn.close()
    assert row[0] == 660271
    assert row[1] == 608566

    # Checkpoint written
    assert checkpoint_path.exists()
    loaded = load_checkpoint(checkpoint_path)
    assert {100001, 100002, 100003}.issubset(loaded)


def test_backfill_resumes_from_checkpoint(
    db_path: Path, checkpoint_path: Path, mock_game_result: MagicMock
):
    """Backfill skips already-processed games from checkpoint."""
    # Pre-populate checkpoint with 2 games
    save_checkpoint(checkpoint_path, {100001, 100002})

    with patch("pipelines.mlb_stats_api.MLBStatsAPIClient") as MockClient:
        instance = MockClient.return_value
        instance.fetch_game_result.return_value = mock_game_result

        backfill(
            db_path=db_path,
            checkpoint_path=checkpoint_path,
            batch_size=10,
        )

    # Only 1 API call (game 100003 — the one not in checkpoint)
    instance = MockClient.return_value
    assert instance.fetch_game_result.call_count == 1


def test_backfill_handles_api_errors(db_path: Path, checkpoint_path: Path):
    """API errors are counted and skipped, not raised."""
    with patch("pipelines.mlb_stats_api.MLBStatsAPIClient") as MockClient:
        instance = MockClient.return_value
        instance.fetch_game_result.return_value = None  # simulates API failure

        summary = backfill(
            db_path=db_path,
            checkpoint_path=checkpoint_path,
            batch_size=10,
        )

    assert summary["api_errors"] == 3
    assert summary["updated"] == 0


def test_backfill_season_filter(db_path: Path, checkpoint_path: Path, mock_game_result: MagicMock):
    """Season filter restricts which games are processed."""
    with patch("pipelines.mlb_stats_api.MLBStatsAPIClient") as MockClient:
        instance = MockClient.return_value
        instance.fetch_game_result.return_value = mock_game_result

        summary = backfill(
            db_path=db_path,
            checkpoint_path=checkpoint_path,
            season=2023,
            batch_size=10,
        )

    assert summary["total_games"] == 2
    assert instance.fetch_game_result.call_count == 2


def test_backfill_partial_starters(db_path: Path, checkpoint_path: Path):
    """Games where only one starter is found are counted correctly."""
    partial_result = MagicMock()
    partial_result.home_starter_id = 660271
    partial_result.away_starter_id = None

    with patch("pipelines.mlb_stats_api.MLBStatsAPIClient") as MockClient:
        instance = MockClient.return_value
        instance.fetch_game_result.return_value = partial_result

        summary = backfill(
            db_path=db_path,
            checkpoint_path=checkpoint_path,
            batch_size=10,
        )

    assert summary["home_found"] == 3
    assert summary["away_found"] == 0
    assert summary["both_found"] == 0
    assert summary["neither_found"] == 0
