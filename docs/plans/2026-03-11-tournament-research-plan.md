# Tournament Research Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Engineer and evaluate 12 features across two research items (Late-Season Losses, Efficiency Trajectory) for marginal CLV lift in the NCAAB betting pipeline.

**Architecture:** Two independent feature computation modules extend `NCABBFeatureEngine`. Each produces per-team-per-game feature parquets, then a consolidation script merges both, runs combined walk-forward backtesting against the baseline, and produces a final research report. All code follows the existing `safe_rolling` / `.shift(1)` leakage prevention pattern.

**Tech Stack:** Python 3.11+, pandas, numpy, scipy.stats (linregress), existing `features/engineering.py` primitives, existing `backtest_ncaab_elo.py` harness.

**Design docs:** `docs/plans/2026-03-11-late-season-losses-design.md`, `docs/plans/2026-03-11-efficiency-trajectory-design.md`

---

## Phase 0: Shared Infrastructure

### Task 0.1: Create research output directory and data loading utilities

**Files:**
- Create: `features/sport_specific/ncaab/research_utils.py`
- Create: `data/research/` (directory)
- Test: `tests/test_research_utils.py`

**Step 1: Create the output directory**

Run: `mkdir -p data/research`

**Step 2: Write failing tests for data loading and COVID filtering**

```python
"""Tests for research utility functions."""
import numpy as np
import pandas as pd
import pytest

from features.sport_specific.ncaab.research_utils import (
    load_season_games,
    load_barttorvik_snapshots,
    filter_covid_gaps,
    pit_opponent_barthag,
    VALID_SEASONS,
)


class TestLoadSeasonGames:
    def test_loads_parquet_and_adds_point_diff(self):
        df = load_season_games(2025)
        assert "point_diff" in df.columns
        assert (df["point_diff"] == df["points_for"] - df["points_against"]).all()

    def test_excludes_2020(self):
        assert 2020 not in VALID_SEASONS

    def test_sorts_by_date(self):
        df = load_season_games(2025)
        dates = pd.to_datetime(df["date"])
        assert dates.is_monotonic_increasing


class TestFilterCovidGaps:
    def test_flags_large_gaps_in_2021(self):
        dates = pd.to_datetime([
            "2021-01-01", "2021-01-03", "2021-01-20",  # 17-day gap
            "2021-01-22",
        ])
        df = pd.DataFrame({
            "date": dates,
            "team_id": ["A"] * 4,
            "result": ["W", "L", "W", "L"],
        })
        result = filter_covid_gaps(df, max_gap_days=10)
        # Game after the gap should be excluded from windows
        assert result["covid_gap"].iloc[2] is True or result["covid_gap"].iloc[2] == True

    def test_no_gaps_returns_all_false(self):
        dates = pd.to_datetime(["2022-01-01", "2022-01-03", "2022-01-06"])
        df = pd.DataFrame({
            "date": dates,
            "team_id": ["A"] * 3,
            "result": ["W", "L", "W"],
        })
        result = filter_covid_gaps(df, max_gap_days=10)
        assert not result["covid_gap"].any()


class TestPitOpponentBarthag:
    def test_returns_barthag_before_game_date(self):
        bart_df = pd.DataFrame({
            "team": ["OPP", "OPP", "OPP"],
            "date": pd.to_datetime(["2025-01-01", "2025-01-05", "2025-01-10"]),
            "barthag": [0.8, 0.85, 0.9],
        })
        # Game on Jan 7 should use Jan 5 snapshot (0.85), not Jan 10 (0.9)
        result = pit_opponent_barthag(bart_df, "OPP", pd.Timestamp("2025-01-07"))
        assert result == pytest.approx(0.85)

    def test_returns_nan_if_no_data(self):
        bart_df = pd.DataFrame({
            "team": ["OTHER"],
            "date": pd.to_datetime(["2025-01-01"]),
            "barthag": [0.5],
        })
        result = pit_opponent_barthag(bart_df, "OPP", pd.Timestamp("2025-01-07"))
        assert np.isnan(result)

    def test_strict_less_than(self):
        """Same-day snapshot must NOT be used (could include today's games)."""
        bart_df = pd.DataFrame({
            "team": ["OPP", "OPP"],
            "date": pd.to_datetime(["2025-01-05", "2025-01-10"]),
            "barthag": [0.85, 0.9],
        })
        # Game ON Jan 10 should use Jan 5 snapshot (0.85), not Jan 10 (0.9)
        result = pit_opponent_barthag(bart_df, "OPP", pd.Timestamp("2025-01-10"))
        assert result == pytest.approx(0.85)
```

**Step 3: Run tests to verify they fail**

Run: `venv/Scripts/python.exe -m pytest tests/test_research_utils.py -v -p no:examples`
Expected: ImportError / ModuleNotFoundError

**Step 4: Implement research_utils.py**

```python
"""Research utilities for tournament feature engineering.

Shared data loading, COVID gap filtering, and point-in-time Barttorvik
lookups used by both Late-Season Losses and Efficiency Trajectory research.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "ncaab"
BART_DIR = PROJECT_ROOT / "data" / "external" / "barttorvik"

# 2020 excluded (cancelled tournament). 2021 included with COVID flag.
VALID_SEASONS: tuple[int, ...] = (2021, 2022, 2023, 2024, 2025)


def load_season_games(season: int) -> pd.DataFrame:
    """Load game data for a season, sorted by date with point_diff added."""
    path = RAW_DIR / f"ncaab_games_{season}.parquet"
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    df["point_diff"] = df["points_for"] - df["points_against"]
    return df


def load_barttorvik_snapshots(season: int) -> pd.DataFrame:
    """Load Barttorvik point-in-time snapshots for a season."""
    path = BART_DIR / f"barttorvik_ratings_{season}.parquet"
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["team", "date"]).reset_index(drop=True)


def filter_covid_gaps(
    team_games: pd.DataFrame,
    max_gap_days: int = 10,
) -> pd.DataFrame:
    """Add covid_gap column flagging games after large schedule gaps.

    A game is flagged if the gap from the previous game for the same team
    exceeds max_gap_days. Flagged games are excluded from rolling windows.
    """
    result = team_games.copy()
    result["covid_gap"] = False
    dates = pd.to_datetime(result["date"])
    gap = dates.diff()
    result.loc[gap.dt.days > max_gap_days, "covid_gap"] = True
    return result


def pit_opponent_barthag(
    bart_df: pd.DataFrame,
    opponent: str,
    game_date: pd.Timestamp,
) -> float:
    """Get opponent's barthag from most recent snapshot strictly before game_date.

    Returns np.nan if no data available.
    """
    mask = (bart_df["team"] == opponent) & (bart_df["date"] < game_date)
    filtered = bart_df.loc[mask]
    if filtered.empty:
        return np.nan
    return float(filtered.sort_values("date").iloc[-1]["barthag"])
```

