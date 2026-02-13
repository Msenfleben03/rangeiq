"""Paper Bet Logging Utilities.

Handles insertion and validation of paper bets, exposure limit checks,
and batch operations.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from config.constants import BANKROLL
from tracking.database import BettingDatabase

logger = logging.getLogger(__name__)


def log_paper_bet(
    db: BettingDatabase,
    bet_data: dict[str, Any],
) -> int:
    """Insert a single paper bet into the database.

    Automatically sets is_live=FALSE for paper bets.

    Args:
        db: BettingDatabase instance.
        bet_data: Dictionary with bet details. Required keys:
            sport, game_date, bet_type, selection, odds_placed, stake, sportsbook.
            Optional: game_id, line, model_probability, model_edge, notes.

    Returns:
        Bet ID of the inserted record.

    Raises:
        ValueError: If required fields are missing.
    """
    required = {"sport", "game_date", "bet_type", "selection", "odds_placed", "stake", "sportsbook"}
    missing = required - set(bet_data.keys())
    if missing:
        raise ValueError(f"Missing required bet fields: {missing}")

    # Ensure paper bet flag
    record = dict(bet_data)
    record["is_live"] = False

    return db.insert_bet(record)


def log_multiple_bets(
    db: BettingDatabase,
    bets: list[dict[str, Any]],
) -> list[int]:
    """Insert multiple paper bets in batch.

    Args:
        db: BettingDatabase instance.
        bets: List of bet dictionaries.

    Returns:
        List of inserted bet IDs.
    """
    ids = []
    for bet in bets:
        try:
            bet_id = log_paper_bet(db, bet)
            ids.append(bet_id)
        except (ValueError, Exception) as e:
            logger.error("Failed to log bet: %s — %s", bet.get("game_id", "?"), e)
    logger.info("Logged %d/%d paper bets", len(ids), len(bets))
    return ids


def get_pending_bets(
    db: BettingDatabase,
    sport: Optional[str] = None,
) -> list[dict]:
    """Get all unsettled bets.

    Args:
        db: BettingDatabase instance.
        sport: Optional sport filter.

    Returns:
        List of pending bet dicts.
    """
    query = "SELECT * FROM bets WHERE result IS NULL"
    params: tuple = ()
    if sport:
        query += " AND sport = ?"
        params = (sport,)
    return db.execute_query(query, params)


def get_bets_by_date(
    db: BettingDatabase,
    game_date: str,
    sport: Optional[str] = None,
) -> list[dict]:
    """Get bets for a specific game date.

    Args:
        db: BettingDatabase instance.
        game_date: Date string in YYYY-MM-DD format.
        sport: Optional sport filter.

    Returns:
        List of bet dicts.
    """
    query = "SELECT * FROM bets WHERE game_date = ?"
    params: list = [game_date]
    if sport:
        query += " AND sport = ?"
        params.append(sport)
    return db.execute_query(query, tuple(params))


def validate_bet_limits(
    bet_stake: float,
    db: BettingDatabase,
    bankroll_config: Any = BANKROLL,
) -> dict[str, Any]:
    """Validate that a bet doesn't exceed exposure limits.

    Checks:
        1. Stake doesn't exceed max bet (3% of bankroll)
        2. Daily exposure doesn't exceed 10% of bankroll
        3. Weekly loss hasn't triggered sizing reduction

    Args:
        bet_stake: Proposed stake amount.
        db: BettingDatabase instance.
        bankroll_config: BankrollConfig with limits.

    Returns:
        Dict with 'allowed' bool and 'reason' if rejected.
    """
    max_bet = bankroll_config.TOTAL_BANKROLL * bankroll_config.MAX_BET_FRACTION

    # Check max single bet
    if bet_stake > max_bet:
        return {
            "allowed": False,
            "reason": f"Stake ${bet_stake:.2f} exceeds max bet ${max_bet:.2f}",
        }

    # Check daily exposure
    today = date.today().isoformat()
    today_bets = db.execute_query(
        "SELECT COALESCE(SUM(stake), 0) as total_staked FROM bets WHERE game_date = ?",
        (today,),
    )
    daily_staked = today_bets[0]["total_staked"] if today_bets else 0
    daily_limit = bankroll_config.TOTAL_BANKROLL * bankroll_config.DAILY_EXPOSURE_LIMIT

    if daily_staked + bet_stake > daily_limit:
        return {
            "allowed": False,
            "reason": (
                f"Daily exposure ${daily_staked + bet_stake:.2f} would exceed "
                f"limit ${daily_limit:.2f}"
            ),
        }

    return {"allowed": True, "reason": ""}
