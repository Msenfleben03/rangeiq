"""Odds Conversion Utilities.

Converts between different odds formats (American, Decimal, Implied Probability)
and calculates key betting metrics like expected value and closing line value.
"""

from __future__ import annotations

from typing import Any


def american_to_decimal(american: int) -> float:
    """Convert American odds to decimal odds.

    Args:
        american: American odds (e.g., -110, +150). Must be non-zero.

    Returns:
        Decimal odds

    Raises:
        ValueError: If american is 0 (invalid odds).

    Examples:
        >>> american_to_decimal(-110)
        1.9090909090909092
        >>> american_to_decimal(+150)
        2.5
    """
    if american == 0:
        raise ValueError("American odds cannot be 0")
    if american > 0:
        return (american / 100) + 1
    return (100 / abs(american)) + 1


def american_to_implied_prob(american: int) -> float:
    """Convert American odds to implied probability.

    Args:
        american: American odds. Must be non-zero.

    Returns:
        Implied probability (0 to 1)

    Raises:
        ValueError: If american is 0 (invalid odds).

    Examples:
        >>> american_to_implied_prob(-110)
        0.5238095238095238
        >>> american_to_implied_prob(+150)
        0.4
    """
    if american == 0:
        raise ValueError("American odds cannot be 0")
    if american > 0:
        return 100 / (american + 100)
    return abs(american) / (abs(american) + 100)


def decimal_to_american(decimal: float) -> int:
    """Convert decimal odds to American odds.

    Args:
        decimal: Decimal odds

    Returns:
        American odds

    Examples:
        >>> decimal_to_american(1.91)
        -109
        >>> decimal_to_american(2.5)
        150
    """
    if decimal >= 2.0:
        return int((decimal - 1) * 100)
    return int(-100 / (decimal - 1))


def expected_value(win_prob: float, profit_if_win: float, stake: float) -> float:
    """Calculate expected value of a bet.

    EV = (p × profit) - (q × stake)

    Args:
        win_prob: Probability of winning (0 to 1)
        profit_if_win: Profit if bet wins
        stake: Amount wagered

    Returns:
        Expected value

    Examples:
        >>> expected_value(0.55, 100, 100)
        10.0
    """
    return (win_prob * profit_if_win) - ((1 - win_prob) * stake)


def calculate_edge(model_prob: float, american_odds: int) -> float:
    """Calculate edge: model probability minus implied probability.

    Args:
        model_prob: Model's win probability (0 to 1)
        american_odds: Current odds

    Returns:
        Edge (positive = favorable bet)

    Examples:
        >>> calculate_edge(0.55, -110)
        0.02619047619047622
    """
    implied = american_to_implied_prob(american_odds)
    return model_prob - implied


def calculate_clv(odds_placed: int, odds_closing: int) -> float:
    """Calculate Closing Line Value.

    CLV is THE KEY PREDICTOR of long-term profitability.
    Positive CLV = got better odds than market closed at.

    Args:
        odds_placed: Odds when bet was placed
        odds_closing: Odds when market closed

    Returns:
        CLV as a percentage (positive = good)

    Examples:
        >>> calculate_clv(-105, -110)
        0.009569377990430622  # Got better odds!
        >>> calculate_clv(-110, -105)
        -0.009615384615384581  # Got worse odds
    """
    prob_placed = american_to_implied_prob(odds_placed)
    prob_closing = american_to_implied_prob(odds_closing)
    return (prob_closing - prob_placed) / prob_placed


def fractional_kelly(
    win_prob: float, decimal_odds: float, fraction: float = 0.25, max_bet: float = 0.03
) -> float:
    """Conservative fractional Kelly bet sizing.

    ALWAYS use fractional Kelly - full Kelly is too aggressive.

    Args:
        win_prob: Probability of winning (0 to 1)
        decimal_odds: Decimal odds
        fraction: Kelly fraction (default 0.25 = quarter Kelly)
        max_bet: Maximum bet as fraction of bankroll (default 3%)

    Returns:
        Recommended bet size as fraction of bankroll

    Examples:
        >>> fractional_kelly(0.55, 2.0, fraction=0.25)
        0.025
    """
    b = decimal_odds - 1
    q = 1 - win_prob

    if b <= 0:
        return 0.0

    kelly = (b * win_prob - q) / b
    recommended = max(0, kelly * fraction)
    return min(recommended, max_bet)


