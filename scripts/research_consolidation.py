"""Research Consolidation: Combine Late-Season Losses + Efficiency Trajectory.

Runs AFTER both research agents complete. Merges feature sets,
runs cross-correlation analysis, VIF checks, and combined evaluation.

Usage:
    venv/Scripts/python.exe scripts/research_consolidation.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from scipy import stats

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RESEARCH_DIR = PROJECT_ROOT / "data" / "research"
REPORT_DIR = PROJECT_ROOT / "docs" / "research"
BACKTEST_DIR = PROJECT_ROOT / "data" / "backtests"
VALID_SEASONS = (2021, 2022, 2023, 2024, 2025)

LOSS_COLS = [
    "late_loss_count_5g",
    "late_loss_count_10g",
    "loss_margin_mean_10g",
    "weighted_quality_loss_10g",
    "bad_loss_weighted_10g",
    "home_loss_rate_10g",
]
TRAJ_COLS = [
    "adj_o_slope_10s",
    "adj_d_slope_10s",
    "net_efficiency_slope_10s",
    "barthag_delta_10s",
    "barthag_delta_20s",
    "rank_change_20s",
]
ALL_FEATURE_COLS = LOSS_COLS + TRAJ_COLS


def compute_vif(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Compute Variance Inflation Factor for each feature."""
    clean = df[columns].dropna()
    if len(clean) < len(columns) + 10:
        return pd.DataFrame({"feature": columns, "vif": [np.nan] * len(columns)})

    vifs = []
    for i, col in enumerate(columns):
        others = [c for j, c in enumerate(columns) if j != i]
        y = clean[col].values
        x_mat = clean[others].values
        x_mat = np.column_stack([np.ones(len(x_mat)), x_mat])
        try:
            beta, _, _, _ = np.linalg.lstsq(x_mat, y, rcond=None)
            y_pred = x_mat @ beta
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r_sq = 1 - ss_res / ss_tot if ss_tot > 0 else 0
            vif = 1 / (1 - r_sq) if r_sq < 1 else np.inf
        except np.linalg.LinAlgError:
            vif = np.nan
        vifs.append(vif)

    return pd.DataFrame({"feature": columns, "vif": vifs})


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Load both feature sets
    loss_dfs = []
    traj_dfs = []

    for season in VALID_SEASONS:
        loss_path = RESEARCH_DIR / f"late_season_loss_features_{season}.parquet"
        traj_path = RESEARCH_DIR / f"efficiency_trajectory_features_{season}.parquet"

        if loss_path.exists():
            loss_dfs.append(pd.read_parquet(loss_path))
        else:
            logger.warning("Missing loss features for %d", season)

        if traj_path.exists():
            traj_dfs.append(pd.read_parquet(traj_path))
        else:
            logger.warning("Missing trajectory features for %d", season)

    has_loss = len(loss_dfs) > 0
    has_traj = len(traj_dfs) > 0

    if not has_loss and not has_traj:
        logger.error("ABORT: Neither research item produced results")
        sys.exit(1)

    lines = ["# Consolidated Tournament Research Report\n\n"]
    lines.append(
        f"Generated from {len(loss_dfs)} loss seasons + {len(traj_dfs)} trajectory seasons\n\n"
    )

    if has_loss and has_traj:
        loss_all = pd.concat(loss_dfs, ignore_index=True)
        traj_all = pd.concat(traj_dfs, ignore_index=True)

        logger.info("Loss features: %d rows", len(loss_all))
        logger.info("Trajectory features: %d rows", len(traj_all))

        # Merge on shared keys
        merge_keys = ["season", "game_id", "team_id"]
        # Normalize column names for merge
        if "game_date" in loss_all.columns and "game_date" not in traj_all.columns:
            pass  # Only need shared keys
        if "game_date" in traj_all.columns:
            traj_all = traj_all.rename(columns={"game_date": "game_date_traj"})

        merged = loss_all.merge(
            traj_all,
            on=[k for k in merge_keys if k in loss_all.columns and k in traj_all.columns],
            how="inner",
            suffixes=("", "_traj"),
        )
        logger.info("Merged: %d rows", len(merged))

        # Cross-correlation matrix
        available = [c for c in ALL_FEATURE_COLS if c in merged.columns]
        if available:
            corr = merged[available].corr()
            lines.append("## Cross-Correlation Matrix\n\n```text\n")
            lines.append(corr.round(3).to_string())
            lines.append("\n```\n\n")

            # Flag high correlations
            lines.append("## High Correlations (|r| > 0.7)\n\n")
            found_high = False
            for i, c1 in enumerate(available):
                for c2 in available[i + 1 :]:
                    r = corr.loc[c1, c2]
                    if abs(r) > 0.7:
                        lines.append(f"- **{c1}** vs **{c2}**: r={r:.3f} — REDUNDANCY FLAG\n")
                        found_high = True
            if not found_high:
                lines.append("None found. All feature pairs have |r| < 0.7.\n")

            # VIF analysis
            vif_df = compute_vif(merged, available)
            lines.append("\n## VIF Analysis\n\n")
            lines.append("| Feature | VIF | Flag |\n|---------|-----|------|\n")
            for _, row in vif_df.iterrows():
                flag = "HIGH" if row["vif"] > 5 else ""
                lines.append(f"| {row['feature']} | {row['vif']:.2f} | {flag} |\n")

        # Per-season combined evaluation against baseline
        lines.append("\n## Combined Feature Evaluation vs Baseline\n\n")
        for season in VALID_SEASONS:
            bt_path = BACKTEST_DIR / f"ncaab_elo_backtest_{season}.parquet"
            if not bt_path.exists():
                continue

            baseline = pd.read_parquet(bt_path)
            season_merged = merged[merged["season"] == season]
            combined = baseline.merge(
                season_merged, on="game_id", how="inner", suffixes=("", "_res")
            )

            if len(combined) < 50:
                lines.append(f"### Season {season}: insufficient merged rows ({len(combined)})\n\n")
                continue

            lines.append(f"### Season {season} (n={len(combined)})\n\n")
            baseline_clv = combined["clv"].mean()
            baseline_roi = combined["profit_loss"].sum() / combined["stake"].sum()
            lines.append(f"- Baseline CLV: {baseline_clv:.4f}\n")
            lines.append(f"- Baseline ROI: {baseline_roi:.2%}\n\n")

            # CLV has zero variance for 2021-2023 — check and skip
            if combined["clv"].std() < 1e-8:
                lines.append(
                    "- CLV has zero variance (simulated odds) — correlations not meaningful\n\n"
                )
                continue

            lines.append("| Feature | r(CLV) | p-value | Sig? |\n")
            lines.append("|---------|--------|---------|------|\n")
            for col in available:
                if col in combined.columns:
                    valid = combined[[col, "clv"]].dropna()
                    if len(valid) >= 30:
                        r, p = stats.pearsonr(valid[col], valid["clv"])
                        sig = "**YES**" if p < 0.05 else ""
                        lines.append(f"| {col} | {r:.4f} | {p:.4f} | {sig} |\n")
            lines.append("\n")

    elif has_loss:
        lines.append("## Only Late-Season Loss results available\n\n")
        lines.append("See `late_season_losses_report.md` for details.\n\n")
    else:
        lines.append("## Only Efficiency Trajectory results available\n\n")
        lines.append("See `efficiency_trajectory_report.md` for details.\n\n")

    # Convergence-based promotion gate (replaces CLV-only gate)
    lines.append("## Promotion Gate — Convergence-Based\n\n")
    lines.append("### Primary Gates (ALL must pass)\n\n")
    lines.append("- [ ] Pooled ROI lift > 0% (walk-forward OOS)\n")
    lines.append("- [ ] Per-season consistency: positive ROI lift in >= 3/5 seasons\n")
    lines.append("- [ ] Do-no-harm: no season with ROI lift < -5%\n")
    lines.append("- [ ] Brier improvement on betted subset (walk-forward OOS)\n")
    lines.append("- [ ] Brier per-season consistency: improved in >= 3/5 seasons\n")
    lines.append("- [ ] >= 200 bets per test season\n\n")
    lines.append("### Structural Gates (at least 1 must pass)\n\n")
    lines.append("- [ ] Edge-outcome Spearman rho > 0 (pooled)\n")
    lines.append("- [ ] Edge-bucket monotonicity (median split)\n\n")
    lines.append("### Hard Blocks (any triggers REJECT)\n\n")
    lines.append("- [ ] Edge-outcome rho < 0 → REJECT\n")
    lines.append("- [ ] Augmented-only bets ROI < -10% → REJECT\n")
    lines.append("- [ ] Removing 2021 flips ROI sign → NEEDS_REVIEW\n\n")
    lines.append("### Supplemental (informational, non-blocking)\n\n")
    lines.append("- [ ] VIF < 5 for all selected features\n")
    lines.append("- [ ] No feature correlated > 0.7 with existing model features\n")
    lines.append("- [ ] In-sample ROI <= 2x OOS ROI\n")
    lines.append("- [ ] User review completed\n")

    report = "".join(lines)
    report_path = REPORT_DIR / "consolidated_tournament_research.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info("Consolidated report written to %s", report_path)


if __name__ == "__main__":
    main()
