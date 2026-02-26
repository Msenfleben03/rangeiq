"""Poisson run distribution model for MLB game predictions.

Core model that projects expected runs (lambda) per team and derives:
- Moneyline win probabilities
- Run line probabilities (±1.5)
- Total (over/under) probabilities
- First-5-innings variants of all above

Architecture:
    1. Compute lambda_home and lambda_away from pitcher matchup + lineup + context
    2. Build Poisson score matrix (0-0 through ~15-15)
    3. Sum matrix cells for each market type

References:
    - Research doc: docs/mlb/MODEL_ARCHITECTURE.md
    - Poisson approach: docs/mlb/research/market-strategies.md
    - Standard exponent: 1.83 (Huemann), not 2.0
"""

# TODO: Phase 1 implementation
# - PoissonModel class with fit() and predict() methods
# - Score matrix generation (optimize with scipy.stats.poisson)
# - Market probability extraction (ML, RL, totals)
# - F5 innings variant (separate lambda for first 5 IP)
# - Integration with pitcher_model.py and lineup_model.py
# - Calibration hook for Platt scaling (shared KellySizer)
