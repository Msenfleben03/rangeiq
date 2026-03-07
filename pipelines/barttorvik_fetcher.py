"""Barttorvik T-Rank Fetcher Pipeline.

Fetches historical Barttorvik T-Rank efficiency ratings from the free
cbbdata.com REST API. All columns returned by the API are preserved in
the parquet cache (currently 22 columns), including:
- Adjusted Offensive/Defensive Efficiency (adj_o, adj_d) and ranks
- Adjusted Tempo (adj_tempo) and rank
- Barthag (overall team quality, 0-1)
- WAB (Wins Above Bubble) and rank
- Records, projected records, daily rank change, and more

The API returns Apache Parquet format. Data is cached to parquet files
per season for fast repeated access.

Usage:
    fetcher = BarttovikFetcher(api_key="your_key")
    df = fetcher.fetch_season(2025)
    ratings = lookup_team_ratings(df, "Houston", date(2025, 1, 15))
"""

from __future__ import annotations

import io
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CBBDATA_BASE_URL = "https://www.cbbdata.com/api"
RATINGS_ENDPOINT = f"{CBBDATA_BASE_URL}/torvik/ratings/archive"
DEFAULT_CACHE_DIR = Path("data/external/barttorvik")

# Core columns used by downstream consumers (lookup, differentials, backtest).
# All API columns are preserved in the cache; this list is for reference only.
CORE_RATING_COLUMNS = [
    "rank",
    "team",
    "conf",
    "barthag",
    "adj_o",
    "adj_d",
    "adj_tempo",
    "wab",
    "year",
    "date",
]

# Backward-compatible alias
RATING_COLUMNS = CORE_RATING_COLUMNS

# Rate limiting
REQUEST_DELAY = 1.0  # seconds between requests


# ---------------------------------------------------------------------------
# Response Parsing
# ---------------------------------------------------------------------------


