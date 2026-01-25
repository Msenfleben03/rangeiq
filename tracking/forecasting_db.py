"""Superforecasting Prediction Market Database Interface.

Provides a clean API for interacting with the forecasting schema,
including belief revision tracking, calibration analysis, and
performance metrics based on Philip Tetlock's methodology.
"""

import sqlite3
import uuid
import math
from pathlib import Path
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMS AND DATA CLASSES
# ==============================================================================


class Platform(Enum):
    """Supported prediction market platforms."""

    POLYMARKET = "polymarket"
    KALSHI = "kalshi"
    PREDICTIT = "predictit"
    METACULUS = "metaculus"
    MANIFOLD = "manifold"
    PAPER = "paper"
    GJP = "gjp"


class QuestionCategory(Enum):
    """Question categories for classification."""

    GEOPOLITICS = "geopolitics"
    ECONOMICS = "economics"
    SPORTS = "sports"
    TECHNOLOGY = "technology"
    SCIENCE = "science"
    ELECTIONS = "elections"
    CORPORATE = "corporate"
    OTHER = "other"


class RevisionTrigger(Enum):
    """What prompted a belief revision."""

    NEW_DATA = "new_data"
    NEWS_EVENT = "news_event"
    EXPERT_OPINION = "expert_opinion"
    MODEL_UPDATE = "model_update"
    MARKET_MOVEMENT = "market_movement"
    RECONSIDERATION = "reconsideration"
    BASE_RATE_ADJUSTMENT = "base_rate_adjustment"
    TIME_DECAY = "time_decay"
    DECOMPOSITION_UPDATE = "decomposition_update"
    ERROR_CORRECTION = "error_correction"
    OTHER = "other"


class Confidence(Enum):
    """Confidence levels for forecasts."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class EvidenceQuality(Enum):
    """Quality of evidence for a revision."""

    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"


class EvidenceDirection(Enum):
    """Direction of evidence impact."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    MIXED = "mixed"
    NEUTRAL = "neutral"


@dataclass
class Forecast:
    """Represents a forecast/prediction."""

    forecast_id: str
    question_text: str
    question_category: str
    platform: str
    initial_probability: float
    current_probability: float
    resolution_date_expected: date
    question_short: Optional[str] = None
    question_subcategory: Optional[str] = None
    market_id: Optional[str] = None
    contract_id: Optional[str] = None
    market_url: Optional[str] = None
    initial_confidence: Optional[str] = None
    initial_market_price: Optional[float] = None
    current_confidence: Optional[str] = None
    revision_count: int = 0
    resolution_date_actual: Optional[date] = None
    outcome: Optional[float] = None
    brier_score: Optional[float] = None
    log_score: Optional[float] = None
    reference_class_id: Optional[int] = None
    base_rate_used: Optional[float] = None
    tags: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class BeliefRevision:
    """Represents a belief update."""

    forecast_id: str
    revision_number: int
    previous_probability: float
    new_probability: float
    revision_trigger: str
    previous_confidence: Optional[str] = None
    new_confidence: Optional[str] = None
    market_price_at_revision: Optional[float] = None
    market_delta: Optional[float] = None
    trigger_source: Optional[str] = None
    reasoning: Optional[str] = None
    evidence_quality: Optional[str] = None
    evidence_direction: Optional[str] = None


@dataclass
class CalibrationBin:
    """Data for a single calibration curve bin."""

    bin_label: str
    min_prob: float
    max_prob: float
    avg_forecast: float
    actual_frequency: float
    count: int
    calibration_error: float


@dataclass
class CalibrationReport:
    """Complete calibration analysis."""

    n_forecasts: int
    brier_score: float
    log_score: float
    calibration_bins: List[CalibrationBin]
    overconfidence_score: float
    improvement_vs_random: float
    improvement_vs_market: Optional[float] = None


# ==============================================================================
# DATABASE CLASS
# ==============================================================================


