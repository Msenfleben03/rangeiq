# Barttorvik T-Rank Integration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate Barttorvik T-Rank efficiency ratings (AdjO, AdjD, AdjTempo, Barthag)
as features in the NCAAB Elo model, using the free cbbdata REST API with point-in-time
daily snapshots.

**Architecture:** A new `BarttovikFetcher` pipeline fetches and caches all 6 seasons of
daily T-Rank ratings to a single Parquet file. The backtest loads this file at startup and
looks up point-in-time ratings for each team before each game. Barttorvik features are
injected as probability adjustments alongside existing advanced features, reusing the
`run_backtest_with_features()` framework.

**Tech Stack:** Python 3.11+, requests, pandas, pyarrow (parquet), pytest

---

## Prerequisites

Before starting, the user must have a cbbdata API key. Check:

```bash
# Check for existing key in .env
grep -i cbbdata .env 2>/dev/null || echo "No CBBDATA key in .env"
```

If no key exists, the user must register at <https://www.cbbdata.com> and add
`CBBDATA_API_KEY=<key>` to `.env`. The plan cannot proceed without this.

---

## Task 1: Add CBBDATA_API_KEY to Environment Config

##### Files

- Modify: `.env.example`
- Modify: `config/settings.py`

##### Step 1: Add CBBDATA_API_KEY to .env.example

Add after the CFBD_API_KEY section:

```python
# CBBData / Barttorvik T-Rank (https://www.cbbdata.com/)
# Free with registration - provides daily point-in-time efficiency ratings
CBBDATA_API_KEY=your_cbbdata_api_key_here
```

##### Step 2: Load CBBDATA_API_KEY in config/settings.py

Add after `ODDS_API_KEY` line (~131):

```python
# CBBData / Barttorvik T-Rank API key (free, provides efficiency ratings)
CBBDATA_API_KEY = os.environ.get("CBBDATA_API_KEY", "")
```

Also add a path constant for the cached ratings data:

```python
BARTTORVIK_DATA_DIR = DATA_DIR / "external" / "barttorvik"
```

##### Step 3: Run test to verify config loads

Run:

```bash
venv/Scripts/python.exe -c "from config.settings import CBBDATA_API_KEY, BARTTORVIK_DATA_DIR; print(f'Key loaded: {bool(CBBDATA_API_KEY)}'); print(f'Dir: {BARTTORVIK_DATA_DIR}')"
```

Expected: Prints key status and path without errors.

##### Step 4: Commit

```bash
git add .env.example config/settings.py
git commit -m "feat: add CBBDATA_API_KEY config for Barttorvik integration"
```

---

## Task 2: Write Failing Tests for BarttovikFetcher

##### Files

- Create: `tests/test_barttorvik_fetcher.py`

##### Step 1: Write the failing tests

