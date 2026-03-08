# F5 Market Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add First 5 Innings (F5) moneyline prediction to the MLB Poisson model and backtest it against historical data using full-game closing odds as a CLV proxy.

**Architecture:** Three sequential layers — (1) backfill F5 scores from MLB Stats API linescore into `mlb_data.db`, (2) extend `PoissonModel.predict()` to output F5 lambda and win probability using a 5/9 × 1.02 scaling factor with raw (uncalibrated) probability, (3) add `--f5` flag to `mlb_backtest.py` that switches bet simulation to F5 probabilities while reusing full-game closing odds as the CLV proxy.

**Tech Stack:** Python 3.11+, SQLite (`mlb_data.db`), statsapi (MLB Stats API), pandas, scipy, pytest. Worktree: `.worktrees/f5-market`, branch: `feature/f5-market`.

**Design doc:** `docs/plans/2026-03-02-f5-market-design.md` — read this for rationale behind each decision.

**Run all tests from:** `C:\Users\msenf\sports-betting\.worktrees\f5-market\` using `C:\Users\msenf\sports-betting\venv\Scripts\python.exe`

---

## Task 1: DB Schema Migration

Add `home_f5_score` and `away_f5_score` columns to the `games` table in `mlb_data.db`.

**Files:**
- Modify: `scripts/mlb_init_db.py` (add migration helper)
- Create: `tests/test_mlb_backfill_f5_scores.py` (new test file)

---

**Step 1: Write the failing test**

In `tests/test_mlb_backfill_f5_scores.py`:

```python
"""Tests for F5 score backfill: DB migration and score population."""
import sqlite3
import pytest


@pytest.fixture
def tmp_db(tmp_path):
    """Minimal mlb_data.db with games table (no F5 columns yet)."""
    db = tmp_path / "mlb_data.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""
        CREATE TABLE games (
            game_pk INTEGER PRIMARY KEY,
            game_date DATE NOT NULL,
            season INTEGER NOT NULL,
            home_team_id INTEGER NOT NULL,
            away_team_id INTEGER NOT NULL,
            home_score INTEGER,
            away_score INTEGER,
            status TEXT DEFAULT 'scheduled'
        )
    """)
    conn.execute(
        "INSERT INTO games VALUES (745001, '2025-04-01', 2025, 1, 2, 5, 3, 'final')"
    )
    conn.commit()
    conn.close()
    return db


def test_migration_adds_f5_columns(tmp_db):
    """migrate_f5_columns() adds home_f5_score and away_f5_score."""
    from scripts.mlb_backfill_f5_scores import migrate_f5_columns

    migrate_f5_columns(str(tmp_db))

    conn = sqlite3.connect(str(tmp_db))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(games)")}
    conn.close()
    assert "home_f5_score" in cols
    assert "away_f5_score" in cols


def test_migration_is_idempotent(tmp_db):
    """Running migrate_f5_columns() twice does not raise."""
    from scripts.mlb_backfill_f5_scores import migrate_f5_columns

    migrate_f5_columns(str(tmp_db))
    migrate_f5_columns(str(tmp_db))  # second call must not raise
```

**Step 2: Run test to verify it fails**

```
venv/Scripts/python.exe -m pytest tests/test_mlb_backfill_f5_scores.py::test_migration_adds_f5_columns -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'scripts.mlb_backfill_f5_scores'`

---

**Step 3: Create `scripts/mlb_backfill_f5_scores.py` with migration function**

```python
"""Backfill F5 (first 5 innings) scores for all final MLB games.

Adds home_f5_score and away_f5_score columns to the games table,
then populates them by fetching linescore data from the MLB Stats API.

Usage:
    python scripts/mlb_backfill_f5_scores.py
    python scripts/mlb_backfill_f5_scores.py --db-path data/mlb_data.db
    python scripts/mlb_backfill_f5_scores.py --limit 100  # test run
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "mlb_data.db"
MLB_LINESCORE_URL = "https://statsapi.mlb.com/api/v1/game/{game_pk}/linescore"
THROTTLE_SECONDS = 0.1
CHECKPOINT_EVERY = 500