class ForecastingDatabase:
    """Database interface for superforecasting prediction market tracking.

    Provides methods for:
    - Creating and managing forecasts
    - Recording belief revisions
    - Calculating calibration metrics
    - Tracking positions and P&L
    """

    def __init__(self, db_path: str = "data/betting.db"):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """Create database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def get_cursor(self):
        """Context manager for database operations."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[sqlite3.Row]:
        """Execute a SQL query and return results."""
        with self.get_cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()

    def execute_script(self, script_path: str) -> None:
        """Execute a SQL script file."""
        script = Path(script_path).read_text(encoding="utf-8")
        conn = self._get_connection()
        try:
            conn.executescript(script)
            conn.commit()
            logger.info(f"Executed script: {script_path}")
        finally:
            conn.close()

    # ==========================================================================
    # FORECAST MANAGEMENT
    # ==========================================================================

    def create_forecast(
        self,
        question_text: str,
        question_category: str,
        platform: str,
        initial_probability: float,
        resolution_date_expected: date,
        question_short: Optional[str] = None,
        market_id: Optional[str] = None,
        market_url: Optional[str] = None,
        initial_confidence: Optional[str] = None,
        initial_market_price: Optional[float] = None,
        base_rate_used: Optional[float] = None,
        reference_class_id: Optional[int] = None,
        tags: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> str:
        """Create a new forecast.

        Args:
            question_text: Full question text
            question_category: Category classification
            platform: Prediction market platform
            initial_probability: Initial probability estimate (0-1)
            resolution_date_expected: Expected resolution date
            question_short: Abbreviated question
            market_id: Platform-specific market ID
            market_url: URL to the market
            initial_confidence: Confidence level
            initial_market_price: Market price at creation
            base_rate_used: Base rate from reference class
            reference_class_id: Link to reference class
            tags: Comma-separated tags
            notes: Additional notes

        Returns:
            forecast_id: Unique identifier for the forecast
        """
        forecast_id = f"fc_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"

        time_horizon = (resolution_date_expected - date.today()).days

        adjustment = None
        if base_rate_used is not None:
            adjustment = initial_probability - base_rate_used

        query = """
            INSERT INTO forecasts (
                forecast_id, question_text, question_short, question_category,
                platform, market_id, market_url,
                initial_probability, initial_confidence, initial_market_price,
                current_probability, current_confidence,
                resolution_date_expected, time_horizon_days,
                reference_class_id, base_rate_used, adjustment_from_base,
                tags, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self.get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    forecast_id,
                    question_text,
                    question_short,
                    question_category,
                    platform,
                    market_id,
                    market_url,
                    initial_probability,
                    initial_confidence,
                    initial_market_price,
                    initial_probability,
                    initial_confidence,  # current = initial
                    resolution_date_expected,
                    time_horizon,
                    reference_class_id,
                    base_rate_used,
                    adjustment,
                    tags,
                    notes,
                ),
            )

        logger.info(f"Created forecast: {forecast_id}")
        return forecast_id

    def get_forecast(self, forecast_id: str) -> Optional[Dict[str, Any]]:
        """Get a forecast by ID."""
        query = "SELECT * FROM forecasts WHERE forecast_id = ?"
        results = self.execute_query(query, (forecast_id,))
        return dict(results[0]) if results else None

    def get_active_forecasts(
        self, category: Optional[str] = None, platform: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all unresolved forecasts."""
        query = """
            SELECT * FROM forecasts
            WHERE is_resolved = FALSE AND is_voided = FALSE
        """
        params = []

        if category:
            query += " AND question_category = ?"
            params.append(category)
        if platform:
            query += " AND platform = ?"
            params.append(platform)

        query += " ORDER BY resolution_date_expected ASC"
        results = self.execute_query(query, tuple(params))
        return [dict(row) for row in results]

    def resolve_forecast(
        self,
        forecast_id: str,
        outcome: float,
        outcome_source: Optional[str] = None,
        outcome_notes: Optional[str] = None,
        is_ambiguous: bool = False,
    ) -> Dict[str, float]:
        """Resolve a forecast with the actual outcome.

        Args:
            forecast_id: Forecast to resolve
            outcome: Actual outcome (1.0 = yes, 0.0 = no)
            outcome_source: URL/source confirming outcome
            outcome_notes: Additional notes
            is_ambiguous: Whether resolution was unclear

        Returns:
            Dict with brier_score and log_score
        """
        # Get current probability
        forecast = self.get_forecast(forecast_id)
        if not forecast:
            raise ValueError(f"Forecast not found: {forecast_id}")

        prob = forecast["current_probability"]

        # Calculate scores
        brier_score = (prob - outcome) ** 2
        if outcome == 1:
            log_score = -math.log(max(prob, 0.001))
        else:
            log_score = -math.log(max(1 - prob, 0.001))

        query = """
            UPDATE forecasts SET
                outcome = ?,
                outcome_source = ?,
                outcome_notes = ?,
                is_resolved = TRUE,
                is_ambiguous = ?,
                resolution_date_actual = DATE('now'),
                brier_score = ?,
                log_score = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE forecast_id = ?
        """

        with self.get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    outcome,
                    outcome_source,
                    outcome_notes,
                    is_ambiguous,
                    brier_score,
                    log_score,
                    forecast_id,
                ),
            )

        logger.info(f"Resolved forecast {forecast_id}: outcome={outcome}, brier={brier_score:.4f}")
        return {"brier_score": brier_score, "log_score": log_score}

    # ==========================================================================
    # BELIEF REVISION TRACKING
    # ==========================================================================

    def record_revision(
        self,
        forecast_id: str,
        new_probability: float,
        revision_trigger: str,
        new_confidence: Optional[str] = None,
        market_price_at_revision: Optional[float] = None,
        trigger_source: Optional[str] = None,
        reasoning: Optional[str] = None,
        evidence_quality: Optional[str] = None,
        evidence_direction: Optional[str] = None,
    ) -> int:
        """Record a belief revision for a forecast.

        Args:
            forecast_id: Forecast being updated
            new_probability: New probability estimate (0-1)
            revision_trigger: What prompted the update
            new_confidence: New confidence level
            market_price_at_revision: Current market price
            trigger_source: URL/source of trigger
            reasoning: Explanation for update
            evidence_quality: Quality of evidence
            evidence_direction: Direction of evidence

        Returns:
            revision_number: Sequential revision number
        """
        # Get current state
        forecast = self.get_forecast(forecast_id)
        if not forecast:
            raise ValueError(f"Forecast not found: {forecast_id}")

        if forecast["is_resolved"]:
            raise ValueError(f"Cannot revise resolved forecast: {forecast_id}")

        previous_prob = forecast["current_probability"]
        previous_conf = forecast["current_confidence"]
        revision_num = forecast["revision_count"] + 1

        # Calculate market delta if we have market prices
        market_delta = None
        if market_price_at_revision is not None:
            # Get last revision's market price
            last_revision = self.execute_query(
                """SELECT market_price_at_revision FROM belief_revisions
                   WHERE forecast_id = ? ORDER BY revision_number DESC LIMIT 1""",
                (forecast_id,),
            )
            if last_revision and last_revision[0]["market_price_at_revision"]:
                market_delta = (
                    market_price_at_revision - last_revision[0]["market_price_at_revision"]
                )

        # Calculate days
        created = datetime.fromisoformat(forecast["created_at"].replace("Z", "+00:00"))
        days_since = (datetime.now() - created).days
        expected_res = forecast["resolution_date_expected"]
        if isinstance(expected_res, str):
            expected_res = date.fromisoformat(expected_res)
        days_until = (expected_res - date.today()).days

        query = """
            INSERT INTO belief_revisions (
                forecast_id, revision_number,
                previous_probability, new_probability,
                previous_confidence, new_confidence,
                market_price_at_revision, market_delta,
                revision_trigger, trigger_source, reasoning,
                evidence_quality, evidence_direction,
                days_since_creation, days_until_resolution
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self.get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    forecast_id,
                    revision_num,
                    previous_prob,
                    new_probability,
                    previous_conf,
                    new_confidence or previous_conf,
                    market_price_at_revision,
                    market_delta,
                    revision_trigger,
                    trigger_source,
                    reasoning,
                    evidence_quality,
                    evidence_direction,
                    days_since,
                    days_until,
                ),
            )

        # Note: Trigger will update forecast's current_probability
        logger.info(
            f"Revision #{revision_num} for {forecast_id}: "
            f"{previous_prob:.2%} -> {new_probability:.2%} ({revision_trigger})"
        )
        return revision_num

    def get_revision_history(self, forecast_id: str) -> List[Dict[str, Any]]:
        """Get all revisions for a forecast."""
        query = """
            SELECT * FROM belief_revisions
            WHERE forecast_id = ?
            ORDER BY revision_number ASC
        """
        results = self.execute_query(query, (forecast_id,))
        return [dict(row) for row in results]

    # ==========================================================================
    # REFERENCE CLASS MANAGEMENT
    # ==========================================================================

    def create_reference_class(
        self,
        class_name: str,
        class_category: str,
        base_rate: float,
        sample_size: int,
        source_name: str,
        class_description: Optional[str] = None,
        sample_period_start: Optional[date] = None,
        sample_period_end: Optional[date] = None,
        base_rate_confidence: Optional[str] = None,
        source_url: Optional[str] = None,
        source_type: Optional[str] = None,
        applicable_question_types: Optional[str] = None,
    ) -> int:
        """Create a new reference class for base rate forecasting.

        Returns:
            id: Reference class ID
        """
        query = """
            INSERT INTO reference_classes (
                class_name, class_category, class_description,
                base_rate, sample_size, sample_period_start, sample_period_end,
                base_rate_confidence, source_name, source_url, source_type,
                applicable_question_types
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self.get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    class_name,
                    class_category,
                    class_description,
                    base_rate,
                    sample_size,
                    sample_period_start,
                    sample_period_end,
                    base_rate_confidence,
                    source_name,
                    source_url,
                    source_type,
                    applicable_question_types,
                ),
            )
            return cursor.lastrowid

    def get_reference_classes(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all reference classes, optionally filtered by category."""
        query = "SELECT * FROM reference_classes WHERE is_active = TRUE"
        params = []

        if category:
            query += " AND class_category = ?"
            params.append(category)

        query += " ORDER BY times_used DESC"
        results = self.execute_query(query, tuple(params))
        return [dict(row) for row in results]

    # ==========================================================================
    # CALIBRATION ANALYSIS
    # ==========================================================================

    def calculate_brier_score(
        self,
        category: Optional[str] = None,
        platform: Optional[str] = None,
        days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Calculate Brier score for resolved forecasts.

        Args:
            category: Filter by question category
            platform: Filter by platform
            days: Only include forecasts resolved in last N days

        Returns:
            Dict with scoring metrics
        """
        query = """
            SELECT
                COUNT(*) as n_forecasts,
                AVG(brier_score) as avg_brier_score,
                AVG(log_score) as avg_log_score,
                0.25 - AVG(brier_score) as improvement_vs_random,
                AVG(CASE WHEN brier_score < 0.25 THEN 1.0 ELSE 0.0 END) as pct_better_than_random,
                MIN(brier_score) as best_brier,
                MAX(brier_score) as worst_brier
            FROM forecasts
            WHERE is_resolved = TRUE
        """
        params = []

        if category:
            query += " AND question_category = ?"
            params.append(category)
        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if days:
            query += " AND resolution_date_actual >= date('now', '-' || ? || ' days')"
            params.append(days)

        results = self.execute_query(query, tuple(params))
        if results and results[0]["n_forecasts"]:
            return dict(results[0])
        return {
            "n_forecasts": 0,
            "avg_brier_score": None,
            "avg_log_score": None,
            "improvement_vs_random": None,
        }

    def generate_calibration_curve(
        self, category: Optional[str] = None, platform: Optional[str] = None, n_bins: int = 10
    ) -> List[CalibrationBin]:
        """Generate calibration curve data.

        Args:
            category: Filter by question category
            platform: Filter by platform
            n_bins: Number of probability bins (default 10)

        Returns:
            List of CalibrationBin objects
        """
        # Generate bin boundaries
        bin_size = 1.0 / n_bins
        bins = []

        for i in range(n_bins):
            min_prob = i * bin_size
            max_prob = (i + 1) * bin_size

            query = """
                SELECT
                    COUNT(*) as count,
                    AVG(current_probability) as avg_forecast,
                    AVG(outcome) as actual_frequency
                FROM forecasts
                WHERE is_resolved = TRUE
                    AND current_probability >= ?
                    AND current_probability < ?
            """
            params = [min_prob, max_prob if i < n_bins - 1 else 1.01]

            if category:
                query += " AND question_category = ?"
                params.append(category)
            if platform:
                query += " AND platform = ?"
                params.append(platform)

            result = self.execute_query(query, tuple(params))
            row = result[0] if result else None

            if row and row["count"] > 0:
                bins.append(
                    CalibrationBin(
                        bin_label=f"{int(min_prob*100)}-{int(max_prob*100)}%",
                        min_prob=min_prob,
                        max_prob=max_prob,
                        avg_forecast=row["avg_forecast"],
                        actual_frequency=row["actual_frequency"],
                        count=row["count"],
                        calibration_error=row["actual_frequency"] - row["avg_forecast"],
                    )
                )
            else:
                bins.append(
                    CalibrationBin(
                        bin_label=f"{int(min_prob*100)}-{int(max_prob*100)}%",
                        min_prob=min_prob,
                        max_prob=max_prob,
                        avg_forecast=0,
                        actual_frequency=0,
                        count=0,
                        calibration_error=0,
                    )
                )

        return bins

    def analyze_overconfidence(self) -> Dict[str, Any]:
        """Analyze overconfidence patterns in forecasts.

        Returns:
            Dict with overconfidence metrics by confidence level
        """
        query = """
            SELECT
                CASE
                    WHEN current_probability >= 0.9 THEN 'very_confident_yes'
                    WHEN current_probability <= 0.1 THEN 'very_confident_no'
                    WHEN current_probability >= 0.75 THEN 'confident_yes'
                    WHEN current_probability <= 0.25 THEN 'confident_no'
                    ELSE 'moderate'
                END as confidence_level,
                COUNT(*) as n_forecasts,
                AVG(current_probability) as avg_forecast,
                AVG(outcome) as actual_rate,
                AVG(outcome) - AVG(current_probability) as calibration_error
            FROM forecasts
            WHERE is_resolved = TRUE
            GROUP BY confidence_level
            ORDER BY avg_forecast DESC
        """

        results = self.execute_query(query)
        analysis = {}
        for row in results:
            level = row["confidence_level"]
            analysis[level] = {
                "n_forecasts": row["n_forecasts"],
                "avg_forecast": row["avg_forecast"],
                "actual_rate": row["actual_rate"],
                "calibration_error": row["calibration_error"],
                "bias": "overconfident" if row["calibration_error"] < 0 else "underconfident",
            }

        return analysis

    def analyze_revision_patterns(self) -> Dict[str, Any]:
        """Analyze belief revision patterns and effectiveness.

        Returns:
            Dict with revision pattern analysis
        """
        query = """
            SELECT
                revision_trigger,
                COUNT(*) as n_updates,
                AVG(ABS(probability_delta)) as avg_magnitude,
                AVG(probability_delta) as avg_direction,
                AVG(CASE
                    WHEN f.outcome = 1 AND br.probability_delta > 0 THEN 1.0
                    WHEN f.outcome = 0 AND br.probability_delta < 0 THEN 1.0
                    ELSE 0.0
                END) as toward_truth_rate
            FROM belief_revisions br
            JOIN forecasts f ON br.forecast_id = f.forecast_id
            WHERE f.is_resolved = TRUE
            GROUP BY revision_trigger
            ORDER BY n_updates DESC
        """

        results = self.execute_query(query)
        patterns = {}
        for row in results:
            patterns[row["revision_trigger"]] = {
                "n_updates": row["n_updates"],
                "avg_magnitude": row["avg_magnitude"],
                "avg_direction": row["avg_direction"],
                "toward_truth_rate": row["toward_truth_rate"],
            }

        return patterns

    # ==========================================================================
    # POSITION MANAGEMENT
    # ==========================================================================

    def create_position(
        self,
        forecast_id: str,
        platform: str,
        market_id: str,
        position_type: str,
        entry_price: float,
        entry_quantity: float,
        is_paper: bool = True,
        our_probability_at_entry: Optional[float] = None,
        kelly_fraction_used: Optional[float] = None,
        position_size_pct: Optional[float] = None,
        notes: Optional[str] = None,
    ) -> str:
        """Create a new market position.

        Args:
            forecast_id: Associated forecast
            platform: Trading platform
            market_id: Platform-specific market ID
            position_type: 'yes' or 'no'
            entry_price: Price paid per contract
            entry_quantity: Number of contracts
            is_paper: True for paper trading
            our_probability_at_entry: Our forecast probability
            kelly_fraction_used: Fraction of Kelly used
            position_size_pct: Position as % of bankroll
            notes: Additional notes

        Returns:
            position_uuid: Unique position identifier
        """
        position_uuid = f"pos_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8]}"
        entry_cost = entry_price * entry_quantity

        # Calculate edge
        edge = None
        if our_probability_at_entry is not None:
            if position_type == "yes":
                edge = our_probability_at_entry - entry_price
            else:
                edge = (1 - our_probability_at_entry) - entry_price

        query = """
            INSERT INTO pm_positions (
                position_uuid, forecast_id,
                platform, market_id,
                position_type, is_paper,
                entry_price, entry_quantity, entry_cost, entry_timestamp,
                our_probability_at_entry, edge_at_entry,
                kelly_fraction_used, position_size_pct,
                current_price, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, 'open', ?)
        """

        with self.get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    position_uuid,
                    forecast_id,
                    platform,
                    market_id,
                    position_type,
                    is_paper,
                    entry_price,
                    entry_quantity,
                    entry_cost,
                    our_probability_at_entry,
                    edge,
                    kelly_fraction_used,
                    position_size_pct,
                    entry_price,
                    notes,
                ),
            )

        logger.info(f"Created position: {position_uuid} ({position_type} @ {entry_price})")
        return position_uuid

    def close_position(
        self, position_uuid: str, exit_price: float, exit_quantity: Optional[float] = None
    ) -> Dict[str, float]:
        """Close a position (fully or partially).

        Args:
            position_uuid: Position to close
            exit_price: Exit price
            exit_quantity: Quantity to close (None = full)

        Returns:
            Dict with realized P&L
        """
        query = "SELECT * FROM pm_positions WHERE position_uuid = ?"
        results = self.execute_query(query, (position_uuid,))
        if not results:
            raise ValueError(f"Position not found: {position_uuid}")

        pos = dict(results[0])

        if exit_quantity is None:
            exit_quantity = pos["entry_quantity"]

        exit_proceeds = exit_price * exit_quantity

        # Calculate P&L
        if pos["position_type"] == "yes":
            realized_pnl = (exit_price - pos["entry_price"]) * exit_quantity
        else:
            realized_pnl = (pos["entry_price"] - exit_price) * exit_quantity

        roi = realized_pnl / pos["entry_cost"] if pos["entry_cost"] else 0

        # Determine status
        remaining = pos["entry_quantity"] - exit_quantity
        status = "closed" if remaining <= 0 else "partial"

        update_query = """
            UPDATE pm_positions SET
                exit_price = ?,
                exit_quantity = ?,
                exit_proceeds = ?,
                exit_timestamp = CURRENT_TIMESTAMP,
                realized_pnl = ?,
                total_pnl = ?,
                roi = ?,
                status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE position_uuid = ?
        """

        with self.get_cursor() as cursor:
            cursor.execute(
                update_query,
                (
                    exit_price,
                    exit_quantity,
                    exit_proceeds,
                    realized_pnl,
                    realized_pnl,
                    roi,
                    status,
                    position_uuid,
                ),
            )

        return {"realized_pnl": realized_pnl, "roi": roi, "status": status}

    def get_open_positions(
        self, platform: Optional[str] = None, is_paper: Optional[bool] = None
    ) -> List[Dict[str, Any]]:
        """Get all open positions."""
        query = """
            SELECT p.*, f.question_short, f.current_probability
            FROM pm_positions p
            JOIN forecasts f ON p.forecast_id = f.forecast_id
            WHERE p.status = 'open'
        """
        params = []

        if platform:
            query += " AND p.platform = ?"
            params.append(platform)
        if is_paper is not None:
            query += " AND p.is_paper = ?"
            params.append(is_paper)

        query += " ORDER BY p.entry_timestamp DESC"
        results = self.execute_query(query, tuple(params))
        return [dict(row) for row in results]

    def get_position_performance(
        self, platform: Optional[str] = None, is_paper: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Get aggregate position performance."""
        query = """
            SELECT
                COUNT(*) as n_positions,
                SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open_positions,
                SUM(CASE WHEN status IN ('closed', 'expired') THEN 1 ELSE 0 END) as closed_positions,
                SUM(realized_pnl) as total_realized_pnl,
                SUM(unrealized_pnl) as total_unrealized_pnl,
                AVG(roi) as avg_roi,
                AVG(clv_equivalent) as avg_clv
            FROM pm_positions
            WHERE 1=1
        """
        params = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if is_paper is not None:
            query += " AND is_paper = ?"
            params.append(is_paper)

        results = self.execute_query(query, tuple(params))
        return dict(results[0]) if results else {}

    # ==========================================================================
    # CALIBRATION METRICS STORAGE
    # ==========================================================================

    def store_calibration_metrics(
        self,
        period_type: str,
        period_start: date,
        period_end: date,
        category: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> int:
        """Calculate and store calibration metrics for a period.

        Args:
            period_type: 'daily', 'weekly', 'monthly', etc.
            period_start: Start of period
            period_end: End of period
            category: Optional category filter
            platform: Optional platform filter

        Returns:
            id: Calibration metrics record ID
        """
        # Calculate all metrics
        scores = self.calculate_brier_score(category, platform)
        bins = self.generate_calibration_curve(category, platform)

        if scores["n_forecasts"] == 0:
            logger.warning("No resolved forecasts for calibration metrics")
            return -1

        # Calculate overconfidence
        overconfidence = 0
        for b in bins:
            if b.count > 0:
                overconfidence += b.calibration_error * b.count
        overconfidence /= max(scores["n_forecasts"], 1)

        # Build insert query
        query = """
            INSERT OR REPLACE INTO calibration_metrics (
                period_type, period_start, period_end,
                category, platform,
                n_forecasts, brier_score, log_score,
                overconfidence_score, improvement_over_market,
                bin_0_10_avg_prob, bin_0_10_actual_freq, bin_0_10_count,
                bin_10_20_avg_prob, bin_10_20_actual_freq, bin_10_20_count,
                bin_20_30_avg_prob, bin_20_30_actual_freq, bin_20_30_count,
                bin_30_40_avg_prob, bin_30_40_actual_freq, bin_30_40_count,
                bin_40_50_avg_prob, bin_40_50_actual_freq, bin_40_50_count,
                bin_50_60_avg_prob, bin_50_60_actual_freq, bin_50_60_count,
                bin_60_70_avg_prob, bin_60_70_actual_freq, bin_60_70_count,
                bin_70_80_avg_prob, bin_70_80_actual_freq, bin_70_80_count,
                bin_80_90_avg_prob, bin_80_90_actual_freq, bin_80_90_count,
                bin_90_100_avg_prob, bin_90_100_actual_freq, bin_90_100_count
            ) VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """

        # Extract bin data
        bin_data = []
        for i, b in enumerate(bins):
            bin_data.extend([b.avg_forecast, b.actual_frequency, b.count])

        with self.get_cursor() as cursor:
            cursor.execute(
                query,
                (
                    period_type,
                    period_start,
                    period_end,
                    category,
                    platform,
                    scores["n_forecasts"],
                    scores["avg_brier_score"],
                    scores["avg_log_score"],
                    overconfidence,
                    None,
                    *bin_data,
                ),
            )
            return cursor.lastrowid


# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================


def calculate_kelly_fraction(
    probability: float, odds: float, fraction: float = 0.25  # decimal odds
) -> float:
    """Calculate Kelly fraction for prediction market position.

    Args:
        probability: Estimated probability of winning
        odds: Decimal odds (e.g., 2.0 for even money)
        fraction: Kelly fraction to use (default 0.25)

    Returns:
        Recommended bet size as fraction of bankroll
    """
    if odds <= 1:
        return 0

    b = odds - 1
    q = 1 - probability

    kelly = (b * probability - q) / b
    return max(0, kelly * fraction)


def american_to_probability(american_odds: int) -> float:
    """Convert American odds to implied probability."""
    if american_odds > 0:
        return 100 / (american_odds + 100)
    return abs(american_odds) / (abs(american_odds) + 100)


def probability_to_decimal(probability: float) -> float:
    """Convert probability to decimal odds."""
    if probability <= 0 or probability >= 1:
        return float("inf") if probability <= 0 else 1.0
    return 1 / probability


# ==============================================================================
# MAIN (for testing)
# ==============================================================================

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Initialize database
    db = ForecastingDatabase("data/betting.db")

    print("Forecasting Database initialized.")
    print(f"Database path: {db.db_path}")

    # Test query
    try:
        active = db.get_active_forecasts()
        print(f"Active forecasts: {len(active)}")
    except Exception as e:
        print("Note: Run init_forecasting_schema.sql first to create tables")
        print(f"Error: {e}")