```python
"""Tests for Barttorvik T-Rank fetcher pipeline.

Tests cover:
- API response parsing (mocked)
- Point-in-time rating lookup
- Season caching to parquet
- Team name matching
- Error handling (no API key, network errors, bad data)
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# --- Fixtures ---

SAMPLE_API_RESPONSE = [
    {
        "rank": 1,
        "team": "Houston",
        "conf": "Big 12",
        "barthag": 0.9744,
        "adj_o": 120.5,
        "adj_d": 85.3,
        "adj_t": 67.2,
        "wab": 9.8,
        "year": 2025,
        "date": "2025-01-15",
    },
    {
        "rank": 2,
        "team": "Duke",
        "conf": "ACC",
        "barthag": 0.9650,
        "adj_o": 122.1,
        "adj_d": 88.0,
        "adj_t": 70.5,
        "wab": 8.5,
        "year": 2025,
        "date": "2025-01-15",
    },
    {
        "rank": 1,
        "team": "Houston",
        "conf": "Big 12",
        "barthag": 0.9750,
        "adj_o": 121.0,
        "adj_d": 85.0,
        "adj_t": 67.5,
        "wab": 10.0,
        "year": 2025,
        "date": "2025-01-20",
    },
    {
        "rank": 3,
        "team": "Duke",
        "conf": "ACC",
        "barthag": 0.9600,
        "adj_o": 121.5,
        "adj_d": 89.0,
        "adj_t": 70.2,
        "wab": 8.0,
        "year": 2025,
        "date": "2025-01-20",
    },
]


@pytest.fixture
def sample_ratings_df():
    """Create a sample ratings DataFrame matching API structure."""
    return pd.DataFrame(SAMPLE_API_RESPONSE)


@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache = tmp_path / "barttorvik"
    cache.mkdir()
    return cache


# --- Test: API Response Parsing ---


class TestParseAPIResponse:
    """Test parsing raw JSON response into DataFrame."""

    def test_parse_valid_response(self):
        from pipelines.barttorvik_fetcher import parse_ratings_response

        df = parse_ratings_response(SAMPLE_API_RESPONSE, season=2025)
        assert len(df) == 4
        assert "team" in df.columns
        assert "adj_o" in df.columns
        assert "adj_d" in df.columns
        assert "adj_t" in df.columns
        assert "barthag" in df.columns
        assert "date" in df.columns

    def test_parse_empty_response(self):
        from pipelines.barttorvik_fetcher import parse_ratings_response

        df = parse_ratings_response([], season=2025)
        assert len(df) == 0

    def test_parse_coerces_date_to_datetime(self):
        from pipelines.barttorvik_fetcher import parse_ratings_response

        df = parse_ratings_response(SAMPLE_API_RESPONSE, season=2025)
        assert pd.api.types.is_datetime64_any_dtype(df["date"])

    def test_parse_coerces_numeric_columns(self):
        from pipelines.barttorvik_fetcher import parse_ratings_response

        df = parse_ratings_response(SAMPLE_API_RESPONSE, season=2025)
        assert df["adj_o"].dtype in (np.float64, np.float32)
        assert df["adj_d"].dtype in (np.float64, np.float32)
        assert df["barthag"].dtype in (np.float64, np.float32)


# --- Test: Point-in-Time Lookup ---


class TestPointInTimeLookup:
    """Test looking up a team's ratings on or before a specific date."""

    def test_lookup_exact_date(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import lookup_team_ratings

        result = lookup_team_ratings(
            sample_ratings_df, team="Houston", game_date=date(2025, 1, 15)
        )
        assert result is not None
        assert result["adj_o"] == pytest.approx(120.5)
        assert result["barthag"] == pytest.approx(0.9744)

    def test_lookup_between_dates_uses_earlier(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import lookup_team_ratings

        # Game on Jan 18 — should use Jan 15 ratings (not Jan 20)
        sample_ratings_df["date"] = pd.to_datetime(sample_ratings_df["date"])
        result = lookup_team_ratings(
            sample_ratings_df, team="Houston", game_date=date(2025, 1, 18)
        )
        assert result is not None
        assert result["adj_o"] == pytest.approx(120.5)

    def test_lookup_after_latest_uses_latest(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import lookup_team_ratings

        sample_ratings_df["date"] = pd.to_datetime(sample_ratings_df["date"])
        result = lookup_team_ratings(
            sample_ratings_df, team="Houston", game_date=date(2025, 2, 1)
        )
        assert result is not None
        assert result["adj_o"] == pytest.approx(121.0)  # Jan 20 value

    def test_lookup_before_earliest_returns_none(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import lookup_team_ratings

        sample_ratings_df["date"] = pd.to_datetime(sample_ratings_df["date"])
        result = lookup_team_ratings(
            sample_ratings_df, team="Houston", game_date=date(2024, 10, 1)
        )
        assert result is None

    def test_lookup_unknown_team_returns_none(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import lookup_team_ratings

        sample_ratings_df["date"] = pd.to_datetime(sample_ratings_df["date"])
        result = lookup_team_ratings(
            sample_ratings_df, team="Nonexistent U", game_date=date(2025, 1, 15)
        )
        assert result is None


# --- Test: Cache Management ---


class TestCacheManagement:
    """Test saving/loading ratings to parquet cache."""

    def test_save_and_load_season(self, sample_ratings_df, tmp_cache_dir):
        from pipelines.barttorvik_fetcher import (
            load_cached_season,
            save_season_cache,
        )

        sample_ratings_df["date"] = pd.to_datetime(sample_ratings_df["date"])
        save_season_cache(sample_ratings_df, season=2025, cache_dir=tmp_cache_dir)
        loaded = load_cached_season(season=2025, cache_dir=tmp_cache_dir)
        assert loaded is not None
        assert len(loaded) == 4

    def test_load_missing_cache_returns_none(self, tmp_cache_dir):
        from pipelines.barttorvik_fetcher import load_cached_season

        result = load_cached_season(season=2099, cache_dir=tmp_cache_dir)
        assert result is None


# --- Test: Matchup Ratings Extraction ---


class TestMatchupRatings:
    """Test extracting Barttorvik differentials for a matchup."""

    def test_compute_matchup_differentials(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import compute_barttorvik_differentials

        sample_ratings_df["date"] = pd.to_datetime(sample_ratings_df["date"])
        diffs = compute_barttorvik_differentials(
            ratings_df=sample_ratings_df,
            home_team="Houston",
            away_team="Duke",
            game_date=date(2025, 1, 15),
        )
        assert diffs is not None
        # Houston AdjO=120.5, Duke AdjO=122.1 -> diff = -1.6
        assert "adj_o_diff" in diffs
        assert diffs["adj_o_diff"] == pytest.approx(120.5 - 122.1)
        # Houston AdjD=85.3, Duke AdjD=88.0 -> diff = -2.7 (lower = better)
        assert "adj_d_diff" in diffs
        assert diffs["adj_d_diff"] == pytest.approx(85.3 - 88.0)
        assert "barthag_diff" in diffs
        assert "adj_t_diff" in diffs

    def test_differentials_missing_one_team_returns_none(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import compute_barttorvik_differentials

        sample_ratings_df["date"] = pd.to_datetime(sample_ratings_df["date"])
        diffs = compute_barttorvik_differentials(
            ratings_df=sample_ratings_df,
            home_team="Houston",
            away_team="Nonexistent U",
            game_date=date(2025, 1, 15),
        )
        assert diffs is None


# --- Test: Fetcher Class ---


class TestBarttovikFetcher:
    """Test the main fetcher class."""

    @patch("pipelines.barttorvik_fetcher.requests.Session")
    def test_fetch_season_success(self, mock_session_cls):
        from pipelines.barttorvik_fetcher import BarttovikFetcher

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_API_RESPONSE
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        fetcher = BarttovikFetcher(api_key="test_key")
        df = fetcher.fetch_season(2025)
        assert df is not None
        assert len(df) == 4

    @patch("pipelines.barttorvik_fetcher.requests.Session")
    def test_fetch_season_401_raises(self, mock_session_cls):
        from pipelines.barttorvik_fetcher import BarttovikFetcher

        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
        mock_session.get.return_value = mock_response
        mock_session_cls.return_value = mock_session

        fetcher = BarttovikFetcher(api_key="bad_key")
        with pytest.raises(Exception):
            fetcher.fetch_season(2025)

    def test_fetcher_no_api_key_raises(self):
        from pipelines.barttorvik_fetcher import BarttovikFetcher

        with pytest.raises(ValueError, match="API key"):
            BarttovikFetcher(api_key="")


# --- Test: Efficiency Feature Computation ---


class TestEfficiencyFeatures:
    """Test deriving betting features from raw Barttorvik ratings."""

    def test_net_rating_computed(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import compute_barttorvik_differentials

        sample_ratings_df["date"] = pd.to_datetime(sample_ratings_df["date"])
        diffs = compute_barttorvik_differentials(
            ratings_df=sample_ratings_df,
            home_team="Houston",
            away_team="Duke",
            game_date=date(2025, 1, 15),
        )
        # Net rating = AdjO - AdjD
        # Houston: 120.5 - 85.3 = 35.2
        # Duke: 122.1 - 88.0 = 34.1
        # Diff = 35.2 - 34.1 = 1.1
        assert "net_rating_diff" in diffs
        assert diffs["net_rating_diff"] == pytest.approx(1.1, abs=0.01)

    def test_tempo_differential(self, sample_ratings_df):
        from pipelines.barttorvik_fetcher import compute_barttorvik_differentials

        sample_ratings_df["date"] = pd.to_datetime(sample_ratings_df["date"])
        diffs = compute_barttorvik_differentials(
            ratings_df=sample_ratings_df,
            home_team="Houston",
            away_team="Duke",
            game_date=date(2025, 1, 15),
        )
        # Houston tempo=67.2, Duke tempo=70.5
        assert "adj_t_diff" in diffs
        assert diffs["adj_t_diff"] == pytest.approx(67.2 - 70.5)
```