**Step 5: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_research_utils.py -v -p no:examples`
Expected: All PASS

**Step 6: Commit**

```bash
git add data/research/.gitkeep features/sport_specific/ncaab/research_utils.py tests/test_research_utils.py
git commit -m "feat: add research utilities for tournament feature engineering"
```

---

### Task 0.2: Verify baseline backtest results are usable

**Files:**
- Read: `data/backtests/ncaab_elo_backtest_{2021..2025}.parquet`

**Step 1: Run verification script**

```bash
venv/Scripts/python.exe -c "
import pandas as pd
for s in [2021, 2022, 2023, 2024, 2025]:
    try:
        df = pd.read_parquet(f'data/backtests/ncaab_elo_backtest_{s}.parquet')
        n = len(df)
        clv = df['clv'].mean()
        roi = df['profit_loss'].sum() / df['stake'].sum()
        print(f'{s}: {n} bets, CLV={clv:.4f}, ROI={roi:.2%}')
    except Exception as e:
        print(f'{s}: MISSING or ERROR - {e}')
"
```

Expected: All 5 seasons present with ≥200 bets each.

**Step 2: Document baseline numbers for comparison**

Record the output — these are the baseline numbers the research features must beat.

---

## Phase 1: Late-Season Losses Features (Agent 1)

### Task 1.1: Implement late_loss_count features

**Files:**
- Create: `features/sport_specific/ncaab/late_season_losses.py`
- Test: `tests/test_late_season_losses.py`

**Step 1: Write failing tests**

```python
"""Tests for late-season loss features."""
import numpy as np
import pandas as pd
import pytest

from features.sport_specific.ncaab.late_season_losses import (
    compute_loss_count,
    compute_loss_margin_mean,
    compute_weighted_quality_loss,
    compute_bad_loss_weighted,
    compute_home_loss_rate,
    compute_all_loss_features,
)


@pytest.fixture
def team_games_with_losses() -> pd.DataFrame:
    """Team with a mix of wins and losses, 20 games."""
    np.random.seed(42)
    n = 20
    dates = pd.date_range("2025-01-01", periods=n, freq="3D")
    results = ["W", "L", "W", "W", "L", "L", "W", "W", "L", "W",
               "L", "W", "L", "W", "W", "L", "W", "L", "W", "W"]
    pts_for = np.where(np.array(results) == "W",
                       np.random.randint(70, 90, n),
                       np.random.randint(55, 70, n))
    pts_against = np.where(np.array(results) == "L",
                           np.random.randint(70, 90, n),
                           np.random.randint(55, 70, n))
    locations = (["Home", "Away"] * 10)[:n]
    return pd.DataFrame({
        "date": dates,
        "team_id": "TEAM_A",
        "result": results,
        "points_for": pts_for,
        "points_against": pts_against,
        "point_diff": pts_for - pts_against,
        "location": locations,
        "opponent_id": [f"OPP_{i}" for i in range(n)],
    })


class TestLossCount:
    def test_shift_prevents_leakage(self, team_games_with_losses):
        """Value at row i must not include game i."""
        result = compute_loss_count(team_games_with_losses, window=5)
        # Row 0-4 should be NaN (insufficient window + shift)
        assert result["late_loss_count_5g"].iloc[:5].isna().all()
        # Row 5 should count losses in rows 0-4 only
        expected = (team_games_with_losses["result"].iloc[0:5] == "L").sum()
        assert result["late_loss_count_5g"].iloc[5] == expected

    def test_10g_window(self, team_games_with_losses):
        result = compute_loss_count(team_games_with_losses, window=10)
        assert result["late_loss_count_10g"].iloc[:10].isna().all()
        expected = (team_games_with_losses["result"].iloc[0:10] == "L").sum()
        assert result["late_loss_count_10g"].iloc[10] == expected

    def test_all_wins_returns_zero(self):
        df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=10, freq="2D"),
            "team_id": "TEAM",
            "result": ["W"] * 10,
            "point_diff": [10] * 10,
        })
        result = compute_loss_count(df, window=5)
        valid = result["late_loss_count_5g"].dropna()
        assert (valid == 0).all()


class TestLossMarginMean:
    def test_no_losses_returns_zero(self):
        df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=10, freq="2D"),
            "team_id": "TEAM",
            "result": ["W"] * 10,
            "points_for": [80] * 10,
            "points_against": [65] * 10,
            "point_diff": [15] * 10,
        })
        result = compute_loss_margin_mean(df, window=5)
        valid = result["loss_margin_mean_10g"].dropna()
        assert (valid == 0.0).all()

    def test_computes_mean_of_losses_only(self, team_games_with_losses):
        result = compute_loss_margin_mean(team_games_with_losses, window=10)
        # Should be non-negative (margin of defeat = pts_against - pts_for)
        valid = result["loss_margin_mean_10g"].dropna()
        assert (valid >= 0).all()


class TestComputeAllLossFeatures:
    def test_output_shape(self, team_games_with_losses):
        result = compute_all_loss_features(team_games_with_losses)
        assert len(result) == len(team_games_with_losses)
        expected_cols = {
            "late_loss_count_5g", "late_loss_count_10g",
            "loss_margin_mean_10g", "home_loss_rate_10g",
        }
        assert expected_cols.issubset(set(result.columns))

    def test_no_leakage_assertion(self, team_games_with_losses):
        """All feature values at row i use only data from rows < i."""
        result = compute_all_loss_features(team_games_with_losses)
        # First 10 rows must be NaN for 10g features
        for col in ["late_loss_count_10g", "loss_margin_mean_10g"]:
            assert result[col].iloc[:10].isna().all()
