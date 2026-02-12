#!/usr/bin/env python3
"""Arbitrage Scanner Pipeline.

Lightweight script to scan for arbitrage opportunities.
Can be run standalone or integrated with existing pipelines.

Usage:
    python -m pipelines.arb_scanner              # Scan all upcoming games
    python -m pipelines.arb_scanner --sport NCAAB  # Filter by sport
    python -m pipelines.arb_scanner --json        # Output as JSON

Integration:
    Call scan_for_arbs() from your existing pipeline code to
    opportunistically check for arbs on games being modeled.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from betting.arb_detector import ArbDetector, ArbOpportunity  # noqa: E402


def scan_for_arbs(
    sport: Optional[str] = None,
    hours_ahead: int = 24,
    min_profit: float = 0.01,
    db_path: str = "data/betting.db",
    log_to_db: bool = True,
) -> list[ArbOpportunity]:
    """Scan for arbitrage opportunities.

    This is the main integration point. Call this from your
    existing pipelines to opportunistically detect arbs.

    Args:
        sport: Filter by sport code (NCAAB, MLB, NFL, etc.)
        hours_ahead: Hours to look ahead for games
        min_profit: Minimum profit percentage to report
        db_path: Path to database
        log_to_db: Whether to log found arbs to database

    Returns:
        List of ArbOpportunity objects

    Example:
        # In your existing NCAAB pipeline:
        from pipelines.arb_scanner import scan_for_arbs

        # After fetching odds...
        arbs = scan_for_arbs(sport="NCAAB", min_profit=0.02)
        if arbs:
            notify_arb_found(arbs)  # Your notification logic
    """
    detector = ArbDetector(db_path=db_path)
    detector.MIN_PROFIT_PCT = min_profit

    opportunities = detector.scan_current_games(sport=sport, hours_ahead=hours_ahead)

    if log_to_db and opportunities:
        for arb in opportunities:
            detector.log_opportunity(arb)

    return opportunities


def scan_single_game(
    game_id: str, db_path: str = "data/betting.db", min_profit: float = 0.01
) -> list[ArbOpportunity]:
    """Scan a single game for arbitrage.

    Use this when you're already processing a specific game
    in your model pipeline.

    Args:
        game_id: Game identifier
        db_path: Path to database
        min_profit: Minimum profit threshold

    Returns:
        List of ArbOpportunity objects for this game
    """
    detector = ArbDetector(db_path=db_path)
    detector.MIN_PROFIT_PCT = min_profit
    return detector.scan_game(game_id)


def format_arb_alert(arb: ArbOpportunity) -> str:
    """Format arbitrage opportunity as alert message.

    Args:
        arb: ArbOpportunity object

    Returns:
        Formatted alert string
    """
    lines = [
        f"🎯 ARB ALERT: {arb.arb_type.upper()}",
        f"Game: {arb.game_id}",
        f"Profit: {arb.profit_pct:.2%} (${arb.profit_pct * 100:.2f} per $100)",
        "",
        f"Leg 1: {arb.selection1} @ {arb.book1}",
        f"        Odds: {arb.odds1:+d} | Stake: ${arb.stake1:.2f}",
        "",
        f"Leg 2: {arb.selection2} @ {arb.book2}",
        f"        Odds: {arb.odds2:+d} | Stake: ${arb.stake2:.2f}",
    ]

    if arb.game_time:
        lines.append("")
        lines.append(f"Game Time: {arb.game_time.strftime('%Y-%m-%d %H:%M')}")

    return "\n".join(lines)


# =============================================================================
# CLI INTERFACE
# =============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Scan for arbitrage opportunities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m pipelines.arb_scanner
  python -m pipelines.arb_scanner --sport NCAAB --hours 12
  python -m pipelines.arb_scanner --min-profit 0.02 --json
        """,
    )

    parser.add_argument(
        "--sport", type=str, choices=["NCAAB", "MLB", "NFL", "NCAAF"], help="Filter by sport"
    )
    parser.add_argument("--hours", type=int, default=24, help="Hours ahead to scan (default: 24)")
    parser.add_argument(
        "--min-profit", type=float, default=0.01, help="Minimum profit %% (default: 0.01 = 1%%)"
    )
    parser.add_argument("--db", type=str, default="data/betting.db", help="Database path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--no-log", action="store_true", help="Don't log opportunities to database")

    args = parser.parse_args()

    opportunities = scan_for_arbs(
        sport=args.sport,
        hours_ahead=args.hours,
        min_profit=args.min_profit,
        db_path=args.db,
        log_to_db=not args.no_log,
    )

    if args.json:
        output = {
            "scan_time": datetime.now().isoformat(),
            "sport_filter": args.sport,
            "hours_ahead": args.hours,
            "min_profit_pct": args.min_profit,
            "count": len(opportunities),
            "opportunities": [arb.to_dict() for arb in opportunities],
        }
        print(json.dumps(output, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"ARB SCANNER | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*60}")
        print(f"Sport: {args.sport or 'ALL'} | Window: {args.hours}h | Min: {args.min_profit:.1%}")
        print(f"{'='*60}\n")

        if not opportunities:
            print("No arbitrage opportunities found.\n")
        else:
            print(f"Found {len(opportunities)} opportunities:\n")
            for arb in opportunities:
                print(format_arb_alert(arb))
                print(f"\n{'-'*40}\n")


if __name__ == "__main__":
    main()
