"""Research pipeline: Late-Season Loss Features for NCAAB Tournament Prep.

Computes late-season loss features per season, merges with baseline backtest
CLV, and produces a correlation report.

Usage:
    python scripts/research_late_season_losses.py

Output:
    - data/research/late_season_loss_features_{season}.parquet (per season)
    - docs/research/late_season_losses_report.md (analysis report)

Error handling:
    - If a season fails, logs error and continues
    - If fewer than 4 valid seasons complete, aborts with error
    - COVID gap filtering applied for 2021 season only
"""

from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# Project root (resolve from script location)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Add project root to path for imports
sys.path.insert(0, str(PROJECT_ROOT))

from features.sport_specific.ncaab.late_season_losses import (
    ALL_LOSS_FEATURE_NAMES,
    compute_all_loss_features,
)
from features.sport_specific.ncaab.research_utils import (
    VALID_SEASONS,
    filter_covid_gaps,
    load_barttorvik_snapshots,
    load_season_games,
    pit_opponent_barthag,
)

# Directories
DATA_DIR = PROJECT_ROOT / "data"
RESEARCH_DIR = DATA_DIR / "research"
BACKTEST_DIR = DATA_DIR / "backtests"
REPORT_DIR = PROJECT_ROOT / "docs" / "research"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Features that require opp_barthag
BARTHAG_FEATURES = {"weighted_quality_loss_10g", "bad_loss_weighted_10g"}


def compute_season_features(season: int) -> pd.DataFrame | None:
    """Compute all late-season loss features for a single season.

    Returns DataFrame with columns: season, game_date, game_id, team_id,
    + all 6 feature columns. Returns None on failure.
    """
    logger.info("Processing season %d...", season)

    try:
        games = load_season_games(season)
        bart_df = load_barttorvik_snapshots(season)
    except FileNotFoundError as e:
        logger.error("Data not found for season %d: %s", season, e)
        return None

    all_features = []

    for team_id, team_games in games.groupby("team_id"):
        team_games = team_games.sort_values("date").reset_index(drop=True)

        # For 2021, apply COVID gap filtering
        if season == 2021:
            team_games = filter_covid_gaps(team_games)
            # Exclude games after COVID gaps from rolling windows
            # Keep only non-gap games for feature computation
            if "covid_gap" in team_games.columns:
                team_games = team_games[~team_games["covid_gap"]].reset_index(drop=True)

        if len(team_games) < 11:
            # Need at least 11 games (10-game window + 1 shift)
            continue

        # Compute PIT opponent barthag for each game
        opp_barthag_values = []
        for _, row in team_games.iterrows():
            opp_b = pit_opponent_barthag(bart_df, row["opponent_id"], row["date"])
            opp_barthag_values.append(opp_b)

        opp_barthag = pd.Series(opp_barthag_values, index=team_games.index)

        # If too many NaN barthag values, compute without barthag features
        non_null_pct = opp_barthag.notna().mean()
        if non_null_pct < 0.5:
            features = compute_all_loss_features(team_games, opp_barthag=None)
        else:
            features = compute_all_loss_features(team_games, opp_barthag=opp_barthag)

        # Attach metadata
        features["season"] = season
        features["game_date"] = team_games["date"].values
        features["game_id"] = team_games["game_id"].values
        features["team_id"] = team_games["team_id"].values

        all_features.append(features)

    if not all_features:
        logger.error("No teams processed for season %d", season)
        return None

    result = pd.concat(all_features, ignore_index=True)

    # Reorder columns: metadata first, then features
    meta_cols = ["season", "game_date", "game_id", "team_id"]
    feature_cols = [c for c in result.columns if c not in meta_cols]
    result = result[meta_cols + feature_cols]

    logger.info("Season %d: %d rows, %d teams", season, len(result), result["team_id"].nunique())
    return result