```

**Step 2: Run tests to verify failure**

Run: `venv/Scripts/python.exe -m pytest tests/test_late_season_losses.py -v -p no:examples`
Expected: ImportError

**Step 3: Implement late_season_losses.py**

```python
"""Late-Season Loss features for NCAAB tournament research.

All features use game-count-based windows (pre-registered: 5g and 10g).
Rolling computations apply .shift(1) to prevent look-ahead bias.

Features:
- late_loss_count_{5,10}g: Loss count in window
- loss_margin_mean_10g: Mean margin of defeat (losses only)
- weighted_quality_loss_10g: Losses weighted by opponent PIT barthag
- bad_loss_weighted_10g: Losses weighted by (1 - opponent PIT barthag)
- home_loss_rate_10g: Home losses / home games in window
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_loss_count(
    team_games: pd.DataFrame,
    window: int = 5,
) -> pd.DataFrame:
    """Count losses in a rolling window, lagged by 1 game.

    Args:
        team_games: Single-team game log sorted by date.
            Must have 'result' column with 'W'/'L' values.
        window: Number of games in lookback window.

    Returns:
        DataFrame with late_loss_count_{window}g column.
    """
    is_loss = (team_games["result"] == "L").astype(int)
    rolling_count = is_loss.rolling(window=window, min_periods=window).sum()
    col_name = f"late_loss_count_{window}g"
    return pd.DataFrame({col_name: rolling_count.shift(1)}, index=team_games.index)


def compute_loss_margin_mean(
    team_games: pd.DataFrame,
    window: int = 10,
) -> pd.DataFrame:
    """Mean margin of defeat for losses in the window.

    Margin = points_against - points_for (positive = lost by N).
    Returns 0.0 if no losses in window.
    """
    is_loss = team_games["result"] == "L"
    margin = (team_games["points_against"] - team_games["points_for"]).clip(lower=0)
    # Only count margins from losses
    loss_margin = margin.where(is_loss, 0.0)
    loss_count = is_loss.astype(int).rolling(window=window, min_periods=window).sum()
    loss_margin_sum = loss_margin.rolling(window=window, min_periods=window).sum()

    # Mean margin of losses (0 if no losses)
    mean = np.where(loss_count > 0, loss_margin_sum / loss_count, 0.0)
    result = pd.Series(mean, index=team_games.index)

    return pd.DataFrame(
        {"loss_margin_mean_10g": result.shift(1)},
        index=team_games.index,
    )


def compute_weighted_quality_loss(
    team_games: pd.DataFrame,
    opp_barthag: pd.Series,
    window: int = 10,
) -> pd.DataFrame:
    """Losses weighted by opponent's PIT barthag / total games in window.

    Higher value = losses came against stronger opponents.
    opp_barthag must be pre-computed via PIT join (one value per game).
    """
    is_loss = team_games["result"] == "L"
    weighted = opp_barthag.where(is_loss, 0.0)
    rolling_sum = weighted.rolling(window=window, min_periods=window).sum()
    result = rolling_sum / window  # Normalize by total games, not just losses

    return pd.DataFrame(
        {"weighted_quality_loss_10g": result.shift(1)},
        index=team_games.index,
    )


def compute_bad_loss_weighted(
    team_games: pd.DataFrame,
    opp_barthag: pd.Series,
    window: int = 10,
) -> pd.DataFrame:
    """Losses weighted by (1 - opponent PIT barthag) / total games.

    Higher value = losses came against weaker opponents (bad losses).
    """
    is_loss = team_games["result"] == "L"
    weighted = (1.0 - opp_barthag).where(is_loss, 0.0)
    rolling_sum = weighted.rolling(window=window, min_periods=window).sum()
    result = rolling_sum / window

    return pd.DataFrame(
        {"bad_loss_weighted_10g": result.shift(1)},
        index=team_games.index,
    )


def compute_home_loss_rate(
    team_games: pd.DataFrame,
    window: int = 10,
) -> pd.DataFrame:
    """Home losses / home games in rolling window.

    Neutral site games excluded. NaN if no home games in window.
    """
    is_home = team_games["location"] == "Home"
    is_home_loss = is_home & (team_games["result"] == "L")

    home_count = is_home.astype(int).rolling(window=window, min_periods=window).sum()
    home_loss_count = is_home_loss.astype(int).rolling(window=window, min_periods=window).sum()

    rate = np.where(home_count > 0, home_loss_count / home_count, np.nan)
    result = pd.Series(rate, index=team_games.index)

    return pd.DataFrame(
        {"home_loss_rate_10g": result.shift(1)},
        index=team_games.index,
    )


def compute_all_loss_features(
    team_games: pd.DataFrame,
    opp_barthag: pd.Series | None = None,
) -> pd.DataFrame:
    """Compute all late-season loss features for a single team.

    Args:
        team_games: Single-team game log sorted by date.
            Required columns: result, points_for, points_against, location.
        opp_barthag: PIT opponent barthag per game (optional — needed for
            weighted_quality_loss and bad_loss_weighted).

    Returns:
        DataFrame with all loss feature columns.
    """
    result = pd.DataFrame(index=team_games.index)

    # Loss counts (5g and 10g)
    for w in (5, 10):
        lc = compute_loss_count(team_games, window=w)
        result = result.join(lc)

    # Loss margin mean (10g)
    lm = compute_loss_margin_mean(team_games, window=10)
    result = result.join(lm)

    # Home loss rate (10g)
    hlr = compute_home_loss_rate(team_games, window=10)
    result = result.join(hlr)

    # Quality/bad loss features (require PIT barthag)
    if opp_barthag is not None:
        ql = compute_weighted_quality_loss(team_games, opp_barthag, window=10)
        result = result.join(ql)
        bl = compute_bad_loss_weighted(team_games, opp_barthag, window=10)
        result = result.join(bl)

    return result
```

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_late_season_losses.py -v -p no:examples`
Expected: All PASS

**Step 5: Commit**

```bash
git add features/sport_specific/ncaab/late_season_losses.py tests/test_late_season_losses.py
git commit -m "feat: implement late-season loss features (6 features, TDD)"
```

---

### Task 1.2: Build Late-Season Losses research pipeline script

**Files:**
- Create: `scripts/research_late_season_losses.py`

This script is the **Agent 1 entry point**. It:
1. Loads games + Barttorvik for each valid season
2. Computes PIT opponent barthag per game
3. Computes all 6 loss features per team per season
4. Merges with baseline backtest results
5. Runs walk-forward evaluation (marginal CLV lift)
6. Generates report markdown

**Step 1: Write the pipeline script**

```python
"""Research Pipeline: Late-Season Loss Features.

Autonomous execution — no user input required.
Loads data, computes features, evaluates against baseline, writes report.

Usage:
    venv/Scripts/python.exe scripts/research_late_season_losses.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from scipy import stats

