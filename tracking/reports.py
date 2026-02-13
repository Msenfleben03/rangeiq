"""Performance Reports & Monitoring.

Generates daily, weekly, CLV analysis, model health checks, and
odds system health reports from the betting database.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from tracking.database import BettingDatabase

logger = logging.getLogger(__name__)


def daily_report(db: BettingDatabase, report_date: str | None = None) -> dict[str, Any]:
    """Generate a daily performance report.

    Args:
        db: BettingDatabase instance.
        report_date: Date in YYYY-MM-DD format (default: today).

    Returns:
        Dict with daily metrics.
    """
    if report_date is None:
        report_date = date.today().isoformat()

    bets = db.execute_query("SELECT * FROM bets WHERE game_date = ?", (report_date,))

    settled = [b for b in bets if b["result"] is not None]
    pending = [b for b in bets if b["result"] is None]

    total_pnl = sum(b["profit_loss"] for b in settled if b["profit_loss"] is not None)
    total_staked = sum(b["stake"] for b in settled if b["stake"] is not None)
    wins = sum(1 for b in settled if b["result"] == "win")
    losses = sum(1 for b in settled if b["result"] == "loss")
    pushes = sum(1 for b in settled if b["result"] == "push")

    clv_values = [b["clv"] for b in settled if b["clv"] is not None]
    avg_clv = sum(clv_values) / len(clv_values) if clv_values else 0.0

    return {
        "date": report_date,
        "total_bets": len(bets),
        "settled": len(settled),
        "pending": len(pending),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_rate": wins / len(settled) if settled else 0.0,
        "total_pnl": total_pnl,
        "total_staked": total_staked,
        "roi": total_pnl / total_staked if total_staked > 0 else 0.0,
        "avg_clv": avg_clv,
    }


def weekly_report(db: BettingDatabase, weeks: int = 1) -> dict[str, Any]:
    """Generate a rolling weekly performance report.

    Args:
        db: BettingDatabase instance.
        weeks: Number of weeks to include.

    Returns:
        Dict with weekly metrics including CLV trend and Sharpe.
    """
    days = weeks * 7
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    bets = db.execute_query(
        "SELECT * FROM bets WHERE game_date >= ? AND game_date <= ? AND result IS NOT NULL",
        (start_date.isoformat(), end_date.isoformat()),
    )

    if not bets:
        return {"period": f"{start_date} to {end_date}", "total_bets": 0}

    total_pnl = sum(b["profit_loss"] for b in bets if b["profit_loss"] is not None)
    total_staked = sum(b["stake"] for b in bets if b["stake"] is not None)
    wins = sum(1 for b in bets if b["result"] == "win")
    clv_values = [b["clv"] for b in bets if b["clv"] is not None]

    # Daily P/L for Sharpe calculation
    daily_pnl: dict[str, float] = {}
    for b in bets:
        d = str(b["game_date"])
        daily_pnl.setdefault(d, 0.0)
        if b["profit_loss"] is not None:
            daily_pnl[d] += b["profit_loss"]

    pnl_values = list(daily_pnl.values())
    if len(pnl_values) > 1:
        import math

        mean_pnl = sum(pnl_values) / len(pnl_values)
        std_pnl = math.sqrt(sum((x - mean_pnl) ** 2 for x in pnl_values) / (len(pnl_values) - 1))
        sharpe = (mean_pnl / std_pnl) * math.sqrt(150) if std_pnl > 0 else 0.0
    else:
        sharpe = 0.0

    return {
        "period": f"{start_date} to {end_date}",
        "total_bets": len(bets),
        "wins": wins,
        "losses": len(bets) - wins,
        "win_rate": wins / len(bets) if bets else 0.0,
        "total_pnl": total_pnl,
        "total_staked": total_staked,
        "roi": total_pnl / total_staked if total_staked > 0 else 0.0,
        "avg_clv": sum(clv_values) / len(clv_values) if clv_values else 0.0,
        "sharpe_ratio": sharpe,
        "betting_days": len(daily_pnl),
    }


def clv_analysis(db: BettingDatabase, days: int = 30) -> dict[str, Any]:
    """Analyze CLV distribution and trends.

    Args:
        db: BettingDatabase instance.
        days: Number of days to analyze.

    Returns:
        Dict with CLV metrics.
    """
    start_date = (date.today() - timedelta(days=days)).isoformat()

    bets = db.execute_query(
        "SELECT * FROM bets WHERE game_date >= ? AND clv IS NOT NULL",
        (start_date,),
    )

    if not bets:
        return {"period_days": days, "bets_with_clv": 0}

    clv_values = [b["clv"] for b in bets]
    positive_clv = [c for c in clv_values if c > 0]
    negative_clv = [c for c in clv_values if c < 0]

    # CLV by bet type
    by_type: dict[str, list[float]] = {}
    for b in bets:
        bt = b["bet_type"]
        by_type.setdefault(bt, [])
        by_type[bt].append(b["clv"])

    # Daily CLV trend
    daily_clv: dict[str, list[float]] = {}
    for b in bets:
        d = str(b["game_date"])
        daily_clv.setdefault(d, [])
        daily_clv[d].append(b["clv"])

    daily_avg = {d: sum(v) / len(v) for d, v in daily_clv.items()}

    return {
        "period_days": days,
        "bets_with_clv": len(bets),
        "avg_clv": sum(clv_values) / len(clv_values),
        "median_clv": sorted(clv_values)[len(clv_values) // 2],
        "positive_clv_pct": len(positive_clv) / len(clv_values) if clv_values else 0,
        "avg_positive_clv": sum(positive_clv) / len(positive_clv) if positive_clv else 0,
        "avg_negative_clv": sum(negative_clv) / len(negative_clv) if negative_clv else 0,
        "clv_by_bet_type": {bt: sum(v) / len(v) for bt, v in by_type.items()},
        "daily_avg_clv": daily_avg,
    }


def model_health_check(db: BettingDatabase) -> dict[str, Any]:
    """Check model health for drift and performance degradation.

    Alerts:
        - CLV < 0 for 7+ consecutive days -> CRITICAL
        - 5+ consecutive losses -> WARNING
        - Win rate < 48% over last 100 bets -> WARNING

    Returns:
        Dict with health status and alerts.
    """
    alerts = []

    # Check recent CLV trend (last 7 days)
    recent_bets = db.execute_query(
        """SELECT game_date, AVG(clv) as avg_clv
           FROM bets
           WHERE clv IS NOT NULL AND game_date >= date('now', '-7 days')
           GROUP BY game_date
           ORDER BY game_date"""
    )

    negative_clv_days = sum(1 for b in recent_bets if (b["avg_clv"] or 0) < 0)
    if negative_clv_days >= 7:
        alerts.append(
            {
                "level": "CRITICAL",
                "message": f"CLV negative for {negative_clv_days} consecutive days",
                "action": "Review model predictions and odds accuracy",
            }
        )

    # Check consecutive losses
    recent_results = db.execute_query(
        "SELECT result FROM bets WHERE result IS NOT NULL ORDER BY created_at DESC LIMIT 20"
    )
    consecutive_losses = 0
    for b in recent_results:
        if b["result"] == "loss":
            consecutive_losses += 1
        else:
            break

    if consecutive_losses >= 5:
        alerts.append(
            {
                "level": "WARNING",
                "message": f"{consecutive_losses} consecutive losses",
                "action": "Reduce bet sizing by 50% until streak breaks",
            }
        )

    # Check win rate over last 100 bets
    last_100 = db.execute_query(
        "SELECT result FROM bets WHERE result IS NOT NULL ORDER BY created_at DESC LIMIT 100"
    )
    if len(last_100) >= 50:
        wins = sum(1 for b in last_100 if b["result"] == "win")
        win_rate = wins / len(last_100)
        if win_rate < 0.48:
            alerts.append(
                {
                    "level": "WARNING",
                    "message": f"Win rate {win_rate:.1%} over last {len(last_100)} bets",
                    "action": "Review model calibration",
                }
            )

    status = "HEALTHY"
    if any(a["level"] == "CRITICAL" for a in alerts):
        status = "CRITICAL"
    elif any(a["level"] == "WARNING" for a in alerts):
        status = "WARNING"

    return {
        "status": status,
        "alerts": alerts,
        "negative_clv_days": negative_clv_days,
        "consecutive_losses": consecutive_losses,
        "recent_bets_count": len(last_100),
    }


def odds_system_health(db: BettingDatabase) -> dict[str, Any]:
    """Check odds retrieval system health.

    Tracks provider success rates, cache performance, and API budget.

    Returns:
        Dict with system health metrics.
    """
    # Count odds snapshots by source
    snapshots = db.execute_query(
        """SELECT sportsbook, COUNT(*) as count,
                  MIN(captured_at) as first, MAX(captured_at) as last
           FROM odds_snapshots
           GROUP BY sportsbook"""
    )

    providers = {}
    for row in snapshots:
        providers[row["sportsbook"]] = {
            "count": row["count"],
            "first_capture": row["first"],
            "last_capture": row["last"],
        }

    # Check for stale data
    stale_threshold = (datetime.now() - timedelta(hours=24)).isoformat()
    stale = db.execute_query(
        "SELECT COUNT(*) as count FROM odds_snapshots WHERE captured_at < ?",
        (stale_threshold,),
    )

    return {
        "providers": providers,
        "total_snapshots": sum(p["count"] for p in providers.values()),
        "stale_snapshots": stale[0]["count"] if stale else 0,
    }