def save_season_features(df: pd.DataFrame, season: int) -> Path:
    """Save per-season feature parquet."""
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    path = RESEARCH_DIR / f"late_season_loss_features_{season}.parquet"
    df.to_parquet(path, index=False)
    logger.info("Saved %s (%d rows)", path.name, len(df))
    return path


def load_backtest(season: int) -> pd.DataFrame | None:
    """Load baseline backtest results for a season."""
    path = BACKTEST_DIR / f"ncaab_elo_backtest_{season}.parquet"
    if not path.exists():
        logger.warning("Backtest not found: %s", path)
        return None
    return pd.read_parquet(path)


def compute_clv_correlations(
    features_df: pd.DataFrame,
    backtest_df: pd.DataFrame,
    feature_cols: list[str],
) -> dict[str, dict[str, float]]:
    """Compute Pearson correlation of each feature with CLV.

    Returns dict mapping feature name -> {corr, pvalue, n}.
    """
    # Backtest has one row per bet (game_id is for the game, bet_side picks team)
    # We need to merge on game_id + team alignment
    # The backtest bet_side is which side was bet — merge features by game_id
    # For simplicity, merge features with backtest on game_id and use the
    # features for the team that was bet on.

    # The backtest uses game_id and bet_side (home/away).
    # Features have game_id + team_id. We need to match.
    # bet_side in backtest is 'home' or 'away', and the game has home/away columns.

    # Expand backtest: for bet_side='home', the team is backtest['home']
    # for bet_side='away', the team is backtest['away']
    bt = backtest_df.copy()
    bt["bet_team"] = np.where(bt["bet_side"] == "home", bt["home"], bt["away"])

    # Merge
    merged = bt.merge(
        features_df,
        left_on=["game_id", "bet_team"],
        right_on=["game_id", "team_id"],
        how="inner",
        suffixes=("_bt", "_feat"),
    )

    results = {}
    for col in feature_cols:
        if col not in merged.columns:
            continue
        valid = merged[["clv", col]].dropna()
        if len(valid) < 30:
            results[col] = {"corr": np.nan, "pvalue": np.nan, "n": len(valid)}
            continue
        # Suppress ConstantInputWarning when CLV column is all zeros
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", stats.ConstantInputWarning)
            corr, pval = stats.pearsonr(valid[col], valid["clv"])
        results[col] = {"corr": float(corr), "pvalue": float(pval), "n": len(valid)}

    return results


