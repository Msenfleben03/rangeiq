# CLV Collection System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Collect opening and closing odds for every NCAAB game so the pipeline can calculate Closing Line Value (CLV) — the primary success metric — on every settled paper bet.

**Architecture:** Two new steps in existing pipelines (no new scheduled tasks). Nightly refresh (11pm) fetches opening odds for tomorrow's games via ESPN Core API. Morning settlement (10am) fetches actual closing odds from ESPN Core API `close` fields for yesterday's settled games, then calculates CLV. All data stored in `odds_snapshots` with a new `snapshot_type` column.

**Tech Stack:** Python 3.11+, SQLite, ESPN Core API (free, no key), existing `ESPNCoreOddsFetcher`, `calculate_clv()` from `betting/odds_converter.py`

---

## Task 1: Add `snapshot_type` Column to `odds_snapshots`

**Files:**
- Modify: `tracking/database.py:160-179` (CREATE TABLE statement)
- Modify: `tracking/database.py` (add migration method)

**Step 1: Write the migration function**

Add a `migrate_add_snapshot_type()` method to `BettingDatabase` and call it from `_initialize_db()`. SQLite `ALTER TABLE ADD COLUMN` is safe — it's a no-op if the column already exists (we catch the error).

In `tracking/database.py`, after the `CREATE TABLE odds_snapshots` block (line 179), add:

```python
            # Migration: add snapshot_type column if missing
            try:
                cursor.execute(
                    "ALTER TABLE odds_snapshots ADD COLUMN snapshot_type TEXT DEFAULT 'current'"
                )
                logger.info("Added snapshot_type column to odds_snapshots")
            except Exception:
                pass  # Column already exists
```

Also update the CREATE TABLE statement to include `snapshot_type` for fresh databases. After line 175 (`is_closing BOOLEAN DEFAULT FALSE,`), add:

```python
                    snapshot_type TEXT DEFAULT 'current',
```

**Step 2: Backfill existing rows**

After the ALTER TABLE migration, add:

```python
            # Backfill existing rows without snapshot_type
            cursor.execute(
                "UPDATE odds_snapshots SET snapshot_type = 'current' "
                "WHERE snapshot_type IS NULL"
            )
```

**Step 3: Run existing tests to verify no regressions**