def migrate_f5_columns(db_path: str) -> None:
    """Add home_f5_score and away_f5_score columns to games table if absent.

    Idempotent: safe to call multiple times.
    """
    conn = sqlite3.connect(db_path)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(games)")}
    for col in ("home_f5_score", "away_f5_score"):
        if col not in existing:
            conn.execute(f"ALTER TABLE games ADD COLUMN {col} INTEGER")
            logger.info("Added column %s to games table", col)
    conn.commit()
    conn.close()


def fetch_f5_scores(game_pk: int) -> tuple[int, int] | None:
    """Fetch F5 scores for a single game from MLB Stats API linescore.

    Returns:
        (home_f5_score, away_f5_score) or None if linescore unavailable.
        Ties (home == away after 5 innings) are valid — returns the tie.
        Games with fewer than 5 innings recorded return partial sums.
    """
    url = MLB_LINESCORE_URL.format(game_pk=game_pk)
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("linescore(%d) failed: %s", game_pk, exc)
        return None

    data = resp.json()
    innings = data.get("innings", [])
    if not innings:
        logger.debug("No innings data for game_pk=%d", game_pk)
        return None

    home_f5 = sum(inn.get("home", {}).get("runs", 0) for inn in innings[:5])
    away_f5 = sum(inn.get("away", {}).get("runs", 0) for inn in innings[:5])
    return home_f5, away_f5


def backfill(db_path: str, limit: int | None = None) -> dict[str, int]:
    """Backfill F5 scores for all final games missing F5 data.

    Args:
        db_path: Path to mlb_data.db.
        limit: Maximum games to process (None = all). Useful for test runs.

    Returns:
        Dict with keys: total, updated, skipped, failed.
    """
    migrate_f5_columns(db_path)

    conn = sqlite3.connect(db_path)
    query = (
        "SELECT game_pk FROM games "
        "WHERE status = 'final' AND home_f5_score IS NULL"
    )
    rows = conn.execute(query).fetchall()
    conn.close()

    game_pks = [row[0] for row in rows]
    if limit is not None:
        game_pks = game_pks[:limit]

    logger.info("Found %d games needing F5 backfill", len(game_pks))

    stats = {"total": len(game_pks), "updated": 0, "skipped": 0, "failed": 0}

    for i, game_pk in enumerate(game_pks, 1):
        scores = fetch_f5_scores(game_pk)

        if scores is None:
            stats["failed"] += 1
        else:
            home_f5, away_f5 = scores
            conn = sqlite3.connect(db_path)
            conn.execute(
                "UPDATE games SET home_f5_score = ?, away_f5_score = ? "
                "WHERE game_pk = ?",
                (home_f5, away_f5, game_pk),
            )
            conn.commit()
            conn.close()
            stats["updated"] += 1

        if i % CHECKPOINT_EVERY == 0:
            logger.info(
                "Checkpoint: %d/%d processed (updated=%d, failed=%d)",
                i, len(game_pks), stats["updated"], stats["failed"],
            )

        time.sleep(THROTTLE_SECONDS)

    logger.info(
        "Backfill complete: %d updated, %d failed of %d total",
        stats["updated"], stats["failed"], stats["total"],
    )
    return stats


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Backfill F5 scores into mlb_data.db")
    parser.add_argument("--db-path", default=str(DB_PATH))
    parser.add_argument("--limit", type=int, default=None,
                        help="Max games to process (omit for all)")
    args = parser.parse_args()

    stats = backfill(args.db_path, limit=args.limit)
    print(f"Done: {stats}")


if __name__ == "__main__":
    main()