##### Step 2: Run tests to verify they fail

Run: `venv/Scripts/python.exe -m pytest tests/test_barttorvik_fetcher.py -v`

Expected: All tests FAIL with `ModuleNotFoundError: No module named 'pipelines.barttorvik_fetcher'`

##### Step 3: Commit

```bash
git add tests/test_barttorvik_fetcher.py
git commit -m "test: add failing tests for Barttorvik T-Rank fetcher"
```

---

## Task 3: Implement BarttovikFetcher Pipeline

##### Files

- Create: `pipelines/barttorvik_fetcher.py`

##### Step 1: Implement the module

```python
"""Barttorvik T-Rank Fetcher Pipeline.

Fetches historical Barttorvik T-Rank efficiency ratings from the free
cbbdata.com REST API. Provides point-in-time daily snapshots of:
- Adjusted Offensive Efficiency (AdjO)
- Adjusted Defensive Efficiency (AdjD)
- Adjusted Tempo (AdjT)
- Barthag (overall team quality, 0-1)

Data is cached to parquet files per season for fast repeated access.

Usage:
    fetcher = BarttovikFetcher(api_key="your_key")
    df = fetcher.fetch_season(2025)
    ratings = lookup_team_ratings(df, "Houston", date(2025, 1, 15))
"""

from __future__ import annotations

import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CBBDATA_BASE_URL = "https://www.cbbdata.com/api"
RATINGS_ENDPOINT = f"{CBBDATA_BASE_URL}/torvik/ratings/archive"
DEFAULT_CACHE_DIR = Path("data/external/barttorvik")

# Columns we care about from the API response
RATING_COLUMNS = [
    "rank", "team", "conf", "barthag",
    "adj_o", "adj_d", "adj_t",
    "wab", "year", "date",
]

# Rate limiting
REQUEST_DELAY = 1.0  # seconds between requests


# ---------------------------------------------------------------------------
# Response Parsing
# ---------------------------------------------------------------------------


def parse_ratings_response(
    data: list[dict[str, Any]],
    season: int,
) -> pd.DataFrame:
    """Parse raw API JSON response into a clean DataFrame.

    Args:
        data: List of rating records from the API.
        season: Season year for labeling.

    Returns:
        DataFrame with standardized columns and dtypes.
        Empty DataFrame if input is empty.
    """
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)

    # Keep only columns we need (API may return extras)
    available = [c for c in RATING_COLUMNS if c in df.columns]
    df = df[available].copy()

    # Coerce types
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    for col in ("adj_o", "adj_d", "adj_t", "barthag", "wab"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "rank" in df.columns:
        df["rank"] = pd.to_numeric(df["rank"], errors="coerce").astype("Int64")

    if "year" not in df.columns:
        df["year"] = season

    # Sort by date then team for consistent ordering
    if "date" in df.columns and "team" in df.columns:
        df = df.sort_values(["date", "team"]).reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# Point-in-Time Lookup
# ---------------------------------------------------------------------------


def lookup_team_ratings(
    ratings_df: pd.DataFrame,
    team: str,
    game_date: date,
) -> Optional[dict[str, Any]]:
    """Look up a team's most recent ratings on or before a given date.

    This is the core point-in-time function that prevents look-ahead bias:
    for a game on date X, we only use ratings published on or before date X.

    Args:
        ratings_df: Full season ratings DataFrame (must have 'team', 'date' cols).
        team: Team name (must match Barttorvik naming).
        game_date: Game date — ratings on or before this date are considered.

    Returns:
        Dict with rating fields, or None if no data available.
    """
    if ratings_df.empty:
        return None

    # Ensure date column is datetime
    if not pd.api.types.is_datetime64_any_dtype(ratings_df["date"]):
        ratings_df = ratings_df.copy()
        ratings_df["date"] = pd.to_datetime(ratings_df["date"])

    game_dt = pd.Timestamp(game_date)

    # Filter to this team's ratings on or before game date
    mask = (ratings_df["team"] == team) & (ratings_df["date"] <= game_dt)
    team_ratings = ratings_df.loc[mask]

    if team_ratings.empty:
        return None

    # Take the most recent entry
    latest = team_ratings.loc[team_ratings["date"].idxmax()]
    return latest.to_dict()


# ---------------------------------------------------------------------------
# Matchup Differentials
# ---------------------------------------------------------------------------


def compute_barttorvik_differentials(
    ratings_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    game_date: date,
) -> Optional[dict[str, float]]:
    """Compute Barttorvik rating differentials for a matchup.

    Returns home - away differences for each metric. Also computes
    derived features like net rating differential.

    Args:
        ratings_df: Full season ratings DataFrame.
        home_team: Home team name.
        away_team: Away team name.
        game_date: Game date for point-in-time lookup.

    Returns:
        Dict of differentials, or None if either team lacks data.
    """
    home_ratings = lookup_team_ratings(ratings_df, home_team, game_date)
    away_ratings = lookup_team_ratings(ratings_df, away_team, game_date)

    if home_ratings is None or away_ratings is None:
        return None

    diffs: dict[str, float] = {}

    # Raw differentials
    for col in ("adj_o", "adj_d", "adj_t", "barthag"):
        h_val = home_ratings.get(col)
        a_val = away_ratings.get(col)
        if h_val is not None and a_val is not None:
            diffs[f"{col}_diff"] = float(h_val) - float(a_val)

    # Derived: net rating (AdjO - AdjD) differential
    h_net = (home_ratings.get("adj_o", 0) or 0) - (home_ratings.get("adj_d", 0) or 0)
    a_net = (away_ratings.get("adj_o", 0) or 0) - (away_ratings.get("adj_d", 0) or 0)
    diffs["net_rating_diff"] = float(h_net - a_net)

    return diffs


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------


def _cache_path(season: int, cache_dir: Path) -> Path:
    """Return the parquet cache file path for a season."""
    return cache_dir / f"barttorvik_ratings_{season}.parquet"


def save_season_cache(
    df: pd.DataFrame,
    season: int,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Path:
    """Save season ratings to parquet cache.

    Args:
        df: Ratings DataFrame.
        season: Season year.
        cache_dir: Cache directory path.

    Returns:
        Path to the saved file.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(season, cache_dir)
    df.to_parquet(path, index=False)
    logger.info("Cached %d ratings for season %d to %s", len(df), season, path)
    return path


def load_cached_season(
    season: int,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Optional[pd.DataFrame]:
    """Load cached season ratings from parquet.

    Args:
        season: Season year.
        cache_dir: Cache directory path.

    Returns:
        DataFrame or None if cache doesn't exist.
    """
    path = _cache_path(season, cache_dir)
    if not path.exists():
        return None

    df = pd.read_parquet(path)
    logger.info("Loaded %d cached ratings for season %d", len(df), season)
    return df


# ---------------------------------------------------------------------------
# Fetcher Class
# ---------------------------------------------------------------------------


class BarttovikFetcher:
    """Fetches Barttorvik T-Rank ratings from cbbdata.com API.

    Args:
        api_key: cbbdata.com API key. Required.
        cache_dir: Directory for parquet cache files.
        request_delay: Seconds between API requests.

    Raises:
        ValueError: If api_key is empty.
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        request_delay: float = REQUEST_DELAY,
    ) -> None:
        if not api_key:
            # Try environment variable
            api_key = os.environ.get("CBBDATA_API_KEY", "")
        if not api_key:
            raise ValueError(
                "API key required. Set CBBDATA_API_KEY environment variable "
                "or pass api_key parameter. Register free at https://www.cbbdata.com"
            )
        self._api_key = api_key
        self._cache_dir = cache_dir
        self._request_delay = request_delay
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "sports-betting-research/1.0",
            "Accept": "application/json",
        })
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            time.sleep(self._request_delay - elapsed)

    def fetch_season(
        self,
        season: int,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch all daily ratings for a season.

        Checks cache first. If not cached, fetches from API and caches.

        Args:
            season: Season year (e.g. 2025 = 2024-25 season).
            use_cache: If True, check cache before hitting API.

        Returns:
            DataFrame with daily ratings for all teams.

        Raises:
            Exception: If API request fails (401, 500, etc.).
        """
        # Check cache first
        if use_cache:
            cached = load_cached_season(season, self._cache_dir)
            if cached is not None:
                return cached

        # Fetch from API
        self._rate_limit()
        url = RATINGS_ENDPOINT
        params = {"year": season, "key": self._api_key}

        logger.info("Fetching Barttorvik ratings for season %d...", season)
        response = self._session.get(url, params=params, timeout=60)
        self._last_request_time = time.time()

        if response.status_code != 200:
            response.raise_for_status()

        data = response.json()
        df = parse_ratings_response(data, season)

        if not df.empty:
            save_season_cache(df, season, self._cache_dir)

        logger.info(
            "Fetched %d ratings for season %d (%d teams, %d dates)",
            len(df),
            season,
            df["team"].nunique() if "team" in df.columns else 0,
            df["date"].nunique() if "date" in df.columns else 0,
        )
        return df

    def fetch_all_seasons(
        self,
        seasons: list[int] | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch ratings for multiple seasons and combine.

        Args:
            seasons: List of season years. Defaults to 2020-2025.
            use_cache: Check cache before API calls.

        Returns:
            Combined DataFrame for all seasons.
        """
        if seasons is None:
            seasons = [2020, 2021, 2022, 2023, 2024, 2025]

        all_dfs = []
        for season in seasons:
            try:
                df = self.fetch_season(season, use_cache=use_cache)
                if not df.empty:
                    all_dfs.append(df)
                    logger.info("Season %d: %d ratings", season, len(df))
            except Exception as exc:
                logger.error("Failed to fetch season %d: %s", season, exc)
                continue

        if not all_dfs:
            return pd.DataFrame()

        combined = pd.concat(all_dfs, ignore_index=True)
        logger.info(
            "Total: %d ratings across %d seasons",
            len(combined),
            len(all_dfs),
        )
        return combined

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()
```