Run: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py -v --tb=short`
Expected: 26/26 pass (existing tests unaffected)

**Step 4: Verify migration works on live database**

Run:
```bash
venv/Scripts/python.exe -c "
from tracking.database import BettingDatabase
from config.settings import DATABASE_PATH
db = BettingDatabase(str(DATABASE_PATH))
rows = db.execute_query('SELECT snapshot_type, COUNT(*) as cnt FROM odds_snapshots GROUP BY snapshot_type')
for r in rows: print(r)
"
```

Expected: All 81 existing rows show `snapshot_type='current'`.

**Step 5: Commit**

```bash
git add tracking/database.py
git commit -m "feat: add snapshot_type column to odds_snapshots for CLV tracking"
```

---

## Task 2: Create `scripts/fetch_opening_odds.py`

**Files:**
- Create: `scripts/fetch_opening_odds.py`
- Test: `tests/test_fetch_opening_odds.py`

**Step 1: Write tests**

Create `tests/test_fetch_opening_odds.py`:

```python
"""Tests for opening odds fetcher."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


# ── Mock ESPN Core API data ──────────────────────────────────────────────

MOCK_ODDS_SNAPSHOT_DATA = {
    "game_id": "401720001",
    "provider_id": 100,
    "provider_name": "Draft Kings",
    "spread": -3.5,
    "over_under": 145.5,
    "home_moneyline": -150,
    "away_moneyline": 130,
    "home_spread_odds": -110,
    "away_spread_odds": -110,
    "over_odds": -110,
    "under_odds": -110,
    "home_spread_open": -3.5,
    "away_spread_open": 3.5,
    "home_spread_odds_open": -110,
    "away_spread_odds_open": -110,
    "home_ml_open": -150,
    "away_ml_open": 130,
    "total_open": 145.5,
    "over_odds_open": -110,
    "under_odds_open": -110,
    # Close fields None for pre-game
    "home_spread_close": None,
    "away_spread_close": None,
    "home_spread_odds_close": None,
    "away_spread_odds_close": None,
    "home_ml_close": None,
    "away_ml_close": None,
    "total_close": None,
    "over_odds_close": None,
    "under_odds_close": None,
}


def _make_mock_snapshot():
    """Create a mock OddsSnapshot from test data."""
    from pipelines.espn_core_odds_provider import OddsSnapshot

    return OddsSnapshot(**MOCK_ODDS_SNAPSHOT_DATA)


MOCK_SCOREBOARD_GAMES = [
    {
        "game_id": "401720001",
        "home": "DUKE",
        "away": "UNC",
        "home_id": "2305",
        "away_id": "153",
        "home_name": "Duke Blue Devils",
        "away_name": "North Carolina Tar Heels",
        "home_score": 0,
        "away_score": 0,
        "neutral_site": False,
        "status": "STATUS_SCHEDULED",
        "game_time": "2026-02-25T19:00Z",
    },
    {
        "game_id": "401720002",
        "home": "UK",
        "away": "TENN",
        "home_id": "2509",
        "away_id": "2633",
        "home_name": "Kentucky Wildcats",
        "away_name": "Tennessee Volunteers",
        "home_score": 0,
        "away_score": 0,
        "neutral_site": False,
        "status": "STATUS_SCHEDULED",
        "game_time": "2026-02-25T21:00Z",
    },
]


class TestFetchOpeningOdds:
    """Tests for fetch_opening_odds()."""

    @patch("scripts.fetch_opening_odds.ESPNCoreOddsFetcher")
    @patch("scripts.fetch_opening_odds.fetch_espn_scoreboard")
    def test_fetches_odds_for_tomorrows_games(self, mock_sb, mock_fetcher_cls):
        from scripts.fetch_opening_odds import fetch_opening_odds

        mock_sb.return_value = MOCK_SCOREBOARD_GAMES

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_game_odds.return_value = [_make_mock_snapshot()]
        mock_fetcher_cls.return_value = mock_fetcher

        db = MagicMock()
        db.execute_query.return_value = []  # No existing opening odds

        result = fetch_opening_odds(db)

        assert result["games_found"] == 2
        assert result["odds_fetched"] >= 1
        mock_fetcher.fetch_game_odds.assert_called()
        mock_fetcher.close.assert_called_once()

    @patch("scripts.fetch_opening_odds.ESPNCoreOddsFetcher")
    @patch("scripts.fetch_opening_odds.fetch_espn_scoreboard")
    def test_skips_games_with_existing_opening_odds(self, mock_sb, mock_fetcher_cls):
        from scripts.fetch_opening_odds import fetch_opening_odds

        mock_sb.return_value = MOCK_SCOREBOARD_GAMES

        mock_fetcher = MagicMock()
        mock_fetcher_cls.return_value = mock_fetcher

        db = MagicMock()
        # Both games already have opening odds
        db.execute_query.side_effect = lambda q, p=None: (
            [{"game_id": "401720001"}, {"game_id": "401720002"}]
            if "snapshot_type" in q
            else []
        )

        result = fetch_opening_odds(db)

        assert result["skipped_existing"] == 2
        mock_fetcher.fetch_game_odds.assert_not_called()

    @patch("scripts.fetch_opening_odds.fetch_espn_scoreboard")
    def test_no_games_tomorrow(self, mock_sb):
        from scripts.fetch_opening_odds import fetch_opening_odds

        mock_sb.return_value = []
        db = MagicMock()

        result = fetch_opening_odds(db)

        assert result["games_found"] == 0
        assert result["odds_fetched"] == 0


class TestStoreOpeningSnapshot:
    """Tests for store_opening_snapshot()."""

    def test_stores_all_three_markets(self):
        from scripts.fetch_opening_odds import store_opening_snapshot

        snapshot = _make_mock_snapshot()
        db = MagicMock()

        store_opening_snapshot(db, snapshot)

        # Verify execute_query was called with INSERT
        call_args = db.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        assert "INSERT" in query
        assert "odds_snapshots" in query
        # Check snapshot_type is 'opening'
        assert "opening" in params

    def test_stores_moneyline_spread_total(self):
        from scripts.fetch_opening_odds import store_opening_snapshot

        snapshot = _make_mock_snapshot()
        db = MagicMock()

        store_opening_snapshot(db, snapshot)

        call_args = db.execute_query.call_args
        params = call_args[0][1]

        # Params should contain ML, spread, and total data
        # game_id, sportsbook, captured_at, spread_home, spread_home_odds,
        # spread_away_odds, total, over_odds, under_odds,
        # moneyline_home, moneyline_away, is_closing, confidence, snapshot_type
        assert -150 in params  # home ML
        assert 130 in params   # away ML
        assert -3.5 in params  # spread
        assert 145.5 in params  # total
```

**Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_fetch_opening_odds.py -v --tb=short`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.fetch_opening_odds'`

**Step 3: Write the implementation**

Create `scripts/fetch_opening_odds.py`:

```python
"""Fetch Opening Odds for Tomorrow's Games.

