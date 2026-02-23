"""ESPN Game Context Fetcher for Injury/Divergence Detection.

Fetches ESPN game summary API to extract:
- ESPN predictor win probabilities (incorporates injuries, form, roster)
- News headlines (scanned for injury keywords)
- Pickcenter spread

Used by the daily prediction pipeline to flag games where our model
diverges significantly from ESPN's injury-aware probabilities.

Data source:
    site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={game_id}
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from config.constants import INJURY_CHECK

logger = logging.getLogger(__name__)


@dataclass
class GameContext:
    """ESPN game context for a single game."""

    game_id: str
    espn_home_prob: float | None = None
    espn_away_prob: float | None = None
    espn_spread: float | None = None
    injury_keywords_found: list[str] = field(default_factory=list)
    news_headlines: list[str] = field(default_factory=list)
    fetch_success: bool = False


def fetch_game_context(game_ids: list[str]) -> dict[str, GameContext]:
    """Fetch ESPN game summary for each game and extract context.

    Calls the ESPN game summary API for each game_id, extracting:
    - Predictor probabilities (home/away win %)
    - Pickcenter spread
    - News headlines (scanned for injury-related keywords)

    Args:
        game_ids: List of ESPN game IDs to fetch.

    Returns:
        Dict mapping game_id -> GameContext. Games that fail to fetch
        will have fetch_success=False.
    """
    results: dict[str, GameContext] = {}

    for i, game_id in enumerate(game_ids):
        ctx = _fetch_single_game_context(game_id)
        results[game_id] = ctx

        # Rate limiting between requests
        if i < len(game_ids) - 1:
            time.sleep(INJURY_CHECK.REQUEST_DELAY)

    success_count = sum(1 for c in results.values() if c.fetch_success)
    logger.info(
        "Fetched ESPN game context: %d/%d successful",
        success_count,
        len(game_ids),
    )
    return results


def _fetch_single_game_context(game_id: str) -> GameContext:
    """Fetch ESPN game summary for a single game.

    Args:
        game_id: ESPN game/event ID.

    Returns:
        GameContext with extracted fields.
    """
    ctx = GameContext(game_id=game_id)
    url = INJURY_CHECK.ESPN_SUMMARY_URL
    params = {"event": game_id}

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.debug("ESPN summary fetch failed for game %s: %s", game_id, e)
        return ctx

    ctx.fetch_success = True

    # Extract predictor probabilities
    predictor = data.get("predictor", {})
    home_team = predictor.get("homeTeam", {})
    away_team = predictor.get("awayTeam", {})

    if "gameProjection" in home_team:
        try:
            ctx.espn_home_prob = float(home_team["gameProjection"]) / 100.0
        except (ValueError, TypeError):
            pass
    if "gameProjection" in away_team:
        try:
            ctx.espn_away_prob = float(away_team["gameProjection"]) / 100.0
        except (ValueError, TypeError):
            pass

    # Extract pickcenter spread
    pickcenter = data.get("pickcenter", [])
    if pickcenter:
        spread_val = pickcenter[0].get("spread")
        if spread_val is not None:
            try:
                ctx.espn_spread = float(spread_val)
            except (ValueError, TypeError):
                pass

    # Extract and scan news headlines
    news = data.get("news", {})
    articles = news.get("articles", [])
    keywords_lower = tuple(k.lower() for k in INJURY_CHECK.INJURY_KEYWORDS)

    for article in articles:
        headline = article.get("headline", "")
        if headline:
            ctx.news_headlines.append(headline)
            headline_lower = headline.lower()
            for kw in keywords_lower:
                if kw in headline_lower:
                    ctx.injury_keywords_found.append(kw)

    # Deduplicate keywords
    ctx.injury_keywords_found = list(set(ctx.injury_keywords_found))

    return ctx


def check_divergence(
    model_prob: float,
    espn_prob: float | None,
) -> dict[str, Any]:
    """Check probability divergence between model and ESPN predictor.

    Args:
        model_prob: Our model's home win probability.
        espn_prob: ESPN predictor's home win probability (or None).

    Returns:
        Dict with:
            divergence: signed difference (model - ESPN) in percentage points
            is_warning: True if divergence exceeds warning threshold
            is_blocked: True if divergence exceeds block threshold
    """
    if espn_prob is None:
        return {"divergence": None, "is_warning": False, "is_blocked": False}

    divergence = model_prob - espn_prob
    abs_div = abs(divergence)

    return {
        "divergence": divergence,
        "is_warning": abs_div >= INJURY_CHECK.DIVERGENCE_WARN_THRESHOLD,
        "is_blocked": abs_div >= INJURY_CHECK.DIVERGENCE_BLOCK_THRESHOLD,
    }
