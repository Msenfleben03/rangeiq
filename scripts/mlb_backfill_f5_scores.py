"""Backfill F5 (first 5 innings) scores for all final MLB games.

Adds home_f5_score and away_f5_score columns to the games table,
then populates them by fetching linescore data from the MLB Stats API.

Usage:
    python scripts/mlb_backfill_f5_scores.py
    python scripts/mlb_backfill_f5_scores.py --db-path data/mlb_data.db
    python scripts/mlb_backfill_f5_scores.py --limit 100  # test run
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from config.settings import MLB_DATABASE_PATH as DB_PATH

MLB_LINESCORE_URL = "https://statsapi.mlb.com/api/v1/game/{game_pk}/linescore"
THROTTLE_SECONDS = 0.1
CHECKPOINT_EVERY = 500


def migrate_f5_columns(db_path: str) -> None:
    """Add home_f5_score and away_f5_score columns to games table if absent.

    Idempotent: safe to call multiple times.

    Args:
        db_path: Path to mlb_data.db.
    """
    conn = sqlite3.connect(db_path)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(games)")}
    for col in ("home_f5_score", "away_f5_score"):
        if col not in existing:
            conn.execute(f"ALTER TABLE games ADD COLUMN {col} INTEGER")
            logger.info("Added column %s to games table", col)
    conn.commit()
    conn.close()


def fetch_f5_scores(game_pk: int) -> tuple[int, int] | None:
    """Fetch F5 scores for a single game from MLB Stats API linescore.

    Args:
        game_pk: MLB game primary key.

    Returns:
        (home_f5_score, away_f5_score) or None if linescore unavailable.
        Ties (home == away after 5 innings) are valid — returns the tie.
        Games with fewer than 5 innings recorded return partial sums.
    """
    url = MLB_LINESCORE_URL.format(game_pk=game_pk)
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("linescore(%d) failed: %s", game_pk, exc)
        return None

    data = resp.json()
    innings = data.get("innings", [])
    if not innings:
        logger.debug("No innings data for game_pk=%d", game_pk)
        return None

    home_f5 = sum(inn.get("home", {}).get("runs", 0) for inn in innings[:5])
    away_f5 = sum(inn.get("away", {}).get("runs", 0) for inn in innings[:5])
    return home_f5, away_f5


def backfill(db_path: str, limit: int | None = None) -> dict[str, int]:
    """Backfill F5 scores for all final games missing F5 data.

    Args:
        db_path: Path to mlb_data.db.
        limit: Maximum games to process (None = all). Useful for test runs.

    Returns:
        Dict with keys: total, updated, skipped, failed.
    """
    migrate_f5_columns(db_path)

    conn = sqlite3.connect(db_path)
    query = "SELECT game_pk FROM games WHERE status = 'final' AND home_f5_score IS NULL"
    rows = conn.execute(query).fetchall()
    conn.close()

    game_pks = [row[0] for row in rows]
    if limit is not None:
        game_pks = game_pks[:limit]

    logger.info("Found %d games needing F5 backfill", len(game_pks))

    stats = {"total": len(game_pks), "updated": 0, "skipped": 0, "failed": 0}

    for i, game_pk in enumerate(game_pks, 1):
        scores = fetch_f5_scores(game_pk)

        if scores is None:
            stats["failed"] += 1
        else:
            home_f5, away_f5 = scores
            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE games SET home_f5_score = ?, away_f5_score = ? WHERE game_pk = ?",
                (home_f5, away_f5, game_pk),
            )
            conn.commit()
            conn.close()
            stats["updated"] += 1

        if i % CHECKPOINT_EVERY == 0:
            logger.info(
                "Checkpoint: %d/%d processed (updated=%d, failed=%d)",
                i,
                len(game_pks),
                stats["updated"],
                stats["failed"],
            )

        time.sleep(THROTTLE_SECONDS)

    logger.info(
        "Backfill complete: %d updated, %d failed of %d total",
        stats["updated"],
        stats["failed"],
        stats["total"],
    )
    return stats


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Backfill F5 scores into mlb_data.db")
    parser.add_argument("--db-path", default=str(DB_PATH))
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max games to process (omit for all)",
    )
    args = parser.parse_args()

    stats = backfill(args.db_path, limit=args.limit)
    print(f"Done: {stats}")


if __name__ == "__main__":
    main()
