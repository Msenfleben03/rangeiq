"""Settle Paper Bets After Games Complete.

Loads pending bets, fetches game results from sportsipy, determines
outcomes (win/loss/push), calculates P/L and CLV, updates the database,
and refreshes model ratings.

Usage:
    python scripts/settle_paper_bets.py --date today
    python scripts/settle_paper_bets.py --date 2026-02-15
    python scripts/settle_paper_bets.py --date yesterday
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


from betting.odds_converter import calculate_clv, american_to_decimal
from config.settings import NCAAB_DATABASE_PATH as DATABASE_PATH, ODDS_API_KEY, PROCESSED_DATA_DIR
from config.constants import ODDS_CONFIG
from models.model_persistence import load_model, save_model, ModelMetadata
from pipelines.odds_orchestrator import OddsOrchestrator
from tracking.database import BettingDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_date(date_str: str) -> str:
    """Parse date argument to YYYY-MM-DD string."""
    if date_str.lower() in ("today", "now"):
        return datetime.now().strftime("%Y-%m-%d")
    if date_str.lower() == "yesterday":
        return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return date_str


def fetch_game_results(target_date: datetime) -> dict[str, dict]:
    """Fetch game results for the date.

    Returns:
        Dict mapping game_id -> {home_score, away_score, home_team, away_team}.
    """
    try:
        from pipelines.ncaab_data_fetcher import NCAABDataFetcher

        fetcher = NCAABDataFetcher()
        games = fetcher.fetch_games_by_date(target_date)
        results = {}
        for game in games:
            game_id = game.get("game_id", "")
            if game_id and game.get("home_score") is not None:
                results[game_id] = {
                    "home_team": game.get("home_abbr", game.get("home_team", "")),
                    "away_team": game.get("away_abbr", game.get("away_team", "")),
                    "home_score": int(game["home_score"]),
                    "away_score": int(game["away_score"]),
                }
        logger.info(
            "Fetched %d game results for %s", len(results), target_date.strftime("%Y-%m-%d")
        )
        return results
    except Exception as e:
        logger.error("Failed to fetch results: %s", e)
        return {}


def determine_bet_outcome(
    bet: dict,
    game_result: dict,
) -> tuple[str, float]:
    """Determine if a bet won, lost, or pushed.

    Args:
        bet: Bet record from database.
        game_result: Game result dict with home_score, away_score.

    Returns:
        Tuple of (result_str, profit_loss).
    """
    bet_type = bet["bet_type"]
    selection = bet["selection"]
    odds_placed = bet["odds_placed"]
    stake = bet["stake"]
    line = bet.get("line", 0) or 0

    home_score = game_result["home_score"]
    away_score = game_result["away_score"]
    margin = home_score - away_score

    decimal_odds = american_to_decimal(odds_placed)

    if bet_type == "moneyline":
        if selection == "home":
            won = home_score > away_score
        else:
            won = away_score > home_score

        if home_score == away_score:
            return "push", 0.0
        return ("win", stake * (decimal_odds - 1)) if won else ("loss", -stake)

    elif bet_type == "spread":
        if selection == "home":
            adjusted = margin + line  # line is usually negative for favorites
        else:
            adjusted = -margin + line

        if adjusted > 0:
            return "win", stake * (decimal_odds - 1)
        elif adjusted < 0:
            return "loss", -stake
        else:
            return "push", 0.0

    elif bet_type == "total":
        total_points = home_score + away_score
        if selection == "over":
            diff = total_points - line
        else:
            diff = line - total_points

        if diff > 0:
            return "win", stake * (decimal_odds - 1)
        elif diff < 0:
            return "loss", -stake
        else:
            return "push", 0.0

    logger.warning("Unknown bet type: %s", bet_type)
    return "unknown", 0.0


def settle_bets(
    db: BettingDatabase,
    target_date_str: str,
    orchestrator: OddsOrchestrator,
    model=None,
) -> dict:
    """Settle all pending bets for a date.

    Args:
        db: Database instance.
        target_date_str: Date string YYYY-MM-DD.
        orchestrator: For fetching closing odds.
        model: Optional model to update with results.

    Returns:
        Settlement summary dict.
    """
    # Get pending bets
    pending = db.execute_query(
        "SELECT * FROM bets WHERE result IS NULL AND game_date = ?",
        (target_date_str,),
    )

    if not pending:
        logger.info("No pending bets for %s", target_date_str)
        return {"settled": 0, "skipped": 0}

    # Fetch game results
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    results = fetch_game_results(target_date)

    settled = 0
    skipped = 0
    daily_pnl = 0.0
    daily_clv = []

    for bet in pending:
        game_id = bet["game_id"]

        if game_id not in results:
            logger.info("No result yet for game %s — skipping", game_id)
            skipped += 1
            continue

        game_result = results[game_id]

        # Determine outcome
        result_str, profit_loss = determine_bet_outcome(dict(bet), game_result)

        # Fetch closing odds for CLV
        clv = None
        if bet["odds_placed"]:
            closing = orchestrator.fetch_odds(
                sport="ncaab",
                home=game_result.get("home_team", ""),
                away=game_result.get("away_team", ""),
                game_id=game_id,
                mode="auto",
            )
            if closing is not None:
                closing_odds = (
                    closing.moneyline_home if bet["selection"] == "home" else closing.moneyline_away
                )
                if closing_odds is not None:
                    clv = calculate_clv(bet["odds_placed"], closing_odds)

        # Update bet in database
        db.update_bet_result(
            bet_id=bet["id"],
            result=result_str,
            profit_loss=profit_loss,
            clv=clv,
        )

        daily_pnl += profit_loss
        if clv is not None:
            daily_clv.append(clv)

        logger.info(
            "Settled bet #%d: %s %s @ %d -> %s (P/L: $%.2f, CLV: %s)",
            bet["id"],
            bet["bet_type"],
            bet["selection"],
            bet["odds_placed"],
            result_str,
            profit_loss,
            f"{clv:.3%}" if clv is not None else "N/A",
        )

        # Update model ratings
        if model is not None:
            try:
                model.update_game(
                    home_team=game_result["home_team"],
                    away_team=game_result["away_team"],
                    home_score=game_result["home_score"],
                    away_score=game_result["away_score"],
                )
            except Exception as e:
                logger.debug("Model update skipped: %s", e)

        settled += 1

    # Update bankroll log
    if settled > 0:
        wins = sum(
            1
            for b in pending
            if game_id in results
            and determine_bet_outcome(dict(b), results.get(b["game_id"], {}))[0] == "win"
        )
        avg_clv = sum(daily_clv) / len(daily_clv) if daily_clv else 0

        try:
            db.insert_bankroll_entry(
                {
                    "date": target_date_str,
                    "daily_pnl": daily_pnl,
                    "bets_placed": len(pending),
                    "bets_won": wins,
                    "bets_lost": settled - wins,
                    "avg_clv": avg_clv,
                }
            )
        except Exception as e:
            logger.debug("Bankroll log update skipped: %s", e)

    return {
        "settled": settled,
        "skipped": skipped,
        "daily_pnl": daily_pnl,
        "avg_clv": sum(daily_clv) / len(daily_clv) if daily_clv else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Settle paper bets")
    parser.add_argument("--date", type=str, default="today")
    args = parser.parse_args()

    target_date_str = parse_date(args.date)
    db = BettingDatabase(str(DATABASE_PATH))

    # Set up orchestrator for closing odds
    orchestrator = OddsOrchestrator(
        db=db,
        cache_ttl=ODDS_CONFIG.CACHE_TTL_SECONDS,
        monthly_credit_limit=ODDS_CONFIG.API_CREDIT_MONTHLY_LIMIT,
    )
    orchestrator.register_default_providers(api_key=ODDS_API_KEY)

    # Load model for rating updates
    model = None
    model_path = PROCESSED_DATA_DIR / "ncaab_elo_model.pkl"
    if model_path.exists():
        saved = load_model(model_path)
        model = saved.model

    # Settle
    summary = settle_bets(db, target_date_str, orchestrator, model)

    # Save updated model
    if model is not None and summary["settled"] > 0:
        save_model(
            model,
            model_path,
            ModelMetadata(
                model_name="ncaab_elo_v1",
                sport="ncaab",
                notes=f"Updated after settling {summary['settled']} bets on {target_date_str}",
            ),
        )

    print(f"\n{'=' * 60}")
    print(f"SETTLEMENT SUMMARY — {target_date_str}")
    print(f"{'=' * 60}")
    print(f"Settled:    {summary['settled']}")
    print(f"Skipped:    {summary['skipped']}")
    print(f"Daily P/L:  ${summary.get('daily_pnl', 0):+.2f}")
    print(f"Avg CLV:    {summary.get('avg_clv', 0):.3%}")


if __name__ == "__main__":
    main()
