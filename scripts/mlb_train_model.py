"""Train MLB Poisson regression model.

Fits the Poisson model on historical data, learning coefficients for:
    - Pitcher quality (K-BB%, SIERA, xFIP, Stuff+)
    - Lineup strength (platoon-adjusted wRC+, xwOBA)
    - Bullpen quality (team bullpen xFIP, fatigue adjustment)
    - Home field advantage (~54% home win rate in MLB)
    - Park factors (event-specific)
    - Weather adjustments (phase 2)

Model output: coefficients for lambda = exp(X @ beta)
where lambda is expected runs for each team.

Usage:
    python scripts/mlb_train_model.py --end-season 2025
    python scripts/mlb_train_model.py --end-season 2025 --save

References:
    - NCAAB equivalent: scripts/train_ncaab_elo.py
    - Model design: docs/mlb/MODEL_ARCHITECTURE.md
"""

# TODO: Phase 1 implementation
# - Load historical data from mlb_data.db
# - Feature matrix construction from pitcher + lineup + context features
# - Poisson regression fitting (statsmodels or scikit-learn)
# - Model serialization (pickle + metadata JSON)
# - Coefficient interpretation and diagnostics
# - Walk-forward cross-validation during training
