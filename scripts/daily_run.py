"""Daily Paper Betting Orchestrator.

End-to-end pipeline: fetch games -> predict -> record bets -> settle -> report.

Usage:
    python scripts/daily_run.py                    # Full run
    python scripts/daily_run.py --dry-run          # Preview without recording
    python scripts/daily_run.py --settle-only      # Only settle yesterday's bets
    python scripts/daily_run.py --report-only      # Only generate weekly report
    python scripts/daily_run.py --date 2026-02-15  # Specific date
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from betting.odds_converter import american_to_decimal, calculate_clv
from config.constants import BREADWINNER, INJURY_CHECK, ODDS_CONFIG, PAPER_BETTING
from config.settings import DATABASE_PATH, ODDS_API_KEY, PROCESSED_DATA_DIR
from features.sport_specific.ncaab.breadwinner import build_breadwinner_lookup
from models.model_persistence import load_model
from pipelines.barttorvik_fetcher import BarttovikFetcher, load_cached_season
from pipelines.espn_core_odds_provider import ESPNCoreOddsFetcher, OddsSnapshot
from pipelines.injury_checker import fetch_game_context
from pipelines.kenpom_fetcher import KenPomFetcher, load_cached_season as load_kenpom_cached
from pipelines.odds_orchestrator import OddsOrchestrator
from pipelines.player_stats_fetcher import load_cached_players
from scripts.backtest_ncaab_elo import BarttovikCoeffs, KenPomCoeffs
from scripts.daily_predictions import (
    display_predictions,
    fetch_espn_scoreboard,
    generate_predictions,
)
from tracking.database import BettingDatabase
from tracking.logger import auto_record_bets_from_predictions
from tracking.reports import daily_report, model_health_check, weekly_report

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _get_closing_ml_for_bet(
    selection: str,
    game: dict,
    snapshot: OddsSnapshot,
) -> int | None:
    """Determine the correct closing moneyline for a bet's side.

    Args:
        selection: Bet selection string (e.g. "Duke Blue Devils ML").
        game: Game dict from ESPN scoreboard.
        snapshot: OddsSnapshot with closing odds.

    Returns:
        Closing moneyline integer, or None if side can't be determined.
    """
    home_abbr = game.get("home", "")
    away_abbr = game.get("away", "")
    home_name = game.get("home_name", "")
    away_name = game.get("away_name", "")

    is_home = "HOME" in selection.upper() or home_abbr in selection or home_name in selection
    is_away = "AWAY" in selection.upper() or away_abbr in selection or away_name in selection

    if is_home and snapshot.home_ml_close is not None:
        return snapshot.home_ml_close
    if is_away and snapshot.away_ml_close is not None:
        return snapshot.away_ml_close

    # Fallback: try current ML if close not available
    if is_home and snapshot.home_moneyline is not None:
        return snapshot.home_moneyline
    if is_away and snapshot.away_moneyline is not None:
        return snapshot.away_moneyline

    return None


def _store_closing_snapshot(db: BettingDatabase, snapshot: OddsSnapshot) -> None:
    """Store a closing odds snapshot to odds_snapshots table.

    Args:
        db: BettingDatabase instance.
        snapshot: OddsSnapshot with closing data from ESPN Core API.
    """
    from datetime import timezone

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
            snapshot.home_spread_close or snapshot.spread,
            snapshot.home_spread_odds_close or snapshot.home_spread_odds,
            snapshot.away_spread_odds_close or snapshot.away_spread_odds,
            snapshot.total_close or snapshot.over_under,
            snapshot.over_odds_close or snapshot.over_odds,
            snapshot.under_odds_close or snapshot.under_odds,
            snapshot.home_ml_close or snapshot.home_moneyline,
            snapshot.away_ml_close or snapshot.away_moneyline,
            True,  # is_closing
            0.92,  # confidence (ESPN Core API)
            "closing",
        ),
    )


def settle_yesterdays_bets(db: BettingDatabase, settle_date: str | None = None) -> dict:
    """Settle paper bets from a past date using ESPN final scores.

    After settling win/loss, fetches closing odds from ESPN Core API
    and calculates CLV for each bet.

    Args:
        db: BettingDatabase instance.
        settle_date: Date to settle (YYYY-MM-DD). Default: yesterday.

    Returns:
        Dict with settlement and CLV stats.
    """
    if settle_date is None:
        settle_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Get pending bets for the date
    pending = db.execute_query(
        "SELECT * FROM bets WHERE game_date = ? AND result IS NULL AND is_live = 0",
        (settle_date,),
    )

    if not pending:
        logger.info("No pending bets to settle for %s", settle_date)
        return {"date": settle_date, "settled": 0, "pending": 0}

    # Fetch final scores from ESPN
    settle_dt = datetime.strptime(settle_date, "%Y-%m-%d")
    games = fetch_espn_scoreboard(settle_dt)
    final_games = {
        g["game_id"]: g for g in games if g["status"] in ("STATUS_FINAL", "STATUS_FINAL_OT")
    }

    # -- Pass 1: Settle win/loss -------------------------------------------------
    settled_count = 0
    settled_game_ids: set[str] = set()

    for bet in pending:
        game_id = bet["game_id"] or ""
        if game_id not in final_games:
            logger.debug("Game %s not final yet, skipping", game_id)
            continue

        game = final_games[game_id]
        home_score = game["home_score"]
        away_score = game["away_score"]

        # Determine result based on selection
        selection = bet["selection"] or ""
        bet_type = bet["bet_type"] or ""

        if bet_type == "moneyline":
            # Parse which team was bet on
            home_abbr = game["home"]
            away_abbr = game["away"]

            # Check if bet was on home or away
            if "HOME" in selection.upper() or home_abbr in selection:
                won = home_score > away_score
            elif "AWAY" in selection.upper() or away_abbr in selection:
                won = away_score > home_score
            else:
                # Try matching by team name
                if game["home_name"] in selection:
                    won = home_score > away_score
                elif game["away_name"] in selection:
                    won = away_score > home_score
                else:
                    logger.warning("Cannot determine result for bet: %s", selection)
                    continue

            result = "win" if won else "loss"
            odds_placed = bet["odds_placed"] or -110
            stake = bet["stake"] or 0

            if won and odds_placed != 0:
                decimal_odds = american_to_decimal(odds_placed)
                profit = stake * (decimal_odds - 1)
            else:
                profit = -stake

            # Update bet in database
            try:
                db.execute_query(
                    """UPDATE bets
                       SET result = ?, profit_loss = ?
                       WHERE id = ?""",
                    (result, profit, bet["id"]),
                )
                settled_count += 1
                settled_game_ids.add(game_id)
                logger.info(
                    "Settled bet #%d: %s -> %s ($%+.2f)",
                    bet["id"],
                    selection,
                    result,
                    profit,
                )
            except Exception as e:
                logger.error("Failed to settle bet #%d: %s", bet["id"], e)

    # -- Pass 2: Fetch closing odds and calculate CLV ----------------------------
    clv_updated = 0
    clv_failed = 0
    clv_values: list[float] = []

    if settled_game_ids:
        closing_odds: dict[str, OddsSnapshot] = {}
        fetcher = ESPNCoreOddsFetcher(sport="ncaab")
        try:
            for game_id in settled_game_ids:
                try:
                    snapshots = fetcher.fetch_game_odds(game_id)
                    if snapshots:
                        pre_game = [s for s in snapshots if s.provider_id != 59]
                        best = pre_game[0] if pre_game else snapshots[0]
                        closing_odds[game_id] = best

                        # Store closing snapshot
                        _store_closing_snapshot(db, best)
                    else:
                        logger.warning("No closing odds for game %s", game_id)
                except Exception as e:
                    logger.error("Failed to fetch closing odds for %s: %s", game_id, e)
        finally:
            fetcher.close()

        # Calculate CLV for each settled bet
        for bet in pending:
            game_id = bet["game_id"] or ""
            if game_id not in closing_odds:
                if game_id in settled_game_ids:
                    clv_failed += 1
                continue

            odds_placed = bet["odds_placed"]
            if not odds_placed:
                continue

            selection = bet["selection"] or ""
            game = final_games.get(game_id, {})
            snapshot = closing_odds[game_id]

            # Determine which closing ML to use based on bet side
            closing_ml = _get_closing_ml_for_bet(selection, game, snapshot)
            if closing_ml is None:
                clv_failed += 1
                continue

            try:
                clv = calculate_clv(odds_placed, closing_ml)
                db.execute_query(
                    """UPDATE bets
                       SET odds_closing = ?, clv = ?
                       WHERE id = ?""",
                    (closing_ml, clv, bet["id"]),
                )
                clv_updated += 1
                clv_values.append(clv)
                logger.info(
                    "CLV bet #%d: placed %+d, closed %+d, CLV %+.2f%%",
                    bet["id"],
                    odds_placed,
                    closing_ml,
                    clv * 100,
                )
            except Exception as e:
                logger.error("Failed to update CLV for bet #%d: %s", bet["id"], e)
                clv_failed += 1

    avg_clv = sum(clv_values) / len(clv_values) if clv_values else 0.0

    return {
        "date": settle_date,
        "settled": settled_count,
        "pending": len(pending) - settled_count,
        "total_pending": len(pending),
        "clv_updated": clv_updated,
        "clv_failed": clv_failed,
        "avg_clv": avg_clv,
    }


def run_predictions(
    target_date: datetime,
    db: BettingDatabase,
    dry_run: bool = False,
) -> pd.DataFrame:
    """Run the full prediction pipeline for a date.

    Args:
        target_date: Date to generate predictions for.
        db: BettingDatabase instance.
        dry_run: If True, preview bets without recording.

    Returns:
        DataFrame of predictions.
    """
    # Load model
    model_path = PROCESSED_DATA_DIR / "ncaab_elo_model.pkl"
    if not model_path.exists():
        logger.error("No trained model. Run train_ncaab_elo.py first.")
        return pd.DataFrame()

    saved = load_model(model_path)
    model = saved.model
    logger.info("Model loaded: %d teams", len(model.ratings))

    # Fetch games
    games = fetch_espn_scoreboard(target_date)
    if not games:
        logger.warning("No games found for %s", target_date.strftime("%Y-%m-%d"))
        return pd.DataFrame()

    # Filter to pre-game
    pre_game = [g for g in games if g["status"] in ("STATUS_SCHEDULED", "STATUS_PREGAME", "")]
    logger.info("%d pre-game / %d total games", len(pre_game), len(games))

    if not pre_game:
        logger.info("All games already started/completed")
        pre_game = games  # Show all for informational purposes

    # Set up odds orchestrator
    orchestrator = OddsOrchestrator(
        db=db,
        cache_ttl=ODDS_CONFIG.CACHE_TTL_SECONDS,
        monthly_credit_limit=ODDS_CONFIG.API_CREDIT_MONTHLY_LIMIT,
    )
    try:
        orchestrator.register_default_providers(api_key=ODDS_API_KEY)
    except Exception as e:
        logger.warning("Odds orchestrator setup failed: %s (predictions will lack odds)", e)
        orchestrator = None

    # Load Barttorvik data
    season = target_date.year if target_date.month >= 10 else target_date.year
    barttorvik_df = load_cached_season(season)
    bart_coeffs = BarttovikCoeffs(
        net_diff_coeff=PAPER_BETTING.BARTTORVIK_NET_DIFF_COEFF,
        barthag_diff_coeff=PAPER_BETTING.BARTTORVIK_BARTHAG_DIFF_COEFF,
    )

    # Load breadwinner data (uses cached player stats + Barttorvik for quality filter)
    bw_lookup = None
    if barttorvik_df is not None and BREADWINNER.BREADWINNER_COEFF > 0:
        player_df = load_cached_players(season)
        if player_df is None:
            # Try previous season as fallback (2026 player data not available)
            player_df = load_cached_players(season - 1)
        if player_df is not None and not player_df.empty:
            bw_lookup = build_breadwinner_lookup(
                player_df,
                barttorvik_df,
                rotation_size=BREADWINNER.ROTATION_SIZE,
                quality_cutoff=BREADWINNER.QUALITY_RANK_CUTOFF,
            )
            logger.info(
                "Breadwinner lookup: %d teams (%d eligible)",
                len(bw_lookup),
                sum(1 for s in bw_lookup.values() if s.eligible),
            )

    # Load KenPom data
    from config.constants import KENPOM

    kenpom_df = load_kenpom_cached(season)
    kenpom_coeffs = KenPomCoeffs(
        net_diff_coeff=KENPOM.KENPOM_NET_DIFF_COEFF,
        sos_coeff=KENPOM.KENPOM_SOS_COEFF,
    )
    use_kenpom = kenpom_df is not None and KENPOM.KENPOM_WEIGHT > 0
    if kenpom_df is not None:
        logger.info("KenPom data: %d rows for season %d", len(kenpom_df), season)

    # Fetch ESPN game context for injury/divergence detection
    game_ctx = None
    if INJURY_CHECK.ENABLED:
        game_ids = [g["game_id"] for g in pre_game]
        logger.info("Fetching ESPN game context for %d games...", len(game_ids))
        game_ctx = fetch_game_context(game_ids)
        ctx_with_predictor = sum(1 for c in game_ctx.values() if c.espn_home_prob is not None)
        logger.info(
            "ESPN predictor available for %d/%d games",
            ctx_with_predictor,
            len(game_ids),
        )

    # Generate predictions
    predictions = generate_predictions(
        model=model,
        games=pre_game,
        orchestrator=orchestrator,
        min_edge=PAPER_BETTING.MIN_EDGE,
        use_barttorvik=barttorvik_df is not None,
        barttorvik_df=barttorvik_df,
        bart_coeffs=bart_coeffs,
        barttorvik_weight=PAPER_BETTING.BARTTORVIK_WEIGHT,
        use_kenpom=use_kenpom,
        kenpom_df=kenpom_df,
        kenpom_coeffs=kenpom_coeffs,
        kenpom_weight=KENPOM.KENPOM_WEIGHT,
        breadwinner_lookup=bw_lookup,
        breadwinner_coeff=BREADWINNER.BREADWINNER_COEFF,
        breadwinner_variant=BREADWINNER.BREADWINNER_VARIANT,
        breadwinner_include_centers=BREADWINNER.INCLUDE_CENTERS,
        target_date=target_date,
        game_context=game_ctx,
    )

    # Record paper bets
    game_date_str = target_date.strftime("%Y-%m-%d")
    recorded = auto_record_bets_from_predictions(
        db=db,
        predictions_df=predictions,
        game_date=game_date_str,
        dry_run=dry_run,
        max_bets=PAPER_BETTING.MAX_BETS_PER_DAY,
    )

    # Display
    display_predictions(predictions)

    if recorded:
        print(f"\n{'=' * 60}")
        print(f"{'[DRY RUN] ' if dry_run else ''}PAPER BETS RECORDED: {len(recorded)}")
        print(f"{'=' * 60}")
        total_stake = sum(b["stake"] for b in recorded)
        print(f"Total stake: ${total_stake:.2f}")

    return predictions


def generate_report(db: BettingDatabase) -> None:
    """Generate and display the weekly paper betting report."""
    print(f"\n{'=' * 70}")
    print("WEEKLY PAPER BETTING REPORT")
    print(f"{'=' * 70}")

    # Weekly summary
    report = weekly_report(db, weeks=1)
    if report.get("total_bets", 0) == 0:
        print("No bets in the last 7 days.")
        return

    print(f"\nPeriod:      {report['period']}")
    print(f"Total bets:  {report['total_bets']}")
    print(f"Record:      {report['wins']}-{report['losses']}")
    print(f"Win rate:    {report['win_rate']:.1%}")
    print(f"Total P/L:   ${report['total_pnl']:+.2f}")
    print(f"ROI:         {report['roi']:.2%}")
    print(f"Avg CLV:     {report['avg_clv']:.3%}")
    print(f"Sharpe:      {report['sharpe_ratio']:.2f}")
    print(f"Betting days: {report['betting_days']}")

    # Model health
    health = model_health_check(db)
    print(f"\nModel health: {health['status']}")
    for alert in health.get("alerts", []):
        print(f"  [{alert['level']}] {alert['message']}")
        print(f"    Action: {alert['action']}")

    # Daily breakdown
    print(f"\n{'Date':<12} {'Bets':>5} {'W':>3} {'L':>3} {'P/L':>8} {'ROI':>7}")
    print("-" * 45)

    for i in range(7):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        day_report = daily_report(db, d)
        if day_report["total_bets"] > 0:
            print(
                f"{d:<12} {day_report['total_bets']:>5} "
                f"{day_report['wins']:>3} {day_report['losses']:>3} "
                f"${day_report['total_pnl']:>+7.2f} "
                f"{day_report['roi']:>6.1%}"
            )


def _fetch_daily_snapshots(target_date: datetime) -> None:
    """Fetch Barttorvik + KenPom daily snapshots and append to cache."""
    import os

    from config.settings import CBBDATA_API_KEY, KENPOM_EMAIL, KENPOM_PASSWORD

    season = target_date.year if target_date.month >= 10 else target_date.year

    # Barttorvik
    api_key = CBBDATA_API_KEY or os.environ.get("CBBDATA_API_KEY", "")
    if api_key:
        try:
            fetcher = BarttovikFetcher(api_key=api_key)
            df = fetcher.fetch_daily_snapshot(season)
            fetcher.close()
            if not df.empty:
                logger.info("Barttorvik snapshot: %d teams", len(df))
            else:
                logger.warning("Barttorvik snapshot empty")
        except Exception as exc:
            logger.error("Barttorvik snapshot failed: %s", exc)
    else:
        logger.warning("Barttorvik skipped: no CBBDATA_API_KEY")

    # KenPom
    email = KENPOM_EMAIL or os.environ.get("KENPOM_EMAIL", "")
    password = KENPOM_PASSWORD or os.environ.get("KENPOM_PASSWORD", "")
    if email and password:
        try:
            kp_fetcher = KenPomFetcher(email=email, password=password)
            df = kp_fetcher.fetch_current_snapshot()
            if not df.empty:
                logger.info("KenPom snapshot: %d teams", len(df))
            else:
                logger.warning("KenPom snapshot empty")
        except Exception as exc:
            logger.error("KenPom snapshot failed: %s", exc)
    else:
        logger.warning("KenPom skipped: no credentials")


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily paper betting orchestrator")
    parser.add_argument("--date", type=str, default="today")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview bets without recording to database",
    )
    parser.add_argument(
        "--settle-only",
        action="store_true",
        help="Only settle yesterday's bets (skip predictions)",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Only generate weekly report",
    )
    parser.add_argument(
        "--settle-date",
        type=str,
        default=None,
        help="Specific date to settle (YYYY-MM-DD, default: yesterday)",
    )
    parser.add_argument(
        "--skip-settle",
        action="store_true",
        help="Skip settling yesterday's bets",
    )
    parser.add_argument(
        "--fetch-snapshots",
        action="store_true",
        help="Fetch daily Barttorvik + KenPom snapshots before predicting",
    )
    args = parser.parse_args()

    db = BettingDatabase(str(DATABASE_PATH))

    # Parse target date
    if args.date.lower() in ("today", "now"):
        target_date = datetime.now()
    elif args.date.lower() == "tomorrow":
        target_date = datetime.now() + timedelta(days=1)
    else:
        target_date = datetime.strptime(args.date, "%Y-%m-%d")

    print(f"Daily Run — {target_date.strftime('%Y-%m-%d')}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE PAPER'}")

    # Report only
    if args.report_only:
        generate_report(db)
        return

    # Settle only
    if args.settle_only:
        result = settle_yesterdays_bets(db, args.settle_date)
        print(f"\nSettlement: {result['settled']} settled, {result['pending']} still pending")
        if result.get("clv_updated", 0) > 0:
            print(f"CLV: {result['clv_updated']} updated, avg CLV: {result['avg_clv']:+.2%}")
        if result.get("clv_failed", 0) > 0:
            print(f"CLV failed: {result['clv_failed']} (no closing odds)")
        return

    # Full pipeline
    # Step 0: Fetch daily rating snapshots (if requested)
    if args.fetch_snapshots:
        print("\n--- Fetching daily rating snapshots ---")
        _fetch_daily_snapshots(target_date)

    # Step 1: Settle yesterday's bets
    if not args.skip_settle:
        print("\n--- Settling yesterday's bets ---")
        settle_result = settle_yesterdays_bets(db, args.settle_date)
        print(f"Settled: {settle_result['settled']}, Pending: {settle_result['pending']}")
        if settle_result.get("clv_updated", 0) > 0:
            print(
                f"CLV: {settle_result['clv_updated']} updated, "
                f"avg CLV: {settle_result['avg_clv']:+.2%}"
            )
        if settle_result.get("clv_failed", 0) > 0:
            print(f"CLV failed: {settle_result['clv_failed']} (no closing odds)")

    # Step 2: Generate today's predictions and record bets
    print("\n--- Generating today's predictions ---")
    _predictions = run_predictions(target_date, db, dry_run=args.dry_run)

    if _predictions.empty and not args.dry_run:
        logger.error("No predictions generated for %s", target_date.strftime("%Y-%m-%d"))
        sys.exit(1)

    # Step 3: Quick report
    print("\n--- Quick daily summary ---")
    today_str = target_date.strftime("%Y-%m-%d")
    today_report = daily_report(db, today_str)
    if today_report["total_bets"] > 0:
        print(f"Today's bets: {today_report['total_bets']}")
        print(f"  Settled: {today_report['settled']}")
        print(f"  Pending: {today_report['pending']}")
        if today_report["settled"] > 0:
            print(f"  P/L: ${today_report['total_pnl']:+.2f}")
    else:
        print("No bets recorded for today yet.")


if __name__ == "__main__":
    main()