Queries ESPN Scoreboard API for tomorrow's game IDs, then fetches
current odds from ESPN Core API. At 11pm (nightly run), current
odds represent the opening/early lines for next day's games.

All three markets captured: moneyline, spread, total.

Usage:
    python scripts/fetch_opening_odds.py                    # Tomorrow
    python scripts/fetch_opening_odds.py --date 2026-02-25  # Specific date
    python scripts/fetch_opening_odds.py --dry-run           # Preview only
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import DATABASE_PATH
from pipelines.espn_core_odds_provider import ESPNCoreOddsFetcher, OddsSnapshot
from scripts.daily_predictions import fetch_espn_scoreboard
from tracking.database import BettingDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def store_opening_snapshot(db: BettingDatabase, snapshot: OddsSnapshot) -> None:
    """Store an opening odds snapshot to the database.

    Uses the 'current' fields from OddsSnapshot (which at 11pm
    represent opening/early lines for next-day games).

    Args:
        db: BettingDatabase instance.
        snapshot: OddsSnapshot from ESPN Core API.
    """
    db.execute_query(
        """INSERT OR IGNORE INTO odds_snapshots
            (game_id, sportsbook, captured_at,
             spread_home, spread_home_odds, spread_away_odds,
             total, over_odds, under_odds,
             moneyline_home, moneyline_away,
             is_closing, confidence, snapshot_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            snapshot.game_id,
            snapshot.provider_name.lower().replace(" ", "_"),
            datetime.now(timezone.utc).isoformat(),
            snapshot.spread,
            snapshot.home_spread_odds,
            snapshot.away_spread_odds,
            snapshot.over_under,
            snapshot.over_odds,
            snapshot.under_odds,
            snapshot.home_moneyline,
            snapshot.away_moneyline,
            False,    # is_closing
            0.92,     # confidence (ESPN Core API)
            "opening",
        ),
    )


def fetch_opening_odds(
    db: BettingDatabase,
    target_date: datetime | None = None,
) -> dict:
    """Fetch opening odds for a date's games.

    Args:
        db: BettingDatabase instance.
        target_date: Date to fetch odds for. Default: tomorrow.

    Returns:
        Dict with fetch statistics.
    """
    if target_date is None:
        target_date = datetime.now() + timedelta(days=1)

    date_str = target_date.strftime("%Y-%m-%d")
    logger.info("Fetching opening odds for %s", date_str)

    result = {
        "date": date_str,
        "games_found": 0,
        "odds_fetched": 0,
        "odds_failed": 0,
        "skipped_existing": 0,
    }

    # Step 1: Discover games from ESPN Scoreboard
    games = fetch_espn_scoreboard(target_date)
    result["games_found"] = len(games)

    if not games:
        logger.info("No games found for %s", date_str)
        return result

    # Step 2: Check which games already have opening odds
    game_ids = [g["game_id"] for g in games]
    placeholders = ",".join("?" for _ in game_ids)
    existing = db.execute_query(
        f"SELECT game_id FROM odds_snapshots "
        f"WHERE game_id IN ({placeholders}) AND snapshot_type = 'opening'",
        tuple(game_ids),
    )
    existing_ids = {r["game_id"] for r in existing}

    games_to_fetch = [g for g in games if g["game_id"] not in existing_ids]
    result["skipped_existing"] = len(existing_ids)

    if not games_to_fetch:
        logger.info("All %d games already have opening odds", len(games))
        return result

    logger.info(
        "%d games need opening odds (%d already exist)",
        len(games_to_fetch),
        len(existing_ids),
    )

    # Step 3: Fetch odds from ESPN Core API
    fetcher = ESPNCoreOddsFetcher(sport="ncaab")
    try:
        for game in games_to_fetch:
            game_id = game["game_id"]
            try:
                snapshots = fetcher.fetch_game_odds(game_id)
                if snapshots:
                    # Prefer non-live provider, take first
                    pre_game = [s for s in snapshots if s.provider_id != 59]
                    best = pre_game[0] if pre_game else snapshots[0]
                    store_opening_snapshot(db, best)
                    result["odds_fetched"] += 1
                    logger.info(
                        "Opening odds: %s @ %s — ML %s/%s, Spread %s, Total %s",
                        game["away_name"],
                        game["home_name"],
                        best.home_moneyline,
                        best.away_moneyline,
                        best.spread,
                        best.over_under,
                    )
                else:
                    result["odds_failed"] += 1
                    logger.warning(
                        "No odds available for %s @ %s (%s)",
                        game["away_name"],
                        game["home_name"],
                        game_id,
                    )
            except Exception as e:
                result["odds_failed"] += 1
                logger.error("Failed to fetch odds for %s: %s", game_id, e)
    finally:
        fetcher.close()

    logger.info(
        "Opening odds complete: %d fetched, %d failed, %d skipped",
        result["odds_fetched"],
        result["odds_failed"],
        result["skipped_existing"],
    )
    return result


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch opening odds for tomorrow's NCAAB games"
    )
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date (YYYY-MM-DD). Default: tomorrow.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview games without fetching odds.",
    )
    args = parser.parse_args()

    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d")
    else:
        target = datetime.now() + timedelta(days=1)

    if args.dry_run:
        games = fetch_espn_scoreboard(target)
        print(f"Games for {target.strftime('%Y-%m-%d')}: {len(games)}")
        for g in games:
            print(f"  {g['away_name']} @ {g['home_name']} ({g['game_id']})")
        return

    db = BettingDatabase(str(DATABASE_PATH))
    result = fetch_opening_odds(db, target)

    print(f"\n{'=' * 50}")
    print(f"Opening Odds Fetch — {result['date']}")
    print(f"{'=' * 50}")
    print(f"Games found:     {result['games_found']}")
    print(f"Odds fetched:    {result['odds_fetched']}")
    print(f"Already existed: {result['skipped_existing']}")
    print(f"Failed:          {result['odds_failed']}")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_fetch_opening_odds.py -v --tb=short`
Expected: 6/6 pass

**Step 5: Run existing tests to verify no regressions**

Run: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py -v --tb=short`
Expected: 26/26 pass

**Step 6: Manual smoke test**

Run:
```bash
venv/Scripts/python.exe scripts/fetch_opening_odds.py --dry-run
```
Expected: Lists tomorrow's games (or "0 games" if no NCAAB slate).

**Step 7: Commit**

```bash
git add scripts/fetch_opening_odds.py tests/test_fetch_opening_odds.py
git commit -m "feat: add opening odds fetcher for nightly pipeline"
```

---

## Task 3: Add Opening Odds Step to `nightly-refresh.ps1`

**Files:**
- Modify: `scripts/nightly-refresh.ps1:79-97` (steps hashtable)

**Step 1: Add the step**

In `scripts/nightly-refresh.ps1`, insert a new entry in the `$steps` ordered hashtable between `scrape_barttorvik` and `generate_dashboard`. After the `scrape_barttorvik` block (line 84), add:

```powershell
    fetch_opening_odds = @{
        script    = "fetch_opening_odds.py"
        args      = @()
        critical  = $false
        timeout   = 180
    }
```

This runs after Barttorvik scraping and before dashboard generation. Non-critical so a failure doesn't abort the pipeline.

**Step 2: Test with dry run**

Run:
```powershell
.\scripts\nightly-refresh.ps1 -DryRun
```

Expected: Output includes `Step: fetch_opening_odds` in the dry run log with `[DRY RUN]` prefix.

**Step 3: Commit**

```bash
git add scripts/nightly-refresh.ps1
git commit -m "feat: add opening odds fetch step to nightly pipeline"
```

---

## Task 4: Add CLV Calculation to Settlement

**Files:**
- Modify: `scripts/daily_run.py:52-153` (`settle_yesterdays_bets()`)
- Test: `tests/test_daily_run.py` (add new tests to `TestSettlement`)

**Step 1: Write failing tests**

Add to `tests/test_daily_run.py` inside the existing `TestSettlement` class:

```python
    @patch("scripts.daily_run.ESPNCoreOddsFetcher")
    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_settle_calculates_clv(self, mock_fetch, mock_fetcher_cls):
        from scripts.daily_run import settle_yesterdays_bets
        from pipelines.espn_core_odds_provider import OddsSnapshot

        mock_fetch.return_value = [
            {
                "game_id": "401720001",
                "home": "DUKE",
                "away": "UNC",
                "home_name": "Duke Blue Devils",
                "away_name": "North Carolina Tar Heels",
                "home_score": 85,
                "away_score": 72,
                "status": "STATUS_FINAL",
            }
        ]

        # Mock ESPN Core API returning closing odds
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_game_odds.return_value = [
            OddsSnapshot(
                game_id="401720001",
                provider_id=100,
                provider_name="Draft Kings",
                home_moneyline=-160,
                away_moneyline=140,
                spread=-3.5,
                home_spread_odds=-110,
                away_spread_odds=-110,
                over_under=145.5,
                over_odds=-110,
                under_odds=-110,
                home_ml_close=-160,
                away_ml_close=140,
                home_spread_close=-3.5,
                home_spread_odds_close=-112,
                away_spread_close=3.5,
                away_spread_odds_close=-108,
                total_close=146.0,
                over_odds_close=-108,
                under_odds_close=-112,
            )
        ]
        mock_fetcher_cls.return_value = mock_fetcher

        # Track all SQL updates
        updates = []

        def mock_execute(q, p=None):
            if "SELECT * FROM bets" in q:
                return [
                    {
                        "id": 1,
                        "game_id": "401720001",
                        "selection": "Duke Blue Devils ML",
                        "bet_type": "moneyline",
                        "odds_placed": -150,
                        "stake": 100.0,
                    }
                ]
            if "UPDATE bets" in q:
                updates.append((q, p))
                return None
            return []

        db = MagicMock()
        db.execute_query.side_effect = mock_execute

        result = settle_yesterdays_bets(db, "2026-02-16")

        assert result["settled"] == 1
        assert result["clv_updated"] >= 1

        # Verify CLV update was called
        clv_updates = [
            (q, p) for q, p in updates if "odds_closing" in q or "clv" in q
        ]
        assert len(clv_updates) >= 1

    @patch("scripts.daily_run.ESPNCoreOddsFetcher")
    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_settle_clv_graceful_on_missing_odds(self, mock_fetch, mock_fetcher_cls):
        from scripts.daily_run import settle_yesterdays_bets

        mock_fetch.return_value = [
            {
                "game_id": "401720001",
                "home": "DUKE",
                "away": "UNC",
                "home_name": "Duke Blue Devils",
                "away_name": "North Carolina Tar Heels",
                "home_score": 85,
                "away_score": 72,
                "status": "STATUS_FINAL",
            }
        ]

        # ESPN Core API returns no odds
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_game_odds.return_value = []
        mock_fetcher_cls.return_value = mock_fetcher

        db = MagicMock()
        db.execute_query.side_effect = lambda q, p=None: (
            [
                {
                    "id": 1,
                    "game_id": "401720001",
                    "selection": "Duke Blue Devils ML",
                    "bet_type": "moneyline",
                    "odds_placed": -150,
                    "stake": 100.0,
                }
            ]
            if "SELECT * FROM bets" in q
            else None
        )

        result = settle_yesterdays_bets(db, "2026-02-16")

        # Settlement still works even without closing odds
        assert result["settled"] == 1
        assert result["clv_failed"] >= 1

    @patch("scripts.daily_run.ESPNCoreOddsFetcher")
    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_settle_stores_closing_snapshot(self, mock_fetch, mock_fetcher_cls):
        from scripts.daily_run import settle_yesterdays_bets
        from pipelines.espn_core_odds_provider import OddsSnapshot

        mock_fetch.return_value = [
            {
                "game_id": "401720001",
                "home": "DUKE",
                "away": "UNC",
                "home_name": "Duke Blue Devils",
                "away_name": "North Carolina Tar Heels",
                "home_score": 85,
                "away_score": 72,
                "status": "STATUS_FINAL",
            }
        ]

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_game_odds.return_value = [
            OddsSnapshot(
                game_id="401720001",
                provider_id=100,
                provider_name="Draft Kings",
                home_ml_close=-160,
                away_ml_close=140,
                home_spread_close=-3.5,
                home_spread_odds_close=-112,
                away_spread_close=3.5,
                away_spread_odds_close=-108,
                total_close=146.0,
                over_odds_close=-108,
                under_odds_close=-112,
            )
        ]
        mock_fetcher_cls.return_value = mock_fetcher

        inserts = []

        def mock_execute(q, p=None):
            if "SELECT * FROM bets" in q:
                return [
                    {
                        "id": 1,
                        "game_id": "401720001",
                        "selection": "Duke Blue Devils ML",
                        "bet_type": "moneyline",
                        "odds_placed": -150,
                        "stake": 100.0,
                    }
                ]
            if "INSERT" in q and "odds_snapshots" in q:
                inserts.append((q, p))
            return None

        db = MagicMock()
        db.execute_query.side_effect = mock_execute

        settle_yesterdays_bets(db, "2026-02-16")

        # Verify closing snapshot was stored
        assert len(inserts) >= 1
        insert_params = inserts[0][1]
        assert "closing" in insert_params  # snapshot_type
```

**Step 2: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py::TestSettlement -v --tb=short`
Expected: New tests FAIL (old tests still pass)

**Step 3: Modify `settle_yesterdays_bets()` in `scripts/daily_run.py`**

Add the import at the top of the file (near the other imports around line 31):

```python
from pipelines.espn_core_odds_provider import ESPNCoreOddsFetcher, OddsSnapshot
from betting.odds_converter import american_to_implied_prob, calculate_clv
```

Replace the `settle_yesterdays_bets()` function (lines 52-153) with:

```python
def settle_yesterdays_bets(db: BettingDatabase, settle_date: str | None = None) -> dict:
    """Settle paper bets from a past date using ESPN final scores.

    After settling win/loss, fetches closing odds from ESPN Core API
    and calculates CLV for each bet.

    Args:
        db: BettingDatabase instance.
        settle_date: Date to settle (YYYY-MM-DD). Default: yesterday.

    Returns:
        Dict with settlement and CLV stats.
    """
    if settle_date is None:
        settle_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    # Get pending bets for the date
    pending = db.execute_query(
        "SELECT * FROM bets WHERE game_date = ? AND result IS NULL AND is_live = 0",
        (settle_date,),
    )

    if not pending:
        logger.info("No pending bets to settle for %s", settle_date)
        return {"date": settle_date, "settled": 0, "pending": 0}

    # Fetch final scores from ESPN
    settle_dt = datetime.strptime(settle_date, "%Y-%m-%d")
    games = fetch_espn_scoreboard(settle_dt)
    final_games = {
        g["game_id"]: g for g in games if g["status"] in ("STATUS_FINAL", "STATUS_FINAL_OT")
    }

    # ── Pass 1: Settle win/loss ──────────────────────────────────────────
    settled_count = 0
    settled_game_ids: set[str] = set()

    for bet in pending:
        game_id = bet["game_id"] or ""
        if game_id not in final_games:
            logger.debug("Game %s not final yet, skipping", game_id)
            continue

        game = final_games[game_id]
        home_score = game["home_score"]
        away_score = game["away_score"]

        # Determine result based on selection
        selection = bet["selection"] or ""
        bet_type = bet["bet_type"] or ""

        if bet_type == "moneyline":
            # Parse which team was bet on
            home_abbr = game["home"]
            away_abbr = game["away"]

            # Check if bet was on home or away
            if "HOME" in selection.upper() or home_abbr in selection:
                won = home_score > away_score
            elif "AWAY" in selection.upper() or away_abbr in selection:
                won = away_score > home_score
            else:
                # Try matching by team name
                if game["home_name"] in selection:
                    won = home_score > away_score
                elif game["away_name"] in selection:
                    won = away_score > home_score
                else:
                    logger.warning("Cannot determine result for bet: %s", selection)
                    continue

            result = "win" if won else "loss"
            odds_placed = bet["odds_placed"] or -110
            stake = bet["stake"] or 0

            if won and odds_placed != 0:
                from betting.odds_converter import american_to_decimal

                decimal_odds = american_to_decimal(odds_placed)
                profit = stake * (decimal_odds - 1)
            else:
                profit = -stake

            # Update bet in database
            try:
                db.execute_query(
                    """UPDATE bets
                       SET result = ?, profit_loss = ?
                       WHERE id = ?""",
                    (result, profit, bet["id"]),
                )
                settled_count += 1
                settled_game_ids.add(game_id)
                logger.info(
                    "Settled bet #%d: %s -> %s ($%+.2f)",
                    bet["id"],
                    selection,
                    result,
                    profit,
                )
            except Exception as e:
                logger.error("Failed to settle bet #%d: %s", bet["id"], e)

    # ── Pass 2: Fetch closing odds and calculate CLV ─────────────────────
    clv_updated = 0
    clv_failed = 0
    clv_values: list[float] = []

    if settled_game_ids:
        closing_odds: dict[str, OddsSnapshot] = {}
        fetcher = ESPNCoreOddsFetcher(sport="ncaab")
        try:
            for game_id in settled_game_ids:
                try:
                    snapshots = fetcher.fetch_game_odds(game_id)
                    if snapshots:
                        pre_game = [s for s in snapshots if s.provider_id != 59]
                        best = pre_game[0] if pre_game else snapshots[0]
                        closing_odds[game_id] = best

                        # Store closing snapshot
                        _store_closing_snapshot(db, best)
                    else:
                        logger.warning("No closing odds for game %s", game_id)
                except Exception as e:
                    logger.error("Failed to fetch closing odds for %s: %s", game_id, e)
        finally:
            fetcher.close()

        # Calculate CLV for each settled bet
        for bet in pending:
            game_id = bet["game_id"] or ""
            if game_id not in closing_odds:
                if game_id in settled_game_ids:
                    clv_failed += 1
                continue

            snapshot = closing_odds[game_id]
            odds_placed = bet["odds_placed"]
            if not odds_placed:
                continue

            selection = bet["selection"] or ""
            game = final_games.get(game_id, {})

            # Determine which closing ML to use based on bet side
            closing_ml = _get_closing_ml_for_bet(selection, game, snapshot)
            if closing_ml is None:
                clv_failed += 1
                continue

            try:
                clv = calculate_clv(odds_placed, closing_ml)
                db.execute_query(
                    """UPDATE bets
                       SET odds_closing = ?, clv = ?
                       WHERE id = ?""",
                    (closing_ml, clv, bet["id"]),
                )
                clv_updated += 1
                clv_values.append(clv)
                logger.info(
                    "CLV bet #%d: placed %+d, closed %+d, CLV %+.2f%%",
                    bet["id"],
                    odds_placed,
                    closing_ml,
                    clv * 100,
                )
            except Exception as e:
                logger.error("Failed to update CLV for bet #%d: %s", bet["id"], e)
                clv_failed += 1

    avg_clv = sum(clv_values) / len(clv_values) if clv_values else 0.0

    return {
        "date": settle_date,
        "settled": settled_count,
        "pending": len(pending) - settled_count,
        "total_pending": len(pending),
        "clv_updated": clv_updated,
        "clv_failed": clv_failed,
        "avg_clv": avg_clv,
    }


def _get_closing_ml_for_bet(
    selection: str,
    game: dict,
    snapshot: OddsSnapshot,
) -> int | None:
    """Determine the correct closing moneyline for a bet's side.

    Matches bet selection text to home/away, then returns the
    corresponding closing ML from the OddsSnapshot.

    Args:
        selection: Bet selection string (e.g. "Duke Blue Devils ML").
        game: Game dict from ESPN scoreboard.
        snapshot: OddsSnapshot with closing odds.

    Returns:
        Closing moneyline integer, or None if side can't be determined.
    """
    home_abbr = game.get("home", "")
    away_abbr = game.get("away", "")
    home_name = game.get("home_name", "")
    away_name = game.get("away_name", "")

    is_home = (
        "HOME" in selection.upper()
        or home_abbr in selection
        or home_name in selection
    )
    is_away = (
        "AWAY" in selection.upper()
        or away_abbr in selection
        or away_name in selection
    )

    if is_home and snapshot.home_ml_close is not None:
        return snapshot.home_ml_close
    if is_away and snapshot.away_ml_close is not None:
        return snapshot.away_ml_close

    # Fallback: try current ML if close not available
    if is_home and snapshot.home_moneyline is not None:
        return snapshot.home_moneyline
    if is_away and snapshot.away_moneyline is not None:
        return snapshot.away_moneyline

    return None


def _store_closing_snapshot(db: BettingDatabase, snapshot: OddsSnapshot) -> None:
    """Store a closing odds snapshot to odds_snapshots table.

    Args:
        db: BettingDatabase instance.
        snapshot: OddsSnapshot with closing data from ESPN Core API.
    """
    from datetime import timezone

    db.execute_query(
        """INSERT OR IGNORE INTO odds_snapshots
            (game_id, sportsbook, captured_at,
             spread_home, spread_home_odds, spread_away_odds,
             total, over_odds, under_odds,
             moneyline_home, moneyline_away,
             is_closing, confidence, snapshot_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            snapshot.game_id,
            snapshot.provider_name.lower().replace(" ", "_"),
            datetime.now(timezone.utc).isoformat(),
            snapshot.home_spread_close or snapshot.spread,
            snapshot.home_spread_odds_close or snapshot.home_spread_odds,
            snapshot.away_spread_odds_close or snapshot.away_spread_odds,
            snapshot.total_close or snapshot.over_under,
            snapshot.over_odds_close or snapshot.over_odds,
            snapshot.under_odds_close or snapshot.under_odds,
            snapshot.home_ml_close or snapshot.home_moneyline,
            snapshot.away_ml_close or snapshot.away_moneyline,
            True,      # is_closing
            0.92,      # confidence (ESPN Core API)
            "closing",
        ),
    )
