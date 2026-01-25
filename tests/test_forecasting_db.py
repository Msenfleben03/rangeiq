"""
Tests for the Superforecasting Database Module

Tests cover:
- Forecast creation and management
- Belief revision tracking
- Calibration calculations
- Position management
- Reference class handling
"""

import pytest
import tempfile
import os
from datetime import date
from pathlib import Path

# Add parent directory to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.forecasting_db import (  # noqa: E402
    ForecastingDatabase,
    calculate_kelly_fraction,
    american_to_probability,
    probability_to_decimal,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test_betting.db")
        db = ForecastingDatabase(db_path)

        # Initialize schema from SQL file
        schema_path = Path(__file__).parent.parent / "scripts" / "init_forecasting_schema.sql"
        if schema_path.exists():
            db.execute_script(str(schema_path))
        else:
            # Minimal schema for testing
            with db.get_cursor() as cursor:
                cursor.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS forecasts (
                        forecast_id TEXT PRIMARY KEY,
                        question_text TEXT NOT NULL,
                        question_short TEXT,
                        question_category TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        market_id TEXT,
                        market_url TEXT,
                        initial_probability REAL NOT NULL,
                        initial_confidence TEXT,
                        initial_market_price REAL,
                        current_probability REAL NOT NULL,
                        current_confidence TEXT,
                        revision_count INTEGER DEFAULT 0,
                        resolution_date_expected DATE NOT NULL,
                        resolution_date_actual DATE,
                        time_horizon_days INTEGER,
                        outcome REAL,
                        outcome_source TEXT,
                        outcome_notes TEXT,
                        is_resolved BOOLEAN DEFAULT FALSE,
                        is_ambiguous BOOLEAN DEFAULT FALSE,
                        is_voided BOOLEAN DEFAULT FALSE,
                        brier_score REAL,
                        log_score REAL,
                        reference_class_id INTEGER,
                        base_rate_used REAL,
                        adjustment_from_base REAL,
                        tags TEXT,
                        notes TEXT,
                        source_of_question TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS belief_revisions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        forecast_id TEXT NOT NULL,
                        revision_number INTEGER NOT NULL,
                        previous_probability REAL NOT NULL,
                        new_probability REAL NOT NULL,
                        probability_delta REAL,
                        previous_confidence TEXT,
                        new_confidence TEXT,
                        market_price_at_revision REAL,
                        market_delta REAL,
                        revision_trigger TEXT NOT NULL,
                        trigger_source TEXT,
                        reasoning TEXT,
                        evidence_quality TEXT,
                        evidence_direction TEXT,
                        days_since_creation INTEGER,
                        days_until_resolution INTEGER,
                        revision_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (forecast_id) REFERENCES forecasts(forecast_id),
                        UNIQUE(forecast_id, revision_number)
                    );

                    CREATE TABLE IF NOT EXISTS reference_classes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        class_name TEXT UNIQUE NOT NULL,
                        class_category TEXT NOT NULL,
                        class_description TEXT,
                        base_rate REAL NOT NULL,
                        sample_size INTEGER NOT NULL,
                        sample_period_start DATE,
                        sample_period_end DATE,
                        base_rate_confidence TEXT,
                        base_rate_notes TEXT,
                        source_name TEXT NOT NULL,
                        source_url TEXT,
                        source_type TEXT,
                        applicable_question_types TEXT,
                        selection_criteria TEXT,
                        times_used INTEGER DEFAULT 0,
                        avg_adjustment REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_by TEXT,
                        is_active BOOLEAN DEFAULT TRUE
                    );

                    CREATE TABLE IF NOT EXISTS pm_positions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        position_uuid TEXT UNIQUE NOT NULL,
                        forecast_id TEXT NOT NULL,
                        platform TEXT NOT NULL,
                        market_id TEXT NOT NULL,
                        contract_id TEXT,
                        position_type TEXT NOT NULL,
                        is_paper BOOLEAN DEFAULT TRUE,
                        entry_price REAL NOT NULL,
                        entry_quantity REAL NOT NULL,
                        entry_cost REAL NOT NULL,
                        entry_timestamp TIMESTAMP NOT NULL,
                        current_price REAL,
                        exit_price REAL,
                        exit_quantity REAL,
                        exit_proceeds REAL,
                        exit_timestamp TIMESTAMP,
                        our_probability_at_entry REAL,
                        edge_at_entry REAL,
                        kelly_fraction_used REAL,
                        position_size_pct REAL,
                        realized_pnl REAL,
                        unrealized_pnl REAL,
                        total_pnl REAL,
                        roi REAL,
                        closing_price REAL,
                        clv_equivalent REAL,
                        status TEXT DEFAULT 'open',
                        final_outcome REAL,
                        settlement_amount REAL,
                        stop_loss_price REAL,
                        take_profit_price REAL,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (forecast_id) REFERENCES forecasts(forecast_id)
                    );

                    CREATE TABLE IF NOT EXISTS calibration_metrics (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        period_type TEXT NOT NULL,
                        period_start DATE NOT NULL,
                        period_end DATE NOT NULL,
                        category TEXT,
                        platform TEXT,
                        time_horizon TEXT,
                        n_forecasts INTEGER NOT NULL,
                        brier_score REAL,
                        log_score REAL,
                        overconfidence_score REAL,
                        calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );

                    CREATE TABLE IF NOT EXISTS schema_version (
                        version INTEGER PRIMARY KEY,
                        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        description TEXT
                    );

                    INSERT OR IGNORE INTO schema_version (version, description)
                    VALUES (1, 'Initial test schema');
                """
                )

        yield db


class TestForecastManagement:
    """Tests for forecast CRUD operations."""

    def test_create_forecast(self, temp_db):
        """Test creating a new forecast."""
        forecast_id = temp_db.create_forecast(
            question_text="Will the Fed cut rates in Q1 2025?",
            question_category="economics",
            platform="polymarket",
            initial_probability=0.35,
            resolution_date_expected=date(2025, 3, 31),
            question_short="Fed cut Q1 2025",
        )

        assert forecast_id is not None
        assert forecast_id.startswith("fc_")

    def test_get_forecast(self, temp_db):
        """Test retrieving a forecast."""
        forecast_id = temp_db.create_forecast(
            question_text="Test question",
            question_category="economics",
            platform="paper",
            initial_probability=0.50,
            resolution_date_expected=date(2025, 6, 30),
        )

        forecast = temp_db.get_forecast(forecast_id)

        assert forecast is not None
        assert forecast["forecast_id"] == forecast_id
        assert forecast["initial_probability"] == 0.50
        assert forecast["current_probability"] == 0.50
        assert forecast["is_resolved"] is False

    def test_get_active_forecasts(self, temp_db):
        """Test retrieving active forecasts."""
        # Create multiple forecasts
        temp_db.create_forecast(
            question_text="Q1",
            question_category="economics",
            platform="paper",
            initial_probability=0.30,
            resolution_date_expected=date(2025, 3, 31),
        )
        temp_db.create_forecast(
            question_text="Q2",
            question_category="geopolitics",
            platform="paper",
            initial_probability=0.60,
            resolution_date_expected=date(2025, 6, 30),
        )

        # Get all active
        all_active = temp_db.get_active_forecasts()
        assert len(all_active) == 2

        # Filter by category
        econ_only = temp_db.get_active_forecasts(category="economics")
        assert len(econ_only) == 1
        assert econ_only[0]["question_category"] == "economics"

    def test_resolve_forecast(self, temp_db):
        """Test resolving a forecast."""
        forecast_id = temp_db.create_forecast(
            question_text="Test resolution",
            question_category="economics",
            platform="paper",
            initial_probability=0.80,
            resolution_date_expected=date(2025, 1, 31),
        )

        scores = temp_db.resolve_forecast(
            forecast_id=forecast_id, outcome=1.0, outcome_source="https://example.com"
        )

        # Brier score for 80% forecast on YES outcome = (0.8 - 1.0)^2 = 0.04
        assert scores["brier_score"] == pytest.approx(0.04, rel=0.001)

        # Verify forecast is marked resolved
        forecast = temp_db.get_forecast(forecast_id)
        assert forecast["is_resolved"] is True
        assert forecast["outcome"] == 1.0


class TestBeliefRevisions:
    """Tests for belief revision tracking."""

    def test_record_revision(self, temp_db):
        """Test recording a belief revision."""
        forecast_id = temp_db.create_forecast(
            question_text="Test revision",
            question_category="economics",
            platform="paper",
            initial_probability=0.40,
            resolution_date_expected=date(2025, 6, 30),
        )

        revision_num = temp_db.record_revision(
            forecast_id=forecast_id,
            new_probability=0.55,
            revision_trigger="news_event",
            reasoning="Important news changed my view",
        )

        assert revision_num == 1

        # Verify forecast was updated
        forecast = temp_db.get_forecast(forecast_id)
        assert forecast["current_probability"] == 0.55
        assert forecast["revision_count"] == 1

    def test_multiple_revisions(self, temp_db):
        """Test multiple sequential revisions."""
        forecast_id = temp_db.create_forecast(
            question_text="Test multi-revision",
            question_category="economics",
            platform="paper",
            initial_probability=0.50,
            resolution_date_expected=date(2025, 6, 30),
        )

        # First revision
        rev1 = temp_db.record_revision(
            forecast_id=forecast_id, new_probability=0.60, revision_trigger="new_data"
        )

        # Second revision
        rev2 = temp_db.record_revision(
            forecast_id=forecast_id, new_probability=0.45, revision_trigger="reconsideration"
        )

        assert rev1 == 1
        assert rev2 == 2

        # Check history
        history = temp_db.get_revision_history(forecast_id)
        assert len(history) == 2
        assert history[0]["previous_probability"] == 0.50
        assert history[0]["new_probability"] == 0.60
        assert history[1]["previous_probability"] == 0.60
        assert history[1]["new_probability"] == 0.45

    def test_cannot_revise_resolved(self, temp_db):
        """Test that resolved forecasts cannot be revised."""
        forecast_id = temp_db.create_forecast(
            question_text="Test resolved",
            question_category="economics",
            platform="paper",
            initial_probability=0.50,
            resolution_date_expected=date(2025, 1, 31),
        )

        temp_db.resolve_forecast(forecast_id, outcome=1.0)

        with pytest.raises(ValueError, match="Cannot revise resolved forecast"):
            temp_db.record_revision(
                forecast_id=forecast_id, new_probability=0.70, revision_trigger="error"
            )


class TestCalibration:
    """Tests for calibration analysis."""

    def test_brier_score_calculation(self, temp_db):
        """Test Brier score calculation."""
        # Create and resolve multiple forecasts
        test_cases = [
            (0.90, 1.0),  # Confident and right: (0.9-1)^2 = 0.01
            (0.10, 0.0),  # Confident and right: (0.1-0)^2 = 0.01
            (0.70, 1.0),  # Somewhat confident: (0.7-1)^2 = 0.09
            (0.30, 0.0),  # Somewhat confident: (0.3-0)^2 = 0.09
        ]

        for prob, outcome in test_cases:
            fc_id = temp_db.create_forecast(
                question_text=f"Test {prob}",
                question_category="economics",
                platform="paper",
                initial_probability=prob,
                resolution_date_expected=date(2025, 1, 31),
            )
            temp_db.resolve_forecast(fc_id, outcome)

        # Calculate overall Brier
        scores = temp_db.calculate_brier_score()

        assert scores["n_forecasts"] == 4
        # Average: (0.01 + 0.01 + 0.09 + 0.09) / 4 = 0.05
        assert scores["avg_brier_score"] == pytest.approx(0.05, rel=0.01)

    def test_calibration_curve(self, temp_db):
        """Test calibration curve generation."""
        # Create forecasts across probability range
        test_data = [
            (0.15, 0.0),
            (0.15, 0.0),
            (0.15, 1.0),  # 3 at 15%
            (0.85, 1.0),
            (0.85, 1.0),
            (0.85, 0.0),  # 3 at 85%
        ]

        for prob, outcome in test_data:
            fc_id = temp_db.create_forecast(
                question_text=f"Cal test {prob}",
                question_category="economics",
                platform="paper",
                initial_probability=prob,
                resolution_date_expected=date(2025, 1, 31),
            )
            temp_db.resolve_forecast(fc_id, outcome)

        bins = temp_db.generate_calibration_curve()

        # Find the bins with data
        bin_10_20 = next((b for b in bins if b.bin_label == "10-20%"), None)
        bin_80_90 = next((b for b in bins if b.bin_label == "80-90%"), None)

        assert bin_10_20 is not None
        assert bin_10_20.count == 3
        assert bin_10_20.actual_frequency == pytest.approx(1 / 3, rel=0.01)

        assert bin_80_90 is not None
        assert bin_80_90.count == 3
        assert bin_80_90.actual_frequency == pytest.approx(2 / 3, rel=0.01)


class TestPositions:
    """Tests for position management."""

    def test_create_position(self, temp_db):
        """Test creating a position."""
        forecast_id = temp_db.create_forecast(
            question_text="Position test",
            question_category="economics",
            platform="polymarket",
            initial_probability=0.45,
            resolution_date_expected=date(2025, 6, 30),
        )

        position_id = temp_db.create_position(
            forecast_id=forecast_id,
            platform="polymarket",
            market_id="test-market",
            position_type="yes",
            entry_price=0.40,
            entry_quantity=100,
            is_paper=True,
            our_probability_at_entry=0.45,
        )

        assert position_id is not None
        assert position_id.startswith("pos_")

    def test_close_position(self, temp_db):
        """Test closing a position."""
        forecast_id = temp_db.create_forecast(
            question_text="Close test",
            question_category="economics",
            platform="polymarket",
            initial_probability=0.50,
            resolution_date_expected=date(2025, 6, 30),
        )

        position_id = temp_db.create_position(
            forecast_id=forecast_id,
            platform="polymarket",
            market_id="test-market",
            position_type="yes",
            entry_price=0.40,
            entry_quantity=100,
            is_paper=True,
        )

        # Close at higher price
        result = temp_db.close_position(position_uuid=position_id, exit_price=0.60)

        # P&L = (0.60 - 0.40) * 100 = 20
        assert result["realized_pnl"] == pytest.approx(20.0, rel=0.01)
        assert result["status"] == "closed"

    def test_get_open_positions(self, temp_db):
        """Test getting open positions."""
        forecast_id = temp_db.create_forecast(
            question_text="Open pos test",
            question_category="economics",
            platform="polymarket",
            initial_probability=0.50,
            resolution_date_expected=date(2025, 6, 30),
        )

        temp_db.create_position(
            forecast_id=forecast_id,
            platform="polymarket",
            market_id="test-1",
            position_type="yes",
            entry_price=0.40,
            entry_quantity=50,
            is_paper=True,
        )

        temp_db.create_position(
            forecast_id=forecast_id,
            platform="kalshi",
            market_id="test-2",
            position_type="no",
            entry_price=0.55,
            entry_quantity=75,
            is_paper=False,
        )

        # All open
        all_open = temp_db.get_open_positions()
        assert len(all_open) == 2

        # Filter by platform
        poly_only = temp_db.get_open_positions(platform="polymarket")
        assert len(poly_only) == 1

        # Filter by paper
        paper_only = temp_db.get_open_positions(is_paper=True)
        assert len(paper_only) == 1


class TestReferenceClasses:
    """Tests for reference class management."""

    def test_create_reference_class(self, temp_db):
        """Test creating a reference class."""
        ref_id = temp_db.create_reference_class(
            class_name="Test Class",
            class_category="economics",
            base_rate=0.30,
            sample_size=100,
            source_name="Test Source",
        )

        assert ref_id is not None
        assert ref_id > 0

    def test_get_reference_classes(self, temp_db):
        """Test retrieving reference classes."""
        temp_db.create_reference_class(
            class_name="Econ Class 1",
            class_category="economics",
            base_rate=0.25,
            sample_size=50,
            source_name="Source 1",
        )

        temp_db.create_reference_class(
            class_name="Geo Class 1",
            class_category="geopolitics",
            base_rate=0.15,
            sample_size=30,
            source_name="Source 2",
        )

        # Get all
        all_classes = temp_db.get_reference_classes()
        assert len(all_classes) == 2

        # Filter by category
        econ_classes = temp_db.get_reference_classes(category="economics")
        assert len(econ_classes) == 1
        assert econ_classes[0]["class_name"] == "Econ Class 1"


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_kelly_fraction(self):
        """Test Kelly fraction calculation."""
        # 60% edge at even money (2.0 decimal)
        kelly = calculate_kelly_fraction(0.60, 2.0, fraction=1.0)
        # Full Kelly: (b*p - q) / b = (1*0.6 - 0.4) / 1 = 0.2
        assert kelly == pytest.approx(0.20, rel=0.01)

        # Quarter Kelly
        quarter_kelly = calculate_kelly_fraction(0.60, 2.0, fraction=0.25)
        assert quarter_kelly == pytest.approx(0.05, rel=0.01)

        # No edge (50% at even money)
        no_edge = calculate_kelly_fraction(0.50, 2.0, fraction=1.0)
        assert no_edge == pytest.approx(0.0, abs=0.001)

    def test_american_to_probability(self):
        """Test American odds to probability conversion."""
        # -110 (standard vig)
        assert american_to_probability(-110) == pytest.approx(0.5238, rel=0.01)

        # +100 (even money)
        assert american_to_probability(100) == pytest.approx(0.50, rel=0.01)

        # -200 (heavy favorite)
        assert american_to_probability(-200) == pytest.approx(0.6667, rel=0.01)

        # +200 (underdog)
        assert american_to_probability(200) == pytest.approx(0.3333, rel=0.01)

    def test_probability_to_decimal(self):
        """Test probability to decimal odds conversion."""
        # 50% = 2.0 decimal
        assert probability_to_decimal(0.50) == pytest.approx(2.0, rel=0.01)

        # 25% = 4.0 decimal
        assert probability_to_decimal(0.25) == pytest.approx(4.0, rel=0.01)

        # 80% = 1.25 decimal
        assert probability_to_decimal(0.80) == pytest.approx(1.25, rel=0.01)


class TestScoringMetrics:
    """Tests for scoring metric calculations."""

    def test_brier_score_perfect(self, temp_db):
        """Test Brier score for perfect predictions."""
        # Perfect prediction: 100% confidence, correct
        fc_id = temp_db.create_forecast(
            question_text="Perfect",
            question_category="economics",
            platform="paper",
            initial_probability=1.0,
            resolution_date_expected=date(2025, 1, 31),
        )
        scores = temp_db.resolve_forecast(fc_id, outcome=1.0)
        assert scores["brier_score"] == pytest.approx(0.0, abs=0.001)

    def test_brier_score_worst(self, temp_db):
        """Test Brier score for maximally wrong predictions."""
        # Worst prediction: 100% wrong
        fc_id = temp_db.create_forecast(
            question_text="Worst",
            question_category="economics",
            platform="paper",
            initial_probability=1.0,
            resolution_date_expected=date(2025, 1, 31),
        )
        scores = temp_db.resolve_forecast(fc_id, outcome=0.0)
        # (1.0 - 0.0)^2 = 1.0
        assert scores["brier_score"] == pytest.approx(1.0, rel=0.01)

    def test_log_score_calculation(self, temp_db):
        """Test log score calculation."""
        import math

        # 80% forecast, YES outcome
        fc_id = temp_db.create_forecast(
            question_text="Log test",
            question_category="economics",
            platform="paper",
            initial_probability=0.80,
            resolution_date_expected=date(2025, 1, 31),
        )
        scores = temp_db.resolve_forecast(fc_id, outcome=1.0)

        # Log score = -log(0.8) = 0.223
        expected_log = -math.log(0.80)
        assert scores["log_score"] == pytest.approx(expected_log, rel=0.01)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
