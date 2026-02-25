"""Tests for opening odds fetcher."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


# -- Mock ESPN Core API data ------------------------------------------------

MOCK_ODDS_SNAPSHOT_DATA = {
    "game_id": "401720001",
    "provider_id": 100,
    "provider_name": "Draft Kings",
    "spread": -3.5,
    "over_under": 145.5,
    "home_moneyline": -150,
    "away_moneyline": 130,
    "home_spread_odds": -110,
    "away_spread_odds": -110,
    "over_odds": -110,
    "under_odds": -110,
    "home_spread_open": -3.5,
    "away_spread_open": 3.5,
    "home_spread_odds_open": -110,
    "away_spread_odds_open": -110,
    "home_ml_open": -150,
    "away_ml_open": 130,
    "total_open": 145.5,
    "over_odds_open": -110,
    "under_odds_open": -110,
    # Close fields None for pre-game
    "home_spread_close": None,
    "away_spread_close": None,
    "home_spread_odds_close": None,
    "away_spread_odds_close": None,
    "home_ml_close": None,
    "away_ml_close": None,
    "total_close": None,
    "over_odds_close": None,
    "under_odds_close": None,
}


def _make_mock_snapshot():
    """Create a mock OddsSnapshot from test data."""
    from pipelines.espn_core_odds_provider import OddsSnapshot

    return OddsSnapshot(**MOCK_ODDS_SNAPSHOT_DATA)


MOCK_SCOREBOARD_GAMES = [
    {
        "game_id": "401720001",
        "home": "DUKE",
        "away": "UNC",
        "home_id": "2305",
        "away_id": "153",
        "home_name": "Duke Blue Devils",
        "away_name": "North Carolina Tar Heels",
        "home_score": 0,
        "away_score": 0,
        "neutral_site": False,
        "status": "STATUS_SCHEDULED",
        "game_time": "2026-02-25T19:00Z",
    },
    {
        "game_id": "401720002",
        "home": "UK",
        "away": "TENN",
        "home_id": "2509",
        "away_id": "2633",
        "home_name": "Kentucky Wildcats",
        "away_name": "Tennessee Volunteers",
        "home_score": 0,
        "away_score": 0,
        "neutral_site": False,
        "status": "STATUS_SCHEDULED",
        "game_time": "2026-02-25T21:00Z",
    },
]


class TestFetchOpeningOdds:
    """Tests for fetch_opening_odds()."""

    @patch("scripts.fetch_opening_odds.ESPNCoreOddsFetcher")
    @patch("scripts.fetch_opening_odds.fetch_espn_scoreboard")
    def test_fetches_odds_for_tomorrows_games(self, mock_sb, mock_fetcher_cls):
        from scripts.fetch_opening_odds import fetch_opening_odds

        mock_sb.return_value = MOCK_SCOREBOARD_GAMES

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_game_odds.return_value = [_make_mock_snapshot()]
        mock_fetcher_cls.return_value = mock_fetcher

        db = MagicMock()
        db.execute_query.return_value = []  # No existing opening odds

        result = fetch_opening_odds(db)

        assert result["games_found"] == 2
        assert result["odds_fetched"] >= 1
        mock_fetcher.fetch_game_odds.assert_called()
        mock_fetcher.close.assert_called_once()

    @patch("scripts.fetch_opening_odds.ESPNCoreOddsFetcher")
    @patch("scripts.fetch_opening_odds.fetch_espn_scoreboard")
    def test_skips_games_with_existing_opening_odds(self, mock_sb, mock_fetcher_cls):
        from scripts.fetch_opening_odds import fetch_opening_odds

        mock_sb.return_value = MOCK_SCOREBOARD_GAMES

        mock_fetcher = MagicMock()
        mock_fetcher_cls.return_value = mock_fetcher

        db = MagicMock()
        # Both games already have opening odds
        db.execute_query.side_effect = lambda q, p=None: (
            [{"game_id": "401720001"}, {"game_id": "401720002"}] if "snapshot_type" in q else []
        )

        result = fetch_opening_odds(db)

        assert result["skipped_existing"] == 2
        mock_fetcher.fetch_game_odds.assert_not_called()

    @patch("scripts.fetch_opening_odds.fetch_espn_scoreboard")
    def test_no_games_tomorrow(self, mock_sb):
        from scripts.fetch_opening_odds import fetch_opening_odds

        mock_sb.return_value = []
        db = MagicMock()

        result = fetch_opening_odds(db)

        assert result["games_found"] == 0
        assert result["odds_fetched"] == 0


class TestStoreOpeningSnapshot:
    """Tests for store_opening_snapshot()."""

    def test_stores_with_opening_snapshot_type(self):
        from scripts.fetch_opening_odds import store_opening_snapshot

        snapshot = _make_mock_snapshot()
        db = MagicMock()

        store_opening_snapshot(db, snapshot)

        # Verify execute_query was called with INSERT
        call_args = db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "INSERT" in query
        assert "odds_snapshots" in query
        # Check snapshot_type is 'opening'
        assert "opening" in params

    def test_stores_moneyline_spread_total(self):
        from scripts.fetch_opening_odds import store_opening_snapshot

        snapshot = _make_mock_snapshot()
        db = MagicMock()

        store_opening_snapshot(db, snapshot)

        call_args = db.execute_query.call_args
        params = call_args[0][1]

        # Params should contain ML, spread, and total data
        assert -150 in params  # home ML
        assert 130 in params  # away ML
        assert -3.5 in params  # spread
        assert 145.5 in params  # total
