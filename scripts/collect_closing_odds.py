"""Collect Closing Odds — Multi-Provider Post-Game Odds Retrieval.

Fetches closing odds for recently completed NCAAB games from multiple
providers (ESPN Core API + The Odds API) and stores them in the
odds_snapshots table. Updates bets.odds_closing and bets.clv for
any matched paper bets.

Design:
    1. Query ESPN Site API scoreboard for games completed in the last N hours
    2. For each completed game, fetch closing odds from:
       - ESPN Core API (free, has open/close data for completed games)
       - The Odds API (free tier, 500 credits/month, multi-book lines)
    3. Store ALL provider snapshots in odds_snapshots (one row per game+book)
    4. Pick "consensus" closing line and update bets.odds_closing + bets.clv

Usage:
    # Collect closing odds for games completed in last 48 hours
    python scripts/collect_closing_odds.py

    # Specify lookback window
    python scripts/collect_closing_odds.py --hours 72

    # Dry run — show what would be collected
    python scripts/collect_closing_odds.py --dry-run

    # Specific date
    python scripts/collect_closing_odds.py --date 2026-03-06

    # Skip The Odds API (save credits)
    python scripts/collect_closing_odds.py --espn-only

Integration:
    Add to daily pipeline after settle_bets step:
        python scripts/collect_closing_odds.py --hours 48
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import requests

from betting.odds_converter import calculate_clv
from config.settings import NCAAB_DATABASE_PATH
from pipelines.espn_core_odds_provider import (
    ESPNCoreOddsFetcher,
    OddsSnapshot,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports"
NCAAB_SCOREBOARD = f"{ESPN_SITE_BASE}/basketball/mens-college-basketball/scoreboard"

# The Odds API — free tier (500 credits/month)
ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports"
ODDS_API_SPORT_KEY = "basketball_ncaab"
ODDS_API_BOOKMAKERS = ["draftkings", "fanduel", "betmgm", "williamhill_us", "espnbet"]

# Provider priority for consensus closing line (lower = preferred)
PROVIDER_PRIORITY = {
    "draftkings": 1,
    "fanduel": 2,
    "betmgm": 3,
    "williamhill_us": 4,  # Caesars
    "espnbet": 5,
    "espn_bet": 5,
    "caesars": 4,
}


# ---------------------------------------------------------------------------
# ESPN Scoreboard — discover completed games
# ---------------------------------------------------------------------------


def fetch_completed_games(
    date: str,
    session: requests.Session | None = None,
) -> list[dict]:
    """Fetch completed NCAAB games from ESPN scoreboard for a date.

    Args:
        date: Date in YYYY-MM-DD format.
        session: Optional requests session for connection reuse.

    Returns:
        List of dicts with game_id, home, away, home_name, away_name,
        home_score, away_score, status.
    """
    s = session or requests.Session()
    date_compact = date.replace("-", "")
    url = f"{NCAAB_SCOREBOARD}?dates={date_compact}&limit=500"

    try:
        resp = s.get(url, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error("Scoreboard fetch failed for %s: %s", date, exc)
        return []

    games = []
    for event in data.get("events", []):
        competition = event.get("competitions", [{}])[0]
        status_type = competition.get("status", {}).get("type", {}).get("name", "")

        if status_type != "STATUS_FINAL":
            continue

        competitors = competition.get("competitors", [])
        if len(competitors) < 2:
            continue

        home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
        away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

        games.append(
            {
                "game_id": str(event.get("id", "")),
                "home": home.get("team", {}).get("abbreviation", ""),
                "away": away.get("team", {}).get("abbreviation", ""),
                "home_name": home.get("team", {}).get("displayName", ""),
                "away_name": away.get("team", {}).get("displayName", ""),
                "home_score": int(home.get("score", 0)),
                "away_score": int(away.get("score", 0)),
            }
        )

    logger.info("Found %d completed games for %s", len(games), date)
    return games


# ---------------------------------------------------------------------------
# Provider 1: ESPN Core API (free, reliable closing odds)
# ---------------------------------------------------------------------------


def fetch_espn_closing_odds(
    game_ids: list[str],
) -> dict[str, OddsSnapshot]:
    """Fetch closing odds from ESPN Core API for completed games.

    Args:
        game_ids: List of ESPN event IDs.

    Returns:
        Dict mapping game_id to best OddsSnapshot (prefers pre-game provider).
    """
    fetcher = ESPNCoreOddsFetcher(sport="ncaab", requests_per_second=2.0)
    results: dict[str, OddsSnapshot] = {}

    for idx, gid in enumerate(game_ids):
        try:
            snapshots = fetcher.fetch_game_odds(gid)
            if snapshots:
                # Prefer pre-game providers (filter out live provider ID 59)
                pre_game = [s for s in snapshots if s.provider_id != 59]
                best = pre_game[0] if pre_game else snapshots[0]
                results[gid] = best
        except Exception as exc:
            logger.warning("ESPN Core failed for %s: %s", gid, exc)

        if (idx + 1) % 50 == 0:
            logger.info("ESPN Core: %d/%d games fetched", idx + 1, len(game_ids))

    fetcher.close()
    logger.info("ESPN Core: got closing odds for %d/%d games", len(results), len(game_ids))
    return results


# ---------------------------------------------------------------------------
# Provider 2: The Odds API (multi-book, free tier)
# ---------------------------------------------------------------------------


def fetch_odds_api_closing(
    api_key: str,
    game_ids: set[str] | None = None,
) -> dict[str, list[dict]]:
    """Fetch current odds from The Odds API for all live/upcoming NCAAB games.

    The Odds API returns odds for current/upcoming events, not historical.
    For closing odds, call this AFTER games complete — the API may still
    have the last-known odds cached briefly. Primary value is for games
    that are about to start or just started.

    Args:
        api_key: The Odds API key.
        game_ids: Optional filter — only return odds for these game IDs.

    Returns:
        Dict mapping game_id to list of bookmaker odds dicts.
        Each dict has: sportsbook, moneyline_home, moneyline_away,
        spread_home, spread_home_odds, spread_away_odds,
        total, over_odds, under_odds.
    """
    if not api_key:
        logger.info("No ODDS_API_KEY set — skipping The Odds API")
        return {}

    url = f"{ODDS_API_BASE}/{ODDS_API_SPORT_KEY}/odds"
    params = {
        "apiKey": api_key,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "american",
        "bookmakers": ",".join(ODDS_API_BOOKMAKERS),
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        remaining = resp.headers.get("x-requests-remaining", "?")
        used = resp.headers.get("x-requests-used", "?")
        logger.info("Odds API credits: %s used, %s remaining", used, remaining)
        resp.raise_for_status()
        events = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error("Odds API request failed: %s", exc)
        return {}

    results: dict[str, list[dict]] = {}

    for event in events:
        eid = event.get("id", "")
        if game_ids and eid not in game_ids:
            continue

        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")
        book_odds: list[dict] = []

        for bookmaker in event.get("bookmakers", []):
            book_key = bookmaker.get("key", "")
            entry: dict[str, Any] = {
                "sportsbook": book_key,
                "home_team": home_team,
                "away_team": away_team,
            }

            for market in bookmaker.get("markets", []):
                mkey = market.get("key", "")
                outcomes = {o["name"]: o for o in market.get("outcomes", [])}

                if mkey == "h2h":
                    home_oc = outcomes.get(home_team, {})
                    away_oc = outcomes.get(away_team, {})
                    entry["moneyline_home"] = _safe_int(home_oc.get("price"))
                    entry["moneyline_away"] = _safe_int(away_oc.get("price"))

                elif mkey == "spreads":
                    home_oc = outcomes.get(home_team, {})
                    away_oc = outcomes.get(away_team, {})
                    entry["spread_home"] = home_oc.get("point")
                    entry["spread_home_odds"] = _safe_int(home_oc.get("price"))
                    entry["spread_away_odds"] = _safe_int(away_oc.get("price"))

                elif mkey == "totals":
                    over_oc = outcomes.get("Over", {})
                    under_oc = outcomes.get("Under", {})
                    entry["total"] = over_oc.get("point")
                    entry["over_odds"] = _safe_int(over_oc.get("price"))
                    entry["under_odds"] = _safe_int(under_oc.get("price"))

            book_odds.append(entry)

        if book_odds:
            results[eid] = book_odds

    logger.info("Odds API: got odds for %d events", len(results))
    return results


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------


def _safe_int(value: Any) -> Optional[int]:
    """Convert value to int safely."""
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def get_existing_closing_game_ids(db_path: Path) -> set[str]:
    """Get game IDs that already have closing odds stored.

    Args:
        db_path: Path to SQLite database.

    Returns:
        Set of game_id strings with existing closing snapshots.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute("SELECT DISTINCT game_id FROM odds_snapshots WHERE is_closing = 1")
        return {row[0] for row in cursor.fetchall()}
    finally:
        conn.close()


