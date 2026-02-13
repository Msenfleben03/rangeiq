# /fetch-odds — Agent-Assisted Odds Retrieval

Fetch real-time odds for a game using browser automation tools.

## Usage

```bash
/fetch-odds Duke vs UNC tonight
/fetch-odds Kansas -3.5 at BetMGM
```

## Instructions

When the user invokes `/fetch-odds`, follow these steps:

1. **Parse the matchup** from the argument (home team, away team, optional sportsbook preference).

2. **Navigate to the sportsbook odds page** using `mcp__claude-in-chrome__navigate`:
   - Default: DraftKings NCAAB page (`https://sportsbook.draftkings.com/leagues/basketball/ncaab`)
   - If user specifies a book, navigate there instead.

3. **Read the page content** using `mcp__claude-in-chrome__read_page` or `mcp__claude-in-chrome__get_page_text`.

4. **Find the game** in the page content. Look for both team names in the text.

5. **Extract odds data**:
   - Spread (home line, odds)
   - Total (over/under, odds)
   - Moneyline (home/away)

6. **Format as ClosingOdds** and save to database:

   ```python
   from pipelines.closing_odds_collector import ClosingOdds
   from pipelines.odds_orchestrator import OddsOrchestrator
   from tracking.database import BettingDatabase
   from datetime import datetime, timezone

   odds = ClosingOdds(
       game_id="<generated_or_found>",
       sportsbook="draftkings",
       captured_at=datetime.now(timezone.utc),
       spread_home=<parsed>,
       spread_home_odds=<parsed>,
       moneyline_home=<parsed>,
       moneyline_away=<parsed>,
       total=<parsed>,
       over_odds=<parsed>,
       under_odds=<parsed>,
       is_closing=False,
       confidence=0.90,
   )
   ```

7. **Report results** to the user with a formatted table.

## When to Use

- API quota is exhausted
- Need odds for a specific game right now
- Want to verify API data against actual sportsbook
- Scraper selectors are broken
