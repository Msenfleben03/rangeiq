"""Multi-Modal Odds Providers.

Implements a strategy-pattern architecture where multiple odds data sources
share a common interface: ManualOddsProvider, TheOddsAPIProvider,
ESPNOddsProvider, and ScraperOddsProvider.

Each provider can fetch odds for a single game or an entire slate of games.
The OddsOrchestrator (see odds_orchestrator.py) manages provider selection,
fallback chains, and caching.
"""

from __future__ import annotations

import csv
import logging
import os
import re
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from pipelines.closing_odds_collector import ClosingOdds

logger = logging.getLogger(__name__)


# =============================================================================
# ABSTRACT BASE
# =============================================================================


class OddsProvider(ABC):
    """Base class for all odds retrieval methods."""

    @abstractmethod
    def fetch_game_odds(
        self,
        sport: str,
        home: str,
        away: str,
        game_id: str,
    ) -> Optional[ClosingOdds]:
        """Fetch odds for a single game.

        Args:
            sport: Sport code (e.g., 'basketball_ncaab').
            home: Home team name or abbreviation.
            away: Away team name or abbreviation.
            game_id: Unique game identifier.

        Returns:
            ClosingOdds if successful, None otherwise.
        """

    @abstractmethod
    def fetch_slate_odds(
        self,
        sport: str,
        date: str,
    ) -> list[ClosingOdds]:
        """Fetch odds for all games on a given date.

        Args:
            sport: Sport code.
            date: Date string in YYYY-MM-DD format.

        Returns:
            List of ClosingOdds for available games.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Whether the provider is currently usable."""

    @property
    @abstractmethod
    def cost_per_request(self) -> float:
        """Cost per API request (0.0 for free providers)."""


# =============================================================================
# MANUAL CSV PROVIDER
# =============================================================================


