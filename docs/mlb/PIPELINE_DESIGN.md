# MLB Daily Pipeline Design

## Architecture: Event-Driven

Unlike NCAAB's single morning run, MLB requires lineup-dependent predictions.
The pipeline uses a per-game state machine triggered by lineup confirmations.

## Game State Machine

```text
SCHEDULED ──▶ PITCHERS_SET ──▶ LINEUPS_CONFIRMED ──▶ PREDICTED ──▶ SETTLED
    │              │                   │                  │            │
    │              │                   │                  │            │
  Morning       Probable           Lineups             Model        Post-game
  schedule      pitchers           confirmed           output       results +
  + odds        announced          (2-4h pre)          + Kelly      CLV calc
```

## Daily Timeline (ET)

| Time | Action | Trigger |
|------|--------|---------|
| 8:00 AM | Morning init: schedule, probable pitchers, opening odds | Scheduled |
| 10:00 AM | Start lineup monitoring (poll every 15 min) | Scheduled |
| 11:00 AM - 1:00 PM | Early games: lineups confirm → trigger predictions | Event |
| 4:00 PM - 6:00 PM | Evening games: lineups confirm → trigger predictions | Event |
| 8:00 PM | Stop monitoring, force-predict remaining unconfirmed | Timeout |
| 11:00 PM | Post-game: results, settlement, stat updates, CLV | Scheduled |

## Fallback: 3-Cycle Mode

If event-driven proves too complex:

| Cycle | Time | Actions |
|-------|------|---------|
| Morning | 8:00 AM ET | Schedule, pitchers, opening odds, weather forecast |
| Pre-game | 1:00 PM ET | Confirmed lineups, updated weather, predictions, Kelly |
| Post-game | 11:00 PM ET | Results, settlement, stat updates, CLV |

## Per-Game Prediction Flow

```text
Lineup confirmed for game_pk=745632
    │
    ├─▶ Fetch pitcher features (starter K-BB%, SIERA, Stuff+)
    ├─▶ Fetch bullpen fatigue (team bullpen xFIP, PC_L3/L7)
    ├─▶ Fetch lineup features (platoon-adjusted wRC+/xwOBA)
    ├─▶ Fetch park factors (event-specific)
    ├─▶ Fetch weather (if outdoor stadium)
    │
    ▼
    Compute λ_home, λ_away (Poisson regression)
    │
    ├─▶ Derive P(home win) → compare to ML odds → edge?
    ├─▶ Derive P(home -1.5) → compare to RL odds → edge?
    ├─▶ Derive P(total > T) → compare to total odds → edge?
    ├─▶ Derive F5 variants → compare to Pinnacle full-game close (proxy) → edge?
    │        (ESPN Core API has no F5-specific odds; see ADR-MLB-010)
    │
    ▼
    For each market with positive calibrated edge:
        → KellySizer.size_bet() → stake recommendation
        → Log to betting.db (sport='mlb')
```

## Integration with Shared Infrastructure

| Component | Location | MLB Usage |
|-----------|----------|-----------|
| KellySizer | betting/odds_converter.py | MLB-specific Platt calibration |
| CLV tracking | tracking/ | Same as NCAAB, sport='mlb' |
| Gatekeeper | backtesting/validators/ | Extended with MLB checks |
| odds_snapshots | betting.db | Opening/closing odds, sport='mlb' |
| bets table | betting.db | All MLB bets, sport='mlb' |

## Automation

Phase 1: Manual invocation via CLI
Phase 2: Task Scheduler (like NCAAB daily-pipeline.ps1)
Phase 3: Event-driven monitoring daemon
