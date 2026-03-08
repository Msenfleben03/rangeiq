# MLB Odds Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Backfill historical MLB moneyline odds from ESPN Core API and integrate edge/CLV calculation into the walk-forward backtest.

**Architecture:** Add an `odds` table to `mlb_data.db`, write a backfill script that maps MLBAM game_pks to ESPN event IDs via the scoreboard API, fetches odds using the existing `ESPNCoreOddsProvider`, and stores open/close moneylines. The backtest loads odds at startup and computes edge per prediction.

**Tech Stack:** SQLite, existing `ESPNCoreOddsProvider` (pipelines/espn_core_odds_provider.py), requests

---

### Task 1: Add odds table to mlb_data.db

**Files:**
- Modify: `scripts/mlb_init_db.py`
- Test: manual — run init script and verify table exists

**Step 1: Add odds table DDL to mlb_init_db.py**

Find the section that creates tables and add after the last CREATE TABLE:

```python
# In the schema creation section, add:
"""
CREATE TABLE IF NOT EXISTS odds (
    game_pk         INTEGER NOT NULL REFERENCES games(game_pk),
    provider        TEXT NOT NULL,
    home_ml_open    INTEGER,
    away_ml_open    INTEGER,
    home_ml_close   INTEGER,
    away_ml_close   INTEGER,
    total_open      REAL,
    total_close     REAL,
    fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game_pk, provider)
);
CREATE INDEX IF NOT EXISTS idx_odds_game ON odds(game_pk);
"""
```