class ManualOddsProvider(OddsProvider):
    """Reads odds from a CSV file (manual entry by user).

    CSV format:
        game_id,sportsbook,spread_home,spread_home_odds,spread_away_odds,
        total,over_odds,under_odds,moneyline_home,moneyline_away

    Always available, zero cost, highest confidence (human-verified).
    """

    def __init__(self, csv_path: str | Path | None = None):
        """Initialize the manual CSV odds provider.

        Args:
            csv_path: Optional path to CSV file containing odds data.
        """
        self._csv_path = Path(csv_path) if csv_path else None
        self._cache: dict[str, ClosingOdds] = {}

    @property
    def provider_name(self) -> str:
        """Return the human-readable provider name."""
        return "manual_csv"

    @property
    def is_available(self) -> bool:
        """Check if the provider is currently usable."""
        return self._csv_path is not None and self._csv_path.exists()

    @property
    def cost_per_request(self) -> float:
        """Return cost per API request (free for manual provider)."""
        return 0.0

    def load_csv(self, path: str | Path | None = None) -> int:
        """Load odds data from CSV file.

        Args:
            path: Optional override path; otherwise uses configured path.

        Returns:
            Number of records loaded.
        """
        csv_file = Path(path) if path else self._csv_path
        if csv_file is None or not csv_file.exists():
            logger.warning("Manual CSV not found: %s", csv_file)
            return 0

        self._csv_path = csv_file
        self._cache.clear()
        count = 0

        with open(csv_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                game_id = row.get("game_id", "").strip()
                if not game_id:
                    continue

                odds = ClosingOdds(
                    game_id=game_id,
                    sportsbook=row.get("sportsbook", "manual").strip(),
                    captured_at=datetime.now(timezone.utc),
                    spread_home=_safe_float(row.get("spread_home")),
                    spread_home_odds=_safe_int(row.get("spread_home_odds")),
                    spread_away_odds=_safe_int(row.get("spread_away_odds")),
                    total=_safe_float(row.get("total")),
                    over_odds=_safe_int(row.get("over_odds")),
                    under_odds=_safe_int(row.get("under_odds")),
                    moneyline_home=_safe_int(row.get("moneyline_home")),
                    moneyline_away=_safe_int(row.get("moneyline_away")),
                    is_closing=False,
                    confidence=1.0,
                )
                self._cache[game_id] = odds
                count += 1

        logger.info("Loaded %d odds records from %s", count, csv_file)
        return count

    def fetch_game_odds(
        self,
        sport: str,
        home: str,
        away: str,
        game_id: str,
    ) -> Optional[ClosingOdds]:
        """Fetch odds for a single game from cached CSV data."""
        if not self._cache:
            self.load_csv()
        return self._cache.get(game_id)

    def fetch_slate_odds(self, sport: str, date: str) -> list[ClosingOdds]:
        """Fetch odds for all games from cached CSV data."""
        if not self._cache:
            self.load_csv()
        return list(self._cache.values())


# =============================================================================
# THE ODDS API PROVIDER
# =============================================================================

# Sport key mappings for The Odds API
ODDS_API_SPORT_KEYS = {
    "ncaab": "basketball_ncaab",
    "nba": "basketball_nba",
    "nfl": "americanfootball_nfl",
    "ncaaf": "americanfootball_ncaaf",
    "mlb": "baseball_mlb",
}

ODDS_API_BOOKMAKERS = [
    "draftkings",
    "fanduel",
    "betmgm",
    "williamhill_us",  # Caesars
    "espnbet",
]


class TheOddsAPIProvider(OddsProvider):
    """Retrieves odds from The Odds API (https://the-odds-api.com).

    Free tier: 500 credits/month. Each API call costs 1 credit per
    market per region requested.

    Credit strategy:
        - Default: pull 'spreads' only (1 credit)
        - For close games: add 'h2h' (2 credits total)
        - Budget tracking via response headers
    """

    BASE_URL = "https://api.the-odds-api.com/v4/sports"

    def __init__(
        self,
        api_key: str | None = None,
        monthly_credit_limit: int = 500,
    ):
        """Initialize The Odds API provider.

        Args:
            api_key: API key (defaults to ODDS_API_KEY env var).
            monthly_credit_limit: Max credits allowed per month.
        """
        self._api_key = api_key or os.environ.get("ODDS_API_KEY", "")
        self._monthly_credit_limit = monthly_credit_limit
        self._credits_remaining: int | None = None
        self._credits_used: int | None = None

    @property
    def provider_name(self) -> str:
        """Return the human-readable provider name."""
        return "the_odds_api"

    @property
    def is_available(self) -> bool:
        """Check if the provider is currently usable."""
        return bool(self._api_key) and REQUESTS_AVAILABLE

    @property
    def cost_per_request(self) -> float:
        """Return cost per API request (free tier)."""
        return 0.0  # Free tier

    @property
    def credits_remaining(self) -> int | None:
        """Return the number of API credits remaining this month."""
        return self._credits_remaining

    @property
    def credits_used(self) -> int | None:
        """Return the number of API credits used this month."""
        return self._credits_used

    def _request(
        self,
        sport_key: str,
        markets: str = "spreads",
        regions: str = "us",
        bookmakers: str | None = None,
    ) -> tuple[list[dict], dict]:
        """Make an API request and track credits.

        Returns:
            Tuple of (response data, credit info dict).
        """
        if not self.is_available:
            return [], {}

        params: dict[str, Any] = {
            "apiKey": self._api_key,
            "regions": regions,
            "markets": markets,
            "oddsFormat": "american",
        }
        if bookmakers:
            params["bookmakers"] = bookmakers

        url = f"{self.BASE_URL}/{sport_key}/odds"
        response = requests.get(url, params=params, timeout=30)

        # Track credits from headers
        credit_info = {}
        if "x-requests-remaining" in response.headers:
            self._credits_remaining = int(response.headers["x-requests-remaining"])
            credit_info["remaining"] = self._credits_remaining
        if "x-requests-used" in response.headers:
            self._credits_used = int(response.headers["x-requests-used"])
            credit_info["used"] = self._credits_used

        response.raise_for_status()
        return response.json(), credit_info

    def _parse_event(
        self,
        event: dict,
        target_home: str | None = None,
        target_away: str | None = None,
    ) -> list[ClosingOdds]:
        """Parse a single event from API response into ClosingOdds.

        Returns one ClosingOdds per bookmaker.
        """
        results = []
        game_id = event.get("id", "")
        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")

        # If filtering for specific teams, do fuzzy match
        if target_home and target_away:
            if not (_fuzzy_match(home_team, target_home) and _fuzzy_match(away_team, target_away)):
                return []

        for bookmaker in event.get("bookmakers", []):
            book_key = bookmaker.get("key", "")
            odds = ClosingOdds(
                game_id=game_id,
                sportsbook=book_key,
                captured_at=datetime.now(timezone.utc),
                is_closing=False,
                confidence=0.95,
            )

            for market in bookmaker.get("markets", []):
                mkey = market.get("key", "")
                outcomes = {o["name"]: o for o in market.get("outcomes", [])}

                if mkey == "spreads":
                    home_oc = outcomes.get(home_team, {})
                    away_oc = outcomes.get(away_team, {})
                    odds.spread_home = home_oc.get("point")
                    odds.spread_home_odds = _safe_int(home_oc.get("price"))
                    odds.spread_away_odds = _safe_int(away_oc.get("price"))

                elif mkey == "h2h":
                    home_oc = outcomes.get(home_team, {})
                    away_oc = outcomes.get(away_team, {})
                    odds.moneyline_home = _safe_int(home_oc.get("price"))
                    odds.moneyline_away = _safe_int(away_oc.get("price"))

                elif mkey == "totals":
                    over_oc = outcomes.get("Over", {})
                    under_oc = outcomes.get("Under", {})
                    odds.total = over_oc.get("point")
                    odds.over_odds = _safe_int(over_oc.get("price"))
                    odds.under_odds = _safe_int(under_oc.get("price"))

            results.append(odds)

        return results

    def fetch_game_odds(
        self,
        sport: str,
        home: str,
        away: str,
        game_id: str,
    ) -> Optional[ClosingOdds]:
        """Fetch odds for a single game from The Odds API."""
        sport_key = ODDS_API_SPORT_KEYS.get(sport.lower(), sport)

        try:
            events, _ = self._request(sport_key, markets="spreads,h2h")
        except Exception as e:
            logger.error("Odds API request failed: %s", e)
            return None

        for event in events:
            matches = self._parse_event(event, target_home=home, target_away=away)
            if matches:
                # Return DraftKings odds if available, else first match
                for m in matches:
                    if m.sportsbook == "draftkings":
                        return m
                return matches[0]

        return None

    def fetch_slate_odds(self, sport: str, date: str) -> list[ClosingOdds]:
        """Fetch odds for all games on a given date from The Odds API."""
        sport_key = ODDS_API_SPORT_KEYS.get(sport.lower(), sport)

        try:
            events, credit_info = self._request(sport_key, markets="spreads")
        except Exception as e:
            logger.error("Odds API slate request failed: %s", e)
            return []

        results = []
        for event in events:
            results.extend(self._parse_event(event))

        logger.info(
            "Odds API: %d odds from %d events (credits remaining: %s)",
            len(results),
            len(events),
            credit_info.get("remaining", "?"),
        )
        return results

    def get_credit_budget(self) -> dict:
        """Get current credit usage status."""
        return {
            "remaining": self._credits_remaining,
            "used": self._credits_used,
            "limit": self._monthly_credit_limit,
            "pct_used": (
                self._credits_used / self._monthly_credit_limit
                if self._credits_used is not None
                else None
            ),
        }


# =============================================================================
# ESPN ODDS PROVIDER
# =============================================================================

ESPN_SPORT_PATHS = {
    "ncaab": "basketball/mens-college-basketball",
    "nba": "basketball/nba",
    "nfl": "football/nfl",
    "ncaaf": "football/college-football",
    "mlb": "baseball/mlb",
}

ESPN_PROVIDER_IDS = {
    "draftkings": 41,
    "caesars": 38,
    "bet365": 2000,
    "fanduel": 58,
    "betmgm": 45,
}


class ESPNOddsProvider(OddsProvider):
    """Retrieves odds from ESPN's unofficial API endpoints.

    Free, no API key needed. Endpoints are undocumented and may change.
    Rate limited conservatively at 2 req/sec.
    """

    SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/{sport_path}/scoreboard"

    def __init__(self, rate_limit_rps: float = 2.0):
        """Initialize the ESPN odds provider.

        Args:
            rate_limit_rps: Rate limit in requests per second.
        """
        self._rate_limit_delay = 1.0 / rate_limit_rps
        self._last_request_time = 0.0

    @property
    def provider_name(self) -> str:
        """Return the human-readable provider name."""
        return "espn"

    @property
    def is_available(self) -> bool:
        """Check if the provider is currently usable."""
        return REQUESTS_AVAILABLE

    @property
    def cost_per_request(self) -> float:
        """Return cost per API request (free for ESPN)."""
        return 0.0

    def _rate_limited_get(self, url: str, params: dict | None = None) -> dict:
        """Make a rate-limited GET request to ESPN."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)

        response = requests.get(url, params=params or {}, timeout=30)
        self._last_request_time = time.time()
        response.raise_for_status()
        return response.json()

    def _parse_espn_event(self, event: dict) -> list[ClosingOdds]:
        """Parse an ESPN event into ClosingOdds."""
        results = []
        event_id = event.get("id", "")
        competition = (event.get("competitions") or [{}])[0]

        # Get team names
        competitors = competition.get("competitors", [])
        for comp in competitors:
            if comp.get("homeAway") == "home":
                comp.get("team", {}).get("displayName", "")
            elif comp.get("homeAway") == "away":
                comp.get("team", {}).get("displayName", "")

        # Parse odds from competition
        odds_list = competition.get("odds", [])
        for odds_entry in odds_list:
            provider_name = odds_entry.get("provider", {}).get("name", "unknown")
            book_key = provider_name.lower().replace(" ", "")

            odds = ClosingOdds(
                game_id=event_id,
                sportsbook=book_key,
                captured_at=datetime.now(timezone.utc),
                is_closing=False,
                confidence=0.80,
            )

            # Spread
            spread_val = odds_entry.get("spread")
            if spread_val is not None:
                odds.spread_home = _safe_float(spread_val)
                odds.spread_home_odds = _safe_int(odds_entry.get("spreadOdds"))

            # Total
            total_val = odds_entry.get("overUnder")
            if total_val is not None:
                odds.total = _safe_float(total_val)
                odds.over_odds = _safe_int(odds_entry.get("overOdds"))
                odds.under_odds = _safe_int(odds_entry.get("underOdds"))

            # Moneyline
            home_ml = odds_entry.get("homeTeamOdds", {}).get("moneyLine")
            away_ml = odds_entry.get("awayTeamOdds", {}).get("moneyLine")
            if home_ml is not None:
                odds.moneyline_home = _safe_int(home_ml)
            if away_ml is not None:
                odds.moneyline_away = _safe_int(away_ml)

            results.append(odds)

        return results

    def fetch_game_odds(
        self,
        sport: str,
        home: str,
        away: str,
        game_id: str,
    ) -> Optional[ClosingOdds]:
        """Fetch odds for a single game from ESPN API."""
        sport_path = ESPN_SPORT_PATHS.get(sport.lower())
        if not sport_path:
            logger.warning("ESPN: unsupported sport '%s'", sport)
            return None

        url = self.SCOREBOARD_URL.format(sport_path=sport_path)

        try:
            data = self._rate_limited_get(url)
        except Exception as e:
            logger.error("ESPN scoreboard request failed: %s", e)
            return None

        for event in data.get("events", []):
            odds_list = self._parse_espn_event(event)
            if not odds_list:
                continue

            # Check if this event matches our game
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors", [])
            event_teams = [c.get("team", {}).get("displayName", "") for c in competitors]

            if _fuzzy_match_any(home, event_teams) and _fuzzy_match_any(away, event_teams):
                # Return DraftKings if available
                for o in odds_list:
                    if "draftkings" in o.sportsbook.lower():
                        return o
                return odds_list[0]

        return None

    def fetch_slate_odds(self, sport: str, date: str) -> list[ClosingOdds]:
        """Fetch odds for all games on a given date from ESPN API."""
        sport_path = ESPN_SPORT_PATHS.get(sport.lower())
        if not sport_path:
            return []

        url = self.SCOREBOARD_URL.format(sport_path=sport_path)
        params = {"dates": date.replace("-", "")}

        try:
            data = self._rate_limited_get(url, params)
        except Exception as e:
            logger.error("ESPN slate request failed: %s", e)
            return []

        results = []
        for event in data.get("events", []):
            results.extend(self._parse_espn_event(event))

        logger.info("ESPN: %d odds from %d events", len(results), len(data.get("events", [])))
        return results


# =============================================================================
# SCRAPER PROVIDER (wraps existing Selenium infrastructure)
# =============================================================================


class ScraperOddsProvider(OddsProvider):
    """Wraps existing Selenium-based sportsbook scrapers.

    Delegates to ClosingOddsCollector from closing_odds_collector.py.
    Requires Chrome + Selenium (optional dependency).
    """

    def __init__(self, db_path: str = "data/betting.db", headless: bool = True):
        """Initialize the Selenium scraper provider.

        Args:
            db_path: Path to database for storing scraped odds.
            headless: Whether to run browser in headless mode.
        """
        self._db_path = db_path
        self._headless = headless
        self._collector = None

    @property
    def provider_name(self) -> str:
        """Return the human-readable provider name."""
        return "selenium_scraper"

    @property
    def is_available(self) -> bool:
        """Check if the provider is currently usable."""
        try:
            from pipelines.closing_odds_collector import SELENIUM_AVAILABLE

            return SELENIUM_AVAILABLE
        except ImportError:
            return False

    @property
    def cost_per_request(self) -> float:
        """Return cost per API request (free for scraper)."""
        return 0.0

    def _get_collector(self):
        """Lazy-initialize the closing odds collector."""
        if self._collector is None:
            from pipelines.closing_odds_collector import ClosingOddsCollector

            self._collector = ClosingOddsCollector(
                db_path=self._db_path,
                headless=self._headless,
            )
        return self._collector

    def fetch_game_odds(
        self,
        sport: str,
        home: str,
        away: str,
        game_id: str,
    ) -> Optional[ClosingOdds]:
        """Fetch odds for a single game using Selenium scraper."""
        if not self.is_available:
            logger.warning("Selenium not available for scraper provider")
            return None

        try:
            collector = self._get_collector()
            return collector.collect_game_closing_odds(
                game_id=game_id,
                sport=sport.upper(),
                home_team=home,
                away_team=away,
            )
        except Exception as e:
            logger.error("Scraper failed for %s: %s", game_id, e)
            return None

    def fetch_slate_odds(self, sport: str, date: str) -> list[ClosingOdds]:
        """Fetch odds for all games (not supported by scraper)."""
        # Scraper doesn't efficiently support slate fetching
        logger.info("Scraper provider does not support full slate fetching")
        return []


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _safe_float(value: Any) -> Optional[float]:
    """Convert value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    """Convert value to int, returning None on failure."""
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _normalize_team_name(name: str) -> str:
    """Normalize team name for fuzzy matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower().strip())


def _fuzzy_match(name_a: str, name_b: str) -> bool:
    """Check if two team names are a fuzzy match."""
    a = _normalize_team_name(name_a)
    b = _normalize_team_name(name_b)
    return a == b or a in b or b in a


def _fuzzy_match_any(name: str, candidates: list[str]) -> bool:
    """Check if name fuzzy-matches any candidate."""
    return any(_fuzzy_match(name, c) for c in candidates)
