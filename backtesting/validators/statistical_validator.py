"""Statistical Robustness Validator for Backtest Results.

This module enforces statistical rigor requirements to prevent deployment of
models based on insufficient evidence or noise. No metric claims should be
made without proper uncertainty quantification.

Key Validations:
    - Sample size >= 500 bets (MIN_SAMPLE_SIZE)
    - 95% confidence intervals on all metrics
    - Sharpe ratio >= 0.5 (MIN_SHARPE)
    - Out-of-sample degradation < 20%
    - Monte Carlo ruin probability < 5%

CRITICAL: Do not deploy any model that fails these statistical checks.
Variance in small samples can easily masquerade as alpha.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

# scipy is optional - provide fallback for analytical CI
try:
    from scipy import stats

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


@dataclass
class DrawdownAnalysis:
    """Results from drawdown analysis.

    Attributes:
        max_drawdown: Maximum peak-to-trough decline as decimal
        max_drawdown_start_idx: Index where max drawdown began
        max_drawdown_end_idx: Index where max drawdown ended
        recovery_time_periods: Periods to recover from max drawdown (-1 if not recovered)
        avg_drawdown: Average drawdown across all periods
        drawdown_duration_max: Longest time spent in drawdown
        underwater_pct: Percentage of time spent in drawdown
    """

    max_drawdown: float
    max_drawdown_start_idx: int
    max_drawdown_end_idx: int
    recovery_time_periods: int
    avg_drawdown: float
    drawdown_duration_max: int
    underwater_pct: float


@dataclass
class MonteCarloRuinResult:
    """Results from Monte Carlo ruin probability simulation.

    Attributes:
        ruin_probability: Probability of hitting ruin threshold
        n_simulations: Number of simulations run
        n_bets_per_sim: Bets per simulation
        ruin_threshold: Fraction of bankroll considered ruin
        median_final_bankroll: Median ending bankroll (as fraction of initial)
        percentile_5: 5th percentile of final bankroll
        percentile_95: 95th percentile of final bankroll
        expected_growth: Expected bankroll growth rate
    """

    ruin_probability: float
    n_simulations: int
    n_bets_per_sim: int
    ruin_threshold: float
    median_final_bankroll: float
    percentile_5: float
    percentile_95: float
    expected_growth: float


@dataclass
class StatisticalValidation:
    """Complete statistical validation results.

    Attributes:
        sample_size: Number of bets in the backtest
        is_sufficient: Whether sample size meets minimum (n >= 500)
        confidence_interval_roi: 95% CI for ROI
        confidence_interval_clv: 95% CI for CLV
        confidence_interval_win_rate: 95% CI for win rate
        sharpe_ratio: Annualized Sharpe ratio
        sharpe_passes: Whether Sharpe >= MIN_SHARPE (0.5)
        max_drawdown: Maximum drawdown as decimal
        recovery_time_days: Days to recover from max drawdown
        out_of_sample_degradation: Degradation from in-sample performance
        oos_passes: Whether degradation < 20%
        ruin_probability: Monte Carlo ruin probability
        ruin_passes: Whether ruin probability < 5%
        all_checks_pass: Whether ALL validations pass
        validation_messages: List of validation messages/warnings
    """

    sample_size: int
    is_sufficient: bool
    confidence_interval_roi: Tuple[float, float]
    confidence_interval_clv: Tuple[float, float]
    confidence_interval_win_rate: Tuple[float, float]
    sharpe_ratio: float
    sharpe_passes: bool
    max_drawdown: float
    recovery_time_days: int
    out_of_sample_degradation: Optional[float]
    oos_passes: Optional[bool]
    ruin_probability: float
    ruin_passes: bool
    all_checks_pass: bool
    validation_messages: List[str] = field(default_factory=list)


@dataclass
class StatisticalValidationResult:
    """Results from statistical validation (legacy compatibility).

    Attributes:
        passed: Whether all statistical checks passed
        sample_size_adequate: Whether sample size meets minimum requirements
        results_significant: Whether results are statistically significant
        sharpe_adequate: Whether Sharpe ratio meets threshold
        details: Detailed results for each check
    """

    passed: bool = True
    sample_size_adequate: bool = True
    results_significant: bool = True
    sharpe_adequate: bool = True
    details: Dict = field(default_factory=dict)
    failure_reasons: List[str] = field(default_factory=list)


class StatisticalValidator:
    """Validates statistical robustness of backtest results.

    This validator enforces minimum statistical requirements to prevent
    deployment of models based on insufficient evidence. It implements
    the anti-noise philosophy: no metric claims without uncertainty bounds.

    Example:
        ```python
        validator = StatisticalValidator()

        # Validate sample size
        if not validator.validate_sample_size(n_bets):
            print("INSUFFICIENT SAMPLE SIZE - Results unreliable")

        # Calculate confidence interval
        roi_ci = validator.calculate_confidence_interval(returns, 'roi')
        print(f"ROI: {np.mean(returns):.2%} (95% CI: {roi_ci[0]:.2%} - {roi_ci[1]:.2%})")

        # Full validation
        validation = validator.full_validation(backtest_results)
        if not validation.all_checks_pass:
            print("DO NOT DEPLOY - Statistical checks failed")
        ```

    Attributes:
        MIN_SAMPLE_SIZE: Minimum required bets (500)
        MIN_SHARPE: Minimum acceptable Sharpe ratio (0.5)
        CONFIDENCE_LEVEL: Confidence level for intervals (0.95)
        MAX_OOS_DEGRADATION: Maximum allowed out-of-sample degradation (0.20)
        MAX_RUIN_PROBABILITY: Maximum acceptable ruin probability (0.05)
    """

    MIN_SAMPLE_SIZE: int = 500
    MIN_SHARPE: float = 0.5
    CONFIDENCE_LEVEL: float = 0.95
    MAX_OOS_DEGRADATION: float = 0.20
    MAX_RUIN_PROBABILITY: float = 0.05

    # Minimum sample sizes by bet type (legacy compatibility)
    MIN_SAMPLES = {
        "default": 500,
        "spread": 500,
        "moneyline": 500,
        "total": 500,
        "prop": 300,  # Props have higher variance, slightly fewer samples ok
    }

    def __init__(
        self,
        min_sample_size: int = 500,
        min_sharpe: float = 0.5,
        confidence_level: float = 0.95,
        max_oos_degradation: float = 0.20,
        max_ruin_probability: float = 0.05,
        significance_level: float = 0.05,
        min_positive_ev_confidence: float = 0.90,
    ):
        """Initialize the validator with configurable thresholds.

        Args:
            min_sample_size: Minimum required sample size (default 500)
            min_sharpe: Minimum acceptable Sharpe ratio (default 0.5)
            confidence_level: Confidence level for intervals (default 0.95)
            max_oos_degradation: Maximum allowed OOS degradation (default 0.20)
            max_ruin_probability: Maximum acceptable ruin probability (default 0.05)
            significance_level: Alpha for hypothesis testing (default 0.05)
            min_positive_ev_confidence: Minimum confidence for positive EV
        """
        self.min_sample_size = min_sample_size
        self.min_sharpe = min_sharpe
        self.confidence_level = confidence_level
        self.max_oos_degradation = max_oos_degradation
        self.max_ruin_probability = max_ruin_probability
        self.significance_level = significance_level
        self.min_positive_ev_confidence = min_positive_ev_confidence

    def validate_sample_size(self, n_bets: int) -> bool:
        """Check if sample size meets minimum requirement.

        Args:
            n_bets: Number of bets in the backtest

        Returns:
            True if n_bets >= MIN_SAMPLE_SIZE, False otherwise

        Note:
            500 bets is the MINIMUM for any meaningful statistical inference.
            Even this is marginal - 1000+ bets provides much better confidence.
        """
        return n_bets >= self.min_sample_size

    def calculate_confidence_interval(
        self,
        values: Union[np.ndarray, pd.DataFrame],
        metric: str = "mean",
        n_bootstrap: int = 10000,
    ) -> Tuple[float, float]:
        """Calculate confidence interval for a metric using bootstrap.

        For ROI, CLV, and win rate, bootstrap provides robust CIs that
        don't assume normality.

        Args:
            values: Array of values (returns, CLV values, or binary outcomes)
                    OR DataFrame for legacy compatibility
            metric: Type of metric - 'roi', 'clv', 'win_rate', or 'mean'
            n_bootstrap: Number of bootstrap samples (default 10000)

        Returns:
            Tuple of (lower_bound, upper_bound) for the confidence interval

        Example:
            >>> returns = np.array([0.02, -0.01, 0.03, -0.02, 0.015])
            >>> ci = validator.calculate_confidence_interval(returns, 'roi')
            >>> print(f"95% CI: ({ci[0]:.4f}, {ci[1]:.4f})")
        """
        # Handle DataFrame for legacy compatibility
        if isinstance(values, pd.DataFrame):
            return self._calculate_ci_from_dataframe(values, metric)

        if len(values) == 0:
            return (0.0, 0.0)

        values = np.asarray(values)

        # Remove NaN values
        values = values[~np.isnan(values)]

        if len(values) == 0:
            return (0.0, 0.0)

        # For small samples, use analytical CI if scipy available
        if len(values) < 30 and HAS_SCIPY:
            return self._analytical_ci(values)

        # Bootstrap CI
        bootstrap_stats = np.zeros(n_bootstrap)
        n = len(values)

        np.random.seed(42)  # Reproducibility

        for i in range(n_bootstrap):
            sample = np.random.choice(values, size=n, replace=True)
            bootstrap_stats[i] = np.mean(sample)

        alpha = 1 - self.confidence_level
        lower = np.percentile(bootstrap_stats, alpha / 2 * 100)
        upper = np.percentile(bootstrap_stats, (1 - alpha / 2) * 100)

        return (float(lower), float(upper))

    def _calculate_ci_from_dataframe(self, df: pd.DataFrame, metric: str) -> Tuple[float, float]:
        """Calculate CI from DataFrame (legacy compatibility)."""
        if metric == "roi":
            if "profit_loss" not in df.columns or "stake" not in df.columns:
                return (0.0, 0.0)
            values = (df["profit_loss"] / df["stake"]).values
        elif metric == "clv":
            if "clv" not in df.columns:
                return (0.0, 0.0)
            values = df["clv"].values
        elif metric == "win_rate":
            if "result" not in df.columns:
                return (0.0, 0.0)
            values = (df["result"] == "win").astype(float).values
        else:
            raise ValueError(f"Unknown metric: {metric}")

        values = values[~np.isnan(values)]
        if len(values) < 2:
            return (0.0, 0.0)

        return self.calculate_confidence_interval(values, "mean")

    def _analytical_ci(self, values: np.ndarray) -> Tuple[float, float]:
        """Calculate analytical confidence interval using t-distribution.

        Used for small samples where bootstrap may be unreliable.

        Args:
            values: Array of values

        Returns:
            Tuple of (lower_bound, upper_bound)
        """
        n = len(values)
        mean = np.mean(values)
        se = np.std(values, ddof=1) / np.sqrt(n)

        if se == 0:
            return (mean, mean)

        alpha = 1 - self.confidence_level
        t_critical = stats.t.ppf(1 - alpha / 2, df=n - 1)

        margin = t_critical * se
        return (float(mean - margin), float(mean + margin))

    def calculate_sharpe_ratio(
        self,
        returns: np.ndarray,
        risk_free: float = 0.0,
        periods_per_year: int = 365,
    ) -> float:
        """Calculate annualized Sharpe ratio.

        Sharpe = (mean_return - risk_free) / std_dev * sqrt(periods_per_year)

        Args:
            returns: Array of period returns (as decimals, e.g., 0.02 for 2%)
            risk_free: Annual risk-free rate (default 0)
            periods_per_year: Number of betting periods per year

        Returns:
            Annualized Sharpe ratio

        Note:
            For betting, we typically use 0 as risk-free rate since our
            alternative is not investing, not risk-free bonds.
        """
        if len(returns) == 0:
            return 0.0

        returns = np.asarray(returns)
        returns = returns[~np.isnan(returns)]

        if len(returns) == 0:
            return 0.0

        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        if std_return == 0:
            return 0.0

        # Convert annual risk-free to per-period
        rf_per_period = risk_free / periods_per_year

        # Calculate and annualize
        sharpe = (mean_return - rf_per_period) / std_return * np.sqrt(periods_per_year)

        return float(sharpe)

    def analyze_drawdown(self, bankroll_series: np.ndarray) -> DrawdownAnalysis:
        """Analyze maximum drawdown and recovery time.

        Drawdown = peak-to-trough decline in bankroll.
        Critical for understanding the psychological and financial stress
        a strategy will impose.

        Args:
            bankroll_series: Array of cumulative bankroll values over time

        Returns:
            DrawdownAnalysis with comprehensive drawdown metrics

        Example:
            >>> bankroll = np.array([1000, 1100, 1050, 900, 950, 1000, 1100])
            >>> analysis = validator.analyze_drawdown(bankroll)
            >>> print(f"Max DD: {analysis.max_drawdown:.1%}")
        """
        if len(bankroll_series) == 0:
            return DrawdownAnalysis(
                max_drawdown=0.0,
                max_drawdown_start_idx=0,
                max_drawdown_end_idx=0,
                recovery_time_periods=-1,
                avg_drawdown=0.0,
                drawdown_duration_max=0,
                underwater_pct=0.0,
            )

        bankroll_series = np.asarray(bankroll_series)

        # Running maximum (peak)
        running_max = np.maximum.accumulate(bankroll_series)

        # Drawdown at each point
        drawdowns = (running_max - bankroll_series) / np.maximum(running_max, 1e-10)
        drawdowns = np.clip(drawdowns, 0, 1)

        max_drawdown = float(np.max(drawdowns))
        max_dd_end_idx = int(np.argmax(drawdowns))

        # Find start of max drawdown (the peak before the trough)
        max_dd_start_idx = max_dd_end_idx
        for i in range(max_dd_end_idx, -1, -1):
            if bankroll_series[i] >= running_max[max_dd_end_idx]:
                max_dd_start_idx = i
                break

        # Calculate recovery time (periods until new high after max drawdown)
        recovery_time = -1
        peak_value = running_max[max_dd_end_idx]
        for i in range(max_dd_end_idx + 1, len(bankroll_series)):
            if bankroll_series[i] >= peak_value:
                recovery_time = i - max_dd_end_idx
                break

        # Average drawdown
        avg_drawdown = float(np.mean(drawdowns))

        # Max drawdown duration
        in_drawdown = drawdowns > 0
        max_duration = 0
        current_duration = 0
        for is_dd in in_drawdown:
            if is_dd:
                current_duration += 1
                max_duration = max(max_duration, current_duration)
            else:
                current_duration = 0

        # Percentage of time underwater
        underwater_pct = float(np.mean(in_drawdown))

        return DrawdownAnalysis(
            max_drawdown=max_drawdown,
            max_drawdown_start_idx=max_dd_start_idx,
            max_drawdown_end_idx=max_dd_end_idx,
            recovery_time_periods=recovery_time,
            avg_drawdown=avg_drawdown,
            drawdown_duration_max=max_duration,
            underwater_pct=underwater_pct,
        )

    def validate_out_of_sample(
        self,
        in_sample_roi: float,
        out_sample_roi: float,
    ) -> bool:
        """Check if out-of-sample degradation is acceptable.

        Significant OOS degradation indicates overfitting to the in-sample period.
        A maximum degradation of 20% is allowed.

        Args:
            in_sample_roi: ROI on in-sample (training) data
            out_sample_roi: ROI on out-of-sample (test) data

        Returns:
            True if degradation < MAX_OOS_DEGRADATION, False otherwise

        Example:
            >>> in_sample = 0.10  # 10% ROI in-sample
            >>> out_sample = 0.08  # 8% ROI out-of-sample
            >>> degradation = (0.10 - 0.08) / 0.10 = 0.20 = 20%
            >>> validator.validate_out_of_sample(0.10, 0.08)  # Returns True (barely)
        """
        if in_sample_roi <= 0:
            # If in-sample is negative, OOS can't "degrade" meaningfully
            return out_sample_roi > 0 or abs(out_sample_roi) <= abs(in_sample_roi)

        # Calculate degradation as relative decline
        degradation = (in_sample_roi - out_sample_roi) / abs(in_sample_roi)

        return degradation < self.max_oos_degradation

    def calculate_oos_degradation(
        self,
        in_sample_roi: float,
        out_sample_roi: float,
    ) -> float:
        """Calculate out-of-sample degradation percentage.

        Args:
            in_sample_roi: ROI on in-sample data
            out_sample_roi: ROI on out-of-sample data

        Returns:
            Degradation as a decimal (0.15 = 15% degradation)
        """
        if in_sample_roi <= 0:
            return 0.0 if out_sample_roi >= in_sample_roi else 1.0

        return (in_sample_roi - out_sample_roi) / abs(in_sample_roi)

    def run_monte_carlo(
        self,
        win_rate: float,
        avg_odds: float,
        n_bets: int,
        kelly_fraction: float = 0.25,
        n_simulations: int = 10000,
        ruin_threshold: float = 0.1,
    ) -> MonteCarloRuinResult:
        """Run Monte Carlo simulation for ruin probability.

        Simulates 10,000 possible bankroll paths to estimate the probability
        of hitting the ruin threshold (losing 90% of bankroll by default).

        Args:
            win_rate: Expected win rate as decimal (0.54 for 54%)
            avg_odds: Average decimal odds (e.g., 1.91 for -110)
            n_bets: Number of bets to simulate per path
            kelly_fraction: Fraction of Kelly to use for sizing
            n_simulations: Number of simulation paths
            ruin_threshold: Fraction of bankroll considered ruin (default 0.1 = 90% loss)

        Returns:
            MonteCarloRuinResult with ruin probability and statistics

        Example:
            >>> result = validator.run_monte_carlo(
            ...     win_rate=0.54,
            ...     avg_odds=1.91,  # -110
            ...     n_bets=500,
            ...     kelly_fraction=0.25
            ... )
            >>> print(f"Ruin probability: {result.ruin_probability:.2%}")
        """
        np.random.seed(42)  # Reproducibility

        # Calculate Kelly bet size
        b = avg_odds - 1  # Profit per unit bet
        q = 1 - win_rate

        if b <= 0:
            return MonteCarloRuinResult(
                ruin_probability=1.0,
                n_simulations=n_simulations,
                n_bets_per_sim=n_bets,
                ruin_threshold=ruin_threshold,
                median_final_bankroll=0.0,
                percentile_5=0.0,
                percentile_95=0.0,
                expected_growth=-1.0,
            )

        # Full Kelly fraction
        full_kelly = (b * win_rate - q) / b
        bet_fraction = max(0, full_kelly * kelly_fraction)
        bet_fraction = min(bet_fraction, 0.05)  # Cap at 5% of bankroll

        final_bankrolls = np.zeros(n_simulations)
        ruin_count = 0

        for sim in range(n_simulations):
            bankroll = 1.0  # Start at 1 unit

            for _ in range(n_bets):
                if bankroll <= ruin_threshold:
                    ruin_count += 1
                    break

                bet_size = bankroll * bet_fraction

                if np.random.random() < win_rate:
                    bankroll += bet_size * b
                else:
                    bankroll -= bet_size

            final_bankrolls[sim] = bankroll

        ruin_probability = ruin_count / n_simulations

        return MonteCarloRuinResult(
            ruin_probability=ruin_probability,
            n_simulations=n_simulations,
            n_bets_per_sim=n_bets,
            ruin_threshold=ruin_threshold,
            median_final_bankroll=float(np.median(final_bankrolls)),
            percentile_5=float(np.percentile(final_bankrolls, 5)),
            percentile_95=float(np.percentile(final_bankrolls, 95)),
            expected_growth=float(np.mean(final_bankrolls) - 1.0),
        )

    def full_validation(
        self,
        backtest_results: Dict,
        in_sample_roi: Optional[float] = None,
        out_sample_roi: Optional[float] = None,
    ) -> StatisticalValidation:
        """Run all statistical validation checks.

        This is the primary entry point for validating backtest results.
        A model should NOT be deployed if any check fails.

        Args:
            backtest_results: Dictionary containing:
                - n_bets: Number of bets
                - returns: Array of per-bet returns
                - clv_values: Array of CLV values
                - win_rate: Overall win rate
                - outcomes: Array of binary outcomes (1=win, 0=loss)
                - bankroll_series: Array of cumulative bankroll
                - avg_odds: Average decimal odds
            in_sample_roi: Optional in-sample ROI for OOS comparison
            out_sample_roi: Optional out-of-sample ROI for comparison

        Returns:
            StatisticalValidation with all check results

        Example:
            ```python
            results = {
                'n_bets': 600,
                'returns': np.array([...]),
                'clv_values': np.array([...]),
                'outcomes': np.array([...]),
                'bankroll_series': np.array([...]),
                'avg_odds': 1.91
            }
            validation = validator.full_validation(results)

            if not validation.all_checks_pass:
                print("VALIDATION FAILED:")
                for msg in validation.validation_messages:
                    print(f"  - {msg}")
            ```
        """
        messages = []
        all_pass = True

        # Extract data
        n_bets = backtest_results.get("n_bets", 0)
        returns = np.asarray(backtest_results.get("returns", []))
        clv_values = np.asarray(backtest_results.get("clv_values", []))
        outcomes = np.asarray(backtest_results.get("outcomes", []))
        bankroll_series = np.asarray(backtest_results.get("bankroll_series", []))
        avg_odds = backtest_results.get("avg_odds", 1.91)
        win_rate = backtest_results.get("win_rate", np.mean(outcomes) if len(outcomes) > 0 else 0.5)

        # 1. Sample size check
        is_sufficient = self.validate_sample_size(n_bets)
        if not is_sufficient:
            messages.append(
                f"FAIL: Sample size {n_bets} < minimum {self.min_sample_size}. "
                "Results are statistically unreliable."
            )
            all_pass = False
        else:
            messages.append(f"PASS: Sample size {n_bets} >= {self.min_sample_size}")

        # 2. Confidence intervals
        ci_roi = self.calculate_confidence_interval(returns, "roi")
        ci_clv = self.calculate_confidence_interval(clv_values, "clv")
        ci_win_rate = self.calculate_confidence_interval(outcomes, "win_rate")

        messages.append(f"INFO: ROI 95% CI: ({ci_roi[0]:.4f}, {ci_roi[1]:.4f})")
        messages.append(f"INFO: CLV 95% CI: ({ci_clv[0]:.4f}, {ci_clv[1]:.4f})")

        # 3. Sharpe ratio
        sharpe = self.calculate_sharpe_ratio(returns)
        sharpe_passes = sharpe >= self.min_sharpe

        if not sharpe_passes:
            messages.append(
                f"FAIL: Sharpe ratio {sharpe:.2f} < minimum {self.min_sharpe}. "
                "Risk-adjusted returns are insufficient."
            )
            all_pass = False
        else:
            messages.append(f"PASS: Sharpe ratio {sharpe:.2f} >= {self.min_sharpe}")

        # 4. Drawdown analysis
        dd_analysis = self.analyze_drawdown(bankroll_series)
        max_drawdown = dd_analysis.max_drawdown
        recovery_time = dd_analysis.recovery_time_periods

        if max_drawdown > 0.3:
            messages.append(
                f"WARNING: Max drawdown {max_drawdown:.1%} exceeds 30%. "
                "Consider reducing position sizes."
            )

        # 5. Out-of-sample check
        oos_degradation = None
        oos_passes = None

        if in_sample_roi is not None and out_sample_roi is not None:
            oos_degradation = self.calculate_oos_degradation(in_sample_roi, out_sample_roi)
            oos_passes = self.validate_out_of_sample(in_sample_roi, out_sample_roi)

            if not oos_passes:
                messages.append(
                    f"FAIL: OOS degradation {oos_degradation:.1%} >= maximum "
                    f"{self.max_oos_degradation:.0%}. Possible overfitting detected."
                )
                all_pass = False
            else:
                messages.append(
                    f"PASS: OOS degradation {oos_degradation:.1%} < "
                    f"{self.max_oos_degradation:.0%}"
                )

        # 6. Monte Carlo ruin probability
        mc_result = self.run_monte_carlo(
            win_rate=win_rate,
            avg_odds=avg_odds,
            n_bets=n_bets,
            kelly_fraction=0.25,
        )
        ruin_passes = mc_result.ruin_probability < self.max_ruin_probability

        if not ruin_passes:
            messages.append(
                f"FAIL: Ruin probability {mc_result.ruin_probability:.1%} >= "
                f"maximum {self.max_ruin_probability:.0%}. Risk of ruin is too high."
            )
            all_pass = False
        else:
            messages.append(
                f"PASS: Ruin probability {mc_result.ruin_probability:.1%} < "
                f"{self.max_ruin_probability:.0%}"
            )

        return StatisticalValidation(
            sample_size=n_bets,
            is_sufficient=is_sufficient,
            confidence_interval_roi=ci_roi,
            confidence_interval_clv=ci_clv,
            confidence_interval_win_rate=ci_win_rate,
            sharpe_ratio=sharpe,
            sharpe_passes=sharpe_passes,
            max_drawdown=max_drawdown,
            recovery_time_days=recovery_time,
            out_of_sample_degradation=oos_degradation,
            oos_passes=oos_passes,
            ruin_probability=mc_result.ruin_probability,
            ruin_passes=ruin_passes,
            all_checks_pass=all_pass,
            validation_messages=messages,
        )

    # =========================================================================
    # Legacy methods for backward compatibility
    # =========================================================================

    def validate(
        self,
        backtest_results: pd.DataFrame,
        model_metadata: Optional[Dict] = None,
    ) -> StatisticalValidationResult:
        """Run all statistical validations (legacy interface).

        Args:
            backtest_results: DataFrame containing backtest results
            model_metadata: Optional metadata about the model

        Returns:
            StatisticalValidationResult with all validation outcomes
        """
        result = StatisticalValidationResult()

        # Check 1: Sample size
        sample_check = self._check_sample_size(backtest_results, model_metadata)
        result.sample_size_adequate = sample_check["passed"]
        result.details["sample_size"] = sample_check
        if not sample_check["passed"]:
            result.passed = False
            result.failure_reasons.append(sample_check["reason"])

        # Check 2: Statistical significance of positive returns
        significance_check = self._check_significance(backtest_results)
        result.results_significant = significance_check["passed"]
        result.details["significance"] = significance_check
        if not significance_check["passed"]:
            result.passed = False
            result.failure_reasons.append(significance_check["reason"])

        # Check 3: Sharpe ratio threshold
        sharpe_check = self._check_sharpe_ratio(backtest_results)
        result.sharpe_adequate = sharpe_check["passed"]
        result.details["sharpe"] = sharpe_check
        if not sharpe_check["passed"]:
            result.passed = False
            result.failure_reasons.append(sharpe_check["reason"])

        return result

    def _check_sample_size(self, df: pd.DataFrame, metadata: Optional[Dict]) -> Dict:
        """Verify sample size is adequate for statistical conclusions."""
        n_bets = len(df)

        # Determine minimum based on bet type if available
        bet_type = metadata.get("bet_type", "default") if metadata else "default"
        min_required = self.MIN_SAMPLES.get(bet_type, self.min_sample_size)

        passed = n_bets >= min_required

        return {
            "passed": passed,
            "n_bets": n_bets,
            "min_required": min_required,
            "reason": (
                f"Sample size {n_bets} below minimum {min_required} required for "
                f"reliable statistical conclusions on {bet_type} bets."
                if not passed
                else None
            ),
        }

    def _check_significance(self, df: pd.DataFrame) -> Dict:
        """Test whether positive returns are statistically significant."""
        if "profit_loss" not in df.columns:
            return {
                "passed": True,
                "reason": "No profit_loss column to test",
                "p_value": None,
            }

        returns = df["profit_loss"].values

        if len(returns) < 30:
            return {
                "passed": False,
                "reason": "Insufficient data for significance testing (n < 30)",
                "p_value": None,
            }

        # Test H0: mean return = 0 vs H1: mean return > 0
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)
        n = len(returns)

        if std_return == 0:
            return {
                "passed": False,
                "reason": "Zero variance in returns - check for data issues",
                "p_value": None,
            }

        # t-statistic
        t_stat = mean_return / (std_return / np.sqrt(n))

        # One-sided p-value
        if HAS_SCIPY:
            p_value = 1 - stats.t.cdf(t_stat, df=n - 1)
        else:
            # Approximate using normal distribution for large n
            p_value = 1 - 0.5 * (1 + np.tanh(t_stat / np.sqrt(2)))

        passed = p_value < self.significance_level and mean_return > 0

        return {
            "passed": passed,
            "t_statistic": t_stat,
            "p_value": p_value,
            "mean_return": mean_return,
            "std_return": std_return,
            "reason": (
                f"Returns not statistically significant (p={p_value:.4f} >= "
                f"{self.significance_level}). Mean return: ${mean_return:.2f}"
                if not passed
                else None
            ),
        }

    def _check_sharpe_ratio(self, df: pd.DataFrame) -> Dict:
        """Verify Sharpe ratio meets minimum threshold."""
        if "profit_loss" not in df.columns or "stake" not in df.columns:
            return {
                "passed": True,
                "reason": "Missing columns for Sharpe calculation",
                "sharpe": None,
            }

        # Calculate returns per bet
        returns = df["profit_loss"] / df["stake"]

        if len(returns) < 30 or returns.std() == 0:
            return {
                "passed": False,
                "reason": "Insufficient data or zero variance for Sharpe calculation",
                "sharpe": None,
            }

        # Annualize assuming daily betting
        bets_per_year = 365

        mean_return = returns.mean()
        std_return = returns.std()

        sharpe = (mean_return / std_return) * np.sqrt(bets_per_year)
        passed = sharpe >= self.min_sharpe

        return {
            "passed": passed,
            "sharpe": sharpe,
            "min_sharpe": self.min_sharpe,
            "mean_return_per_bet": mean_return,
            "std_return_per_bet": std_return,
            "reason": (
                f"Sharpe ratio {sharpe:.2f} below minimum {self.min_sharpe}. "
                f"Risk-adjusted returns are insufficient."
                if not passed
                else None
            ),
        }

    def power_analysis(
        self,
        expected_edge: float = 0.02,
        std_dev: float = 1.0,
        alpha: float = 0.05,
        power: float = 0.80,
    ) -> int:
        """Calculate required sample size for detecting an edge.

        Args:
            expected_edge: Expected ROI/edge to detect
            std_dev: Standard deviation of returns (typically ~1 for unit bets)
            alpha: Significance level
            power: Desired statistical power

        Returns:
            Required sample size
        """
        if not HAS_SCIPY:
            # Rough approximation without scipy
            z_alpha = 1.645 if alpha == 0.05 else 1.96
            z_beta = 0.84 if power == 0.80 else 1.28
            return int(np.ceil(((z_alpha + z_beta) * std_dev / expected_edge) ** 2))

        from scipy.stats import norm

        z_alpha = norm.ppf(1 - alpha)
        z_beta = norm.ppf(power)

        n = ((z_alpha + z_beta) * std_dev / expected_edge) ** 2
        return int(np.ceil(n))

    def test_edge_vs_luck(
        self,
        df: pd.DataFrame,
        n_simulations: int = 10000,
    ) -> Dict:
        """Bootstrap test to determine if results are skill vs luck.

        Uses bootstrap simulation to compare observed performance
        against random chance.

        Args:
            df: DataFrame with backtest results
            n_simulations: Number of bootstrap samples

        Returns:
            Dictionary with test results
        """
        if "profit_loss" not in df.columns:
            return {"passed": False, "reason": "No profit_loss column"}

        observed_profit = df["profit_loss"].sum()
        profits = df["profit_loss"].values
        n = len(profits)

        # Bootstrap: resample with replacement
        np.random.seed(42)
        bootstrap_totals = np.array(
            [np.random.choice(profits, size=n, replace=True).sum() for _ in range(n_simulations)]
        )

        # What percentage of bootstrap samples beat our observed?
        percentile = np.mean(bootstrap_totals >= observed_profit) * 100

        # If observed is better than 95% of bootstraps, likely skill
        is_skill = percentile <= 5  # Top 5%

        return {
            "passed": is_skill,
            "observed_profit": observed_profit,
            "bootstrap_mean": np.mean(bootstrap_totals),
            "bootstrap_std": np.std(bootstrap_totals),
            "percentile_rank": 100 - percentile,
            "reason": (
                f"Observed profit ranks in top {100-percentile:.1f}% of bootstrap "
                f"samples. {'Likely skill-based edge.' if is_skill else 'May be luck-based.'}"
            ),
        }

    def format_validation_report(self, validation: StatisticalValidation) -> str:
        """Format validation results as a readable report.

        Args:
            validation: StatisticalValidation result

        Returns:
            Formatted string report
        """
        lines = []
        lines.append("=" * 70)
        lines.append("STATISTICAL VALIDATION REPORT")
        lines.append("=" * 70)

        status = "PASS" if validation.all_checks_pass else "FAIL"
        lines.append(f"\nOVERALL STATUS: {status}")
        lines.append("-" * 50)

        lines.append("\n1. SAMPLE SIZE")
        lines.append(f"   Count: {validation.sample_size}")
        lines.append(f"   Minimum: {self.min_sample_size}")
        lines.append(f"   Status: {'PASS' if validation.is_sufficient else 'FAIL'}")

        lines.append("\n2. CONFIDENCE INTERVALS (95%)")
        lines.append(
            f"   ROI: ({validation.confidence_interval_roi[0]:.4f}, "
            f"{validation.confidence_interval_roi[1]:.4f})"
        )
        lines.append(
            f"   CLV: ({validation.confidence_interval_clv[0]:.4f}, "
            f"{validation.confidence_interval_clv[1]:.4f})"
        )
        lines.append(
            f"   Win Rate: ({validation.confidence_interval_win_rate[0]:.4f}, "
            f"{validation.confidence_interval_win_rate[1]:.4f})"
        )

        lines.append("\n3. SHARPE RATIO")
        lines.append(f"   Value: {validation.sharpe_ratio:.2f}")
        lines.append(f"   Minimum: {self.min_sharpe}")
        lines.append(f"   Status: {'PASS' if validation.sharpe_passes else 'FAIL'}")

        lines.append("\n4. DRAWDOWN ANALYSIS")
        lines.append(f"   Max Drawdown: {validation.max_drawdown:.1%}")
        lines.append(f"   Recovery Time: {validation.recovery_time_days} periods")

        if validation.out_of_sample_degradation is not None:
            lines.append("\n5. OUT-OF-SAMPLE DEGRADATION")
            lines.append(f"   Degradation: {validation.out_of_sample_degradation:.1%}")
            lines.append(f"   Maximum: {self.max_oos_degradation:.0%}")
            lines.append(f"   Status: {'PASS' if validation.oos_passes else 'FAIL'}")

        lines.append("\n6. MONTE CARLO RUIN PROBABILITY")
        lines.append(f"   Ruin Probability: {validation.ruin_probability:.2%}")
        lines.append(f"   Maximum: {self.max_ruin_probability:.0%}")
        lines.append(f"   Status: {'PASS' if validation.ruin_passes else 'FAIL'}")

        lines.append("\n" + "-" * 50)
        lines.append("VALIDATION MESSAGES:")
        for msg in validation.validation_messages:
            lines.append(f"  - {msg}")

        lines.append("\n" + "=" * 70)

        if not validation.all_checks_pass:
            lines.append("WARNING: DO NOT DEPLOY - Statistical validation failed")
        else:
            lines.append("Model passed all statistical validation checks")

        lines.append("=" * 70)

        return "\n".join(lines)
