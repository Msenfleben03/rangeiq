"""
Pytest configuration and fixtures for sports betting tests.

This file is automatically loaded by pytest and makes fixtures available
to all test files without explicit imports.
"""

import sys
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# Configuration
# =============================================================================


@pytest.fixture(scope="session")
def project_root():
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def test_data_dir(project_root):
    """Return the test data directory, creating if needed."""
    test_dir = project_root / "tests" / "data"
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def test_db(tmp_path):
    """Create a fresh test database for each test."""
    import sqlite3

    db_path = tmp_path / "test_betting.db"

    # Initialize with schema
    schema_path = PROJECT_ROOT / "scripts" / "init_database.sql"
    if schema_path.exists():
        conn = sqlite3.connect(db_path)
        with open(schema_path) as f:
            conn.executescript(f.read())
        conn.close()

    yield db_path

    # Cleanup happens automatically with tmp_path


@pytest.fixture(scope="session")
def shared_test_db(tmp_path_factory):
    """Create a shared test database for session-scoped tests."""
    import sqlite3

    db_path = tmp_path_factory.mktemp("data") / "shared_test.db"

    schema_path = PROJECT_ROOT / "scripts" / "init_database.sql"
    if schema_path.exists():
        conn = sqlite3.connect(db_path)
        with open(schema_path) as f:
            conn.executescript(f.read())
        conn.close()

    return db_path


# =============================================================================
# Sample Data Fixtures
# =============================================================================


@pytest.fixture
def sample_game():
    """Return a sample game dictionary."""
    return {
        "game_id": "test_game_001",
        "sport": "NCAAB",
        "season": 2024,
        "game_date": date(2024, 1, 15),
        "home_team_id": "duke",
        "away_team_id": "unc",
        "home_score": 75,
        "away_score": 72,
        "is_final": True,
    }


@pytest.fixture
def sample_bet():
    """Return a sample bet dictionary."""
    return {
        "bet_uuid": "test_bet_001",
        "game_id": "test_game_001",
        "sport": "NCAAB",
        "bet_type": "spread",
        "selection": "home",
        "line": -3.5,
        "odds_placed": -110,
        "odds_closing": -108,
        "model_probability": 0.55,
        "model_edge": 0.025,
        "stake": 100.0,
        "sportsbook": "draftkings",
        "placed_at": datetime(2024, 1, 15, 18, 0, 0),
        "result": "win",
        "actual_profit_loss": 90.91,
        "clv": 0.012,
        "is_live": False,
    }


@pytest.fixture
def sample_team_ratings():
    """Return sample Elo ratings DataFrame."""
    return pd.DataFrame(
        {
            "team_id": ["duke", "unc", "kansas", "kentucky"],
            "team_name": ["Duke", "North Carolina", "Kansas", "Kentucky"],
            "elo_rating": [1650, 1620, 1680, 1590],
            "season": [2024, 2024, 2024, 2024],
        }
    )


@pytest.fixture
def sample_odds():
    """Return sample odds data."""
    return {
        "game_id": "test_game_001",
        "sportsbook": "draftkings",
        "spread_home": -3.5,
        "spread_home_odds": -110,
        "spread_away_odds": -110,
        "total": 145.5,
        "over_odds": -110,
        "under_odds": -110,
        "moneyline_home": -150,
        "moneyline_away": +130,
    }


@pytest.fixture
def sample_games_df():
    """Return a DataFrame of sample games for backtesting."""
    return pd.DataFrame(
        {
            "game_id": [f"game_{i}" for i in range(100)],
            "season": [2024] * 100,
            "game_date": pd.date_range("2024-01-01", periods=100, freq="D"),
            "home_team_id": ["duke", "unc"] * 50,
            "away_team_id": ["unc", "duke"] * 50,
            "home_score": [75 + i % 10 for i in range(100)],
            "away_score": [70 + i % 10 for i in range(100)],
            "spread_close": [-3.5 + (i % 7) for i in range(100)],
        }
    )


# =============================================================================
# Model Fixtures
# =============================================================================


@pytest.fixture
def elo_config():
    """Return default Elo model configuration."""
    return {
        "k_factor": 20,
        "home_advantage": 100,
        "initial_rating": 1500,
        "mov_cap": 25,
        "regression_factor": 0.33,
    }


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def random_seed():
    """Set random seed for reproducibility."""
    import numpy as np
    import random

    seed = 42
    np.random.seed(seed)
    random.seed(seed)
    return seed


@pytest.fixture
def mock_api_response():
    """Return a mock API response factory."""

    def _mock_response(data, status_code=200):
        class MockResponse:
            def __init__(self, json_data, status):
                self.json_data = json_data
                self.status_code = status

            def json(self):
                return self.json_data

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise Exception(f"HTTP {self.status_code}")

        return MockResponse(data, status_code)

    return _mock_response


# =============================================================================
# Markers
# =============================================================================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: mark test as slow to run")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "database: mark test as requiring database")


# =============================================================================
# Hooks
# =============================================================================


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers."""
    # Skip slow tests unless explicitly requested
    if not config.getoption("--runslow", default=False):
        skip_slow = pytest.mark.skip(reason="need --runslow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption("--runslow", action="store_true", default=False, help="run slow tests")
    parser.addoption(
        "--runintegration",
        action="store_true",
        default=False,
        help="run integration tests that require external APIs",
    )