```

**Step 4: Run the new settlement tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py::TestSettlement -v --tb=short`
Expected: All tests pass (including new CLV tests)

**Step 5: Run full test suite for regressions**

Run: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py -v --tb=short`
Expected: All 26 existing tests + 3 new tests pass

**Step 6: Commit**

```bash
git add scripts/daily_run.py tests/test_daily_run.py
git commit -m "feat: calculate CLV during settlement using ESPN Core API closing odds"
```

---

## Task 5: Update Settlement Output in `morning-betting.ps1` and `daily_run.py:main()`

**Files:**
- Modify: `scripts/daily_run.py:446-449` (settlement output in `main()`)

**Step 1: Update the settlement output in `main()`**

In `scripts/daily_run.py`, the `main()` function prints settlement results at line 448. Update to show CLV info:

```python
        print(f"Settled: {settle_result['settled']}, Pending: {settle_result['pending']}")
        if settle_result.get("clv_updated", 0) > 0:
            print(
                f"CLV: {settle_result['clv_updated']} updated, "
                f"avg CLV: {settle_result['avg_clv']:+.2%}"
            )
        if settle_result.get("clv_failed", 0) > 0:
            print(f"CLV failed: {settle_result['clv_failed']} (no closing odds)")
```

**Step 2: Verify output with dry settle**

Run:
```bash
venv/Scripts/python.exe scripts/daily_run.py --settle-only
```

Expected: Settlement runs, shows CLV stats for any settled bets.

**Step 3: Commit**

```bash
git add scripts/daily_run.py
git commit -m "feat: display CLV stats in settlement output"
```

---

## Task 6: Remove Stale Import and Clean Up

**Files:**
- Modify: `scripts/daily_run.py` (move `american_to_decimal` import out of the loop)

**Step 1: Clean up the inline import**

The existing code has `from betting.odds_converter import american_to_decimal` inside the settlement loop (line 122). Now that we import `calculate_clv` and `american_to_implied_prob` at the top, move `american_to_decimal` to the top-level import block too. Remove the inline import from inside the loop.

The top-level imports (added in Task 4) should be:

```python
from betting.odds_converter import american_to_decimal, american_to_implied_prob, calculate_clv
```

And delete the `from betting.odds_converter import american_to_decimal` line inside the `if won and odds_placed != 0:` block.

**Step 2: Run tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py -v --tb=short`
Expected: All pass