##### Step 2: Run tests to verify they pass

Run: `venv/Scripts/python.exe -m pytest tests/test_barttorvik_fetcher.py -v`

Expected: All tests PASS.

##### Step 3: Commit

```bash
git add pipelines/barttorvik_fetcher.py
git commit -m "feat: implement Barttorvik T-Rank fetcher with caching and PIT lookup"
```

---

## Task 4: Write Fetch Script for All 6 Seasons

##### Files

- Create: `scripts/fetch_barttorvik_data.py`

##### Step 1: Write the CLI script

```python
"""Fetch and cache Barttorvik T-Rank ratings for all seasons.

Downloads daily point-in-time efficiency ratings from the cbbdata.com API
and caches them as parquet files in data/external/barttorvik/.

Requires CBBDATA_API_KEY in .env or environment.

Usage:
    python scripts/fetch_barttorvik_data.py
    python scripts/fetch_barttorvik_data.py --seasons 2025
    python scripts/fetch_barttorvik_data.py --force  # re-download even if cached
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from config.settings import CBBDATA_API_KEY
from pipelines.barttorvik_fetcher import BarttovikFetcher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Barttorvik T-Rank ratings")
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=[2020, 2021, 2022, 2023, 2024, 2025],
        help="Seasons to fetch (default: 2020-2025)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if cache exists",
    )
    args = parser.parse_args()

    if not CBBDATA_API_KEY:
        logger.error(
            "CBBDATA_API_KEY not found. Set it in .env or environment. "
            "Register free at https://www.cbbdata.com"
        )
        sys.exit(1)

    fetcher = BarttovikFetcher(api_key=CBBDATA_API_KEY)

    try:
        combined = fetcher.fetch_all_seasons(
            seasons=args.seasons,
            use_cache=not args.force,
        )

        if combined.empty:
            logger.error("No data fetched. Check your API key.")
            sys.exit(1)

        # Print summary
        print(f"\n{'=' * 60}")
        print("BARTTORVIK DATA SUMMARY")
        print(f"{'=' * 60}")
        for season in args.seasons:
            season_df = combined[combined["year"] == season]
            if not season_df.empty:
                print(
                    f"  Season {season}: {len(season_df):,} ratings, "
                    f"{season_df['team'].nunique()} teams, "
                    f"{season_df['date'].nunique()} dates"
                )
        print(f"\n  Total: {len(combined):,} ratings")
        print(f"  Cache: data/external/barttorvik/")
    finally:
        fetcher.close()


if __name__ == "__main__":
    main()
```

