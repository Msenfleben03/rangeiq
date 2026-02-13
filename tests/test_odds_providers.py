"""Tests for the multi-modal odds retrieval system."""

from __future__ import annotations

import csv
import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from pipelines.closing_odds_collector import ClosingOdds
from pipelines.odds_providers import (
    ESPNOddsProvider,
    ManualOddsProvider,
    ScraperOddsProvider,
    TheOddsAPIProvider,
    _fuzzy_match,
    _safe_float,
    _safe_int,
)
from pipelines.odds_orchestrator import (
    CreditBudget,
    OddsCache,
    OddsOrchestrator,
)


# ============================================================================
# Helper fixtures
# ============================================================================


@pytest.fixture
def sample_csv(tmp_path):
    """Create a sample odds CSV file."""
    csv_file = tmp_path / "odds.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "game_id",
                "sportsbook",
                "spread_home",
                "spread_home_odds",
                "spread_away_odds",
                "total",
                "over_odds",
                "under_odds",
                "moneyline_home",
                "moneyline_away",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "game_id": "GAME001",
                "sportsbook": "draftkings",
                "spread_home": "-5.5",
                "spread_home_odds": "-110",
                "spread_away_odds": "-110",
                "total": "145.5",
                "over_odds": "-110",
                "under_odds": "-110",
                "moneyline_home": "-220",
                "moneyline_away": "+180",
            }
        )
        writer.writerow(
            {
                "game_id": "GAME002",
                "sportsbook": "fanduel",
                "spread_home": "3.0",
                "spread_home_odds": "-105",
                "spread_away_odds": "-115",
                "total": "150.0",
                "over_odds": "-108",
                "under_odds": "-112",
                "moneyline_home": "+130",
                "moneyline_away": "-150",
            }
        )
    return csv_file


@pytest.fixture
def mock_odds_api_response():
    """Sample The Odds API response."""
    return [
        {
            "id": "abc123",
            "sport_key": "basketball_ncaab",
            "home_team": "Duke Blue Devils",
            "away_team": "North Carolina Tar Heels",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "markets": [
                        {
                            "key": "spreads",
                            "outcomes": [
                                {
                                    "name": "Duke Blue Devils",
                                    "price": -110,
                                    "point": -5.5,
                                },
                                {
                                    "name": "North Carolina Tar Heels",
                                    "price": -110,
                                    "point": 5.5,
                                },
                            ],
                        },
                        {
                            "key": "h2h",
                            "outcomes": [
                                {"name": "Duke Blue Devils", "price": -220},
                                {"name": "North Carolina Tar Heels", "price": 180},
                            ],
                        },
                    ],
                }
            ],
        }
    ]


@pytest.fixture
def mock_espn_response():
    """Sample ESPN scoreboard response."""
    return {
        "events": [
            {
                "id": "espn_001",
                "competitions": [
                    {
                        "competitors": [
                            {
                                "homeAway": "home",
                                "team": {"displayName": "Duke Blue Devils"},
                            },
                            {
                                "homeAway": "away",
                                "team": {"displayName": "North Carolina Tar Heels"},
                            },
                        ],
                        "odds": [
                            {
                                "provider": {"name": "DraftKings"},
                                "spread": -5.5,
                                "spreadOdds": -110,
                                "overUnder": 145.5,
                                "overOdds": -110,
                                "underOdds": -110,
                                "homeTeamOdds": {"moneyLine": -220},
                                "awayTeamOdds": {"moneyLine": 180},
                            }
                        ],
                    }
                ],
            }
        ]
    }


# ============================================================================
# Tests: Helper functions
# ============================================================================


class TestHelpers:
    def test_safe_float_valid(self):
        assert _safe_float("5.5") == 5.5
        assert _safe_float(-3.0) == -3.0

    def test_safe_float_invalid(self):
        assert _safe_float(None) is None
        assert _safe_float("abc") is None

    def test_safe_int_valid(self):
        assert _safe_int("-110") == -110
        assert _safe_int(150) == 150

    def test_safe_int_invalid(self):
        assert _safe_int(None) is None
        assert _safe_int("abc") is None

    def test_fuzzy_match_exact(self):
        assert _fuzzy_match("Duke", "Duke")

    def test_fuzzy_match_substring(self):
        assert _fuzzy_match("Duke", "Duke Blue Devils")

    def test_fuzzy_match_case_insensitive(self):
        assert _fuzzy_match("duke", "DUKE")

    def test_fuzzy_match_no_match(self):
        assert not _fuzzy_match("Duke", "Kansas")


