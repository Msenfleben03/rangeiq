"""Research pipeline: Efficiency Trajectory features for NCAAB tournament prep.

Computes trajectory features from Barttorvik snapshots, aligns them to games
using strict point-in-time (PIT) logic, and correlates with CLV from backtests.

Usage:
    venv/Scripts/python.exe scripts/research_efficiency_trajectory.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from features.sport_specific.ncaab.efficiency_trajectory import (  # noqa: E402
    compute_all_trajectory_features,
)
from features.sport_specific.ncaab.research_utils import (
    VALID_SEASONS,
)  # noqa: E402  # pylint: disable=wrong-import-position
from pipelines.team_name_mapping import build_espn_barttorvik_mapping  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Resolve the actual data root — in worktrees, data lives in the main repo
# Walk up from __file__ looking for data/external/barttorvik
_SCRIPT_ROOT = Path(__file__).resolve().parent.parent
_MAIN_ROOT = _SCRIPT_ROOT
for _candidate in [_SCRIPT_ROOT, _SCRIPT_ROOT.parent.parent.parent]:
    if (_candidate / "data" / "external" / "barttorvik").is_dir():
        _MAIN_ROOT = _candidate
        break
# Also check the non-worktree project root
_GIT_ROOT = Path("C:/Users/msenf/sports-betting")
if (_GIT_ROOT / "data" / "external" / "barttorvik").is_dir():
    _MAIN_ROOT = _GIT_ROOT

DATA_DIR = _MAIN_ROOT / "data"
RESEARCH_DIR = PROJECT_ROOT / "data" / "research"
BACKTEST_DIR = DATA_DIR / "backtests"
REPORT_DIR = PROJECT_ROOT / "docs" / "research"

# Feature column names
FEATURE_COLS = [
    "adj_o_slope_10s",
    "adj_d_slope_10s",
    "net_efficiency_slope_10s",
    "barthag_delta_10s",
    "barthag_delta_20s",
    "rank_change_20s",
]

MIN_UNIQUE_DATES = 30


def audit_snapshot_frequency(bart_df: pd.DataFrame, season: int) -> dict:
    """Audit Barttorvik snapshot frequency for a season.

    Returns dict with unique_dates, avg_gap_days, max_gap_days, min_date, max_date.
    """
    dates = bart_df["date"].dt.normalize().unique()
    dates = np.sort(dates)
    n_dates = len(dates)
    if n_dates < 2:
        return {
            "season": season,
            "unique_dates": n_dates,
            "avg_gap_days": np.nan,
            "max_gap_days": np.nan,
            "min_date": str(dates[0])[:10] if n_dates else "N/A",
            "max_date": str(dates[-1])[:10] if n_dates else "N/A",
        }

    gaps = np.diff(dates).astype("timedelta64[D]").astype(float)
    return {
        "season": season,
        "unique_dates": n_dates,
        "avg_gap_days": round(float(np.mean(gaps)), 1),
        "max_gap_days": round(float(np.max(gaps)), 1),
        "min_date": str(dates[0])[:10],
        "max_date": str(dates[-1])[:10],
    }


def compute_season_features(
    bart_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute trajectory features for all teams in a season's snapshots.

    Groups by team, computes features per team, concatenates results.
    Season boundary is enforced by using only this season's snapshots.

    Args:
        bart_df: Barttorvik snapshots for a single season, sorted by [team, date].

    Returns:
        DataFrame with trajectory features + date and team columns.
    """
    all_team_features = []

    for team, team_snaps in bart_df.groupby("team"):
        team_snaps = team_snaps.sort_values("date").reset_index(drop=True)
        if len(team_snaps) < 2:
            continue

        features = compute_all_trajectory_features(team_snaps)
        features["date"] = team_snaps["date"].values
        features["team"] = team
        all_team_features.append(features)

    if not all_team_features:
        return pd.DataFrame()

    return pd.concat(all_team_features, ignore_index=True)