def generate_report(
    all_features: dict[int, pd.DataFrame],
    all_correlations: dict[int, dict[str, dict[str, float]]],
    feature_cols: list[str],
) -> str:
    """Generate markdown report."""
    lines = [
        "# Late-Season Loss Features — Research Report",
        "",
        "## Overview",
        "",
        f"Seasons analyzed: {sorted(all_features.keys())}",
        f"Features computed: {len(feature_cols)}",
        "",
    ]

    # Feature distributions
    lines.append("## Feature Distributions")
    lines.append("")
    lines.append("| Feature | Mean | Std | Min | Max |")
    lines.append("|---------|------|-----|-----|-----|")

    combined = pd.concat(all_features.values(), ignore_index=True)
    for col in feature_cols:
        if col not in combined.columns:
            continue
        s = combined[col].dropna()
        if len(s) == 0:
            lines.append(f"| {col} | N/A | N/A | N/A | N/A |")
        else:
            lines.append(
                f"| {col} | {s.mean():.4f} | {s.std():.4f} | {s.min():.4f} | {s.max():.4f} |"
            )
    lines.append("")

    # Internal correlation matrix
    lines.append("## Internal Correlation Matrix")
    lines.append("")
    available_cols = [c for c in feature_cols if c in combined.columns]
    if available_cols:
        corr_matrix = combined[available_cols].corr()
        lines.append("| | " + " | ".join(available_cols) + " |")
        lines.append("|" + "---|" * (len(available_cols) + 1))
        for row_col in available_cols:
            row_vals = " | ".join(f"{corr_matrix.loc[row_col, c]:.3f}" for c in available_cols)
            lines.append(f"| {row_col} | {row_vals} |")
    lines.append("")

    # Per-season CLV correlations
    lines.append("## Per-Season Univariate CLV Correlations")
    lines.append("")
    lines.append("| Season | Feature | Pearson r | p-value | n |")
    lines.append("|--------|---------|-----------|---------|---|")
    for season in sorted(all_correlations.keys()):
        corrs = all_correlations[season]
        for col in feature_cols:
            if col not in corrs:
                continue
            c = corrs[col]
            r_str = f"{c['corr']:.4f}" if not np.isnan(c["corr"]) else "N/A"
            p_str = f"{c['pvalue']:.4f}" if not np.isnan(c["pvalue"]) else "N/A"
            lines.append(f"| {season} | {col} | {r_str} | {p_str} | {c['n']} |")
    lines.append("")

    # Pooled correlations
    lines.append("## Pooled CLV Correlations (All Seasons)")
    lines.append("")
    lines.append("| Feature | Pearson r | p-value | n |")
    lines.append("|---------|-----------|---------|---|")

    # Recompute pooled from all_correlations by weighting
    # Actually simpler to compute from combined data — but we don't have CLV here.
    # Summarize from per-season instead: compute weighted average
    for col in feature_cols:
        total_n = 0
        weighted_r = 0.0
        for season in all_correlations:
            if col in all_correlations[season]:
                c = all_correlations[season][col]
                if not np.isnan(c["corr"]) and c["n"] > 0:
                    weighted_r += c["corr"] * c["n"]
                    total_n += c["n"]
        if total_n > 0:
            avg_r = weighted_r / total_n
            lines.append(f"| {col} | {avg_r:.4f} | — | {total_n} |")
        else:
            lines.append(f"| {col} | N/A | N/A | 0 |")
    lines.append("")

    # Recommendation placeholder
    lines.append("## Recommendations")
    lines.append("")
    lines.append("_TODO: Review correlations and decide which features to include in_")
    lines.append("_the tournament model. Key questions:_")
    lines.append("")
    lines.append("1. Which features show consistent positive CLV correlation across seasons?")
    lines.append("2. Are any features redundant (high internal correlation)?")
    lines.append("3. What is the marginal lift over the base Elo+Barttorvik model?")
    lines.append("4. Should features be used raw or as interaction terms?")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    """Run the full late-season loss research pipeline."""
    all_features: dict[int, pd.DataFrame] = {}
    all_correlations: dict[int, dict[str, dict[str, float]]] = {}
    feature_cols = list(ALL_LOSS_FEATURE_NAMES)

    for season in VALID_SEASONS:
        try:
            df = compute_season_features(season)
            if df is None:
                continue

            save_season_features(df, season)
            all_features[season] = df

            # Load backtest and compute CLV correlations
            bt = load_backtest(season)
            if bt is not None and "clv" in bt.columns:
                avail_features = [c for c in feature_cols if c in df.columns]
                corrs = compute_clv_correlations(df, bt, avail_features)
                all_correlations[season] = corrs
                logger.info(
                    "Season %d CLV correlations computed for %d features",
                    season,
                    len(corrs),
                )
            else:
                logger.warning("No CLV data for season %d", season)

        except Exception:
            logger.exception("Failed processing season %d", season)
            continue

    # Check minimum seasons
    if len(all_features) < 4:
        logger.error(
            "Only %d valid seasons (need >= 4). Aborting report generation.",
            len(all_features),
        )
        sys.exit(1)

    # Generate report
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report = generate_report(all_features, all_correlations, feature_cols)
    report_path = REPORT_DIR / "late_season_losses_report.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info("Report saved to %s", report_path)

    # Summary
    logger.info("=" * 60)
    logger.info("Pipeline complete: %d seasons processed", len(all_features))
    total_rows = sum(len(df) for df in all_features.values())
    logger.info("Total feature rows: %d", total_rows)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
