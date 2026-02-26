"""Tests for MLB Stats API client."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

# Import with statsapi mocked so tests run without the package installed
import sys

mock_statsapi = MagicMock()
sys.modules.setdefault("statsapi", mock_statsapi)

from pipelines.mlb_stats_api import (  # noqa: E402
    MLBGame,
    MLBGameResult,
    MLBStatsAPIClient,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    """Client with statsapi available (mocked at module level)."""
    with (
        patch("pipelines.mlb_stats_api._HAS_STATSAPI", True),
        patch("pipelines.mlb_stats_api.time.sleep"),
    ):
        return MLBStatsAPIClient(request_delay=0)


SAMPLE_SCHEDULE_GAME = {
    "game_id": 745632,
    "game_date": "2025-04-10",
    "game_datetime": "2025-04-10T18:10:00Z",
    "status": "Final",
    "home_id": 147,
    "home_name": "New York Yankees",
    "away_id": 111,
    "away_name": "Boston Red Sox",
    "home_score": 5,
    "away_score": 3,
    "home_probable_pitcher_id": 660271,
    "home_probable_pitcher": "Gerrit Cole",
    "away_probable_pitcher_id": 608566,
    "away_probable_pitcher": "Chris Sale",
    "venue_name": "Yankee Stadium",
}

SAMPLE_BOXSCORE = {
    "home": {
        "team": {"id": 147},
        "teamStats": {"batting": {"runs": 5}},
        "battingOrder": [660271, 665742, 665489, 641355, 621566, 641531, 596019, 543760, 665750],
        "players": {
            "660271": {
                "person": {"id": 660271, "fullName": "Gerrit Cole"},
                "position": {"abbreviation": "P"},
                "gameStatus": {"isCurrentPitcher": False},
                "allPositions": [{"type": "Pitcher"}],
                "stats": {"pitching": {"inningsPitched": "7.0"}},
            }
        },
    },
    "away": {
        "team": {"id": 111},
        "teamStats": {"batting": {"runs": 3}},
        "battingOrder": [608566, 665927, 543484, 592450, 571578, 605113, 543877, 514888, 672515],
        "players": {
            "608566": {
                "person": {"id": 608566, "fullName": "Chris Sale"},
                "position": {"abbreviation": "P"},
                "gameStatus": {"isCurrentPitcher": False},
                "allPositions": [{"type": "Pitcher"}],
                "stats": {"pitching": {"inningsPitched": "6.0"}},
            }
        },
    },
    "gameBoxInfo": [],
}


# ---------------------------------------------------------------------------
# Tests: fetch_schedule
# ---------------------------------------------------------------------------


def test_fetch_schedule_returns_games(client):
    """fetch_schedule returns a list of MLBGame on success."""
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.schedule.return_value = [SAMPLE_SCHEDULE_GAME]
        games = client.fetch_schedule(date(2025, 4, 10))

    assert len(games) == 1
    assert isinstance(games[0], MLBGame)


def test_game_pk_is_integer(client):
    """game_pk field is always an integer."""
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.schedule.return_value = [SAMPLE_SCHEDULE_GAME]
        games = client.fetch_schedule(date(2025, 4, 10))

    assert isinstance(games[0].game_pk, int)
    assert games[0].game_pk == 745632


def test_schedule_game_scores_populated(client):
    """Final game has home/away scores parsed correctly."""
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.schedule.return_value = [SAMPLE_SCHEDULE_GAME]
        games = client.fetch_schedule(date(2025, 4, 10))

    g = games[0]
    assert g.home_score == 5
    assert g.away_score == 3
    assert g.home_team_id == 147
    assert g.away_team_id == 111


def test_probable_pitchers_populated(client):
    """Probable pitchers are parsed from schedule game."""
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.schedule.return_value = [SAMPLE_SCHEDULE_GAME]
        games = client.fetch_schedule(date(2025, 4, 10))

    g = games[0]
    assert g.home_starter_id == 660271
    assert g.home_starter_name == "Gerrit Cole"
    assert g.away_starter_id == 608566
    assert g.away_starter_name == "Chris Sale"


def test_schedule_no_starter_returns_none(client):
    """Missing probable pitcher fields return None (not 0 or empty string)."""
    game = {**SAMPLE_SCHEDULE_GAME, "home_probable_pitcher_id": None, "home_probable_pitcher": None}
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.schedule.return_value = [game]
        games = client.fetch_schedule(date(2025, 4, 10))

    assert games[0].home_starter_id is None
    assert games[0].home_starter_name is None


def test_fetch_schedule_api_error_returns_empty(client):
    """API failure returns empty list (no exception propagated)."""
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.schedule.side_effect = Exception("network error")
        games = client.fetch_schedule(date(2025, 4, 10))

    assert games == []


# ---------------------------------------------------------------------------
# Tests: fetch_confirmed_lineups
# ---------------------------------------------------------------------------


def test_confirmed_lineup_has_9_batters(client):
    """Complete lineup has 9 batters and confirmed=True."""
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.boxscore_data.return_value = SAMPLE_BOXSCORE
        lineups = client.fetch_confirmed_lineups(745632)

    assert len(lineups) == 2
    home_lineup = next(lu for lu in lineups if lu.team_id == 147)
    assert home_lineup.confirmed is True
    assert len(home_lineup.batters) == 9


def test_lineup_batter_has_required_fields(client):
    """Each batter dict has player_id, full_name, batting_order, position."""
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.boxscore_data.return_value = SAMPLE_BOXSCORE
        lineups = client.fetch_confirmed_lineups(745632)

    home_lineup = next(lu for lu in lineups if lu.team_id == 147)
    batter = home_lineup.batters[0]
    assert "player_id" in batter
    assert "full_name" in batter
    assert "batting_order" in batter
    assert "position" in batter


def test_lineup_api_error_returns_empty(client):
    """Boxscore API failure returns empty list."""
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.boxscore_data.side_effect = Exception("timeout")
        lineups = client.fetch_confirmed_lineups(745632)

    assert lineups == []


# ---------------------------------------------------------------------------
# Tests: fetch_game_result
# ---------------------------------------------------------------------------


def test_fetch_game_result_final_scores(client):
    """Final game result has correct scores and team IDs."""
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.boxscore_data.return_value = SAMPLE_BOXSCORE
        result = client.fetch_game_result(745632)

    assert isinstance(result, MLBGameResult)
    assert result.home_score == 5
    assert result.away_score == 3
    assert result.home_team_id == 147
    assert result.away_team_id == 111


def test_fetch_game_result_api_error_returns_none(client):
    """API failure returns None."""
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.boxscore_data.side_effect = Exception("API down")
        result = client.fetch_game_result(745632)

    assert result is None


# ---------------------------------------------------------------------------
# Tests: fetch_probable_pitchers
# ---------------------------------------------------------------------------


def test_fetch_probable_pitchers_returns_dict(client):
    """Returns dict keyed by game_pk with home/away sub-dicts."""
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.schedule.return_value = [SAMPLE_SCHEDULE_GAME]
        pitchers = client.fetch_probable_pitchers(date(2025, 4, 10))

    assert 745632 in pitchers
    assert pitchers[745632]["home"]["id"] == 660271
    assert pitchers[745632]["away"]["id"] == 608566


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


def test_error_handling_bad_schedule_data(client):
    """Malformed game dict in schedule is skipped, not raised."""
    bad_game = {"game_id": "bad_id", "game_date": "not-a-date"}
    with patch("pipelines.mlb_stats_api.statsapi") as mock:
        mock.schedule.return_value = [bad_game]
        games = client.fetch_schedule(date(2025, 4, 10))

    # Malformed game is skipped
    assert games == []
