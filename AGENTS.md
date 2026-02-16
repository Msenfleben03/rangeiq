<!-- Last updated: 2026-02-16 | Last verified: 2026-02-16 -->
# AGENTS.md — Sports Betting Model Development

> Precedence: CLAUDE.md > AGENTS.md > scoped AGENTS.md

## Commands (verified 2026-02-16)

| Command | Purpose | ~Time |
|---------|---------|-------|
| `venv/Scripts/python.exe -m pytest tests/ -v` | Run all 533 tests | ~15s |
| `venv/Scripts/python.exe -m pytest tests/ -k "validator"` | Run validator tests only | ~5s |
| `venv/Scripts/python.exe scripts/backtest_ncaab_elo.py --season 2025 --min-edge 0.075` | Backtest at 7.5% edge | ~30s |
| `venv/Scripts/python.exe scripts/train_ncaab_elo.py` | Train Elo model | ~60s |
| `venv/Scripts/python.exe scripts/fetch_season_data.py --season 2025` | Fetch scores + odds | ~2h |
| `venv/Scripts/python.exe scripts/backfill_historical_odds.py --season 2025 --resume` | Backfill odds (ESPN Core API) | ~1.5h |
| `venv/Scripts/python.exe scripts/daily_predictions.py --date today` | Generate daily picks | ~10s |
| `venv/Scripts/python.exe scripts/run_gatekeeper_validation.py` | 5-dim model validation | ~30s |
| `pre-commit run --all-files` | Run 15 pre-commit hooks | ~30s |

## File Map

```text
betting/          -> Odds conversion, arb detection, Kelly sizing
models/           -> Elo rating system, model persistence, sport-specific ratings
models/sport_specific/ncaab/ -> NCAAB team ratings
pipelines/        -> Data fetchers: ESPN scores, ESPN Core odds, unified pipeline
scripts/          -> CLI entry points: train, backtest, fetch, validate, daily workflow
backtesting/      -> Walk-forward validation, metrics, Monte Carlo simulation
backtesting/validators/ -> 5-dimension validation: temporal, statistical, overfit, betting, gatekeeper
config/           -> Settings, constants (edge thresholds, K-factors)
tracking/         -> SQLite DB interface, bet logging, forecasting, reports
features/         -> Feature engineering (placeholder for KenPom integration)
tests/            -> 533 tests (pytest), 16 test files
dashboards/       -> Interactive Elo ratings dashboard (HTML)
data/raw/         -> ESPN game data (35,719 games, 6 seasons)
data/odds/        -> Historical odds (318,158 records, 91.6% coverage)
data/processed/   -> Trained model pkl, processed datasets
docs/             -> Architecture, data dictionary, research docs
```

## Golden Samples

| For | Reference | Key patterns |
|-----|-----------|-------------|
| Odds math | `betting/odds_converter.py` | Type hints, ValueError guards, docstrings |
| Model code | `models/elo.py` | Immutable updates, K-factor tuning |
| Validator | `backtesting/validators/gatekeeper.py` | 5-dim pipeline, GateDecision enum |
| Data pipeline | `pipelines/espn_core_odds_provider.py` | Checkpoint/resume, rate limiting |
| CLI script | `scripts/backtest_ncaab_elo.py` | argparse, `--min-edge`, flat-stake ROI |

## Utilities (reuse, don't rewrite)

| Need | Use | Location |
|------|-----|----------|
| Odds conversion | `american_to_decimal()`, `american_to_implied_prob()` | `betting/odds_converter.py` |
| Edge calculation | `calculate_edge()`, `calculate_clv()` | `betting/odds_converter.py` |
| Bet sizing | `fractional_kelly()` | `betting/odds_converter.py` |
| Model save/load | `save_model()`, `load_model()` | `models/model_persistence.py` |
| DB access | `Database` class | `tracking/database.py` |

## Heuristics

| When | Do |
|------|-----|
| Adding new model | Must pass Gatekeeper (5-dim validation) before deployment |
| Running backtest | `copy.deepcopy(model)` before `run_backtest()` — model mutates |
| Calculating ROI | Use `mean(pnl/stake)` flat-stake, never compound Kelly |
| American odds = 0 | Treat as invalid, skip game (raises ValueError) |
| Measuring CLV | Only valid for 2024-2025 seasons (no open/close before 2024) |
| Running Python | Always use `venv/Scripts/python.exe`, not system Python |
| Pre-commit fails | bandit: `# nosec BXXX`, ruff: `# noqa: EXXX` |

## Boundaries

**Always:**

- Validate all odds inputs (reject 0, NaN, None)
- Use type hints on all function signatures
- Run Gatekeeper before approving any model
- Use immutable patterns (new objects, not mutations)

**Ask first:**

- Changing edge thresholds in `config/constants.py`
- Modifying database schema
- Adding new data providers

**Never:**

- Hardcode API keys (use `.env`)
- Use full Kelly (always fractional, max 3%)
- Trust sportsipy (broken — use `ESPNDataFetcher`)
- Skip walk-forward validation for backtests

## Codebase State

- sportsipy is broken; `pipelines/espn_ncaab_fetcher.py` replaces it
- 2020-2023 odds have NO open/close moneylines (CLV = 0 for those seasons)
- Provider IDs: 40=DraftKings, 36=Unibet, 43=Caesars, 58=ESPN BET
- IDs 1001-1004 are prediction services, NOT real sportsbooks
- KenPom integration planned (next milestone)
- Incremental retraining (train N-1, test N) not yet implemented

## Terminology

| Term | Means |
|------|-------|
| CLV | Closing Line Value — primary profitability predictor |
| EV | Expected Value of a bet |
| Edge | Model probability minus implied probability |
| Vig/Juice | Sportsbook commission built into odds |
| Sharp | Professional bettor / efficient market |
| Flat-stake | Equal bet size regardless of edge (for validation) |
| Walk-forward | Train on past, test on future — no look-ahead |
| Gatekeeper | 5-dimension validation gate (198 tests) |
