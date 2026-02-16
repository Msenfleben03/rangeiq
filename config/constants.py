# Configuration & Constants
# sports_betting/config/constants.py

"""Central location for all magic numbers, thresholds, and configuration values.

Claude Code: Reference this file when implementing any betting logic.
DO NOT hardcode these values elsewhere in the codebase.
"""

from dataclasses import dataclass
from typing import Dict, List

# =============================================================================
# BANKROLL MANAGEMENT
# =============================================================================


@dataclass
class BankrollConfig:
    """Bankroll management configuration."""

    TOTAL_BANKROLL: float = 5000.0
    ACTIVE_CAPITAL: float = 4000.0  # Distributed across sportsbooks
    RESERVE: float = 1000.0  # Emergency fund, never touch

    # Bet sizing limits (as fraction of bankroll)
    KELLY_FRACTION_DEFAULT: float = 0.25  # Quarter Kelly
    KELLY_FRACTION_HIGH_CONF: float = 0.33  # Third Kelly
    KELLY_FRACTION_UNCERTAIN: float = 0.15

    MAX_BET_FRACTION: float = 0.03  # 3% of bankroll
    MAX_BET_DOLLARS: float = 150.0  # $150 cap

    # Exposure limits
    DAILY_EXPOSURE_LIMIT: float = 0.10  # 10% of bankroll
    WEEKLY_LOSS_TRIGGER: float = 0.15  # 15% triggers sizing reduction
    MONTHLY_LOSS_PAUSE: float = 0.25  # 25% triggers full pause


BANKROLL = BankrollConfig()

# =============================================================================
# SPORTSBOOK ALLOCATION
# =============================================================================

SPORTSBOOK_ALLOCATION: Dict[str, float] = {
    "draftkings": 1000.0,
    "fanduel": 1000.0,
    "betmgm": 750.0,
    "caesars": 750.0,
    "espn_bet": 500.0,
}

# =============================================================================
# ELO SYSTEM PARAMETERS
# =============================================================================


@dataclass
class EloConfig:
    """Elo rating system configuration."""

    # Base parameters
    INITIAL_RATING: float = 1500.0
    MEAN_RATING: float = 1500.0

    # Sport-specific K-factors (rating volatility)
    K_FACTOR_NCAAB: int = 20
    K_FACTOR_MLB: int = 4  # Lower due to 162 game season
    K_FACTOR_NFL: int = 20
    K_FACTOR_NCAAF: int = 25  # Higher due to fewer games

    # Rating to points conversion
    # ~25 Elo points = 1 point on spread (varies by sport)
    ELO_TO_POINTS_NCAAB: float = 25.0
    ELO_TO_POINTS_MLB: float = 25.0  # For run line
    ELO_TO_POINTS_NFL: float = 25.0
    ELO_TO_POINTS_NCAAF: float = 25.0

    # Home court/field advantage (in Elo points)
    HOME_ADVANTAGE_NCAAB: float = 100.0  # ~4 points
    HOME_ADVANTAGE_MLB: float = 24.0  # ~1 run (less significant)
    HOME_ADVANTAGE_NFL: float = 48.0  # ~2 points (declining trend)
    HOME_ADVANTAGE_NCAAF: float = 75.0  # ~3 points

    # Regression to mean between seasons
    REGRESSION_FACTOR_NCAAB: float = 0.50  # 50% regression
    REGRESSION_FACTOR_MLB: float = 0.40
    REGRESSION_FACTOR_NFL: float = 0.33
    REGRESSION_FACTOR_NCAAF: float = 0.50

    # Margin of victory adjustments
    MOV_CAP_NCAAB: int = 25  # Cap blowouts at 25 points
    MOV_CAP_MLB: int = 10  # Cap at 10 runs
    MOV_CAP_NFL: int = 24
    MOV_CAP_NCAAF: int = 28

    # Rating bounds (sanity checks)
    MIN_RATING: float = 1000.0
    MAX_RATING: float = 2000.0


ELO = EloConfig()

# =============================================================================
# BETTING THRESHOLDS
# =============================================================================