##### Step 2: Verify it runs (dry run with cache check)

Run: `venv/Scripts/python.exe scripts/fetch_barttorvik_data.py --seasons 2025`

Expected: Fetches season 2025 from API (or cache) and prints summary.

##### Step 3: Fetch all 6 seasons

Run: `venv/Scripts/python.exe scripts/fetch_barttorvik_data.py`

Expected: All 6 seasons fetched and cached. ~347K total ratings.

##### Step 4: Commit

```bash
git add scripts/fetch_barttorvik_data.py
git commit -m "feat: add CLI script to fetch and cache Barttorvik ratings"
```

---

## Task 5: Build Team Name Mapping (ESPN <-> Barttorvik)

##### Files

- Create: `pipelines/team_name_mapping.py`
- Create: `tests/test_team_name_mapping.py`

**Context:** ESPN uses team IDs (e.g., "2305" for Houston), while Barttorvik uses
team names (e.g., "Houston"). The backtest games have ESPN team IDs. We need a
mapping to look up Barttorvik ratings.

##### Step 1: Write failing test for team name mapper

```python
"""Tests for ESPN <-> Barttorvik team name mapping."""

import pytest


class TestTeamNameMapping:
    def test_espn_id_to_barttorvik_name(self):
        from pipelines.team_name_mapping import espn_id_to_barttorvik

        # Houston Cougars
        assert espn_id_to_barttorvik("2305") == "Houston"

    def test_unknown_id_returns_none(self):
        from pipelines.team_name_mapping import espn_id_to_barttorvik

        assert espn_id_to_barttorvik("999999") is None

    def test_build_mapping_from_data(self):
        from pipelines.team_name_mapping import build_espn_barttorvik_mapping

        mapping = build_espn_barttorvik_mapping()
        assert len(mapping) > 300  # D1 has ~360 teams
        assert isinstance(mapping, dict)
```

