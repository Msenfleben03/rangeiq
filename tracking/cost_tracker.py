"""Zero-Cost Enforcement and Opportunity Cost Tracking.

This module enforces the zero-cost data retrieval constraint and tracks
opportunity costs from stale data. Any cost detection triggers immediate
rejection of the data source.

Key Principles:
1. Zero-cost is NON-NEGOTIABLE - reject any paid API calls
2. Opportunity cost = edge_loss × bet_frequency × avg_stake
3. SLA violations accumulate quantifiable costs

Author: Zero-cost data retrieval implementation
Date: 2026-01-26
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CostViolationType(Enum):
    """Types of cost violations."""

    PAID_API = "paid_api"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    AUTHENTICATION_REQUIRED = "authentication_required"
    BILLING_HEADER_DETECTED = "billing_header_detected"
    SUBSCRIPTION_ENDPOINT = "subscription_endpoint"


class SLACategory(Enum):
    """SLA categories with different freshness requirements."""

    CLOSING_ODDS = "closing_odds"
    MARKET_PRICES = "market_prices"
    TEAM_RATINGS = "team_ratings"
    SCHEDULE_DATA = "schedule_data"
    HISTORICAL_DATA = "historical_data"


@dataclass
class SLADefinition:
    """Service Level Agreement definition for data freshness."""

    category: SLACategory
    max_age_seconds: int  # Maximum acceptable age
    edge_loss_per_violation: float  # Edge loss percentage per violation
    description: str


@dataclass
class CostViolation:
    """Record of a cost policy violation."""

    timestamp: datetime
    violation_type: CostViolationType
    source: str
    details: str
    blocked: bool = True


@dataclass
class OpportunityCost:
    """Calculated opportunity cost from data staleness."""

    category: SLACategory
    data_age_seconds: float
    max_allowed_seconds: int
    edge_loss_percentage: float
    bet_frequency: float  # Bets per day
    avg_stake: float
    calculated_cost: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CostReport:
    """Summary report of cost tracking."""

    report_date: datetime
    total_violations: int
    total_opportunity_cost: float
    violations_by_type: dict
    opportunity_costs_by_category: dict
    zero_cost_compliance: bool
    recommendations: list


# =============================================================================
# SLA DEFINITIONS (from plan)
# =============================================================================
SLA_DEFINITIONS: dict[SLACategory, SLADefinition] = {
    SLACategory.CLOSING_ODDS: SLADefinition(
        category=SLACategory.CLOSING_ODDS,
        max_age_seconds=15 * 60,  # 15 minutes
        edge_loss_per_violation=0.10,  # 10% of bet profit
        description="Closing odds must be captured within 15 minutes of game start",
    ),
    SLACategory.MARKET_PRICES: SLADefinition(
        category=SLACategory.MARKET_PRICES,
        max_age_seconds=5 * 60,  # 5 minutes
        edge_loss_per_violation=0.02,  # 2% edge loss
        description="Prediction market prices should be within 5 minutes",
    ),
    SLACategory.TEAM_RATINGS: SLADefinition(
        category=SLACategory.TEAM_RATINGS,
        max_age_seconds=24 * 60 * 60,  # 1 day
        edge_loss_per_violation=0.005,  # 0.5% edge loss
        description="Team ratings should be updated daily",
    ),
    SLACategory.SCHEDULE_DATA: SLADefinition(
        category=SLACategory.SCHEDULE_DATA,
        max_age_seconds=6 * 60 * 60,  # 6 hours
        edge_loss_per_violation=0.001,  # 0.1% edge loss
        description="Schedule data refreshed every 6 hours",
    ),
    SLACategory.HISTORICAL_DATA: SLADefinition(
        category=SLACategory.HISTORICAL_DATA,
        max_age_seconds=7 * 24 * 60 * 60,  # 7 days
        edge_loss_per_violation=0.0001,  # 0.01% edge loss
        description="Historical data can be up to 7 days old",
    ),
}


class ZeroCostEnforcer:
    """Enforces zero-cost data retrieval policy.

    CRITICAL: Any cost detection triggers immediate rejection.
    This class monitors API responses and blocks paid sources.
    """

    # Blocked APIs that require payment
    PAID_APIS_BLOCKED: list[str] = [
        "the-odds-api",
        "odds-api.com",
        "prophetx",
        "sportsdata.io",
        "sportradar",
        "action-network",
        "covers.com/api",
        "betfair-exchange",  # Unless using free tier
        "pinnacle-api",
        "betonline-api",
    ]

    # HTTP status codes indicating payment issues
    COST_STATUS_CODES: list[int] = [
        402,  # Payment Required
        403,  # Forbidden (often billing-related)
        429,  # Too Many Requests (may indicate paid tier needed)
    ]

    # Headers that indicate billing/subscription
    BILLING_HEADERS: list[str] = [
        "x-ratelimit-remaining-month",
        "x-api-credits-remaining",
        "x-subscription-tier",
        "x-billing-cycle",
        "x-cost-per-request",
        "x-credits-used",
    ]

    def __init__(self, db_path: Optional[str] = None):
        """Initialize zero-cost enforcer.

        Args:
            db_path: Path to SQLite database for logging violations.
        """
        self.db_path = db_path
        self.violations: list[CostViolation] = []
        self._init_violation_table()

    def _init_violation_table(self) -> None:
        """Initialize violations table if using database."""
        if not self.db_path:
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cost_violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    violation_type TEXT NOT NULL,
                    source TEXT NOT NULL,
                    details TEXT,
                    blocked BOOLEAN DEFAULT TRUE
                )
            """
            )
            conn.commit()

    def verify_source(self, source_url: str) -> tuple[bool, Optional[CostViolation]]:
        """Verify that a source is not a paid API.

        Args:
            source_url: URL or identifier of the data source.

        Returns:
            Tuple of (is_allowed, violation_if_blocked).
        """
        source_lower = source_url.lower()

        # Check against blocked paid APIs
        for blocked_api in self.PAID_APIS_BLOCKED:
            if blocked_api in source_lower:
                violation = CostViolation(
                    timestamp=datetime.now(timezone.utc),
                    violation_type=CostViolationType.PAID_API,
                    source=source_url,
                    details=f"Blocked paid API detected: {blocked_api}",
                    blocked=True,
                )
                self._log_violation(violation)
                return False, violation

        return True, None

    def verify_response(
        self, source: str, status_code: int, headers: dict[str, str]
    ) -> tuple[bool, Optional[CostViolation]]:
        """Verify that an API response doesn't indicate paid service.

        Args:
            source: Source identifier.
            status_code: HTTP status code.
            headers: Response headers.

        Returns:
            Tuple of (is_allowed, violation_if_blocked).
        """
        # Check for payment-required status codes
        if status_code == 402:
            violation = CostViolation(
                timestamp=datetime.now(timezone.utc),
                violation_type=CostViolationType.AUTHENTICATION_REQUIRED,
                source=source,
                details="HTTP 402 Payment Required received",
                blocked=True,
            )
            self._log_violation(violation)
            return False, violation

        # Check for billing headers
        headers_lower = {k.lower(): v for k, v in headers.items()}
        for billing_header in self.BILLING_HEADERS:
            if billing_header.lower() in headers_lower:
                violation = CostViolation(
                    timestamp=datetime.now(timezone.utc),
                    violation_type=CostViolationType.BILLING_HEADER_DETECTED,
                    source=source,
                    details=f"Billing header detected: {billing_header}",
                    blocked=True,
                )
                self._log_violation(violation)
                return False, violation

        return True, None

    def _log_violation(self, violation: CostViolation) -> None:
        """Log a violation to memory and database."""
        self.violations.append(violation)
        logger.error(
            f"ZERO-COST VIOLATION: {violation.violation_type.value} "
            f"from {violation.source} - {violation.details}"
        )

        if self.db_path:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO cost_violations
                    (timestamp, violation_type, source, details, blocked)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        violation.timestamp.isoformat(),
                        violation.violation_type.value,
                        violation.source,
                        violation.details,
                        violation.blocked,
                    ),
                )
                conn.commit()

    def get_violations(self, since: Optional[datetime] = None) -> list[CostViolation]:
        """Get all violations, optionally filtered by time.

        Args:
            since: Only return violations after this datetime.

        Returns:
            List of cost violations.
        """
        if since is None:
            return self.violations

        return [v for v in self.violations if v.timestamp >= since]

    def is_compliant(self) -> bool:
        """Check if system is currently zero-cost compliant.

        Returns:
            True if no violations in last 24 hours.
        """
        cutoff = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        recent_violations = self.get_violations(since=cutoff)
        return len(recent_violations) == 0


