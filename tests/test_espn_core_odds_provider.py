"""Tests for ESPN Core API Odds Provider.

Tests cover:
    - OddsSnapshot dataclass and to_closing_odds conversion
    - parse_odds_response from real ESPN API structures
    - Parsing helpers (_parse_american, _parse_spread, etc.)
    - ESPNCoreClient rate limiting
    - ESPNCoreOddsFetcher single game and batch
    - ESPNCoreOddsProvider (OddsProvider interface)
    - Error handling and edge cases
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from pipelines.espn_core_odds_provider import (
    ESPNCoreClient,
    ESPNCoreOddsFetcher,
    ESPNCoreOddsProvider,
    OddsSnapshot,
    _parse_american,
    _parse_american_from_odds_obj,
    _parse_spread,
    _safe_float,
    _safe_int,
    parse_odds_response,
)


# =========================================================================
# Fixtures — realistic ESPN Core API responses
# =========================================================================


@pytest.fixture()
def espn_odds_response() -> dict:
    """Realistic ESPN Core API odds response for a completed NCAAB game."""
    return {
        "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/401706885/competitions/401706885/odds/58",
        "provider": {
            "id": "58",
            "name": "ESPN BET",
            "priority": 0,
        },
        "details": "ARIZ -1.5",
        "overUnder": 162.5,
        "spread": -1.5,
        "overOdds": -105.0,
        "underOdds": -115.0,
        "awayTeamOdds": {
            "favorite": False,
            "underdog": True,
            "moneyLine": 110,
            "spreadOdds": -105.0,
            "open": {
                "favorite": False,
                "pointSpread": {
                    "alternateDisplayValue": "+1.5",
                    "american": "+1.5",
                },
                "spread": {
                    "value": 1.8,
                    "displayValue": "4/5",
                    "alternateDisplayValue": "-125",
                    "decimal": 1.8,
                    "fraction": "4/5",
                    "american": "-125",
                },
                "moneyLine": {
                    "value": 1.909,
                    "displayValue": "10/11",
                    "alternateDisplayValue": "-110",
                    "decimal": 1.909,
                    "fraction": "10/11",
                    "american": "-110",
                },
            },
            "close": {
                "pointSpread": {
                    "alternateDisplayValue": "+1.5",
                    "american": "+1.5",
                },
                "spread": {
                    "value": 1.952,
                    "displayValue": "20/21",
                    "alternateDisplayValue": "-105",
                    "decimal": 1.952,
                    "fraction": "20/21",
                    "american": "-105",
                },
                "moneyLine": {
                    "value": 2.1,
                    "displayValue": "11/10",
                    "alternateDisplayValue": "+110",
                    "decimal": 2.1,
                    "fraction": "11/10",
                    "american": "+110",
                },
            },
            "current": {
                "pointSpread": {
                    "alternateDisplayValue": "+1.5",
                    "american": "+1.5",
                },
                "spread": {
                    "value": 1.952,
                    "displayValue": "20/21",
                    "alternateDisplayValue": "-105",
                    "decimal": 1.952,
                    "fraction": "20/21",
                    "american": "-105",
                },
                "moneyLine": {
                    "value": 2.1,
                    "displayValue": "11/10",
                    "alternateDisplayValue": "+110",
                    "decimal": 2.1,
                    "fraction": "11/10",
                    "american": "+110",
                },
            },
            "team": {
                "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/2025/teams/150"
            },
        },
        "homeTeamOdds": {
            "favorite": True,
            "underdog": False,
            "moneyLine": -130,
            "spreadOdds": -115.0,
            "open": {
                "favorite": True,
                "pointSpread": {
                    "value": 2.05,
                    "displayValue": "21/20",
                    "alternateDisplayValue": "-1.5",
                    "decimal": 2.05,
                    "fraction": "21/20",
                    "american": "-1.5",
                },
                "spread": {
                    "value": 2.05,
                    "displayValue": "21/20",
                    "alternateDisplayValue": "+105",
                    "decimal": 2.05,
                    "fraction": "21/20",
                    "american": "+105",
                },
                "moneyLine": {
                    "value": 1.909,
                    "displayValue": "10/11",
                    "alternateDisplayValue": "-110",
                    "decimal": 1.909,
                    "fraction": "10/11",
                    "american": "-110",
                },
            },
            "close": {
                "pointSpread": {
                    "alternateDisplayValue": "-1.5",
                    "american": "-1.5",
                },
                "spread": {
                    "value": 1.87,
                    "displayValue": "20/23",
                    "alternateDisplayValue": "-115",
                    "decimal": 1.87,
                    "fraction": "20/23",
                    "american": "-115",
                },
                "moneyLine": {
                    "value": 1.769,
                    "displayValue": "10/13",
                    "alternateDisplayValue": "-130",
                    "decimal": 1.769,
                    "fraction": "10/13",
                    "american": "-130",
                },
            },
            "current": {
                "pointSpread": {
                    "alternateDisplayValue": "-1.5",
                    "american": "-1.5",
                },
                "spread": {
                    "value": 1.87,
                    "displayValue": "20/23",
                    "alternateDisplayValue": "-115",
                    "decimal": 1.87,
                    "fraction": "20/23",
                    "american": "-115",
                },
                "moneyLine": {
                    "value": 1.769,
                    "displayValue": "10/13",
                    "alternateDisplayValue": "-130",
                    "decimal": 1.769,
                    "fraction": "10/13",
                    "american": "-130",
                },
            },
            "team": {
                "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/seasons/2025/teams/12"
            },
        },
        "moneylineWinner": False,
        "spreadWinner": False,
        "open": {
            "over": {
                "value": 1.9,
                "displayValue": "10/11",
                "alternateDisplayValue": "-110",
                "decimal": 1.9,
                "fraction": "10/11",
                "american": "-110",
            },
            "under": {
                "value": 1.9,
                "displayValue": "10/11",
                "alternateDisplayValue": "-110",
                "decimal": 1.9,
                "fraction": "10/11",
                "american": "-110",
            },
            "total": {
                "alternateDisplayValue": "161.5",
                "american": "161.5",
            },
        },
        "close": {
            "over": {
                "value": 1.952,
                "displayValue": "20/21",
                "alternateDisplayValue": "-105",
                "decimal": 1.952,
                "fraction": "20/21",
                "american": "-105",
            },
            "under": {
                "value": 1.87,
                "displayValue": "20/23",
                "alternateDisplayValue": "-115",
                "decimal": 1.87,
                "fraction": "20/23",
                "american": "-115",
            },
            "total": {
                "alternateDisplayValue": "162.5",
                "american": "162.5",
            },
        },
    }


@pytest.fixture()
def espn_odds_list_response() -> dict:
    """ESPN Core API odds list response with $ref items."""
    return {
        "count": 2,
        "pageIndex": 1,
        "pageSize": 25,
        "pageCount": 1,
        "items": [
            {
                "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/401706885/competitions/401706885/odds/58"
            },
            {
                "$ref": "http://sports.core.api.espn.com/v2/sports/basketball/leagues/mens-college-basketball/events/401706885/competitions/401706885/odds/59"
            },
        ],
    }


@pytest.fixture()
def empty_odds_response() -> dict:
    """Response for a game with no betting odds."""
    return {"count": 0, "items": []}


# =========================================================================
# Parsing helpers
# =========================================================================


class TestParseAmerican:
    """Tests for _parse_american helper."""

    def test_negative_odds(self) -> None:
        assert _parse_american("-110") == -110

    def test_positive_odds(self) -> None:
        assert _parse_american("+150") == 150

    def test_float_input(self) -> None:
        assert _parse_american(-110.0) == -110

    def test_int_input(self) -> None:
        assert _parse_american(-200) == -200

    def test_none_returns_none(self) -> None:
        assert _parse_american(None) is None

    def test_point_spread_returns_none(self) -> None:
        # Point spreads like -1.5 are not odds
        assert _parse_american("-1.5") is None
        assert _parse_american("+6.5") is None

    def test_dict_with_american_key(self) -> None:
        assert _parse_american({"american": "-110"}) == -110

    def test_invalid_string(self) -> None:
        assert _parse_american("abc") is None

    def test_zero(self) -> None:
        # Zero is edge case — not valid American odds but parses to 0
        assert _parse_american(0) == 0


class TestParseSpread:
    """Tests for _parse_spread helper."""

    def test_negative_spread(self) -> None:
        assert _parse_spread("-6.5") == -6.5

    def test_positive_spread(self) -> None:
        assert _parse_spread("+3.5") == 3.5

    def test_float_input(self) -> None:
        assert _parse_spread(1.5) == 1.5

    def test_none_returns_none(self) -> None:
        assert _parse_spread(None) is None

    def test_dict_with_american_key(self) -> None:
        assert _parse_spread({"american": "-1.5"}) == -1.5

    def test_total_value(self) -> None:
        assert _parse_spread("162.5") == 162.5


class TestParseAmericanFromOddsObj:
    """Tests for _parse_american_from_odds_obj helper."""

    def test_standard_odds_object(self) -> None:
        obj = {
            "value": 1.909,
            "displayValue": "10/11",
            "alternateDisplayValue": "-110",
            "decimal": 1.909,
            "fraction": "10/11",
            "american": "-110",
        }
        assert _parse_american_from_odds_obj(obj) == -110

    def test_positive_odds(self) -> None:
        obj = {"american": "+150"}
        assert _parse_american_from_odds_obj(obj) == 150

    def test_fallback_to_alternate_display(self) -> None:
        obj = {"alternateDisplayValue": "-120"}
        assert _parse_american_from_odds_obj(obj) == -120

    def test_none_input(self) -> None:
        assert _parse_american_from_odds_obj(None) is None

    def test_empty_dict(self) -> None:
        assert _parse_american_from_odds_obj({}) is None


class TestSafeConversions:
    """Tests for _safe_int and _safe_float."""

    def test_safe_int_from_float(self) -> None:
        assert _safe_int(-110.0) == -110

    def test_safe_int_from_string(self) -> None:
        assert _safe_int("150") == 150

    def test_safe_int_none(self) -> None:
        assert _safe_int(None) is None

    def test_safe_float_from_string(self) -> None:
        assert _safe_float("162.5") == 162.5

    def test_safe_float_none(self) -> None:
        assert _safe_float(None) is None


# =========================================================================
# parse_odds_response
# =========================================================================


class TestParseOddsResponse:
    """Tests for parse_odds_response from real API structures."""

    def test_full_response(self, espn_odds_response: dict) -> None:
        snap = parse_odds_response(espn_odds_response, "401706885")
        assert snap is not None
        assert snap.game_id == "401706885"
        assert snap.provider_id == 58
        assert snap.provider_name == "ESPN BET"

    def test_current_odds(self, espn_odds_response: dict) -> None:
        snap = parse_odds_response(espn_odds_response, "401706885")
        assert snap is not None
        assert snap.spread == -1.5
        assert snap.over_under == 162.5
        assert snap.home_moneyline == -130
        assert snap.away_moneyline == 110
        assert snap.home_spread_odds == -115
        assert snap.away_spread_odds == -105
        assert snap.over_odds == -105
        assert snap.under_odds == -115

    def test_opening_odds(self, espn_odds_response: dict) -> None:
        snap = parse_odds_response(espn_odds_response, "401706885")
        assert snap is not None
        # Home opening
        assert snap.home_spread_open == -1.5
        assert snap.home_ml_open == -110
        # Away opening
        assert snap.away_spread_open == 1.5
        assert snap.away_ml_open == -110
        # Totals opening
        assert snap.total_open == 161.5
        assert snap.over_odds_open == -110
        assert snap.under_odds_open == -110

    def test_closing_odds(self, espn_odds_response: dict) -> None:
        snap = parse_odds_response(espn_odds_response, "401706885")
        assert snap is not None
        # Home closing
        assert snap.home_spread_close == -1.5
        assert snap.home_spread_odds_close == -115
        assert snap.home_ml_close == -130
        # Away closing
        assert snap.away_spread_close == 1.5
        assert snap.away_spread_odds_close == -105
        assert snap.away_ml_close == 110
        # Totals closing
        assert snap.total_close == 162.5
        assert snap.over_odds_close == -105
        assert snap.under_odds_close == -115

    def test_missing_provider(self) -> None:
        data = {"spread": -3.5}  # No provider field
        snap = parse_odds_response(data, "123")
        assert snap is None

    def test_empty_response(self) -> None:
        snap = parse_odds_response({}, "123")
        assert snap is None

    def test_missing_open_close(self) -> None:
        """Test response without open/close data (upcoming game)."""
        data = {
            "provider": {"id": "100", "name": "DraftKings"},
            "spread": -3.5,
            "overUnder": 145.0,
            "homeTeamOdds": {
                "moneyLine": -150,
                "spreadOdds": -110.0,
            },
            "awayTeamOdds": {
                "moneyLine": 130,
                "spreadOdds": -110.0,
            },
            "overOdds": -110.0,
            "underOdds": -110.0,
        }
        snap = parse_odds_response(data, "999")
        assert snap is not None
        assert snap.spread == -3.5
        assert snap.home_moneyline == -150
        assert snap.home_ml_open is None
        assert snap.home_ml_close is None


# =========================================================================
# OddsSnapshot
# =========================================================================


class TestOddsSnapshot:
    """Tests for OddsSnapshot dataclass."""

    def test_frozen(self) -> None:
        snap = OddsSnapshot(game_id="123", provider_id=58, provider_name="ESPN BET")
        with pytest.raises(AttributeError):
            snap.spread = 5.0  # type: ignore[misc]

    def test_to_dict(self) -> None:
        snap = OddsSnapshot(
            game_id="123",
            provider_id=58,
            provider_name="ESPN BET",
            spread=-3.5,
            home_moneyline=-150,
        )
        d = snap.to_dict()
        assert d["game_id"] == "123"
        assert d["spread"] == -3.5
        assert d["home_moneyline"] == -150
        assert d["home_ml_open"] is None

    def test_to_closing_odds_with_close(self, espn_odds_response: dict) -> None:
        snap = parse_odds_response(espn_odds_response, "401706885")
        assert snap is not None
        co = snap.to_closing_odds(use_close=True)
        assert co.is_closing is True
        assert co.moneyline_home == -130
        assert co.moneyline_away == 110
        assert co.spread_home == -1.5
        assert co.sportsbook == "espn_bet"
        assert co.confidence == 0.92

    def test_to_closing_odds_without_close(self) -> None:
        snap = OddsSnapshot(
            game_id="123",
            provider_id=100,
            provider_name="Draft Kings",
            spread=-3.5,
            home_moneyline=-150,
            away_moneyline=130,
            home_spread_odds=-110,
            away_spread_odds=-110,
            over_under=145.0,
            over_odds=-110,
            under_odds=-110,
        )
        co = snap.to_closing_odds(use_close=True)
        # No close data, should fall back to current
        assert co.is_closing is False
        assert co.moneyline_home == -150
        assert co.spread_home == -3.5

    def test_to_closing_odds_force_current(self, espn_odds_response: dict) -> None:
        snap = parse_odds_response(espn_odds_response, "401706885")
        assert snap is not None
        co = snap.to_closing_odds(use_close=False)
        assert co.is_closing is False
        assert co.moneyline_home == -130  # current = close for completed games


# =========================================================================
# ESPNCoreClient
# =========================================================================


class TestESPNCoreClient:
    """Tests for the HTTP client with rate limiting."""

    def test_rate_limiting(self) -> None:
        """Verify rate limiter enforces delay between requests."""
        client = ESPNCoreClient(requests_per_second=100.0)  # Fast for testing
        client._last_request_time = time.time()

        # Mock successful response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"test": True}
        mock_resp.raise_for_status = MagicMock()

        with patch.object(client._session, "get", return_value=mock_resp):
            start = time.time()
            client.get("http://example.com/test")
            elapsed = time.time() - start
            # Should wait at least the delay (0.01s for 100 rps)
            assert elapsed >= 0.005

    def test_retry_on_failure(self) -> None:
        """Verify retry with exponential backoff."""
        client = ESPNCoreClient(requests_per_second=100.0)

        mock_resp_fail = MagicMock()
        mock_resp_fail.status_code = 500
        mock_resp_fail.raise_for_status.side_effect = requests.HTTPError("Server error")

        mock_resp_ok = MagicMock()
        mock_resp_ok.status_code = 200
        mock_resp_ok.json.return_value = {"ok": True}
        mock_resp_ok.raise_for_status = MagicMock()

        with patch.object(
            client._session,
            "get",
            side_effect=[mock_resp_fail, mock_resp_ok],
        ):
            with patch("pipelines.espn_core_odds_provider.time.sleep"):
                result = client.get("http://example.com/test")
                assert result == {"ok": True}

    def test_all_retries_fail(self) -> None:
        """Verify exception after all retries exhausted."""
        client = ESPNCoreClient(requests_per_second=100.0)

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.raise_for_status.side_effect = requests.HTTPError("Server error")

        with patch.object(client._session, "get", return_value=mock_resp):
            with patch("pipelines.espn_core_odds_provider.time.sleep"):
                with pytest.raises(
                    requests.RequestException,
                    match="All 3 attempts failed",
                ):
                    client.get("http://example.com/test")


# =========================================================================
# ESPNCoreOddsFetcher
# =========================================================================


class TestESPNCoreOddsFetcher:
    """Tests for the high-level odds fetcher."""

    def test_invalid_sport(self) -> None:
        with pytest.raises(ValueError, match="Unsupported sport"):
            ESPNCoreOddsFetcher(sport="curling")

    def test_fetch_game_odds_with_results(
        self,
        espn_odds_list_response: dict,
        espn_odds_response: dict,
    ) -> None:
        """Test single game fetch with mocked HTTP."""
        fetcher = ESPNCoreOddsFetcher(sport="ncaab")

        def mock_get(url: str) -> dict:
            if url.endswith("/odds"):
                return espn_odds_list_response
            return espn_odds_response

        with patch.object(fetcher._client, "get", side_effect=mock_get):
            snapshots = fetcher.fetch_game_odds("401706885")

        assert len(snapshots) == 2
        assert snapshots[0].provider_name == "ESPN BET"
        assert snapshots[0].home_moneyline == -130

    def test_fetch_game_odds_empty(
        self,
        empty_odds_response: dict,
    ) -> None:
        """Test game with no odds returns empty list."""
        fetcher = ESPNCoreOddsFetcher(sport="ncaab")

        with patch.object(
            fetcher._client,
            "get",
            return_value=empty_odds_response,
        ):
            snapshots = fetcher.fetch_game_odds("401725371")

        assert snapshots == []

    def test_fetch_game_odds_network_error(self) -> None:
        """Test graceful handling of network errors."""
        fetcher = ESPNCoreOddsFetcher(sport="ncaab")

        with patch.object(
            fetcher._client,
            "get",
            side_effect=requests.RequestException("Network error"),
        ):
            snapshots = fetcher.fetch_game_odds("401706885")

        assert snapshots == []

    def test_fetch_batch(
        self,
        espn_odds_list_response: dict,
        espn_odds_response: dict,
        empty_odds_response: dict,
    ) -> None:
        """Test batch fetching of multiple events."""
        fetcher = ESPNCoreOddsFetcher(sport="ncaab")

        call_count = 0

        def mock_get(url: str) -> dict:
            nonlocal call_count
            call_count += 1
            if "999" in url and url.endswith("/odds"):
                return empty_odds_response
            if url.endswith("/odds"):
                return espn_odds_list_response
            return espn_odds_response

        with patch.object(fetcher._client, "get", side_effect=mock_get):
            results = fetcher.fetch_batch(["401706885", "999"])

        assert "401706885" in results
        assert "999" not in results
        assert len(results["401706885"]) == 2

    def test_fetch_game_odds_direct(
        self,
        espn_odds_response: dict,
    ) -> None:
        """Test direct provider access."""
        fetcher = ESPNCoreOddsFetcher(sport="ncaab")

        with patch.object(
            fetcher._client,
            "get",
            return_value=espn_odds_response,
        ):
            snap = fetcher.fetch_game_odds_direct("401706885", 58)

        assert snap is not None
        assert snap.provider_id == 58


# =========================================================================
# ESPNCoreOddsProvider (OddsProvider interface)
# =========================================================================


class TestESPNCoreOddsProvider:
    """Tests for the OddsProvider implementation."""

    def test_provider_properties(self) -> None:
        provider = ESPNCoreOddsProvider(sport="ncaab")
        assert provider.provider_name == "espn_core_api"
        assert provider.is_available is True
        assert provider.cost_per_request == 0.0

    def test_fetch_game_odds_returns_closing(
        self,
        espn_odds_list_response: dict,
        espn_odds_response: dict,
    ) -> None:
        """Test that fetch_game_odds returns ClosingOdds."""
        provider = ESPNCoreOddsProvider(sport="ncaab")

        def mock_get(url: str) -> dict:
            if url.endswith("/odds"):
                return espn_odds_list_response
            return espn_odds_response

        with patch.object(
            provider._fetcher._client,
            "get",
            side_effect=mock_get,
        ):
            result = provider.fetch_game_odds(
                "ncaab",
                "Duke",
                "Arizona",
                "401706885",
            )

        assert result is not None
        assert result.sportsbook == "espn_bet"
        assert result.moneyline_home == -130
        assert result.is_closing is True

    def test_fetch_game_odds_no_odds(
        self,
        empty_odds_response: dict,
    ) -> None:
        provider = ESPNCoreOddsProvider(sport="ncaab")

        with patch.object(
            provider._fetcher._client,
            "get",
            return_value=empty_odds_response,
        ):
            result = provider.fetch_game_odds(
                "ncaab",
                "Home",
                "Away",
                "401725371",
            )

        assert result is None

    def test_filters_live_odds(
        self,
        espn_odds_response: dict,
    ) -> None:
        """Verify live-odds provider (59) is filtered out when pre-game available."""
        provider = ESPNCoreOddsProvider(sport="ncaab")

        live_response = {**espn_odds_response}
        live_response["provider"] = {
            "id": "59",
            "name": "ESPN Bet - Live Odds",
            "priority": 1,
        }

        list_response = {
            "count": 2,
            "items": [
                {"$ref": "http://example.com/odds/58"},
                {"$ref": "http://example.com/odds/59"},
            ],
        }

        call_idx = 0

        def mock_get(url: str) -> dict:
            nonlocal call_idx
            call_idx += 1
            if url.endswith("/odds"):
                return list_response
            # First ref = pre-game (58), second = live (59)
            if call_idx == 2:
                return espn_odds_response
            return live_response

        with patch.object(
            provider._fetcher._client,
            "get",
            side_effect=mock_get,
        ):
            result = provider.fetch_game_odds(
                "ncaab",
                "",
                "",
                "401706885",
            )

        assert result is not None
        assert result.sportsbook == "espn_bet"  # Pre-game, not live


# =========================================================================
# Edge cases
# =========================================================================


class TestEdgeCases:
    """Edge case and error handling tests."""

    def test_malformed_odds_object(self) -> None:
        """Test parsing of malformed odds data."""
        data = {
            "provider": {"id": "42", "name": "Unknown"},
            "spread": "not_a_number",
            "overUnder": None,
            "homeTeamOdds": {},
            "awayTeamOdds": {},
        }
        snap = parse_odds_response(data, "123")
        assert snap is not None
        assert snap.spread is None
        assert snap.over_under is None

    def test_partial_open_data(self) -> None:
        """Test response with only some open fields."""
        data = {
            "provider": {"id": "58", "name": "ESPN BET"},
            "spread": -3.0,
            "overUnder": 145.0,
            "homeTeamOdds": {
                "moneyLine": -150,
                "spreadOdds": -110.0,
                "open": {
                    "moneyLine": {"american": "-120"},
                    # No pointSpread or spread
                },
            },
            "awayTeamOdds": {
                "moneyLine": 130,
                "spreadOdds": -110.0,
            },
        }
        snap = parse_odds_response(data, "456")
        assert snap is not None
        assert snap.home_ml_open == -120
        assert snap.home_spread_open is None
        assert snap.home_spread_odds_open is None

    def test_snapshot_to_dict_all_none(self) -> None:
        """Test to_dict with minimal data."""
        snap = OddsSnapshot(
            game_id="789",
            provider_id=100,
            provider_name="DraftKings",
        )
        d = snap.to_dict()
        assert d["game_id"] == "789"
        assert d["spread"] is None
        assert d["home_ml_close"] is None
        # Should have all 29 keys
        assert len(d) == 29

    def test_ref_url_failure_continues(
        self,
        espn_odds_list_response: dict,
    ) -> None:
        """Test that failure to follow one $ref doesn't block others."""
        fetcher = ESPNCoreOddsFetcher(sport="ncaab")

        call_count = 0

        def mock_get(url: str) -> dict:
            nonlocal call_count
            call_count += 1
            if url.endswith("/odds"):
                return espn_odds_list_response
            if call_count == 2:
                raise requests.RequestException("Network error on first ref")
            return {
                "provider": {"id": "59", "name": "ESPN Bet Live"},
                "spread": 5.0,
                "homeTeamOdds": {"moneyLine": 200},
                "awayTeamOdds": {"moneyLine": -250},
            }

        with patch.object(fetcher._client, "get", side_effect=mock_get):
            snapshots = fetcher.fetch_game_odds("401706885")

        # Should get 1 snapshot (second ref succeeded)
        assert len(snapshots) == 1