##### Step 2: Implement team name mapper

Two approaches:

1. **Static mapping** — build once from ESPN API team list + Barttorvik team list,
   use fuzzy matching to align
2. **Dynamic** — use the ESPN fetcher's existing team data

The pragmatic approach: load ESPN raw game data to extract `team_id` <-> `team_name`
pairs, then fuzzy-match against Barttorvik team names from the ratings data.

The mapper will:

1. Load all ESPN game data to get `(team_id, team_name)` pairs
2. Load Barttorvik ratings to get unique team names
3. Match using normalized names (lowercase, remove "State", etc.)
4. Cache the mapping as JSON

##### Step 3: Run tests, implement, verify

##### Step 4: Commit

```bash
git add pipelines/team_name_mapping.py tests/test_team_name_mapping.py
git commit -m "feat: add ESPN <-> Barttorvik team name mapping"
```

---

## Task 6: Integrate Barttorvik into Backtest

##### Files

- Modify: `scripts/backtest_ncaab_elo.py` — add `--barttorvik` flag
- Modify: `scripts/backtest_ncaab_elo.py:run_backtest_with_features()` — accept
  barttorvik ratings and compute differentials per game

##### Step 1: Add barttorvik_lookup parameter to run_backtest_with_features()

Extend the function signature:

```python
def run_backtest_with_features(
    model: NCAABEloModel,
    games: list[dict],
    feature_engine: NCABBFeatureEngine | None = None,
    feature_weight: float = 0.0,
    barttorvik_df: pd.DataFrame | None = None,  # NEW
    barttorvik_weight: float = 0.0,              # NEW
    team_mapper: Callable | None = None,          # NEW
    min_edge: float = 0.02,
    ...
) -> pd.DataFrame:
```

