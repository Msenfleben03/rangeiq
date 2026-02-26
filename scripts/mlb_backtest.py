"""Walk-forward backtesting for MLB Poisson model.

Unlike NCAAB's discrete season structure, MLB uses rolling windows:
    Train through April → validate on May
    Retrain through May → validate on June
    etc.

Handles projection blending during backtest:
    - Early-season games use 90% projections / 10% observed
    - Blending shifts as season progresses (managed by projection_blender)

Outputs:
    - Per-bet results with CLV
    - Season-level ROI, Sharpe, Brier score
    - Market-type breakdown (ML, RL, totals independently)
    - Calibration curves per market type
    - Parquet files for KellySizer calibration

Usage:
    python scripts/mlb_backtest.py --test-season 2025
    python scripts/mlb_backtest.py --test-season 2025 --calibrated-kelly
    python scripts/mlb_backtest.py --test-season 2024 2025 --market moneyline

References:
    - NCAAB equivalent: scripts/backtest_ncaab_elo.py
    - Gatekeeper: backtesting/validators/gatekeeper.py
"""

# TODO: Phase 1 implementation
# - Walk-forward validation with rolling windows (not season-based)
# - Projection blending during backtest (respecting temporal boundaries)
# - Multi-market output (ML, RL, totals tracked independently)
# - Parquet export for KellySizer calibration
# - Integration with existing Gatekeeper (sport='mlb')
# - CLI arguments: --test-season, --market, --calibrated-kelly