from features.sport_specific.ncaab.late_season_losses import compute_all_loss_features
from features.sport_specific.ncaab.research_utils import (
    VALID_SEASONS,
    filter_covid_gaps,
    load_barttorvik_snapshots,
    load_season_games,
    pit_opponent_barthag,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RESEARCH_DIR = PROJECT_ROOT / "data" / "research"
REPORT_DIR = PROJECT_ROOT / "docs" / "research"
BACKTEST_DIR = PROJECT_ROOT / "data" / "backtests"

LOSS_FEATURE_COLS = [
    "late_loss_count_5g", "late_loss_count_10g",
    "loss_margin_mean_10g", "weighted_quality_loss_10g",
    "bad_loss_weighted_10g", "home_loss_rate_10g",
]


def compute_season_features(season: int) -> pd.DataFrame:
    """Compute all loss features for a single season."""
    logger.info("Processing season %d", season)
    games = load_season_games(season)
    bart = load_barttorvik_snapshots(season)

    if season == 2021:
        games = filter_covid_gaps(games, max_gap_days=10)

    all_features = []
    for team_id, team_df in games.groupby("team_id"):
        team_df = team_df.sort_values("date").reset_index(drop=True)

        # PIT opponent barthag for each game
        opp_barthag = pd.Series(
            [pit_opponent_barthag(bart, row["opponent_id"], row["date"])
             for _, row in team_df.iterrows()],
            index=team_df.index,
        )

        # Exclude COVID-gap games from windows (set result to NaN)
        if "covid_gap" in team_df.columns:
            team_df = team_df[~team_df["covid_gap"]].reset_index(drop=True)
            opp_barthag = opp_barthag[~games.loc[team_df.index, "covid_gap"]].reset_index(drop=True)

        features = compute_all_loss_features(team_df, opp_barthag)
        features["team_id"] = team_id
        features["game_date"] = team_df["date"]
        features["game_id"] = team_df["game_id"]
        features["season"] = season
        all_features.append(features)

    result = pd.concat(all_features, ignore_index=True)
    logger.info("Season %d: %d rows, %d teams", season, len(result), result["team_id"].nunique())
    return result


def evaluate_against_baseline(
    features_df: pd.DataFrame,
    baseline_df: pd.DataFrame,
    season: int,
) -> dict:
    """Evaluate feature impact on CLV for a single season."""
    # Merge features with baseline backtest on game_id + team (bet_side)
    merged = baseline_df.merge(
        features_df,
        left_on=["game_id"],
        right_on=["game_id"],
        how="inner",
        suffixes=("", "_feat"),
    )

    if len(merged) < 50:
        logger.warning("Season %d: only %d merged rows, skipping", season, len(merged))
        return {"season": season, "n_bets": len(merged), "valid": False}

    results = {"season": season, "n_bets": len(merged), "valid": True}

    # Univariate correlations: each feature vs CLV
    for col in LOSS_FEATURE_COLS:
        if col in merged.columns:
            valid = merged[[col, "clv"]].dropna()
            if len(valid) >= 30:
                corr, pval = stats.pearsonr(valid[col], valid["clv"])
                results[f"{col}_corr"] = corr
                results[f"{col}_pval"] = pval

    results["baseline_clv"] = merged["clv"].mean()
    results["baseline_roi"] = merged["profit_loss"].sum() / merged["stake"].sum()

    return results


def generate_report(all_results: list[dict], all_features: pd.DataFrame) -> str:
    """Generate markdown research report."""
    lines = ["# Late-Season Losses — Research Report\n"]
    lines.append(f"Seasons analyzed: {VALID_SEASONS}\n")
    lines.append(f"Total feature rows: {len(all_features):,}\n")

    lines.append("\n## Feature Distributions\n")
    for col in LOSS_FEATURE_COLS:
        if col in all_features.columns:
            valid = all_features[col].dropna()
            lines.append(f"- **{col}**: mean={valid.mean():.4f}, std={valid.std():.4f}, "
                         f"min={valid.min():.4f}, max={valid.max():.4f}, "
                         f"n_valid={len(valid):,}\n")

    lines.append("\n## Correlation Matrix (Features)\n")
    available = [c for c in LOSS_FEATURE_COLS if c in all_features.columns]
    corr_matrix = all_features[available].corr()
    lines.append("```\n")
    lines.append(corr_matrix.to_string())
    lines.append("\n```\n")

    lines.append("\n## Univariate CLV Lift (per season)\n")
    lines.append("| Season | N Bets | Baseline CLV | " +
                 " | ".join(f"{c[:20]}" for c in LOSS_FEATURE_COLS) + " |\n")
    lines.append("|" + "--------|" * (3 + len(LOSS_FEATURE_COLS)) + "\n")
    for r in all_results:
        if not r.get("valid", False):
            continue
        row = f"| {r['season']} | {r['n_bets']} | {r.get('baseline_clv', 0):.4f} |"
        for col in LOSS_FEATURE_COLS:
            corr = r.get(f"{col}_corr", float("nan"))
            pval = r.get(f"{col}_pval", float("nan"))
            row += f" {corr:.3f} (p={pval:.3f}) |"
        lines.append(row + "\n")

    lines.append("\n## Recommendation\n")
    lines.append("_To be filled after consolidation step._\n")

    return "".join(lines)


def main():
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    all_features = []
    all_results = []

    for season in VALID_SEASONS:
        try:
            features = compute_season_features(season)
            features.to_parquet(
                RESEARCH_DIR / f"late_season_loss_features_{season}.parquet",
                index=False,
            )
            all_features.append(features)

            # Load baseline backtest
            bt_path = BACKTEST_DIR / f"ncaab_elo_backtest_{season}.parquet"
            if bt_path.exists():
                baseline = pd.read_parquet(bt_path)
                result = evaluate_against_baseline(features, baseline, season)
                all_results.append(result)
            else:
                logger.warning("No baseline backtest for season %d", season)

        except Exception as e:
            logger.error("Season %d failed: %s", season, e)
            continue

    if len(all_results) < 4:
        logger.error("ABORT: Only %d valid seasons (need ≥4)", len(all_results))
        sys.exit(1)

    combined = pd.concat(all_features, ignore_index=True)
    report = generate_report(all_results, combined)

    report_path = REPORT_DIR / "late_season_losses_report.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info("Report written to %s", report_path)


if __name__ == "__main__":
    main()
```

**Step 2: Run the pipeline**

Run: `venv/Scripts/python.exe scripts/research_late_season_losses.py`
Expected: Feature parquets in `data/research/`, report in `docs/research/`

**Step 3: Commit**

```bash
git add scripts/research_late_season_losses.py
git commit -m "feat: add late-season losses research pipeline"
```

---

## Phase 2: Efficiency Trajectory Features (Agent 2 — runs in parallel)

### Task 2.1: Implement trajectory slope features

**Files:**
- Create: `features/sport_specific/ncaab/efficiency_trajectory.py`
- Test: `tests/test_efficiency_trajectory.py`

**Step 1: Write failing tests**

```python
"""Tests for efficiency trajectory features."""
import numpy as np
import pandas as pd
import pytest

from features.sport_specific.ncaab.efficiency_trajectory import (
    compute_ols_slope,
    compute_barthag_delta,
    compute_rank_change,
    compute_all_trajectory_features,
)


@pytest.fixture
def barttorvik_snapshots() -> pd.DataFrame:
    """Simulated Barttorvik snapshots: 30 updates over ~60 days."""
    np.random.seed(42)
    n = 30
    dates = pd.date_range("2025-01-01", periods=n, freq="2D")
    # Trending upward offense, stable defense
    adj_o = 100 + np.linspace(0, 5, n) + np.random.normal(0, 0.3, n)
    adj_d = 98 + np.random.normal(0, 0.3, n)
    barthag = 0.7 + np.linspace(0, 0.1, n) + np.random.normal(0, 0.01, n)
    rank = np.linspace(100, 50, n).astype(int) + np.random.randint(-5, 5, n)

    return pd.DataFrame({
        "date": dates,
        "team": "TEAM_A",
        "adj_o": adj_o,
        "adj_d": adj_d,
        "barthag": barthag,
        "rank": rank,
    })


class TestOlsSlope:
    def test_positive_trend_positive_slope(self, barttorvik_snapshots):
        result = compute_ols_slope(barttorvik_snapshots, column="adj_o", n_snapshots=10)
        valid = result["adj_o_slope_10s"].dropna()
        # Offense is trending up, slope should be positive
        assert valid.mean() > 0

    def test_defense_sign_flip(self, barttorvik_snapshots):
        """adj_d slope should be flipped so positive = improving."""
        result = compute_ols_slope(barttorvik_snapshots, column="adj_d", n_snapshots=10)
        # adj_d is stable, so slope should be near 0 (not strongly positive or negative)
        valid = result["adj_d_slope_10s"].dropna()
        assert abs(valid.mean()) < 1.0

    def test_nan_for_insufficient_data(self, barttorvik_snapshots):
        result = compute_ols_slope(barttorvik_snapshots, column="adj_o", n_snapshots=10)
        # First 4 rows should be NaN (min 5 required)
        assert result["adj_o_slope_10s"].iloc[:4].isna().all()

    def test_min_points_enforced(self):
        """Slope requires minimum 5 data points."""
        df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=3, freq="2D"),
            "team": "T",
            "adj_o": [100, 101, 102],
        })
        result = compute_ols_slope(df, column="adj_o", n_snapshots=10)
        assert result["adj_o_slope_10s"].isna().all()


