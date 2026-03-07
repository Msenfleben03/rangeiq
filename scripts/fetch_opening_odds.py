"""Fetch Opening Odds across Lookahead Window.

Queries ESPN Scoreboard API for game IDs across the lookahead window
(today through today+N), then fetches current odds from ESPN Core API.
At nightly run time, current odds represent opening/early lines.

All three markets captured: moneyline, spread, total.

Usage:
    python scripts/fetch_opening_odds.py                        # Today + lookahead window
    python scripts/fetch_opening_odds.py --date 2026-02-25      # Start from specific date
    python scripts/fetch_opening_odds.py --lookahead-days 3     # Override window size
    python scripts/fetch_opening_odds.py --dry-run              # Preview only
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import NCAAB_DATABASE_PATH as DATABASE_PATH
from pipelines.espn_core_odds_provider import ESPNCoreOddsFetcher, OddsSnapshot
from scripts.daily_predictions import fetch_espn_scoreboard
from tracking.database import BettingDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def store_opening_snapshot(db: BettingDatabase, snapshot: OddsSnapshot) -> None:
    """Store an opening odds snapshot to the database.

    Uses the 'current' fields from OddsSnapshot (which at 11pm
    represent opening/early lines for next-day games).

    Args:
        db: BettingDatabase instance.
        snapshot: OddsSnapshot from ESPN Core API.
    """
    db.execute_query(
        """INSERT OR IGNORE INTO odds_snapshots
            (game_id, sportsbook, captured_at,
             spread_home, spread_home_odds, spread_away_odds,
             total, over_odds, under_odds,
             moneyline_home, moneyline_away,
             is_closing, confidence, snapshot_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            snapshot.game_id,
            snapshot.provider_name.lower().replace(" ", "_"),
            datetime.now(timezone.utc).isoformat(),
            snapshot.spread,
            snapshot.home_spread_odds,
            snapshot.away_spread_odds,
            snapshot.over_under,
            snapshot.over_odds,
            snapshot.under_odds,
            snapshot.home_moneyline,
            snapshot.away_moneyline,
            False,  # is_closing
            0.92,  # confidence (ESPN Core API)
            "opening",
        ),
    )


def fetch_opening_odds(
    db: BettingDatabase,
    target_date: datetime | None = None,
) -> dict:
    """Fetch opening odds for a date's games.

    Args:
        db: BettingDatabase instance.
        target_date: Date to fetch odds for. Default: tomorrow.

    Returns:
        Dict with fetch statistics.
    """
    if target_date is None:
        target_date = datetime.now() + timedelta(days=1)

    date_str = target_date.strftime("%Y-%m-%d")
    logger.info("Fetching opening odds for %s", date_str)

    result = {
        "date": date_str,
        "games_found": 0,
        "odds_fetched": 0,
        "odds_failed": 0,
        "skipped_existing": 0,
    }

    # Step 1: Discover games from ESPN Scoreboard
    games = fetch_espn_scoreboard(target_date)
    result["games_found"] = len(games)

    if not games:
        logger.info("No games found for %s", date_str)
        return result

    # Step 2: Check which games already have opening odds
    game_ids = [g["game_id"] for g in games]
    placeholders = ",".join("?" for _ in game_ids)
    existing = db.execute_query(
        f"SELECT game_id FROM odds_snapshots "  # nosec B608
        f"WHERE game_id IN ({placeholders}) AND snapshot_type = 'opening'",
        tuple(game_ids),
    )
    existing_ids = {r["game_id"] for r in existing}

    games_to_fetch = [g for g in games if g["game_id"] not in existing_ids]
    result["skipped_existing"] = len(existing_ids)

    if not games_to_fetch:
        logger.info("All %d games already have opening odds", len(games))
        return result

    logger.info(
        "%d games need opening odds (%d already exist)",
        len(games_to_fetch),
        len(existing_ids),
    )

    # Step 3: Fetch odds from ESPN Core API
    fetcher = ESPNCoreOddsFetcher(sport="ncaab")
    try:
        for game in games_to_fetch:
            game_id = game["game_id"]
            try:
                snapshots = fetcher.fetch_game_odds(game_id)
                if snapshots:
                    # Prefer non-live provider, take first
                    pre_game = [s for s in snapshots if s.provider_id != 59]
                    best = pre_game[0] if pre_game else snapshots[0]
                    store_opening_snapshot(db, best)
                    result["odds_fetched"] += 1
                    logger.info(
                        "Opening odds: %s @ %s -- ML %s/%s, Spread %s, Total %s",
                        game.get("away_name", game.get("away", "")),
                        game.get("home_name", game.get("home", "")),
                        best.home_moneyline,
                        best.away_moneyline,
                        best.spread,
                        best.over_under,
                    )
                else:
                    result["odds_failed"] += 1
                    logger.warning(
                        "No odds available for %s @ %s (%s)",
                        game.get("away_name", game.get("away", "")),
                        game.get("home_name", game.get("home", "")),
                        game_id,
                    )
            except Exception as e:
                result["odds_failed"] += 1
                logger.error("Failed to fetch odds for %s: %s", game_id, e)
    finally:
        fetcher.close()

    logger.info(
        "Opening odds complete: %d fetched, %d failed, %d skipped",
        result["odds_fetched"],
        result["odds_failed"],
        result["skipped_existing"],
    )
    return result