# ============================================================================
# Tests: ManualOddsProvider
# ============================================================================


class TestManualOddsProvider:
    def test_load_csv(self, sample_csv):
        provider = ManualOddsProvider(sample_csv)
        count = provider.load_csv()
        assert count == 2

    def test_is_available(self, sample_csv):
        provider = ManualOddsProvider(sample_csv)
        assert provider.is_available

    def test_not_available_no_file(self, tmp_path):
        provider = ManualOddsProvider(tmp_path / "nonexistent.csv")
        assert not provider.is_available

    def test_provider_name(self, sample_csv):
        provider = ManualOddsProvider(sample_csv)
        assert provider.provider_name == "manual_csv"

    def test_cost_is_zero(self, sample_csv):
        provider = ManualOddsProvider(sample_csv)
        assert provider.cost_per_request == 0.0

    def test_fetch_game_odds(self, sample_csv):
        provider = ManualOddsProvider(sample_csv)
        provider.load_csv()
        odds = provider.fetch_game_odds("ncaab", "Duke", "UNC", "GAME001")
        assert odds is not None
        assert odds.spread_home == -5.5
        assert odds.spread_home_odds == -110
        assert odds.moneyline_home == -220
        assert odds.moneyline_away == 180
        assert odds.total == 145.5
        assert odds.confidence == 1.0

    def test_fetch_game_not_found(self, sample_csv):
        provider = ManualOddsProvider(sample_csv)
        provider.load_csv()
        odds = provider.fetch_game_odds("ncaab", "Duke", "UNC", "NONEXISTENT")
        assert odds is None

    def test_fetch_slate(self, sample_csv):
        provider = ManualOddsProvider(sample_csv)
        provider.load_csv()
        slate = provider.fetch_slate_odds("ncaab", "2026-02-15")
        assert len(slate) == 2


# ============================================================================
# Tests: TheOddsAPIProvider
# ============================================================================


