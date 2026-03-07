"""Generate Performance Reports.

CLI for daily, weekly, CLV, and system health reports.

Usage:
    python scripts/generate_report.py --daily
    python scripts/generate_report.py --weekly
    python scripts/generate_report.py --clv
    python scripts/generate_report.py --health
    python scripts/generate_report.py --odds-health
    python scripts/generate_report.py --all
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import NCAAB_DATABASE_PATH as DATABASE_PATH
from tracking.database import BettingDatabase
from tracking.reports import (
    clv_analysis,
    daily_report,
    model_health_check,
    odds_system_health,
    weekly_report,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def print_daily(db: BettingDatabase, report_date: str | None = None) -> None:
    """Print daily report."""
    report = daily_report(db, report_date)
    print(f"\n{'=' * 60}")
    print(f"DAILY REPORT — {report['date']}")
    print(f"{'=' * 60}")
    print(
        f"Total bets:  {report['total_bets']}  (settled: {report['settled']}, pending: {report['pending']})"
    )
    print(f"Record:      {report['wins']}W - {report['losses']}L - {report['pushes']}P")
    print(f"Win rate:    {report['win_rate']:.1%}")
    print(f"P/L:         ${report['total_pnl']:+.2f}")
    print(f"ROI:         {report['roi']:.2%}")
    print(f"Avg CLV:     {report['avg_clv']:.3%}")


def print_weekly(db: BettingDatabase, weeks: int = 1) -> None:
    """Print weekly report."""
    report = weekly_report(db, weeks)
    print(f"\n{'=' * 60}")
    print(f"WEEKLY REPORT — {report['period']}")
    print(f"{'=' * 60}")
    if report["total_bets"] == 0:
        print("No bets in this period.")
        return
    print(f"Total bets:   {report['total_bets']}")
    print(f"Record:       {report['wins']}W - {report['losses']}L")
    print(f"Win rate:     {report['win_rate']:.1%}")
    print(f"P/L:          ${report['total_pnl']:+.2f}")
    print(f"ROI:          {report['roi']:.2%}")
    print(f"Avg CLV:      {report['avg_clv']:.3%}")
    print(f"Sharpe ratio: {report['sharpe_ratio']:.2f}")
    print(f"Betting days: {report['betting_days']}")


def print_clv(db: BettingDatabase, days: int = 30) -> None:
    """Print CLV analysis."""
    report = clv_analysis(db, days)
    print(f"\n{'=' * 60}")
    print(f"CLV ANALYSIS — Last {report['period_days']} days")
    print(f"{'=' * 60}")
    if report["bets_with_clv"] == 0:
        print("No bets with CLV data.")
        return
    print(f"Bets with CLV:   {report['bets_with_clv']}")
    print(f"Average CLV:     {report['avg_clv']:.3%}")
    print(f"Median CLV:      {report['median_clv']:.3%}")
    print(f"Positive CLV %:  {report['positive_clv_pct']:.1%}")
    print(f"Avg +CLV:        {report['avg_positive_clv']:.3%}")
    print(f"Avg -CLV:        {report['avg_negative_clv']:.3%}")

    if report.get("clv_by_bet_type"):
        print("\nCLV by bet type:")
        for bt, avg in report["clv_by_bet_type"].items():
            print(f"  {bt}: {avg:.3%}")


def print_health(db: BettingDatabase) -> None:
    """Print model health check."""
    report = model_health_check(db)
    print(f"\n{'=' * 60}")
    print(f"MODEL HEALTH: {report['status']}")
    print(f"{'=' * 60}")

    if report["alerts"]:
        for alert in report["alerts"]:
            print(f"  [{alert['level']}] {alert['message']}")
            print(f"     Action: {alert['action']}")
    else:
        print("  No alerts. Model is healthy.")


def print_odds_health(db: BettingDatabase) -> None:
    """Print odds system health."""
    report = odds_system_health(db)
    print(f"\n{'=' * 60}")
    print("ODDS SYSTEM HEALTH")
    print(f"{'=' * 60}")
    print(f"Total snapshots: {report['total_snapshots']}")
    print(f"Stale (24h+):    {report['stale_snapshots']}")

    if report["providers"]:
        print("\nProviders:")
        for name, info in report["providers"].items():
            print(f"  {name}: {info['count']} snapshots (last: {info['last_capture']})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate performance reports")
    parser.add_argument("--daily", action="store_true")
    parser.add_argument("--weekly", action="store_true")
    parser.add_argument("--clv", action="store_true")
    parser.add_argument("--health", action="store_true")
    parser.add_argument("--odds-health", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--weeks", type=int, default=1)
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    db = BettingDatabase(str(DATABASE_PATH))

    run_any = args.daily or args.weekly or args.clv or args.health or args.odds_health or args.all

    if not run_any:
        # Default: show daily
        print_daily(db, args.date)
        return

    if args.daily or args.all:
        print_daily(db, args.date)
    if args.weekly or args.all:
        print_weekly(db, args.weeks)
    if args.clv or args.all:
        print_clv(db, args.days)
    if args.health or args.all:
        print_health(db)
    if args.odds_health or args.all:
        print_odds_health(db)


if __name__ == "__main__":
    main()
