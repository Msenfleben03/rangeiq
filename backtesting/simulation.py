"""Monte Carlo Simulation for Sports Betting.

This module provides simulation tools for:
    - Projecting bankroll trajectories
    - Calculating confidence intervals on expected returns
    - Analyzing drawdown distributions
    - Validating Kelly criterion sizing
    - Risk of ruin analysis

Use these simulations to:
    1. Understand variance in your strategy
    2. Set appropriate bankroll requirements
    3. Validate bet sizing strategy
    4. Estimate probability of hitting various profit/loss thresholds
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# scipy is optional - only needed for advanced statistics
try:
    from scipy import stats  # noqa: F401

    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from betting.odds_converter import american_to_decimal, fractional_kelly  # noqa: E402


@dataclass
class SimulationConfig:
    """Configuration for Monte Carlo simulation.

    Attributes:
        n_simulations: Number of simulation paths to generate
        n_bets: Number of bets to simulate per path
        initial_bankroll: Starting bankroll amount
        random_seed: Seed for reproducibility
        use_kelly: Whether to use Kelly criterion for sizing
        kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
        max_bet_fraction: Maximum bet as fraction of bankroll
        min_bet: Minimum bet size (absolute)
        stop_loss_fraction: Fraction of bankroll loss to stop betting
    """

    n_simulations: int = 10000
    n_bets: int = 1000
    initial_bankroll: float = 5000.0
    random_seed: Optional[int] = 42
    use_kelly: bool = True
    kelly_fraction: float = 0.25
    max_bet_fraction: float = 0.03
    min_bet: float = 10.0
    stop_loss_fraction: float = 0.5  # Stop if lose 50% of bankroll


@dataclass
class SimulationResult:
    """Results from Monte Carlo simulation.

    Attributes:
        config: Configuration used for simulation
        final_bankrolls: Array of final bankroll values
        bankroll_paths: Optional full paths (memory intensive)
        max_drawdowns: Maximum drawdown per simulation
        bust_rate: Percentage of simulations that went bust
        profit_rate: Percentage of simulations that profited
        expected_value: Mean final bankroll
        median_value: Median final bankroll
        percentiles: Dictionary of key percentiles
        roi_distribution: ROI for each simulation
    """

    config: SimulationConfig
    final_bankrolls: np.ndarray
    bankroll_paths: Optional[np.ndarray] = None
    max_drawdowns: np.ndarray = field(default_factory=lambda: np.array([]))
    bust_rate: float = 0.0
    profit_rate: float = 0.0
    expected_value: float = 0.0
    median_value: float = 0.0
    percentiles: Dict[int, float] = field(default_factory=dict)
    roi_distribution: np.ndarray = field(default_factory=lambda: np.array([]))


class MonteCarloSimulator:
    """Monte Carlo simulator for betting bankroll projections.

    This simulator generates thousands of possible bankroll paths to understand
    the distribution of outcomes for your betting strategy.

    Example:
        ```python
        # Define your betting edge and typical odds
        simulator = MonteCarloSimulator(
            win_probability=0.54,
            avg_odds=-110,
            config=SimulationConfig(
                n_simulations=10000,
                n_bets=500,
                initial_bankroll=5000
            )
        )

        results = simulator.run()
        print(f"Expected ROI: {results.expected_value / 5000 - 1:.1%}")
        print(f"95% CI: ${results.percentiles[5]:,.0f} - ${results.percentiles[95]:,.0f}")
        print(f"Bust rate: {results.bust_rate:.1%}")
        ```
    """

    def __init__(
        self,
        win_probability: float,
        avg_odds: int = -110,
        config: Optional[SimulationConfig] = None,
    ):
        """Initialize the simulator.

        Args:
            win_probability: True win probability of bets
            avg_odds: Average American odds
            config: Simulation configuration
        """
        self.win_probability = win_probability
        self.avg_odds = avg_odds
        self.decimal_odds = american_to_decimal(avg_odds)
        self.config = config or SimulationConfig()

        if self.config.random_seed is not None:
            np.random.seed(self.config.random_seed)

    def _calculate_bet_size(
        self, current_bankroll: float, win_prob: float, decimal_odds: float
    ) -> float:
        """Calculate bet size using Kelly criterion or fixed fraction.

        Args:
            current_bankroll: Current bankroll amount
            win_prob: Win probability
            decimal_odds: Decimal odds

        Returns:
            Bet size in dollars
        """
        if self.config.use_kelly:
            kelly_frac = fractional_kelly(
                win_prob,
                decimal_odds,
                fraction=self.config.kelly_fraction,
                max_bet=self.config.max_bet_fraction,
            )
            bet_size = current_bankroll * kelly_frac
        else:
            # Fixed fraction
            bet_size = current_bankroll * self.config.max_bet_fraction

        # Apply minimum bet constraint
        return max(bet_size, self.config.min_bet)

    def run(self, store_paths: bool = False) -> SimulationResult:
        """Run Monte Carlo simulation.

        Args:
            store_paths: Whether to store full bankroll paths (memory intensive)

        Returns:
            SimulationResult with all metrics
        """
        n_sims = self.config.n_simulations
        n_bets = self.config.n_bets
        initial = self.config.initial_bankroll

        final_bankrolls = np.zeros(n_sims)
        max_drawdowns = np.zeros(n_sims)

        if store_paths:
            all_paths = np.zeros((n_sims, n_bets + 1))

        # Generate all random outcomes at once for efficiency
        outcomes = np.random.random((n_sims, n_bets)) < self.win_probability

        for sim in range(n_sims):
            bankroll = initial
            peak_bankroll = initial
            max_dd = 0.0

            if store_paths:
                all_paths[sim, 0] = bankroll

            for bet_idx in range(n_bets):
                # Check stop loss
                if bankroll < initial * self.config.stop_loss_fraction:
                    # Bankroll too low, stop betting
                    if store_paths:
                        all_paths[sim, bet_idx + 1 :] = bankroll
                    break

                # Calculate bet size
                bet_size = self._calculate_bet_size(
                    bankroll, self.win_probability, self.decimal_odds
                )

                # Can't bet more than we have
                bet_size = min(bet_size, bankroll)

                # Simulate outcome
                if outcomes[sim, bet_idx]:
                    # Win: profit = bet * (decimal_odds - 1)
                    profit = bet_size * (self.decimal_odds - 1)
                else:
                    # Loss: lose the stake
                    profit = -bet_size

                bankroll += profit

                # Track peak and drawdown
                if bankroll > peak_bankroll:
                    peak_bankroll = bankroll

                current_dd = (peak_bankroll - bankroll) / peak_bankroll if peak_bankroll > 0 else 0
                max_dd = max(max_dd, current_dd)

                if store_paths:
                    all_paths[sim, bet_idx + 1] = bankroll

            final_bankrolls[sim] = bankroll
            max_drawdowns[sim] = max_dd

        # Calculate statistics
        result = SimulationResult(
            config=self.config,
            final_bankrolls=final_bankrolls,
            max_drawdowns=max_drawdowns,
        )

        if store_paths:
            result.bankroll_paths = all_paths

        # Bust = lost 50%+ of initial bankroll
        result.bust_rate = np.mean(final_bankrolls < initial * 0.5)
        result.profit_rate = np.mean(final_bankrolls > initial)

        result.expected_value = np.mean(final_bankrolls)
        result.median_value = np.median(final_bankrolls)

        # Key percentiles
        result.percentiles = {
            1: np.percentile(final_bankrolls, 1),
            5: np.percentile(final_bankrolls, 5),
            10: np.percentile(final_bankrolls, 10),
            25: np.percentile(final_bankrolls, 25),
            50: np.percentile(final_bankrolls, 50),
            75: np.percentile(final_bankrolls, 75),
            90: np.percentile(final_bankrolls, 90),
            95: np.percentile(final_bankrolls, 95),
            99: np.percentile(final_bankrolls, 99),
        }

        # ROI distribution
        result.roi_distribution = (final_bankrolls - initial) / initial

        return result


def run_drawdown_analysis(
    win_probability: float,
    avg_odds: int = -110,
    bankroll: float = 5000.0,
    n_bets: int = 1000,
    n_simulations: int = 10000,
    kelly_fraction: float = 0.25,
) -> Dict[str, float]:
    """Analyze drawdown distribution for a betting strategy.

    This helps set realistic expectations for the inevitable losing streaks.

    Args:
        win_probability: True win probability
        avg_odds: Average American odds
        bankroll: Starting bankroll
        n_bets: Number of bets to simulate
        n_simulations: Number of simulation paths
        kelly_fraction: Fraction of Kelly to use

    Returns:
        Dictionary with drawdown statistics

    Example:
        >>> stats = run_drawdown_analysis(0.54, -110, 5000, 500)
        >>> print(f"Expected max drawdown: {stats['expected_max_dd']:.1%}")
        >>> print(f"95% chance drawdown stays under: {stats['dd_95th']:.1%}")
    """
    config = SimulationConfig(
        n_simulations=n_simulations,
        n_bets=n_bets,
        initial_bankroll=bankroll,
        kelly_fraction=kelly_fraction,
    )

    simulator = MonteCarloSimulator(win_probability, avg_odds, config)
    results = simulator.run()

    return {
        "expected_max_dd": np.mean(results.max_drawdowns),
        "median_max_dd": np.median(results.max_drawdowns),
        "dd_5th": np.percentile(results.max_drawdowns, 5),
        "dd_25th": np.percentile(results.max_drawdowns, 25),
        "dd_75th": np.percentile(results.max_drawdowns, 75),
        "dd_95th": np.percentile(results.max_drawdowns, 95),
        "dd_99th": np.percentile(results.max_drawdowns, 99),
        "prob_dd_over_20pct": np.mean(results.max_drawdowns > 0.20),
        "prob_dd_over_30pct": np.mean(results.max_drawdowns > 0.30),
        "prob_dd_over_50pct": np.mean(results.max_drawdowns > 0.50),
    }


def calculate_risk_of_ruin(
    win_probability: float,
    avg_odds: int = -110,
    bankroll: float = 5000.0,
    bet_size: float = 100.0,
    ruin_threshold: float = 0.1,  # 10% of bankroll = ruin
    n_bets: int = 1000,
    n_simulations: int = 10000,
) -> Dict[str, float]:
    """Calculate probability of ruin for fixed bet sizing.

    Risk of ruin is the probability of losing a specified percentage of
    your bankroll over a given number of bets.

    Args:
        win_probability: True win probability
        avg_odds: Average American odds
        bankroll: Starting bankroll
        bet_size: Fixed bet size
        ruin_threshold: Fraction of bankroll considered ruin
        n_bets: Number of bets to simulate
        n_simulations: Number of paths to simulate

    Returns:
        Dictionary with risk metrics

    Example:
        >>> risk = calculate_risk_of_ruin(0.54, -110, 5000, 100)
        >>> print(f"Risk of ruin (90% loss): {risk['risk_of_ruin']:.2%}")
    """
    np.random.seed(42)

    decimal_odds = american_to_decimal(avg_odds)
    _profit_if_win = bet_size * (decimal_odds - 1)  # noqa: F841

    ruin_level = bankroll * ruin_threshold
    ruin_count = 0

    for _ in range(n_simulations):
        current = bankroll
        min_bankroll = bankroll

        for _ in range(n_bets):
            if current <= ruin_level:
                break

            actual_bet = min(bet_size, current)

            if np.random.random() < win_probability:
                current += actual_bet * (decimal_odds - 1)
            else:
                current -= actual_bet

            min_bankroll = min(min_bankroll, current)

        if min_bankroll <= ruin_level:
            ruin_count += 1

    risk = ruin_count / n_simulations

    return {
        "risk_of_ruin": risk,
        "survival_rate": 1 - risk,
        "ruin_threshold_pct": ruin_threshold,
        "ruin_threshold_dollars": ruin_level,
        "n_bets": n_bets,
        "win_probability": win_probability,
        "bet_size": bet_size,
    }


def validate_kelly_fraction(
    win_probability: float,
    avg_odds: int = -110,
    bankroll: float = 5000.0,
    kelly_fractions: List[float] = None,
    n_bets: int = 500,
    n_simulations: int = 5000,
) -> pd.DataFrame:
    """Compare different Kelly fractions to find optimal sizing.

    Full Kelly maximizes long-term growth but has high variance.
    Fractional Kelly reduces variance at the cost of growth rate.

    Args:
        win_probability: True win probability
        avg_odds: Average American odds
        bankroll: Starting bankroll
        kelly_fractions: List of Kelly fractions to test
        n_bets: Number of bets per simulation
        n_simulations: Number of simulations per fraction

    Returns:
        DataFrame comparing each Kelly fraction

    Example:
        >>> comparison = validate_kelly_fraction(0.54, -110, 5000)
        >>> print(comparison)
        #   fraction  expected_value  median_value  max_drawdown  bust_rate
        # 0     0.10          6500.0        6200.0          0.08       0.01
        # 1     0.25          8200.0        7100.0          0.15       0.03
        # 2     0.50         12000.0        8500.0          0.28       0.08
        # 3     1.00         25000.0        9200.0          0.45       0.22
    """
    if kelly_fractions is None:
        kelly_fractions = [0.10, 0.15, 0.25, 0.33, 0.50, 0.75, 1.00]

    results = []

    for fraction in kelly_fractions:
        config = SimulationConfig(
            n_simulations=n_simulations,
            n_bets=n_bets,
            initial_bankroll=bankroll,
            kelly_fraction=fraction,
            use_kelly=True,
        )

        simulator = MonteCarloSimulator(win_probability, avg_odds, config)
        sim_result = simulator.run()

        results.append(
            {
                "kelly_fraction": fraction,
                "expected_value": sim_result.expected_value,
                "median_value": sim_result.median_value,
                "expected_roi": (sim_result.expected_value - bankroll) / bankroll,
                "median_roi": (sim_result.median_value - bankroll) / bankroll,
                "avg_max_drawdown": np.mean(sim_result.max_drawdowns),
                "median_max_drawdown": np.median(sim_result.max_drawdowns),
                "p95_max_drawdown": np.percentile(sim_result.max_drawdowns, 95),
                "bust_rate": sim_result.bust_rate,
                "profit_rate": sim_result.profit_rate,
                "p5_final": sim_result.percentiles[5],
                "p95_final": sim_result.percentiles[95],
            }
        )

    return pd.DataFrame(results)


def calculate_confidence_intervals(
    win_probability: float,
    avg_odds: int = -110,
    bankroll: float = 5000.0,
    n_bets: int = 500,
    n_simulations: int = 10000,
    confidence_levels: List[float] = None,
) -> Dict[str, Tuple[float, float]]:
    """Calculate confidence intervals for final bankroll.

    Args:
        win_probability: True win probability
        avg_odds: Average American odds
        bankroll: Starting bankroll
        n_bets: Number of bets
        n_simulations: Number of simulations
        confidence_levels: List of confidence levels (e.g., [0.90, 0.95, 0.99])

    Returns:
        Dictionary mapping confidence level to (lower, upper) bounds

    Example:
        >>> ci = calculate_confidence_intervals(0.54, -110, 5000, 500)
        >>> print(f"95% CI: ${ci[0.95][0]:,.0f} to ${ci[0.95][1]:,.0f}")
    """
    if confidence_levels is None:
        confidence_levels = [0.50, 0.80, 0.90, 0.95, 0.99]

    config = SimulationConfig(
        n_simulations=n_simulations,
        n_bets=n_bets,
        initial_bankroll=bankroll,
    )

    simulator = MonteCarloSimulator(win_probability, avg_odds, config)
    results = simulator.run()

    intervals = {}

    for level in confidence_levels:
        lower_pct = (1 - level) / 2 * 100
        upper_pct = (1 + level) / 2 * 100

        lower = np.percentile(results.final_bankrolls, lower_pct)
        upper = np.percentile(results.final_bankrolls, upper_pct)

        intervals[level] = (lower, upper)

    return intervals


def simulate_from_backtest(
    backtest_results: pd.DataFrame,
    bankroll: float = 5000.0,
    n_simulations: int = 10000,
    stake_col: str = "stake",
    profit_col: str = "profit_loss",
    model_prob_col: str = "model_probability",
    odds_col: str = "odds_placed",
) -> SimulationResult:
    """Run simulation using actual backtest distribution.

    Instead of assuming a single win probability, this samples from the
    actual distribution of bets in your backtest results.

    Args:
        backtest_results: DataFrame with backtest results
        bankroll: Starting bankroll
        n_simulations: Number of simulation paths
        stake_col: Column name for stakes
        profit_col: Column name for profits
        model_prob_col: Column name for model probability
        odds_col: Column name for odds

    Returns:
        SimulationResult based on empirical distribution
    """
    if len(backtest_results) == 0:
        raise ValueError("Backtest results cannot be empty")

    n_bets = len(backtest_results)
    initial = bankroll

    # Extract the distribution of outcomes
    profits_dist = backtest_results[profit_col].values
    stakes_dist = backtest_results[stake_col].values

    # Calculate win rates for each bet based on actual outcome
    # A bet is a "win" if profit > 0
    _outcomes = (profits_dist > 0).astype(int)  # noqa: F841

    final_bankrolls = np.zeros(n_simulations)
    max_drawdowns = np.zeros(n_simulations)

    np.random.seed(42)

    for sim in range(n_simulations):
        # Bootstrap sample from actual results
        indices = np.random.choice(len(backtest_results), size=n_bets, replace=True)
        sampled_profits = profits_dist[indices]
        sampled_stakes = stakes_dist[indices]

        # Scale stakes to current bankroll proportion
        stake_fractions = sampled_stakes / sampled_stakes.mean()

        current = initial
        peak = initial
        max_dd = 0.0

        for i in range(n_bets):
            # Scale bet to current bankroll
            bet_fraction = stake_fractions[i] / n_bets * 10  # Normalize
            bet_fraction = min(bet_fraction, 0.03)  # Cap at 3%
            actual_stake = current * bet_fraction

            # Scale profit/loss proportionally
            if sampled_stakes[i] > 0:
                profit_ratio = sampled_profits[i] / sampled_stakes[i]
                profit = actual_stake * profit_ratio
            else:
                profit = 0

            current += profit

            if current > peak:
                peak = current

            dd = (peak - current) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

            if current <= 0:
                break

        final_bankrolls[sim] = max(current, 0)
        max_drawdowns[sim] = max_dd

    config = SimulationConfig(
        n_simulations=n_simulations,
        n_bets=n_bets,
        initial_bankroll=bankroll,
    )

    result = SimulationResult(
        config=config,
        final_bankrolls=final_bankrolls,
        max_drawdowns=max_drawdowns,
    )

    result.bust_rate = np.mean(final_bankrolls < initial * 0.5)
    result.profit_rate = np.mean(final_bankrolls > initial)
    result.expected_value = np.mean(final_bankrolls)
    result.median_value = np.median(final_bankrolls)

    result.percentiles = {
        1: np.percentile(final_bankrolls, 1),
        5: np.percentile(final_bankrolls, 5),
        10: np.percentile(final_bankrolls, 10),
        25: np.percentile(final_bankrolls, 25),
        50: np.percentile(final_bankrolls, 50),
        75: np.percentile(final_bankrolls, 75),
        90: np.percentile(final_bankrolls, 90),
        95: np.percentile(final_bankrolls, 95),
        99: np.percentile(final_bankrolls, 99),
    }

    result.roi_distribution = (final_bankrolls - initial) / initial

    return result


def format_simulation_report(result: SimulationResult) -> str:
    """Format simulation results as a readable report.

    Args:
        result: SimulationResult from Monte Carlo simulation

    Returns:
        Formatted string report
    """
    initial = result.config.initial_bankroll

    report = []
    report.append("=" * 60)
    report.append("MONTE CARLO SIMULATION REPORT")
    report.append("=" * 60)

    report.append("\nConfiguration:")
    report.append(f"  Simulations:      {result.config.n_simulations:,}")
    report.append(f"  Bets per path:    {result.config.n_bets:,}")
    report.append(f"  Initial bankroll: ${initial:,.2f}")
    report.append(f"  Kelly fraction:   {result.config.kelly_fraction:.0%}")

    report.append("\nExpected Outcomes:")
    report.append(f"  Expected final:   ${result.expected_value:,.2f}")
    report.append(f"  Median final:     ${result.median_value:,.2f}")

    expected_roi = (result.expected_value - initial) / initial
    median_roi = (result.median_value - initial) / initial
    report.append(f"  Expected ROI:     {expected_roi:.1%}")
    report.append(f"  Median ROI:       {median_roi:.1%}")

    report.append("\nRisk Metrics:")
    report.append(f"  Profit rate:      {result.profit_rate:.1%}")
    report.append(f"  Bust rate:        {result.bust_rate:.1%}")
    report.append(f"  Avg max drawdown: {np.mean(result.max_drawdowns):.1%}")

    report.append("\nConfidence Intervals (Final Bankroll):")
    for pct, val in sorted(result.percentiles.items()):
        roi = (val - initial) / initial
        report.append(f"  {pct:3d}th percentile: ${val:>10,.2f} (ROI: {roi:+.1%})")

    report.append("\n" + "=" * 60)

    return "\n".join(report)
