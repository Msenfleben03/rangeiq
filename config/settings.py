"""
Global Configuration Settings

Centralizes configuration for the sports betting project including
bankroll management, risk parameters, and API settings.
"""
from pathlib import Path
from typing import Dict


# =============================================================================
# PROJECT PATHS
# =============================================================================
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
ODDS_DATA_DIR = DATA_DIR / "odds"
DATABASE_PATH = DATA_DIR / "betting.db"

# =============================================================================
# BANKROLL MANAGEMENT
# =============================================================================
TOTAL_BANKROLL = 5000  # Total available capital
ACTIVE_CAPITAL = 4000  # Distributed across sportsbooks
RESERVE = 1000  # Emergency reserve - never touch

# Sportsbook allocation
SPORTSBOOK_ALLOCATION: Dict[str, int] = {
    "DraftKings": 1000,
    "FanDuel": 1000,
    "BetMGM": 750,
    "Caesars": 750,
    "ESPN BET": 500,
}

# =============================================================================
# RISK MANAGEMENT
# =============================================================================
# Kelly Criterion settings
DEFAULT_KELLY_FRACTION = 0.25  # Quarter Kelly (conservative)
HIGH_CONFIDENCE_FRACTION = 0.33  # Third Kelly
UNCERTAIN_FRACTION = 0.15  # Very conservative

# Maximum bet sizes (as fraction of bankroll)
MAX_BET_STANDARD = 0.03  # 3% for standard bets
MAX_BET_HIGH = 0.04  # 4% for high confidence
MAX_BET_UNCERTAIN = 0.02  # 2% for uncertain bets

# Risk limits
DAILY_EXPOSURE_LIMIT = 0.10  # 10% of bankroll
WEEKLY_LOSS_LIMIT = 0.15  # 15% of bankroll
MONTHLY_LOSS_LIMIT = 0.25  # 25% of bankroll

# =============================================================================
# MODEL SETTINGS
# =============================================================================
# Elo rating system
ELO_START_RATING = 1500  # Starting rating for new teams
ELO_K_FACTOR = 20  # Update rate
ELO_POINTS_PER_100 = 25  # Points per 100 Elo difference
ELO_REGRESSION_FACTOR = 0.33  # Offseason regression to mean

# Minimum edge required to place bet
MIN_EDGE_REQUIRED = 0.02  # 2% minimum edge

# Minimum CLV target
TARGET_CLV = 0.01  # Aim for 1%+ CLV

# =============================================================================
# DATA FETCHING
# =============================================================================
# Rate limiting for API calls
API_DELAY_SECONDS = 1.0  # Delay between requests
MAX_RETRIES = 3  # Maximum retry attempts

# Seasons to fetch for historical data
NCAAB_SEASONS_START = 2020  # Start from 2019-20 season
NCAAB_SEASONS_END = 2025  # Through 2024-25 season

# =============================================================================
# FEATURE ENGINEERING
# =============================================================================
# Rolling window sizes for statistics
ROLLING_WINDOW_GAMES = 10  # Last N games for rolling averages
STRENGTH_OF_SCHEDULE_WINDOW = 20  # Games for SOS calculation

# =============================================================================
# BETTING MARKETS
# =============================================================================
# Market inefficiency priorities (1 = highest priority)
MARKET_PRIORITIES = {
    "player_props": 1,  # Highest inefficiency
    "small_conference": 2,  # Reduced coverage
    "derivative_markets": 3,  # Team totals, F5
    "main_markets": 4,  # Most efficient, benchmark only
}

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_FILE = PROJECT_ROOT / "logs" / "sports_betting.log"

# =============================================================================
# DATABASE
# =============================================================================
DB_ECHO = False  # SQLAlchemy echo (set True for debugging)


if __name__ == "__main__":
    print("Sports Betting Configuration")
    print("=" * 60)
    print(f"\nProject Root: {PROJECT_ROOT}")
    print(f"Database: {DATABASE_PATH}")
    print("\nBankroll:")
    print(f"  Total: ${TOTAL_BANKROLL:,}")
    print(f"  Active: ${ACTIVE_CAPITAL:,}")
    print(f"  Reserve: ${RESERVE:,}")
    print("\nRisk Parameters:")
    print(f"  Kelly Fraction: {DEFAULT_KELLY_FRACTION}")
    print(f"  Max Bet: {MAX_BET_STANDARD:.1%}")
    print(f"  Min Edge: {MIN_EDGE_REQUIRED:.1%}")
    print(f"  Target CLV: {TARGET_CLV:.1%}")
    print("\nSportsbook Allocation:")
    for book, amount in SPORTSBOOK_ALLOCATION.items():
        print(f"  {book}: ${amount:,}")