Inside the game loop, after Elo prediction, add Barttorvik adjustment:

```python
# 1c. BARTTORVIK ADJUSTMENT (if enabled)
bart_adj = 0.0
if barttorvik_df is not None and barttorvik_weight != 0.0 and team_mapper:
    home_bart = team_mapper(home)
    away_bart = team_mapper(away)
    if home_bart and away_bart:
        diffs = compute_barttorvik_differentials(
            barttorvik_df, home_bart, away_bart,
            game["date"].date() if hasattr(game["date"], "date") else game["date"],
        )
        if diffs:
            # Net rating diff is the strongest signal
            net_diff = diffs.get("net_rating_diff", 0)
            barthag_diff = diffs.get("barthag_diff", 0)
            # Convert to probability adjustment
            # ~30 net rating points = ~100% prob range
            bart_adj = (net_diff * 0.015) + (barthag_diff * 0.5)

    home_win_prob = max(0.01, min(0.99,
                        home_win_prob + barttorvik_weight * bart_adj))
```

##### Step 2: Add --barttorvik CLI flag to main()

```python
parser.add_argument(
    "--barttorvik", action="store_true",
    help="Include Barttorvik efficiency ratings as features",
)
parser.add_argument(
    "--barttorvik-weight", type=float, default=1.0,
    help="Weight for Barttorvik probability adjustment (default: 1.0)",
)
```

##### Step 3: Load Barttorvik data in main() when flag is set

```python
if args.barttorvik:
    from pipelines.barttorvik_fetcher import BarttovikFetcher
    from pipelines.team_name_mapping import espn_id_to_barttorvik

    fetcher = BarttovikFetcher()
    barttorvik_df = fetcher.fetch_season(args.test_season)
    team_mapper = espn_id_to_barttorvik
    barttorvik_weight = args.barttorvik_weight
```

##### Step 4: Run single-season backtest with Barttorvik

Run: `venv/Scripts/python.exe scripts/backtest_ncaab_elo.py --test-season 2025 --barttorvik`

Expected: Backtest runs with Barttorvik adjustments. Compare ROI/Sharpe/CLV to Elo-only.

