"""Global Configuration Settings.

Centralizes configuration for the sports betting project including
bankroll management, risk parameters, and API settings.
"""

import os
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
NCAAB_DATABASE_PATH = DATA_DIR / "ncaab_betting.db"
MLB_DATABASE_PATH = DATA_DIR / "mlb_data.db"
DATABASE_PATH = NCAAB_DATABASE_PATH  # backwards-compat alias — NCAAB consumers use this

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
NCAAB_SEASONS_END = 2026  # Through 2025-26 season

# =============================================================================
# ZERO-COST DATA RETRIEVAL SLA DEFINITIONS
# =============================================================================
# Service Level Agreements for data freshness
# Violation incurs opportunity_cost = edge_loss × bet_frequency × avg_stake

SLA_CLOSING_ODDS_MAX_AGE = 15 * 60  # 15 minutes - CRITICAL for CLV
SLA_CLOSING_ODDS_EDGE_LOSS = 0.10  # 10% of bet profit per violation

SLA_MARKET_PRICES_MAX_AGE = 5 * 60  # 5 minutes
SLA_MARKET_PRICES_EDGE_LOSS = 0.02  # 2% edge loss per violation

SLA_TEAM_RATINGS_MAX_AGE = 24 * 60 * 60  # 1 day
SLA_TEAM_RATINGS_EDGE_LOSS = 0.005  # 0.5% edge loss per violation

SLA_SCHEDULE_DATA_MAX_AGE = 6 * 60 * 60  # 6 hours
SLA_SCHEDULE_DATA_EDGE_LOSS = 0.001  # 0.1% edge loss per violation

SLA_HISTORICAL_DATA_MAX_AGE = 7 * 24 * 60 * 60  # 7 days
SLA_HISTORICAL_DATA_EDGE_LOSS = 0.0001  # 0.01% edge loss per violation

# Rate limits for zero-cost sources (requests per minute)
RATE_LIMITS: Dict[str, dict] = {
    "sportsipy": {"rpm": 60, "delay": 1.0},
    "sports_reference": {"rpm": 30, "delay": 2.0},
    "espn_undocumented": {"rpm": 20, "delay": 3.0},
    "polymarket": {"rpm": 100, "delay": 0.6},
    "kalshi": {"rpm": 60, "delay": 1.0},
    "draftkings_scrape": {"rpm": 10, "delay": 6.0},
    "fanduel_scrape": {"rpm": 10, "delay": 6.0},
    "betmgm_scrape": {"rpm": 10, "delay": 6.0},
}

# Blocked paid APIs (zero-cost enforcement)
# Note: the-odds-api is allowed when ALLOW_FREE_TIER_APIS is True (free 500 credits/mo)
ALLOW_FREE_TIER_APIS = True
PAID_APIS_BLOCKED = [
    "prophetx",
    "sportsdata.io",
    "sportradar",
    "action-network",
    "pinnacle-api",
]
# Also block these when ALLOW_FREE_TIER_APIS is False
_FREE_TIER_APIS = [
    "the-odds-api",
    "odds-api.com",
]

# The Odds API key (free tier: 500 credits/month)
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "")

# CBBData / Barttorvik T-Rank API key (free, provides efficiency ratings)
CBBDATA_API_KEY = os.environ.get("CBBDATA_API_KEY", "")

# Barttorvik ratings cache directory
BARTTORVIK_DATA_DIR = DATA_DIR / "external" / "barttorvik"

# KenPom efficiency ratings (requires $25/yr subscription)
KENPOM_EMAIL = os.environ.get("KENPOM_EMAIL", "")
KENPOM_PASSWORD = os.environ.get("KENPOM_PASSWORD", "")
KENPOM_DATA_DIR = DATA_DIR / "external" / "kenpom"

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
