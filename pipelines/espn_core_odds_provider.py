"""ESPN Core API Odds Provider.

Retrieves historical and live odds from ESPN's undocumented Core API
(sports.core.api.espn.com). Provides open/close/current odds with
American, decimal, and fraction formats.

Key features:
    - Free, no API key required
    - Historical odds for completed games (open + close)
    - Multi-format odds (American, decimal, fraction)
    - Rate-limited requests with exponential backoff

Provider coverage (as of Feb 2026):
    - 2025 season: ESPN BET (58), ESPN BET Live (59)
    - 2026 season: DraftKings (100) after ESPN BET transition

WARNING: Undocumented API — may change without notice.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from pipelines.closing_odds_collector import ClosingOdds
from pipelines.odds_providers import OddsProvider

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ESPN_CORE_BASE = "https://sports.core.api.espn.com/v2/sports"

ESPN_CORE_SPORT_PATHS: dict[str, str] = {
    "ncaab": "basketball/leagues/mens-college-basketball",
    "nba": "basketball/leagues/nba",
    "nfl": "football/leagues/nfl",
    "ncaaf": "football/leagues/college-football",
    "mlb": "baseball/leagues/mlb",
}

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports"

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OddsSnapshot:
    """Rich odds record with open/close/current from ESPN Core API.

    All American odds stored as int (e.g. -110, +150).
    Point spreads and totals stored as float (e.g. -6.5, 152.5).
    Fields are None when the API omits them.
    """

    game_id: str
    provider_id: int
    provider_name: str

    # Current top-level odds
    spread: Optional[float] = None
    over_under: Optional[float] = None
    home_moneyline: Optional[int] = None
    away_moneyline: Optional[int] = None
    home_spread_odds: Optional[int] = None
    away_spread_odds: Optional[int] = None
    over_odds: Optional[int] = None
    under_odds: Optional[int] = None

    # Opening odds
    home_spread_open: Optional[float] = None
    away_spread_open: Optional[float] = None
    home_spread_odds_open: Optional[int] = None
    away_spread_odds_open: Optional[int] = None
    home_ml_open: Optional[int] = None
    away_ml_open: Optional[int] = None
    total_open: Optional[float] = None
    over_odds_open: Optional[int] = None
    under_odds_open: Optional[int] = None

    # Closing odds (only for completed games)
    home_spread_close: Optional[float] = None
    away_spread_close: Optional[float] = None
    home_spread_odds_close: Optional[int] = None
    away_spread_odds_close: Optional[int] = None
    home_ml_close: Optional[int] = None
    away_ml_close: Optional[int] = None
    total_close: Optional[float] = None
    over_odds_close: Optional[int] = None
    under_odds_close: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for parquet/DB storage."""
        return asdict(self)

    def to_closing_odds(self, use_close: bool = True) -> ClosingOdds:
        """Convert to ClosingOdds for orchestrator compatibility.

        Args:
            use_close: If True, use closing odds; otherwise use current.

        Returns:
            ClosingOdds populated with the best available data.
        """
        if use_close and self.home_ml_close is not None:
            ml_home = self.home_ml_close
            ml_away = self.away_ml_close
            sp_odds_home = self.home_spread_odds_close
            sp_odds_away = self.away_spread_odds_close
            sp = self.home_spread_close
            tot = self.total_close
            ov = self.over_odds_close
            un = self.under_odds_close
            is_closing = True
        else:
            ml_home = self.home_moneyline
            ml_away = self.away_moneyline
            sp_odds_home = self.home_spread_odds
            sp_odds_away = self.away_spread_odds
            sp = self.spread
            tot = self.over_under
            ov = self.over_odds
            un = self.under_odds
            is_closing = False

        return ClosingOdds(
            game_id=self.game_id,
            sportsbook=self.provider_name.lower().replace(" ", "_"),
            captured_at=datetime.now(timezone.utc),
            spread_home=sp,
            spread_home_odds=sp_odds_home,
            spread_away_odds=sp_odds_away,
            total=tot,
            over_odds=ov,
            under_odds=un,
            moneyline_home=ml_home,
            moneyline_away=ml_away,
            is_closing=is_closing,
            confidence=0.92,
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_american(value: Any) -> Optional[int]:
    """Parse American odds from ESPN response.

    ESPN returns American odds as strings like "-110", "+150", or
    as floats like -110.0. Point spreads like "-1.5" are NOT odds.

    Args:
        value: Raw value from API (str, int, float, or dict).

    Returns:
        Integer American odds, or None if not parseable.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("american", value.get("alternateDisplayValue"))
    if value is None:
        return None
    try:
        f = float(value)
        # Point spreads are typically -20 to +20, odds are >=100 or <=-100
        if -99 < f < 100 and f != 0:
            return None  # This is a point spread, not odds
        return int(f)
    except (ValueError, TypeError):
        return None


def _parse_spread(value: Any) -> Optional[float]:
    """Parse point spread value from ESPN response.

    Args:
        value: Raw value — string like "-1.5" or float.

    Returns:
        Float spread value, or None.
    """
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("american", value.get("alternateDisplayValue"))
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_american_from_odds_obj(odds_obj: Optional[dict]) -> Optional[int]:
    """Extract American odds int from an ESPN odds object.

    ESPN odds objects look like:
        {"value": 1.8, "displayValue": "4/5",
         "alternateDisplayValue": "-125", "american": "-125", ...}

    Args:
        odds_obj: ESPN odds dict with american/alternateDisplayValue keys.

    Returns:
        Integer American odds, or None.
    """
    if not odds_obj or not isinstance(odds_obj, dict):
        return None
    raw = odds_obj.get("american") or odds_obj.get("alternateDisplayValue")
    if raw is None:
        return None
    try:
        f = float(raw)
        return int(f)
    except (ValueError, TypeError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    """Convert value to int safely."""
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    """Convert value to float safely."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def parse_odds_response(data: dict, game_id: str) -> Optional[OddsSnapshot]:
    """Parse a single ESPN Core API odds response into OddsSnapshot.

    Args:
        data: Full JSON response from following a provider $ref URL.
        game_id: ESPN event ID.

    Returns:
        OddsSnapshot with all available fields, or None on parse failure.
    """
    provider = data.get("provider", {})
    provider_id = _safe_int(provider.get("id"))
    provider_name = provider.get("name", "unknown")

    if provider_id is None:
        return None

    home = data.get("homeTeamOdds", {})
    away = data.get("awayTeamOdds", {})
    home_open = home.get("open", {}) or {}
    home_close = home.get("close", {}) or {}
    away_open = away.get("open", {}) or {}
    away_close = away.get("close", {}) or {}

    # Top-level totals open/close
    totals_open = data.get("open", {}) or {}
    totals_close = data.get("close", {}) or {}

    return OddsSnapshot(
        game_id=game_id,
        provider_id=provider_id,
        provider_name=provider_name,
        # Current / top-level
        spread=_safe_float(data.get("spread")),
        over_under=_safe_float(data.get("overUnder")),
        home_moneyline=_safe_int(home.get("moneyLine")),
        away_moneyline=_safe_int(away.get("moneyLine")),
        home_spread_odds=_safe_int(home.get("spreadOdds")),
        away_spread_odds=_safe_int(away.get("spreadOdds")),
        over_odds=_safe_int(data.get("overOdds")),
        under_odds=_safe_int(data.get("underOdds")),
        # Opening — spreads
        home_spread_open=_parse_spread(
            home_open.get("pointSpread", {}).get("american")
            if home_open.get("pointSpread")
            else None
        ),
        away_spread_open=_parse_spread(
            away_open.get("pointSpread", {}).get("american")
            if away_open.get("pointSpread")
            else None
        ),
        home_spread_odds_open=_parse_american_from_odds_obj(home_open.get("spread")),
        away_spread_odds_open=_parse_american_from_odds_obj(away_open.get("spread")),
        # Opening — moneylines
        home_ml_open=_parse_american_from_odds_obj(home_open.get("moneyLine")),
        away_ml_open=_parse_american_from_odds_obj(away_open.get("moneyLine")),
        # Opening — totals
        total_open=_parse_spread(
            totals_open.get("total", {}).get("american") if totals_open.get("total") else None
        ),
        over_odds_open=_parse_american_from_odds_obj(totals_open.get("over")),
        under_odds_open=_parse_american_from_odds_obj(totals_open.get("under")),
        # Closing — spreads
        home_spread_close=_parse_spread(
            home_close.get("pointSpread", {}).get("american")
            if home_close.get("pointSpread")
            else None
        ),
        away_spread_close=_parse_spread(
            away_close.get("pointSpread", {}).get("american")
            if away_close.get("pointSpread")
            else None
        ),
        home_spread_odds_close=_parse_american_from_odds_obj(home_close.get("spread")),
        away_spread_odds_close=_parse_american_from_odds_obj(away_close.get("spread")),
        # Closing — moneylines
        home_ml_close=_parse_american_from_odds_obj(home_close.get("moneyLine")),
        away_ml_close=_parse_american_from_odds_obj(away_close.get("moneyLine")),
        # Closing — totals
        total_close=_parse_spread(
            totals_close.get("total", {}).get("american") if totals_close.get("total") else None
        ),
        over_odds_close=_parse_american_from_odds_obj(totals_close.get("over")),
        under_odds_close=_parse_american_from_odds_obj(totals_close.get("under")),
    )


# ---------------------------------------------------------------------------
# HTTP client with rate limiting + retry
# ---------------------------------------------------------------------------


class ESPNCoreClient:
    """Low-level HTTP client for ESPN Core API with rate limiting.

    Args:
        requests_per_second: Maximum request rate.
        timeout: HTTP timeout in seconds.
    """

    def __init__(
        self,
        requests_per_second: float = 2.0,
        timeout: float = 20.0,
    ) -> None:
        """Initialize HTTP client with rate limiting and session.

        Args:
            requests_per_second: Maximum request rate.
            timeout: HTTP timeout in seconds.
        """
        self._delay = 1.0 / requests_per_second
        self._timeout = timeout
        self._last_request_time = 0.0
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (sports-betting-research)",
            }
        )

    def get(self, url: str) -> dict:
        """Rate-limited GET with retry and exponential backoff.

        Args:
            url: Full URL to fetch.

        Returns:
            Parsed JSON response.

        Raises:
            requests.RequestException: After all retries fail.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(MAX_RETRIES):
            # Rate limit
            elapsed = time.time() - self._last_request_time
            if elapsed < self._delay:
                time.sleep(self._delay - elapsed)

            try:
                resp = self._session.get(url, timeout=self._timeout)
                self._last_request_time = time.time()

                if resp.status_code == 429:
                    wait = RETRY_BASE_DELAY * (2**attempt) * 5
                    logger.warning(
                        "ESPN Core API rate limited — backing off %.1fs",
                        wait,
                    )
                    time.sleep(wait)
                    continue

                resp.raise_for_status()
                return resp.json()

            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                if attempt < MAX_RETRIES - 1:
                    wait = RETRY_BASE_DELAY * (2**attempt)
                    logger.warning(
                        "ESPN Core API request failed (attempt %d/%d): %s",
                        attempt + 1,
                        MAX_RETRIES,
                        exc,
                    )
                    time.sleep(wait)

        raise requests.RequestException(
            f"All {MAX_RETRIES} attempts failed for {url}"
        ) from last_exc

    def close(self) -> None:
        """Close the underlying session."""
        self._session.close()


# ---------------------------------------------------------------------------
# High-level fetcher
# ---------------------------------------------------------------------------


class ESPNCoreOddsFetcher:
    """Fetches odds from ESPN Core API for single games or bulk backfill.

    Supports:
        - Single game odds (all providers)
        - Bulk backfill from list of event IDs
        - Rich open/close/current data via OddsSnapshot
    """

    def __init__(
        self,
        sport: str = "ncaab",
        requests_per_second: float = 2.0,
    ) -> None:
        """Initialize fetcher for a specific sport.

        Args:
            sport: Sport code (e.g. 'ncaab', 'nba').
            requests_per_second: API rate limit.
        """
        sport_path = ESPN_CORE_SPORT_PATHS.get(sport.lower())
        if not sport_path:
            raise ValueError(f"Unsupported sport '{sport}'. Valid: {list(ESPN_CORE_SPORT_PATHS)}")
        self._sport = sport.lower()
        self._sport_path = sport_path
        self._base = f"{ESPN_CORE_BASE}/{sport_path}"
        self._client = ESPNCoreClient(
            requests_per_second=requests_per_second,
        )

    def fetch_game_odds(self, event_id: str) -> list[OddsSnapshot]:
        """Fetch odds from all available providers for a single game.

        Args:
            event_id: ESPN event ID.

        Returns:
            List of OddsSnapshot (one per provider). Empty if no odds.
        """
        odds_url = f"{self._base}/events/{event_id}/competitions/{event_id}/odds"

        try:
            data = self._client.get(odds_url)
        except requests.RequestException as exc:
            logger.warning(
                "Failed to fetch odds list for event %s: %s",
                event_id,
                exc,
            )
            return []

        items = data.get("items", [])
        if not items:
            return []

        snapshots: list[OddsSnapshot] = []
        for item in items:
            ref_url = item.get("$ref")
            if ref_url:
                try:
                    odds_data = self._client.get(ref_url)
                except requests.RequestException as exc:
                    logger.warning(
                        "Failed to follow $ref for event %s: %s",
                        event_id,
                        exc,
                    )
                    continue
            else:
                # Some sports (e.g. MLB) return inline odds data without $ref
                odds_data = item

            snapshot = parse_odds_response(odds_data, event_id)
            if snapshot is not None:
                snapshots.append(snapshot)

        return snapshots

    def fetch_game_odds_direct(
        self,
        event_id: str,
        provider_id: int,
    ) -> Optional[OddsSnapshot]:
        """Fetch odds from a specific provider by ID.

        Args:
            event_id: ESPN event ID.
            provider_id: ESPN provider ID (e.g. 58, 100).

        Returns:
            OddsSnapshot or None if not available.
        """
        url = f"{self._base}/events/{event_id}/competitions/{event_id}/odds/{provider_id}"

        try:
            data = self._client.get(url)
        except requests.RequestException:
            return None

        return parse_odds_response(data, event_id)

    def fetch_batch(
        self,
        event_ids: list[str],
        progress_callback: Optional[Any] = None,
    ) -> dict[str, list[OddsSnapshot]]:
        """Fetch odds for multiple events.

        Args:
            event_ids: List of ESPN event IDs.
            progress_callback: Optional callable(current, total, game_id).

        Returns:
            Dict mapping event_id to list of OddsSnapshot.
        """
        results: dict[str, list[OddsSnapshot]] = {}
        total = len(event_ids)

        for idx, eid in enumerate(event_ids):
            snapshots = self.fetch_game_odds(eid)
            if snapshots:
                results[eid] = snapshots

            if progress_callback:
                progress_callback(idx + 1, total, eid)
            elif (idx + 1) % 100 == 0 or idx + 1 == total:
                n_with_odds = len(results)
                logger.info(
                    "Progress: %d/%d events fetched (%d with odds)",
                    idx + 1,
                    total,
                    n_with_odds,
                )

        return results

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()


# ---------------------------------------------------------------------------
# OddsProvider implementation (for OddsOrchestrator integration)
# ---------------------------------------------------------------------------


class ESPNCoreOddsProvider(OddsProvider):
    """ESPN Core API odds provider for OddsOrchestrator.

    Implements the OddsProvider interface using ESPN Core API.
    Returns closing odds when available (completed games) or
    current odds (upcoming/live games).
    """

    def __init__(
        self,
        sport: str = "ncaab",
        requests_per_second: float = 2.0,
    ) -> None:
        """Initialize the ESPN Core API odds provider.

        Args:
            sport: Sport code (e.g. 'ncaab').
            requests_per_second: API rate limit.
        """
        self._fetcher = ESPNCoreOddsFetcher(
            sport=sport,
            requests_per_second=requests_per_second,
        )

    @property
    def provider_name(self) -> str:
        """Return the human-readable provider name."""
        return "espn_core_api"

    @property
    def is_available(self) -> bool:
        """Check if the provider is currently usable."""
        return True

    @property
    def cost_per_request(self) -> float:
        """Return cost per API request (free)."""
        return 0.0

    def fetch_game_odds(
        self,
        sport: str,
        home: str,
        away: str,
        game_id: str,
    ) -> Optional[ClosingOdds]:
        """Fetch odds for a single game, returning best available.

        Prefers closing odds from the highest-priority provider.
        Falls back to current odds if close not available.

        Args:
            sport: Sport code (ignored — set at init).
            home: Home team (not needed — Core API uses event IDs).
            away: Away team (not needed).
            game_id: ESPN event ID.

        Returns:
            ClosingOdds or None.
        """
        snapshots = self._fetcher.fetch_game_odds(game_id)
        if not snapshots:
            return None

        # Filter out live-odds providers (ID 59) — prefer pre-game
        pre_game = [s for s in snapshots if s.provider_id != 59]
        if not pre_game:
            pre_game = snapshots

        # Return first (highest priority) as ClosingOdds
        return pre_game[0].to_closing_odds(use_close=True)

    def fetch_slate_odds(
        self,
        sport: str,
        date: str,
    ) -> list[ClosingOdds]:
        """Fetch odds for all games on a date.

        Uses ESPN Site API scoreboard to discover event IDs,
        then Core API for odds.

        Args:
            sport: Sport code.
            date: Date in YYYY-MM-DD format.

        Returns:
            List of ClosingOdds for games with odds.
        """
        sport_path = ESPN_CORE_SPORT_PATHS.get(sport.lower())
        if not sport_path:
            logger.warning("Unsupported sport: %s", sport)
            return []

        # Get event IDs from Site API scoreboard
        date_compact = date.replace("-", "")
        scoreboard_url = f"{ESPN_SITE_BASE}/{sport_path}/scoreboard?dates={date_compact}&limit=500"

        try:
            client = ESPNCoreClient(requests_per_second=2.0)
            sb_data = client.get(scoreboard_url)
        except requests.RequestException as exc:
            logger.error("Scoreboard fetch failed for %s: %s", date, exc)
            return []

        event_ids = [str(ev.get("id", "")) for ev in sb_data.get("events", []) if ev.get("id")]

        if not event_ids:
            logger.info("No events found for %s on %s", sport, date)
            return []

        # Fetch odds for each event
        results: list[ClosingOdds] = []
        for eid in event_ids:
            snapshots = self._fetcher.fetch_game_odds(eid)
            if snapshots:
                pre_game = [s for s in snapshots if s.provider_id != 59]
                if not pre_game:
                    pre_game = snapshots
                results.append(pre_game[0].to_closing_odds(use_close=True))

        logger.info(
            "ESPN Core API: %d/%d events with odds for %s",
            len(results),
            len(event_ids),
            date,
        )
        return results
