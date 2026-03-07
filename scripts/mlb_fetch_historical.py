"""Bulk historical data fetcher for MLB backtesting (2023-2025).

Pulls game results + pitcher season stats for walk-forward backtesting:
    - Game schedule and results from MLB Stats API (by month, with checkpointing)
    - Starter player records discovered from schedule data
    - Season pitcher stats from FanGraphs via pybaseball

Skipped for Phase 1 (Phase 2 additions):
    - Statcast per-pitch game logs (too slow for bulk historical)
    - Historical weather (Open-Meteo archive API)
    - Bullpen usage logs (retroactive from boxscores)

Usage:
    python scripts/mlb_fetch_historical.py --seasons 2023 2024 2025
    python scripts/mlb_fetch_historical.py --seasons 2025 --incremental
    python scripts/mlb_fetch_historical.py --seasons 2023 --games-only
    python scripts/mlb_fetch_historical.py --seasons 2024 --stats-only

Run mlb_init_db.py --seed-teams first to create the schema.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sqlite3
import sys
import time
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Generator, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import MLB_DATABASE_PATH as DEFAULT_DB_PATH

CHECKPOINT_PATH = BASE_DIR / "data" / "mlb_historical_checkpoint.json"

# Season date ranges (inclusive, covers regular season + playoffs)
SEASON_RANGES: dict[int, tuple[str, str]] = {
    2023: ("2023-03-30", "2023-11-05"),
    2024: ("2024-03-20", "2024-11-02"),
    2025: ("2025-03-27", "2025-10-31"),
}

# Statuses that indicate a completed game
FINAL_STATUSES = frozenset({"Final", "Game Over", "Completed Early", "Final: Suspended"})

# MLBAM team IDs seeded in the teams table (from mlb_init_db.py)
VALID_TEAM_IDS = frozenset(
    {
        108,
        109,
        110,
        111,
        112,
        113,
        114,
        115,
        116,
        117,
        118,
        119,
        120,
        121,
        133,
        134,
        135,
        136,
        137,
        138,
        139,
        140,
        141,
        142,
        143,
        144,
        145,
        146,
        147,
        158,
    }
)

try:
    import statsapi  # type: ignore[import-untyped]

    _HAS_STATSAPI = True
except ImportError:
    _HAS_STATSAPI = False

try:
    import pybaseball  # type: ignore[import-untyped]

    _HAS_PYBASEBALL = True
except ImportError:
    _HAS_PYBASEBALL = False


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------


def load_checkpoint() -> dict:
    """Load checkpoint from disk, or return empty dict."""
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(checkpoint: dict) -> None:
    """Persist checkpoint to disk atomically."""
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(checkpoint, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


@contextmanager
def get_conn(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """SQLite connection context manager with WAL + FK support."""
    conn = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Month iteration
# ---------------------------------------------------------------------------


def month_ranges(start_str: str, end_str: str) -> Generator[tuple[str, str], None, None]:
    """Yield (start, end) date strings for each calendar month in [start, end]."""
    start = datetime.strptime(start_str, "%Y-%m-%d").date()
    end = datetime.strptime(end_str, "%Y-%m-%d").date()
    current = start
    while current <= end:
        if current.month == 12:
            next_month = date(current.year + 1, 1, 1)
        else:
            next_month = date(current.year, current.month + 1, 1)
        month_end = min(next_month - timedelta(days=1), end)
        yield current.strftime("%Y-%m-%d"), month_end.strftime("%Y-%m-%d")
        current = next_month


# ---------------------------------------------------------------------------
# Status normalization
# ---------------------------------------------------------------------------


def normalize_status(raw: str) -> str:
    """Normalize MLB API status string to schema values."""
    lower = raw.lower()
    if "final" in lower or "game over" in lower or "completed" in lower:
        return "final"
    if "postponed" in lower:
        return "postponed"
    if "cancelled" in lower:
        return "cancelled"
    if "suspended" in lower:
        return "cancelled"
    return "scheduled"


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------


def upsert_players(player_records: dict[int, str], db_path: Path) -> None:
    """Insert player stubs (player_id → name). INSERT OR IGNORE — safe to re-run.

    Sets position='SP' for all starters discovered from schedule data.
    """
    if not player_records:
        return
    rows = [(pid, name, "SP") for pid, name in player_records.items()]
    with get_conn(db_path) as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO players (player_id, full_name, position) VALUES (?,?,?)",
            rows,
        )


# ---------------------------------------------------------------------------
# Game parsing and insertion
# ---------------------------------------------------------------------------


def parse_schedule_games(
    raw_games: list[dict[str, Any]],
    valid_team_ids: set[int],
    season: int,
) -> tuple[list[dict], dict[int, str]]:
    """Parse statsapi.schedule() output into (game_dicts, starter_records).

    Filters to games where both teams are in valid_team_ids (MLB teams only,
    excludes spring training and minor league exhibition games).

    Returns:
        games: List of game dicts ready for DB insertion.
        starters: Dict of player_id → name for players table insertion.
    """
    games: list[dict] = []
    starters: dict[int, str] = {}

    for g in raw_games:
        try:
            home_id = int(g.get("home_id") or 0)
            away_id = int(g.get("away_id") or 0)

            # Skip spring training, minors, or unknown teams
            if home_id not in valid_team_ids or away_id not in valid_team_ids:
                continue
            if home_id == 0 or away_id == 0:
                continue

            game_pk = int(g["game_id"])
            game_date_str = g.get("game_date", "")
            status_raw = g.get("status", "")

            # Collect starter IDs + names for players table (FK prerequisite)
            home_starter_id: Optional[int] = None
            away_starter_id: Optional[int] = None

            prob_home = g.get("home_probable_pitcher_id")
            if prob_home and int(prob_home) > 0:
                home_starter_id = int(prob_home)
                name = g.get("home_probable_pitcher") or f"Player {home_starter_id}"
                starters[home_starter_id] = name

            prob_away = g.get("away_probable_pitcher_id")
            if prob_away and int(prob_away) > 0:
                away_starter_id = int(prob_away)
                name = g.get("away_probable_pitcher") or f"Player {away_starter_id}"
                starters[away_starter_id] = name

            home_score_raw = g.get("home_score")
            away_score_raw = g.get("away_score")

            games.append(
                {
                    "game_pk": game_pk,
                    "game_date": game_date_str,
                    "season": season,
                    "home_team_id": home_id,
                    "away_team_id": away_id,
                    "home_score": int(home_score_raw) if home_score_raw is not None else None,
                    "away_score": int(away_score_raw) if away_score_raw is not None else None,
                    "status": normalize_status(status_raw),
                    "home_starter_id": home_starter_id,
                    "away_starter_id": away_starter_id,
                    "venue": g.get("venue_name"),
                    "game_time_utc": g.get("game_datetime"),
                }
            )
        except Exception as exc:
            logger.warning("Failed to parse game %s: %s", g.get("game_id"), exc)

    return games, starters


def upsert_games(games: list[dict], db_path: Path) -> int:
    """Insert or replace game records. Returns number of rows upserted."""
    if not games:
        return 0

    rows = [
        (
            g["game_pk"],
            g["game_date"],
            g["season"],
            g["home_team_id"],
            g["away_team_id"],
            g.get("home_score"),
            g.get("away_score"),
            g.get("status", "scheduled"),
            g.get("home_starter_id"),
            g.get("away_starter_id"),
            g.get("venue"),
            g.get("game_time_utc"),
        )
        for g in games
    ]

    with get_conn(db_path) as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO games
               (game_pk, game_date, season, home_team_id, away_team_id,
                home_score, away_score, status, home_starter_id, away_starter_id,
                venue, game_time_utc, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
            rows,
        )

    return len(rows)


# ---------------------------------------------------------------------------
# Season game fetch (month by month with checkpointing)
# ---------------------------------------------------------------------------


def fetch_season_games(
    season: int,
    db_path: Path,
    checkpoint: dict,
    request_delay: float = 0.5,
) -> int:
    """Fetch all games for one season from MLB Stats API, month by month.

    Saves checkpoint after each month so it can resume if interrupted.
    Returns total games upserted.
    """
    if not _HAS_STATSAPI:
        logger.error("MLB-StatsAPI not installed — run: pip install MLB-StatsAPI")
        return 0

    season_key = str(season)
    season_cp = checkpoint.setdefault(season_key, {})
    completed_months: set[str] = set(season_cp.get("completed_months", []))
    total_games = season_cp.get("game_count", 0)

    start_str, end_str = SEASON_RANGES[season]
    logger.info("Season %d: fetching games %s → %s", season, start_str, end_str)

    for month_start, month_end in month_ranges(start_str, end_str):
        month_key = month_start[:7]  # "YYYY-MM"
        if month_key in completed_months:
            logger.info("  [skip] %s — already fetched", month_key)
            continue

        logger.info("  Fetching %s → %s ...", month_start, month_end)
        try:
            raw = statsapi.schedule(start_date=month_start, end_date=month_end, sportId=1)
        except Exception as exc:
            logger.error("  statsapi.schedule() failed for %s: %s", month_key, exc)
            time.sleep(request_delay * 4)
            continue
        time.sleep(request_delay)

        games, starters = parse_schedule_games(raw, VALID_TEAM_IDS, season)

        # Players MUST be inserted before games (FK constraint on starter IDs)
        upsert_players(starters, db_path)

        n = upsert_games(games, db_path)
        total_games += n

        completed_months.add(month_key)
        season_cp["completed_months"] = sorted(completed_months)
        season_cp["game_count"] = total_games
        save_checkpoint(checkpoint)

        logger.info("  %s: %d games (running total: %d)", month_key, n, total_games)

    logger.info("Season %d: %d total games in DB", season, total_games)
    return total_games


# ---------------------------------------------------------------------------
# Pitcher season stats (FanGraphs via pybaseball)
# ---------------------------------------------------------------------------


def _safe_float(val: Any) -> Optional[float]:
    """Convert value to float, returning None for NaN or non-numeric."""
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    """Convert value to int, returning None for non-numeric."""
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _build_fg_to_mlbam_mapping(mlbam_ids: list[int]) -> dict[str, int]:
    """Cross-reference MLBAM player IDs to FanGraphs IDs.

    Returns dict of {fangraphs_id_str: mlbam_id}.
    """
    mapping: dict[str, int] = {}
    if not _HAS_PYBASEBALL or not mlbam_ids:
        return mapping

    try:
        from pybaseball import playerid_reverse_lookup  # type: ignore[import-untyped]

        xref = playerid_reverse_lookup(mlbam_ids, key_type="mlbam")
        for _, row in xref.iterrows():
            mlbam = row.get("key_mlbam")
            fg_id = row.get("key_fangraphs")
            if mlbam and fg_id and not (isinstance(fg_id, float) and math.isnan(fg_id)):
                mapping[str(int(fg_id))] = int(mlbam)
    except Exception as exc:
        logger.warning("playerid_reverse_lookup failed: %s", exc)

    return mapping


def fetch_pitcher_season_stats(season: int, db_path: Path) -> int:
    """Fetch FanGraphs pitcher leaderboard for a season and store in pitcher_season_stats.

    Builds the players table from FanGraphs data using playerid_reverse_lookup
    (key_type='fangraphs') to convert FanGraphs IDs to MLBAM IDs. This avoids
    the need for pre-populated players from the schedule endpoint, which doesn't
    include pitcher IDs for completed historical games.

    Returns number of pitcher_season_stats rows inserted.
    """
    if not _HAS_PYBASEBALL:
        logger.warning("pybaseball not installed — skipping FanGraphs stats")
        return 0

    pybaseball.cache.enable()

    logger.info("Season %d: fetching FanGraphs pitcher stats...", season)

    # Step 1: Download FanGraphs pitcher leaderboard (qual=1 = all pitchers, 1+ IP)
    logger.info("  Downloading FanGraphs pitching_stats(%d)...", season)
    try:
        stats_df = pybaseball.pitching_stats(season, season, qual=1, split_seasons=True)
    except Exception as exc:
        logger.error("  pitching_stats() failed: %s", exc)
        return 0

    if stats_df is None or len(stats_df) == 0:
        logger.warning("  No FanGraphs data returned for %d", season)
        return 0

    logger.info("  FanGraphs returned %d rows", len(stats_df))

    # Step 2: Extract all FanGraphs IDs from the leaderboard
    fg_ids: list[int] = []
    for _, row in stats_df.iterrows():
        raw = row.get("IDfg")
        if raw is not None:
            try:
                fg_ids.append(int(float(raw)))
            except (TypeError, ValueError):
                pass

    if not fg_ids:
        logger.warning("  No IDfg column found — cannot cross-reference to MLBAM")
        return 0

    # Step 3: Cross-reference FanGraphs IDs → MLBAM IDs
    logger.info("  Cross-referencing %d FanGraphs IDs → MLBAM...", len(fg_ids))
    fg_to_mlbam: dict[int, int] = {}
    fg_to_name: dict[int, str] = {}
    try:
        from pybaseball import playerid_reverse_lookup  # type: ignore[import-untyped]

        xref = playerid_reverse_lookup(fg_ids, key_type="fangraphs")
        for _, xrow in xref.iterrows():
            fg = xrow.get("key_fangraphs")
            mlbam = xrow.get("key_mlbam")
            if fg is None or mlbam is None:
                continue
            try:
                fg_int = int(float(fg))
                mlbam_int = int(float(mlbam))
                if mlbam_int > 0:
                    fg_to_mlbam[fg_int] = mlbam_int
                    # Build name from Chadwick Bureau data
                    last = str(xrow.get("name_last", "")).capitalize()
                    first = str(xrow.get("name_first", "")).capitalize()
                    fg_to_name[fg_int] = f"{first} {last}".strip()
            except (TypeError, ValueError):
                pass
    except Exception as exc:
        logger.warning("  playerid_reverse_lookup failed: %s", exc)

    logger.info("  Resolved %d FanGraphs → MLBAM mappings", len(fg_to_mlbam))

    # Step 4: Build players table from FanGraphs data (FanGraphs name preferred over Chadwick)
    player_rows: list[tuple] = []
    fg_name_map: dict[int, str] = {
        int(float(row["IDfg"])): str(row.get("Name", ""))
        for _, row in stats_df.iterrows()
        if row.get("IDfg") is not None
    }
    for fg_id, mlbam_id in fg_to_mlbam.items():
        fg_name = fg_name_map.get(fg_id) or fg_to_name.get(fg_id, f"Player {mlbam_id}")
        player_rows.append((mlbam_id, fg_name, "SP", str(fg_id)))

    if player_rows:
        with get_conn(db_path) as conn:
            conn.executemany(
                """INSERT OR IGNORE INTO players
                   (player_id, full_name, position, fangraphs_id)
                   VALUES (?,?,?,?)""",
                player_rows,
            )
        logger.info("  Upserted %d players from FanGraphs", len(player_rows))

    # Step 5: Insert pitcher season stats
    _, end_str = SEASON_RANGES[season]
    as_of_date = end_str[:10]

    stat_rows = []
    skipped = 0

    for _, row in stats_df.iterrows():
        raw_fg = row.get("IDfg")
        if raw_fg is None:
            skipped += 1
            continue
        try:
            fg_int = int(float(raw_fg))
        except (TypeError, ValueError):
            skipped += 1
            continue

        player_id = fg_to_mlbam.get(fg_int)
        if not player_id:
            skipped += 1
            continue

        k_pct = _safe_float(row.get("K%"))
        bb_pct = _safe_float(row.get("BB%"))
        k_bb_pct: Optional[float] = None
        if k_pct is not None and bb_pct is not None:
            k_bb_pct = k_pct - bb_pct

        avg_velo = (
            _safe_float(row.get("vFA (sc)"))
            or _safe_float(row.get("FBv"))
            or _safe_float(row.get("vFA"))
        )

        stat_rows.append(
            (
                player_id,
                season,
                as_of_date,
                _safe_int(row.get("GS")),
                _safe_float(row.get("IP")),
                _safe_float(row.get("ERA")),
                _safe_float(row.get("WHIP")),
                _safe_float(row.get("K/9")),
                _safe_float(row.get("BB/9")),
                k_bb_pct,
                _safe_float(row.get("HR/9")),
                _safe_float(row.get("FIP")),
                _safe_float(row.get("xFIP")),
                _safe_float(row.get("SIERA")),
                _safe_float(row.get("Stuff+")),
                avg_velo,
            )
        )

    if stat_rows:
        with get_conn(db_path) as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO pitcher_season_stats
                   (player_id, season, as_of_date, games_started, ip, era, whip,
                    k_per_9, bb_per_9, k_bb_pct, hr_per_9, fip, xfip, siera,
                    stuff_plus, avg_velo)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                stat_rows,
            )

    logger.info(
        "  Pitcher stats: %d inserted, %d skipped (no MLBAM cross-reference)",
        len(stat_rows),
        skipped,
    )
    return len(stat_rows)


# ---------------------------------------------------------------------------
# Summary stats
# ---------------------------------------------------------------------------


def print_db_summary(db_path: Path) -> None:
    """Print current row counts for MLB tables."""
    tables = ["games", "players", "pitcher_season_stats", "park_factors"]
    with get_conn(db_path) as conn:
        print("\nDB summary:")
        for tbl in tables:
            n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]  # noqa: S608 # nosec B608
            print(f"  {tbl:<30} {n:>6}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for mlb_fetch_historical."""
    parser = argparse.ArgumentParser(
        description="Fetch historical MLB data (games + pitcher stats) for 2023-2025"
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=[2023, 2024, 2025],
        choices=[2023, 2024, 2025],
        metavar="YEAR",
        help="Seasons to fetch (default: 2023 2024 2025)",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Skip seasons already marked complete in checkpoint file",
    )
    parser.add_argument(
        "--games-only",
        action="store_true",
        help="Only fetch game schedule/results (skip FanGraphs pitcher stats)",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only fetch FanGraphs pitcher stats (skip game schedule)",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        metavar="PATH",
        help=f"Path to mlb_data.db (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds between API requests (default: 0.5)",
    )
    parser.add_argument(
        "--reset-checkpoint",
        action="store_true",
        help="Ignore existing checkpoint and start from scratch",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        logger.error("Database not found: %s", db_path)
        logger.error("Run first: python scripts/mlb_init_db.py --seed-teams")
        sys.exit(1)

    if not _HAS_STATSAPI and not args.stats_only:
        logger.error("MLB-StatsAPI not installed. Run: pip install MLB-StatsAPI")
        sys.exit(1)

    if not _HAS_PYBASEBALL and not args.games_only:
        logger.warning("pybaseball not installed — pitcher stats will be skipped")

    checkpoint = {} if args.reset_checkpoint else load_checkpoint()
    if args.reset_checkpoint:
        logger.info("Checkpoint reset — fetching all seasons from scratch")

    for season in args.seasons:
        season_key = str(season)
        season_cp = checkpoint.setdefault(season_key, {})

        if args.incremental and season_cp.get("complete"):
            logger.info("Season %d complete — skipping (--incremental)", season)
            continue

        logger.info("=" * 60)
        logger.info("Season %d", season)
        logger.info("=" * 60)

        # --- Games ---
        if not args.stats_only:
            if not season_cp.get("games_complete"):
                n = fetch_season_games(season, db_path, checkpoint, args.delay)
                season_cp["games_complete"] = True
                season_cp["game_count"] = n
                save_checkpoint(checkpoint)
            else:
                logger.info("Games already fetched (%d games)", season_cp.get("game_count", 0))

        # --- FanGraphs pitcher stats ---
        if not args.games_only:
            if not season_cp.get("pitcher_stats_complete"):
                n = fetch_pitcher_season_stats(season, db_path)
                season_cp["pitcher_stats_complete"] = True
                season_cp["pitcher_stats_count"] = n
                save_checkpoint(checkpoint)
            else:
                logger.info(
                    "Pitcher stats already fetched (%d rows)",
                    season_cp.get("pitcher_stats_count", 0),
                )

        season_cp["complete"] = bool(season_cp.get("games_complete")) and bool(
            season_cp.get("pitcher_stats_complete")
        )
        save_checkpoint(checkpoint)

    # Final summary
    logger.info("=" * 60)
    logger.info("Run complete")
    for season in args.seasons:
        cp = checkpoint.get(str(season), {})
        games = cp.get("game_count", 0)
        stats = cp.get("pitcher_stats_count", 0)
        status = "COMPLETE" if cp.get("complete") else "PARTIAL"
        logger.info("  %d: %d games, %d pitcher stat rows [%s]", season, games, stats, status)

    print_db_summary(db_path)


if __name__ == "__main__":
    main()