**Step 2: Run the init script to create the table**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -c "import sqlite3; conn=sqlite3.connect('data/mlb_data.db'); conn.execute('CREATE TABLE IF NOT EXISTS odds (game_pk INTEGER NOT NULL REFERENCES games(game_pk), provider TEXT NOT NULL, home_ml_open INTEGER, away_ml_open INTEGER, home_ml_close INTEGER, away_ml_close INTEGER, total_open REAL, total_close REAL, fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (game_pk, provider))'); conn.execute('CREATE INDEX IF NOT EXISTS idx_odds_game ON odds(game_pk)'); conn.commit(); print('odds table created')"`

**Step 3: Verify**

Run: `sqlite3 data/mlb_data.db ".schema odds"`
Expected: the CREATE TABLE statement above

**Step 4: Commit**

```bash
git add scripts/mlb_init_db.py
git commit -m "feat(mlb): add odds table to mlb_data.db schema"
```

---

### Task 2: Create MLB odds backfill script (tests)

**Files:**
- Create: `scripts/mlb_backfill_odds.py`
- Create: `tests/test_mlb_backfill_odds.py`

**Step 1: Write tests for team ID mapping and DB insert**

```python
"""Tests for MLB odds backfill script."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Import after creation
from scripts.mlb_backfill_odds import (
    ESPN_TO_MLBAM,
    MLBAM_TO_ESPN,
    insert_odds,
    match_espn_to_mlbam,
)


class TestTeamMapping:
    """Tests for MLBAM <-> ESPN team ID mapping."""

    def test_mapping_has_30_teams(self):
        """Both mappings should have 30 entries."""
        assert len(MLBAM_TO_ESPN) == 30
        assert len(ESPN_TO_MLBAM) == 30

    def test_mapping_is_invertible(self):
        """MLBAM->ESPN and ESPN->MLBAM are inverses."""
        for mlbam_id, espn_id in MLBAM_TO_ESPN.items():
            assert ESPN_TO_MLBAM[espn_id] == mlbam_id

    def test_known_mappings(self):
        """Spot-check known team IDs."""
        assert MLBAM_TO_ESPN[147] == 10  # NYY
        assert MLBAM_TO_ESPN[111] == 2   # BOS
        assert MLBAM_TO_ESPN[119] == 19  # LAD
        assert ESPN_TO_MLBAM[10] == 147  # NYY


class TestMatchEspnToMlbam:
    """Tests for matching ESPN events to MLBAM game_pks."""

    def test_match_by_home_and_away(self):
        """Match ESPN event to game_pk via team IDs."""
        games = {
            (108, 147): 776001,  # LAA @ NYY
            (111, 119): 776002,  # BOS @ LAD
        }
        # ESPN event: LAA(3) @ NYY(10)
        result = match_espn_to_mlbam(
            espn_home_id=10, espn_away_id=3, games_by_teams=games
        )
        assert result == 776001

    def test_no_match_returns_none(self):
        """Unknown team combo returns None."""
        games = {(108, 147): 776001}
        result = match_espn_to_mlbam(
            espn_home_id=99, espn_away_id=99, games_by_teams=games
        )
        assert result is None


class TestInsertOdds:
    """Tests for inserting odds into mlb_data.db."""

    def test_insert_and_retrieve(self, tmp_path):
        """Insert odds row and read it back."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE odds ("
            "game_pk INTEGER NOT NULL, provider TEXT NOT NULL, "
            "home_ml_open INTEGER, away_ml_open INTEGER, "
            "home_ml_close INTEGER, away_ml_close INTEGER, "
            "total_open REAL, total_close REAL, "
            "fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY (game_pk, provider))"
        )
        insert_odds(conn, 776001, "espn_bet", -150, 130, -145, 125, 8.5, 8.0)
        conn.commit()

        row = conn.execute("SELECT * FROM odds WHERE game_pk=776001").fetchone()
        assert row is not None
        assert row[0] == 776001  # game_pk
        assert row[2] == -150    # home_ml_open
        assert row[4] == -145    # home_ml_close
        conn.close()

    def test_upsert_on_duplicate(self, tmp_path):
        """Second insert for same game+provider updates values."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE odds ("
            "game_pk INTEGER NOT NULL, provider TEXT NOT NULL, "
            "home_ml_open INTEGER, away_ml_open INTEGER, "
            "home_ml_close INTEGER, away_ml_close INTEGER, "
            "total_open REAL, total_close REAL, "
            "fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY (game_pk, provider))"
        )
        insert_odds(conn, 776001, "espn_bet", -150, 130, None, None, None, None)
        insert_odds(conn, 776001, "espn_bet", -150, 130, -145, 125, 8.5, 8.0)
        conn.commit()

        count = conn.execute("SELECT COUNT(*) FROM odds WHERE game_pk=776001").fetchone()[0]
        assert count == 1  # upsert, not duplicate
        row = conn.execute("SELECT home_ml_close FROM odds WHERE game_pk=776001").fetchone()
        assert row[0] == -145
        conn.close()
```

**Step 2: Run tests to verify they fail**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m pytest tests/test_mlb_backfill_odds.py -v`
Expected: FAIL — module not found

---

### Task 3: Implement MLB odds backfill script

**Files:**
- Create: `scripts/mlb_backfill_odds.py`

**Step 3: Write the backfill script**

```python
"""Backfill historical MLB odds from ESPN Core API.

