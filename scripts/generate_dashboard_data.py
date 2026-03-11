"""Generate merged dashboard data bundle for NCAA D1 Basketball dashboard.

Merges three data sources into a single JSON file:
1. Elo ratings (current, from trained model)
2. Barttorvik T-Rank efficiency ratings (latest available snapshot)
3. Game stats (2026 season W-L, PPG, PAPG, margin)

Output: data/processed/ncaab_dashboard_bundle.json

Usage:
    python scripts/generate_dashboard_data.py
    python scripts/generate_dashboard_data.py --season 2026
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from config.settings import NCAAB_DATABASE_PATH
from pipelines.team_name_mapping import build_espn_barttorvik_mapping

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ELO_PICKLE_PATH = PROJECT_ROOT / "data" / "processed" / "ncaab_elo_model.pkl"
TOP_N_TRAJECTORY_TEAMS = 20
TRAJECTORY_SAMPLE_EVERY = 5

# ---------------------------------------------------------------------------
# Conference abbreviation -> full name lookup
# ---------------------------------------------------------------------------

CONFERENCE_FULL_NAMES: dict[str, str] = {
    "A10": "Atlantic 10",
    "ACC": "ACC",
    "AE": "America East",
    "ASun": "Atlantic Sun",
    "Amer": "American Athletic",
    "B10": "Big Ten",
    "B12": "Big 12",
    "BE": "Big East",
    "BSky": "Big Sky",
    "BSth": "Big South",
    "BW": "Big West",
    "CAA": "Colonial Athletic",
    "CUSA": "Conference USA",
    "Horz": "Horizon League",
    "Ivy": "Ivy League",
    "MAAC": "Metro Atlantic Athletic",
    "MAC": "Mid-American",
    "MEAC": "Mid-Eastern Athletic",
    "MVC": "Missouri Valley",
    "MWC": "Mountain West",
    "NEC": "Northeast",
    "OVC": "Ohio Valley",
    "Pat": "Patriot League",
    "SB": "Sun Belt",
    "SC": "Southern",
    "SEC": "SEC",
    "SWAC": "Southwestern Athletic",
    "Slnd": "Southland",
    "Sum": "Summit League",
    "WAC": "Western Athletic",
    "WCC": "West Coast",
}


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def load_elo_ratings(
    path: Path = PROJECT_ROOT / "data" / "processed" / "ncaab_elo_ratings_current.csv",
) -> pd.DataFrame:
    """Load current Elo ratings CSV."""
    if not path.exists():
        logger.error("Elo ratings not found: %s", path)
        return pd.DataFrame()

    df = pd.read_csv(path)
    logger.info("Loaded %d Elo ratings from %s", len(df), path.name)
    return df


def load_barttorvik_latest(
    bart_dir: Path = PROJECT_ROOT / "data" / "external" / "barttorvik",
) -> tuple[pd.DataFrame, str]:
    """Load latest Barttorvik ratings snapshot.

    Returns the most recent date's ratings from the newest season file.

    Returns:
        Tuple of (DataFrame with latest ratings per team, date string).
    """
    files = sorted(bart_dir.glob("barttorvik_ratings_*.parquet"))
    if not files:
        logger.warning("No Barttorvik data found in %s", bart_dir)
        return pd.DataFrame(), ""

    # Use the most recent season file
    latest_file = files[-1]
    df = pd.read_parquet(latest_file)

    if df.empty or "date" not in df.columns:
        return pd.DataFrame(), ""

    df["date"] = pd.to_datetime(df["date"])
    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date].copy()

    # Compute NET rating (adj_o - adj_d)
    if "adj_o" in latest.columns and "adj_d" in latest.columns:
        latest["adj_net"] = latest["adj_o"] - latest["adj_d"]

    date_str = latest_date.strftime("%Y-%m-%d")
    season = latest_file.stem.split("_")[-1]
    logger.info(
        "Loaded %d Barttorvik teams from season %s (date: %s)",
        len(latest),
        season,
        date_str,
    )
    return latest, date_str


def load_game_stats(
    season: int = 2026,
    games_dir: Path = PROJECT_ROOT / "data" / "raw" / "ncaab",
) -> pd.DataFrame:
    """Aggregate per-team game stats for a season.

    The parquet file is deduplicated by game_id, so each game appears once
    with a single team_id.  A team may appear as team_id in some games and
    as opponent_id in others.  We build two DataFrames (one per perspective),
    normalise the column names, concatenate, and then aggregate.

    Returns DataFrame with: team_id, wins, losses, ppg, papg, margin, games.
    """
    path = games_dir / f"ncaab_games_{season}.parquet"
    if not path.exists():
        logger.warning("Game data not found: %s", path)
        return pd.DataFrame()

    df = pd.read_parquet(path)
    if df.empty:
        return pd.DataFrame()

    # Perspective 1: rows where the team is team_id (original view)
    p1 = df[["team_id", "result", "points_for", "points_against"]].copy()
    p1.columns = ["team_id", "result", "pts_scored", "pts_allowed"]

    # Perspective 2: rows where the team is opponent_id (mirror view)
    result_flip = {"W": "L", "L": "W"}
    p2 = df[["opponent_id", "result", "points_against", "points_for"]].copy()
    p2.columns = ["team_id", "result", "pts_scored", "pts_allowed"]
    p2["result"] = p2["result"].map(result_flip)

    combined = pd.concat([p1, p2], ignore_index=True)

    # Aggregate per team
    stats = (
        combined.groupby("team_id")
        .agg(
            games=("result", "count"),
            wins=("result", lambda x: (x == "W").sum()),
            losses=("result", lambda x: (x == "L").sum()),
            ppg=("pts_scored", "mean"),
            papg=("pts_allowed", "mean"),
        )
        .reset_index()
    )
    stats["margin"] = stats["ppg"] - stats["papg"]
    stats["win_pct"] = stats["wins"] / stats["games"].clip(lower=1)

    # Round numeric columns
    for col in ("ppg", "papg", "margin", "win_pct"):
        stats[col] = stats[col].round(1)

    logger.info("Computed game stats for %d teams (season %d)", len(stats), season)
    return stats


def load_elo_model(path: Path = ELO_PICKLE_PATH) -> object | None:
    """Load the trained Elo model pickle.

    The pickle contains a SavedModel dataclass with a `.model` attribute
    (NCAABEloModel). Returns None if the file is missing or unpicklable.

    Args:
        path: Path to the .pkl model file.

    Returns:
        The SavedModel instance, or None on failure.
    """
    if not path.exists():
        logger.warning("Elo model pickle not found: %s", path)
        return None

    try:
        with open(path, "rb") as f:
            saved = pickle.load(f)  # noqa: S301  # nosec B301
        logger.info("Loaded Elo model pickle from %s", path)
        return saved
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load Elo model pickle: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Trajectory extraction
# ---------------------------------------------------------------------------


def load_trajectories(
    pickle_path: Path = ELO_PICKLE_PATH,
    top_n: int = TOP_N_TRAJECTORY_TEAMS,
    sample_every: int = TRAJECTORY_SAMPLE_EVERY,
) -> list[dict]:
    """Extract Elo rating trajectories for the top N teams by current rating.

    Walks through game_history on the loaded model, recording each top
    team's rating after every game they appear in (home or away).
    Samples every ``sample_every``-th game per team to keep data size
    manageable.

    Args:
        pickle_path: Path to the ncaab_elo_model.pkl file.
        top_n: Number of top-rated teams to include.
        sample_every: Record one data point every this many games per team.

    Returns:
        List of dicts with keys: team, game_idx, rating.
        Returns empty list if the pickle cannot be loaded.
    """
    saved = load_elo_model(pickle_path)
    if saved is None:
        return []

    # Unwrap SavedModel -> NCAABEloModel
    model = saved.model if hasattr(saved, "model") else saved

    if not hasattr(model, "ratings") or not hasattr(model, "game_history"):
        logger.warning("Elo model missing .ratings or .game_history attributes")
        return []

    # Identify top N teams by current rating
    sorted_teams = sorted(model.ratings.items(), key=lambda kv: kv[1], reverse=True)
    top_teams: set[str] = {team for team, _ in sorted_teams[:top_n]}
    logger.info(
        "Building trajectories for %d top teams from %d game history entries",
        len(top_teams),
        len(model.game_history),
    )

    # Walk game history; track per-team appearance count for sampling
    appearances: dict[str, int] = {team: 0 for team in top_teams}
    trajectory_rows: list[dict] = []

    for game_idx, game in enumerate(model.game_history):
        home = game.get("home_team", "")
        away = game.get("away_team", "")

        for team, rating_key in ((home, "home_rating_after"), (away, "away_rating_after")):
            if team not in top_teams:
                continue

            rating_after = game.get(rating_key)
            if rating_after is None:
                continue

            appearances[team] += 1
            # Sample every N-th appearance (always include the first)
            if appearances[team] == 1 or appearances[team] % sample_every == 0:
                trajectory_rows.append(
                    {
                        "team": team,
                        "game_idx": game_idx,
                        "rating": round(float(rating_after), 1),
                    }
                )

    logger.info("Trajectory data: %d sampled data points", len(trajectory_rows))
    return trajectory_rows


# ---------------------------------------------------------------------------
# All-teams historical ratings
# ---------------------------------------------------------------------------


def load_all_team_ratings(
    pickle_path: Path = ELO_PICKLE_PATH,
) -> list[dict]:
    """Extract all-team current Elo ratings from the model pickle.

    Returns one record per team in model.ratings, covering all 1,107+
    rated teams regardless of whether they played in the current season.

    Args:
        pickle_path: Path to the ncaab_elo_model.pkl file.

    Returns:
        List of dicts with keys: team_id, elo_rating (sorted desc by rating).
        Returns empty list if the pickle cannot be loaded.
    """
    saved = load_elo_model(pickle_path)
    if saved is None:
        return []

    model = saved.model if hasattr(saved, "model") else saved

    if not hasattr(model, "ratings"):
        logger.warning("Elo model missing .ratings attribute for all_teams export")
        return []

    all_teams = [
        {"team_id": team_id, "elo_rating": round(float(rating), 1)}
        for team_id, rating in sorted(model.ratings.items(), key=lambda kv: kv[1], reverse=True)
    ]
    logger.info("Exported %d teams for all_teams section", len(all_teams))
    return all_teams


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def classify_tier(elo: float | None) -> str:
    """Classify team into tier based on Elo rating."""
    if elo is None or pd.isna(elo):
        return "Unrated"
    if elo >= 1700:
        return "Elite"
    if elo >= 1550:
        return "Strong"
    if elo >= 1400:
        return "Average"
    return "Below Avg"


def build_opponent_name_map(
    games_dir: Path = PROJECT_ROOT / "data" / "raw" / "ncaab",
) -> dict[str, str]:
    """Build ESPN team_id -> full team name mapping from game data."""
    name_map: dict[str, str] = {}
    for f in sorted(games_dir.glob("ncaab_games_*.parquet")):
        df = pd.read_parquet(f)
        for _, row in df.iterrows():
            oid = row.get("opponent_id")
            oname = row.get("opponent_name")
            if oid and oname and isinstance(oname, str):
                name_map[oid] = oname
    return name_map


def _safe_round(val, decimals: int = 1):
    """Round a value safely, returning None for NaN/None."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return round(float(val), decimals)