def parse_ratings_response(
    data: bytes,
    season: int,
) -> pd.DataFrame:
    """Parse raw API Parquet response into a clean DataFrame.

    The cbbdata.com API returns Apache Parquet format (application/octet-stream).

    Args:
        data: Raw bytes from the API response.
        season: Season year for labeling.

    Returns:
        DataFrame with standardized columns and dtypes.
        Empty DataFrame if input is empty or invalid.
    """
    if not data:
        return pd.DataFrame()

    try:
        df = pd.read_parquet(io.BytesIO(data))
    except Exception:
        logger.warning("Failed to parse Parquet response for season %d", season)
        return pd.DataFrame()

    # Preserve ALL columns from the API response (no filtering).
    # Downstream consumers select by column name, so extra columns are safe.

    # Coerce core numeric types
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

    for col in ("adj_o", "adj_d", "adj_tempo", "barthag", "wab"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Coerce rank columns to nullable int
    for col in df.columns:
        if col == "rank" or col.endswith("_rk"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")

    if "year" not in df.columns:
        df["year"] = season

    # Sort by date then team for consistent ordering
    if "date" in df.columns and "team" in df.columns:
        df = df.sort_values(["date", "team"]).reset_index(drop=True)

    logger.info(
        "Parsed %d rows, %d columns for season %d",
        len(df),
        len(df.columns),
        season,
    )
    return df


# ---------------------------------------------------------------------------
# Point-in-Time Lookup
# ---------------------------------------------------------------------------


def lookup_team_ratings(
    ratings_df: pd.DataFrame,
    team: str,
    game_date: date,
) -> dict[str, Any] | None:
    """Look up a team's most recent ratings on or before a given date.

    This is the core point-in-time function that prevents look-ahead bias:
    for a game on date X, we only use ratings published on or before date X.

    Args:
        ratings_df: Full season ratings DataFrame (must have 'team', 'date' cols).
        team: Team name (must match Barttorvik naming).
        game_date: Game date -- ratings on or before this date are considered.

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
) -> dict[str, float] | None:
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
    for col in ("adj_o", "adj_d", "adj_tempo", "barthag"):
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


def append_to_cache(
    new_df: pd.DataFrame,
    season: int,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Path:
    """Append new ratings snapshot to existing season cache.

    Deduplicates by (team, date) for idempotent daily appends.

    Args:
        new_df: New ratings DataFrame to append.
        season: Season year.
        cache_dir: Cache directory.

    Returns:
        Path to the updated cache file.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(season, cache_dir)

    if path.exists():
        existing = pd.read_parquet(path)
        existing["date"] = pd.to_datetime(existing["date"])
        new_df = new_df.copy()
        new_df["date"] = pd.to_datetime(new_df["date"])
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["team", "date"], keep="last")
        combined = combined.sort_values(["date", "team"]).reset_index(drop=True)
    else:
        combined = new_df.copy()

    combined.to_parquet(path, index=False)
    logger.info(
        "Barttorvik cache updated: %d total ratings for season %d (%d dates)",
        len(combined),
        season,
        combined["date"].nunique() if "date" in combined.columns else 0,
    )
    return path


def load_cached_season(
    season: int,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> pd.DataFrame | None:
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
        """Initialize with API key from argument or CBBDATA_API_KEY env var."""
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
        self._session.headers.update(
            {
                "User-Agent": "sports-betting-research/1.0",
                "Accept": "application/octet-stream",
            }
        )
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

        # API returns Parquet format (application/octet-stream)
        df = parse_ratings_response(response.content, season)

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

    def fetch_daily_snapshot(
        self,
        season: int | None = None,
    ) -> pd.DataFrame:
        """Fetch today's ratings and append to season cache.

        Unlike fetch_season() which overwrites the cache, this method
        APPENDS new data so daily snapshots accumulate over time.
        This is critical for building point-in-time history for backtesting.

        Args:
            season: Season year. Defaults to current season
                (year if month >= 10, else year).

        Returns:
            DataFrame with today's snapshot (365 teams, 1 date).
        """
        if season is None:
            today = date.today()
            season = today.year if today.month >= 10 else today.year

        # Always fetch fresh (bypass cache)
        self._rate_limit()
        url = RATINGS_ENDPOINT
        params = {"year": season, "key": self._api_key}

        logger.info("Fetching daily Barttorvik snapshot for season %d...", season)
        response = self._session.get(url, params=params, timeout=60)
        self._last_request_time = time.time()

        if response.status_code != 200:
            response.raise_for_status()

        df = parse_ratings_response(response.content, season)

        if df.empty:
            logger.warning("Barttorvik returned empty for season %d", season)
            return df

        # Keep only today's snapshot (most recent date in response)
        df["date"] = pd.to_datetime(df["date"])
        latest_date = df["date"].max()
        today_df = df[df["date"] == latest_date].copy()

        # Append to existing cache (preserving historical snapshots)
        append_to_cache(today_df, season, self._cache_dir)

        logger.info(
            "Daily snapshot: %d teams for %s (season %d)",
            len(today_df),
            latest_date.strftime("%Y-%m-%d"),
            season,
        )
        return today_df

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


# ---------------------------------------------------------------------------
# DB Ingestion
# ---------------------------------------------------------------------------


def store_ratings_to_db(df: pd.DataFrame, db_path) -> int:
    """Insert/replace Barttorvik ratings into barttorvik_ratings table.

    Args:
        df: Ratings DataFrame (must have at least team, year/season, date columns).
        db_path: Path to the SQLite database (string or Path).

    Returns:
        Number of rows inserted.
    """
    import sqlite3 as _sqlite3

    COLUMN_MAP = {
        "team": "team",
        "conf": "conf",
        "year": "season",
        "date": "rating_date",
        "rank": "rank",
        "barthag": "barthag",
        "wab": "wab",
        "adj_o": "adj_o",
        "adj_d": "adj_d",
        "adj_tempo": "adj_tempo",
        "efg_o": "efg_o",
        "tov_o": "tov_o",
        "orb": "orb",
        "ftr_o": "ftr_o",
        "efg_d": "efg_d",
        "tov_d": "tov_d",
        "drb": "drb",
        "ftr_d": "ftr_d",
        "two_pt_o": "two_pt_o",
        "three_pt_o": "three_pt_o",
        "three_pt_rate_o": "three_pt_rate_o",
    }

    rows = []
    for _, row in df.iterrows():
        record: dict = {}
        for src_col, dst_col in COLUMN_MAP.items():
            val = row.get(src_col)
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                record[dst_col] = val
        if "team" in record and "season" in record and "rating_date" in record:
            if hasattr(record["rating_date"], "strftime"):
                record["rating_date"] = record["rating_date"].strftime("%Y-%m-%d")
            rows.append(record)

    if not rows:
        return 0

    cols = list(rows[0].keys())
    placeholders = ",".join("?" for _ in cols)
    col_str = ",".join(cols)
    sql = f"INSERT OR REPLACE INTO barttorvik_ratings ({col_str}) VALUES ({placeholders})"  # nosec B608

    conn = _sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executemany(sql, [tuple(r.get(c) for c in cols) for r in rows])
        conn.commit()
    finally:
        conn.close()

    return len(rows)