def fetch_opening_odds_lookahead(
    db: BettingDatabase,
    today: datetime,
    lookahead_days: int | None = None,
) -> list[dict]:
    """Fetch opening odds for all games in the lookahead window.

    Args:
        db: BettingDatabase instance.
        today: Current date (start of window).
        lookahead_days: Days to scan. Default from config.

    Returns:
        List of result dicts, one per day scanned.
    """
    from config.constants import PAPER_BETTING

    if lookahead_days is None:
        lookahead_days = PAPER_BETTING.LOOKAHEAD_DAYS

    results = []
    for offset in range(lookahead_days + 1):
        target = today + timedelta(days=offset)
        result = fetch_opening_odds(db, target)
        results.append(result)

    return results


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch opening odds for NCAAB games across lookahead window"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD). Default: today.",
    )
    parser.add_argument(
        "--lookahead-days",
        type=int,
        default=None,
        help="Days to scan ahead. Default from config.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview games without fetching odds.",
    )
    args = parser.parse_args()

    if args.date:
        today = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        today = datetime.now()

    from config.constants import PAPER_BETTING

    lookahead = (
        args.lookahead_days if args.lookahead_days is not None else PAPER_BETTING.LOOKAHEAD_DAYS
    )

    if args.dry_run:
        for offset in range(lookahead + 1):
            target = today + timedelta(days=offset)
            games = fetch_espn_scoreboard(target)
            date_str = target.strftime("%Y-%m-%d")
            print(f"Day+{offset} ({date_str}): {len(games)} games")
            for g in games:
                print(f"  {g['away_name']} @ {g['home_name']} ({g['game_id']})")
        return

    db = BettingDatabase(str(DATABASE_PATH))
    results = fetch_opening_odds_lookahead(db, today, args.lookahead_days)

    print(f"\n{'=' * 60}")
    print("Opening Odds Fetch -- Lookahead Window")
    print(f"{'=' * 60}")
    total_fetched = 0
    total_failed = 0
    for r in results:
        total_fetched += r["odds_fetched"]
        total_failed += r["odds_failed"]
        if r["games_found"] > 0:
            print(
                f"  {r['date']}: {r['games_found']} games, "
                f"{r['odds_fetched']} fetched, "
                f"{r['skipped_existing']} existing, "
                f"{r['odds_failed']} failed"
            )
    print(f"\nTotal: {total_fetched} fetched, {total_failed} failed")


if __name__ == "__main__":
    main()
