"""Backfill starter IDs for MLB games from boxscore data.

The original mlb_fetch_historical.py used the schedule endpoint which provides
probable_pitcher_id — but for completed games these fields were empty. This script
fetches actual starter IDs from boxscore data via fetch_game_result().

Uses checkpoint/resume pattern for fault tolerance (~63 min for all 7,505 games).

Usage:
    python scripts/mlb_backfill_starters.py --dry-run
    python scripts/mlb_backfill_starters.py --season 2023
    python scripts/mlb_backfill_starters.py
    python scripts/mlb_backfill_starters.py --delay 0.3 --batch-size 100
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Generator, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import MLB_DATABASE_PATH as DEFAULT_DB_PATH

CHECKPOINT_PATH = BASE_DIR / "data" / "mlb_backfill_starters_checkpoint.json"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


@contextmanager
def get_conn(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """SQLite connection context manager with WAL + FK support."""
    conn = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def get_games_needing_starters(db_path: Path, season: Optional[int] = None) -> list[int]:
    """Return game_pks where status='final' AND either starter ID is NULL.

    Args:
        db_path: Path to mlb_data.db.
        season: Optional season filter.

    Returns:
        List of game_pk integers needing backfill.
    """
    sql = (
        "SELECT game_pk FROM games "
        "WHERE status = 'final' "
        "AND (home_starter_id IS NULL OR away_starter_id IS NULL)"
    )
    params: list = []
    if season is not None:
        sql += " AND season = ?"
        params.append(season)
    sql += " ORDER BY game_pk"

    with get_conn(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [row["game_pk"] for row in rows]


def load_checkpoint(path: Path) -> set[int]:
    """Load set of already-processed game_pks from checkpoint JSON."""
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("processed_game_pks", []))
    return set()


def save_checkpoint(path: Path, processed: set[int]) -> None:
    """Write processed game_pks to checkpoint JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(
            {"processed_game_pks": sorted(processed), "count": len(processed)},
            indent=2,
            fp=f,
        )


def upsert_players_if_missing(conn: sqlite3.Connection, player_ids: set[int]) -> int:
    """INSERT OR IGNORE placeholder rows into players table for FK constraint.

    Args:
        conn: Active SQLite connection.
        player_ids: Set of MLBAM player IDs to ensure exist.

    Returns:
        Number of new players inserted.
    """
    if not player_ids:
        return 0
    rows = [(pid, f"Player {pid}") for pid in player_ids]
    cursor = conn.executemany(
        "INSERT OR IGNORE INTO players (player_id, full_name) VALUES (?, ?)",
        rows,
    )
    return cursor.rowcount


def update_starters_batch(
    db_path: Path,
    updates: list[tuple[Optional[int], Optional[int], int]],
) -> tuple[int, int]:
    """Batch UPDATE games with starter IDs. Also inserts missing player FKs.

    Args:
        db_path: Path to mlb_data.db.
        updates: List of (home_starter_id, away_starter_id, game_pk) tuples.

    Returns:
        Tuple of (games_updated, new_players_added).
    """
    if not updates:
        return 0, 0

    # Collect all non-None player IDs for FK insertion
    player_ids: set[int] = set()
    for home_id, away_id, _game_pk in updates:
        if home_id is not None:
            player_ids.add(home_id)
        if away_id is not None:
            player_ids.add(away_id)

    with get_conn(db_path) as conn:
        new_players = upsert_players_if_missing(conn, player_ids)
        conn.executemany(
            "UPDATE games SET home_starter_id = ?, away_starter_id = ?, "
            "updated_at = CURRENT_TIMESTAMP WHERE game_pk = ?",
            updates,
        )

    return len(updates), new_players