@dataclass
class BettingThresholds:
    """Thresholds for bet qualification."""

    # Minimum edge required to place bet (model_prob - implied_prob)
    # 5% validated via 2025 backtest: Sharpe 0.62, CLV 1.67%, flat ROI 6.15%
    MIN_EDGE_SPREAD: float = 0.05  # 5% edge minimum
    MIN_EDGE_TOTAL: float = 0.05
    MIN_EDGE_MONEYLINE: float = 0.05
    MIN_EDGE_PROP: float = 0.03

    # CLV targets
    TARGET_CLV: float = 0.01  # 1% CLV target
    MIN_CLV_ACCEPTABLE: float = -0.02  # -2% triggers review

    # Model confidence thresholds
    HIGH_CONFIDENCE_EDGE: float = 0.05  # 5%+ edge = high confidence

    # Odds bounds (ignore extreme odds)
    MAX_FAVORITE_ODDS: int = -500  # Don't bet favorites over -500
    MAX_UNDERDOG_ODDS: int = 500  # Don't bet underdogs over +500

    # Line movement thresholds
    SIGNIFICANT_LINE_MOVE: float = 1.0  # 1 point move is significant
    STEAM_MOVE_THRESHOLD: float = 2.0  # 2+ points = steam


THRESHOLDS = BettingThresholds()

# =============================================================================
# SPORT-SPECIFIC CONSTANTS
# =============================================================================


@dataclass
class NCABBConstants:
    """NCAA Basketball specific constants."""

    # Game parameters
    GAME_LENGTH_MINUTES: int = 40
    POSSESSIONS_PER_40: float = 70.0  # Average possessions

    # Home court advantage (points)
    AVG_HOME_COURT_ADV: float = 3.5

    # Conference strength tiers
    POWER_CONFERENCES: List[str] = None
    MID_MAJOR_CONFERENCES: List[str] = None

    # Tournament seeds
    SEEDS: List[int] = None

    # Pace adjustments
    FAST_PACE_THRESHOLD: float = 72.0
    SLOW_PACE_THRESHOLD: float = 65.0

    def __post_init__(self):
        """Validate and compute derived NCAAB constants."""
        self.POWER_CONFERENCES = ["ACC", "Big 12", "Big Ten", "SEC", "Big East"]
        self.MID_MAJOR_CONFERENCES = ["A-10", "AAC", "MWC", "WCC"]
        self.SEEDS = list(range(1, 17))


NCAAB = NCABBConstants()


@dataclass
class MLBConstants:
    """MLB specific constants."""

    # Game parameters
    INNINGS_REGULATION: int = 9
    INNINGS_F5: int = 5

    # Park factor baseline
    NEUTRAL_PARK_FACTOR: float = 100.0

    # Weather impact thresholds
    COLD_WEATHER_THRESHOLD: float = 50.0  # Below 50°F impacts offense
    HOT_WEATHER_THRESHOLD: float = 85.0  # Above 85°F may impact pitchers
    HIGH_WIND_THRESHOLD: float = 15.0  # mph, impacts balls in play

    # Pitcher workload
    HIGH_PITCH_COUNT: int = 100
    DAYS_REST_MIN: int = 4  # Standard rest for starters

    # Splits considerations
    PLATOON_ADVANTAGE: float = 0.020  # ~20 points wOBA

    # Run scoring
    AVG_RUNS_PER_GAME: float = 4.5  # League average


MLB = MLBConstants()


@dataclass
class NFLConstants:
    """NFL specific constants."""

    # Game parameters
    GAME_LENGTH_MINUTES: int = 60

    # Home field advantage (points)
    AVG_HOME_FIELD_ADV: float = 2.5  # Has declined in recent years

    # Bye week advantages
    BYE_WEEK_ADV: float = 1.5  # Points for team coming off bye

    # Division game adjustments
    DIVISION_GAME_ADJ: float = -0.5  # Teams know each other

    # Weather thresholds
    COLD_GAME_THRESHOLD: float = 32.0
    WIND_THRESHOLD: float = 15.0


NFL = NFLConstants()

# =============================================================================
# DATA VALIDATION
# =============================================================================


