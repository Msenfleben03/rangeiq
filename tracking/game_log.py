"""Game Log Tracking — records every D1 NCAAB game with predictions and odds.

Append-only log: each daily pipeline run inserts all games for the target date.
Settlement run updates scores, closing odds, and results the next day.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


def insert_game_log_entries(
    db_path: str | Path,
    game_date: str,
    games: list[dict],
    predictions: dict[str, dict],
    bets: dict[str, str],
) -> int:
    """Insert games into game_log table.

    Args:
        db_path: Path to ncaab_betting.db.
        game_date: Date string (YYYY-MM-DD).
        games: List of game dicts from ESPN Scoreboard (must have game_id, home, away).
        predictions: Dict mapping game_id -> {model_prob_home, edge,
            odds_opening_home, odds_opening_away}.
        bets: Dict mapping game_id -> bet_side ("home" or "away") for games we bet.

    Returns:
        Number of rows inserted (skips duplicates).
    """
    conn = sqlite3.connect(str(db_path))
    inserted = 0

    try:
        for game in games:
            game_id = game.get("game_id", "")
            if not game_id:
                continue

            pred = predictions.get(game_id, {})
            bet_side = bets.get(game_id)

            try:
                cursor = conn.execute(
                    """INSERT OR IGNORE INTO game_log
                        (game_date, game_id, home, away,
                         model_prob_home, edge,
                         odds_opening_home, odds_opening_away,
                         bet_placed, bet_side, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        game_date,
                        game_id,
                        game.get("home", ""),
                        game.get("away", ""),
                        pred.get("model_prob_home"),
                        pred.get("edge"),
                        pred.get("odds_opening_home"),
                        pred.get("odds_opening_away"),
                        1 if bet_side else 0,
                        bet_side,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                if cursor.rowcount > 0:
                    inserted += 1
            except sqlite3.Error as e:
                logger.warning("Failed to insert game %s: %s", game_id, e)

        conn.commit()
    finally:
        conn.close()

    logger.info("Game log: inserted %d games for %s", inserted, game_date)
    return inserted


def settle_game_log_entries(
    db_path: str | Path,
    completed_games: list[dict],
    closing_odds: dict[str, dict],
) -> int:
    """Update game_log with final scores, closing odds, and results.

    Args:
        db_path: Path to ncaab_betting.db.
        completed_games: List of game dicts with game_id, home_score, away_score.
        closing_odds: Dict mapping game_id -> {"home": int, "away": int} closing MLs.
            Games not in this dict get NULL closing odds.

    Returns:
        Number of games settled.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    settled = 0

    try:
        for game in completed_games:
            game_id = game.get("game_id", "")
            if not game_id:
                continue

            # Check if game exists and is unsettled
            row = conn.execute(
                "SELECT id, result FROM game_log WHERE game_id = ?",
                (game_id,),
            ).fetchone()

            if row is None:
                logger.debug("Game %s not in game_log, skipping", game_id)
                continue

            if row["result"] is not None:
                logger.debug("Game %s already settled, skipping", game_id)
                continue

            home_score = game.get("home_score", 0)
            away_score = game.get("away_score", 0)
            result = "home" if home_score > away_score else "away"

            odds = closing_odds.get(game_id, {})
            closing_home = odds.get("home")
            closing_away = odds.get("away")

            conn.execute(
                """UPDATE game_log
                   SET home_score = ?, away_score = ?, result = ?,
                       odds_closing_home = ?, odds_closing_away = ?,
                       settled_at = ?
                   WHERE game_id = ?""",
                (
                    home_score,
                    away_score,
                    result,
                    closing_home,
                    closing_away,
                    datetime.now(timezone.utc).isoformat(),
                    game_id,
                ),
            )
            settled += 1

        conn.commit()
    finally:
        conn.close()

    logger.info("Game log: settled %d games", settled)
    return settled
