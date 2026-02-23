"""A/B Comparison Framework for Feature Evaluation.

Compares Elo-only baseline (config A) against Elo + advanced features
(config B) using paired t-tests on per-bet returns for the same games.

With --barttorvik flag, also runs:
- Config C: Elo + Barttorvik efficiency ratings
- Config D: Elo + Barttorvik + advanced features

Paired comparison is far more powerful than unpaired because it controls
for game-level variance — both configs see the same games and odds.

CRITICAL: Must deepcopy(model) before each config run. The model mutates
during backtest (Elo updates), so running config A corrupts the model state
for config B unless you start from a fresh copy.

Usage:
    python scripts/ab_compare_features.py --seasons 2020 2021 2022 2023 2024 2025
    python scripts/ab_compare_features.py --seasons 2025 --feature-weight 1.0
    python scripts/ab_compare_features.py --barttorvik --seasons 2025
"""

from __future__ import annotations

import argparse
import copy
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from scipy import stats

from config.constants import THRESHOLDS
from config.settings import PROCESSED_DATA_DIR
from features.sport_specific.ncaab.advanced_features import NCABBFeatureEngine
from models.model_persistence import load_model
from scripts.backtest_ncaab_elo import (
    BarttovikCoeffs,
    load_odds_data,
    load_test_season,
    prepare_test_games,
    run_backtest_with_features,
    summarize_backtest,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Best real provider per season (from MEMORY.md)
BEST_PROVIDER: dict[int, int] = {
    2020: 40,  # DraftKings
    2021: 36,  # Unibet
    2022: 43,  # Caesars PA
    2023: 58,  # ESPN BET
    2024: 36,  # Unibet
    2025: 58,  # ESPN BET
}


@dataclass
class ABResult:
    """Result of an A/B comparison between two configurations."""

    config_a_name: str
    config_b_name: str
    season: int
    n_common_bets: int
    n_a_only: int
    n_b_only: int
    roi_a: float
    roi_b: float
    flat_roi_a: float
    flat_roi_b: float
    sharpe_a: float
    sharpe_b: float
    clv_a: float
    clv_b: float
    paired_t_stat: float
    paired_p_value: float
    improvement_significant: bool  # p < 0.10 (one-sided)
    roi_improvement: float  # roi_b - roi_a
    flat_roi_improvement: float  # flat_roi_b - flat_roi_a

    def summary_line(self) -> str:
        sig = "***" if self.paired_p_value < 0.05 else ("**" if self.paired_p_value < 0.10 else "")
        return (
            f"Season {self.season}: "
            f"flatA={self.flat_roi_a:+.2%} flatB={self.flat_roi_b:+.2%} "
            f"delta={self.flat_roi_improvement:+.2%} "
            f"t={self.paired_t_stat:.2f} p={self.paired_p_value:.4f} {sig}"
        )


def paired_comparison(
    results_a: pd.DataFrame,
    results_b: pd.DataFrame,
) -> dict:
    """Compute paired t-test on per-bet returns for common games.

    Only games where BOTH configs placed a bet are compared.
    This controls for game-level variance and is much more powerful
    than comparing aggregate ROI.

    Args:
        results_a: Backtest results from config A.
        results_b: Backtest results from config B.

    Returns:
        Dict with paired test statistics.
    """
    if results_a.empty or results_b.empty:
        return {
            "n_common": 0,
            "t_stat": 0.0,
            "p_value": 1.0,
            "mean_diff": 0.0,
        }

    # Compute per-bet return (P/L as fraction of stake)
    a = results_a.copy()
    b = results_b.copy()
    a["return"] = a["profit_loss"] / a["stake"]
    b["return"] = b["profit_loss"] / b["stake"]

    # Find common games
    common_ids = set(a["game_id"]) & set(b["game_id"])

    if len(common_ids) < 10:
        return {
            "n_common": len(common_ids),
            "t_stat": 0.0,
            "p_value": 1.0,
            "mean_diff": 0.0,
        }

    a_common = a[a["game_id"].isin(common_ids)].set_index("game_id")
    b_common = b[b["game_id"].isin(common_ids)].set_index("game_id")

    # Align on game_id
    shared_idx = a_common.index.intersection(b_common.index)
    returns_a = a_common.loc[shared_idx, "return"]
    returns_b = b_common.loc[shared_idx, "return"]

    diff = returns_b - returns_a
    t_stat, p_value = stats.ttest_rel(returns_b, returns_a)

    return {
        "n_common": len(shared_idx),
        "n_a_only": len(set(a["game_id"]) - common_ids),
        "n_b_only": len(set(b["game_id"]) - common_ids),
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "mean_diff": float(diff.mean()),
    }


def _run_config(
    base_model: object,
    games: list[dict],
    odds_lookup: dict[str, dict],
    min_edge: float,
    feature_engine: NCABBFeatureEngine | None = None,
    feature_weight: float = 0.0,
    barttorvik_df: pd.DataFrame | None = None,
    barttorvik_weight: float = 0.0,
    team_mapper: object | None = None,
    bart_coeffs: BarttovikCoeffs | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Run a single backtest config and return results + summary."""
    model = copy.deepcopy(base_model)
    model.apply_season_regression()
    results = run_backtest_with_features(
        model=model,
        games=games,
        feature_engine=feature_engine,
        feature_weight=feature_weight,
        barttorvik_df=barttorvik_df,
        barttorvik_weight=barttorvik_weight,
        team_mapper=team_mapper,
        bart_coeffs=bart_coeffs,
        min_edge=min_edge,
        odds_lookup=odds_lookup,
    )
    summary = summarize_backtest(results)
    return results, summary


def _make_ab_result(
    config_a_name: str,
    config_b_name: str,
    season: int,
    results_a: pd.DataFrame,
    results_b: pd.DataFrame,
    summary_a: dict,
    summary_b: dict,
) -> ABResult:
    """Build ABResult from two config runs."""
    paired = paired_comparison(results_a, results_b)
    flat_a = summary_a.get("flat_roi", 0)
    flat_b = summary_b.get("flat_roi", 0)
    return ABResult(
        config_a_name=config_a_name,
        config_b_name=config_b_name,
        season=season,
        n_common_bets=paired["n_common"],
        n_a_only=paired.get("n_a_only", 0),
        n_b_only=paired.get("n_b_only", 0),
        roi_a=summary_a.get("roi", 0),
        roi_b=summary_b.get("roi", 0),
        flat_roi_a=flat_a,
        flat_roi_b=flat_b,
        sharpe_a=summary_a.get("sharpe", 0),
        sharpe_b=summary_b.get("sharpe", 0),
        clv_a=summary_a.get("avg_clv", 0),
        clv_b=summary_b.get("avg_clv", 0),
        paired_t_stat=paired["t_stat"],
        paired_p_value=paired["p_value"],
        improvement_significant=paired["p_value"] < 0.10,
        roi_improvement=summary_b.get("roi", 0) - summary_a.get("roi", 0),
        flat_roi_improvement=flat_b - flat_a,
    )


def run_ab_comparison(
    model_path: Path,
    seasons: list[int],
    feature_weight: float = 1.0,
    min_edge: float = 0.05,
    use_barttorvik: bool = False,
    barttorvik_weight: float = 1.0,
    bart_coeffs: BarttovikCoeffs | None = None,
) -> list[ABResult]:
    """Run A/B comparison across multiple seasons.

    Config A: Elo-only baseline.
    Config B: Elo + advanced features.

    With use_barttorvik=True, also runs:
    Config C: Elo + Barttorvik.
    Config D: Elo + Barttorvik + advanced features.

    All configs compared against Config A (baseline).

    Args:
        model_path: Path to trained model pickle.
        seasons: List of season years to test.
        feature_weight: Weight for features in config B/D.
        min_edge: Minimum edge threshold.
        use_barttorvik: If True, run Barttorvik configs (C, D).
        barttorvik_weight: Weight for Barttorvik adjustment.

    Returns:
        List of ABResult, one per season per comparison pair.
    """
    saved = load_model(model_path)
    base_model = saved.model
    engine = NCABBFeatureEngine()
    results: list[ABResult] = []

    # Load Barttorvik data + mapper if needed
    bart_mapper = None
    bart_seasons: dict[int, pd.DataFrame] = {}
    if use_barttorvik:
        from pipelines.barttorvik_fetcher import load_cached_season
        from pipelines.team_name_mapping import espn_id_to_barttorvik

        bart_mapper = espn_id_to_barttorvik
        for s in seasons:
            cached = load_cached_season(s)
            if cached is not None:
                bart_seasons[s] = cached
                logger.info("Loaded Barttorvik ratings for %d: %d rows", s, len(cached))
            else:
                logger.warning("No Barttorvik data for season %d", s)

    for season in seasons:
        logger.info("=" * 60)
        logger.info("A/B COMPARISON — Season %d", season)
        logger.info("=" * 60)

        # Load data
        try:
            df_raw = load_test_season(season)
        except FileNotFoundError:
            logger.warning("No data for season %d, skipping", season)
            continue

        games = prepare_test_games(df_raw)
        provider = BEST_PROVIDER.get(season, 58)
        odds_lookup = load_odds_data(season, provider_id=provider)

        if not odds_lookup:
            logger.warning("No odds for season %d, skipping", season)
            continue

        # ---- Config A: Elo-only baseline ----
        results_a, summary_a = _run_config(
            base_model,
            games,
            odds_lookup,
            min_edge,
        )

        # ---- Config B: Elo + features ----
        results_b, summary_b = _run_config(
            base_model,
            games,
            odds_lookup,
            min_edge,
            feature_engine=engine,
            feature_weight=feature_weight,
        )

        ab = _make_ab_result(
            "elo_only",
            f"elo+features_w{feature_weight}",
            season,
            results_a,
            results_b,
            summary_a,
            summary_b,
        )
        results.append(ab)
        logger.info("[A vs B] %s", ab.summary_line())

        # ---- Config C: Elo + Barttorvik (if enabled) ----
        if use_barttorvik and season in bart_seasons:
            bart_df = bart_seasons[season]

            results_c, summary_c = _run_config(
                base_model,
                games,
                odds_lookup,
                min_edge,
                barttorvik_df=bart_df,
                barttorvik_weight=barttorvik_weight,
                team_mapper=bart_mapper,
                bart_coeffs=bart_coeffs,
            )

            ac = _make_ab_result(
                "elo_only",
                f"elo+bart_w{barttorvik_weight}",
                season,
                results_a,
                results_c,
                summary_a,
                summary_c,
            )
            results.append(ac)
            logger.info("[A vs C] %s", ac.summary_line())

            # ---- Config D: Elo + Barttorvik + features ----
            results_d, summary_d = _run_config(
                base_model,
                games,
                odds_lookup,
                min_edge,
                feature_engine=engine,
                feature_weight=feature_weight,
                barttorvik_df=bart_df,
                barttorvik_weight=barttorvik_weight,
                team_mapper=bart_mapper,
                bart_coeffs=bart_coeffs,
            )

            ad = _make_ab_result(
                "elo_only",
                "elo+bart+feat",
                season,
                results_a,
                results_d,
                summary_a,
                summary_d,
            )
            results.append(ad)
            logger.info("[A vs D] %s", ad.summary_line())

        # Update base_model with this season's games (for next season)
        model_update = copy.deepcopy(base_model)
        model_update.apply_season_regression()
        for game in games:
            model_update.update_game(
                game["home"],
                game["away"],
                game["home_score"],
                game["away_score"],
                game["neutral_site"],
            )
        base_model = model_update

    return results


def print_summary(results: list[ABResult]) -> None:
    """Print formatted summary of A/B comparison results."""
    if not results:
        print("No results to display.")
        return

    # Group results by comparison pair (config_b_name)
    pairs: dict[str, list[ABResult]] = {}
    for r in results:
        pairs.setdefault(r.config_b_name, []).append(r)

    for pair_name, pair_results in pairs.items():
        print(f"\n{'=' * 90}")
        print(f"COMPARISON: {pair_results[0].config_a_name} vs {pair_name}")
        print(f"{'=' * 90}")

        print(
            f"\n{'Season':<8} {'Common':<8} {'FlatA':>8} {'FlatB':>8} "
            f"{'Delta':>8} {'KellyA':>8} {'KellyB':>8} "
            f"{'t-stat':>8} {'p-value':>8} {'Sig':>5}"
        )
        print("-" * 96)

        for r in pair_results:
            sig = "***" if r.paired_p_value < 0.05 else ("**" if r.paired_p_value < 0.10 else "")
            print(
                f"{r.season:<8} {r.n_common_bets:<8} "
                f"{r.flat_roi_a:>+7.2%} {r.flat_roi_b:>+7.2%} "
                f"{r.flat_roi_improvement:>+7.2%} "
                f"{r.roi_a:>+7.2%} {r.roi_b:>+7.2%} "
                f"{r.paired_t_stat:>8.2f} {r.paired_p_value:>8.4f} {sig:>5}"
            )

        # Pooled statistics for this pair (using flat ROI as primary)
        valid = [r for r in pair_results if r.n_common_bets > 0]
        if len(valid) >= 3:
            flat_diffs = [r.flat_roi_improvement for r in valid]
            t, p = stats.ttest_1samp(flat_diffs, 0)
            mean_flat_a = np.mean([r.flat_roi_a for r in valid])
            mean_flat_b = np.mean([r.flat_roi_b for r in valid])
            print(
                f"\n  Pooled flat-stake: A={mean_flat_a:+.2%}, B={mean_flat_b:+.2%}, "
                f"delta={mean_flat_b - mean_flat_a:+.2%}"
            )
            print(f"  Paired t-test: t={t:.2f}, p={p:.4f} (two-sided), " f"p={p/2:.4f} (one-sided)")
            if p < 0.05:
                print("  *** STATISTICALLY SIGNIFICANT (p < 0.05) ***")
            elif p < 0.10:
                print("  ** Marginally significant (p < 0.10) **")
            else:
                print("     Not significant at p < 0.10")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="A/B comparison: Elo-only vs Elo + features / Barttorvik"
    )
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=[2020, 2021, 2022, 2023, 2024, 2025],
    )
    parser.add_argument("--feature-weight", type=float, default=1.0)
    parser.add_argument("--min-edge", type=float, default=THRESHOLDS.MIN_EDGE_SPREAD)
    parser.add_argument(
        "--barttorvik",
        action="store_true",
        help="Include Barttorvik configs (C: Elo+Bart, D: Elo+Bart+features)",
    )
    parser.add_argument(
        "--barttorvik-weight",
        type=float,
        default=1.0,
        help="Weight for Barttorvik probability adjustment (default: 1.0)",
    )
    args = parser.parse_args()

    model_path = PROCESSED_DATA_DIR / "ncaab_elo_model.pkl"
    if not model_path.exists():
        logger.error("No trained model found at %s", model_path)
        sys.exit(1)

    results = run_ab_comparison(
        model_path=model_path,
        seasons=args.seasons,
        feature_weight=args.feature_weight,
        min_edge=args.min_edge,
        use_barttorvik=args.barttorvik,
        barttorvik_weight=args.barttorvik_weight,
    )

    print_summary(results)


if __name__ == "__main__":
    main()