def pit_align_to_games(
    features_df: pd.DataFrame,
    games_df: pd.DataFrame,
    espn_to_bart: dict[str, str],
) -> pd.DataFrame:
    """Align trajectory features to game schedule using strict PIT logic.

    For each game row, finds the most recent trajectory feature snapshot
    STRICTLY BEFORE game_date (snapshot.date < game.date).

    Args:
        features_df: Trajectory features with date and team columns.
        games_df: Season games from ESPN data.
        espn_to_bart: ESPN team_id -> Barttorvik team name mapping.

    Returns:
        DataFrame with game_id, game_date, team_id, and all 6 feature columns.
    """
    # Sort features by date for efficient lookup
    features_df = features_df.sort_values("date").reset_index(drop=True)

    aligned_rows = []

    for _, game in games_df.iterrows():
        game_date = pd.Timestamp(game["date"])
        team_id = game["team_id"]
        game_id = game["game_id"]

        bart_name = espn_to_bart.get(team_id)
        if bart_name is None:
            continue

        # Strict PIT: snapshot.date < game.date
        team_feats = features_df[
            (features_df["team"] == bart_name) & (features_df["date"] < game_date)
        ]

        if team_feats.empty:
            continue

        # Take most recent snapshot before game
        latest = team_feats.iloc[-1]

        row = {
            "game_id": game_id,
            "game_date": game_date,
            "team_id": team_id,
        }
        for col in FEATURE_COLS:
            row[col] = latest.get(col, np.nan)

        aligned_rows.append(row)

    if not aligned_rows:
        return pd.DataFrame()

    return pd.DataFrame(aligned_rows)


def compute_clv_correlations(
    features_df: pd.DataFrame,
    backtest_df: pd.DataFrame,
    season: int,
) -> dict:
    """Compute Pearson correlation of each feature with CLV.

    Merges on game_id and computes correlations with p-values.

    Returns:
        Dict with feature -> (correlation, p_value, n_obs) mappings.
    """
    merged = features_df.merge(
        backtest_df[["game_id", "clv"]],
        on="game_id",
        how="inner",
    )

    if len(merged) < 10:
        logger.warning("Season %d: only %d merged rows, skipping correlations", season, len(merged))
        return {}

    results = {}
    for col in FEATURE_COLS:
        valid = merged[[col, "clv"]].dropna()
        if len(valid) < 10:
            results[col] = (np.nan, np.nan, len(valid))
            continue
        # Skip if either column is constant (pearsonr undefined)
        if valid[col].std() == 0 or valid["clv"].std() == 0:
            results[col] = (np.nan, np.nan, len(valid))
            continue
        r, p = pearsonr(valid[col], valid["clv"])
        results[col] = (round(r, 4), round(p, 4), len(valid))

    return results


def generate_report(
    audit_records: list[dict],
    season_correlations: dict[int, dict],
    feature_stats: dict[int, pd.DataFrame],
    output_path: Path,
) -> None:
    """Generate markdown research report.

    Args:
        audit_records: Snapshot frequency audit per season.
        season_correlations: Per-season CLV correlations.
        feature_stats: Per-season feature distribution stats.
        output_path: Path to write the report.
    """
    lines = [
        "# Efficiency Trajectory Research Report",
        "",
        "## Snapshot Frequency Audit",
        "",
        "| Season | Unique Dates | Avg Gap (days) | Max Gap (days) | Date Range |",
        "|--------|-------------|----------------|----------------|------------|",
    ]

    for rec in audit_records:
        lines.append(
            f"| {rec['season']} | {rec['unique_dates']} | "
            f"{rec['avg_gap_days']} | {rec['max_gap_days']} | "
            f"{rec['min_date']} to {rec['max_date']} |"
        )

    lines.extend(["", "## Feature Distributions", ""])

    for season, stats_df in sorted(feature_stats.items()):
        lines.append(f"### Season {season}")
        lines.append("")
        lines.append(stats_df.to_markdown())
        lines.append("")

    lines.extend(["", "## Internal Correlation Matrix", ""])
    lines.append(
        "Computed across all seasons combined. "
        "High internal correlation (>0.8) suggests redundant features."
    )
    lines.append("")

    lines.extend(["", "## CLV Correlations by Season", ""])
    lines.append("| Season | Feature | Pearson r | p-value | N obs |")
    lines.append("|--------|---------|-----------|---------|-------|")

    for season, corrs in sorted(season_correlations.items()):
        for feat, (r, p, n) in corrs.items():
            lines.append(f"| {season} | {feat} | {r} | {p} | {n} |")

    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "*Placeholder: Analyze correlations above to determine which trajectory",
            "features add predictive value beyond the base Elo+Barttorvik model.",
            "Features with consistent positive CLV correlation across seasons",
            "are candidates for inclusion.*",
            "",
        ]
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Report written to %s", output_path)


