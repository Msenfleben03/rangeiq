# Contributing & Development Guide

**Last Updated:** 2026-02-12

## Environment Setup

### Prerequisites

- Python 3.11+ (3.13 recommended)
- Git
- SQLite3 (bundled with Python)
- Virtual environment (`venv` or `uv`)

### Initial Setup

```bash
# Clone and enter project
git clone <repo-url>
cd sports-betting

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables (.env)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ODDS_API_KEY` | For live odds | _(none)_ | The Odds API key (500 free credits/mo) |
| `CFBD_API_KEY` | For NCAAF | _(none)_ | CollegeFootballData.com API key |
| `DATABASE_PATH` | No | `data/ncaab_betting.db` | NCAAB SQLite database (alias for NCAAB_DATABASE_PATH) |
| `ENVIRONMENT` | No | `development` | development / staging / production |
| `DISPLAY_TIMEZONE` | No | `America/Chicago` | Display timezone (storage is UTC) |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `LOG_FILE` | No | `logs/sports_betting.log` | Log file path |
| `INITIAL_BANKROLL` | No | `5000` | Starting bankroll reference |
| `KELLY_FRACTION` | No | `0.25` | Default Kelly fraction |
| `MAX_BET_FRACTION` | No | `0.03` | Max bet as fraction of bankroll |
| `PAPER_BETTING_MODE` | No | `true` | Paper vs live betting flag |
| `USE_CACHED_DATA` | No | `false` | Use cached data for development |
| `DEBUG` | No | `false` | Enable debug logging |

**Rate Limits (optional overrides):**

| Variable | Default | Purpose |
|----------|---------|---------|
| `SPORTSIPY_RATE_LIMIT` | 30 | Requests/min for sportsipy |
| `PYBASEBALL_RATE_LIMIT` | 60 | Requests/min for pybaseball |
| `ODDS_API_RATE_LIMIT` | 10 | Requests/min for The Odds API |

**Notifications (optional):**

- `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALERT_EMAIL` — Email alerts
- `SLACK_WEBHOOK_URL` — Slack webhook for alerts

## Available Scripts

### Paper Betting Pipeline (6 Phases)

| Phase | Script | Purpose | Usage |
|-------|--------|---------|-------|
| 1 - Data | `scripts/fetch_historical_data.py` | Download NCAAB seasons via sportsipy | `python scripts/fetch_historical_data.py --start 2020 --end 2025` |
| 1 - Train | `scripts/train_ncaab_elo.py` | Train Elo model on historical data | `python scripts/train_ncaab_elo.py --validate` |
| 3 - Backtest | `scripts/backtest_ncaab_elo.py` | Walk-forward backtest with Kelly + CLV | `python scripts/backtest_ncaab_elo.py --test-season 2025` |
| 3 - Validate | `scripts/run_gatekeeper_validation.py` | 5-dimension Gatekeeper validation | `python scripts/run_gatekeeper_validation.py` |
| 4 - Predict | `scripts/daily_predictions.py` | Morning: predict + odds + bet recs | `python scripts/daily_predictions.py --date today` |
| 5 - Record | `scripts/record_paper_bets.py` | Record bet decisions | `python scripts/record_paper_bets.py --date today` |
| 5 - Settle | `scripts/settle_paper_bets.py` | Settle completed games + CLV | `python scripts/settle_paper_bets.py --date today` |
| 6 - Report | `scripts/generate_report.py` | Performance reports | `python scripts/generate_report.py --all` |

### Utility Scripts

| Script | Purpose | Usage |
|--------|---------|-------|
| `scripts/validate_ncaab_elo.py` | Legacy Gatekeeper validation | `python scripts/validate_ncaab_elo.py` |
| `scripts/verify_schema.py` | Check database schema health | `python scripts/verify_schema.py` |
| `scripts/reset_closing_odds.py` | Repair closing odds data | `python scripts/reset_closing_odds.py` |
| `scripts/fix_docstrings.py` | Format docstrings to Google style | `python scripts/fix_docstrings.py` |

### Daily Workflow

```bash
# MORNING (2-3 hours before games)
python scripts/daily_predictions.py --date today
python scripts/record_paper_bets.py --date today

# EVENING (after games complete)
python scripts/settle_paper_bets.py --date today
python scripts/generate_report.py --daily --odds-health

# WEEKLY (Sunday evening)
python scripts/generate_report.py --weekly --clv
```

## Testing

### Run Tests

