"""KenPom Efficiency Rating Fetcher Pipeline.

Fetches adjusted efficiency ratings from kenpom.com using the kenpompy library.
Provides both season-level snapshots and current-day ratings. Data is cached
to parquet for fast repeated access.

All columns returned by kenpompy are preserved in the cache (currently 22+):
  Rk, Team, Conf, W-L, AdjEM, AdjO, AdjO.Rank, AdjD, AdjD.Rank,
  AdjT, AdjT.Rank, Luck, Luck.Rank, SOS-AdjEM, SOS-AdjEM.Rank,
  SOS-OppO, SOS-OppO.Rank, SOS-OppD, SOS-OppD.Rank,
  NCSOS-AdjEM, NCSOS-AdjEM.Rank, Seed

Columns are renamed to snake_case for consistency. Metadata columns
(year, date) are added. Downstream consumers select columns by name.

Usage:
    fetcher = KenPomFetcher("email@example.com", "password")
    df = fetcher.fetch_season_ratings(2025)
    ratings = lookup_team_ratings(df, "Houston", date(2025, 1, 15))
"""

from __future__ import annotations

import logging
import time
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_CACHE_DIR = Path("data/external/kenpom")

# Rate limiting
REQUEST_DELAY = 3.0  # seconds between requests

# Core columns used by downstream consumers (lookup, differentials, backtest).
# All kenpompy columns are preserved in the cache; this list is for reference only.
CORE_OUTPUT_COLUMNS = [
    "rank",
    "team",
    "conf",
    "adj_em",
    "adj_o",
    "adj_d",
    "adj_t",
    "sos_adj_em",
    "luck",
    "year",
    "date",
]

# Backward-compatible alias
OUTPUT_COLUMNS = CORE_OUTPUT_COLUMNS

# Mapping from raw kenpompy column names to snake_case.
# Any raw column NOT in this map is kept with its original name.
_RAW_TO_SNAKE = {
    "Rk": "rank",
    "Team": "team",
    "Conf": "conf",
    "W-L": "w_l",
    "AdjEM": "adj_em",
    "AdjO": "adj_o",
    "AdjO.Rank": "adj_o_rk",
    "AdjD": "adj_d",
    "AdjD.Rank": "adj_d_rk",
    "AdjT": "adj_t",
    "AdjT.Rank": "adj_t_rk",
    "Luck": "luck",
    "Luck.Rank": "luck_rk",
    "SOS-AdjEM": "sos_adj_em",
    "SOS-AdjEM.Rank": "sos_adj_em_rk",
    "SOS-OppO": "sos_opp_o",
    "SOS-OppO.Rank": "sos_opp_o_rk",
    "SOS-OppD": "sos_opp_d",
    "SOS-OppD.Rank": "sos_opp_d_rk",
    "NCSOS-AdjEM": "ncsos_adj_em",
    "NCSOS-AdjEM.Rank": "ncsos_adj_em_rk",
    "Seed": "seed",
}


# ---------------------------------------------------------------------------
# Response Normalization
# ---------------------------------------------------------------------------


