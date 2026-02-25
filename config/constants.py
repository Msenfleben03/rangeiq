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

    MAX_BET_FRACTION: float = 0.05  # 5% of bankroll
    MAX_BET_DOLLARS: float = 250.0  # $250 cap

    # Exposure limits
    DAILY_EXPOSURE_LIMIT: float = 0.20  # 20% of bankroll
    WEEKLY_LOSS_TRIGGER: float = 0.25  # 25% triggers sizing reduction
    MONTHLY_LOSS_PAUSE: float = 0.40  # 40% triggers full pause


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

    # --- Advanced feature configuration ---

    # Rolling volatility windows (std dev of point_diff)
    VOLATILITY_WINDOWS: tuple = (5, 10)

    # Opponent-quality weighting
    OQ_MEAN_ELO: float = 1500.0  # Neutral weight when opponent is average

    # Rest days
    BACK_TO_BACK_THRESHOLD: int = 1  # days_rest <= 1 = back-to-back

    # Decay-weighted rolling
    DECAY_HALF_LIFE_GAMES: int = 8  # Games for weight to halve

    # Feature toggles — empty = Elo-only baseline
    FEATURES_ENABLED: tuple = ()

    # All available advanced features
    ALL_FEATURES: tuple = (
        "vol_5",
        "vol_10",
        "oq_margin_10",
        "rest_days",
        "is_back_to_back",
        "decay_margin_10",
    )


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

# =============================================================================
# PAPER BETTING CONFIGURATION
# =============================================================================


@dataclass
class PaperBettingConfig:
    """Paper betting pipeline configuration."""

    # Edge thresholds — only bet when model edge exceeds this
    MIN_EDGE: float = 0.075  # 7.5% minimum edge for paper bets

    # Barttorvik integration
    BARTTORVIK_WEIGHT: float = 1.0  # Full weight on Barttorvik adjustment
    BARTTORVIK_NET_DIFF_COEFF: float = 0.005
    BARTTORVIK_BARTHAG_DIFF_COEFF: float = 0.20

    # KenPom integration (disabled until grid search completes)
    KENPOM_WEIGHT: float = 0.0
    KENPOM_NET_DIFF_COEFF: float = 0.005
    KENPOM_SOS_COEFF: float = 0.0

    # Bet sizing for paper tracking
    PAPER_BANKROLL: float = 5000.0  # Virtual bankroll
    KELLY_FRACTION: float = 0.25  # Quarter Kelly
    MAX_BET_FRACTION: float = 0.05  # 5% max

    # Daily limits
    MAX_BETS_PER_DAY: int = 10
    MAX_DAILY_EXPOSURE_FRACTION: float = 0.20  # 20% of bankroll

    # ESPN Scoreboard API
    ESPN_SCOREBOARD_URL: str = (
        "http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"
    )

    # Reporting
    WEEKLY_REVIEW_WINDOW_DAYS: int = 7
    MIN_BETS_FOR_REPORT: int = 5


PAPER_BETTING = PaperBettingConfig()

# =============================================================================
# BREADWINNER METRIC CONFIGURATION
# =============================================================================


@dataclass
class BreadwinnerConfig:
    """Breadwinner (player production concentration) metric configuration."""

    # Rotation definition
    MIN_MINUTES_ROTATION: float = 0.0  # Min mpg to be in rotation (0 = no filter)
    ROTATION_SIZE: int = 8  # Top N players by minutes

    # Quality filter: team must be top-N in BOTH adj_o AND adj_d
    QUALITY_RANK_CUTOFF: int = 50

    # Variance compression coefficient (grid searchable)
    # NOTE: Needs to be large (0.5-5.0) because USG% share diffs are small (~0.02-0.05)
    # DISABLED (0.0): 6-season backtest showed no reliable signal.
    # Best variant (top1-centers, cutoff=150, coeff=3.0) averaged +0.13% ROI
    # improvement — within noise. 2025 was the only positive season (+0.84%),
    # suggesting single-season overfitting. Set >0 to re-enable for experimentation.
    BREADWINNER_COEFF: float = 0.0

    # Concentration variant: "top1", "top2", or "hhi"
    BREADWINNER_VARIANT: str = "top1"

    # Overall weight applied to the adjustment
    BREADWINNER_WEIGHT: float = 1.0

    # Center dampening: if False, skip adjustment when breadwinner is a center
    INCLUDE_CENTERS: bool = True

    # Player stats cache directory
    PLAYER_STATS_CACHE_DIR: str = "data/external/barttorvik"

    # cbbdata player endpoint
    PLAYER_SEASON_ENDPOINT: str = "https://www.cbbdata.com/api/torvik/player/season"


BREADWINNER = BreadwinnerConfig()

# =============================================================================
# KENPOM EFFICIENCY METRIC CONFIGURATION
# =============================================================================


@dataclass
class KenPomConfig:
    """KenPom efficiency rating integration configuration."""

    # Weight applied to KenPom adjustment (0 = disabled)
    # Start disabled — grid search (tune_kenpom_weights.py) will optimize
    KENPOM_WEIGHT: float = 0.0

    # AdjEM (net efficiency) differential coefficient
    # Higher = more adjustment based on KenPom net rating diff
    KENPOM_NET_DIFF_COEFF: float = 0.005

    # SOS differential coefficient (optional)
    # Schedule strength adjustment
    KENPOM_SOS_COEFF: float = 0.0

    # Rate limiting for kenpompy requests
    REQUEST_DELAY: float = 3.0  # seconds between requests

    # KenPom ratings cache directory
    KENPOM_CACHE_DIR: str = "data/external/kenpom"


KENPOM = KenPomConfig()

# =============================================================================
# ESPN PREDICTOR INJURY/DIVERGENCE CHECK
# =============================================================================


@dataclass
class InjuryCheckConfig:
    """ESPN predictor cross-check for injury/roster detection.

    Compares our model's probability against ESPN's predictor (which
    incorporates injuries, form, and roster changes). Large divergences
    signal that our model is missing key information (e.g., star player out).
    """

    ENABLED: bool = True

    # Divergence thresholds (in probability, e.g., 0.10 = 10 percentage points)
    DIVERGENCE_WARN_THRESHOLD: float = 0.10  # 10pp = warning in output
    DIVERGENCE_BLOCK_THRESHOLD: float = 0.15  # 15pp = suppress bet

    # Keywords to scan in ESPN game news headlines
    INJURY_KEYWORDS: tuple = (
        "injury",
        "injured",
        "out",
        "fracture",
        "sprain",
        "tear",
        "surgery",
        "concussion",
        "illness",
        "day-to-day",
        "questionable",
        "doubtful",
        "sidelined",
        "miss",
        "absence",
        "ruled out",
    )

    # ESPN game summary endpoint
    ESPN_SUMMARY_URL: str = (
        "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary"
    )

    # Rate limiting between ESPN summary requests
    REQUEST_DELAY: float = 0.5  # seconds


INJURY_CHECK = InjuryCheckConfig()
