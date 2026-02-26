"""MLB odds fetching and line tracking.

Retrieves opening and closing odds for MLB markets:
- Moneylines (phase 1)
- Run lines ±1.5 (phase 2)
- Totals over/under (phase 2)
- F5 innings lines (phase 2)

Providers (in priority order):
    1. ESPN Core API (free, historical, reuse existing infrastructure)
    2. The Odds API (free tier: 500 calls/month, 40+ sportsbooks)
    3. Additional providers TBD

Critical for:
    - CLV tracking (opening vs closing lines)
    - Bet placement odds comparison
    - Line movement detection (reverse line movement signals)

Note: Always bet "listed pitcher" to maintain model integrity.
If the pitcher changes, pricing basis evaporates.

References:
    - Odds storage: odds_snapshots table in shared betting.db
    - CLV system: docs/mlb/research/market-strategies.md
    - Existing infra: pipelines/espn_core_odds_provider.py
"""

# TODO: Phase 1 implementation
# - MLBOddsProvider class (extend or mirror NCAAB pattern)
# - fetch_opening_odds(game_date) → moneyline odds per game
# - fetch_closing_odds(game_pk) → closing line for CLV calc
# - fetch_current_odds(game_pk) → live odds for bet sizing
# - Line movement tracking: detect reverse line movement
# - Integration with shared odds_snapshots table (sport='mlb')
# - ESPN Core API adapter for MLB (different sport ID / endpoints)