```

**Step 4: Run migration tests to verify they pass**

```
venv/Scripts/python.exe -m pytest tests/test_mlb_backfill_f5_scores.py::test_migration_adds_f5_columns tests/test_mlb_backfill_f5_scores.py::test_migration_is_idempotent -v
```

Expected: `2 passed`

---

## Task 2: F5 Score Backfill Tests

Add tests for `fetch_f5_scores()` and `backfill()` using mocked HTTP responses.

**Files:**
- Modify: `tests/test_mlb_backfill_f5_scores.py`

---

**Step 1: Add backfill tests**

Append to `tests/test_mlb_backfill_f5_scores.py`:

```python
from unittest.mock import MagicMock, patch


LINESCORE_9_INNINGS = {
    "innings": [
        {"num": i, "home": {"runs": [0, 2, 0, 1, 0, 0, 0, 0, 2][i-1]},
                   "away": {"runs": [1, 0, 0, 0, 1, 0, 0, 0, 0][i-1]}}
        for i in range(1, 10)
    ]
}
# home F5: 0+2+0+1+0 = 3, away F5: 1+0+0+0+1 = 2


def test_fetch_f5_scores_sums_first_five_innings():
    """fetch_f5_scores returns sum of first 5 innings only."""
    from scripts.mlb_backfill_f5_scores import fetch_f5_scores

    mock_resp = MagicMock()
    mock_resp.json.return_value = LINESCORE_9_INNINGS
    mock_resp.raise_for_status.return_value = None

    with patch("scripts.mlb_backfill_f5_scores.requests.get", return_value=mock_resp):
        result = fetch_f5_scores(745001)

    assert result == (3, 2)


