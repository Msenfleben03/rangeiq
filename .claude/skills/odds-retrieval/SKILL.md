---
name: odds-retrieval
description: Agent skill for navigating sportsbook websites and extracting odds data
version: 1.0.0
triggers:
  - fetch odds
  - get odds
  - check odds
  - line shop
  - sportsbook odds
---

# Odds Retrieval Skill

## Purpose

Navigate sportsbook websites to extract current odds for games. Used when
automated providers (API, ESPN) are unavailable or when manual verification
is needed.

## Sportsbook Navigation Patterns

### DraftKings

- **NCAAB URL**: `https://sportsbook.draftkings.com/leagues/basketball/ncaab`
- **Game layout**: Games listed vertically with spread/total/moneyline columns
- **Odds format**: American odds (e.g., -110, +150)

### FanDuel

- **NCAAB URL**: `https://sportsbook.fanduel.com/basketball/ncaab`
- **Game layout**: Tab-based (Spread, Total, Moneyline)
- **Odds format**: American odds

### BetMGM

- **NCAAB URL**: `https://sports.betmgm.com/en/sports/basketball-23/betting/usa-9/college-basketball-251`
- **Game layout**: Compact event cards
- **Odds format**: American odds

## Extraction Process

1. Navigate to sportsbook game page
2. Read page content via `mcp__claude-in-chrome__read_page`
3. Identify the target game by team names
4. Extract structured odds:
   - **Spread**: Home line (e.g., -5.5), home odds, away odds
   - **Total**: Over/Under number, over odds, under odds
   - **Moneyline**: Home ML, Away ML
5. Parse American odds format: `+150` = 150, `-110` = -110, `EVEN` = 100

## Data Storage Format

Store extracted odds as `ClosingOdds` dataclass from
`pipelines/closing_odds_collector.py` and persist via
`OddsOrchestrator.store_odds()`.

## Line Shopping

When comparing across books:

1. Fetch odds from 2-3 sportsbooks for the same game
2. Compare spreads and moneylines side by side
3. Identify the best available line
4. Report which book has the most favorable odds

## Error Handling

- If a sportsbook page doesn't load, try alternative books
- If odds format is unexpected, report raw text for manual parsing
- If game isn't found on the page, try searching by date or team abbreviation