class OpportunityCostTracker:
    """Tracks opportunity costs from stale/missing data.

    Quantifies the cost of data retrieval inefficiencies in terms of
    lost betting edge.
    """

    def __init__(
        self, db_path: Optional[str] = None, avg_stake: float = 100.0, bets_per_day: float = 5.0
    ):
        """Initialize opportunity cost tracker.

        Args:
            db_path: Path to SQLite database.
            avg_stake: Average stake per bet in dollars.
            bets_per_day: Average number of bets placed per day.
        """
        self.db_path = db_path
        self.avg_stake = avg_stake
        self.bets_per_day = bets_per_day
        self.costs: list[OpportunityCost] = []
        self._init_cost_table()

    def _init_cost_table(self) -> None:
        """Initialize opportunity costs table if using database."""
        if not self.db_path:
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS opportunity_costs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    category TEXT NOT NULL,
                    data_age_seconds REAL,
                    max_allowed_seconds INTEGER,
                    edge_loss_percentage REAL,
                    bet_frequency REAL,
                    avg_stake REAL,
                    calculated_cost REAL
                )
            """
            )
            conn.commit()

    def check_data_freshness(
        self, category: SLACategory, data_timestamp: datetime
    ) -> tuple[bool, Optional[OpportunityCost]]:
        """Check if data meets freshness SLA.

        Args:
            category: SLA category of the data.
            data_timestamp: When the data was captured.

        Returns:
            Tuple of (meets_sla, opportunity_cost_if_stale).
        """
        sla = SLA_DEFINITIONS.get(category)
        if not sla:
            logger.warning(f"No SLA defined for category: {category}")
            return True, None

        now = datetime.now(timezone.utc)
        if data_timestamp.tzinfo is None:
            data_timestamp = data_timestamp.replace(tzinfo=timezone.utc)

        age_seconds = (now - data_timestamp).total_seconds()

        if age_seconds <= sla.max_age_seconds:
            return True, None

        # Calculate opportunity cost
        # Formula: opportunity_cost = edge_loss × bet_frequency × avg_stake
        cost = OpportunityCost(
            category=category,
            data_age_seconds=age_seconds,
            max_allowed_seconds=sla.max_age_seconds,
            edge_loss_percentage=sla.edge_loss_per_violation,
            bet_frequency=self.bets_per_day,
            avg_stake=self.avg_stake,
            calculated_cost=sla.edge_loss_per_violation * self.bets_per_day * self.avg_stake,
        )

        self._log_cost(cost)
        return False, cost

    def _log_cost(self, cost: OpportunityCost) -> None:
        """Log an opportunity cost to memory and database."""
        self.costs.append(cost)
        logger.warning(
            f"SLA VIOLATION: {cost.category.value} data is "
            f"{cost.data_age_seconds:.0f}s old (max: {cost.max_allowed_seconds}s). "
            f"Opportunity cost: ${cost.calculated_cost:.2f}"
        )

        if self.db_path:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO opportunity_costs
                    (timestamp, category, data_age_seconds, max_allowed_seconds,
                     edge_loss_percentage, bet_frequency, avg_stake, calculated_cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cost.timestamp.isoformat(),
                        cost.category.value,
                        cost.data_age_seconds,
                        cost.max_allowed_seconds,
                        cost.edge_loss_percentage,
                        cost.bet_frequency,
                        cost.avg_stake,
                        cost.calculated_cost,
                    ),
                )
                conn.commit()

    def calculate_total_cost(
        self, since: Optional[datetime] = None, category: Optional[SLACategory] = None
    ) -> float:
        """Calculate total opportunity cost.

        Args:
            since: Only include costs after this datetime.
            category: Filter to specific category.

        Returns:
            Total opportunity cost in dollars.
        """
        filtered = self.costs

        if since:
            filtered = [c for c in filtered if c.timestamp >= since]

        if category:
            filtered = [c for c in filtered if c.category == category]

        return sum(c.calculated_cost for c in filtered)


class CostTracker:
    """Combined cost tracker managing zero-cost enforcement and opportunity costs.

    This is the main interface for cost tracking throughout the system.
    """

    def __init__(
        self, db_path: Optional[str] = None, avg_stake: float = 100.0, bets_per_day: float = 5.0
    ):
        """Initialize cost tracker.

        Args:
            db_path: Path to SQLite database.
            avg_stake: Average stake per bet.
            bets_per_day: Average bets per day.
        """
        self.db_path = db_path
        self.zero_cost_enforcer = ZeroCostEnforcer(db_path)
        self.opportunity_tracker = OpportunityCostTracker(db_path, avg_stake, bets_per_day)

    def verify_and_track(
        self,
        source: str,
        status_code: int = 200,
        headers: Optional[dict] = None,
        data_category: Optional[SLACategory] = None,
        data_timestamp: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Comprehensive verification and tracking.

        Args:
            source: Data source URL or identifier.
            status_code: HTTP response status code.
            headers: Response headers.
            data_category: SLA category for freshness check.
            data_timestamp: When the data was captured.

        Returns:
            Dictionary with verification results.
        """
        headers = headers or {}
        result = {
            "source": source,
            "allowed": True,
            "zero_cost_compliant": True,
            "sla_compliant": True,
            "violations": [],
            "opportunity_cost": 0.0,
        }

        # Verify source is not paid
        allowed, violation = self.zero_cost_enforcer.verify_source(source)
        if not allowed:
            result["allowed"] = False
            result["zero_cost_compliant"] = False
            result["violations"].append(violation)
            return result

        # Verify response doesn't indicate payment
        allowed, violation = self.zero_cost_enforcer.verify_response(source, status_code, headers)
        if not allowed:
            result["allowed"] = False
            result["zero_cost_compliant"] = False
            result["violations"].append(violation)
            return result

        # Check data freshness SLA
        if data_category and data_timestamp:
            meets_sla, cost = self.opportunity_tracker.check_data_freshness(
                data_category, data_timestamp
            )
            if not meets_sla and cost:
                result["sla_compliant"] = False
                result["opportunity_cost"] = cost.calculated_cost

        return result

    def generate_report(self, since: Optional[datetime] = None) -> CostReport:
        """Generate comprehensive cost tracking report.

        Args:
            since: Report period start (default: today).

        Returns:
            CostReport with summary statistics.
        """
        if since is None:
            since = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        violations = self.zero_cost_enforcer.get_violations(since)

        # Group violations by type
        violations_by_type: dict[str, int] = {}
        for v in violations:
            key = v.violation_type.value
            violations_by_type[key] = violations_by_type.get(key, 0) + 1

        # Group opportunity costs by category
        opportunity_by_category: dict[str, float] = {}
        for category in SLACategory:
            cost = self.opportunity_tracker.calculate_total_cost(since, category)
            if cost > 0:
                opportunity_by_category[category.value] = cost

        total_opportunity = sum(opportunity_by_category.values())

        # Generate recommendations
        recommendations = []
        if len(violations) > 0:
            recommendations.append("CRITICAL: Zero-cost violations detected. Review data sources.")
        if total_opportunity > 10:
            recommendations.append(
                f"HIGH: ${total_opportunity:.2f} opportunity cost today. "
                "Consider improving data refresh frequency."
            )
        if SLACategory.CLOSING_ODDS.value in opportunity_by_category:
            recommendations.append(
                "CRITICAL: Closing odds SLA violations affect CLV tracking. "
                "Ensure closing_odds_collector is running 15 min before games."
            )

        return CostReport(
            report_date=datetime.now(timezone.utc),
            total_violations=len(violations),
            total_opportunity_cost=total_opportunity,
            violations_by_type=violations_by_type,
            opportunity_costs_by_category=opportunity_by_category,
            zero_cost_compliance=len(violations) == 0,
            recommendations=recommendations,
        )