Usage:
    python scripts/mlb_backfill_odds.py --seasons 2023 2024 2025
    python scripts/mlb_backfill_odds.py --seasons 2025 --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.espn_core_odds_provider import (
    ESPNCoreClient,
    ESPNCoreOddsProvider,
    OddsSnapshot,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "mlb_data.db"

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_MLB_SCOREBOARD = f"{ESPN_SITE_BASE}/baseball/mlb/scoreboard"

# ============================================================================
# MLBAM <-> ESPN team ID mapping (30 teams)
# ============================================================================

MLBAM_TO_ESPN: dict[int, int] = {
    108: 3,   # LAA
    109: 29,  # ARI
    110: 1,   # BAL
    111: 2,   # BOS
    112: 16,  # CHC
    113: 17,  # CIN
    114: 5,   # CLE
    115: 27,  # COL
    116: 6,   # DET
    117: 18,  # HOU
    118: 7,   # KC
    119: 19,  # LAD
    120: 20,  # WSH
    121: 21,  # NYM
    133: 11,  # OAK/ATH
    134: 23,  # PIT
    135: 25,  # SD
    136: 12,  # SEA
    137: 26,  # SF
    138: 24,  # STL
    139: 30,  # TB
    140: 13,  # TEX
    141: 14,  # TOR
    142: 9,   # MIN
    143: 22,  # PHI
    144: 15,  # ATL
    145: 4,   # CWS
    146: 28,  # MIA
    147: 10,  # NYY
    158: 8,   # MIL
}

ESPN_TO_MLBAM: dict[int, int] = {v: k for k, v in MLBAM_TO_ESPN.items()}


def match_espn_to_mlbam(
    espn_home_id: int,
    espn_away_id: int,
    games_by_teams: dict[tuple[int, int], int],
) -> int | None:
    """Match an ESPN event to an MLBAM game_pk.

    Args:
        espn_home_id: ESPN home team ID.
        espn_away_id: ESPN away team ID.
        games_by_teams: Dict mapping (away_mlbam_id, home_mlbam_id) to game_pk.

    Returns:
        game_pk if matched, None otherwise.
    """
    mlbam_home = ESPN_TO_MLBAM.get(espn_home_id)
    mlbam_away = ESPN_TO_MLBAM.get(espn_away_id)
    if mlbam_home is None or mlbam_away is None:
        return None
    return games_by_teams.get((mlbam_away, mlbam_home))


def insert_odds(
    conn: sqlite3.Connection,
    game_pk: int,
    provider: str,
    home_ml_open: int | None,
    away_ml_open: int | None,
    home_ml_close: int | None,
    away_ml_close: int | None,
    total_open: float | None,
    total_close: float | None,
) -> None:
    """Insert or replace odds row."""
    conn.execute(
        "INSERT OR REPLACE INTO odds "
        "(game_pk, provider, home_ml_open, away_ml_open, "
        "home_ml_close, away_ml_close, total_open, total_close, fetched_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            game_pk, provider, home_ml_open, away_ml_open,
            home_ml_close, away_ml_close, total_open, total_close,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def get_games_for_date(
    conn: sqlite3.Connection, game_date: str
) -> dict[tuple[int, int], int]:
    """Get games for a date, keyed by (away_team_id, home_team_id) -> game_pk."""
    rows = conn.execute(
        "SELECT game_pk, home_team_id, away_team_id FROM games "
        "WHERE game_date = ? AND status = 'final'",
        (game_date,),
    ).fetchall()
    return {(r[2], r[1]): r[0] for r in rows}


def get_dates_needing_odds(
    conn: sqlite3.Connection, seasons: list[int]
) -> list[str]:
    """Get game dates that have final games but no odds yet."""
    placeholders = ",".join("?" for _ in seasons)
    rows = conn.execute(
        f"SELECT DISTINCT g.game_date FROM games g "
        f"WHERE g.season IN ({placeholders}) AND g.status = 'final' "
        f"AND g.game_pk NOT IN (SELECT game_pk FROM odds) "
        f"ORDER BY g.game_date",
        seasons,
    ).fetchall()
    return [r[0] for r in rows]


def fetch_espn_events(game_date: str) -> list[dict]:
    """Fetch ESPN MLB scoreboard events for a date.

    Returns list of dicts with keys: event_id, espn_home_id, espn_away_id.
    """
    date_compact = game_date.replace("-", "")
    url = f"{ESPN_MLB_SCOREBOARD}?dates={date_compact}&limit=500"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Scoreboard fetch failed for %s: %s", game_date, exc)
        return []

    events = []
    for ev in data.get("events", []):
        event_id = str(ev.get("id", ""))
        comps = ev.get("competitions", [{}])[0]
        competitors = comps.get("competitors", [])
        home = [c for c in competitors if c.get("homeAway") == "home"]
        away = [c for c in competitors if c.get("homeAway") == "away"]
        if not home or not away or not event_id:
            continue
        events.append({
            "event_id": event_id,
            "espn_home_id": int(home[0]["team"]["id"]),
            "espn_away_id": int(away[0]["team"]["id"]),
        })
    return events


def pick_best_snapshot(snapshots: list[OddsSnapshot]) -> OddsSnapshot | None:
    """Pick best odds snapshot (prefer non-live provider with closing odds)."""
    # Prefer providers with closing moneylines
    with_close = [s for s in snapshots if s.home_ml_close is not None]
    if with_close:
        # Prefer non-live providers (provider_id != 59)
        non_live = [s for s in with_close if s.provider_id != 59]
        return non_live[0] if non_live else with_close[0]
    # Fall back to any provider with opening moneylines
    with_open = [s for s in snapshots if s.home_ml_open is not None]
    if with_open:
        non_live = [s for s in with_open if s.provider_id != 59]
        return non_live[0] if non_live else with_open[0]
    return snapshots[0] if snapshots else None


def backfill_date(
    game_date: str,
    db_conn: sqlite3.Connection,
    odds_provider: ESPNCoreOddsProvider,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Backfill odds for all games on a single date.

    Returns (matched, total_games) count.
    """
    games_by_teams = get_games_for_date(db_conn, game_date)
    if not games_by_teams:
        return 0, 0

    espn_events = fetch_espn_events(game_date)
    time.sleep(0.5)  # rate limit scoreboard calls

    matched = 0
    for ev in espn_events:
        game_pk = match_espn_to_mlbam(
            ev["espn_home_id"], ev["espn_away_id"], games_by_teams
        )
        if game_pk is None:
            continue

        snapshots = odds_provider.fetch_game_odds(ev["event_id"])
        time.sleep(0.5)  # rate limit odds calls

        best = pick_best_snapshot(snapshots)
        if best is None:
            continue

        if dry_run:
            logger.info(
                "[DRY RUN] %s game_pk=%d: home_ml=%s/%s provider=%s",
                game_date, game_pk, best.home_ml_open, best.home_ml_close,
                best.provider_name,
            )
        else:
            insert_odds(
                db_conn, game_pk, best.provider_name,
                best.home_ml_open, best.away_ml_open,
                best.home_ml_close, best.away_ml_close,
                best.total_open, best.total_close,
            )
        matched += 1

    return matched, len(games_by_teams)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Backfill MLB odds from ESPN Core API")
    parser.add_argument(
        "--seasons", nargs="+", type=int, default=[2023, 2024, 2025],
        help="Seasons to backfill",
    )
    parser.add_argument(
        "--db-path", type=str, default=str(DB_PATH), help="Path to mlb_data.db",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print matches without writing to DB",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.db_path)

    # Ensure odds table exists
    conn.execute(
        "CREATE TABLE IF NOT EXISTS odds ("
        "game_pk INTEGER NOT NULL REFERENCES games(game_pk), "
        "provider TEXT NOT NULL, "
        "home_ml_open INTEGER, away_ml_open INTEGER, "
        "home_ml_close INTEGER, away_ml_close INTEGER, "
        "total_open REAL, total_close REAL, "
        "fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, "
        "PRIMARY KEY (game_pk, provider))"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_odds_game ON odds(game_pk)")
    conn.commit()

    dates = get_dates_needing_odds(conn, args.seasons)
    logger.info("Found %d dates needing odds for seasons %s", len(dates), args.seasons)

    odds_provider = ESPNCoreOddsProvider(sport="mlb", requests_per_second=2.0)

    total_matched = 0
    total_games = 0

    for i, game_date in enumerate(dates):
        matched, n_games = backfill_date(game_date, conn, odds_provider, args.dry_run)
        total_matched += matched
        total_games += n_games

        if (i + 1) % 10 == 0:
            if not args.dry_run:
                conn.commit()
            coverage = total_matched / total_games * 100 if total_games > 0 else 0
            logger.info(
                "Progress: %d/%d dates, %d/%d games matched (%.1f%%)",
                i + 1, len(dates), total_matched, total_games, coverage,
            )

    if not args.dry_run:
        conn.commit()

    coverage = total_matched / total_games * 100 if total_games > 0 else 0
    logger.info(
        "Done: %d/%d games with odds (%.1f%%) across %d dates",
        total_matched, total_games, coverage, len(dates),
    )
    conn.close()


if __name__ == "__main__":
    main()
```

**Step 4: Run tests**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m pytest tests/test_mlb_backfill_odds.py -v`
Expected: all 6 PASS

**Step 5: Lint**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m ruff check scripts/mlb_backfill_odds.py tests/test_mlb_backfill_odds.py && venv/Scripts/python.exe -m ruff format scripts/mlb_backfill_odds.py tests/test_mlb_backfill_odds.py`

**Step 6: Commit**

```bash
git add scripts/mlb_backfill_odds.py tests/test_mlb_backfill_odds.py
git commit -m "feat(mlb): add odds backfill script with ESPN Core API

MLBAM<->ESPN 30-team ID mapping, scoreboard event matching,
pick_best_snapshot provider selection, checkpoint every 10 dates.
6 tests covering mapping, matching, and DB insert/upsert."
```

---

### Task 4: Add edge calculation to backtest

**Files:**
- Modify: `scripts/mlb_backtest.py`
- Modify: `tests/test_mlb_poisson_model.py`

**Step 7: Write failing test for odds-aware backtest**

Add to `TestWalkForward` in `tests/test_mlb_poisson_model.py`:

```python
def test_backtest_with_odds_computes_edge(self):
    """When odds dict is provided, results include edge column."""
    from scripts.mlb_backtest import run_backtest

    rng = np.random.RandomState(42)
    games = []
    teams = list(range(100, 110))
    for season in [2023, 2024]:
        for i in range(200):
            h, a = rng.choice(teams, 2, replace=False)
            games.append(
                {
                    "game_pk": season * 1000 + i,
                    "game_date": f"{season}-06-15",
                    "season": season,
                    "home_team_id": int(h),
                    "away_team_id": int(a),
                    "home_score": int(rng.poisson(4.5)),
                    "away_score": int(rng.poisson(4.3)),
                    "home_starter_id": None,
                    "away_starter_id": None,
                }
            )
    df = pd.DataFrame(games)

    # Provide odds for some test games
    odds = {}
    for gpk in range(2024000, 2024050):
        odds[gpk] = {"home_ml_close": -130, "away_ml_close": 110}

    results = run_backtest(df, test_season=2024, odds=odds)
    assert "edge" in results.columns
    assert "home_ml_close" in results.columns
    # Games with odds should have non-null edge
    has_odds = results["home_ml_close"].notna()
    assert has_odds.sum() > 0
    assert results.loc[has_odds, "edge"].notna().all()
```

**Step 8: Run test to verify it fails**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py::TestWalkForward::test_backtest_with_odds_computes_edge -v`
Expected: FAIL — `run_backtest()` has no `odds` parameter

**Step 9: Implement odds integration in backtest**

In `scripts/mlb_backtest.py`:

1. Add `odds` parameter to `run_backtest()`:

```python
def run_backtest(
    games: pd.DataFrame,
    test_season: int,
    pitcher_adj: bool = False,
    pitcher_stats: dict[tuple[int, int], dict] | None = None,
    calibrated: bool = False,
    odds: dict[int, dict] | None = None,
) -> pd.DataFrame:
```

2. In the results append block, add edge calculation:

```python
        # Odds lookup
        game_odds = odds.get(int(row["game_pk"])) if odds else None
        ml_close = game_odds["home_ml_close"] if game_odds else None
        ml_away_close = game_odds["away_ml_close"] if game_odds else None

        # Edge: model prob minus implied prob from closing line
        edge = None
        if ml_close is not None:
            from betting.odds_converter import american_to_implied_prob
            implied = american_to_implied_prob(ml_close)
            edge = cal_prob - implied

        results.append(
            {
                ...existing fields...,
                "home_ml_close": ml_close,
                "away_ml_close": ml_away_close,
                "edge": edge,
            }
        )
```

3. Add a `load_odds()` helper:

```python
def load_odds(db_path: Path) -> dict[int, dict]:
    """Load odds from mlb_data.db keyed by game_pk."""
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT game_pk, home_ml_close, away_ml_close FROM odds"
    ).fetchall()
    conn.close()
    return {r[0]: {"home_ml_close": r[1], "away_ml_close": r[2]} for r in rows}
```

4. In `main()`, load odds automatically if the table exists:

```python
    # Load odds if available
    odds = None
    try:
        odds = load_odds(db_path)
        if odds:
            logger.info("Loaded odds for %d games", len(odds))
    except Exception:
        logger.info("No odds table found, skipping edge calculation")
```

5. Update `print_report()` to show edge stats when available:

```python
    # Edge stats (if odds available)
    if "edge" in results.columns and results["edge"].notna().any():
        has_edge = results[results["edge"].notna()]
        pos_edge = has_edge[has_edge["edge"] > 0]
        print(f"\nEdge Stats (odds available: {len(has_edge)}/{n} games)")
        print(f"  Mean edge:     {has_edge['edge'].mean():+.2%}")
        print(f"  Pos edge bets: {len(pos_edge)} ({len(pos_edge)/len(has_edge):.1%})")
        if len(pos_edge) > 0:
            # Flat-stake ROI on positive-edge bets
            pos_correct = pos_edge["correct"].sum()
            # Simple ROI: assume -110 juice on all bets
            wins = pos_correct
            losses = len(pos_edge) - pos_correct
            roi = (wins * 100 - losses * 110) / (len(pos_edge) * 110)
            print(f"  Flat-stake ROI: {roi:+.1%} (assuming -110)")
```

**Step 10: Run tests**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py -v`
Expected: 50/50 PASS

**Step 11: Lint**

Run: `cd /c/Users/msenf/sports-betting && venv/Scripts/python.exe -m ruff check scripts/mlb_backtest.py tests/test_mlb_poisson_model.py && venv/Scripts/python.exe -m ruff format scripts/mlb_backtest.py tests/test_mlb_poisson_model.py`

**Step 12: Commit**

```bash
git add scripts/mlb_backtest.py tests/test_mlb_poisson_model.py
git commit -m "feat(mlb): add edge calculation to walk-forward backtest

Loads odds from mlb_data.db, computes edge per prediction,
reports mean edge and flat-stake ROI on positive-edge bets.
Gracefully skips if no odds table exists."
```

---

### Task 5: Run odds backfill and re-backtest

**Step 13: Run the backfill (2025 first as smoke test)**

```bash
cd /c/Users/msenf/sports-betting
venv/Scripts/python.exe scripts/mlb_backfill_odds.py --seasons 2025 --dry-run
```

Verify it finds events and matches game_pks. Then run for real:

```bash
venv/Scripts/python.exe scripts/mlb_backfill_odds.py --seasons 2023 2024 2025
```

Expected: ~85-90% coverage across ~7,500 games.

**Step 14: Re-run backtest with odds**

```bash
venv/Scripts/python.exe scripts/mlb_backtest.py --test-season 2025 --pitcher-adj --calibrated
```

Expected: same accuracy/log loss as before, plus new Edge Stats section showing mean edge and flat-stake ROI.

**Step 15: Record results in session-state.md**