**Step 3: Commit all changes**

```bash
git add scripts/daily_run.py
git commit -m "refactor: move odds_converter imports to top level"
```

---

## Verification Checklist

After all tasks complete, verify end-to-end:

1. **Schema**: `venv/Scripts/python.exe -c "from tracking.database import BettingDatabase; from config.settings import DATABASE_PATH; db = BettingDatabase(str(DATABASE_PATH)); print(db.execute_query('PRAGMA table_info(odds_snapshots)'))"` — should show `snapshot_type` column

2. **Opening odds**: `venv/Scripts/python.exe scripts/fetch_opening_odds.py --dry-run` — should list tomorrow's games

3. **Nightly pipeline**: `.\scripts\nightly-refresh.ps1 -DryRun` — should show `fetch_opening_odds` step

4. **Settlement CLV**: `venv/Scripts/python.exe scripts/daily_run.py --settle-only` — should show CLV stats

5. **Full test suite**: `venv/Scripts/python.exe -m pytest tests/test_daily_run.py tests/test_fetch_opening_odds.py -v` — all green

6. **Check CLV data**: `venv/Scripts/python.exe -c "from tracking.database import BettingDatabase; from config.settings import DATABASE_PATH; db = BettingDatabase(str(DATABASE_PATH)); rows = db.execute_query('SELECT id, selection, odds_placed, odds_closing, clv FROM bets WHERE clv IS NOT NULL'); [print(dict(r)) for r in rows]"` — should show CLV values on settled bets