class TestTheOddsAPIProvider:
    def test_provider_name(self):
        provider = TheOddsAPIProvider(api_key="test_key")
        assert provider.provider_name == "the_odds_api"

    def test_not_available_without_key(self):
        provider = TheOddsAPIProvider(api_key="")
        assert not provider.is_available

    def test_available_with_key(self):
        provider = TheOddsAPIProvider(api_key="test_key")
        assert provider.is_available

    @patch("pipelines.odds_providers.requests.get")
    def test_fetch_game_odds(self, mock_get, mock_odds_api_response):
        mock_response = MagicMock()
        mock_response.json.return_value = mock_odds_api_response
        mock_response.headers = {
            "x-requests-remaining": "499",
            "x-requests-used": "1",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = TheOddsAPIProvider(api_key="test_key")
        odds = provider.fetch_game_odds("ncaab", "Duke", "North Carolina", "abc123")

        assert odds is not None
        assert odds.sportsbook == "draftkings"
        assert odds.spread_home == -5.5
        assert odds.spread_home_odds == -110
        assert odds.moneyline_home == -220
        assert odds.confidence == 0.95

    @patch("pipelines.odds_providers.requests.get")
    def test_credit_tracking(self, mock_get, mock_odds_api_response):
        mock_response = MagicMock()
        mock_response.json.return_value = mock_odds_api_response
        mock_response.headers = {
            "x-requests-remaining": "498",
            "x-requests-used": "2",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = TheOddsAPIProvider(api_key="test_key")
        provider.fetch_slate_odds("ncaab", "2026-02-15")

        assert provider.credits_remaining == 498
        assert provider.credits_used == 2

    @patch("pipelines.odds_providers.requests.get")
    def test_fetch_api_error(self, mock_get):
        mock_get.side_effect = Exception("Connection refused")
        provider = TheOddsAPIProvider(api_key="test_key")
        odds = provider.fetch_game_odds("ncaab", "Duke", "UNC", "game1")
        assert odds is None


# ============================================================================
# Tests: ESPNOddsProvider
# ============================================================================


class TestESPNOddsProvider:
    def test_provider_name(self):
        provider = ESPNOddsProvider()
        assert provider.provider_name == "espn"

    def test_cost_is_zero(self):
        provider = ESPNOddsProvider()
        assert provider.cost_per_request == 0.0

    @patch("pipelines.odds_providers.requests.get")
    def test_fetch_game_odds(self, mock_get, mock_espn_response):
        mock_response = MagicMock()
        mock_response.json.return_value = mock_espn_response
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = ESPNOddsProvider()
        odds = provider.fetch_game_odds("ncaab", "Duke", "North Carolina", "espn_001")

        assert odds is not None
        assert odds.spread_home == -5.5
        assert odds.total == 145.5
        assert odds.confidence == 0.80

    @patch("pipelines.odds_providers.requests.get")
    def test_fetch_slate(self, mock_get, mock_espn_response):
        mock_response = MagicMock()
        mock_response.json.return_value = mock_espn_response
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = ESPNOddsProvider()
        results = provider.fetch_slate_odds("ncaab", "20260215")
        assert len(results) >= 1

    def test_unsupported_sport(self):
        provider = ESPNOddsProvider()
        result = provider.fetch_game_odds("cricket", "A", "B", "g1")
        assert result is None


# ============================================================================
# Tests: ScraperOddsProvider
# ============================================================================


class TestScraperOddsProvider:
    def test_provider_name(self):
        provider = ScraperOddsProvider()
        assert provider.provider_name == "selenium_scraper"

    def test_cost_is_zero(self):
        provider = ScraperOddsProvider()
        assert provider.cost_per_request == 0.0


# ============================================================================
# Tests: OddsCache
# ============================================================================


class TestOddsCache:
    def test_put_and_get(self):
        cache = OddsCache(ttl=300)
        odds = ClosingOdds(
            game_id="g1",
            sportsbook="dk",
            captured_at=datetime.now(timezone.utc),
        )
        cache.put("key1", odds)
        result = cache.get("key1")
        assert result is not None
        assert result.game_id == "g1"

    def test_miss(self):
        cache = OddsCache(ttl=300)
        assert cache.get("nonexistent") is None

    def test_expiry(self):
        cache = OddsCache(ttl=0)  # Immediate expiry
        odds = ClosingOdds(
            game_id="g1",
            sportsbook="dk",
            captured_at=datetime.now(timezone.utc),
        )
        cache.put("key1", odds)
        time.sleep(0.01)
        assert cache.get("key1") is None

    def test_stats(self):
        cache = OddsCache(ttl=300)
        odds = ClosingOdds(
            game_id="g1",
            sportsbook="dk",
            captured_at=datetime.now(timezone.utc),
        )
        cache.put("key1", odds)
        cache.get("key1")  # hit
        cache.get("key2")  # miss

        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_clear_expired(self):
        cache = OddsCache(ttl=0)
        odds = ClosingOdds(
            game_id="g1",
            sportsbook="dk",
            captured_at=datetime.now(timezone.utc),
        )
        cache.put("key1", odds)
        time.sleep(0.01)
        cleared = cache.clear_expired()
        assert cleared == 1


# ============================================================================
# Tests: CreditBudget
# ============================================================================


class TestCreditBudget:
    def test_initial_state(self, tmp_path):
        usage_file = tmp_path / "usage.json"
        budget = CreditBudget(monthly_limit=500, usage_file=str(usage_file))
        assert budget.can_use_api
        assert not budget.is_warning

    def test_record_usage(self, tmp_path):
        usage_file = tmp_path / "usage.json"
        budget = CreditBudget(monthly_limit=500, usage_file=str(usage_file))
        budget.record_usage(credits_used=100, credits_remaining=400)

        status = budget.status
        assert status["credits_used"] == 100
        assert status["credits_remaining"] == 400

    def test_warning_threshold(self, tmp_path):
        usage_file = tmp_path / "usage.json"
        budget = CreditBudget(monthly_limit=500, warning_pct=0.80, usage_file=str(usage_file))
        budget.record_usage(credits_used=400, credits_remaining=100)
        assert budget.is_warning
        assert budget.can_use_api

    def test_cutoff_threshold(self, tmp_path):
        usage_file = tmp_path / "usage.json"
        budget = CreditBudget(monthly_limit=500, cutoff_pct=0.90, usage_file=str(usage_file))
        budget.record_usage(credits_used=451, credits_remaining=49)
        assert not budget.can_use_api

    def test_persists_to_file(self, tmp_path):
        usage_file = tmp_path / "usage.json"
        budget = CreditBudget(monthly_limit=500, usage_file=str(usage_file))
        budget.record_usage(credits_used=50, credits_remaining=450)

        assert usage_file.exists()
        with open(usage_file) as f:
            data = json.load(f)
        assert data["credits_used"] == 50


# ============================================================================
# Tests: OddsOrchestrator
# ============================================================================


class TestOddsOrchestrator:
    def test_add_provider(self, tmp_path):
        orch = OddsOrchestrator(
            usage_file=str(tmp_path / "usage.json"),
        )
        provider = ManualOddsProvider()
        orch.add_provider(provider)
        assert len(orch._providers) == 1

    def test_invalid_mode_raises(self, tmp_path):
        orch = OddsOrchestrator(
            usage_file=str(tmp_path / "usage.json"),
        )
        with pytest.raises(ValueError, match="Invalid mode"):
            orch.fetch_odds("ncaab", "Duke", "UNC", "g1", mode="invalid")

    @patch("pipelines.odds_providers.requests.get")
    def test_auto_fallback_to_espn(self, mock_get, mock_espn_response, tmp_path):
        """When API provider has no key, auto should fall through to ESPN."""
        mock_response = MagicMock()
        mock_response.json.return_value = mock_espn_response
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        orch = OddsOrchestrator(
            usage_file=str(tmp_path / "usage.json"),
        )
        # Add API with no key (unavailable) then ESPN
        orch.add_provider(TheOddsAPIProvider(api_key=""))
        orch.add_provider(ESPNOddsProvider())

        result = orch.fetch_odds("ncaab", "Duke", "North Carolina", "espn_001")
        assert result is not None
        assert result.spread_home == -5.5

    def test_manual_mode(self, sample_csv, tmp_path):
        orch = OddsOrchestrator(
            usage_file=str(tmp_path / "usage.json"),
        )
        manual = ManualOddsProvider(sample_csv)
        manual.load_csv()
        orch.add_provider(manual)

        result = orch.fetch_odds("ncaab", "Duke", "UNC", "GAME001", mode="manual")
        assert result is not None
        assert result.spread_home == -5.5

    def test_cache_hit(self, tmp_path):
        orch = OddsOrchestrator(
            usage_file=str(tmp_path / "usage.json"),
        )
        # Pre-populate cache
        odds = ClosingOdds(
            game_id="g1",
            sportsbook="dk",
            captured_at=datetime.now(timezone.utc),
            spread_home=-3.0,
        )
        orch.cache.put("ncaab:g1", odds)

        result = orch.fetch_odds("ncaab", "Duke", "UNC", "g1")
        assert result is not None
        assert result.spread_home == -3.0

    def test_provider_health(self, sample_csv, tmp_path):
        orch = OddsOrchestrator(
            usage_file=str(tmp_path / "usage.json"),
        )
        manual = ManualOddsProvider(sample_csv)
        orch.add_provider(manual)

        health = orch.get_provider_health()
        assert "manual_csv" in health
        assert health["manual_csv"]["available"] is True

    def test_credit_budget_integration(self, tmp_path):
        orch = OddsOrchestrator(
            monthly_credit_limit=500,
            usage_file=str(tmp_path / "usage.json"),
        )
        budget = orch.get_credit_budget()
        assert budget["monthly_limit"] == 500
        assert budget["can_use_api"] is True