class KellySizer:
    """Dynamic bet sizer with Platt-calibrated win probabilities.

    Uses logistic regression on historical (edge, win/loss) data to correct
    model overconfidence before feeding into Kelly criterion.

    Args:
        kelly_fraction: Fraction of full Kelly to use (default 0.25 = quarter).
        max_bet_fraction: Max bet as fraction of bankroll (default 0.05 = 5%).
        bankroll: Current bankroll in dollars (default 5000).
        min_bet: Minimum bet in dollars; smaller stakes round to 0 (default 10).
    """

    def __init__(
        self,
        kelly_fraction: float = 0.25,
        max_bet_fraction: float = 0.05,
        bankroll: float = 5000.0,
        min_bet: float = 10.0,
    ) -> None:
        """Initialize KellySizer with bet-sizing parameters."""
        self.kelly_fraction = kelly_fraction
        self.max_bet_fraction = max_bet_fraction
        self.bankroll = bankroll
        self.min_bet = min_bet
        self._calibrator = None

    @property
    def is_calibrated(self) -> bool:
        """Whether Platt calibration has been fitted."""
        return self._calibrator is not None

    def calibrate(self, edges: Any, outcomes: Any) -> None:
        """Fit Platt scaling on historical edge -> win/loss data.

        Args:
            edges: Array of model edge values (0 to 1).
            outcomes: Array of 1 (win) / 0 (loss).
        """
        from sklearn.linear_model import LogisticRegression

        X = edges.reshape(-1, 1) if edges.ndim == 1 else edges
        self._calibrator = LogisticRegression(random_state=42)
        self._calibrator.fit(X, outcomes)

    def calibrated_win_prob(self, edge: float) -> float | None:
        """Return calibrated P(win) for a given edge, or None if uncalibrated.

        Args:
            edge: Model edge value (model_prob - implied_prob).

        Returns:
            Calibrated win probability, or None if not yet calibrated.
        """
        if self._calibrator is None:
            return None
        import numpy as np

        return float(self._calibrator.predict_proba(np.array([[edge]]))[0][1])

    def size_bet(
        self,
        model_prob: float,
        edge: float,
        american_odds: int,
    ) -> float:
        """Calculate stake in dollars using calibrated Kelly.

        If calibrated, uses calibrated P(win) from edge.
        If uncalibrated, falls back to raw model_prob.

        Args:
            model_prob: Raw model win probability (fallback if uncalibrated).
            edge: Model edge (model_prob - implied_prob).
            american_odds: American odds for the bet.

        Returns:
            Stake in dollars (0.0 if bet not recommended).
        """
        cal_prob = self.calibrated_win_prob(edge)
        win_prob = cal_prob if cal_prob is not None else model_prob

        decimal_odds = american_to_decimal(american_odds)
        bet_frac = fractional_kelly(
            win_prob, decimal_odds, self.kelly_fraction, self.max_bet_fraction
        )
        stake = self.bankroll * bet_frac

        if stake < self.min_bet:
            return 0.0
        return round(stake, 2)


# Break-even win rates for common odds
BREAKEVEN_RATES = {-110: 0.5238, -105: 0.5122, +100: 0.5000, +150: 0.4000, -200: 0.6667}


if __name__ == "__main__":
    # Test conversions
    print("Odds Conversion Examples:")
    print(f"  -110 American = {american_to_decimal(-110):.3f} Decimal")
    print(f"  -110 American = {american_to_implied_prob(-110):.1%} Implied Prob")
    print(f"  +150 American = {american_to_decimal(+150):.3f} Decimal")
    print(f"  +150 American = {american_to_implied_prob(+150):.1%} Implied Prob")

    print("\nExpected Value Example:")
    ev = expected_value(0.55, 100, 100)
    print("  Win Prob: 55%, Profit if win: $100, Stake: $100")
    print(f"  Expected Value: ${ev:.2f}")

    print("\nCLV Example:")
    clv = calculate_clv(-105, -110)
    print("  Placed at -105, Closed at -110")
    print(f"  CLV: {clv:.2%} (Positive = Good!)")

    print("\nKelly Bet Sizing:")
    bet_size = fractional_kelly(0.55, 2.0, fraction=0.25)
    print("  Win Prob: 55%, Decimal Odds: 2.0, Quarter Kelly")
    print(f"  Recommended: {bet_size:.1%} of bankroll")