def _safe_int(val):
    """Convert to int safely, returning None for NaN/None."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return int(val)


# ---------------------------------------------------------------------------
# Game log loader
# ---------------------------------------------------------------------------


def _load_game_log(db_path: Path) -> list[dict]:
    """Load game_log table for dashboard export."""
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM game_log ORDER BY game_date DESC, home").fetchall()
        return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        logger.warning("game_log table not found — run daily pipeline first")
        return []
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Bundle generation
# ---------------------------------------------------------------------------


def generate_bundle(season: int = 2026) -> dict:
    """Generate the complete dashboard data bundle."""
    # Load data sources
    elo_df = load_elo_ratings()
    bart_df, bart_date = load_barttorvik_latest()
    game_stats = load_game_stats(season)

    # Filter out non-D1 exhibition opponents (< 10 games) before building
    # the active set.  Real D1 teams play 25-35 games; exhibition opponents
    # that only appear as opponent_id have 1-3 games.
    MIN_GAMES_D1 = 10
    if not game_stats.empty:
        n_before = len(game_stats)
        game_stats = game_stats[game_stats["games"] >= MIN_GAMES_D1].copy()
        logger.info(
            "Filtered non-D1 teams: %d -> %d (min %d games)",
            n_before,
            len(game_stats),
            MIN_GAMES_D1,
        )

    # Filter Elo to only teams active in the current season
    active_team_ids = set(game_stats["team_id"]) if not game_stats.empty else set()
    if active_team_ids:
        elo_df = elo_df[elo_df["team_id"].isin(active_team_ids)].copy()
        elo_df = elo_df.sort_values("elo_rating", ascending=False).reset_index(drop=True)
        elo_df["rank"] = range(1, len(elo_df) + 1)
        logger.info("Filtered to %d active teams for season %d", len(elo_df), season)

    # Build ESPN -> Barttorvik name mapping
    espn_to_bart = build_espn_barttorvik_mapping()
    # Build ESPN ID -> full name mapping
    full_names = build_opponent_name_map()

    # Index Barttorvik by team name for fast lookup
    bart_lookup: dict[str, dict] = {}
    if not bart_df.empty:
        for _, row in bart_df.iterrows():
            bart_lookup[row["team"]] = row.to_dict()

    # Index game stats by team_id
    stats_lookup: dict[str, dict] = {}
    if not game_stats.empty:
        for _, row in game_stats.iterrows():
            stats_lookup[row["team_id"]] = row.to_dict()

    # Build team records
    teams = []
    conf_teams: dict[str, list] = {}

    for _, elo_row in elo_df.iterrows():
        tid = elo_row["team_id"]
        elo_val = round(elo_row["elo_rating"], 1)
        elo_rank = int(elo_row["rank"])

        # Get Barttorvik data via mapping
        bart_name = espn_to_bart.get(tid)
        bart_data = bart_lookup.get(bart_name, {}) if bart_name else {}

        # Get game stats
        gstats = stats_lookup.get(tid, {})

        # Conference from Barttorvik (ESPN conf is always empty)
        conf = bart_data.get("conf", "")
        conf_full = CONFERENCE_FULL_NAMES.get(conf, conf)

        # Full team name: prefer Barttorvik name (cleaner), fallback to ESPN stripped
        raw_name = full_names.get(tid, tid)
        if bart_name:
            team_name = bart_name
        else:
            team_name = raw_name

        team = {
            "id": tid,
            "name": team_name,
            "bart_name": bart_name or "",
            "conf": conf,
            "conf_full": conf_full,
            "elo": elo_val,
            "elo_rank": elo_rank,
            "bart_rank": _safe_int(bart_data.get("rank")),
            "adj_o": _safe_round(bart_data.get("adj_o")),
            "adj_d": _safe_round(bart_data.get("adj_d")),
            "adj_net": _safe_round(bart_data.get("adj_net")),
            "barthag": _safe_round(bart_data.get("barthag"), 4),
            "adj_tempo": _safe_round(bart_data.get("adj_tempo")),
            "wab": _safe_round(bart_data.get("wab")),
            "wins": int(gstats.get("wins", 0)),
            "losses": int(gstats.get("losses", 0)),
            "win_pct": _safe_round(gstats.get("win_pct"), 3),
            "ppg": _safe_round(gstats.get("ppg")),
            "papg": _safe_round(gstats.get("papg")),
            "margin": _safe_round(gstats.get("margin")),
            "games": int(gstats.get("games", 0)),
            "tier": classify_tier(elo_val),
        }
        teams.append(team)

        # Track conference membership
        if conf:
            conf_teams.setdefault(conf, []).append(team)

    # Build conference summaries (with min/max Elo range)
    conferences = []
    for abbr in sorted(conf_teams.keys()):
        members = conf_teams[abbr]
        elos = [t["elo"] for t in members]
        nets = [t["adj_net"] for t in members if t["adj_net"] is not None]
        barthags = [t["barthag"] for t in members if t["barthag"] is not None]

        conferences.append(
            {
                "abbr": abbr,
                "name": CONFERENCE_FULL_NAMES.get(abbr, abbr),
                "teams": len(members),
                "avg_elo": round(sum(elos) / len(elos), 1) if elos else None,
                "min_elo": round(min(elos), 1) if elos else None,
                "max_elo": round(max(elos), 1) if elos else None,
                "avg_adj_net": round(sum(nets) / len(nets), 1) if nets else None,
                "avg_barthag": round(sum(barthags) / len(barthags), 4) if barthags else None,
                "best_team": min(members, key=lambda t: t["elo_rank"])["id"],
                "worst_team": max(members, key=lambda t: t["elo_rank"])["id"],
            }
        )

    # Sort conferences by avg_elo desc
    conferences.sort(key=lambda c: c["avg_elo"] or 0, reverse=True)

    # Load trajectory data and all-team ratings from the model pickle
    trajectories = load_trajectories()
    all_teams = load_all_team_ratings()
    game_log_data = _load_game_log(NCAAB_DATABASE_PATH)

    bart_coverage = sum(1 for t in teams if t["bart_name"])
    elo_date = datetime.now().strftime("%Y-%m-%d")

    bundle = {
        "generated_at": datetime.now().isoformat(),
        "season": season,
        "teams": teams,
        "conferences": conferences,
        "conference_lookup": CONFERENCE_FULL_NAMES,
        "trajectories": trajectories,
        "all_teams": all_teams,
        "game_log": game_log_data,
        "meta": {
            "total_teams": len(teams),
            "all_teams_count": len(all_teams),
            "trajectory_teams": TOP_N_TRAJECTORY_TEAMS,
            "trajectory_sample_every": TRAJECTORY_SAMPLE_EVERY,
            "trajectory_points": len(trajectories),
            "barttorvik_coverage": bart_coverage,
            "elo_model_date": elo_date,
            "barttorvik_date": bart_date,
            "barttorvik_season": "2024-25 (end-of-season)",
            "game_log_count": len(game_log_data),
        },
    }

    return bundle


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for dashboard data generation."""
    parser = argparse.ArgumentParser(description="Generate NCAA D1 dashboard data")
    parser.add_argument("--season", type=int, default=2026, help="Season (default: 2026)")
    parser.add_argument(
        "--output",
        type=str,
        default=str(PROJECT_ROOT / "data" / "processed" / "ncaab_dashboard_bundle.json"),
        help="Output JSON path",
    )
    args = parser.parse_args()

    bundle = generate_bundle(args.season)

    if bundle["meta"]["total_teams"] == 0:
        logger.error("Dashboard bundle has 0 teams -- aborting")
        sys.exit(1)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, default=str)

    meta = bundle["meta"]
    print(f"\nDashboard data generated: {out_path}")
    print(f"  Teams (current season): {meta['total_teams']}")
    print(f"  All teams (historical): {meta['all_teams_count']}")
    print(
        f"  Trajectory points:      {meta['trajectory_points']} ({meta['trajectory_teams']} teams)"
    )
    print(f"  Barttorvik coverage:    {meta['barttorvik_coverage']}")
    print(f"  Elo date:               {meta['elo_model_date']}")
    print(f"  Barttorvik date:        {meta['barttorvik_date']}")
    print(f"  Conferences:            {len(bundle['conferences'])}")


if __name__ == "__main__":
    main()
