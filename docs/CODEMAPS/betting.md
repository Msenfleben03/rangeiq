# Betting Module Codemap

**Last Updated:** 2026-02-12
**Entry Point:** `betting/__init__.py`
**Test Coverage:** `tests/test_backtesting.py` (indirect)

## Architecture

```text
betting/
  __init__.py          # Re-exports core functions from odds_converter
  odds_converter.py    # Pure functions: odds conversion, EV, CLV, Kelly
  arb_detector.py      # Arbitrage detection across sportsbooks (SQLite-backed)
```

## Key Modules

### odds_converter.py

Core utility module with pure functions used throughout the entire project.
Zero external dependencies (no imports beyond stdlib).

| Export | Type | Signature | Purpose |
|--------|------|-----------|---------|
| `american_to_decimal()` | function | `(american: int) -> float` | -110 -> 1.909 |
| `american_to_implied_prob()` | function | `(american: int) -> float` | -110 -> 0.5238 |
| `decimal_to_american()` | function | `(decimal: float) -> int` | 1.91 -> -109 |
| `expected_value()` | function | `(win_prob, profit_if_win, stake) -> float` | EV = p*profit - q*stake |
| `calculate_edge()` | function | `(model_prob, american_odds) -> float` | model_prob - implied_prob |
| `calculate_clv()` | function | `(odds_placed, odds_closing) -> float` | THE key metric for long-term profitability |
| `fractional_kelly()` | function | `(win_prob, decimal_odds, fraction, max_bet) -> float` | Conservative Kelly bet sizing (default: quarter Kelly, 3% cap) |
| `BREAKEVEN_RATES` | dict | `{-110: 0.5238, ...}` | Common break-even win rates |

**Imported By:**

- `backtesting/metrics.py` (calculate_clv)
- `backtesting/simulation.py` (american_to_decimal, fractional_kelly)
- `backtesting/validators/betting_validator.py` (american_to_implied_prob)
- `betting/arb_detector.py` (american_to_decimal, american_to_implied_prob)
- `pipelines/arb_scanner.py` (via arb_detector)

**Design Notes:**

- All functions are pure (no side effects, no state)
- American odds convention: negative = favorite, positive = underdog
- Kelly defaults are conservative: quarter Kelly (0.25), 3% max bet
- Module includes `if __name__ == "__main__"` demo section

### arb_detector.py

Lightweight opportunistic arbitrage detector that scans odds_snapshots table for cross-book opportunities.

| Export | Type | Purpose |
|--------|------|---------|
| `ArbOpportunity` | dataclass | Detected arb (game_id, both legs, combined implied, profit_pct, stakes) |
| `calculate_arb_stakes()` | function | Optimal 2-way arb stake allocation for guaranteed profit |
| `ArbDetector` | class | Scans SQLite for arbs on games already being tracked |

**Key Methods on ArbDetector:**

- `scan_game(game_id)` - Check single game for ML, spread, total arbs
- `scan_current_games(sport, hours_ahead)` - Scan all upcoming games
- `log_opportunity(arb)` - Persist to arb_opportunities table
- `get_recent_opportunities(hours, min_profit)` - Retrieve logged arbs

**Database Tables Used:**

- `odds_snapshots` (read) - Source of cross-book odds data
- `games` (read) - Game schedule for filtering
- `arb_opportunities` (write) - Created by this module for logging arbs

**Design Philosophy:**

- PASSIVE: Only flags arbs on games already being modeled
- MINIMAL: Uses existing tables, no major schema changes
- OPTIONAL: Can be enabled/disabled without affecting core model
- CONSERVATIVE: High threshold (>1% profit) to filter noise

**Arb Types Detected:**

1. **Moneyline** - Best home ML at Book A + best away ML at Book B
2. **Spread** - Same spread number, different juice across books
3. **Total** - Best over at Book A + best under at Book B

**CLI Interface:** `python -m betting.arb_detector --sport NCAAB --hours 24 --min-profit 0.01`

## Data Flow

```text
odds_converter.py (pure functions)
       |
       v
arb_detector.py (reads odds_snapshots, writes arb_opportunities)
       |
       v
pipelines/arb_scanner.py (orchestrates scanning, CLI wrapper)
```

## External Dependencies

| Package | Used In | Purpose |
|---------|---------|---------|
| sqlite3 | arb_detector.py | Database access for odds snapshots |
| (none) | odds_converter.py | Zero dependencies - pure math only |

## Related Areas

- [backtesting.md](backtesting.md) - Uses odds_converter for CLV metrics and simulation
- [pipelines.md](pipelines.md) - arb_scanner.py wraps ArbDetector for pipeline integration
- [config.md](config.md) - BettingThresholds defines min edge and CLV targets
