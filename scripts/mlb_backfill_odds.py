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
    ESPNCoreOddsFetcher,
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
    108: 3,  # LAA
    109: 29,  # ARI
    110: 1,  # BAL
    111: 2,  # BOS
    112: 16,  # CHC
    113: 17,  # CIN
    114: 5,  # CLE
    115: 27,  # COL
    116: 6,  # DET
    117: 18,  # HOU
    118: 7,  # KC
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
    142: 9,  # MIN
    143: 22,  # PHI
    144: 15,  # ATL
    145: 4,  # CWS
    146: 28,  # MIA
    147: 10,  # NYY
    158: 8,  # MIL
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
            game_pk,
            provider,
            home_ml_open,
            away_ml_open,
            home_ml_close,
            away_ml_close,
            total_open,
            total_close,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def get_games_for_date(conn: sqlite3.Connection, game_date: str) -> dict[tuple[int, int], int]:
    """Get games for a date, keyed by (away_team_id, home_team_id) -> game_pk."""
    rows = conn.execute(
        "SELECT game_pk, home_team_id, away_team_id FROM games "
        "WHERE game_date = ? AND status = 'final'",
        (game_date,),
    ).fetchall()
    return {(r[2], r[1]): r[0] for r in rows}


def get_dates_needing_odds(conn: sqlite3.Connection, seasons: list[int]) -> list[str]:
    """Get game dates that have final games but no odds yet."""
    placeholders = ",".join("?" for _ in seasons)
    query = (
        "SELECT DISTINCT g.game_date FROM games g "
        "WHERE g.season IN (%s) AND g.status = 'final' "
        "AND g.game_pk NOT IN (SELECT game_pk FROM odds) "
        "ORDER BY g.game_date"
    ) % placeholders  # nosec B608
    rows = conn.execute(query, seasons).fetchall()
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
        events.append(
            {
                "event_id": event_id,
                "espn_home_id": int(home[0]["team"]["id"]),
                "espn_away_id": int(away[0]["team"]["id"]),
            }
        )
    return events


def pick_best_snapshot(snapshots: list[OddsSnapshot]) -> OddsSnapshot | None:
    """Pick best odds snapshot (prefer non-live provider with closing odds)."""
    with_close = [s for s in snapshots if s.home_ml_close is not None]
    if with_close:
        non_live = [s for s in with_close if s.provider_id != 59]
        return non_live[0] if non_live else with_close[0]
    with_open = [s for s in snapshots if s.home_ml_open is not None]
    if with_open:
        non_live = [s for s in with_open if s.provider_id != 59]
        return non_live[0] if non_live else with_open[0]
    return snapshots[0] if snapshots else None


def backfill_date(
    game_date: str,
    db_conn: sqlite3.Connection,
    odds_provider: ESPNCoreOddsFetcher,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Backfill odds for all games on a single date.

    Returns (matched, total_games) count.
    """
    games_by_teams = get_games_for_date(db_conn, game_date)
    if not games_by_teams:
        return 0, 0

    espn_events = fetch_espn_events(game_date)
    time.sleep(0.5)

    matched = 0
    for ev in espn_events:
        game_pk = match_espn_to_mlbam(ev["espn_home_id"], ev["espn_away_id"], games_by_teams)
        if game_pk is None:
            continue

        snapshots = odds_provider.fetch_game_odds(ev["event_id"])
        time.sleep(0.5)

        best = pick_best_snapshot(snapshots)
        if best is None:
            continue

        if dry_run:
            logger.info(
                "[DRY RUN] %s game_pk=%d: home_ml=%s/%s provider=%s",
                game_date,
                game_pk,
                best.home_ml_open,
                best.home_ml_close,
                best.provider_name,
            )
        else:
            insert_odds(
                db_conn,
                game_pk,
                best.provider_name,
                best.home_ml_open,
                best.away_ml_open,
                best.home_ml_close,
                best.away_ml_close,
                best.total_open,
                best.total_close,
            )
        matched += 1

    return matched, len(games_by_teams)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Backfill MLB odds from ESPN Core API")
    parser.add_argument(
        "--seasons",
        nargs="+",
        type=int,
        default=[2023, 2024, 2025],
        help="Seasons to backfill",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(DB_PATH),
        help="Path to mlb_data.db",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print matches without writing to DB",
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

    odds_provider = ESPNCoreOddsFetcher(sport="mlb", requests_per_second=2.0)

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
                i + 1,
                len(dates),
                total_matched,
                total_games,
                coverage,
            )

    if not args.dry_run:
        conn.commit()

    coverage = total_matched / total_games * 100 if total_games > 0 else 0
    logger.info(
        "Done: %d/%d games with odds (%.1f%%) across %d dates",
        total_matched,
        total_games,
        coverage,
        len(dates),
    )
    conn.close()


if __name__ == "__main__":
    main()
