"""Odds Orchestrator — Provider Chain Management.

Manages odds retrieval across multiple providers with automatic fallback,
response caching, credit budget tracking, and database persistence.

Fallback chain (auto mode):
    TheOddsAPI -> ESPN -> Selenium Scraper -> Cached Data -> None

Usage:
    from pipelines.odds_orchestrator import OddsOrchestrator
    from config.constants import ODDS_CONFIG

    orchestrator = OddsOrchestrator(db=db, config=ODDS_CONFIG)
    orchestrator.register_default_providers()

    odds = orchestrator.fetch_odds('ncaab', 'Duke', 'UNC', 'game123')
    slate = orchestrator.fetch_slate('ncaab', '2026-02-15')
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pipelines.closing_odds_collector import ClosingOdds
from pipelines.espn_core_odds_provider import ESPNCoreOddsProvider
from pipelines.odds_providers import (
    ESPNOddsProvider,
    ManualOddsProvider,
    OddsProvider,
    ScraperOddsProvider,
    TheOddsAPIProvider,
)

logger = logging.getLogger(__name__)


# =============================================================================
# RESPONSE CACHE
# =============================================================================


@dataclass
class CacheEntry:
    """A cached odds response with TTL."""

    data: ClosingOdds
    timestamp: float
    ttl: int = 300  # 5 minutes

    def __init__(self, data: ClosingOdds, timestamp: float, ttl: int = 300):
        """Initialize cache entry with odds data and TTL."""
        self.data = data
        self.timestamp = timestamp
        self.ttl = ttl

    @property
    def is_expired(self) -> bool:
        """Check if cache entry has exceeded its TTL."""
        return (time.time() - self.timestamp) > self.ttl

    @property
    def age_seconds(self) -> float:
        """Return age of cache entry in seconds."""
        return time.time() - self.timestamp


class OddsCache:
    """TTL-based cache for odds responses."""

    def __init__(self, ttl: int = 300):
        """Initialize cache with configurable TTL."""
        self._ttl = ttl
        self._store: dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[ClosingOdds]:
        """Retrieve cached odds by key, returning None if expired or missing."""
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if entry.is_expired:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry.data

    def put(self, key: str, odds: ClosingOdds) -> None:
        """Store odds in cache with current timestamp."""
        self._store[key] = CacheEntry(data=odds, timestamp=time.time(), ttl=self._ttl)

    def clear_expired(self) -> int:
        """Remove all expired entries and return count of cleared items."""
        expired = [k for k, v in self._store.items() if v.is_expired]
        for k in expired:
            del self._store[k]
        return len(expired)

    @property
    def stats(self) -> dict:
        """Return cache performance statistics including hit rate."""
        total = self._hits + self._misses
        return {
            "size": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0.0,
        }


# =============================================================================
# CREDIT BUDGET TRACKER
# =============================================================================


class CreditBudget:
    """Tracks The Odds API credit usage and enforces budget limits."""

    def __init__(
        self,
        monthly_limit: int = 500,
        warning_pct: float = 0.80,
        cutoff_pct: float = 0.90,
        usage_file: str = "data/odds_api_usage.json",
    ):
        """Initialize credit budget tracker with monthly limits and thresholds."""
        self.monthly_limit = monthly_limit
        self.warning_pct = warning_pct
        self.cutoff_pct = cutoff_pct
        self._usage_file = Path(usage_file)
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if self._usage_file.exists():
            with open(self._usage_file, encoding="utf-8") as f:
                return json.load(f)
        return {
            "month": datetime.now(timezone.utc).strftime("%Y-%m"),
            "credits_used": 0,
            "last_known_remaining": None,
        }

    def _save_state(self) -> None:
        self._usage_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._usage_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f, indent=2)

    def _check_month_reset(self) -> None:
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        if self._state["month"] != current_month:
            self._state = {
                "month": current_month,
                "credits_used": 0,
                "last_known_remaining": None,
            }
            self._save_state()

    def record_usage(self, credits_used: int | None, credits_remaining: int | None) -> None:
        """Update budget after an API call."""
        self._check_month_reset()
        if credits_used is not None:
            self._state["credits_used"] = credits_used
        if credits_remaining is not None:
            self._state["last_known_remaining"] = credits_remaining
        self._save_state()

    @property
    def can_use_api(self) -> bool:
        """Whether we're within budget to make API calls."""
        self._check_month_reset()
        used = self._state["credits_used"]
        return used < (self.monthly_limit * self.cutoff_pct)

    @property
    def is_warning(self) -> bool:
        """Whether we've exceeded the warning threshold."""
        self._check_month_reset()
        used = self._state["credits_used"]
        return used >= (self.monthly_limit * self.warning_pct)

    @property
    def status(self) -> dict:
        """Return current credit budget status and usage statistics."""
        self._check_month_reset()
        used = self._state["credits_used"]
        return {
            "month": self._state["month"],
            "credits_used": used,
            "credits_remaining": self._state["last_known_remaining"],
            "monthly_limit": self.monthly_limit,
            "pct_used": used / self.monthly_limit if self.monthly_limit > 0 else 0,
            "can_use_api": self.can_use_api,
            "is_warning": self.is_warning,
        }