##### Step 5: Commit

```bash
git add scripts/backtest_ncaab_elo.py
git commit -m "feat: integrate Barttorvik ratings into backtest with --barttorvik flag"
```

---

## Task 7: A/B Test Elo + Barttorvik vs Elo-Only

##### Files

- Modify: `scripts/ab_compare_features.py` — add Config C: Elo + Barttorvik

##### Step 1: Extend run_ab_comparison() with barttorvik config

Add a third config (C) that uses Barttorvik alone (no advanced features), and
optionally a config D that uses both Barttorvik + advanced features.

The comparison matrix:

- **Config A**: Elo-only (baseline)
- **Config B**: Elo + advanced features
- **Config C**: Elo + Barttorvik
- **Config D**: Elo + Barttorvik + advanced features

This reuses the existing `paired_comparison()` and `ABResult` infrastructure.

##### Step 2: Add --barttorvik flag to A/B script

```python
parser.add_argument(
    "--barttorvik", action="store_true",
    help="Include Barttorvik configs (C, D) in comparison",
)
```

##### Step 3: Run full 6-season A/B comparison

Run: `venv/Scripts/python.exe scripts/ab_compare_features.py --barttorvik --seasons 2020 2021 2022 2023 2024 2025`

Expected: 4-config comparison across all 6 seasons with paired t-tests.

##### Step 4: Commit

```bash
git add scripts/ab_compare_features.py
git commit -m "feat: add Barttorvik configs to A/B comparison framework"
```

---

## Task 8: Update Documentation and Memory

##### Files

- Modify: `CLAUDE.md` — add Barttorvik pipeline to project structure and status
- Modify: `docs/DECISIONS.md` — add ADR-017 for Barttorvik integration
- Modify: `MEMORY.md` — update pipeline status and results

##### Step 1: Add ADR-017 to DECISIONS.md

```markdown
### ADR-017: Barttorvik T-Rank Integration via cbbdata API

**Status:** Accepted
**Date:** 2026-02-16

**Context:** The model needs efficiency ratings (AdjO, AdjD, AdjTempo) to capture
team quality beyond what Elo provides. KenPom costs $95/yr for API access.

**Decision:** Use free cbbdata.com API for Barttorvik T-Rank ratings.
- Free registration, no cost
- Daily point-in-time snapshots (no look-ahead bias)
- Covers all 6 seasons (2020-2025, ~347K ratings)
- Correlates ~0.95 with KenPom — sufficient for betting

##### Consequences
- Saves $95/yr vs KenPom
- Missing Four Factors (computable from ESPN box scores if needed)
- Adds ~4 features (AdjO diff, AdjD diff, net rating diff, Barthag diff)
```

##### Step 2: Update CLAUDE.md project structure

Add `barttorvik_fetcher.py` and `team_name_mapping.py` to pipelines section.
Add `fetch_barttorvik_data.py` to scripts section.

##### Step 3: Commit

```bash
git add CLAUDE.md docs/DECISIONS.md
git commit -m "docs: add Barttorvik integration ADR and update project structure"
```

---

## Dependency Graph

```text
Task 1 (config)
    └──> Task 2 (tests) ──> Task 3 (fetcher implementation)
                                └──> Task 4 (fetch script)
                                └──> Task 5 (team name mapping)
                                        └──> Task 6 (backtest integration)
                                                └──> Task 7 (A/B test)
                                                        └──> Task 8 (docs)
```

Tasks 2-3 are TDD (write test, implement, verify).
Tasks 4-5 can run in parallel after Task 3.
Tasks 6 depends on 4 and 5.
Task 7 depends on 6.
Task 8 depends on 7 (to include results).

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| No CBBDATA API key | Medium | Blocking | Ask user before starting |
| Team name mismatch ESPN<->Barttorvik | High | Medium | Fuzzy matching + manual overrides |
| API rate limits during bulk fetch | Low | Low | Rate limiting + per-season caching |
| Barttorvik adjustment weights wrong | Medium | Medium | A/B test multiple weights |
| Feature leakage from using same-day rating | Low | High | Point-in-time lookup strictly < game_date |

---

## Success Criteria

1. All 6 seasons cached to `data/external/barttorvik/` (~347K ratings)
2. Point-in-time lookup confirmed: no rating from game-day or later used
3. A/B test shows improvement in at least 4/6 seasons
4. Pooled paired t-test p < 0.10 (one-sided) for Barttorvik configs
5. All new tests pass; existing 560 tests still pass