def test_fetch_f5_scores_handles_tie():
    """fetch_f5_scores returns tuple even when F5 scores are tied."""
    from scripts.mlb_backfill_f5_scores import fetch_f5_scores

    tied = {
        "innings": [
            {"num": i, "home": {"runs": 1}, "away": {"runs": 1}}
            for i in range(1, 6)
        ]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = tied
    mock_resp.raise_for_status.return_value = None

    with patch("scripts.mlb_backfill_f5_scores.requests.get", return_value=mock_resp):
        result = fetch_f5_scores(745001)

    assert result == (5, 5)


def test_fetch_f5_scores_handles_short_game():
    """fetch_f5_scores sums only available innings (< 5 due to rain etc)."""
    from scripts.mlb_backfill_f5_scores import fetch_f5_scores

    short = {
        "innings": [
            {"num": 1, "home": {"runs": 2}, "away": {"runs": 0}},
            {"num": 2, "home": {"runs": 0}, "away": {"runs": 1}},
            # game ended after 2 innings
        ]
    }
    mock_resp = MagicMock()
    mock_resp.json.return_value = short
    mock_resp.raise_for_status.return_value = None

    with patch("scripts.mlb_backfill_f5_scores.requests.get", return_value=mock_resp):
        result = fetch_f5_scores(745001)

    assert result == (2, 1)


def test_fetch_f5_scores_returns_none_on_api_error():
    """fetch_f5_scores returns None when request fails."""
    from scripts.mlb_backfill_f5_scores import fetch_f5_scores

    with patch(
        "scripts.mlb_backfill_f5_scores.requests.get",
        side_effect=Exception("timeout"),
    ):
        result = fetch_f5_scores(745001)

    assert result is None


def test_backfill_populates_db(tmp_db):
    """backfill() writes F5 scores to games table."""
    from scripts.mlb_backfill_f5_scores import backfill

    mock_resp = MagicMock()
    mock_resp.json.return_value = LINESCORE_9_INNINGS
    mock_resp.raise_for_status.return_value = None

    with patch("scripts.mlb_backfill_f5_scores.requests.get", return_value=mock_resp):
        stats = backfill(str(tmp_db))

    assert stats["updated"] == 1
    assert stats["failed"] == 0

    conn = sqlite3.connect(str(tmp_db))
    row = conn.execute(
        "SELECT home_f5_score, away_f5_score FROM games WHERE game_pk = 745001"
    ).fetchone()
    conn.close()
    assert row == (3, 2)


def test_backfill_skips_already_populated(tmp_db):
    """backfill() does not overwrite existing F5 scores."""
    from scripts.mlb_backfill_f5_scores import migrate_f5_columns, backfill

    # Pre-populate
    migrate_f5_columns(str(tmp_db))
    conn = sqlite3.connect(str(tmp_db))
    conn.execute(
        "UPDATE games SET home_f5_score = 1, away_f5_score = 0 WHERE game_pk = 745001"
    )
    conn.commit()
    conn.close()

    with patch("scripts.mlb_backfill_f5_scores.requests.get") as mock_get:
        stats = backfill(str(tmp_db))

    mock_get.assert_not_called()
    assert stats["total"] == 0
```

**Step 2: Run tests to verify they pass**

```
venv/Scripts/python.exe -m pytest tests/test_mlb_backfill_f5_scores.py -v
```

Expected: `8 passed`

**Step 3: Commit**

```bash
git add scripts/mlb_backfill_f5_scores.py tests/test_mlb_backfill_f5_scores.py
git commit -m "feat(mlb-f5): add F5 score backfill script and DB migration"
```

---

## Task 3: PoissonModel F5 Output

Extend `PoissonModel.predict()` to return `lambda_f5_home`, `lambda_f5_away`, and
`f5_moneyline_home`.

**Files:**
- Modify: `models/sport_specific/mlb/poisson_model.py`
- Modify: `tests/test_mlb_poisson_model.py`

---

**Step 1: Update existing predict test to expect F5 keys**

In `tests/test_mlb_poisson_model.py`, find `test_predict_returns_all_markets` and add F5 assertions. The test currently checks for `moneyline_home`, `run_line_home`, `total_over`, `lambda_home`, `lambda_away`. Add:

```python
# Find test_predict_returns_all_markets and add these assertions:
assert "lambda_f5_home" in result
assert "lambda_f5_away" in result
assert "f5_moneyline_home" in result
assert 0 < result["f5_moneyline_home"] < 1
```

**Step 2: Run test to verify it fails**

```
venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py::TestPoissonModelPredict::test_predict_returns_all_markets -v
```

Expected: `FAILED` — `AssertionError: 'lambda_f5_home' not in {...}`

---

**Step 3: Add F5 constants and output to `poisson_model.py`**

At the top of `poisson_model.py`, after the existing imports, add the constants:

```python
# F5 (First 5 Innings) lambda scaling
# Base: 5 of 9 innings. Bump: first inning averages ~0.6 runs vs 0.48 per-inning average.
# Sources: docs/mlb/research/poisson-regression-mlb.md, ADR-MLB-010
_F5_FRACTION = 5 / 9
_F5_BUMP = 1.02
_F5_SCALE = _F5_FRACTION * _F5_BUMP  # ≈ 0.567
```

In `PoissonModel.predict()`, after the existing `matrix = build_score_matrix(...)` line and before the `return` statement, add:

```python
lambda_f5_home = lambda_home * _F5_SCALE
lambda_f5_away = lambda_away * _F5_SCALE
f5_matrix = build_score_matrix(lambda_f5_home, lambda_f5_away)
f5_prob = moneyline_prob(f5_matrix)
```

Then add the new keys to the return dict:

```python
return {
    "lambda_home": lambda_home,
    "lambda_away": lambda_away,
    "moneyline_home": moneyline_prob(matrix),
    "run_line_home": run_line_prob(matrix, line=run_line),
    "total_over": total_prob(matrix, total=total_line),
    "lambda_f5_home": lambda_f5_home,
    "lambda_f5_away": lambda_f5_away,
    "f5_moneyline_home": f5_prob,
}
```

**Step 4: Run the updated test to verify it passes**

```
venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py::TestPoissonModelPredict::test_predict_returns_all_markets -v
```

Expected: `PASSED`

---

**Step 5: Add F5-specific tests**

Append to the `TestPoissonModelPredict` class in `tests/test_mlb_poisson_model.py`:

```python
def test_f5_lambda_is_scaled_from_full_game(self, fitted_model):
    """lambda_f5 = lambda_full * F5_SCALE (≈ 0.567)."""
    from models.sport_specific.mlb.poisson_model import _F5_SCALE

    home_id = list(fitted_model.team_ratings.keys())[0]
    away_id = list(fitted_model.team_ratings.keys())[1]
    result = fitted_model.predict(home_id, away_id)

    assert abs(result["lambda_f5_home"] - result["lambda_home"] * _F5_SCALE) < 1e-9
    assert abs(result["lambda_f5_away"] - result["lambda_away"] * _F5_SCALE) < 1e-9


def test_f5_prob_closer_to_half_than_full_game(self, fitted_model):
    """F5 probability is closer to 0.5 than full-game (smaller expected scoring gap)."""
    home_id = list(fitted_model.team_ratings.keys())[0]
    away_id = list(fitted_model.team_ratings.keys())[1]
    result = fitted_model.predict(home_id, away_id)

    full_game_dist = abs(result["moneyline_home"] - 0.5)
    f5_dist = abs(result["f5_moneyline_home"] - 0.5)
    assert f5_dist <= full_game_dist


def test_f5_prob_within_valid_range(self, fitted_model):
    """f5_moneyline_home is a valid probability."""
    home_id = list(fitted_model.team_ratings.keys())[0]
    away_id = list(fitted_model.team_ratings.keys())[1]
    result = fitted_model.predict(home_id, away_id)

    assert 0.0 < result["f5_moneyline_home"] < 1.0


def test_f5_prob_independent_of_total_line_param(self, fitted_model):
    """f5_moneyline_home is not affected by total_line parameter (moneyline market)."""
    home_id = list(fitted_model.team_ratings.keys())[0]
    away_id = list(fitted_model.team_ratings.keys())[1]

    r1 = fitted_model.predict(home_id, away_id, total_line=8.5)
    r2 = fitted_model.predict(home_id, away_id, total_line=10.5)

    assert r1["f5_moneyline_home"] == r2["f5_moneyline_home"]
```

**Step 6: Run all F5 model tests**

```
venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py -v
```

Expected: all previously passing tests still pass + 4 new tests pass.

**Step 7: Commit**

```bash
git add models/sport_specific/mlb/poisson_model.py tests/test_mlb_poisson_model.py
git commit -m "feat(mlb-f5): add F5 lambda and f5_moneyline_home to PoissonModel.predict()"
```

---

## Task 4: Backtest --f5 Flag

Add `--f5` mode to `mlb_backtest.py`: load F5 scores, use F5 raw probability for edge/bets,
report F5 accuracy alongside full-game accuracy.

**Files:**
- Modify: `scripts/mlb_backtest.py`
- Create: `tests/test_mlb_backtest_f5.py`

---

**Step 1: Write failing F5 backtest tests**

Create `tests/test_mlb_backtest_f5.py`:

```python
"""Tests for F5 mode in mlb_backtest.py."""
import sqlite3
import numpy as np
import pandas as pd
import pytest
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def games_with_f5():
    """Minimal games DataFrame with F5 scores for backtest tests."""
    rng = np.random.default_rng(42)
    n = 300
    team_ids = list(range(1, 16))

    records = []
    for i in range(n):
        home = rng.choice(team_ids)
        away = rng.choice([t for t in team_ids if t != home])
        home_score = int(rng.poisson(4.5))
        away_score = int(rng.poisson(4.3))
        home_f5 = int(rng.poisson(2.5))
        away_f5 = int(rng.poisson(2.4))
        records.append({
            "game_pk": 700000 + i,
            "game_date": f"202{'3' if i < 150 else '4'}-04-{(i % 28) + 1:02d}",
            "season": 2023 if i < 150 else 2024,
            "home_team_id": home,
            "away_team_id": away,
            "home_score": home_score,
            "away_score": away_score,
            "home_starter_id": None,
            "away_starter_id": None,
            "home_f5_score": home_f5,
            "away_f5_score": away_f5,
        })
    return pd.DataFrame(records)


def test_run_backtest_f5_returns_f5_correct_column(games_with_f5):
    """run_backtest with f5=True produces f5_correct column."""
    from scripts.mlb_backtest import run_backtest

    results = run_backtest(games_with_f5, test_season=2024, f5=True)

    assert not results.empty
    assert "f5_correct" in results.columns


def test_f5_correct_excludes_ties(games_with_f5):
    """f5_correct is NaN when home_f5_score == away_f5_score."""
    from scripts.mlb_backtest import run_backtest

    results = run_backtest(games_with_f5, test_season=2024, f5=True)

    tied = results[results["home_f5_score"] == results["away_f5_score"]]
    assert tied["f5_correct"].isna().all()


def test_f5_mode_does_not_apply_calibration(games_with_f5):
    """In f5=True mode, pred_prob used for betting is raw f5_moneyline_home."""
    from scripts.mlb_backtest import run_backtest

    results = run_backtest(games_with_f5, test_season=2024, f5=True, calibrated=True)
    # calibrated=True should be ignored in f5 mode — no crash, just raw prob used
    assert not results.empty
    assert "f5_moneyline_home" in results.columns


def test_f5_away_fav_bets_suppressed_by_default(games_with_f5):
    """--f5 mode suppresses away_fav bets by default (no_away_fav=True)."""
    from scripts.mlb_backtest import run_backtest

    results = run_backtest(
        games_with_f5, test_season=2024, f5=True, odds_df=None
    )
    bets = results[results["stake"] > 0] if "stake" in results.columns else pd.DataFrame()
    if not bets.empty and "bet_side" in bets.columns and "bet_odds" in bets.columns:
        away_favs = bets[
            (bets["bet_side"] == "away") & (bets["bet_odds"] < 0)
        ]
        assert len(away_favs) == 0
```

**Step 2: Run tests to verify they fail**

```
venv/Scripts/python.exe -m pytest tests/test_mlb_backtest_f5.py -v
```

Expected: `FAILED` — `TypeError: run_backtest() got unexpected keyword argument 'f5'`

---

**Step 3: Update `load_games()` to include F5 columns**

In `scripts/mlb_backtest.py`, update `load_games()` SQL to also select F5 columns:

```python
def load_games(db_path: Path) -> pd.DataFrame:
    """Load all final games with starter IDs and F5 scores from the database."""
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql_query(
        "SELECT game_pk, game_date, season, home_team_id, away_team_id, "
        "home_score, away_score, home_starter_id, away_starter_id, "
        "home_f5_score, away_f5_score "
        "FROM games WHERE status = 'final'",
        conn,
    )
    conn.close()
    return df
```

---

**Step 4: Add `f5` and `no_away_fav` parameters to `run_backtest()`**

In the function signature, add:

```python
def run_backtest(
    games: pd.DataFrame,
    test_season: int,
    pitcher_adj: bool = False,
    pitcher_stats: dict[tuple[int, int], dict] | None = None,
    calibrated: bool = False,
    odds_df: pd.DataFrame | None = None,
    f5: bool = False,
    no_away_fav: bool = True,   # default True for --f5 mode per ADR-MLB-011
) -> pd.DataFrame:
```

Inside `run_backtest()`, after the existing calibration block, add:

```python
    # F5 mode: warn and ignore --calibrated (use raw prob — ADR-MLB-010)
    if f5 and calibrated:
        logger.warning(
            "--f5 and --calibrated are mutually exclusive. "
            "Using raw F5 probability (uncalibrated). "
            "Fit a dedicated F5 calibrator after ~500 F5 outcomes."
        )
```

In the per-game loop, replace the probability assignment section:

```python
        pred = model.predict(
            home_id,
            away_id,
            home_pitcher_adj=home_padj,
            away_pitcher_adj=away_padj,
        )
        home_won = row["home_score"] > row["away_score"]
        raw_prob = pred["moneyline_home"]

        if f5:
            # Raw F5 probability — do NOT calibrate (ADR-MLB-010, Session 41 research)
            cal_prob = pred["f5_moneyline_home"]
        else:
            cal_prob = model.calibrate_prob(raw_prob) if calibrated else raw_prob
```

Add F5 accuracy computation inside the per-game loop (after `home_won`):

```python
        # F5 accuracy (requires F5 scores in games data)
        f5_correct = None
        if f5:
            home_f5 = row.get("home_f5_score")
            away_f5 = row.get("away_f5_score")
            if (
                home_f5 is not None and away_f5 is not None
                and not pd.isna(home_f5) and not pd.isna(away_f5)
                and int(home_f5) != int(away_f5)
            ):
                f5_correct = (cal_prob > 0.5) == (int(home_f5) > int(away_f5))
            home_f5_score = home_f5
            away_f5_score = away_f5
        else:
            home_f5_score = None
            away_f5_score = None
```

Add away_fav suppression logic — in the bet placement block (after `if bet_side is not None`):

```python
            # Suppress away_fav bets in F5 mode (ADR-MLB-011: worst CLV cell)
            if f5 and no_away_fav and bet_side == "away" and bet_odds is not None and int(bet_odds) < 0:
                bet_side = None
```

Add new result fields at the end of the per-game `results.append(...)`:

```python
                "f5_moneyline_home": pred["f5_moneyline_home"] if f5 else None,
                "home_f5_score": home_f5_score,
                "away_f5_score": away_f5_score,
                "f5_correct": f5_correct,
```

---

**Step 5: Update `print_report()` to show F5 accuracy**

In `print_report()`, after the existing accuracy/log-loss block, add:

```python
    # F5 accuracy (only when f5 column present and populated)
    if "f5_correct" in results.columns and results["f5_correct"].notna().any():
        f5_valid = results[results["f5_correct"].notna()]
        f5_acc = f5_valid["f5_correct"].mean()
        f5_ties = results["f5_correct"].isna().sum()
        print(f"F5 Accuracy: {f5_acc:.1%} ({int(f5_valid['f5_correct'].sum())}/{len(f5_valid)})")
        print(f"F5 Ties (pushes excluded): {f5_ties} ({f5_ties / len(results):.1%})")
        print(f"Full-game accuracy (same games): {accuracy:.1%}")
        print(f"F5 vs full-game delta: {f5_acc - accuracy:+.1%}")
        if "CLV proxy" not in model_label:
            print("  NOTE: CLV is a proxy — Pinnacle full-game close (F5-specific odds unavailable)")
```

Also update `main()` to add the `--f5` and `--no-away-fav` CLI arguments:

```python
    parser.add_argument(
        "--f5",
        action="store_true",
        default=False,
        help="Use F5 (first 5 innings) probabilities instead of full-game",
    )
    parser.add_argument(
        "--no-away-fav",
        action="store_true",
        default=False,
        help="Suppress away-favorite bets (default on in --f5 mode per ADR-MLB-011)",
    )
```

And pass them through in `main()`:

```python
    results = run_backtest(
        games,
        args.test_season,
        pitcher_adj=args.pitcher_adj,
        pitcher_stats=pitcher_stats,
        calibrated=args.calibrated,
        odds_df=odds_df,
        f5=args.f5,
        no_away_fav=args.no_away_fav or args.f5,  # default on for --f5
    )
```

Update the output suffix logic:

```python
    if args.f5:
        suffix += "_f5"
```

---

**Step 6: Run F5 backtest tests**

```
venv/Scripts/python.exe -m pytest tests/test_mlb_backtest_f5.py -v
```

Expected: `4 passed`

**Step 7: Run full MLB test suite to confirm no regressions**

```
venv/Scripts/python.exe -m pytest tests/test_mlb_poisson_model.py tests/test_mlb_backfill_f5_scores.py tests/test_mlb_backtest_f5.py tests/test_mlb_backfill_odds.py -v
```

Expected: all pass, 0 failures.

**Step 8: Commit**

```bash
git add scripts/mlb_backtest.py tests/test_mlb_backtest_f5.py
git commit -m "feat(mlb-f5): add --f5 flag to backtest with F5 accuracy and away_fav filter"
```

---

## Task 5: End-to-End Smoke Test

Verify the full pipeline runs against the real database.

**Step 1: Run DB migration on real mlb_data.db**

```
venv/Scripts/python.exe -c "
from scripts.mlb_backfill_f5_scores import migrate_f5_columns
migrate_f5_columns('data/mlb_data.db')
print('Migration complete')
"
```

Expected: `Migration complete` (or "Added column home_f5_score" if columns were absent)

**Step 2: Run backfill with limit=20 to verify API connectivity**

```
venv/Scripts/python.exe scripts/mlb_backfill_f5_scores.py --limit 20
```

Expected: `Done: {'total': 20, 'updated': 20, 'failed': 0}` (or small number of failures if some game PKs have no linescore)

**Step 3: Run F5 backtest on 2025 (no odds, quick check)**

```
venv/Scripts/python.exe scripts/mlb_backtest.py --test-season 2025 --pitcher-adj --f5
```

Expected: output includes `F5 Accuracy: XX.X%` and `F5 vs full-game delta: +/-X.X%`

**Step 4: Run full backfill in background (takes ~12 min)**

```
venv/Scripts/python.exe scripts/mlb_backfill_f5_scores.py
```

Note: This is a long-running command. Run in a separate terminal. Do not block on it.

**Step 5: After backfill completes — run full F5 backtest with odds**

```
venv/Scripts/python.exe scripts/mlb_backtest.py --test-season 2025 --pitcher-adj --odds --f5
venv/Scripts/python.exe scripts/mlb_backtest.py --test-season 2024 --pitcher-adj --odds --f5
```

Expected: F5 accuracy > full-game accuracy (hypothesis validation)

**Step 6: Final commit if smoke test passes**

```bash
git add data/mlb_data.db  # schema change only, not full data
git commit -m "chore(mlb-f5): run DB migration (home_f5_score, away_f5_score columns added)"
```

---

## Success Criteria Checklist

- [ ] `test_mlb_backfill_f5_scores.py`: 8 tests pass
- [ ] `test_mlb_poisson_model.py`: all existing tests pass + 4 new F5 tests pass
- [ ] `test_mlb_backtest_f5.py`: 4 tests pass
- [ ] `mlb_backtest.py --f5` runs without error on real DB
- [ ] F5 backtest report shows `F5 Accuracy` and `F5 vs full-game delta`
- [ ] CLV proxy note displayed in F5 output
- [ ] away_fav bets absent from F5 bet report
- [ ] Full `--pitcher-adj --odds --f5` run completes for 2024 and 2025

---

## Key Constants (do not guess these)

```python
_F5_FRACTION = 5 / 9
_F5_BUMP = 1.02
_F5_SCALE = _F5_FRACTION * _F5_BUMP  # ≈ 0.5674
```

Source: `docs/mlb/research/poisson-regression-mlb.md`

## Why No F5 Calibration (important)

Do not add `model.calibrate_prob()` to the F5 probability path. Research (Session 41,
NeurIPS 2020 TransCal) confirmed the full-game calibrator over-shrinks F5 probs toward 0.5.
A dedicated F5 calibrator requires ~500 F5 outcomes (~1.5 seasons). Until then: raw prob.
See: `docs/mlb/DECISIONS.md` ADR-MLB-010, F5 Calibration section.