class TestBarthagDelta:
    def test_positive_trend(self, barttorvik_snapshots):
        result = compute_barthag_delta(barttorvik_snapshots, n_snapshots=10)
        valid = result["barthag_delta_10s"].dropna()
        # barthag is trending up
        assert valid.mean() > 0

    def test_nan_for_insufficient_data(self):
        df = pd.DataFrame({
            "date": pd.date_range("2025-01-01", periods=5, freq="2D"),
            "team": "T",
            "barthag": [0.5, 0.6, 0.7, 0.8, 0.9],
        })
        result = compute_barthag_delta(df, n_snapshots=10)
        assert result["barthag_delta_10s"].isna().all()


class TestRankChange:
    def test_improving_rank_positive_value(self, barttorvik_snapshots):
        result = compute_rank_change(barttorvik_snapshots, n_snapshots=20)
        valid = result["rank_change_20s"].dropna()
        # Rank decreasing (improving) should give positive values
        assert valid.mean() > 0


class TestComputeAllTrajectory:
    def test_output_columns(self, barttorvik_snapshots):
        result = compute_all_trajectory_features(barttorvik_snapshots)
        expected = {
            "adj_o_slope_10s", "adj_d_slope_10s",
            "net_efficiency_slope_10s",
            "barthag_delta_10s", "barthag_delta_20s",
            "rank_change_20s",
        }
        assert expected.issubset(set(result.columns))

    def test_output_length(self, barttorvik_snapshots):
        result = compute_all_trajectory_features(barttorvik_snapshots)
        assert len(result) == len(barttorvik_snapshots)
```

**Step 2: Run tests to verify failure**

Run: `venv/Scripts/python.exe -m pytest tests/test_efficiency_trajectory.py -v -p no:examples`
Expected: ImportError

**Step 3: Implement efficiency_trajectory.py**

```python
"""Efficiency Trajectory features for NCAAB tournament research.

Computes OLS slopes and deltas from Barttorvik point-in-time snapshots.
All features use snapshot-count-based windows (pre-registered: 10s, 20s).

Features:
- adj_o_slope_10s: OLS slope of adjusted offense (positive = improving)
- adj_d_slope_10s: OLS slope of adjusted defense (sign-flipped, positive = improving)
- net_efficiency_slope_10s: OLS slope of (adj_o - adj_d)
- barthag_delta_{10,20}s: Raw barthag change over N snapshots
- rank_change_20s: Rank improvement over 20 snapshots (positive = improving)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import linregress

MIN_SLOPE_POINTS = 5


def compute_ols_slope(
    snapshots: pd.DataFrame,
    column: str,
    n_snapshots: int = 10,
    flip_sign: bool | None = None,
) -> pd.DataFrame:
    """Compute OLS slope of a metric over last N snapshots.

    Args:
        snapshots: Single-team Barttorvik snapshots sorted by date.
        column: Column to compute slope for (adj_o, adj_d, etc.).
        n_snapshots: Window size in number of snapshots.
        flip_sign: If True, multiply slope by -1. If None, auto-flip for adj_d.

    Returns:
        DataFrame with {column}_slope_{n_snapshots}s column.
    """
    if flip_sign is None:
        flip_sign = column == "adj_d"

    col_name = f"{column}_slope_{n_snapshots}s"
    slopes = pd.Series(np.nan, index=snapshots.index)

    values = snapshots[column].values
    for i in range(len(snapshots)):
        start = max(0, i - n_snapshots + 1)
        window = values[start:i + 1]
        if len(window) < MIN_SLOPE_POINTS:
            continue
        x = np.arange(len(window))
        slope = linregress(x, window).slope
        if flip_sign:
            slope = -slope
        slopes.iloc[i] = slope

    return pd.DataFrame({col_name: slopes}, index=snapshots.index)


def compute_net_efficiency_slope(
    snapshots: pd.DataFrame,
    n_snapshots: int = 10,
) -> pd.DataFrame:
    """OLS slope of (adj_o - adj_d) over N snapshots."""
    net = snapshots["adj_o"] - snapshots["adj_d"]
    temp_df = snapshots.assign(_net_eff=net)
    # Reuse slope function on the derived column
    col_name = f"net_efficiency_slope_{n_snapshots}s"
    slopes = pd.Series(np.nan, index=snapshots.index)

    values = net.values
    for i in range(len(snapshots)):
        start = max(0, i - n_snapshots + 1)
        window = values[start:i + 1]
        if len(window) < MIN_SLOPE_POINTS:
            continue
        x = np.arange(len(window))
        slopes.iloc[i] = linregress(x, window).slope

    return pd.DataFrame({col_name: slopes}, index=snapshots.index)


def compute_barthag_delta(
    snapshots: pd.DataFrame,
    n_snapshots: int = 10,
) -> pd.DataFrame:
    """Raw barthag change: current - N snapshots ago."""
    col_name = f"barthag_delta_{n_snapshots}s"
    delta = snapshots["barthag"] - snapshots["barthag"].shift(n_snapshots)
    return pd.DataFrame({col_name: delta}, index=snapshots.index)


def compute_rank_change(
    snapshots: pd.DataFrame,
    n_snapshots: int = 20,
) -> pd.DataFrame:
    """Rank improvement: old_rank - current_rank (positive = improving)."""
    col_name = f"rank_change_{n_snapshots}s"
    change = snapshots["rank"].shift(n_snapshots) - snapshots["rank"]
    return pd.DataFrame({col_name: change}, index=snapshots.index)


def compute_all_trajectory_features(
    snapshots: pd.DataFrame,
) -> pd.DataFrame:
    """Compute all efficiency trajectory features for a single team.

    Args:
        snapshots: Single-team Barttorvik snapshots sorted by date.
            Required columns: adj_o, adj_d, barthag, rank.

    Returns:
        DataFrame with all trajectory feature columns.
    """
    result = pd.DataFrame(index=snapshots.index)

    # OLS slopes (10 snapshots)
    result = result.join(compute_ols_slope(snapshots, "adj_o", 10))
    result = result.join(compute_ols_slope(snapshots, "adj_d", 10))
    result = result.join(compute_net_efficiency_slope(snapshots, 10))

    # Barthag deltas (10 and 20 snapshots)
    result = result.join(compute_barthag_delta(snapshots, 10))
    result = result.join(compute_barthag_delta(snapshots, 20))

    # Rank change (20 snapshots)
    result = result.join(compute_rank_change(snapshots, 20))

    return result
```

**Step 4: Run tests to verify they pass**

Run: `venv/Scripts/python.exe -m pytest tests/test_efficiency_trajectory.py -v -p no:examples`
Expected: All PASS

**Step 5: Commit**

```bash
git add features/sport_specific/ncaab/efficiency_trajectory.py tests/test_efficiency_trajectory.py
git commit -m "feat: implement efficiency trajectory features (6 features, TDD)"
```

---

### Task 2.2: Build Efficiency Trajectory research pipeline script

**Files:**
- Create: `scripts/research_efficiency_trajectory.py`

This follows the same pattern as Task 1.2 but for Barttorvik trajectory features.

**Step 1: Write the pipeline script**

```python
"""Research Pipeline: Efficiency Trajectory Features.