def main() -> None:
    """Run the efficiency trajectory research pipeline."""
    logger.info("Starting Efficiency Trajectory research pipeline")

    # Build ESPN -> Barttorvik team name mapping
    espn_to_bart = build_espn_barttorvik_mapping(
        espn_data_dir=DATA_DIR / "raw" / "ncaab",
        bart_data_dir=DATA_DIR / "external" / "barttorvik",
    )
    logger.info("Team mapping: %d ESPN teams mapped to Barttorvik", len(espn_to_bart))

    audit_records: list[dict] = []
    season_correlations: dict[int, dict] = {}
    feature_stats: dict[int, pd.DataFrame] = {}
    valid_seasons = 0

    for season in VALID_SEASONS:
        logger.info("=" * 60)
        logger.info("Processing season %d", season)

        try:
            # Load data directly from DATA_DIR (not research_utils which
            # resolves paths relative to __file__, broken in worktrees)
            bart_path = (
                DATA_DIR / "external" / "barttorvik" / f"barttorvik_ratings_{season}.parquet"
            )
            games_path = DATA_DIR / "raw" / "ncaab" / f"ncaab_games_{season}.parquet"
            bart_df = pd.read_parquet(bart_path)
            bart_df["date"] = pd.to_datetime(bart_df["date"])
            bart_df = bart_df.sort_values(["team", "date"]).reset_index(drop=True)
            games_df = pd.read_parquet(games_path)
            games_df["date"] = pd.to_datetime(games_df["date"])
            games_df = games_df.sort_values("date").reset_index(drop=True)
        except FileNotFoundError as e:
            logger.warning("Season %d: data not found — %s", season, e)
            continue

        # Audit snapshot frequency
        audit = audit_snapshot_frequency(bart_df, season)
        audit_records.append(audit)
        logger.info(
            "Season %d: %d unique dates, avg gap %.1f days, max gap %.1f days",
            season,
            audit["unique_dates"],
            audit["avg_gap_days"],
            audit["max_gap_days"],
        )

        if audit["unique_dates"] < MIN_UNIQUE_DATES:
            logger.warning(
                "Season %d: only %d unique dates (< %d), SKIPPING",
                season,
                audit["unique_dates"],
                MIN_UNIQUE_DATES,
            )
            continue

        # Compute trajectory features per team
        try:
            season_features = compute_season_features(bart_df)
        except Exception:
            logger.exception("Season %d: failed to compute features", season)
            continue

        if season_features.empty:
            logger.warning("Season %d: no features computed", season)
            continue

        # PIT align to game schedule
        aligned = pit_align_to_games(season_features, games_df, espn_to_bart)
        logger.info(
            "Season %d: %d game-team rows aligned (%.1f%% of games)",
            season,
            len(aligned),
            100 * len(aligned) / max(len(games_df), 1),
        )

        if aligned.empty:
            logger.warning("Season %d: no aligned features", season)
            continue

        # Save per-season parquet
        aligned["season"] = season
        output_cols = ["season", "game_date", "game_id", "team_id"] + FEATURE_COLS
        output_path = RESEARCH_DIR / f"efficiency_trajectory_features_{season}.parquet"
        RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
        aligned[output_cols].to_parquet(output_path, index=False)
        logger.info("Saved %s (%d rows)", output_path.name, len(aligned))

        # Feature distribution stats
        stats = aligned[FEATURE_COLS].describe().T[["mean", "std", "min", "50%", "max"]]
        stats.columns = ["Mean", "Std", "Min", "Median", "Max"]
        feature_stats[season] = stats.round(4)

        # CLV correlations
        backtest_path = BACKTEST_DIR / f"ncaab_elo_backtest_{season}.parquet"
        if backtest_path.exists():
            backtest_df = pd.read_parquet(backtest_path)
            corrs = compute_clv_correlations(aligned, backtest_df, season)
            if corrs:
                season_correlations[season] = corrs
                logger.info("Season %d CLV correlations computed", season)
        else:
            logger.warning("Season %d: no backtest file found at %s", season, backtest_path)

        valid_seasons += 1

    # Abort if too few valid seasons
    if valid_seasons < 4:
        logger.error(
            "Only %d valid seasons (need >= 4). Aborting report generation.",
            valid_seasons,
        )
        sys.exit(1)

    # Internal correlation matrix (all seasons combined)
    all_features = []
    for season in VALID_SEASONS:
        p = RESEARCH_DIR / f"efficiency_trajectory_features_{season}.parquet"
        if p.exists():
            all_features.append(pd.read_parquet(p))

    if all_features:
        combined = pd.concat(all_features, ignore_index=True)
        corr_matrix = combined[FEATURE_COLS].corr().round(3)
        logger.info("Internal correlation matrix:\n%s", corr_matrix.to_string())

    # Generate report
    report_path = REPORT_DIR / "efficiency_trajectory_report.md"
    generate_report(audit_records, season_correlations, feature_stats, report_path)

    logger.info("Pipeline complete. %d seasons processed.", valid_seasons)


if __name__ == "__main__":
    main()
