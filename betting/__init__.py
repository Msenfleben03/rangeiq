"""Betting utilities and tools.

Core Modules:
- odds_converter: Odds format conversion and EV calculations
- arb_detector: Lightweight cross-book arbitrage detection (optional)
"""

from betting.odds_converter import (
    american_to_decimal,
    american_to_implied_prob,
    calculate_clv,
    calculate_edge,
    decimal_to_american,
    expected_value,
    fractional_kelly,
)

# Optional: Arb detection (import only if needed)
# from betting.arb_detector import ArbDetector, ArbOpportunity

__all__ = [
    # Odds conversion
    "american_to_decimal",
    "american_to_implied_prob",
    "decimal_to_american",
    # Betting math
    "expected_value",
    "calculate_edge",
    "calculate_clv",
    "fractional_kelly",
]
