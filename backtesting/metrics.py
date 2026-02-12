"""Backtesting Metrics for Sports Betting Models.

This module provides comprehensive metrics for evaluating betting model performance.
The metrics are designed specifically for sports betting, where Closing Line Value (CLV)
is the PRIMARY indicator of long-term profitability.

Key Metrics:
    - CLV (Closing Line Value): THE most important metric
    - ROI (Return on Investment): Overall profitability
    - Brier Score: Probability calibration quality
    - Sharpe Ratio: Risk-adjusted returns
    - Win Rate by Confidence: Performance segmentation
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

# Import odds conversion utilities
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from betting.odds_converter import (  # noqa: E402
    calculate_clv,
)


@dataclass
class BettingMetrics:
    """Container for comprehensive betting metrics.

    Attributes:
        n_bets: Total number of bets
        n_wins: Number of winning bets
        n_losses: Number of losing bets
        n_pushes: Number of pushed bets
        win_rate: Overall win percentage
        roi: Return on Investment
        total_wagered: Total amount wagered
        total_profit: Net profit/loss
        avg_odds: Average odds (American format)
        avg_stake: Average stake per bet
        avg_clv: Average Closing Line Value (KEY METRIC)
        clv_positive_rate: Percentage of bets with positive CLV
        brier_score: Brier score for probability calibration
        log_loss: Logarithmic loss
        sharpe_ratio: Risk-adjusted returns
        max_drawdown: Maximum drawdown percentage
        longest_losing_streak: Longest consecutive losses
        longest_winning_streak: Longest consecutive wins
    """

    n_bets: int = 0
    n_wins: int = 0
    n_losses: int = 0
    n_pushes: int = 0
    win_rate: float = 0.0
    roi: float = 0.0
    total_wagered: float = 0.0
    total_profit: float = 0.0
    avg_odds: float = 0.0
    avg_stake: float = 0.0
    avg_clv: float = 0.0
    clv_positive_rate: float = 0.0
    brier_score: float = 0.0
    log_loss: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    longest_losing_streak: int = 0
    longest_winning_streak: int = 0
    metrics_by_confidence: Dict[str, Dict] = field(default_factory=dict)


def calculate_roi(stakes: np.ndarray, profits: np.ndarray, include_pushes: bool = False) -> float:
    """Calculate Return on Investment.

    ROI = Total Profit / Total Wagered

    Args:
        stakes: Array of bet stakes
        profits: Array of profit/loss values
        include_pushes: Whether to include pushed bets in denominator

    Returns:
        ROI as a decimal (0.05 = 5% ROI)

    Example:
        >>> stakes = np.array([100, 100, 100])
        >>> profits = np.array([91, -100, 91])  # 2 wins at -110, 1 loss
        >>> calculate_roi(stakes, profits)
        0.27333...  # 27.3% ROI
    """
    total_wagered = np.sum(stakes)

    if total_wagered == 0:
        return 0.0

    total_profit = np.sum(profits)
    return total_profit / total_wagered


def calculate_clv_metrics(
    odds_placed: np.ndarray,
    odds_closing: np.ndarray,
    weights: Optional[np.ndarray] = None,
) -> Dict[str, float]:
    """Calculate comprehensive CLV metrics.

    CLV (Closing Line Value) is THE PRIMARY predictor of long-term profitability.
    A bettor who consistently beats the closing line WILL profit over time.

    Args:
        odds_placed: Array of odds when bets were placed (American format)
        odds_closing: Array of closing odds (American format)
        weights: Optional weights for weighted average (e.g., stake amounts)

    Returns:
        Dictionary containing:
            - avg_clv: Average CLV
            - weighted_avg_clv: Stake-weighted average CLV
            - median_clv: Median CLV
            - clv_positive_rate: Percentage of bets with positive CLV
            - clv_std: Standard deviation of CLV
            - clv_by_direction: CLV segmented by favorite/underdog

    Example:
        >>> placed = np.array([-105, -110, +150])
        >>> closing = np.array([-110, -110, +140])
        >>> metrics = calculate_clv_metrics(placed, closing)
        >>> metrics['avg_clv']  # Positive = beating the closing line
    """
    if len(odds_placed) == 0:
        return {
            "avg_clv": 0.0,
            "weighted_avg_clv": 0.0,
            "median_clv": 0.0,
            "clv_positive_rate": 0.0,
            "clv_std": 0.0,
        }

    # Calculate CLV for each bet
    clv_values = np.array(
        [calculate_clv(int(p), int(c)) for p, c in zip(odds_placed, odds_closing)]
    )

    # Basic statistics
    avg_clv = np.mean(clv_values)
    median_clv = np.median(clv_values)
    clv_std = np.std(clv_values)
    clv_positive_rate = np.mean(clv_values > 0)

    # Weighted average if weights provided
    if weights is not None and len(weights) == len(clv_values):
        weighted_avg_clv = np.average(clv_values, weights=weights)
    else:
        weighted_avg_clv = avg_clv

    return {
        "avg_clv": avg_clv,
        "weighted_avg_clv": weighted_avg_clv,
        "median_clv": median_clv,
        "clv_positive_rate": clv_positive_rate,
        "clv_std": clv_std,
    }


def calculate_brier_score(probabilities: np.ndarray, outcomes: np.ndarray) -> float:
    """Calculate Brier score for probability calibration.

    Brier Score = mean((forecast - outcome)^2)

    Lower is better. A perfectly calibrated model has Brier score approaching 0.
    Random guessing (0.5 for binary outcomes) gives Brier score of 0.25.

    Target: < 0.125 (superforecaster level)

    Args:
        probabilities: Predicted probabilities (0 to 1)
        outcomes: Actual outcomes (0 or 1)

    Returns:
        Brier score (lower is better)

    Example:
        >>> probs = np.array([0.7, 0.3, 0.6, 0.8])
        >>> outcomes = np.array([1, 0, 1, 1])
        >>> calculate_brier_score(probs, outcomes)
        0.075  # Good calibration
    """
    if len(probabilities) != len(outcomes):
        raise ValueError("Length of probabilities and outcomes must match")

    if len(probabilities) == 0:
        return 0.0

    # Clip probabilities to valid range
    probs = np.clip(probabilities, 0.001, 0.999)

    return np.mean((probs - outcomes) ** 2)


def calculate_log_loss(
    probabilities: np.ndarray, outcomes: np.ndarray, eps: float = 1e-15
) -> float:
    """Calculate logarithmic loss (cross-entropy).

    Log Loss = -mean(y*log(p) + (1-y)*log(1-p))

    Args:
        probabilities: Predicted probabilities (0 to 1)
        outcomes: Actual outcomes (0 or 1)
        eps: Small value to avoid log(0)

    Returns:
        Log loss (lower is better)
    """
    if len(probabilities) != len(outcomes):
        raise ValueError("Length of probabilities and outcomes must match")

    if len(probabilities) == 0:
        return 0.0

    # Clip to avoid log(0)
    probs = np.clip(probabilities, eps, 1 - eps)
    outcomes = np.array(outcomes, dtype=float)

    return -np.mean(outcomes * np.log(probs) + (1 - outcomes) * np.log(1 - probs))


def calculate_calibration_error(
    probabilities: np.ndarray,
    outcomes: np.ndarray,
    n_bins: int = 10,
) -> Tuple[float, pd.DataFrame]:
    """Calculate calibration error across probability bins.

    Good calibration: when you predict 70%, events should occur ~70% of the time.

    Args:
        probabilities: Predicted probabilities
        outcomes: Actual outcomes (0 or 1)
        n_bins: Number of bins for calibration analysis

    Returns:
        Tuple of (mean absolute calibration error, calibration DataFrame)

    Example:
        >>> probs = np.random.uniform(0.3, 0.7, 100)
        >>> outcomes = (np.random.random(100) < probs).astype(int)
        >>> error, cal_df = calculate_calibration_error(probs, outcomes)
        >>> cal_df
        #   bin_lower  bin_upper  predicted  actual  count  error
        # 0      0.3      0.34      0.32     0.35     12   0.03
        # ...
    """
    if len(probabilities) == 0:
        return 0.0, pd.DataFrame()

    bin_edges = np.linspace(0, 1, n_bins + 1)
    calibration_data = []

    for i in range(n_bins):
        bin_lower = bin_edges[i]
        bin_upper = bin_edges[i + 1]

        mask = (probabilities >= bin_lower) & (probabilities < bin_upper)
        if i == n_bins - 1:  # Include 1.0 in last bin
            mask = (probabilities >= bin_lower) & (probabilities <= bin_upper)

        if mask.sum() > 0:
            predicted = probabilities[mask].mean()
            actual = outcomes[mask].mean()
            count = mask.sum()
            error = abs(predicted - actual)

            calibration_data.append(
                {
                    "bin_lower": bin_lower,
                    "bin_upper": bin_upper,
                    "predicted": predicted,
                    "actual": actual,
                    "count": count,
                    "error": error,
                }
            )

    cal_df = pd.DataFrame(calibration_data)

    if len(cal_df) == 0:
        return 0.0, cal_df

    # Weighted mean absolute error
    mean_error = np.average(cal_df["error"], weights=cal_df["count"])

    return mean_error, cal_df


def calculate_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 365,
) -> float:
    """Calculate Sharpe ratio for risk-adjusted returns.

    Sharpe Ratio = (Mean Return - Risk Free Rate) / Std Dev of Returns

    Args:
        returns: Array of period returns (as decimals, e.g., 0.05 for 5%)
        risk_free_rate: Annual risk-free rate (default 0)
        periods_per_year: Number of betting periods per year

    Returns:
        Annualized Sharpe ratio

    Example:
        >>> daily_returns = np.array([0.02, -0.01, 0.03, -0.02, 0.01])
        >>> calculate_sharpe_ratio(daily_returns)
    """
    if len(returns) == 0 or np.std(returns) == 0:
        return 0.0

    # Convert annual risk-free to per-period
    rf_per_period = risk_free_rate / periods_per_year

    excess_returns = returns - rf_per_period
    mean_excess = np.mean(excess_returns)
    std_returns = np.std(returns, ddof=1)

    if std_returns == 0:
        return 0.0

    # Annualize
    sharpe = (mean_excess / std_returns) * np.sqrt(periods_per_year)
    return sharpe


def calculate_drawdown_metrics(
    cumulative_pnl: np.ndarray,
) -> Dict[str, float]:
    """Calculate drawdown metrics from cumulative P&L series.

    Drawdown measures the peak-to-trough decline in cumulative returns,
    critical for understanding risk and bankroll requirements.

    Args:
        cumulative_pnl: Array of cumulative profit/loss

    Returns:
        Dictionary containing:
            - max_drawdown: Maximum drawdown as decimal
            - avg_drawdown: Average drawdown
            - max_drawdown_duration: Longest drawdown in periods
            - current_drawdown: Current drawdown from peak

    Example:
        >>> pnl = np.array([100, 150, 120, 80, 130, 140])
        >>> metrics = calculate_drawdown_metrics(pnl)
        >>> metrics['max_drawdown']  # (150 - 80) / 150 = 0.467
    """
    if len(cumulative_pnl) == 0:
        return {
            "max_drawdown": 0.0,
            "avg_drawdown": 0.0,
            "max_drawdown_duration": 0,
            "current_drawdown": 0.0,
        }

    # Running maximum
    running_max = np.maximum.accumulate(cumulative_pnl)

    # Drawdown at each point
    drawdowns = (running_max - cumulative_pnl) / np.maximum(running_max, 1e-10)
    drawdowns = np.clip(drawdowns, 0, 1)  # Clip to valid range

    max_drawdown = np.max(drawdowns)
    avg_drawdown = np.mean(drawdowns)
    current_drawdown = drawdowns[-1] if len(drawdowns) > 0 else 0.0

    # Calculate max drawdown duration
    in_drawdown = drawdowns > 0
    max_duration = 0
    current_duration = 0

    for is_dd in in_drawdown:
        if is_dd:
            current_duration += 1
            max_duration = max(max_duration, current_duration)
        else:
            current_duration = 0

    return {
        "max_drawdown": max_drawdown,
        "avg_drawdown": avg_drawdown,
        "max_drawdown_duration": max_duration,
        "current_drawdown": current_drawdown,
    }


def calculate_streak_metrics(results: np.ndarray) -> Dict[str, int]:
    """Calculate winning and losing streak statistics.

    Args:
        results: Array of bet results (1 = win, 0 = loss, 0.5 = push)

    Returns:
        Dictionary with streak statistics
    """
    if len(results) == 0:
        return {
            "longest_winning_streak": 0,
            "longest_losing_streak": 0,
            "current_streak": 0,
            "current_streak_type": "none",
        }

    # Filter out pushes for streak calculation
    non_push = results[results != 0.5]

    if len(non_push) == 0:
        return {
            "longest_winning_streak": 0,
            "longest_losing_streak": 0,
            "current_streak": 0,
            "current_streak_type": "none",
        }

    max_win_streak = 0
    max_lose_streak = 0
    current_win_streak = 0
    current_lose_streak = 0

    for result in non_push:
        if result == 1:  # Win
            current_win_streak += 1
            current_lose_streak = 0
            max_win_streak = max(max_win_streak, current_win_streak)
        else:  # Loss
            current_lose_streak += 1
            current_win_streak = 0
            max_lose_streak = max(max_lose_streak, current_lose_streak)

    # Current streak
    if current_win_streak > 0:
        current_streak = current_win_streak
        streak_type = "winning"
    elif current_lose_streak > 0:
        current_streak = current_lose_streak
        streak_type = "losing"
    else:
        current_streak = 0
        streak_type = "none"

    return {
        "longest_winning_streak": max_win_streak,
        "longest_losing_streak": max_lose_streak,
        "current_streak": current_streak,
        "current_streak_type": streak_type,
    }


def calculate_win_rate_by_confidence(
    model_probabilities: np.ndarray,
    outcomes: np.ndarray,
    stakes: np.ndarray,
    profits: np.ndarray,
    n_bins: int = 5,
) -> pd.DataFrame:
    """Calculate win rate and ROI segmented by model confidence.

    This helps identify if your model performs better on high-confidence
    or low-confidence plays, informing bet sizing strategy.

    Args:
        model_probabilities: Model's predicted win probabilities
        outcomes: Actual outcomes (1 = win, 0 = loss)
        stakes: Bet stakes
        profits: Profit/loss per bet
        n_bins: Number of confidence bins

    Returns:
        DataFrame with performance metrics by confidence level

    Example:
        >>> probs = np.array([0.55, 0.60, 0.75, 0.52, 0.68])
        >>> outcomes = np.array([1, 1, 1, 0, 1])
        >>> stakes = np.array([100, 100, 100, 100, 100])
        >>> profits = np.array([91, 91, 91, -100, 91])
        >>> df = calculate_win_rate_by_confidence(probs, outcomes, stakes, profits)
    """
    if len(model_probabilities) == 0:
        return pd.DataFrame()

    # Create confidence bins
    # Use model probability deviation from 0.5 as confidence
    confidence = np.abs(model_probabilities - 0.5)
    bin_edges = np.percentile(confidence, np.linspace(0, 100, n_bins + 1))
    bin_edges = np.unique(bin_edges)  # Remove duplicates

    if len(bin_edges) < 2:
        # All same confidence, create single bin
        bin_edges = np.array([confidence.min() - 0.01, confidence.max() + 0.01])

    results = []

    for i in range(len(bin_edges) - 1):
        lower = bin_edges[i]
        upper = bin_edges[i + 1]

        if i == len(bin_edges) - 2:  # Last bin includes upper bound
            mask = (confidence >= lower) & (confidence <= upper)
        else:
            mask = (confidence >= lower) & (confidence < upper)

        if mask.sum() == 0:
            continue

        bin_outcomes = outcomes[mask]
        bin_stakes = stakes[mask]
        bin_profits = profits[mask]
        bin_probs = model_probabilities[mask]

        results.append(
            {
                "confidence_lower": lower + 0.5,  # Convert back to probability
                "confidence_upper": upper + 0.5,
                "n_bets": mask.sum(),
                "win_rate": bin_outcomes.mean(),
                "avg_model_prob": bin_probs.mean(),
                "total_wagered": bin_stakes.sum(),
                "total_profit": bin_profits.sum(),
                "roi": bin_profits.sum() / bin_stakes.sum() if bin_stakes.sum() > 0 else 0,
            }
        )

    return pd.DataFrame(results)


def compute_all_metrics(
    bets_df: pd.DataFrame,
    stake_col: str = "stake",
    profit_col: str = "profit_loss",
    result_col: str = "result",
    odds_placed_col: str = "odds_placed",
    odds_closing_col: str = "odds_closing",
    model_prob_col: str = "model_probability",
    outcome_col: Optional[str] = None,
) -> BettingMetrics:
    """Compute comprehensive betting metrics from a DataFrame of bets.

    This is the main entry point for computing all relevant metrics.

    Args:
        bets_df: DataFrame containing bet records
        stake_col: Column name for stake amounts
        profit_col: Column name for profit/loss
        result_col: Column name for result (win/loss/push)
        odds_placed_col: Column name for odds when placed
        odds_closing_col: Column name for closing odds
        model_prob_col: Column name for model probability
        outcome_col: Optional column for binary outcome (1/0)

    Returns:
        BettingMetrics dataclass with all computed metrics
    """
    if len(bets_df) == 0:
        return BettingMetrics()

    metrics = BettingMetrics()

    # Basic counts
    metrics.n_bets = len(bets_df)
    metrics.n_wins = (bets_df[result_col] == "win").sum()
    metrics.n_losses = (bets_df[result_col] == "loss").sum()
    metrics.n_pushes = (bets_df[result_col] == "push").sum()

    # Win rate (excluding pushes)
    decided = metrics.n_wins + metrics.n_losses
    metrics.win_rate = metrics.n_wins / decided if decided > 0 else 0.0

    # Financials
    stakes = bets_df[stake_col].values
    profits = bets_df[profit_col].values

    metrics.total_wagered = stakes.sum()
    metrics.total_profit = profits.sum()
    metrics.avg_stake = stakes.mean()
    metrics.roi = calculate_roi(stakes, profits)

    # Average odds
    if odds_placed_col in bets_df.columns:
        metrics.avg_odds = bets_df[odds_placed_col].mean()

    # CLV metrics
    if odds_placed_col in bets_df.columns and odds_closing_col in bets_df.columns:
        # Filter out rows with missing closing odds
        clv_mask = bets_df[odds_closing_col].notna()
        if clv_mask.sum() > 0:
            clv_metrics = calculate_clv_metrics(
                bets_df.loc[clv_mask, odds_placed_col].values,
                bets_df.loc[clv_mask, odds_closing_col].values,
                bets_df.loc[clv_mask, stake_col].values,
            )
            metrics.avg_clv = clv_metrics["avg_clv"]
            metrics.clv_positive_rate = clv_metrics["clv_positive_rate"]

    # Probability calibration
    if model_prob_col in bets_df.columns:
        probs = bets_df[model_prob_col].values

        # Determine outcomes for Brier score
        if outcome_col and outcome_col in bets_df.columns:
            outcomes = bets_df[outcome_col].values
        else:
            # Convert result column to binary
            outcomes = (bets_df[result_col] == "win").astype(int).values

        metrics.brier_score = calculate_brier_score(probs, outcomes)
        metrics.log_loss = calculate_log_loss(probs, outcomes)

        # Win rate by confidence
        metrics.metrics_by_confidence = calculate_win_rate_by_confidence(
            probs, outcomes, stakes, profits
        ).to_dict("records")

    # Drawdown
    cumulative_pnl = np.cumsum(profits)
    dd_metrics = calculate_drawdown_metrics(cumulative_pnl)
    metrics.max_drawdown = dd_metrics["max_drawdown"]

    # Streaks
    result_numeric = bets_df[result_col].map({"win": 1, "loss": 0, "push": 0.5}).values
    streak_metrics = calculate_streak_metrics(result_numeric)
    metrics.longest_winning_streak = streak_metrics["longest_winning_streak"]
    metrics.longest_losing_streak = streak_metrics["longest_losing_streak"]

    # Sharpe ratio from daily returns
    if "game_date" in bets_df.columns:
        daily_profits = bets_df.groupby("game_date")[profit_col].sum()
        daily_stakes = bets_df.groupby("game_date")[stake_col].sum()
        daily_returns = (daily_profits / daily_stakes).fillna(0).values
        metrics.sharpe_ratio = calculate_sharpe_ratio(daily_returns)

    return metrics


def format_metrics_report(metrics: BettingMetrics) -> str:
    """Format metrics as a readable report.

    Args:
        metrics: BettingMetrics dataclass

    Returns:
        Formatted string report
    """
    report = []
    report.append("=" * 60)
    report.append("BETTING PERFORMANCE REPORT")
    report.append("=" * 60)

    report.append("\nOVERVIEW")
    report.append("-" * 40)
    report.append(f"Total Bets:      {metrics.n_bets}")
    report.append(f"Wins:            {metrics.n_wins}")
    report.append(f"Losses:          {metrics.n_losses}")
    report.append(f"Pushes:          {metrics.n_pushes}")
    report.append(f"Win Rate:        {metrics.win_rate:.1%}")

    report.append("\nFINANCIAL PERFORMANCE")
    report.append("-" * 40)
    report.append(f"Total Wagered:   ${metrics.total_wagered:,.2f}")
    report.append(f"Total Profit:    ${metrics.total_profit:,.2f}")
    report.append(f"ROI:             {metrics.roi:.2%}")
    report.append(f"Avg Stake:       ${metrics.avg_stake:,.2f}")

    report.append("\nKEY METRICS (CLV = Primary Success Indicator)")
    report.append("-" * 40)
    report.append(
        f"Average CLV:     {metrics.avg_clv:.2%} {'[GOOD]' if metrics.avg_clv > 0 else '[NEEDS WORK]'}"
    )
    report.append(f"CLV+ Rate:       {metrics.clv_positive_rate:.1%}")

    report.append("\nPROBABILITY CALIBRATION")
    report.append("-" * 40)
    report.append(f"Brier Score:     {metrics.brier_score:.4f} (target: < 0.125)")
    report.append(f"Log Loss:        {metrics.log_loss:.4f}")

    report.append("\nRISK METRICS")
    report.append("-" * 40)
    report.append(f"Max Drawdown:    {metrics.max_drawdown:.1%}")
    report.append(f"Sharpe Ratio:    {metrics.sharpe_ratio:.2f}")
    report.append(f"Longest Win Streak:  {metrics.longest_winning_streak}")
    report.append(f"Longest Loss Streak: {metrics.longest_losing_streak}")

    report.append("\n" + "=" * 60)

    return "\n".join(report)
