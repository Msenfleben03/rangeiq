# Arbitrage Detection Module

> **Priority:** LOW | **Status:** Optional Feature | **Last Updated:** 2025-01-25

## Overview

Lightweight cross-book arbitrage detection that integrates seamlessly with the existing sports betting model. Designed to **passively flag opportunities** on games already being tracked—not as a primary strategy.

## Key Design Principles

1. **PASSIVE** - Only scans games with existing odds data in `odds_snapshots`
2. **MINIMAL** - Uses existing tables; adds only one optional tracking table
3. **OPTIONAL** - Can be enabled/disabled without affecting core model
4. **CONSERVATIVE** - 1% minimum profit threshold filters noise

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           EXISTING SPORTS BETTING MODEL                 │
├─────────────────────────────────────────────────────────┤
│  Core: Predictive Edge (NCAAB/MLB)                     │
│  ├── Line value detection                              │
│  ├── CLV tracking                                      │
│  └── Bankroll optimization                             │
├─────────────────────────────────────────────────────────┤
│  [NEW] Arb Detection Module (LOW PRIORITY)              │
│  ├── betting/arb_detector.py     <- Core logic         │
│  ├── pipelines/arb_scanner.py    <- CLI/Integration    │
│  └── arb_opportunities table     <- Optional tracking  │
└─────────────────────────────────────────────────────────┘
```

## Files Added

| File | Purpose |
|------|---------|
| `betting/arb_detector.py` | Core ArbDetector class and math |
| `pipelines/arb_scanner.py` | CLI tool and integration functions |
| `docs/ARB_DETECTION.md` | This documentation |

## Database Changes

**One new table (auto-created on first run):**

```sql
CREATE TABLE arb_opportunities (
    id INTEGER PRIMARY KEY,
    game_id TEXT NOT NULL,
    sport TEXT,
    arb_type TEXT NOT NULL,    -- 'moneyline', 'spread', 'total'

    book1 TEXT NOT NULL,
    selection1 TEXT NOT NULL,
    odds1 INTEGER NOT NULL,

    book2 TEXT NOT NULL,
    selection2 TEXT NOT NULL,
    odds2 INTEGER NOT NULL,

    combined_implied REAL NOT NULL,
    profit_pct REAL NOT NULL,
    stake1 REAL,
    stake2 REAL,

    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    acted_on BOOLEAN DEFAULT FALSE,
    notes TEXT
);
```

## Usage

### CLI (Standalone)

```bash
# Scan all upcoming games
make arb-scan

# Scan specific sport
python -m pipelines.arb_scanner --sport NCAAB --hours 12

# Output as JSON (for automation)
python -m pipelines.arb_scanner --json

# View history
make arb-history
```

### Integration with Existing Pipelines

```python
# In your existing NCAAB pipeline code:
from pipelines.arb_scanner import scan_for_arbs, scan_single_game

# Option 1: Scan after fetching odds (batch)
def fetch_and_check_ncaab():
    # ... existing odds fetching code ...

    # Opportunistic arb check
    arbs = scan_for_arbs(sport="NCAAB", min_profit=0.02)
    if arbs:
        send_notification(arbs)  # Your notification logic

# Option 2: Check specific game during model pipeline
def model_game(game_id):
    # ... existing model predictions ...

    # Quick arb check on this game
    arbs = scan_single_game(game_id)
    if arbs:
        log.info(f"ARB FOUND: {arbs[0].description}")
```

### Python API

```python
from betting.arb_detector import ArbDetector, ArbOpportunity

detector = ArbDetector(db_path="data/betting.db")
detector.MIN_PROFIT_PCT = 0.01  # 1% threshold

# Scan all games
opportunities = detector.scan_current_games(
    sport="NCAAB",
    hours_ahead=24
)

# Scan single game
arbs = detector.scan_game("game_123")

# Log opportunity
if arbs:
    detector.log_opportunity(arbs[0])
```

## Math Reference

### Combined Implied Probability

```
Book A: Lakers +150 (implied 40%)
Book B: Celtics +140 (implied 41.7%)

Combined = 40% + 41.7% = 81.7%
Profit = (1 / 0.817) - 1 = 22.4%
```

### Optimal Stake Calculation

```python
def calculate_stakes(odds1, odds2, total=100):
    dec1 = american_to_decimal(odds1)
    dec2 = american_to_decimal(odds2)

    imp1, imp2 = 1/dec1, 1/dec2
    combined = imp1 + imp2

    stake1 = total * imp1 / combined
    stake2 = total * imp2 / combined

    return stake1, stake2
```

## Why Low Priority?

| Factor | Predictive Model | Arb Detection |
|--------|-----------------|---------------|
| Edge Source | Skill/Research | Market inefficiency |
| Sustainability | Long-term | Accounts get limited |
| Capital Req | Modest | High (1-3% returns) |
| Time Cost | Structured | 24/7 monitoring |
| Account Risk | Low | Very High |

**Bottom line:** Your CLV-focused predictive model is a more sustainable edge than chasing arbs. This module exists for **opportunistic supplemental value** only.

## Configuration

### Thresholds

In `arb_detector.py`:

```python
class ArbDetector:
    MIN_PROFIT_PCT = 0.01  # 1% minimum (adjust as needed)
    ODDS_WINDOW_HOURS = 2   # How recent odds must be
```

### Makefile Commands

| Command | Description |
|---------|-------------|
| `make arb-scan` | Scan all upcoming games |
| `make arb-scan-ncaab` | Scan NCAAB only |
| `make arb-scan-mlb` | Scan MLB only |
| `make arb-scan-json` | JSON output for automation |
| `make arb-history` | View logged opportunities |

## Dependencies

Uses existing project dependencies only:

- Standard library (`sqlite3`, `datetime`, `dataclasses`)
- Your existing `betting/odds_converter.py`

No new packages required.

## Future Enhancements (If Priority Increases)

1. **Alerts** - Webhook/SMS notifications when arbs detected
2. **Auto-tracking** - Monitor specific arbs for line movement
3. **Cross-sport** - Prop bet arb detection (more complex)
4. **Real-time** - WebSocket odds feeds (requires infrastructure)

---

*Created as a minimal-footprint feature. If sports betting arbitrage becomes a higher priority, consider dedicated tools like OddsJam or RebelbetBot.*
