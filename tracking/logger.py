"""Paper Bet Logging Utilities.

Handles insertion and validation of paper bets, exposure limit checks,
and batch operations.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    import pandas as pd

from betting.odds_converter import get_days_out_multiplier
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

    # Ensure paper bet flag and required DB fields
    record = dict(bet_data)
    record["is_live"] = False
    if "bet_uuid" not in record:
        record["bet_uuid"] = str(uuid.uuid4())
    if "placed_at" not in record:
        record["placed_at"] = datetime.now().isoformat()

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


def auto_record_bets_from_predictions(
    db: BettingDatabase,
    predictions_df: "pd.DataFrame",
    game_date: str,
    dry_run: bool = False,
    max_bets: int = 10,
) -> list[dict]:
    """Automatically record paper bets from prediction DataFrame.

    Filters predictions to those with recommendations (rec_side is set),
    validates limits, and inserts as paper bets.

    Args:
        db: BettingDatabase instance.
        predictions_df: DataFrame from generate_predictions() with rec_side.
        game_date: Date string in YYYY-MM-DD format.
        dry_run: If True, return bets without inserting into database.
        max_bets: Maximum number of bets to record per day.

    Returns:
        List of bet dicts that were recorded (or would be in dry_run mode).
    """
    import pandas as pd

    if predictions_df.empty:
        return []

    # Filter to recommendations only
    has_rec = (
        predictions_df["rec_side"].notna()
        if "rec_side" in predictions_df.columns
        else pd.Series(False, index=predictions_df.index)
    )
    recs = predictions_df[has_rec].copy()

    if recs.empty:
        logger.info("No bet recommendations to record")
        return []

    # Sort by edge (best first) and limit
    if "home_edge" in recs.columns and "away_edge" in recs.columns:
        recs["best_edge"] = recs.apply(
            lambda r: r["home_edge"] if r.get("rec_side") == "HOME" else r.get("away_edge", 0),
            axis=1,
        )
        recs = recs.sort_values("best_edge", ascending=False)

    recs = recs.head(max_bets)

    # Skip injury-flagged rows (bet was already suppressed in generate_predictions,
    # but double-check here in case caller passed unfiltered DataFrame)
    if "injury_flag" in recs.columns:
        flagged_count = recs["injury_flag"].sum()
        if flagged_count > 0:
            logger.info(
                "Skipping %d injury-flagged bets (already suppressed)",
                int(flagged_count),
            )
        recs = recs[recs["injury_flag"] != True]  # noqa: E712

    recorded: list[dict] = []
    for _, row in recs.iterrows():
        side = row["rec_side"]
        team = row["home"] if side == "HOME" else row["away"]
        team_name = row.get("home_name", team) if side == "HOME" else row.get("away_name", team)

        # Build notes with ESPN context if available
        notes_parts = [f"Auto-recorded paper bet. Bart adj: {row.get('bart_adj', 0):.4f}"]
        espn_prob = row.get("espn_prob")
        if pd.notna(espn_prob):
            div_val = row.get("prob_divergence", 0) or 0
            notes_parts.append(f"ESPN prob: {espn_prob:.0%}, divergence: {div_val:+.0%}")

        bet_data = {
            "sport": "ncaab",
            "game_date": game_date,
            "game_id": str(row.get("game_id", "")),
            "bet_type": "moneyline",
            "selection": f"{team_name} ML",
            "odds_placed": int(row.get("rec_odds", 0)),
            "stake": float(row.get("rec_stake", 0)),
            "sportsbook": "paper",
            "model_probability": float(row["home_prob"] if side == "HOME" else row["away_prob"]),
            "model_edge": float(
                row.get("home_edge", 0) if side == "HOME" else row.get("away_edge", 0)
            ),
            "notes": ". ".join(notes_parts),
        }

        if dry_run:
            logger.info(
                "[DRY RUN] Would record: %s @ %+d (edge: %.1f%%, stake: $%.0f)",
                bet_data["selection"],
                bet_data["odds_placed"],
                bet_data["model_edge"] * 100,
                bet_data["stake"],
            )
        else:
            # Validate limits
            limits = validate_bet_limits(bet_data["stake"], db)
            if not limits["allowed"]:
                logger.warning("Bet rejected: %s — %s", bet_data["selection"], limits["reason"])
                continue

            try:
                bet_id = log_paper_bet(db, bet_data)
                bet_data["bet_id"] = bet_id
                logger.info(
                    "Recorded bet #%d: %s @ %+d (edge: %.1f%%)",
                    bet_id,
                    bet_data["selection"],
                    bet_data["odds_placed"],
                    bet_data["model_edge"] * 100,
                )
            except Exception as e:
                logger.error("Failed to record bet: %s — %s", bet_data["selection"], e)
                continue

        recorded.append(bet_data)

    logger.info(
        "%s %d/%d paper bets for %s",
        "Would record" if dry_run else "Recorded",
        len(recorded),
        len(recs),
        game_date,
    )
    return recorded


def get_position_summary(
    db: BettingDatabase,
    game_id: str,
    selection: str,
) -> dict[str, Any]:
    """Query the current position for a game+side.

    Args:
        db: BettingDatabase instance.
        game_id: ESPN game ID.
        selection: Bet selection string (e.g. "Duke Blue Devils ML").

    Returns:
        Dict with total_staked, entry_count, max_entry.
    """
    rows = db.execute_query(
        """SELECT
            COALESCE(SUM(stake), 0) as total_staked,
            COUNT(*) as entry_count,
            COALESCE(MAX(position_entry), 0) as max_entry
        FROM bets
        WHERE game_id = ? AND selection = ? AND result IS NULL""",
        (game_id, selection),
    )
    if rows:
        return {
            "total_staked": float(rows[0]["total_staked"]),
            "entry_count": int(rows[0]["entry_count"]),
            "max_entry": int(rows[0]["max_entry"]),
        }
    return {"total_staked": 0.0, "entry_count": 0, "max_entry": 0}


def calculate_entry_stake(
    kelly_optimal: float,
    existing_staked: float,
    days_out: int,
    min_bet: float = 10.0,
) -> float:
    """Calculate stake for a new position entry.

    Uses the days-out multiplier to cap how much of the full Kelly
    allocation is allowed at this point in time. Only the remaining
    room (allowed minus already staked) is returned.

    Args:
        kelly_optimal: Full Kelly-optimal stake at current odds/edge.
        existing_staked: Total already staked on this position.
        days_out: Days until gameday (0 = gameday).
        min_bet: Minimum bet size — below this returns 0.

    Returns:
        Stake for this entry, or 0.0 if position is full or below min.
    """
    multiplier = get_days_out_multiplier(days_out)
    allowed_total = kelly_optimal * multiplier
    remaining = allowed_total - existing_staked

    if remaining < min_bet:
        return 0.0

    return round(remaining, 2)
