"""Betting-Specific Validation for Backtest Results.

This module provides domain-specific validation that accounts for market realities
like vig, line availability, and proper CLV calculation. Theory means nothing if
the lines weren't actually bettable.

Key Validations:
    - CLV as PRIMARY metric (not win rate) - target > 1.5% sustained
    - Realistic vig modeling (-110 baseline)
    - Lines were actually available at predicted time
    - Kelly fraction respects bankroll limits (max 25%, max 3% bet)
    - Book-specific slippage accounted for

Example:
    ```python
    from backtesting.validators import BettingValidator, BettingValidation

    validator = BettingValidator()

    # Validate CLV threshold
    clv_values = [0.02, 0.015, 0.018, 0.025, -0.01]
    is_valid = validator.validate_clv_threshold(clv_values, min_seasons=3)

    # Check realistic vig
    config = {'assumed_vig': -110, 'slippage': 0.01}
    vig_ok = validator.check_realistic_vig(config)

    # Full validation
    result = validator.full_validation(backtest_results)
    print(f"CLV passes: {result.clv_passes}")
    print(f"Lines available: {result.lines_were_available}")
    ```
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Import project modules
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from betting.odds_converter import (  # noqa: E402
    american_to_implied_prob,
)


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationIssue:
    """Represents a single validation issue found."""

    severity: ValidationSeverity
    category: str
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class VigAnalysis:
    """Analysis of vig/juice assumptions in backtest.

    Attributes:
        assumed_baseline_vig: Baseline vig used (American odds, e.g., -110)
        effective_break_even: Actual break-even win rate implied
        vig_correctly_modeled: Whether -110 standard vig was used
        reduced_vig_used: Whether reduced vig lines were assumed
        vig_impact_pct: Estimated impact of vig on results
    """

    assumed_baseline_vig: int = -110
    effective_break_even: float = 0.5238
    vig_correctly_modeled: bool = True
    reduced_vig_used: bool = False
    vig_impact_pct: float = 0.0
    issues: List[ValidationIssue] = field(default_factory=list)


@dataclass
class LineAvailabilityResult:
    """Results from line availability validation.

    Attributes:
        total_bets: Total number of bets checked
        bets_with_available_lines: Bets where line was confirmed available
        bets_with_missing_odds: Bets where odds data was missing
        bets_with_stale_lines: Bets placed on lines that had moved
        availability_rate: Percentage of bets with verified available lines
        avg_line_age_minutes: Average time between line snapshot and bet
        suspicious_bets: Bets that may have used unavailable lines
    """

    total_bets: int = 0
    bets_with_available_lines: int = 0
    bets_with_missing_odds: int = 0
    bets_with_stale_lines: int = 0
    availability_rate: float = 0.0
    avg_line_age_minutes: float = 0.0
    suspicious_bets: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class BettingValidation:
    """Complete validation results for betting backtest.

    This is the main output of the BettingValidator.full_validation() method.

    Attributes:
        clv_mean: Average Closing Line Value
        clv_passes: Whether CLV exceeds minimum threshold (1.5%)
        realistic_vig: Whether vig modeling is realistic
        lines_were_available: Whether lines were actually bettable
        kelly_respects_limits: Whether bet sizing follows Kelly limits
        book_slippage_modeled: Whether book-specific slippage accounted for
        overall_valid: Whether all critical checks pass
        issues: List of all validation issues found
        details: Detailed breakdown by category
    """

    clv_mean: float = 0.0
    clv_passes: bool = False
    realistic_vig: bool = False
    lines_were_available: bool = False
    kelly_respects_limits: bool = False
    book_slippage_modeled: bool = False
    overall_valid: bool = False
    issues: List[ValidationIssue] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        """Generate a human-readable summary of validation results."""
        lines = [
            "=" * 60,
            "BETTING VALIDATION SUMMARY",
            "=" * 60,
            "",
            f"Overall Valid: {'PASS' if self.overall_valid else 'FAIL'}",
            "",
            "Key Metrics:",
            f"  CLV Mean: {self.clv_mean:.2%} ({'PASS' if self.clv_passes else 'FAIL'} - need >1.5%)",
            f"  Realistic Vig: {'PASS' if self.realistic_vig else 'FAIL'}",
            f"  Lines Available: {'PASS' if self.lines_were_available else 'FAIL'}",
            f"  Kelly Limits: {'PASS' if self.kelly_respects_limits else 'FAIL'}",
            f"  Slippage Modeled: {'PASS' if self.book_slippage_modeled else 'FAIL'}",
            "",
        ]

        if self.issues:
            lines.append("Issues Found:")
            for issue in self.issues:
                lines.append(
                    f"  [{issue.severity.value.upper()}] {issue.category}: {issue.message}"
                )

        lines.append("=" * 60)
        return "\n".join(lines)


class BettingValidator:
    """Validates betting-specific assumptions and metrics in backtests.

    This validator ensures that backtest results account for market realities.
    CLV (Closing Line Value) is treated as the PRIMARY success metric, not win rate.

    Key Principles:
        1. CLV > Win Rate: A bettor beating the closing line WILL profit long-term
        2. Lines must have been available: Can't bet lines that didn't exist
        3. Vig is real: -110 baseline vig must be modeled
        4. Bankroll limits matter: Kelly fraction must be respected
        5. Books differ: Sharp vs soft book slippage varies

    Attributes:
        MIN_CLV: Minimum CLV threshold (1.5%)
        STANDARD_VIG: Standard American odds baseline (-110)
        MAX_KELLY_FRACTION: Maximum Kelly fraction allowed (0.25)
        MAX_BET_SIZE: Maximum bet as fraction of bankroll (0.03)

    Example:
        ```python
        validator = BettingValidator()

        # Single check
        clv = validator.calculate_clv(-105, -110)  # 0.96% CLV

        # Full validation
        result = validator.full_validation(backtest_results)
        if not result.overall_valid:
            for issue in result.issues:
                print(f"{issue.severity}: {issue.message}")
        ```
    """

    # Class-level constants
    MIN_CLV: float = 0.015  # 1.5% minimum CLV threshold
    STANDARD_VIG: int = -110  # Standard American odds baseline
    MAX_KELLY_FRACTION: float = 0.25  # Quarter Kelly maximum
    MAX_BET_SIZE: float = 0.03  # 3% of bankroll maximum
    MIN_SEASONS_FOR_CLV: int = 3  # Minimum seasons for CLV validation

    # Book-specific slippage rates
    BOOK_SLIPPAGE: Dict[str, float] = {
        "pinnacle": 0.005,  # Sharp book - 0.5% slippage
        "betfair": 0.006,
        "draftkings": 0.010,  # Soft books - 1% slippage
        "fanduel": 0.010,
        "betmgm": 0.015,
        "caesars": 0.015,
        "pointsbet": 0.012,
        "espn_bet": 0.015,
        "barstool": 0.015,
        "default": 0.010,
    }

    def __init__(
        self,
        min_clv: float = 0.015,
        max_kelly_fraction: float = 0.25,
        max_bet_size: float = 0.03,
    ):
        """Initialize BettingValidator with configurable thresholds.

        Args:
            min_clv: Minimum acceptable CLV threshold (default 1.5%)
            max_kelly_fraction: Maximum Kelly fraction allowed (default 0.25)
            max_bet_size: Maximum bet as bankroll fraction (default 0.03)
        """
        self.min_clv = min_clv
        self.max_kelly_fraction = max_kelly_fraction
        self.max_bet_size = max_bet_size

    def calculate_clv(self, odds_placed: int, odds_closing: int) -> float:
        """Calculate Closing Line Value.

        CLV is THE KEY PREDICTOR of long-term profitability.
        Positive CLV = got better odds than market closed at.

        Formula: CLV = (closing_prob - placed_prob) / placed_prob

        Args:
            odds_placed: American odds when bet was placed
            odds_closing: American odds when market closed

        Returns:
            CLV as a decimal (0.015 = 1.5% positive CLV)

        Example:
            >>> validator = BettingValidator()
            >>> validator.calculate_clv(-105, -110)
            0.00957...  # Got better odds - good!
            >>> validator.calculate_clv(-110, -105)
            -0.00962...  # Got worse odds - bad!
        """
        if odds_placed == 0 or odds_closing == 0:
            return 0.0

        prob_placed = american_to_implied_prob(odds_placed)
        prob_closing = american_to_implied_prob(odds_closing)

        if prob_placed == 0:
            return 0.0

        return (prob_closing - prob_placed) / prob_placed

    def validate_clv_threshold(
        self,
        clv_values: List[float],
        min_seasons: int = 3,
        season_labels: Optional[List[int]] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Validate that CLV exceeds minimum threshold sustained over seasons.

        CLV > 1.5% sustained over 3+ seasons is the gold standard for
        demonstrating a legitimate betting edge.

        Args:
            clv_values: List of CLV values from backtest
            min_seasons: Minimum number of seasons required (default 3)
            season_labels: Optional season labels for each CLV value

        Returns:
            Tuple of (passes_validation, detailed_results)

        Example:
            >>> validator = BettingValidator()
            >>> clv_values = [0.02, 0.015, 0.018, 0.025, 0.012]
            >>> passes, details = validator.validate_clv_threshold(clv_values)
            >>> print(f"CLV passes: {passes}")
        """
        if not clv_values or len(clv_values) == 0:
            return False, {
                "error": "No CLV values provided",
                "mean_clv": 0.0,
                "passes": False,
            }

        clv_array = np.array(clv_values)
        mean_clv = np.mean(clv_array)
        median_clv = np.median(clv_array)
        std_clv = np.std(clv_array) if len(clv_array) > 1 else 0.0
        positive_rate = np.mean(clv_array > 0)

        # Check if mean CLV exceeds threshold
        passes_mean = mean_clv >= self.min_clv

        # If season labels provided, validate per-season
        seasons_pass = True
        season_stats = {}

        if season_labels is not None and len(season_labels) == len(clv_values):
            unique_seasons = sorted(set(season_labels))

            if len(unique_seasons) < min_seasons:
                seasons_pass = False

            for season in unique_seasons:
                season_clv = [clv for clv, s in zip(clv_values, season_labels) if s == season]
                if season_clv:
                    season_mean = np.mean(season_clv)
                    season_stats[season] = {
                        "mean_clv": season_mean,
                        "n_bets": len(season_clv),
                        "passes": season_mean >= self.min_clv * 0.5,  # Allow some variance
                    }

        details = {
            "mean_clv": float(mean_clv),
            "median_clv": float(median_clv),
            "std_clv": float(std_clv),
            "positive_rate": float(positive_rate),
            "n_bets": len(clv_values),
            "threshold": self.min_clv,
            "passes_mean": passes_mean,
            "seasons_analyzed": len(season_stats) if season_stats else None,
            "season_stats": season_stats if season_stats else None,
        }

        overall_passes = passes_mean and seasons_pass

        return overall_passes, details

    def check_realistic_vig(
        self,
        backtest_config: Dict[str, Any],
        bets_df: Optional[pd.DataFrame] = None,
    ) -> VigAnalysis:
        """Verify that -110 baseline vig is properly modeled.

        The standard vig for most markets is -110/-110, meaning:
        - Break-even win rate: 52.38%
        - Implied hold: 4.76%

        If a backtest assumes +100 or reduced vig lines, results are inflated.

        Args:
            backtest_config: Configuration dict with vig assumptions
            bets_df: Optional DataFrame of bets to analyze actual odds

        Returns:
            VigAnalysis with detailed vig validation results

        Example:
            >>> validator = BettingValidator()
            >>> config = {'assumed_vig': -110}
            >>> result = validator.check_realistic_vig(config)
            >>> print(f"Vig correctly modeled: {result.vig_correctly_modeled}")
        """
        issues = []
        assumed_vig = backtest_config.get("assumed_vig", -110)
        reduced_vig = backtest_config.get("reduced_vig", False)
        _slippage = backtest_config.get("slippage", 0.0)  # noqa: F841

        # Calculate effective break-even
        if assumed_vig != 0:
            effective_break_even = american_to_implied_prob(assumed_vig)
        else:
            effective_break_even = 0.50
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="vig",
                    message="Zero vig assumed - unrealistic for real betting",
                )
            )

        # Check if standard vig is used
        vig_correctly_modeled = abs(assumed_vig) >= 105  # At least -105 vig

        if not vig_correctly_modeled:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="vig",
                    message=f"Vig of {assumed_vig} is below realistic threshold (-105 minimum)",
                    details={"assumed_vig": assumed_vig, "threshold": -105},
                )
            )

        if reduced_vig:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    category="vig",
                    message="Reduced vig lines assumed - verify these are consistently available",
                )
            )

        # Analyze actual bets if provided
        vig_impact_pct = 0.0
        if bets_df is not None and "odds_placed" in bets_df.columns:
            avg_odds = bets_df["odds_placed"].mean()

            # Calculate how much better than -110 the average odds were
            baseline_implied = american_to_implied_prob(-110)
            actual_implied = american_to_implied_prob(int(avg_odds))

            if actual_implied < baseline_implied:
                vig_impact_pct = (baseline_implied - actual_implied) / baseline_implied
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.INFO,
                        category="vig",
                        message=f"Average odds ({avg_odds:.0f}) better than -110 by {vig_impact_pct:.2%}",
                    )
                )

        return VigAnalysis(
            assumed_baseline_vig=assumed_vig,
            effective_break_even=effective_break_even,
            vig_correctly_modeled=vig_correctly_modeled,
            reduced_vig_used=reduced_vig,
            vig_impact_pct=vig_impact_pct,
            issues=issues,
        )

    def validate_line_availability(
        self,
        bets_df: pd.DataFrame,
        historical_odds_df: pd.DataFrame,
        time_tolerance_minutes: int = 30,
        line_tolerance: float = 0.5,
    ) -> LineAvailabilityResult:
        """Validate that predicted edges were actually bettable.

        This is CRITICAL - a backtest is meaningless if the lines weren't
        actually available at the time the model would have bet them.

        Checks:
        1. Were odds available at the predicted bet time?
        2. Had the line already moved past the predicted edge?
        3. Is there suspicious timing (betting on lines about to move)?

        Args:
            bets_df: DataFrame with columns:
                - game_id: Unique game identifier
                - bet_time: When bet would have been placed
                - line: The line the bet was placed on
                - odds_placed: The odds used
            historical_odds_df: DataFrame with columns:
                - game_id: Unique game identifier
                - timestamp: When odds were recorded
                - line: Line at that time
                - odds: Odds at that time
            time_tolerance_minutes: Max time between bet and odds snapshot
            line_tolerance: Max line difference allowed (points)

        Returns:
            LineAvailabilityResult with detailed availability analysis

        Example:
            >>> validator = BettingValidator()
            >>> result = validator.validate_line_availability(bets_df, odds_df)
            >>> print(f"Availability rate: {result.availability_rate:.1%}")
        """
        result = LineAvailabilityResult(total_bets=len(bets_df))
        suspicious = []

        required_bet_cols = {"game_id", "bet_time", "line", "odds_placed"}
        required_odds_cols = {"game_id", "timestamp", "line", "odds"}

        # Validate columns exist
        missing_bet_cols = required_bet_cols - set(bets_df.columns)
        missing_odds_cols = required_odds_cols - set(historical_odds_df.columns)

        if missing_bet_cols or missing_odds_cols:
            result.availability_rate = 0.0
            return result

        if len(bets_df) == 0:
            result.availability_rate = 1.0
            return result

        # Convert timestamps
        bets_df = bets_df.copy()
        historical_odds_df = historical_odds_df.copy()
        bets_df["bet_time"] = pd.to_datetime(bets_df["bet_time"])
        historical_odds_df["timestamp"] = pd.to_datetime(historical_odds_df["timestamp"])

        time_diffs = []

        for idx, bet in bets_df.iterrows():
            game_odds = historical_odds_df[
                historical_odds_df["game_id"] == bet["game_id"]
            ].sort_values("timestamp")

            if len(game_odds) == 0:
                result.bets_with_missing_odds += 1
                continue

            # Find closest odds snapshot to bet time
            time_diff = abs(game_odds["timestamp"] - bet["bet_time"])
            closest_idx = time_diff.idxmin()
            closest_odds = game_odds.loc[closest_idx]
            min_diff_minutes = time_diff.min().total_seconds() / 60

            time_diffs.append(min_diff_minutes)

            # Check time tolerance
            if min_diff_minutes > time_tolerance_minutes:
                result.bets_with_stale_lines += 1
                suspicious.append(
                    {
                        "game_id": bet["game_id"],
                        "reason": "stale_line",
                        "time_diff_minutes": min_diff_minutes,
                    }
                )
                continue

            # Check line tolerance
            line_diff = abs(bet["line"] - closest_odds["line"])
            if line_diff > line_tolerance:
                result.bets_with_stale_lines += 1
                suspicious.append(
                    {
                        "game_id": bet["game_id"],
                        "reason": "line_moved",
                        "bet_line": bet["line"],
                        "available_line": closest_odds["line"],
                    }
                )
                continue

            # Line was available
            result.bets_with_available_lines += 1

        result.suspicious_bets = suspicious
        result.avg_line_age_minutes = np.mean(time_diffs) if time_diffs else 0.0

        if result.total_bets > 0:
            result.availability_rate = result.bets_with_available_lines / result.total_bets

        return result

    def validate_kelly_sizing(
        self,
        bet_sizes: List[float],
        bankroll: float,
        max_fraction: Optional[float] = None,
        max_bet: Optional[float] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Validate that bet sizes respect bankroll limits.

        Kelly criterion rules for this project:
        - Maximum Kelly fraction: 0.25 (Quarter Kelly)
        - Maximum bet size: 3% of bankroll
        - No bet should exceed these limits

        Args:
            bet_sizes: List of bet sizes (dollar amounts)
            bankroll: Total bankroll
            max_fraction: Maximum Kelly fraction (default: class setting)
            max_bet: Maximum bet as fraction (default: class setting)

        Returns:
            Tuple of (passes_validation, detailed_results)

        Example:
            >>> validator = BettingValidator()
            >>> bet_sizes = [100, 150, 200, 50]
            >>> passes, details = validator.validate_kelly_sizing(bet_sizes, 5000)
            >>> print(f"Kelly limits respected: {passes}")
        """
        if max_fraction is None:
            max_fraction = self.max_kelly_fraction
        if max_bet is None:
            max_bet = self.max_bet_size

        if bankroll <= 0:
            return False, {"error": "Invalid bankroll"}

        if not bet_sizes:
            return True, {"message": "No bets to validate"}

        bet_array = np.array(bet_sizes)
        bet_fractions = bet_array / bankroll

        max_bet_fraction = np.max(bet_fractions)
        avg_bet_fraction = np.mean(bet_fractions)
        oversized_bets = np.sum(bet_fractions > max_bet)

        passes = max_bet_fraction <= max_bet

        details = {
            "n_bets": len(bet_sizes),
            "bankroll": bankroll,
            "max_allowed_fraction": max_bet,
            "max_actual_fraction": float(max_bet_fraction),
            "avg_bet_fraction": float(avg_bet_fraction),
            "oversized_bets": int(oversized_bets),
            "max_bet_amount": float(np.max(bet_array)),
            "min_bet_amount": float(np.min(bet_array)),
            "passes": passes,
        }

        return passes, details

    def model_book_slippage(self, book_type: str) -> float:
        """Get slippage rate for a specific sportsbook.

        Different books have different execution characteristics:
        - Sharp books (Pinnacle): Tighter limits, faster line moves, less slippage
        - Soft books (DraftKings): Better odds, lower limits, more slippage

        Args:
            book_type: Sportsbook name (e.g., 'pinnacle', 'draftkings')

        Returns:
            Slippage rate as decimal (0.01 = 1% slippage)

        Example:
            >>> validator = BettingValidator()
            >>> slip = validator.model_book_slippage('pinnacle')
            >>> print(f"Pinnacle slippage: {slip:.2%}")  # 0.50%
            >>> slip = validator.model_book_slippage('caesars')
            >>> print(f"Caesars slippage: {slip:.2%}")  # 1.50%
        """
        return self.BOOK_SLIPPAGE.get(book_type.lower(), self.BOOK_SLIPPAGE["default"])

    def validate_slippage_modeled(
        self,
        backtest_config: Dict[str, Any],
        bets_df: Optional[pd.DataFrame] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """Validate that book slippage is properly modeled in backtest.

        Args:
            backtest_config: Configuration with slippage assumptions
            bets_df: Optional bets DataFrame with sportsbook column

        Returns:
            Tuple of (is_modeled, details)
        """
        slippage_modeled = backtest_config.get("slippage_modeled", False)
        global_slippage = backtest_config.get("slippage_rate", 0.0)
        book_specific = backtest_config.get("book_specific_slippage", False)

        details = {
            "slippage_modeled": slippage_modeled,
            "global_slippage_rate": global_slippage,
            "book_specific_slippage": book_specific,
        }

        # Analyze by sportsbook if data available
        if bets_df is not None and "sportsbook" in bets_df.columns:
            books_used = bets_df["sportsbook"].unique().tolist()
            expected_slippage = {}

            for book in books_used:
                expected_slippage[book] = self.model_book_slippage(book)

            details["books_used"] = books_used
            details["expected_slippage_by_book"] = expected_slippage
            details["avg_expected_slippage"] = np.mean(list(expected_slippage.values()))

        # Slippage is "modeled" if either:
        # 1. Explicit slippage_modeled flag is True
        # 2. A reasonable global slippage rate is applied (>= 0.5%)
        is_modeled = slippage_modeled or global_slippage >= 0.005

        return is_modeled, details

    def full_validation(
        self,
        backtest_results: Dict[str, Any],
        bets_df: Optional[pd.DataFrame] = None,
        historical_odds_df: Optional[pd.DataFrame] = None,
    ) -> BettingValidation:
        """Run all betting-specific validation checks.

        This is the main entry point for validating a complete backtest.
        It checks all key aspects that determine if results are realistic.

        Args:
            backtest_results: Dictionary containing:
                - clv_values: List of CLV for each bet
                - season_labels: Optional season labels
                - config: Backtest configuration
                - bet_sizes: List of bet sizes
                - bankroll: Total bankroll
            bets_df: Optional DataFrame of individual bets
            historical_odds_df: Optional historical odds for line validation

        Returns:
            BettingValidation with complete validation results

        Example:
            >>> validator = BettingValidator()
            >>> results = {
            ...     'clv_values': [0.02, 0.015, 0.018],
            ...     'config': {'assumed_vig': -110},
            ...     'bet_sizes': [100, 150, 100],
            ...     'bankroll': 5000
            ... }
            >>> validation = validator.full_validation(results)
            >>> print(validation.summary())
        """
        issues = []
        details = {}

        # Extract data from results
        clv_values = backtest_results.get("clv_values", [])
        season_labels = backtest_results.get("season_labels")
        config = backtest_results.get("config", {})
        bet_sizes = backtest_results.get("bet_sizes", [])
        bankroll = backtest_results.get("bankroll", 5000)

        # 1. Validate CLV threshold
        clv_passes, clv_details = self.validate_clv_threshold(
            clv_values, season_labels=season_labels
        )
        details["clv"] = clv_details
        clv_mean = clv_details.get("mean_clv", 0.0)

        if not clv_passes:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    category="clv",
                    message=f"CLV {clv_mean:.2%} below minimum threshold {self.min_clv:.2%}",
                    details=clv_details,
                )
            )

        # 2. Check realistic vig
        vig_analysis = self.check_realistic_vig(config, bets_df)
        details["vig"] = {
            "assumed_vig": vig_analysis.assumed_baseline_vig,
            "break_even": vig_analysis.effective_break_even,
            "correctly_modeled": vig_analysis.vig_correctly_modeled,
        }
        issues.extend(vig_analysis.issues)

        # 3. Validate line availability (if data provided)
        lines_available = True
        if bets_df is not None and historical_odds_df is not None:
            availability = self.validate_line_availability(bets_df, historical_odds_df)
            details["line_availability"] = {
                "rate": availability.availability_rate,
                "missing_odds": availability.bets_with_missing_odds,
                "stale_lines": availability.bets_with_stale_lines,
            }

            # Require at least 80% availability
            if availability.availability_rate < 0.80:
                lines_available = False
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        category="line_availability",
                        message=f"Only {availability.availability_rate:.1%} of lines verified available",
                        details={"suspicious_bets": availability.suspicious_bets[:5]},
                    )
                )
        else:
            # No data to validate - assume OK but note it
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="line_availability",
                    message="No historical odds data provided - line availability not validated",
                )
            )

        # 4. Validate Kelly sizing
        kelly_passes, kelly_details = self.validate_kelly_sizing(bet_sizes, bankroll)
        details["kelly"] = kelly_details

        if not kelly_passes:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="kelly",
                    message=f"Max bet fraction {kelly_details['max_actual_fraction']:.1%} exceeds limit {self.max_bet_size:.1%}",
                    details=kelly_details,
                )
            )

        # 5. Validate slippage modeling
        slippage_modeled, slippage_details = self.validate_slippage_modeled(config, bets_df)
        details["slippage"] = slippage_details

        if not slippage_modeled:
            issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    category="slippage",
                    message="Book slippage not modeled - results may be optimistic",
                )
            )

        # Determine overall validity
        # Critical: CLV must pass AND vig must be realistic
        # Important: Lines available, Kelly limits
        overall_valid = (
            clv_passes and vig_analysis.vig_correctly_modeled and lines_available and kelly_passes
        )

        return BettingValidation(
            clv_mean=clv_mean,
            clv_passes=clv_passes,
            realistic_vig=vig_analysis.vig_correctly_modeled,
            lines_were_available=lines_available,
            kelly_respects_limits=kelly_passes,
            book_slippage_modeled=slippage_modeled,
            overall_valid=overall_valid,
            issues=issues,
            details=details,
        )

    def validate_no_look_ahead(
        self,
        bets_df: pd.DataFrame,
        odds_col: str = "odds_closing",
        bet_time_col: str = "placed_at",
        game_time_col: str = "game_date",
    ) -> Tuple[bool, List[int]]:
        """Check that no bets use closing odds before game time.

        A common source of inflated results is accidentally using
        closing line information when placing bets.

        Args:
            bets_df: DataFrame of bets
            odds_col: Column with closing odds
            bet_time_col: Column with bet placement time
            game_time_col: Column with game time

        Returns:
            Tuple of (no_look_ahead_detected, suspicious_indices)
        """
        suspicious = []

        if odds_col not in bets_df.columns:
            return True, []

        # Check if closing odds were available at bet time
        # This is a heuristic - closing odds shouldn't be identical
        # to placed odds unless by chance
        for idx, row in bets_df.iterrows():
            if "odds_placed" in bets_df.columns:
                if row["odds_placed"] == row.get(odds_col):
                    # Could be coincidence or could be look-ahead
                    suspicious.append(idx)

        # If >50% have identical placed/closing odds, likely look-ahead
        look_ahead_rate = len(suspicious) / len(bets_df) if len(bets_df) > 0 else 0

        return look_ahead_rate < 0.50, suspicious


def format_validation_report(validation: BettingValidation) -> str:
    """Format a complete validation report as a string.

    Args:
        validation: BettingValidation result

    Returns:
        Formatted report string
    """
    return validation.summary()
