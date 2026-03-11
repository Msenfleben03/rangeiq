# NCAAB Game Log & Odds Database — Design Document

**Date**: 2026-03-11
**Status**: Approved

## Overview

Build an append-only game log that captures every D1 NCAAB game the model evaluates —
whether we bet it or not — with opening odds, closing odds, model probability, edge,
and final scores. Serves two purposes:

1. **Quick daily review**: Standalone dashboard page with sortable/filterable game table
2. **Future backtesting**: Proprietary odds database built from real-time capture

## Approach

New `game_log` table in `ncaab_betting.db` (Approach A — purpose-built table, no schema
mutations to existing tables). Integrated into `daily_run.py` at two touch points, plus
a standalone script for manual runs.

## Schema

```sql
CREATE TABLE game_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_date DATE NOT NULL,
    game_id TEXT NOT NULL,           -- ESPN event ID
    home TEXT NOT NULL,              -- Abbreviation (e.g., "DUKE")
    away TEXT NOT NULL,
    home_score INTEGER,             -- NULL until settled
    away_score INTEGER,
    model_prob_home REAL,           -- Model win probability for home team
    edge REAL,                      -- Best edge (home or away), signed (+home/-away)
    odds_opening_home INTEGER,      -- Consensus ML, American format
    odds_opening_away INTEGER,
    odds_closing_home INTEGER,      -- Populated at settlement
    odds_closing_away INTEGER,
    bet_placed BOOLEAN DEFAULT 0,   -- 1 if we bet this game
    bet_side TEXT,                  -- "home"/"away" or NULL
    result TEXT,                    -- "home"/"away" (winner) or NULL
    settled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id)
);
```

Lean by design — no stake/P&L (lives in `bets` table, joinable on `game_id`).
No Barttorvik/KenPom breakdown columns. Just the decision-time snapshot + outcome.

## Pipeline Integration

### Touch 1 — Prediction Run (in `daily_run.py`)

After predictions are generated for all games on target date:

- ESPN Scoreboard already fetched (groups=50 for all D1 games)
- For each game: INSERT into `game_log` with game_date, game_id, home, away,
  model_prob_home, edge, odds_opening_home/away
- Games with no odds available: insert with NULL odds and NULL edge
- Games we bet: set bet_placed=1, bet_side="home"/"away"

### Touch 2 — Settlement Run (morning after)

During the existing settlement phase:

- ESPN Scoreboard for yesterday's completed games (already fetched)
- For each game in `game_log` WHERE result IS NULL AND game is STATUS_FINAL:
  - Update home_score, away_score, result ("home"/"away" winner)
  - Fetch closing odds from ESPN Core API (same endpoint as collect_closing_odds.py)
  - Update odds_closing_home, odds_closing_away, settled_at
- Settles ALL games, not just bets — the key behavioral change

### Standalone Script: `scripts/generate_game_log.py`

- `--date YYYY-MM-DD` — run prediction-side insert for a specific date
- `--settle` — settle any unsettled games in the log
- `--export csv` — dump game_log table to CSV

## Dashboard

### Standalone Page: `dashboards/ncaab_game_log.html`

- Separate page from existing dashboard (game log grows large quickly)
- Navigation links between the two pages
- Data source: JSON exported by `scripts/generate_dashboard_data.py` (extended)

### View Features

- Sortable/filterable table: date, teams, model prob, edge, opening/closing odds, score, result
- Filters: date range, bet/no-bet, home/away winner
- Color coding: green highlight for games we bet
- Summary row: total games tracked, games bet, settlement rate

### Kept Simple

No charts, no aggregated stats. Raw game log table with sort/filter for quick scanning.

## Testing Strategy

### Unit Tests (`tests/test_game_log.py`)

- Schema creation: table exists with correct columns
- Insert logic: game with odds, game without odds, game with bet
- Settlement logic: scores + closing odds update correctly, settled_at set
- Duplicate handling: re-run for same date doesn't create duplicates (UNIQUE on game_id)
- Edge cases: postponed/cancelled games, overtime scores

### Integration Test (`tests/test_game_log_integration.py`)

- Seed 3-5 synthetic games (mix of bet/no-bet, with/without odds)
- Run prediction-side insert → verify rows
- Run settlement-side update → verify scores, closing odds, result
- Verify standalone script modes (--date, --settle)
- Verify dashboard JSON export includes game log data

### Mocked ESPN Responses

No real API calls in tests — mock scoreboard and odds responses with known fixtures.
Enables full validation before tournament starts.

## Files to Create/Modify

| File | Action |
|------|--------|
| `tracking/database.py` | Add `game_log` table to schema init |
| `tracking/game_log.py` | New module: insert_games(), settle_games() |
| `scripts/daily_run.py` | Call game_log insert after predictions, settle after bets |
| `scripts/generate_game_log.py` | New standalone script |
| `scripts/generate_dashboard_data.py` | Export game_log to JSON bundle |
| `dashboards/ncaab_game_log.html` | New dashboard page |
| `dashboards/ncaab_dashboard.html` | Add nav link to game log |
| `tests/test_game_log.py` | Unit tests |
| `tests/test_game_log_integration.py` | Integration tests |
