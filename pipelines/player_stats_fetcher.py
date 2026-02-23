"""Player Stats Fetcher Pipeline.

Fetches player-level season stats from the cbbdata.com REST API.
Provides per-player data including USG%, DBPM, position, and minutes
for computing breadwinner concentration metrics.

The API returns Apache Parquet format. Data is cached to parquet files
per season for fast repeated access.

Usage:
    fetcher = PlayerStatsFetcher(api_key="your_key")
    df = fetcher.fetch_season(2025)
    rotation = get_team_rotation(df, "Houston", rotation_size=8)
"""

from __future__ import annotations

import io
import logging
import os
import time
from pathlib import Path

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CBBDATA_BASE_URL = "https://www.cbbdata.com/api"
PLAYER_SEASON_ENDPOINT = f"{CBBDATA_BASE_URL}/torvik/player/season"
DEFAULT_CACHE_DIR = Path("data/external/barttorvik")

# Columns we need for breadwinner metric
PLAYER_COLUMNS = [
    "player",
    "pos",
    "team",
    "conf",
    "g",
    "min",
    "mpg",
    "usg",
    "dbpm",
    "obpm",
    "bpm",
    "spg",
    "bpg",
    "stl",
    "blk",
    "stops",
    "drtg",
    "adj_de",
    "year",
]

# Rate limiting
REQUEST_DELAY = 1.0  # seconds between requests

# Center positions
CENTER_POSITIONS = frozenset({"C", "PF/C"})


# ---------------------------------------------------------------------------
# Response Parsing
# ---------------------------------------------------------------------------


def parse_player_response(data: bytes, season: int) -> pd.DataFrame:
    """Parse raw API Parquet response into a clean player DataFrame.

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
        logger.warning("Failed to parse player Parquet for season %d", season)
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    # Keep only columns we need (API may return extras)
    available = [c for c in PLAYER_COLUMNS if c in df.columns]
    df = df[available].copy()

    # Coerce numeric types
    numeric_cols = [
        "g",
        "min",
        "mpg",
        "usg",
        "dbpm",
        "obpm",
        "bpm",
        "spg",
        "bpg",
        "stl",
        "blk",
        "stops",
        "drtg",
        "adj_de",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "year" not in df.columns:
        df["year"] = season

    # Sort by team then USG% descending for consistent ordering
    if "team" in df.columns and "usg" in df.columns:
        df = df.sort_values(["team", "usg"], ascending=[True, False])
        df = df.reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# Team Rotation Extraction
# ---------------------------------------------------------------------------


def get_team_rotation(
    player_df: pd.DataFrame,
    team: str,
    rotation_size: int = 8,
    min_minutes: float = 0.0,
) -> pd.DataFrame:
    """Get a team's rotation players sorted by minutes.

    Args:
        player_df: Full season player DataFrame.
        team: Team name (must match Barttorvik naming).
        rotation_size: Max number of players to include.
        min_minutes: Minimum minutes per game to qualify.

    Returns:
        DataFrame of rotation players sorted by minutes descending.
    """
    if player_df.empty or "team" not in player_df.columns:
        return pd.DataFrame()

    team_players = player_df[player_df["team"] == team].copy()
    if team_players.empty:
        return pd.DataFrame()

    # Filter by minimum minutes
    if min_minutes > 0 and "mpg" in team_players.columns:
        team_players = team_players[team_players["mpg"] >= min_minutes]

    # Take top N by minutes
    if "mpg" in team_players.columns:
        team_players = team_players.nlargest(rotation_size, "mpg")
    elif "min" in team_players.columns:
        team_players = team_players.nlargest(rotation_size, "min")

    return team_players.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Cache Management
# ---------------------------------------------------------------------------


def _cache_path(season: int, cache_dir: Path) -> Path:
    """Return the parquet cache file path for a season."""
    return cache_dir / f"player_stats_{season}.parquet"


def save_player_cache(
    df: pd.DataFrame,
    season: int,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Path:
    """Save season player stats to parquet cache.

    Args:
        df: Player stats DataFrame.
        season: Season year.
        cache_dir: Cache directory path.

    Returns:
        Path to the saved file.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = _cache_path(season, cache_dir)
    df.to_parquet(path, index=False)
    logger.info("Cached %d player records for season %d to %s", len(df), season, path)
    return path


def load_cached_players(
    season: int,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> pd.DataFrame | None:
    """Load cached player stats from parquet.

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
    logger.info("Loaded %d cached player records for season %d", len(df), season)
    return df


# ---------------------------------------------------------------------------
# Fetcher Class
# ---------------------------------------------------------------------------


class PlayerStatsFetcher:
    """Fetches player season stats from cbbdata.com API.

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
            api_key = os.environ.get("CBBDATA_API_KEY", "")
        if not api_key:
            raise ValueError(
                "API key required. Set CBBDATA_API_KEY environment variable "
                "or pass api_key parameter."
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
        """Fetch all player season stats for a year.

        Args:
            season: Season year (e.g. 2025 = 2024-25 season).
            use_cache: If True, check cache before hitting API.

        Returns:
            DataFrame with player season stats.

        Raises:
            Exception: If API request fails.
        """
        if use_cache:
            cached = load_cached_players(season, self._cache_dir)
            if cached is not None:
                return cached

        self._rate_limit()
        params = {"year": season, "key": self._api_key}

        logger.info("Fetching player stats for season %d...", season)
        response = self._session.get(PLAYER_SEASON_ENDPOINT, params=params, timeout=60)
        self._last_request_time = time.time()

        if response.status_code != 200:
            response.raise_for_status()

        df = parse_player_response(response.content, season)

        if not df.empty:
            save_player_cache(df, season, self._cache_dir)

        logger.info(
            "Fetched %d players for season %d (%d teams)",
            len(df),
            season,
            df["team"].nunique() if "team" in df.columns else 0,
        )
        return df

    def fetch_all_seasons(
        self,
        seasons: list[int] | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch player stats for multiple seasons.

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
                    logger.info("Season %d: %d players", season, len(df))
            except Exception as exc:
                logger.error("Failed to fetch player stats for %d: %s", season, exc)
                continue

        if not all_dfs:
            return pd.DataFrame()

        combined = pd.concat(all_dfs, ignore_index=True)
        logger.info(
            "Total: %d player records across %d seasons",
            len(combined),
            len(all_dfs),
        )
        return combined

    def close(self) -> None:
        """Close the HTTP session."""
        self._session.close()
