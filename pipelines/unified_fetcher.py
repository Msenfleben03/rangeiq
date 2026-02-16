"""Unified NCAAB Data Fetcher — Scores + Odds in One Pass.

Combines ESPN Site API (scores) and ESPN Core API (odds) into a single
pipeline so data is always training-ready without a separate backfill step.

Modes:
    - Full season: Fetch all games + odds for a season
    - Incremental: Only fetch games not already in the parquet

Output:
    - data/raw/ncaab/ncaab_games_{season}.parquet  (enriched with best-provider odds)
    - data/odds/ncaab_odds_{season}.parquet         (all providers, full detail)

Usage:
    from pipelines.unified_fetcher import UnifiedNCAABFetcher
    fetcher = UnifiedNCAABFetcher()
    df = fetcher.fetch_season(2025)             # full season
    df = fetcher.fetch_season(2025, incremental=True)  # only new games
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd

from pipelines.espn_core_odds_provider import ESPNCoreOddsFetcher, OddsSnapshot
from pipelines.espn_ncaab_fetcher import ESPNDataFetcher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RAW_DATA_DIR = Path("data/raw/ncaab")
ODDS_DATA_DIR = Path("data/odds")
CHECKPOINT_DIR = Path("data/odds/checkpoints")

# Games that returned empty odds — skip in future runs to save requests
SKIP_LIST_DIR = Path("data/odds/skip_lists")

# Best-provider odds columns appended to the enriched scores parquet
ODDS_COLUMNS = [
    "spread",
    "over_under",
    "home_moneyline",
    "away_moneyline",
    "home_spread_odds",
    "away_spread_odds",
    "over_odds",
    "under_odds",
    "home_spread_open",
    "away_spread_open",
    "home_ml_open",
    "away_ml_open",
    "total_open",
    "home_spread_close",
    "away_spread_close",
    "home_ml_close",
    "away_ml_close",
    "total_close",
    "odds_provider",
]


# ---------------------------------------------------------------------------
# Skip list management
# ---------------------------------------------------------------------------


def _load_skip_list(season: int) -> set[str]:
    """Load game IDs known to have no odds.

    Args:
        season: Season year.

    Returns:
        Set of game IDs to skip when fetching odds.
    """
    path = SKIP_LIST_DIR / f"no_odds_{season}.txt"
    if not path.exists():
        return set()
    with open(path, encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _save_skip_list(season: int, game_ids: set[str]) -> None:
    """Save game IDs that returned no odds.

    Args:
        season: Season year.
        game_ids: Set of game IDs with no odds.
    """
    SKIP_LIST_DIR.mkdir(parents=True, exist_ok=True)
    path = SKIP_LIST_DIR / f"no_odds_{season}.txt"
    with open(path, "w", encoding="utf-8") as f:
        for gid in sorted(game_ids):
            f.write(f"{gid}\n")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pick_best_provider(snapshots: list[OddsSnapshot]) -> Optional[OddsSnapshot]:
    """Select the best odds provider from a list.

    Priority: pre-game providers (not live ID 59), prefer close data present.

    Args:
        snapshots: List of OddsSnapshot from all providers.

    Returns:
        Best OddsSnapshot, or None if empty.
    """
    if not snapshots:
        return None

    # Filter out live-odds provider (ID 59)
    pre_game = [s for s in snapshots if s.provider_id != 59]
    if not pre_game:
        pre_game = snapshots

    # Prefer one with closing moneyline data
    with_close = [s for s in pre_game if s.home_ml_close is not None]
    if with_close:
        return with_close[0]

    return pre_game[0]


def _snapshot_to_flat_dict(snap: Optional[OddsSnapshot]) -> dict:
    """Convert OddsSnapshot to flat dict matching ODDS_COLUMNS.

    Args:
        snap: OddsSnapshot or None.

    Returns:
        Dict with odds column values (None-filled if snap is None).
    """
    if snap is None:
        return {col: None for col in ODDS_COLUMNS}

    return {
        "spread": snap.spread,
        "over_under": snap.over_under,
        "home_moneyline": snap.home_moneyline,
        "away_moneyline": snap.away_moneyline,
        "home_spread_odds": snap.home_spread_odds,
        "away_spread_odds": snap.away_spread_odds,
        "over_odds": snap.over_odds,
        "under_odds": snap.under_odds,
        "home_spread_open": snap.home_spread_open,
        "away_spread_open": snap.away_spread_open,
        "home_ml_open": snap.home_ml_open,
        "away_ml_open": snap.away_ml_open,
        "total_open": snap.total_open,
        "home_spread_close": snap.home_spread_close,
        "away_spread_close": snap.away_spread_close,
        "home_ml_close": snap.home_ml_close,
        "away_ml_close": snap.away_ml_close,
        "total_close": snap.total_close,
        "odds_provider": snap.provider_name,
    }


def _snapshots_to_dataframe(
    results: dict[str, list[OddsSnapshot]],
) -> pd.DataFrame:
    """Convert bulk odds results to flat DataFrame.

    Args:
        results: Dict mapping event_id to list of OddsSnapshot.

    Returns:
        DataFrame with one row per (event_id, provider).
    """
    rows = []
    for snapshots in results.values():
        for snap in snapshots:
            rows.append(snap.to_dict())
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Unified fetcher
# ---------------------------------------------------------------------------


class UnifiedNCAABFetcher:
    """Fetches NCAAB scores and odds in a single pass.

    Combines ESPNDataFetcher (scores) and ESPNCoreOddsFetcher (odds)
    so every game is enriched with market data immediately.

    Args:
        raw_dir: Directory for enriched game parquets.
        odds_dir: Directory for raw odds parquets.
        score_delay: Seconds between score requests.
        odds_rate: Odds API requests per second.
    """

    def __init__(
        self,
        raw_dir: str = "data/raw/ncaab",
        odds_dir: str = "data/odds",
        score_delay: float = 0.3,
        odds_rate: float = 2.0,
    ) -> None:
        """Initialize unified fetcher with score and odds sub-fetchers.

        Args:
            raw_dir: Directory for enriched game parquets.
            odds_dir: Directory for raw odds parquets.
            score_delay: Seconds between score requests.
            odds_rate: Odds API requests per second.
        """
        self._raw_dir = Path(raw_dir)
        self._odds_dir = Path(odds_dir)
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        self._odds_dir.mkdir(parents=True, exist_ok=True)

        self._score_fetcher = ESPNDataFetcher(
            output_dir=str(self._raw_dir),
            delay=score_delay,
        )
        self._odds_rate = odds_rate
        self._odds_fetcher: Optional[ESPNCoreOddsFetcher] = None

    def _get_odds_fetcher(self) -> ESPNCoreOddsFetcher:
        """Lazy-init the odds fetcher to avoid session overhead if unused."""
        if self._odds_fetcher is None:
            self._odds_fetcher = ESPNCoreOddsFetcher(
                sport="ncaab",
                requests_per_second=self._odds_rate,
            )
        return self._odds_fetcher

    def fetch_season(
        self,
        season: int,
        with_odds: bool = True,
        incremental: bool = False,
        force: bool = False,
        use_skip_list: bool = True,
    ) -> pd.DataFrame:
        """Fetch a complete season of scores + odds.

        Args:
            season: Season year (e.g. 2025 for 2024-25).
            with_odds: If True, fetch odds for each game.
            incremental: If True, only fetch games not in existing parquet.
            force: If True, re-fetch everything (ignore cache/checkpoints).
            use_skip_list: If True, skip games known to have no odds.

        Returns:
            Enriched DataFrame with scores and odds columns.
        """
        games_path = self._raw_dir / f"ncaab_games_{season}.parquet"

        # ----- Step 1: Scores -----
        existing_game_ids: set[str] = set()
        if incremental and games_path.exists() and not force:
            existing_df = pd.read_parquet(games_path)
            existing_game_ids = set(existing_df["game_id"].astype(str).unique())
            logger.info(
                "Incremental mode: %d existing games for season %d",
                len(existing_game_ids),
                season,
            )

        if force or not games_path.exists():
            logger.info("Fetching full season %d scores...", season)
            scores_df = self._score_fetcher.fetch_season_data(season)
        elif incremental:
            # Re-fetch scores to discover new games
            logger.info("Fetching season %d scores for incremental update...", season)
            scores_df = self._score_fetcher.fetch_season_data(season)
        else:
            # Scores already exist, just load
            logger.info("Loading cached scores for season %d", season)
            scores_df = pd.read_parquet(games_path)

        if scores_df.empty:
            logger.error("No scores for season %d", season)
            return scores_df

        # Identify new games (for incremental mode)
        all_game_ids = set(scores_df["game_id"].astype(str).unique())
        new_game_ids = all_game_ids - existing_game_ids if incremental else all_game_ids

        logger.info(
            "Season %d: %d total games, %d new to process",
            season,
            len(all_game_ids),
            len(new_game_ids),
        )

        # ----- Step 2: Odds -----
        if not with_odds or not new_game_ids:
            # Ensure odds columns exist even without fetching
            for col in ODDS_COLUMNS:
                if col not in scores_df.columns:
                    scores_df[col] = None
            return scores_df

        # Load skip list
        skip_ids: set[str] = set()
        if use_skip_list and not force:
            skip_ids = _load_skip_list(season)
            if skip_ids:
                logger.info("Skip list: %d games known to have no odds", len(skip_ids))

        # Filter to games that need odds
        ids_to_fetch = sorted(new_game_ids - skip_ids)

        # Also skip games that already have odds in the dataframe
        if incremental and games_path.exists():
            existing_df = pd.read_parquet(games_path)
            if "home_moneyline" in existing_df.columns:
                has_odds = set(
                    existing_df.loc[existing_df["home_moneyline"].notna(), "game_id"]
                    .astype(str)
                    .unique()
                )
                ids_to_fetch = [gid for gid in ids_to_fetch if gid not in has_odds]

        logger.info(
            "Fetching odds for %d games (skipping %d known-empty, %d already have odds)",
            len(ids_to_fetch),
            len(skip_ids & new_game_ids),
            len(new_game_ids) - len(ids_to_fetch) - len(skip_ids & new_game_ids),
        )

        # Fetch odds
        odds_fetcher = self._get_odds_fetcher()
        all_odds: dict[str, list[OddsSnapshot]] = {}
        new_empty_ids: set[str] = set()

        start_time = time.time()
        for idx, gid in enumerate(ids_to_fetch):
            snapshots = odds_fetcher.fetch_game_odds(gid)
            if snapshots:
                all_odds[gid] = snapshots
            else:
                new_empty_ids.add(gid)

            # Progress logging
            done = idx + 1
            if done % 50 == 0 or done == len(ids_to_fetch):
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                eta = (len(ids_to_fetch) - done) / rate if rate > 0 else 0
                logger.info(
                    "Odds progress: %d/%d (%.0f%%) | "
                    "found: %d | empty: %d | "
                    "%.1f games/s | ETA: %.0fs",
                    done,
                    len(ids_to_fetch),
                    100 * done / len(ids_to_fetch),
                    len(all_odds),
                    len(new_empty_ids),
                    rate,
                    eta,
                )

        # Update skip list
        if new_empty_ids:
            updated_skip = skip_ids | new_empty_ids
            _save_skip_list(season, updated_skip)
            logger.info(
                "Updated skip list: %d -> %d entries",
                len(skip_ids),
                len(updated_skip),
            )

        # ----- Step 3: Save raw odds parquet -----
        if all_odds:
            raw_odds_df = _snapshots_to_dataframe(all_odds)
            odds_path = self._odds_dir / f"ncaab_odds_{season}.parquet"

            if odds_path.exists():
                existing_odds = pd.read_parquet(odds_path)
                raw_odds_df = pd.concat([existing_odds, raw_odds_df], ignore_index=True)
                raw_odds_df = raw_odds_df.drop_duplicates(
                    subset=["game_id", "provider_id"], keep="last"
                )

            raw_odds_df.to_parquet(odds_path, index=False)
            logger.info("Saved %d raw odds records to %s", len(raw_odds_df), odds_path)

        # ----- Step 4: Enrich scores with best-provider odds -----
        odds_rows: list[dict] = []
        for gid in all_game_ids:
            gid_str = str(gid)
            if gid_str in all_odds:
                best = _pick_best_provider(all_odds[gid_str])
                odds_rows.append({"game_id": gid_str, **_snapshot_to_flat_dict(best)})
            else:
                odds_rows.append({"game_id": gid_str, **_snapshot_to_flat_dict(None)})

        odds_merge_df = pd.DataFrame(odds_rows)

        # Drop existing odds columns from scores to avoid conflicts
        drop_cols = [c for c in ODDS_COLUMNS if c in scores_df.columns]
        if drop_cols:
            scores_df = scores_df.drop(columns=drop_cols)

        # Merge odds into scores
        scores_df["game_id"] = scores_df["game_id"].astype(str)
        enriched_df = scores_df.merge(odds_merge_df, on="game_id", how="left")

        # If incremental, merge with existing data
        if incremental and games_path.exists():
            existing_df = pd.read_parquet(games_path)
            # Ensure existing has all columns
            for col in ODDS_COLUMNS:
                if col not in existing_df.columns:
                    existing_df[col] = None
            existing_df["game_id"] = existing_df["game_id"].astype(str)

            # Replace updated rows, keep existing for untouched games
            enriched_df = pd.concat([existing_df, enriched_df], ignore_index=True)
            enriched_df = enriched_df.drop_duplicates(subset=["game_id"], keep="last")

        # Save enriched parquet
        enriched_df.to_parquet(games_path, index=False)

        # ----- Step 5: Summary -----
        n_with_odds = enriched_df["home_moneyline"].notna().sum()
        n_total = len(enriched_df)
        logger.info(
            "Season %d complete: %d games, %d with odds (%.0f%% coverage)",
            season,
            n_total,
            n_with_odds,
            100 * n_with_odds / n_total if n_total > 0 else 0,
        )

        return enriched_df

    def close(self) -> None:
        """Release resources."""
        if self._odds_fetcher is not None:
            self._odds_fetcher.close()
            self._odds_fetcher = None