# =============================================================================
# ODDS ORCHESTRATOR
# =============================================================================


# Valid modes for odds retrieval
VALID_MODES = {"auto", "manual", "api", "espn_core", "espn", "scraper", "agent"}


class OddsOrchestrator:
    """Manages odds retrieval across multiple providers with fallback.

    Attributes:
        providers: Ordered list of (name, provider) tuples.
        cache: TTL-based response cache.
        credit_budget: Tracks API credit usage.
    """

    def __init__(
        self,
        db: Any = None,
        cache_ttl: int = 300,
        monthly_credit_limit: int = 500,
        credit_warning_pct: float = 0.80,
        credit_cutoff_pct: float = 0.90,
        usage_file: str = "data/odds_api_usage.json",
    ):
        """Initialize orchestrator with cache, credit tracking, and provider registry."""
        self._db = db
        self._providers: list[tuple[str, OddsProvider]] = []
        self.cache = OddsCache(ttl=cache_ttl)
        self.credit_budget = CreditBudget(
            monthly_limit=monthly_credit_limit,
            warning_pct=credit_warning_pct,
            cutoff_pct=credit_cutoff_pct,
            usage_file=usage_file,
        )
        self._fetch_log: list[dict] = []

    def add_provider(self, provider: OddsProvider) -> None:
        """Add a provider to the chain (order matters for fallback)."""
        self._providers.append((provider.provider_name, provider))
        logger.info("Registered odds provider: %s", provider.provider_name)

    def register_default_providers(
        self,
        api_key: str | None = None,
        csv_path: str | None = None,
    ) -> None:
        """Register the standard provider chain.

        Order: TheOddsAPI -> ESPN Core API -> ESPN Site API -> Scraper -> Manual
        """
        self.add_provider(TheOddsAPIProvider(api_key=api_key))
        self.add_provider(ESPNCoreOddsProvider())
        self.add_provider(ESPNOddsProvider())
        self.add_provider(ScraperOddsProvider())
        if csv_path:
            manual = ManualOddsProvider(csv_path)
            manual.load_csv()
            self.add_provider(manual)

    def _get_provider(self, mode: str) -> Optional[OddsProvider]:
        """Get the provider matching a specific mode."""
        mode_to_name = {
            "api": "the_odds_api",
            "espn_core": "espn_core_api",
            "espn": "espn",
            "scraper": "selenium_scraper",
            "manual": "manual_csv",
        }
        target = mode_to_name.get(mode)
        if target:
            for name, provider in self._providers:
                if name == target:
                    return provider
        return None

    def _get_auto_chain(self) -> list[tuple[str, OddsProvider]]:
        """Get the provider chain for auto mode, respecting budget."""
        chain = []
        for name, provider in self._providers:
            # Skip API if over budget
            if name == "the_odds_api" and not self.credit_budget.can_use_api:
                logger.info("Skipping Odds API (over budget)")
                continue
            if provider.is_available:
                chain.append((name, provider))
        return chain

    def fetch_odds(
        self,
        sport: str,
        home: str,
        away: str,
        game_id: str,
        mode: str = "auto",
    ) -> Optional[ClosingOdds]:
        """Fetch odds using specified mode or auto-fallback.

        Args:
            sport: Sport code (e.g., 'ncaab').
            home: Home team name.
            away: Away team name.
            game_id: Unique game identifier.
            mode: Retrieval mode — 'auto', 'manual', 'api', 'espn', 'scraper', 'agent'.

        Returns:
            ClosingOdds if found, None otherwise.
        """
        if mode not in VALID_MODES:
            raise ValueError(f"Invalid mode '{mode}'. Valid: {VALID_MODES}")

        # Check cache first
        cache_key = f"{sport}:{game_id}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            logger.debug("Cache hit for %s", cache_key)
            return cached

        result = None

        if mode == "auto":
            chain = self._get_auto_chain()
            for name, provider in chain:
                try:
                    result = provider.fetch_game_odds(sport, home, away, game_id)
                    if result is not None:
                        logger.info("Odds fetched via %s for %s", name, game_id)
                        self._record_fetch(name, game_id, success=True)
                        self._update_credit_budget(provider)
                        break
                except Exception as e:
                    logger.warning("Provider %s failed: %s", name, e)
                    self._record_fetch(name, game_id, success=False, error=str(e))
        elif mode == "agent":
            # Agent mode is handled externally via /fetch-odds command
            logger.info("Agent mode: use /fetch-odds command for %s vs %s", home, away)
            return None
        else:
            provider = self._get_provider(mode)
            if provider is None:
                logger.error("No provider registered for mode '%s'", mode)
                return None
            if not provider.is_available:
                logger.error("Provider '%s' is not available", mode)
                return None
            try:
                result = provider.fetch_game_odds(sport, home, away, game_id)
                self._update_credit_budget(provider)
            except Exception as e:
                logger.error("Provider %s failed: %s", mode, e)

        # Cache and store successful result
        if result is not None:
            self.cache.put(cache_key, result)
            if self._db is not None:
                self.store_odds(result)

        return result

    def fetch_slate(
        self,
        sport: str,
        date: str,
        mode: str = "auto",
    ) -> list[ClosingOdds]:
        """Fetch odds for all games on a date.

        Args:
            sport: Sport code.
            date: Date in YYYY-MM-DD format.
            mode: Retrieval mode.

        Returns:
            List of ClosingOdds for available games.
        """
        if mode == "auto":
            chain = self._get_auto_chain()
            for name, provider in chain:
                try:
                    results = provider.fetch_slate_odds(sport, date)
                    if results:
                        logger.info(
                            "Slate fetched via %s: %d odds for %s",
                            name,
                            len(results),
                            date,
                        )
                        self._update_credit_budget(provider)
                        # Cache individual games
                        for odds in results:
                            cache_key = f"{sport}:{odds.game_id}"
                            self.cache.put(cache_key, odds)
                        # Store to DB
                        if self._db is not None:
                            for odds in results:
                                self.store_odds(odds)
                        return results
                except Exception as e:
                    logger.warning("Provider %s failed for slate: %s", name, e)
        else:
            provider = self._get_provider(mode)
            if provider and provider.is_available:
                try:
                    results = provider.fetch_slate_odds(sport, date)
                    self._update_credit_budget(provider)
                    return results
                except Exception as e:
                    logger.error("Provider %s failed: %s", mode, e)

        return []

    def store_odds(self, odds: ClosingOdds) -> Optional[int]:
        """Store odds to the odds_snapshots table.

        Args:
            odds: ClosingOdds to persist.

        Returns:
            Row ID if stored, None on failure.
        """
        if self._db is None:
            return None

        try:
            data = odds.to_dict()
            with self._db.get_cursor() as cursor:
                cursor.execute(
                    """INSERT OR REPLACE INTO odds_snapshots
                        (game_id, sportsbook, captured_at,
                         spread_home, spread_home_odds, spread_away_odds,
                         total, over_odds, under_odds,
                         moneyline_home, moneyline_away,
                         is_closing, confidence)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["game_id"],
                        data["sportsbook"],
                        data["captured_at"],
                        data.get("spread_home"),
                        data.get("spread_home_odds"),
                        data.get("spread_away_odds"),
                        data.get("total"),
                        data.get("over_odds"),
                        data.get("under_odds"),
                        data.get("moneyline_home"),
                        data.get("moneyline_away"),
                        data.get("is_closing", False),
                        data.get("confidence", 1.0),
                    ),
                )
                return cursor.lastrowid
        except Exception as e:
            logger.error("Failed to store odds: %s", e)
            return None

    def get_credit_budget(self) -> dict:
        """Get full credit budget status."""
        return self.credit_budget.status

    def get_provider_health(self) -> dict:
        """Get health status for all providers."""
        health = {}
        for name, provider in self._providers:
            health[name] = {
                "available": provider.is_available,
                "cost_per_request": provider.cost_per_request,
            }
        # Add fetch log stats
        if self._fetch_log:
            for name in {entry["provider"] for entry in self._fetch_log}:
                entries = [e for e in self._fetch_log if e["provider"] == name]
                successes = sum(1 for e in entries if e["success"])
                health.setdefault(name, {})
                health[name]["total_requests"] = len(entries)
                health[name]["success_rate"] = successes / len(entries) if entries else 0
        return health

    def _update_credit_budget(self, provider: OddsProvider) -> None:
        """Update credit budget from provider state (if applicable)."""
        if isinstance(provider, TheOddsAPIProvider):
            self.credit_budget.record_usage(provider.credits_used, provider.credits_remaining)

    def _record_fetch(
        self,
        provider: str,
        game_id: str,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Record a fetch attempt for health monitoring."""
        self._fetch_log.append(
            {
                "provider": provider,
                "game_id": game_id,
                "success": success,
                "error": error,
                "timestamp": time.time(),
            }
        )
        # Keep last 1000 entries
        if len(self._fetch_log) > 1000:
            self._fetch_log = self._fetch_log[-500:]
