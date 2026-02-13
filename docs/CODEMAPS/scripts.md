# Scripts Module Codemap

**Last Updated:** 2026-02-12

## Architecture

```text
scripts/
  validate_ncaab_elo.py     # Run NCAAB Elo model through Gatekeeper validation
  verify_schema.py          # Verify SQLite database schema matches expected structure
  reset_closing_odds.py     # Reset/repair closing odds data in database
  fix_docstrings.py         # Automated docstring formatting and repair
```

## Key Scripts

### validate_ncaab_elo.py

Runs the NCAAB Elo model through the full 5-dimension validation pipeline.

**Purpose:** Pre-deployment validation script that loads backtest results and passes them through the Gatekeeper.

**Usage:**

```bash
python scripts/validate_ncaab_elo.py
```

**Dependencies:** backtesting.validators (Gatekeeper), models.sport_specific.ncaab.team_ratings

### verify_schema.py

Validates that the SQLite database schema matches the expected structure defined in tracking/database.py and tracking/models.py.

**Purpose:** Database health check ensuring all tables and columns exist with correct types.

**Usage:**

```bash
python scripts/verify_schema.py
```

**Dependencies:** sqlite3, tracking.database

### reset_closing_odds.py

Utility to reset or repair closing odds data in the bets table.

**Purpose:** Data maintenance when closing odds collector encounters issues or needs re-running.

**Usage:**

```bash
python scripts/reset_closing_odds.py
```

**Dependencies:** sqlite3

### fix_docstrings.py

Automated docstring formatting and repair tool.

**Purpose:** Ensures consistent Google-style docstrings across the codebase. Used with pre-commit hooks.

**Usage:**

```bash
python scripts/fix_docstrings.py
```

**Dependencies:** ast (Python AST parsing)

## Related Areas

- [backtesting.md](backtesting.md) - validate_ncaab_elo.py uses the Gatekeeper
- [tracking.md](tracking.md) - verify_schema.py and reset_closing_odds.py interact with database
- [models.md](models.md) - validate_ncaab_elo.py tests the NCAAB model