@dataclass
class ValidationRanges:
    """Valid ranges for data validation."""

    # Spreads
    SPREAD_MIN: float = -35.0
    SPREAD_MAX: float = 35.0

    # Totals by sport
    TOTAL_MIN_NCAAB: float = 100.0
    TOTAL_MAX_NCAAB: float = 200.0
    TOTAL_MIN_MLB: float = 5.0
    TOTAL_MAX_MLB: float = 15.0
    TOTAL_MIN_NFL: float = 30.0
    TOTAL_MAX_NFL: float = 65.0

    # Probabilities
    PROB_MIN: float = 0.01
    PROB_MAX: float = 0.99

    # Elo ratings
    ELO_MIN: float = 1000.0
    ELO_MAX: float = 2000.0

    # Efficiency metrics
    EFFICIENCY_MIN: float = 70.0  # Points per 100 possessions
    EFFICIENCY_MAX: float = 140.0


VALIDATION = ValidationRanges()

# =============================================================================
# BACKTESTING PARAMETERS
# =============================================================================


@dataclass
class BacktestConfig:
    """Backtesting configuration."""

    # Minimum sample sizes
    MIN_BETS_PRELIMINARY: int = 100
    MIN_BETS_MODERATE: int = 500
    MIN_BETS_STRONG: int = 1000
    MIN_BETS_PROFESSIONAL: int = 2000

    # Train/test split
    MIN_TRAINING_SEASONS: int = 2

    # Performance thresholds
    MIN_CLV_TO_DEPLOY: float = 0.005  # 0.5% CLV minimum
    MIN_ROI_TO_DEPLOY: float = 0.01  # 1% ROI minimum in backtest

    # Overfitting detection
    MAX_TRAIN_TEST_GAP: float = 0.10  # 10% max gap between train/test performance


BACKTEST = BacktestConfig()

# =============================================================================
# API CONFIGURATION
# =============================================================================


@dataclass
class APIConfig:
    """External API configuration."""

    # Rate limits
    ODDS_API_CALLS_PER_MONTH: int = 500
    CFB_DATA_CALLS_PER_MINUTE: int = 60

    # Timeouts
    REQUEST_TIMEOUT_SECONDS: int = 30

    # Retry logic
    MAX_RETRIES: int = 3
    RETRY_DELAY_SECONDS: int = 5


API = APIConfig()

# =============================================================================
# ODDS RETRIEVAL CONFIGURATION
# =============================================================================


@dataclass
class OddsConfig:
    """Multi-modal odds retrieval configuration."""

    DEFAULT_MODE: str = "auto"
    API_CREDIT_MONTHLY_LIMIT: int = 500
    API_CREDIT_WARNING_PCT: float = 0.80
    API_CREDIT_CUTOFF_PCT: float = 0.90
    CACHE_TTL_SECONDS: int = 300  # 5 minutes
    STALE_THRESHOLD_SECONDS: int = 900  # 15 min = stale
    ESPN_RATE_LIMIT_RPS: float = 2.0
    DEFAULT_BOOKMAKERS: tuple = (
        "draftkings",
        "fanduel",
        "betmgm",
        "caesars",
    )


ODDS_CONFIG = OddsConfig()

# =============================================================================
# FEATURE ENGINEERING
# =============================================================================


@dataclass
class FeatureConfig:
    """Feature engineering parameters."""

    # Rolling window sizes
    ROLLING_WINDOW_SHORT: int = 5  # games
    ROLLING_WINDOW_MEDIUM: int = 10
    ROLLING_WINDOW_LONG: int = 20

    # Recency weighting
    DECAY_FACTOR: float = 0.95  # Exponential decay for older games

    # Lag features (to prevent leakage)
    MIN_LAG_GAMES: int = 1  # Always lag at least 1 game


FEATURES = FeatureConfig()

# =============================================================================
# LOGGING & MONITORING
# =============================================================================


@dataclass
class LoggingConfig:
    """Logging configuration."""

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "logs/sports_betting.log"

    # Monitoring thresholds
    ALERT_CONSECUTIVE_LOSSES: int = 5
    ALERT_DAILY_LOSS_PCT: float = 0.05  # 5% daily loss triggers alert


LOGGING = LoggingConfig()
