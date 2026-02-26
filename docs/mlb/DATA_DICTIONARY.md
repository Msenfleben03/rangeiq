# MLB Data Dictionary

## Database: `data/mlb_data.db`

MLB-specific raw data. 14 tables + 1 view.
Cross-sport tables (bets, bankroll, predictions) remain in shared `data/betting.db`.

Full schema SQL: see `docs/plans/2026-02-25-mlb-expansion-design.md`

## Table Summary

| Table | Rows (est. 3 seasons) | Purpose |
|-------|----------------------|---------|
| teams | 30 | MLB team reference with stadium coordinates |
| players | ~2,000 | Player cross-reference IDs (MLBAM, FanGraphs, BBRef) |
| games | ~7,300 | Game results with game_pk as primary key |
| pitcher_game_logs | ~60,000 | Per-appearance pitcher stats with Statcast |
| pitcher_season_stats | ~5,000 | Rolling season stats snapshots (as_of_date) |
| batter_season_stats | ~10,000 | Rolling batter stats with platoon splits |
| lineups | ~130,000 | Confirmed batting orders (9 per team per game) |
| weather | ~7,300 | Game-time weather conditions (outdoor only) |
| park_factors | ~90 | Event-specific park factors (30 teams × 3 seasons) |
| umpire_stats | ~300 | HP umpire tendencies per season |
| projections | ~4,000 | ZiPS/Steamer preseason projections |
| bullpen_usage | ~120,000 | Reliever pitch counts and fatigue tracking |

## Key Fields

### game_pk (Universal Game ID)

- Source: MLB Stats API
- Type: INTEGER
- Used as PRIMARY KEY in games table and FOREIGN KEY everywhere else
- Example: 745632

### as_of_date (Temporal Boundary)

- Present on: pitcher_season_stats, batter_season_stats, umpire_stats
- Purpose: Prevents look-ahead bias in backtesting
- Only data available BEFORE this date is included in the snapshot

### Player IDs

- `player_id`: MLBAM ID (primary, used by MLB Stats API)
- `fangraphs_id`: FanGraphs ID (used by pybaseball)
- `bbref_id`: Baseball Reference ID (text format: "troutmi01")
- `retrosheet_id`: Retrosheet ID (text format: "troum001")