def normalize_kenpom_df(raw_df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Normalize kenpompy output: rename columns to snake_case, coerce types.

    Preserves ALL columns from the raw kenpompy response. Adds ``year``
    and ``date`` metadata columns.

    Args:
        raw_df: DataFrame from kenpompy get_pomeroy_ratings().
        year: Season year.

    Returns:
        DataFrame with all columns renamed to snake_case plus year/date.
    """
    if raw_df.empty:
        return pd.DataFrame(columns=CORE_OUTPUT_COLUMNS)

    # Rename known columns to snake_case; keep unknown columns as-is
    rename_map = {k: v for k, v in _RAW_TO_SNAKE.items() if k in raw_df.columns}
    df = raw_df.rename(columns=rename_map).copy()

    # Strip whitespace on string identity columns
    if "team" in df.columns:
        df["team"] = df["team"].astype(str).str.strip()
    if "conf" in df.columns:
        df["conf"] = df["conf"].astype(str).str.strip()

    # Coerce numeric columns — some may have "+" prefix
    _plus_strip_cols = {"adj_em", "sos_adj_em", "luck", "ncsos_adj_em"}
    for col in df.columns:
        if col in ("team", "conf", "w_l", "seed"):
            continue
        if col in _plus_strip_cols:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace("+", "", regex=False),
                errors="coerce",
            )
        elif col == "rank" or col.endswith("_rk"):
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
        else:
            # Try numeric coercion; leave non-numeric columns unchanged
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notna().any():
                df[col] = converted

    # Add metadata
    df["year"] = year
    df["date"] = pd.Timestamp(date.today())

    logger.info(
        "Normalized %d rows, %d columns for season %d",
        len(df),
        len(df.columns),
        year,
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
    """Look up a team's most recent KenPom ratings on or before a given date.

    For point-in-time safety in backtesting: only uses ratings published
    on or before the game date.

    Args:
        ratings_df: Season ratings DataFrame (must have 'team', 'date' cols).
        team: Team name (must match KenPom naming).
        game_date: Game date -- ratings on or before this date are considered.

    Returns:
        Dict with rating fields, or None if no data available.
    """
    if ratings_df.empty:
        return None

    if not pd.api.types.is_datetime64_any_dtype(ratings_df["date"]):
        ratings_df = ratings_df.copy()
        ratings_df["date"] = pd.to_datetime(ratings_df["date"])

    game_dt = pd.Timestamp(game_date)
    mask = (ratings_df["team"] == team) & (ratings_df["date"] <= game_dt)
    team_ratings = ratings_df.loc[mask]

    if team_ratings.empty:
        return None

    latest = team_ratings.loc[team_ratings["date"].idxmax()]
    return latest.to_dict()


# ---------------------------------------------------------------------------
# Matchup Differentials
# ---------------------------------------------------------------------------


def compute_kenpom_differentials(
    ratings_df: pd.DataFrame,
    home_team: str,
    away_team: str,
    game_date: date,
) -> dict[str, float] | None:
    """Compute KenPom rating differentials for a matchup.

    Returns home - away differences for each metric.

    Args:
        ratings_df: Season ratings DataFrame.
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

    for col in ("adj_em", "adj_o", "adj_d", "adj_t", "sos_adj_em"):
        h_val = home_ratings.get(col)
        a_val = away_ratings.get(col)
        if h_val is not None and a_val is not None:
            diffs[f"{col}_diff"] = float(h_val) - float(a_val)

    return diffs


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------


def _cache_path(season: int, cache_dir: Path) -> Path:
    """Return the parquet cache file path for a season."""
    return cache_dir / f"kenpom_ratings_{season}.parquet"


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
    logger.info("Cached %d KenPom ratings for season %d to %s", len(df), season, path)
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
    logger.info("Loaded %d cached KenPom ratings for season %d", len(df), season)
    return df


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
        new_df["date"] = pd.to_datetime(new_df["date"])
        combined = pd.concat([existing, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["team", "date"], keep="last")
        combined = combined.sort_values(["date", "team"]).reset_index(drop=True)
    else:
        combined = new_df.copy()

    combined.to_parquet(path, index=False)
    logger.info("KenPom cache updated: %d total ratings for season %d", len(combined), season)
    return path


# ---------------------------------------------------------------------------
# Fetcher Class
# ---------------------------------------------------------------------------


class KenPomFetcher:
    """Fetches KenPom efficiency ratings via kenpompy.

    Requires a KenPom subscription ($25/year). Uses kenpompy library
    which wraps kenpom.com scraping with cloudscraper.

    Args:
        email: KenPom login email.
        password: KenPom login password.
        cache_dir: Directory for parquet cache files.
        request_delay: Seconds between requests.
    """

    def __init__(
        self,
        email: str,
        password: str,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        request_delay: float = REQUEST_DELAY,
    ) -> None:
        """Initialize KenPom fetcher with credentials and cache settings."""
        self._email = email
        self._password = password
        self._cache_dir = cache_dir
        self._request_delay = request_delay
        self._browser = None
        self._last_request_time = 0.0

    def _login(self) -> None:
        """Authenticate with KenPom."""
        if self._browser is not None:
            return

        try:
            from kenpompy.utils import login
        except ImportError:
            raise ImportError("kenpompy not installed. Run: pip install kenpompy")

        logger.info("Logging in to KenPom...")
        self._browser = login(self._email, self._password)
        logger.info("KenPom login successful")

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            time.sleep(self._request_delay - elapsed)

    def fetch_season_ratings(
        self,
        season: int,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch end-of-season (or current) ratings for a season.

        For completed seasons, returns the final ratings.
        For the current season, returns today's ratings.

        Args:
            season: Season year (e.g., 2025 = 2024-25 season).
            use_cache: If True, check cache before fetching.

        Returns:
            DataFrame with normalized KenPom ratings.
        """
        if use_cache:
            cached = load_cached_season(season, self._cache_dir)
            if cached is not None:
                return cached

        self._login()
        self._rate_limit()

        try:
            from kenpompy.misc import get_pomeroy_ratings
        except ImportError:
            raise ImportError("kenpompy not installed. Run: pip install kenpompy")

        logger.info("Fetching KenPom ratings for season %d...", season)
        raw_df = get_pomeroy_ratings(self._browser, season=str(season))
        self._last_request_time = time.time()

        if raw_df is None or raw_df.empty:
            logger.warning("KenPom returned empty data for season %d", season)
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        df = normalize_kenpom_df(raw_df, season)

        if not df.empty:
            save_season_cache(df, season, self._cache_dir)

        logger.info(
            "Fetched %d KenPom ratings for season %d (%d teams)",
            len(df),
            season,
            df["team"].nunique() if "team" in df.columns else 0,
        )
        return df

    def fetch_current_snapshot(self) -> pd.DataFrame:
        """Fetch today's ratings for the current season.

        Returns:
            DataFrame with today's ratings, appended to current season cache.
        """
        self._login()
        self._rate_limit()

        try:
            from kenpompy.misc import get_pomeroy_ratings, get_current_season
        except ImportError:
            raise ImportError("kenpompy not installed. Run: pip install kenpompy")

        try:
            current_season = int(get_current_season(self._browser))
        except Exception:
            current_season = date.today().year

        logger.info("Fetching current KenPom snapshot (season %d)...", current_season)
        raw_df = get_pomeroy_ratings(self._browser)
        self._last_request_time = time.time()

        if raw_df is None or raw_df.empty:
            logger.warning("KenPom returned empty for current season")
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        df = normalize_kenpom_df(raw_df, current_season)

        if not df.empty:
            append_to_cache(df, current_season, self._cache_dir)

        return df

    def fetch_all_seasons(
        self,
        seasons: list[int] | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch ratings for multiple seasons and combine.

        Args:
            seasons: List of season years. Defaults to 2020-2026.
            use_cache: Check cache before fetching.

        Returns:
            Combined DataFrame for all seasons.
        """
        if seasons is None:
            seasons = [2020, 2021, 2022, 2023, 2024, 2025, 2026]

        all_dfs = []
        for season in seasons:
            try:
                df = self.fetch_season_ratings(season, use_cache=use_cache)
                if not df.empty:
                    all_dfs.append(df)
                    logger.info("KenPom season %d: %d ratings", season, len(df))
            except Exception as exc:
                logger.error("Failed to fetch KenPom season %d: %s", season, exc)
                continue

        if not all_dfs:
            return pd.DataFrame(columns=OUTPUT_COLUMNS)

        combined = pd.concat(all_dfs, ignore_index=True)
        logger.info(
            "KenPom total: %d ratings across %d seasons",
            len(combined),
            len(all_dfs),
        )
        return combined
