# Config Module Codemap

**Last Updated:** 2026-02-12
**Entry Point:** `config/__init__.py` (empty, import directly)

## Architecture

```text
config/
  __init__.py        # Empty package marker
  settings.py        # Global project paths, bankroll, risk limits, API config
  constants.py       # Dataclass-based constants for all sports and systems
```

## Key Modules

### settings.py

Runtime configuration for paths, bankroll allocation, and operational parameters.

| Export | Type | Value/Purpose |
|--------|------|---------------|
| `PROJECT_ROOT` | Path | Auto-detected project root directory |
| `DATA_DIR` | Path | `PROJECT_ROOT / "data"` |
| `RAW_DATA_DIR` | Path | `DATA_DIR / "raw"` |
| `PROCESSED_DATA_DIR` | Path | `DATA_DIR / "processed"` |
| `ODDS_DATA_DIR` | Path | `DATA_DIR / "odds"` |
| `DATABASE_PATH` | Path | `DATA_DIR / "betting.db"` |
| `TOTAL_BANKROLL` | int | 5000 |
| `ACTIVE_CAPITAL` | int | 4000 |
| `RESERVE` | int | 1000 |
| `SPORTSBOOK_ALLOCATION` | dict | DK: $1000, FD: $1000, MGM: $750, Caesars: $750, ESPN: $500 |
| `DEFAULT_KELLY_FRACTION` | float | 0.25 (quarter Kelly) |
| `MAX_BET_STANDARD` | float | 0.03 (3% of bankroll) |
| `DAILY_EXPOSURE_LIMIT` | float | 0.10 (10%) |
| `WEEKLY_LOSS_LIMIT` | float | 0.15 (15%) |
| `MONTHLY_LOSS_LIMIT` | float | 0.25 (25%) |
| `ELO_START_RATING` | int | 1500 |
| `ELO_K_FACTOR` | int | 20 |
| `MIN_EDGE_REQUIRED` | float | 0.02 (2%) |
| `TARGET_CLV` | float | 0.01 (1%) |
| `NCAAB_SEASONS_START` | int | Starting season for data fetch |
| `NCAAB_SEASONS_END` | int | Ending season for data fetch |
| `ODDS_API_KEY` | str | The Odds API key (from env or .env) |
| `SLA_CLOSING_ODDS_MAX_AGE` | int | 900 seconds (15 min) |
| `RATE_LIMITS` | dict | Per-source rate limits (sportsipy, polymarket, kalshi, etc.) |
| `PAID_APIS_BLOCKED` | list | Blocked paid API domains (zero-cost enforcement) |
| `MARKET_PRIORITIES` | dict | player_props: 1, small_conference: 2, derivative: 3, main: 4 |
| `LOG_LEVEL` | str | "INFO" |

### constants.py

Structured dataclass-based constants for all domain logic. Never hardcode these values elsewhere.

| Export | Type | Purpose |
|--------|------|---------|
| `BankrollConfig` / `BANKROLL` | dataclass/instance | Bankroll limits: total ($5000), Kelly fractions, exposure limits |
| `EloConfig` / `ELO` | dataclass/instance | Sport-specific Elo parameters (K-factors, home advantage, regression, MOV caps) |
| `BettingThresholds` / `THRESHOLDS` | dataclass/instance | Min edge by bet type, CLV targets, odds bounds, line movement thresholds |
| `NCABBConstants` / `NCAAB` | dataclass/instance | Game length, home court advantage, power conferences, pace thresholds |
| `MLBConstants` / `MLB` | dataclass/instance | Innings, park factors, weather thresholds, pitcher workload, platoon splits |
| `NFLConstants` / `NFL` | dataclass/instance | Game length, home field (2.5 pts), bye week, division adjustments |
| `ValidationRanges` / `VALIDATION` | dataclass/instance | Valid ranges for spreads, totals, probabilities, Elo ratings |
| `BacktestConfig` / `BACKTEST` | dataclass/instance | Min sample sizes (100-2000), training seasons, deploy thresholds |
| `APIConfig` / `API` | dataclass/instance | Rate limits, timeouts, retry logic |
| `FeatureConfig` / `FEATURES` | dataclass/instance | Rolling window sizes (5/10/20), decay factor, min lag |
| `LoggingConfig` / `LOGGING` | dataclass/instance | Log level, format, alert thresholds |
| `OddsConfig` / `ODDS_CONFIG` | dataclass/instance | Odds retrieval: default mode, cache TTL, credit limit, provider chain |

**OddsConfig Fields:**

| Field | Default | Purpose |
|-------|---------|---------|
| `DEFAULT_MODE` | "auto" | Default odds retrieval mode |
| `CACHE_TTL_SECONDS` | 300 | TTL for odds cache (5 min) |
| `API_CREDIT_MONTHLY_LIMIT` | 500 | The Odds API monthly credit budget |
| `API_CREDIT_WARNING_PCT` | 0.80 | Warning threshold (80%) |
| `API_CREDIT_CUTOFF_PCT` | 0.90 | Cutoff threshold (90%) |
| `PROVIDER_CHAIN` | list | Ordered fallback chain |

**Imported By:**

- `models/elo.py` -> `ELO` (K-factor, rating bounds)
- `models/sport_specific/ncaab/team_ratings.py` -> `ELO` (NCAAB-specific parameters)
- `tracking/logger.py` -> `BANKROLL` (exposure limits)
- `scripts/daily_predictions.py` -> `BANKROLL`, `ODDS_CONFIG`, `THRESHOLDS`
- `scripts/backtest_ncaab_elo.py` -> `BANKROLL`, `ELO`, `THRESHOLDS`
- `scripts/settle_paper_bets.py` -> `ODDS_CONFIG`
- `pipelines/odds_orchestrator.py` -> (indirectly via scripts)
- `backtesting/validators/gatekeeper.py` -> Thresholds referenced indirectly

## Sport-Specific Elo Parameters

| Parameter | NCAAB | MLB | NFL | NCAAF |
|-----------|-------|-----|-----|-------|
| K-Factor | 20 | 4 | 20 | 25 |
| Home Advantage (Elo pts) | 100 | 24 | 48 | 75 |
| Regression Factor | 0.50 | 0.40 | 0.33 | 0.50 |
| MOV Cap | 25 | 10 | 24 | 28 |
| Elo-to-Points | 25 | 25 | 25 | 25 |

## External Dependencies

None. Both files use only Python stdlib and dataclasses.

## Related Areas

- [models.md](models.md) - ELO config consumed by all Elo model implementations
- [betting.md](betting.md) - THRESHOLDS defines min edge, CLV targets
- [backtesting.md](backtesting.md) - BACKTEST config for sample sizes and deploy thresholds
- [pipelines.md](pipelines.md) - ODDS_CONFIG consumed by odds_orchestrator
- [tracking.md](tracking.md) - BANKROLL consumed by logger.py for limit validation
- [scripts.md](scripts.md) - All scripts reference BANKROLL, ODDS_CONFIG, THRESHOLDS