def backfill(
    db_path: Path,
    checkpoint_path: Path,
    season: Optional[int] = None,
    delay: float = 0.5,
    batch_size: int = 50,
    dry_run: bool = False,
) -> dict[str, int]:
    """Main backfill loop: fetch boxscores, extract starters, update DB.

    Args:
        db_path: Path to mlb_data.db.
        checkpoint_path: Path to checkpoint JSON file.
        season: Optional season filter.
        delay: Seconds between API calls.
        batch_size: Number of updates to accumulate before flushing to DB.
        dry_run: If True, print what would be updated without writing.

    Returns:
        Summary dict with counts.
    """
    # Late import to avoid requiring statsapi at module level
    sys.path.insert(0, str(BASE_DIR))
    from pipelines.mlb_stats_api import MLBStatsAPIClient

    all_game_pks = get_games_needing_starters(db_path, season)
    processed = set() if dry_run else load_checkpoint(checkpoint_path)
    remaining = [gp for gp in all_game_pks if gp not in processed]

    logger.info(
        "Games needing starters: %d total, %d already processed, %d remaining",
        len(all_game_pks),
        len(processed),
        len(remaining),
    )

    if not remaining:
        logger.info("Nothing to backfill.")
        return _build_summary(db_path, season, 0, 0)

    if dry_run:
        logger.info("[DRY RUN] Would process %d games. No DB writes.", len(remaining))
        return {"total_games": len(all_game_pks), "remaining": len(remaining)}

    client = MLBStatsAPIClient(request_delay=delay)
    batch: list[tuple[Optional[int], Optional[int], int]] = []
    total_updated = 0
    total_new_players = 0
    home_found = 0
    away_found = 0
    both_found = 0
    neither_found = 0
    api_errors = 0

    for i, game_pk in enumerate(remaining, 1):
        try:
            result = client.fetch_game_result(game_pk)
        except Exception as exc:
            logger.warning("Error fetching game_pk=%d: %s", game_pk, exc)
            api_errors += 1
            processed.add(game_pk)
            continue

        if result is None:
            logger.debug("No result for game_pk=%d (API returned None)", game_pk)
            api_errors += 1
            processed.add(game_pk)
            continue

        h_id = result.home_starter_id
        a_id = result.away_starter_id

        if h_id is not None:
            home_found += 1
        if a_id is not None:
            away_found += 1
        if h_id is not None and a_id is not None:
            both_found += 1
        if h_id is None and a_id is None:
            neither_found += 1

        batch.append((h_id, a_id, game_pk))
        processed.add(game_pk)

        # Flush batch
        if len(batch) >= batch_size:
            n_updated, n_players = update_starters_batch(db_path, batch)
            total_updated += n_updated
            total_new_players += n_players
            batch.clear()
            save_checkpoint(checkpoint_path, processed)
            logger.info(
                "  Progress: %d/%d (%.1f%%) — %d updated, %d new players",
                i,
                len(remaining),
                100 * i / len(remaining),
                total_updated,
                total_new_players,
            )

    # Flush remaining
    if batch:
        n_updated, n_players = update_starters_batch(db_path, batch)
        total_updated += n_updated
        total_new_players += n_players
        save_checkpoint(checkpoint_path, processed)

    total_processed = home_found + away_found - both_found + neither_found
    logger.info("=" * 60)
    logger.info("Backfill complete: %d games processed", total_processed)
    logger.info("  Home starter found: %d", home_found)
    logger.info("  Away starter found: %d", away_found)
    logger.info("  Both found: %d", both_found)
    logger.info("  Neither found: %d", neither_found)
    logger.info("  API errors: %d", api_errors)
    logger.info("  New players added: %d", total_new_players)
    logger.info("  DB rows updated: %d", total_updated)

    return {
        "total_games": len(all_game_pks),
        "processed": total_processed,
        "home_found": home_found,
        "away_found": away_found,
        "both_found": both_found,
        "neither_found": neither_found,
        "api_errors": api_errors,
        "new_players": total_new_players,
        "updated": total_updated,
    }


def _build_summary(
    db_path: Path, season: Optional[int], updated: int, new_players: int
) -> dict[str, int]:
    """Query DB for current starter coverage and return summary."""
    where = "WHERE status = 'final'"
    params: list = []
    if season is not None:
        where += " AND season = ?"
        params.append(season)

    with get_conn(db_path) as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM games {where}",  # noqa: S608  # nosec B608
            params,
        ).fetchone()[0]
        has_home = conn.execute(
            f"SELECT COUNT(*) FROM games {where} AND home_starter_id IS NOT NULL",  # noqa: S608  # nosec B608
            params,
        ).fetchone()[0]
        has_away = conn.execute(
            f"SELECT COUNT(*) FROM games {where} AND away_starter_id IS NOT NULL",  # noqa: S608  # nosec B608
            params,
        ).fetchone()[0]
        has_both = conn.execute(
            f"SELECT COUNT(*) FROM games {where} "  # noqa: S608  # nosec B608
            "AND home_starter_id IS NOT NULL AND away_starter_id IS NOT NULL",
            params,
        ).fetchone()[0]

    logger.info("Current coverage (season=%s):", season or "all")
    logger.info("  Total final games: %d", total)
    if total > 0:
        logger.info("  Home starter: %d (%.1f%%)", has_home, 100 * has_home / total)
        logger.info("  Away starter: %d (%.1f%%)", has_away, 100 * has_away / total)
        logger.info("  Both starters: %d (%.1f%%)", has_both, 100 * has_both / total)

    return {
        "total_games": total,
        "has_home": has_home,
        "has_away": has_away,
        "has_both": has_both,
        "updated": updated,
        "new_players": new_players,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for mlb_backfill_starters."""
    parser = argparse.ArgumentParser(
        description="Backfill starter IDs for MLB games from boxscore data"
    )
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        metavar="PATH",
        help=f"Path to mlb_data.db (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--season",
        type=int,
        choices=[2023, 2024, 2025],
        help="Filter to a specific season (default: all)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds between API calls (default: 0.5)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Games per DB flush + checkpoint (default: 50)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without writing to DB",
    )
    parser.add_argument(
        "--reset-checkpoint",
        action="store_true",
        help="Ignore existing checkpoint and reprocess all games",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Print current starter coverage without fetching",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    if not db_path.exists():
        logger.error("Database not found: %s", db_path)
        logger.error("Run first: python scripts/mlb_init_db.py --seed-teams")
        sys.exit(1)

    if args.summary_only:
        _build_summary(db_path, args.season, 0, 0)
        return

    checkpoint_path = CHECKPOINT_PATH
    if args.reset_checkpoint and checkpoint_path.exists():
        checkpoint_path.unlink()
        logger.info("Checkpoint reset — will reprocess all games")

    backfill(
        db_path=db_path,
        checkpoint_path=checkpoint_path,
        season=args.season,
        delay=args.delay,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