Autonomous execution — no user input required.
Computes Barttorvik trajectory features, evaluates against baseline, writes report.

Usage:
    venv/Scripts/python.exe scripts/research_efficiency_trajectory.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from scipy import stats

from features.sport_specific.ncaab.efficiency_trajectory import (
    compute_all_trajectory_features,
)
from features.sport_specific.ncaab.research_utils import (
    VALID_SEASONS,
    load_barttorvik_snapshots,
    load_season_games,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RESEARCH_DIR = PROJECT_ROOT / "data" / "research"
REPORT_DIR = PROJECT_ROOT / "docs" / "research"
BACKTEST_DIR = PROJECT_ROOT / "data" / "backtests"

TRAJ_FEATURE_COLS = [
    "adj_o_slope_10s", "adj_d_slope_10s", "net_efficiency_slope_10s",
    "barthag_delta_10s", "barthag_delta_20s", "rank_change_20s",
]


def audit_snapshot_frequency(season: int, bart: pd.DataFrame) -> dict:
    """Audit Barttorvik snapshot frequency for data quality."""
    unique_dates = bart["date"].nunique()
    if unique_dates < 2:
        return {"season": season, "unique_dates": unique_dates, "valid": False}
    date_range = (bart["date"].max() - bart["date"].min()).days
    avg_gap = date_range / unique_dates
    max_gap = bart.groupby("team")["date"].diff().dt.days.max()
    return {
        "season": season,
        "unique_dates": unique_dates,
        "date_range_days": date_range,
        "avg_gap_days": avg_gap,
        "max_gap_days": max_gap,
        "valid": unique_dates >= 30,
    }


def compute_season_features(season: int) -> pd.DataFrame:
    """Compute trajectory features for one season."""
    logger.info("Processing season %d", season)
    games = load_season_games(season)
    bart = load_barttorvik_snapshots(season)

    # Determine season start date (first snapshot)
    season_start = bart["date"].min()

    all_features = []
    for team, team_bart in bart.groupby("team"):
        # Clamp to current season
        team_bart = team_bart[team_bart["date"] >= season_start].sort_values("date").reset_index(drop=True)
        if len(team_bart) < 5:
            continue

        features = compute_all_trajectory_features(team_bart)
        features["team"] = team
        features["snapshot_date"] = team_bart["date"]
        features["season"] = season
        all_features.append(features)

    result = pd.concat(all_features, ignore_index=True)

    # Align to game schedule: for each game, get most recent snapshot features
    # This is the PIT join — find the latest snapshot strictly before game_date
    game_features = []
    for _, game in games.drop_duplicates("game_id").iterrows():
        game_date = game["date"]
        team = game["team_id"]

        team_feats = result[(result["team"] == team) & (result["snapshot_date"] < game_date)]
        if team_feats.empty:
            continue

        latest = team_feats.iloc[-1]
        row = {col: latest.get(col, np.nan) for col in TRAJ_FEATURE_COLS}
        row["team_id"] = team
        row["game_date"] = game_date
        row["game_id"] = game["game_id"]
        row["season"] = season
        game_features.append(row)

    game_df = pd.DataFrame(game_features)
    logger.info("Season %d: %d game-level feature rows", season, len(game_df))
    return game_df


def evaluate_against_baseline(features_df, baseline_df, season) -> dict:
    """Evaluate trajectory features against baseline CLV."""
    merged = baseline_df.merge(features_df, on="game_id", how="inner", suffixes=("", "_feat"))

    if len(merged) < 50:
        return {"season": season, "n_bets": len(merged), "valid": False}

    results = {"season": season, "n_bets": len(merged), "valid": True}
    for col in TRAJ_FEATURE_COLS:
        if col in merged.columns:
            valid = merged[[col, "clv"]].dropna()
            if len(valid) >= 30:
                corr, pval = stats.pearsonr(valid[col], valid["clv"])
                results[f"{col}_corr"] = corr
                results[f"{col}_pval"] = pval

    results["baseline_clv"] = merged["clv"].mean()
    return results


def generate_report(all_results, audit_results, all_features) -> str:
    """Generate markdown report."""
    lines = ["# Efficiency Trajectory — Research Report\n"]
    lines.append(f"Seasons analyzed: {VALID_SEASONS}\n")

    lines.append("\n## Snapshot Frequency Audit\n")
    lines.append("| Season | Unique Dates | Date Range | Avg Gap | Max Gap | Valid |\n")
    lines.append("|--------|-------------|------------|---------|---------|-------|\n")
    for a in audit_results:
        lines.append(f"| {a['season']} | {a.get('unique_dates', 'N/A')} | "
                     f"{a.get('date_range_days', 'N/A')}d | "
                     f"{a.get('avg_gap_days', 0):.1f}d | "
                     f"{a.get('max_gap_days', 'N/A')}d | "
                     f"{'YES' if a.get('valid') else 'NO'} |\n")

    lines.append("\n## Feature Distributions\n")
    for col in TRAJ_FEATURE_COLS:
        if col in all_features.columns:
            valid = all_features[col].dropna()
            lines.append(f"- **{col}**: mean={valid.mean():.4f}, std={valid.std():.4f}, "
                         f"n_valid={len(valid):,}\n")

    lines.append("\n## Correlation Matrix\n```\n")
    available = [c for c in TRAJ_FEATURE_COLS if c in all_features.columns]
    lines.append(all_features[available].corr().to_string())
    lines.append("\n```\n")

    lines.append("\n## Univariate CLV Correlations\n")
    lines.append("| Season | N Bets | Baseline CLV | " +
                 " | ".join(c[:20] for c in TRAJ_FEATURE_COLS) + " |\n")
    lines.append("|" + "--------|" * (3 + len(TRAJ_FEATURE_COLS)) + "\n")
    for r in all_results:
        if not r.get("valid"):
            continue
        row = f"| {r['season']} | {r['n_bets']} | {r.get('baseline_clv', 0):.4f} |"
        for col in TRAJ_FEATURE_COLS:
            corr = r.get(f"{col}_corr", float("nan"))
            pval = r.get(f"{col}_pval", float("nan"))
            row += f" {corr:.3f} (p={pval:.3f}) |"
        lines.append(row + "\n")

    lines.append("\n## Recommendation\n_To be filled after consolidation._\n")
    return "".join(lines)


def main():
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    all_features = []
    all_results = []
    audit_results = []

    for season in VALID_SEASONS:
        try:
            bart = load_barttorvik_snapshots(season)
            audit = audit_snapshot_frequency(season, bart)
            audit_results.append(audit)

            if not audit["valid"]:
                logger.warning("Season %d: insufficient snapshots (%d), skipping",
                               season, audit["unique_dates"])
                continue

            features = compute_season_features(season)
            features.to_parquet(
                RESEARCH_DIR / f"efficiency_trajectory_features_{season}.parquet",
                index=False,
            )
            all_features.append(features)

            bt_path = BACKTEST_DIR / f"ncaab_elo_backtest_{season}.parquet"
            if bt_path.exists():
                baseline = pd.read_parquet(bt_path)
                result = evaluate_against_baseline(features, baseline, season)
                all_results.append(result)

        except Exception as e:
            logger.error("Season %d failed: %s", season, e)
            continue

    if len(all_results) < 4:
        logger.error("ABORT: Only %d valid seasons (need ≥4)", len(all_results))
        sys.exit(1)

    combined = pd.concat(all_features, ignore_index=True)
    report = generate_report(all_results, audit_results, combined)

    report_path = REPORT_DIR / "efficiency_trajectory_report.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info("Report written to %s", report_path)


if __name__ == "__main__":
    main()
```

**Step 2: Run the pipeline**

Run: `venv/Scripts/python.exe scripts/research_efficiency_trajectory.py`
Expected: Feature parquets + report written

**Step 3: Commit**

```bash
git add scripts/research_efficiency_trajectory.py
git commit -m "feat: add efficiency trajectory research pipeline"
```

---

## Phase 3: Consolidation

### Task 3.1: Build consolidation script

**Files:**
- Create: `scripts/research_consolidation.py`

**Step 1: Write the consolidation script**

```python
"""Research Consolidation: Combine Late-Season Losses + Efficiency Trajectory.

Runs AFTER both research agents complete. Merges feature sets,
runs cross-correlation analysis, VIF checks, and combined evaluation.

Usage:
    venv/Scripts/python.exe scripts/research_consolidation.py
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from scipy import stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RESEARCH_DIR = PROJECT_ROOT / "data" / "research"
REPORT_DIR = PROJECT_ROOT / "docs" / "research"
BACKTEST_DIR = PROJECT_ROOT / "data" / "backtests"
VALID_SEASONS = (2021, 2022, 2023, 2024, 2025)

LOSS_COLS = [
    "late_loss_count_5g", "late_loss_count_10g", "loss_margin_mean_10g",
    "weighted_quality_loss_10g", "bad_loss_weighted_10g", "home_loss_rate_10g",
]
TRAJ_COLS = [
    "adj_o_slope_10s", "adj_d_slope_10s", "net_efficiency_slope_10s",
    "barthag_delta_10s", "barthag_delta_20s", "rank_change_20s",
]
ALL_FEATURE_COLS = LOSS_COLS + TRAJ_COLS


def compute_vif(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Compute Variance Inflation Factor for each feature."""
    from numpy.linalg import LinAlgError

    clean = df[columns].dropna()
    if len(clean) < len(columns) + 10:
        return pd.DataFrame({"feature": columns, "vif": [np.nan] * len(columns)})

    vifs = []
    for i, col in enumerate(columns):
        others = [c for j, c in enumerate(columns) if j != i]
        y = clean[col].values
        X = clean[others].values
        X = np.column_stack([np.ones(len(X)), X])
        try:
            from numpy.linalg import lstsq
            beta, _, _, _ = lstsq(X, y, rcond=None)
            y_pred = X @ beta
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else 0
            vif = 1 / (1 - r_sq) if r_sq < 1 else np.inf
        except LinAlgError:
            vif = np.nan
        vifs.append(vif)

    return pd.DataFrame({"feature": columns, "vif": vifs})


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Load both feature sets
    loss_dfs = []
    traj_dfs = []
    has_loss = True
    has_traj = True

    for season in VALID_SEASONS:
        loss_path = RESEARCH_DIR / f"late_season_loss_features_{season}.parquet"
        traj_path = RESEARCH_DIR / f"efficiency_trajectory_features_{season}.parquet"

        if loss_path.exists():
            loss_dfs.append(pd.read_parquet(loss_path))
        if traj_path.exists():
            traj_dfs.append(pd.read_parquet(traj_path))

    if not loss_dfs:
        logger.warning("No late-season loss results found")
        has_loss = False
    if not traj_dfs:
        logger.warning("No efficiency trajectory results found")
        has_traj = False

    if not has_loss and not has_traj:
        logger.error("ABORT: Neither research item produced results")
        sys.exit(1)

    lines = ["# Consolidated Tournament Research Report\n\n"]

    # Merge feature sets
    if has_loss and has_traj:
        loss_all = pd.concat(loss_dfs, ignore_index=True)
        traj_all = pd.concat(traj_dfs, ignore_index=True)

        merged = loss_all.merge(
            traj_all,
            on=["season", "game_id", "team_id"],
            how="inner",
            suffixes=("", "_traj"),
        )
        logger.info("Merged %d rows across both feature sets", len(merged))

        # Cross-correlation matrix
        available = [c for c in ALL_FEATURE_COLS if c in merged.columns]
        corr = merged[available].corr()

        lines.append("## Cross-Correlation Matrix\n```\n")
        lines.append(corr.to_string())
        lines.append("\n```\n\n")

        # Flag high correlations
        lines.append("## High Correlations (|r| > 0.7)\n")
        for i, c1 in enumerate(available):
            for c2 in available[i + 1:]:
                r = corr.loc[c1, c2]
                if abs(r) > 0.7:
                    lines.append(f"- **{c1}** vs **{c2}**: r={r:.3f} — REDUNDANCY FLAG\n")

        # VIF analysis
        vif_df = compute_vif(merged, available)
        lines.append("\n## VIF Analysis\n")
        lines.append("| Feature | VIF | Flag |\n|---------|-----|------|\n")
        for _, row in vif_df.iterrows():
            flag = "HIGH" if row["vif"] > 5 else ""
            lines.append(f"| {row['feature']} | {row['vif']:.2f} | {flag} |\n")

        # Combined evaluation against baseline
        lines.append("\n## Combined Feature Evaluation vs Baseline\n")
        for season in VALID_SEASONS:
            bt_path = BACKTEST_DIR / f"ncaab_elo_backtest_{season}.parquet"
            if not bt_path.exists():
                continue
            baseline = pd.read_parquet(bt_path)
            season_merged = merged[merged["season"] == season]
            combined = baseline.merge(season_merged, on="game_id", how="inner", suffixes=("", "_res"))

            if len(combined) < 50:
                continue

            lines.append(f"\n### Season {season} (n={len(combined)})\n")
            lines.append(f"- Baseline CLV: {combined['clv'].mean():.4f}\n")
            lines.append(f"- Baseline ROI: {combined['profit_loss'].sum() / combined['stake'].sum():.2%}\n")

            for col in available:
                if col in combined.columns:
                    valid = combined[[col, "clv"]].dropna()
                    if len(valid) >= 30:
                        r, p = stats.pearsonr(valid[col], valid["clv"])
                        sig = "*" if p < 0.05 else ""
                        lines.append(f"  - {col}: r={r:.3f}, p={p:.3f} {sig}\n")

    elif has_loss:
        lines.append("## Only Late-Season Loss results available\n")
        lines.append("See `late_season_losses_report.md` for details.\n")
    else:
        lines.append("## Only Efficiency Trajectory results available\n")
        lines.append("See `efficiency_trajectory_report.md` for details.\n")

    # Promotion readiness checklist
    lines.append("\n## Promotion Readiness Checklist\n")
    lines.append("- [ ] Marginal CLV lift ≥ +0.5% (pooled)\n")
    lines.append("- [ ] OOS ROI delta ≥ +2% (pooled)\n")
    lines.append("- [ ] Feature importance stable in ≥4/5 seasons\n")
    lines.append("- [ ] No feature correlated >0.7 with existing model features\n")
    lines.append("- [ ] VIF < 5 for all selected features\n")
    lines.append("- [ ] In-sample ROI ≤ 2x OOS ROI\n")
    lines.append("- [ ] ≥200 bets per test season\n")
    lines.append("- [ ] User review completed\n")

    report = "".join(lines)
    report_path = REPORT_DIR / "consolidated_tournament_research.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info("Consolidated report written to %s", report_path)


if __name__ == "__main__":
    main()
```

**Step 2: This script runs after Phase 1 and Phase 2 complete.**

Run: `venv/Scripts/python.exe scripts/research_consolidation.py`
Expected: `docs/research/consolidated_tournament_research.md` with correlation matrix, VIF, and combined evaluation.

**Step 3: Commit**

```bash
git add scripts/research_consolidation.py
git commit -m "feat: add research consolidation pipeline"
```

---

## Phase 4: Lint, Test, Final Commit

### Task 4.1: Run full test suite and linting

**Step 1: Lint all new files**

Run: `venv/Scripts/python.exe -m ruff check features/sport_specific/ncaab/research_utils.py features/sport_specific/ncaab/late_season_losses.py features/sport_specific/ncaab/efficiency_trajectory.py scripts/research_late_season_losses.py scripts/research_efficiency_trajectory.py scripts/research_consolidation.py --fix`

**Step 2: Format**

Run: `venv/Scripts/python.exe -m ruff format features/sport_specific/ncaab/research_utils.py features/sport_specific/ncaab/late_season_losses.py features/sport_specific/ncaab/efficiency_trajectory.py`

**Step 3: Run all tests**

Run: `venv/Scripts/python.exe -m pytest tests/test_research_utils.py tests/test_late_season_losses.py tests/test_efficiency_trajectory.py -v -p no:examples`
Expected: All PASS

---

## Execution Architecture

```
┌─────────────────────┐     ┌──────────────────────────┐
│ Task 0.1-0.2        │     │  (Sequential prereq)     │
│ Shared infra        │─────│  Must complete first     │
└────────┬────────────┘     └──────────────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌─────────┐    ← PARALLEL: Agents 1 & 2
│Task 1.1│ │Task 2.1 │      run simultaneously
│Task 1.2│ │Task 2.2 │
└───┬────┘ └────┬────┘
    │           │
    └─────┬─────┘
          ▼
   ┌──────────────┐
   │ Task 3.1     │    ← SEQUENTIAL: after both complete
   │Consolidation │
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │ Task 4.1     │    ← Final lint + test
   │ Cleanup      │
   └──────────────┘
```

**Agentic execution strategy:**
1. Main agent runs Task 0.1 and 0.2 (shared infra)
2. Spawn two parallel subagents for Phases 1 and 2
3. When both complete, run Phase 3 consolidation
4. Run Phase 4 cleanup
5. Present final report to user
