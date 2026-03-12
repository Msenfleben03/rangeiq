"""Convergence-Based Promotion Gate Evaluation.

Evaluates tournament research features (late-season losses + efficiency
trajectory) against the convergence-based promotion gate using walk-forward
OOS methodology.

Approach:
    1. Load baseline backtests and research features per season
    2. Merge features with baseline bets (game_id + team alignment)
    3. Walk-forward: train feature weights on prior seasons, test on current
    4. Recompute adjusted probabilities and Kelly stakes
    5. Compare ROI, Brier, edge-outcome correlation vs baseline
    6. Check all promotion gate criteria
    7. Generate evaluation report

Usage:
    venv/Scripts/python.exe scripts/research_evaluation.py
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

from betting.odds_converter import american_to_decimal, fractional_kelly

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BACKTEST_DIR = PROJECT_ROOT / "data" / "backtests"
RESEARCH_DIR = PROJECT_ROOT / "data" / "research"
REPORT_DIR = PROJECT_ROOT / "docs" / "research"
VALID_SEASONS = (2021, 2022, 2023, 2024, 2025)

# Feature candidates — one representative per redundancy cluster
# (chosen based on CLV correlation strength and low cross-correlation)
CANDIDATE_FEATURES = [
    "late_loss_count_10g",
    "loss_margin_mean_10g",
    "weighted_quality_loss_10g",
    "home_loss_rate_10g",
    "barthag_delta_10s",
]

ALL_RESEARCH_FEATURES = [
    "late_loss_count_5g",
    "late_loss_count_10g",
    "loss_margin_mean_10g",
    "weighted_quality_loss_10g",
    "bad_loss_weighted_10g",
    "home_loss_rate_10g",
    "adj_o_slope_10s",
    "adj_d_slope_10s",
    "net_efficiency_slope_10s",
    "barthag_delta_10s",
    "barthag_delta_20s",
    "rank_change_20s",
]


def load_season_data(season: int) -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    """Load baseline backtest and merged research features for a season."""
    bt_path = BACKTEST_DIR / f"ncaab_elo_backtest_{season}.parquet"
    if not bt_path.exists():
        return None, None

    bt = pd.read_parquet(bt_path)

    # Load both feature sets
    loss_path = RESEARCH_DIR / f"late_season_loss_features_{season}.parquet"
    traj_path = RESEARCH_DIR / f"efficiency_trajectory_features_{season}.parquet"

    dfs = []
    if loss_path.exists():
        dfs.append(pd.read_parquet(loss_path))
    if traj_path.exists():
        dfs.append(pd.read_parquet(traj_path))

    if not dfs:
        return bt, None

    if len(dfs) == 2:
        # Merge loss + trajectory on shared keys
        merge_keys = ["season", "game_id", "team_id"]
        feats = dfs[0].merge(dfs[1], on=merge_keys, how="inner", suffixes=("", "_traj"))
    else:
        feats = dfs[0]

    return bt, feats


def merge_features_with_bets(bt: pd.DataFrame, feats: pd.DataFrame) -> pd.DataFrame:
    """Merge research features with baseline bets on game_id + team.

    The backtest has bet_side (home/away) and home/away columns.
    Features have game_id + team_id. Match the bet team.
    """
    bt = bt.copy()
    bt["bet_team"] = np.where(bt["bet_side"] == "home", bt["home"], bt["away"])

    merged = bt.merge(
        feats,
        left_on=["game_id", "bet_team"],
        right_on=["game_id", "team_id"],
        how="inner",
        suffixes=("", "_feat"),
    )
    return merged


def brier_score(probs: np.ndarray, outcomes: np.ndarray) -> float:
    """Brier score: mean squared error of probability forecasts."""
    return float(np.mean((probs - outcomes) ** 2))


def train_feature_weights(
    train_df: pd.DataFrame,
    feature_cols: list[str],
) -> dict[str, float]:
    """Learn linear feature weights via OLS on training data.

    Model: outcome ~ model_prob + sum(w_i * feature_i)
    Returns dict of feature weights.
    """
    available = [c for c in feature_cols if c in train_df.columns]
    if not available:
        return {}

    outcome = (train_df["result"] == "win").astype(float).values
    model_prob = train_df["model_prob"].values

    # Residualize: regress outcome on model_prob, then regress residuals on features
    residual = outcome - model_prob

    weights = {}
    for col in available:
        valid_mask = train_df[col].notna()
        if valid_mask.sum() < 50:
            weights[col] = 0.0
            continue

        x = train_df.loc[valid_mask, col].values
        y = residual[valid_mask.values]

        # Standardize feature for comparable weights
        x_std = x.std()
        if x_std < 1e-10:
            weights[col] = 0.0
            continue

        x_norm = (x - x.mean()) / x_std

        # Simple OLS: w = cov(x,y) / var(x)
        w = np.cov(x_norm, y)[0, 1] / np.var(x_norm) if np.var(x_norm) > 0 else 0.0

        # Store weight in original scale
        weights[col] = w / x_std

    return weights


def apply_feature_adjustment(
    df: pd.DataFrame,
    weights: dict[str, float],
    feature_cols: list[str],
) -> np.ndarray:
    """Compute adjusted probabilities using learned feature weights."""
    adj = df["model_prob"].values.copy()

    for col in feature_cols:
        if col not in weights or col not in df.columns:
            continue
        w = weights[col]
        if w == 0.0:
            continue

        vals = df[col].fillna(0.0).values
        mean_val = vals[vals != 0].mean() if (vals != 0).any() else 0.0
        adj += w * (vals - mean_val)

    # Clamp to valid probability range
    adj = np.clip(adj, 0.01, 0.99)
    return adj


def compute_roi(df: pd.DataFrame, prob_col: str = "model_prob") -> float:
    """Compute flat-stake ROI from backtest results."""
    if df.empty or df["stake"].sum() == 0:
        return 0.0
    return float(df["profit_loss"].sum() / df["stake"].sum())


def compute_adjusted_roi(
    df: pd.DataFrame,
    adjusted_probs: np.ndarray,
    kelly_fraction: float = 0.25,
    max_bet: float = 0.03,
    bankroll: float = 5000.0,
) -> float:
    """Recompute ROI using adjusted probabilities for Kelly sizing.

    Same bet set, but stakes change based on adjusted confidence.
    """
    total_stake = 0.0
    total_pnl = 0.0

    for i, (_, row) in enumerate(df.iterrows()):
        adj_prob = adjusted_probs[i]
        decimal_odds = american_to_decimal(int(row["odds_placed"]))

        new_fraction = fractional_kelly(adj_prob, decimal_odds, kelly_fraction, max_bet)
        new_stake = bankroll * new_fraction

        if new_stake <= 0:
            continue

        total_stake += new_stake
        if row["result"] == "win":
            total_pnl += new_stake * (decimal_odds - 1)
        else:
            total_pnl -= new_stake

    return total_pnl / total_stake if total_stake > 0 else 0.0


def evaluate_season(
    test_df: pd.DataFrame,
    weights: dict[str, float],
    feature_cols: list[str],
) -> dict:
    """Evaluate augmented model on a single test season."""
    outcome = (test_df["result"] == "win").astype(float).values
    baseline_prob = test_df["model_prob"].values
    adjusted_prob = apply_feature_adjustment(test_df, weights, feature_cols)

    # Baseline metrics
    baseline_roi = compute_roi(test_df)
    baseline_brier = brier_score(baseline_prob, outcome)

    # Augmented metrics
    augmented_roi = compute_adjusted_roi(test_df, adjusted_prob)
    augmented_brier = brier_score(adjusted_prob, outcome)

    # Edge-outcome Spearman correlation
    edge = test_df["edge"].values
    rho_baseline, p_rho = stats.spearmanr(edge, outcome)

    # Augmented edge: adjusted_prob - implied_prob
    # Use original bet odds to compute implied prob
    from betting.odds_converter import american_to_implied_prob

    implied = np.array([american_to_implied_prob(int(o)) for o in test_df["odds_placed"]])
    aug_edge = adjusted_prob - implied
    rho_augmented, p_rho_aug = stats.spearmanr(aug_edge, outcome)

    # Edge-bucket monotonicity (median split)
    median_edge = np.median(aug_edge)
    low_edge_roi = compute_adjusted_roi(
        test_df[aug_edge <= median_edge],
        adjusted_prob[aug_edge <= median_edge],
    )
    high_edge_roi = compute_adjusted_roi(
        test_df[aug_edge > median_edge],
        adjusted_prob[aug_edge > median_edge],
    )
    monotonic = high_edge_roi > low_edge_roi

    return {
        "n_bets": len(test_df),
        "baseline_roi": baseline_roi,
        "augmented_roi": augmented_roi,
        "roi_lift": augmented_roi - baseline_roi,
        "baseline_brier": baseline_brier,
        "augmented_brier": augmented_brier,
        "brier_improvement": baseline_brier - augmented_brier,
        "edge_rho_baseline": rho_baseline,
        "edge_rho_augmented": rho_augmented,
        "edge_rho_p": p_rho_aug,
        "edge_monotonic": monotonic,
        "low_edge_roi": low_edge_roi,
        "high_edge_roi": high_edge_roi,
        "weights_used": {k: v for k, v in weights.items() if v != 0.0},
    }


def run_walk_forward_evaluation(
    feature_cols: list[str],
    label: str = "candidate",
) -> dict[int, dict]:
    """Run full walk-forward evaluation across all seasons.

    For each test season k:
        - Train weights on seasons < k
        - Evaluate on season k
    """
    # Load all data
    all_data: dict[int, pd.DataFrame] = {}
    for season in VALID_SEASONS:
        bt, feats = load_season_data(season)
        if bt is None or feats is None:
            logger.warning("Missing data for season %d", season)
            continue

        merged = merge_features_with_bets(bt, feats)
        if len(merged) < 50:
            logger.warning("Season %d: only %d merged rows, skipping", season, len(merged))
            continue

        all_data[season] = merged
        logger.info("Season %d: %d bets with features", season, len(merged))

    results: dict[int, dict] = {}

    for test_season in sorted(all_data.keys()):
        # Train on all prior seasons
        train_seasons = [s for s in all_data if s < test_season]

        if not train_seasons:
            # First season: use no feature adjustment (baseline)
            logger.info("Season %d: no prior data, using zero weights", test_season)
            weights = {col: 0.0 for col in feature_cols}
        else:
            train_df = pd.concat([all_data[s] for s in train_seasons], ignore_index=True)
            weights = train_feature_weights(train_df, feature_cols)
            logger.info(
                "Season %d: trained on %d bets from seasons %s",
                test_season,
                len(train_df),
                train_seasons,
            )

        test_df = all_data[test_season]
        season_result = evaluate_season(test_df, weights, feature_cols)
        season_result["train_seasons"] = train_seasons
        results[test_season] = season_result

        logger.info(
            "Season %d: ROI lift %+.2f%%, Brier improvement %+.6f, edge rho %.4f",
            test_season,
            season_result["roi_lift"] * 100,
            season_result["brier_improvement"],
            season_result["edge_rho_augmented"],
        )

    return results


def check_promotion_gate(results: dict[int, dict]) -> dict[str, dict]:
    """Check all convergence-based promotion gate criteria."""
    seasons = sorted(results.keys())
    n_seasons = len(seasons)

    # Primary Gates
    pooled_baseline_pnl = 0.0
    pooled_baseline_stake = 0.0
    pooled_aug_roi_num = 0.0
    pooled_aug_roi_den = 0.0

    roi_lifts = []
    brier_improvements = []

    for s in seasons:
        r = results[s]
        roi_lifts.append(r["roi_lift"])
        brier_improvements.append(r["brier_improvement"])
        pooled_baseline_pnl += r["baseline_roi"] * r["n_bets"]
        pooled_baseline_stake += r["n_bets"]
        pooled_aug_roi_num += r["augmented_roi"] * r["n_bets"]
        pooled_aug_roi_den += r["n_bets"]

    pooled_baseline_roi = (
        pooled_baseline_pnl / pooled_baseline_stake if pooled_baseline_stake > 0 else 0
    )
    pooled_aug_roi = pooled_aug_roi_num / pooled_aug_roi_den if pooled_aug_roi_den > 0 else 0
    pooled_roi_lift = pooled_aug_roi - pooled_baseline_roi

    positive_roi_seasons = sum(1 for x in roi_lifts if x > 0)
    worst_roi_lift = min(roi_lifts)
    positive_brier_seasons = sum(1 for x in brier_improvements if x > 0)
    pooled_brier_improvement = np.mean(brier_improvements)
    min_bets = min(results[s]["n_bets"] for s in seasons)

    # Structural Gates
    pooled_rho = np.mean([results[s]["edge_rho_augmented"] for s in seasons])
    any_monotonic = any(results[s]["edge_monotonic"] for s in seasons)

    # Hard Blocks
    rho_negative = pooled_rho < 0

    # Check 2021 sensitivity
    if 2021 in results and len(seasons) > 1:
        roi_lifts_no_2021 = [results[s]["roi_lift"] for s in seasons if s != 2021]
        pooled_lift_no_2021 = np.mean(roi_lifts_no_2021)
        sign_flip = (pooled_roi_lift > 0) != (pooled_lift_no_2021 > 0)
    else:
        sign_flip = False

    gate = {
        "primary": {
            "pooled_roi_lift_positive": {
                "pass": pooled_roi_lift > 0,
                "value": pooled_roi_lift,
            },
            "roi_consistency_3_of_5": {
                "pass": positive_roi_seasons >= 3,
                "value": f"{positive_roi_seasons}/{n_seasons}",
            },
            "do_no_harm": {
                "pass": worst_roi_lift >= -0.05,
                "value": worst_roi_lift,
            },
            "brier_improvement_pooled": {
                "pass": pooled_brier_improvement > 0,
                "value": pooled_brier_improvement,
            },
            "brier_consistency_3_of_5": {
                "pass": positive_brier_seasons >= 3,
                "value": f"{positive_brier_seasons}/{n_seasons}",
            },
            "sample_size_200": {
                "pass": min_bets >= 200,
                "value": min_bets,
            },
        },
        "structural": {
            "edge_rho_positive": {
                "pass": pooled_rho > 0,
                "value": pooled_rho,
            },
            "edge_monotonicity": {
                "pass": any_monotonic,
                "value": sum(1 for s in seasons if results[s]["edge_monotonic"]),
            },
        },
        "hard_blocks": {
            "rho_negative_reject": {
                "triggered": rho_negative,
                "value": pooled_rho,
            },
            "covid_sensitivity": {
                "triggered": sign_flip,
                "value": "sign flip" if sign_flip else "stable",
            },
        },
    }

    # Overall decision
    primary_pass = all(v["pass"] for v in gate["primary"].values())
    structural_pass = any(v["pass"] for v in gate["structural"].values())
    hard_block = any(v["triggered"] for v in gate["hard_blocks"].values())

    if hard_block:
        gate["decision"] = "REJECT"
    elif primary_pass and structural_pass:
        gate["decision"] = "PASS"
    elif primary_pass or structural_pass:
        gate["decision"] = "NEEDS_REVIEW"
    else:
        gate["decision"] = "FAIL"

    return gate


def generate_report(
    candidate_results: dict[int, dict],
    candidate_gate: dict,
    all_features_results: dict[int, dict],
    all_features_gate: dict,
) -> str:
    """Generate evaluation report."""
    lines = ["# Tournament Research — Promotion Gate Evaluation\n"]
    lines.append(f"Walk-forward OOS evaluation across seasons {list(VALID_SEASONS)}\n\n")

    for label, results, gate in [
        ("Candidate Features (5 selected)", candidate_results, candidate_gate),
        ("All 12 Features", all_features_results, all_features_gate),
    ]:
        lines.append(f"## {label}\n\n")
        lines.append(f"### Decision: **{gate['decision']}**\n\n")

        # Per-season results table
        lines.append("### Per-Season Results\n\n")
        lines.append(
            "| Season | Bets | Base ROI | Aug ROI | ROI Lift | Base Brier | Aug Brier | Brier Δ | Edge ρ | Monotonic |\n"
        )
        lines.append(
            "|--------|------|----------|---------|----------|------------|-----------|---------|--------|----------|\n"
        )
        for s in sorted(results.keys()):
            r = results[s]
            lines.append(
                f"| {s} | {r['n_bets']} | {r['baseline_roi']:.2%} | {r['augmented_roi']:.2%} "
                f"| {r['roi_lift']:+.2%} | {r['baseline_brier']:.4f} | {r['augmented_brier']:.4f} "
                f"| {r['brier_improvement']:+.6f} | {r['edge_rho_augmented']:.4f} "
                f"| {'Yes' if r['edge_monotonic'] else 'No'} |\n"
            )
        lines.append("\n")

        # Learned weights per season
        lines.append("### Walk-Forward Learned Weights\n\n")
        for s in sorted(results.keys()):
            r = results[s]
            w = r.get("weights_used", {})
            if w:
                lines.append(f"**{s}** (trained on {r['train_seasons']}):\n\n")
                lines.append("| Feature | Weight |\n|---------|--------|\n")
                for k, v in sorted(w.items()):
                    lines.append(f"| {k} | {v:.6f} |\n")
                lines.append("\n")
            else:
                lines.append(f"- **{s}**: no weights (first season)\n")
        lines.append("\n")

        # Gate checks
        lines.append("### Primary Gates (ALL must pass)\n\n")
        for name, check in gate["primary"].items():
            status = "PASS" if check["pass"] else "FAIL"
            lines.append(f"- [{status}] **{name}**: {check['value']}\n")
        lines.append("\n")

        lines.append("### Structural Gates (at least 1 must pass)\n\n")
        for name, check in gate["structural"].items():
            status = "PASS" if check["pass"] else "FAIL"
            lines.append(f"- [{status}] **{name}**: {check['value']}\n")
        lines.append("\n")

        lines.append("### Hard Blocks\n\n")
        for name, check in gate["hard_blocks"].items():
            status = "TRIGGERED" if check["triggered"] else "clear"
            lines.append(f"- [{status}] **{name}**: {check['value']}\n")
        lines.append("\n")

        # Edge-bucket detail
        lines.append("### Edge-Bucket ROI (Median Split)\n\n")
        lines.append("| Season | Low Edge ROI | High Edge ROI | Monotonic? |\n")
        lines.append("|--------|-------------|---------------|------------|\n")
        for s in sorted(results.keys()):
            r = results[s]
            lines.append(
                f"| {s} | {r['low_edge_roi']:.2%} | {r['high_edge_roi']:.2%} "
                f"| {'Yes' if r['edge_monotonic'] else 'No'} |\n"
            )
        lines.append("\n---\n\n")

    # Interpretation
    lines.append("## Interpretation Notes\n\n")
    lines.append("- **Walk-forward OOS**: Feature weights trained on prior seasons only\n")
    lines.append("- **ROI lift**: Same bet set, Kelly re-sized with adjusted probabilities\n")
    lines.append("- **Brier**: Computed on betted subset (not all games)\n")
    lines.append("- **Edge ρ**: Spearman correlation of augmented edge with outcome\n")
    lines.append("- **Monotonic**: High-edge bets have higher ROI than low-edge bets\n")
    lines.append("- First test season (2021) uses zero weights (no prior training data)\n\n")
    lines.append("### Limitations\n\n")
    lines.append("- Bet SET is unchanged — only Kelly sizing adjusts with new probabilities\n")
    lines.append("- True ROI lift requires full re-backtest with augmented model\n")
    lines.append("- Feature weights are simple OLS residualization, not the full model\n")

    return "".join(lines)


def main() -> None:
    """Run the full convergence-based promotion gate evaluation."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Run evaluation with candidate features (de-redundified)
    logger.info("=" * 60)
    logger.info("Evaluating CANDIDATE features (5 selected)")
    logger.info("=" * 60)
    candidate_results = run_walk_forward_evaluation(CANDIDATE_FEATURES, "candidate")
    candidate_gate = check_promotion_gate(candidate_results)
    logger.info("Candidate decision: %s", candidate_gate["decision"])

    # Run evaluation with ALL 12 features
    logger.info("=" * 60)
    logger.info("Evaluating ALL 12 features")
    logger.info("=" * 60)
    all_results = run_walk_forward_evaluation(ALL_RESEARCH_FEATURES, "all")
    all_gate = check_promotion_gate(all_results)
    logger.info("All features decision: %s", all_gate["decision"])

    # Generate report
    report = generate_report(candidate_results, candidate_gate, all_results, all_gate)
    report_path = REPORT_DIR / "promotion_gate_evaluation.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info("Report saved to %s", report_path)

    # Print summary
    print(f"\n{'=' * 60}")
    print("PROMOTION GATE EVALUATION SUMMARY")
    print(f"{'=' * 60}")

    for label, gate in [
        ("Candidate (5 features)", candidate_gate),
        ("All (12 features)", all_gate),
    ]:
        print(f"\n{label}: {gate['decision']}")
        for name, check in gate["primary"].items():
            status = "PASS" if check["pass"] else "FAIL"
            print(f"  [{status}] {name}: {check['value']}")


if __name__ == "__main__":
    main()