# =============================================================================
# CLI INTERFACE
# =============================================================================
def main():
    """CLI entry point for cost tracking."""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Zero-cost enforcement and opportunity cost tracking"
    )
    parser.add_argument("--db", default="data/betting.db", help="Path to SQLite database")
    parser.add_argument("--report", action="store_true", help="Generate cost report")
    parser.add_argument("--verify-source", type=str, help="Verify if a source URL is allowed")
    parser.add_argument(
        "--check-freshness",
        type=str,
        help="Check data freshness for category (closing_odds, market_prices, etc.)",
    )
    parser.add_argument(
        "--data-age", type=int, default=0, help="Data age in seconds for freshness check"
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    db_path = args.db if Path(args.db).exists() else None
    tracker = CostTracker(db_path)

    if args.verify_source:
        allowed, violation = tracker.zero_cost_enforcer.verify_source(args.verify_source)
        if args.json:
            result = {
                "source": args.verify_source,
                "allowed": allowed,
                "violation": violation.__dict__ if violation else None,
            }
            print(json.dumps(result, default=str, indent=2))
        else:
            if allowed:
                print(f"✅ Source allowed: {args.verify_source}")
            else:
                print(f"❌ Source BLOCKED: {args.verify_source}")
                print(f"   Reason: {violation.details}")

    elif args.check_freshness:
        try:
            category = SLACategory(args.check_freshness)
        except ValueError:
            print(f"Invalid category: {args.check_freshness}")
            print(f"Valid categories: {[c.value for c in SLACategory]}")
            return 1

        # Simulate data timestamp based on age
        data_time = datetime.now(timezone.utc).replace(microsecond=0)
        from datetime import timedelta

        data_time = data_time - timedelta(seconds=args.data_age)

        meets_sla, cost = tracker.opportunity_tracker.check_data_freshness(category, data_time)

        if args.json:
            result = {
                "category": category.value,
                "data_age_seconds": args.data_age,
                "meets_sla": meets_sla,
                "opportunity_cost": cost.calculated_cost if cost else 0,
                "sla_max_seconds": SLA_DEFINITIONS[category].max_age_seconds,
            }
            print(json.dumps(result, indent=2))
        else:
            sla = SLA_DEFINITIONS[category]
            if meets_sla:
                print(f"✅ Data freshness OK for {category.value}")
                print(f"   Age: {args.data_age}s (max allowed: {sla.max_age_seconds}s)")
            else:
                print(f"⚠️ SLA VIOLATION for {category.value}")
                print(f"   Age: {args.data_age}s (max allowed: {sla.max_age_seconds}s)")
                print(f"   Opportunity cost: ${cost.calculated_cost:.2f}")

    elif args.report:
        report = tracker.generate_report()

        if args.json:
            result = {
                "report_date": report.report_date.isoformat(),
                "total_violations": report.total_violations,
                "total_opportunity_cost": report.total_opportunity_cost,
                "violations_by_type": report.violations_by_type,
                "opportunity_costs_by_category": report.opportunity_costs_by_category,
                "zero_cost_compliance": report.zero_cost_compliance,
                "recommendations": report.recommendations,
            }
            print(json.dumps(result, indent=2))
        else:
            print("\n" + "=" * 60)
            print("COST TRACKING REPORT")
            print("=" * 60)
            print(f"\nReport Date: {report.report_date.strftime('%Y-%m-%d %H:%M UTC')}")
            print(f"\nZero-Cost Compliance: {'✅ YES' if report.zero_cost_compliance else '❌ NO'}")
            print(f"Total Violations: {report.total_violations}")
            print(f"Total Opportunity Cost: ${report.total_opportunity_cost:.2f}")

            if report.violations_by_type:
                print("\nViolations by Type:")
                for vtype, count in report.violations_by_type.items():
                    print(f"  - {vtype}: {count}")

            if report.opportunity_costs_by_category:
                print("\nOpportunity Costs by Category:")
                for cat, cost in report.opportunity_costs_by_category.items():
                    print(f"  - {cat}: ${cost:.2f}")

            if report.recommendations:
                print("\nRecommendations:")
                for rec in report.recommendations:
                    print(f"  ⚠️ {rec}")

            print("\n" + "=" * 60)

    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    exit(main())
