"""MLB daily pipeline orchestrator.

Event-driven architecture that processes games as lineups are confirmed.
Mirrors scripts/daily_run.py pattern for NCAAB but handles MLB's
unique characteristics: 15 games/day, lineup-dependent predictions,
weather sensitivity, and multiple market types.

Pipeline flow:
    1. Morning init: fetch schedule, probable pitchers, opening odds
    2. Lineup monitor: poll for confirmed lineups (event-driven)
    3. Per-game prediction: when lineup confirmed →
        a. Compute pitcher features (starter + bullpen fatigue)
        b. Compute lineup features (platoon-adjusted strength)
        c. Run Poisson model → lambda_home, lambda_away
        d. Derive market probabilities (ML, RL, totals, F5)
        e. Compare to market odds → edge calculation
        f. Kelly sizing → stake recommendation
        g. Log prediction + recommended bet
    4. Post-game: settle bets, fetch results, update stats, compute CLV

Usage:
    python scripts/mlb_daily_run.py                 # Full event-driven run
    python scripts/mlb_daily_run.py --dry-run       # Preview picks only
    python scripts/mlb_daily_run.py --settle-only   # Settle yesterday only
    python scripts/mlb_daily_run.py --morning-only  # Just fetch schedule/odds

References:
    - NCAAB equivalent: scripts/daily_run.py
    - Pipeline design: docs/mlb/PIPELINE_DESIGN.md
"""

# TODO: Phase 1 implementation
# - MLBDailyPipeline class (or functional like NCAAB)
# - morning_init(date) → schedule, pitchers, opening odds
# - run_lineup_monitor(date) → event loop polling for confirmations
# - predict_game(game_pk) → Poisson prediction + market comparisons
# - recommend_bets(predictions) → Kelly-sized recommendations
# - settle_yesterday() → fetch results, compute CLV
# - CLI argument parsing (--dry-run, --settle-only, etc.)
# - Integration with shared betting.db for bet logging
# - Calibration: KellySizer with MLB-specific Platt calibration