def store_closing_snapshot(
    db_path: Path,
    game_id: str,
    sportsbook: str,
    spread_home: Optional[float],
    spread_home_odds: Optional[int],
    spread_away_odds: Optional[int],
    total: Optional[float],
    over_odds: Optional[int],
    under_odds: Optional[int],
    moneyline_home: Optional[int],
    moneyline_away: Optional[int],
    confidence: float = 0.92,
) -> bool:
    """Store a closing odds snapshot to odds_snapshots table.

    Uses INSERT OR IGNORE with UNIQUE(game_id, sportsbook, snapshot_type, market_type)
    to avoid duplicates.

    Returns:
        True if row was inserted, False if duplicate.
    """
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.execute(
            """INSERT OR IGNORE INTO odds_snapshots
                (game_id, sportsbook, captured_at,
                 spread_home, spread_home_odds, spread_away_odds,
                 total, over_odds, under_odds,
                 moneyline_home, moneyline_away,
                 is_closing, confidence, snapshot_type, market_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                game_id,
                sportsbook,
                datetime.now(timezone.utc).isoformat(),
                spread_home,
                spread_home_odds,
                spread_away_odds,
                total,
                over_odds,
                under_odds,
                moneyline_home,
                moneyline_away,
                True,
                confidence,
                "closing",
                "full_game",
            ),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_bets_clv(db_path: Path, game_id: str) -> int:
    """Update bets.odds_closing and bets.clv for a game using consensus closing line.

    Picks the highest-priority sportsbook's closing moneyline from
    odds_snapshots and updates matching bets.

    Args:
        db_path: Path to SQLite database.
        game_id: ESPN game ID.

    Returns:
        Number of bets updated.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # Get all closing snapshots for this game, ordered by priority
        rows = conn.execute(
            """SELECT sportsbook, moneyline_home, moneyline_away,
                      spread_home, spread_home_odds, spread_away_odds,
                      total, over_odds, under_odds
               FROM odds_snapshots
               WHERE game_id = ? AND is_closing = 1
               ORDER BY confidence DESC""",
            (game_id,),
        ).fetchall()

        if not rows:
            return 0

        # Pick best snapshot by provider priority
        best = min(rows, key=lambda r: PROVIDER_PRIORITY.get(r["sportsbook"], 99))

        # Get unsettled-CLV bets for this game
        bets = conn.execute(
            "SELECT id, selection, odds_placed FROM bets WHERE game_id = ? AND clv IS NULL",
            (game_id,),
        ).fetchall()

        updated = 0
        for bet in bets:
            selection = (bet["selection"] or "").upper()
            closing_ml = None

            if "HOME" in selection or "ML" in selection:
                closing_ml = best["moneyline_home"]
            elif "AWAY" in selection:
                closing_ml = best["moneyline_away"]

            if closing_ml is None:
                continue

            odds_placed = bet["odds_placed"]
            try:
                clv = calculate_clv(odds_placed, closing_ml)
            except Exception:
                clv = None

            conn.execute(
                "UPDATE bets SET odds_closing = ?, clv = ? WHERE id = ?",
                (closing_ml, clv, bet["id"]),
            )
            updated += 1

        conn.commit()
        return updated
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Main collection logic
# ---------------------------------------------------------------------------


def collect_closing_odds(
    db_path: Path,
    lookback_hours: int = 48,
    target_date: str | None = None,
    espn_only: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Collect closing odds for recently completed games from multiple providers.

    Args:
        db_path: Path to ncaab_betting.db.
        lookback_hours: How far back to look for completed games.
        target_date: If set, only collect for this specific date (YYYY-MM-DD).
        espn_only: If True, skip The Odds API (save credits).
        dry_run: If True, show what would be collected without DB writes.

    Returns:
        Summary dict with collection stats.
    """
    stats: dict[str, Any] = {
        "dates_checked": [],
        "games_found": 0,
        "games_already_have_closing": 0,
        "games_needing_odds": 0,
        "espn_core_collected": 0,
        "odds_api_collected": 0,
        "snapshots_stored": 0,
        "bets_clv_updated": 0,
        "errors": [],
    }

    # Determine dates to check
    if target_date:
        dates = [target_date]
    else:
        today = datetime.now()
        dates = [
            (today - timedelta(days=d)).strftime("%Y-%m-%d")
            for d in range(lookback_hours // 24 + 1)
        ]

    stats["dates_checked"] = dates

    # Get existing closing odds to skip
    existing = get_existing_closing_game_ids(db_path) if not dry_run else set()

    # Discover completed games from ESPN scoreboard
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (sports-betting-research)"
    all_games: list[dict] = []

    for date in dates:
        games = fetch_completed_games(date, session=session)
        all_games.extend(games)

    stats["games_found"] = len(all_games)

    # Filter out games that already have closing odds
    new_games = [g for g in all_games if g["game_id"] not in existing]
    stats["games_already_have_closing"] = len(all_games) - len(new_games)
    stats["games_needing_odds"] = len(new_games)

    if dry_run:
        print(f"\n{'=' * 60}")
        print("DRY RUN — Closing Odds Collection")
        print(f"{'=' * 60}")
        print(f"Dates checked: {', '.join(dates)}")
        print(f"Total completed games: {len(all_games)}")
        print(f"Already have closing odds: {stats['games_already_have_closing']}")
        print(f"Need closing odds: {len(new_games)}")
        print()
        for g in new_games[:20]:
            print(
                f"  {g['away']} @ {g['home']}  ({g['away_score']}-{g['home_score']})  "
                f"ID: {g['game_id']}"
            )
        if len(new_games) > 20:
            print(f"  ... and {len(new_games) - 20} more")
        return stats

    if not new_games:
        logger.info("No new games need closing odds")
        return stats

    game_ids = [g["game_id"] for g in new_games]

    # --- Provider 1: ESPN Core API ---
    logger.info("Fetching closing odds from ESPN Core API for %d games...", len(game_ids))
    espn_results = fetch_espn_closing_odds(game_ids)

    for gid, snapshot in espn_results.items():
        stored = store_closing_snapshot(
            db_path=db_path,
            game_id=gid,
            sportsbook=snapshot.provider_name.lower().replace(" ", "_"),
            spread_home=snapshot.home_spread_close or snapshot.spread,
            spread_home_odds=snapshot.home_spread_odds_close or snapshot.home_spread_odds,
            spread_away_odds=snapshot.away_spread_odds_close or snapshot.away_spread_odds,
            total=snapshot.total_close or snapshot.over_under,
            over_odds=snapshot.over_odds_close or snapshot.over_odds,
            under_odds=snapshot.under_odds_close or snapshot.under_odds,
            moneyline_home=snapshot.home_ml_close or snapshot.home_moneyline,
            moneyline_away=snapshot.away_ml_close or snapshot.away_moneyline,
            confidence=0.92,
        )
        if stored:
            stats["espn_core_collected"] += 1
            stats["snapshots_stored"] += 1

    # --- Provider 2: The Odds API (multi-book) ---
    odds_api_results: dict[str, list[dict]] = {}
    if not espn_only:
        api_key = os.environ.get("ODDS_API_KEY", "")
        if api_key:
            logger.info("Fetching odds from The Odds API (multi-book)...")
            odds_api_results = fetch_odds_api_closing(api_key, set(game_ids))

            for gid, book_list in odds_api_results.items():
                for book in book_list:
                    stored = store_closing_snapshot(
                        db_path=db_path,
                        game_id=gid,
                        sportsbook=book["sportsbook"],
                        spread_home=book.get("spread_home"),
                        spread_home_odds=book.get("spread_home_odds"),
                        spread_away_odds=book.get("spread_away_odds"),
                        total=book.get("total"),
                        over_odds=book.get("over_odds"),
                        under_odds=book.get("under_odds"),
                        moneyline_home=book.get("moneyline_home"),
                        moneyline_away=book.get("moneyline_away"),
                        confidence=0.95,
                    )
                    if stored:
                        stats["odds_api_collected"] += 1
                        stats["snapshots_stored"] += 1
        else:
            logger.info(
                "ODDS_API_KEY not set — skipping The Odds API (use --espn-only to suppress)"
            )

    # --- Update CLV for bets ---
    games_with_new_odds = set(espn_results.keys())
    if not espn_only and odds_api_results:
        games_with_new_odds.update(odds_api_results.keys())

    for gid in games_with_new_odds:
        try:
            updated = update_bets_clv(db_path, gid)
            stats["bets_clv_updated"] += updated
        except Exception as exc:
            logger.warning("CLV update failed for %s: %s", gid, exc)
            stats["errors"].append(f"CLV update {gid}: {exc}")

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Collect closing odds from multiple providers for CLV validation"
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=48,
        help="Lookback window in hours (default: 48)",
    )
    parser.add_argument(
        "--date",
        help="Collect for a specific date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--espn-only",
        action="store_true",
        help="Only use ESPN Core API (skip The Odds API to save credits)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be collected without writing to DB",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=NCAAB_DATABASE_PATH,
        help=f"Database path (default: {NCAAB_DATABASE_PATH})",
    )

    args = parser.parse_args()

    stats = collect_closing_odds(
        db_path=args.db,
        lookback_hours=args.hours,
        target_date=args.date,
        espn_only=args.espn_only,
        dry_run=args.dry_run,
    )

    if not args.dry_run:
        print(f"\n{'=' * 60}")
        print("Closing Odds Collection Summary")
        print(f"{'=' * 60}")
        print(f"Dates checked:        {', '.join(stats['dates_checked'])}")
        print(f"Games found:          {stats['games_found']}")
        print(f"Already had closing:  {stats['games_already_have_closing']}")
        print(f"Needed odds:          {stats['games_needing_odds']}")
        print(f"ESPN Core collected:  {stats['espn_core_collected']}")
        print(f"Odds API collected:   {stats['odds_api_collected']}")
        print(f"Total stored:         {stats['snapshots_stored']}")
        print(f"Bets CLV updated:     {stats['bets_clv_updated']}")
        if stats["errors"]:
            print(f"Errors:               {len(stats['errors'])}")
            for err in stats["errors"][:5]:
                print(f"  - {err}")


if __name__ == "__main__":
    main()