```bash
# All tests (458+)
pytest tests/ -v

# Validator framework only (219 tests)
pytest tests/ -k "validator" -v

# Paper betting pipeline tests (91 tests)
pytest tests/test_logger.py tests/test_reports.py tests/test_settlement.py tests/test_odds_providers.py tests/test_model_persistence.py -v

# Specific module
pytest tests/test_gatekeeper.py -v

# With coverage report
pytest tests/ --cov=backtesting --cov=betting --cov=models --cov=tracking --cov=pipelines -v

# Quick smoke test (imports + connectivity)
pytest tests/test_setup.py -v
```

### Test Organization

| Category | Files | Count | Focus |
|----------|-------|-------|-------|
| Validators | `test_temporal_validator.py` (26), `test_statistical_validator.py` (49), `test_overfit_validator.py` (42), `test_betting_validator.py` (52), `test_gatekeeper.py` (50) | 219 | 5-dimension validation framework |
| Models | `test_elo.py` (53), `test_model_persistence.py` (15) | 68 | Elo math, persistence roundtrips |
| Tracking | `test_logger.py` (11), `test_reports.py` (10), `test_settlement.py` (9) | 30 | Bet logging, reports, settlement |
| Pipelines | `test_odds_providers.py` (46) | 46 | Odds provider strategy pattern |
| Integration | `test_backtesting.py` (51), `test_forecasting_db.py` (20) | 71 | Walk-forward, forecasting DB |
| Environment | `test_setup.py` (24) | 24 | Package imports, database connectivity |

### Writing Tests

- Place tests in `tests/` matching the module name: `test_{module_name}.py`
- Use `conftest.py` fixtures: `project_root`, `test_data_dir`, `sample_backtest_df`, `temp_database`
- Test at boundary values (e.g., exactly 200 samples for sample size check)
- Mock HTTP responses for provider tests — never hit real APIs
- All model code requires unit tests before deployment

## Code Standards

### Style

- **PEP 8** compliance (enforced via `ruff`)
- **Google-style** docstrings for all public functions
- **Type hints** on all function signatures
- **100 character** max line length
- **Immutable patterns** — create new objects, don't mutate existing

### Naming

| Type | Convention | Example |
|------|-----------|---------|
| Functions | `snake_case` | `calculate_clv()` |
| Classes | `PascalCase` | `NCAABEloModel` |
| Constants | `UPPER_SNAKE_CASE` | `BANKROLL` |
| Files | `snake_case.py` | `odds_converter.py` |

### File Size

- Target: 200-400 lines
- Maximum: 800 lines
- Extract utilities from large modules

### Pre-commit Checks

```bash
# Install hooks
pre-commit install

# Manual run
pre-commit run --all-files
```

Hooks run: `black` (formatting), `ruff` (linting), `mypy` (type checking), `interrogate` (docstring coverage)

## Project Structure

See `docs/CODEMAPS/CODEMAP.md` for the full architecture overview and per-module codemaps.
See `docs/ARCHITECTURE.md` for the high-level system architecture diagram.

Key directories:

```text
backtesting/     # Walk-forward validation, 5-dimension validators
betting/         # Odds conversion, EV, CLV, Kelly, arbitrage
config/          # Settings and dataclass constants
models/          # Elo system, model persistence
pipelines/       # Data fetching, odds providers, orchestrator
tracking/        # Database, bet logger, reports
tests/           # pytest suite (458+ tests)
scripts/         # 6-phase paper betting pipeline
docs/            # Architecture, codemaps, runbook
```

## Model Deployment Process

1. **Develop** — Build/update model in `models/`
2. **Backtest** — Walk-forward validation via `scripts/backtest_ncaab_elo.py`
3. **Validate** — Must pass Gatekeeper: `scripts/run_gatekeeper_validation.py`
   - Sample size >= 200 bets
   - Sharpe ratio >= 0.5
   - In-sample ROI <= 15%
   - CLV >= 1.5%
   - Ruin probability <= 5%
4. **Paper Bet** — 50+ paper bets with positive CLV
5. **Go Live** — Gradual rollout (25% -> 50% -> 100%)

## Key Principles

- **CLV > Win Rate** — Closing Line Value is the primary success metric
- **Zero Cost** — All data sources must be free; paid APIs are blocked
- **Walk-Forward Only** — Never use random cross-validation for time-series data
- **Gatekeeper Required** — No model reaches production without passing all 5 dimensions
- **Quarter Kelly** — Default bet sizing is conservative (0.25 fraction, 3% cap)
