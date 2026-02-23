"""Grid Search for KenPom Weight Tuning.

Searches over kenpom_weight, net_diff_coeff, and sos_coeff
to find the combination that maximizes flat-stake ROI while maintaining
statistical significance.

Two modes:
  - KenPom-only: Elo + KenPom (no Barttorvik)
  - Combined: Elo + Barttorvik (fixed best) + KenPom (searched)

Full grid: 5 weights x 4 net_coeffs x 4 sos_coeffs = 80 combos.
Quick mode: 12 combos on [2024, 2025] only.

Usage:
    python scripts/tune_kenpom_weights.py --quick
    python scripts/tune_kenpom_weights.py --seasons 2020 2021 2022 2023 2024 2025
    python scripts/tune_kenpom_weights.py --combined --quick
"""

from __future__ import annotations

import argparse
import copy
import csv
import json
import logging
import sys
import time
from dataclasses import dataclass
from itertools import product
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd
from scipy import stats

from config.constants import THRESHOLDS
from config.settings import PROCESSED_DATA_DIR
from models.model_persistence import load_model
from pipelines.barttorvik_fetcher import load_cached_season as load_bart_season
from pipelines.kenpom_fetcher import load_cached_season as load_kenpom_season
from pipelines.team_name_mapping import espn_id_to_barttorvik, espn_id_to_kenpom
from scripts.backtest_ncaab_elo import (
    BarttovikCoeffs,
    KenPomCoeffs,
    load_odds_data,
    load_test_season,
    prepare_test_games,
    run_backtest_with_features,
    summarize_backtest,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Best real provider per season (same as Barttorvik tuner)
BEST_PROVIDER: dict[int, int] = {
    2020: 40,  # DraftKings
    2021: 36,  # Unibet
    2022: 43,  # Caesars PA
    2023: 58,  # ESPN BET
    2024: 36,  # Unibet
    2025: 58,  # ESPN BET
}

# Best Barttorvik config from grid search (used in combined mode)
BEST_BART_WEIGHT = 1.5
BEST_BART_COEFFS = BarttovikCoeffs(net_diff_coeff=0.005, barthag_diff_coeff=0.20)


@dataclass
class KenPomGridPoint:
    """A single KenPom grid search point with results."""

    kenpom_weight: float
    net_diff_coeff: float
    sos_coeff: float
    combined_mode: bool
    seasons_tested: list[int]
    flat_roi_per_season: dict[int, float]
    pooled_flat_roi: float
    pooled_bets: int
    pooled_sharpe: float
    t_stat: float
    p_value: float


# -- Grid construction --

FULL_WEIGHTS = [0.25, 0.5, 0.75, 1.0, 1.5]
FULL_NET_COEFFS = [0.002, 0.003, 0.005, 0.008]
FULL_SOS_COEFFS = [0.0, 0.002, 0.005, 0.01]

QUICK_WEIGHTS = [0.5, 1.0, 1.5]
QUICK_NET_COEFFS = [0.003, 0.005]
QUICK_SOS_COEFFS = [0.0, 0.005]


def build_kenpom_grid(quick: bool = False) -> list[tuple[float, float, float]]:
    """Build the parameter grid as list of (weight, net_coeff, sos_coeff)."""
    if quick:
        return list(product(QUICK_WEIGHTS, QUICK_NET_COEFFS, QUICK_SOS_COEFFS))
    return list(product(FULL_WEIGHTS, FULL_NET_COEFFS, FULL_SOS_COEFFS))


# -- Data loading --


def load_season_data(
    season: int,
    combined: bool = False,
) -> tuple[list[dict], dict[str, dict], pd.DataFrame | None, pd.DataFrame | None]:
    """Load games, odds, KenPom data, and optionally Barttorvik data for a season.

    Returns:
        (games, odds_lookup, kenpom_df, bart_df)
        bart_df is only loaded if combined=True.
    """
    df_raw = load_test_season(season)
    games = prepare_test_games(df_raw)
    provider = BEST_PROVIDER.get(season, 58)
    odds_lookup = load_odds_data(season, provider_id=provider)
    kenpom_df = load_kenpom_season(season)
    bart_df = load_bart_season(season) if combined else None
    return games, odds_lookup, kenpom_df, bart_df


# -- Single grid point evaluation --


def run_single_grid_point(
    base_model: object,
    season_data: dict[
        int,
        tuple[list[dict], dict[str, dict], pd.DataFrame | None, pd.DataFrame | None],
    ],
    weight: float,
    net_coeff: float,
    sos_coeff: float,
    min_edge: float,
    combined: bool = False,
) -> KenPomGridPoint:
    """Evaluate a single KenPom parameter combination across all loaded seasons."""
    coeffs = KenPomCoeffs(net_diff_coeff=net_coeff, sos_coeff=sos_coeff)
    flat_rois: dict[int, float] = {}
    total_bets = 0
    all_sharpes: list[float] = []
    model_for_season = copy.deepcopy(base_model)

    for season in sorted(season_data.keys()):
        games, odds_lookup, kenpom_df, bart_df = season_data[season]
        if not odds_lookup or kenpom_df is None:
            continue

        model = copy.deepcopy(model_for_season)
        model.apply_season_regression()

        kwargs = {
            "model": model,
            "games": games,
            "kenpom_df": kenpom_df,
            "kenpom_weight": weight,
            "kenpom_mapper": espn_id_to_kenpom,
            "kenpom_coeffs": coeffs,
            "min_edge": min_edge,
            "odds_lookup": odds_lookup,
        }

        # Combined mode: add Barttorvik with fixed best params
        if combined and bart_df is not None:
            kwargs["barttorvik_df"] = bart_df
            kwargs["barttorvik_weight"] = BEST_BART_WEIGHT
            kwargs["team_mapper"] = espn_id_to_barttorvik
            kwargs["bart_coeffs"] = BEST_BART_COEFFS

        results = run_backtest_with_features(**kwargs)

        summary = summarize_backtest(results)
        if summary.get("total_bets", 0) > 0:
            flat_rois[season] = summary["flat_roi"]
            total_bets += summary["total_bets"]
            all_sharpes.append(summary["sharpe"])

        # Advance model for next season
        update_model = copy.deepcopy(model_for_season)
        update_model.apply_season_regression()
        for game in games:
            update_model.update_game(
                game["home"],
                game["away"],
                game["home_score"],
                game["away_score"],
                game["neutral_site"],
            )
        model_for_season = update_model

    # Pooled statistics
    if len(flat_rois) >= 2:
        roi_values = list(flat_rois.values())
        pooled_roi = float(np.mean(roi_values))
        pooled_sharpe = float(np.mean(all_sharpes)) if all_sharpes else 0.0
        t_stat, p_value = stats.ttest_1samp(roi_values, 0)
    else:
        pooled_roi = list(flat_rois.values())[0] if flat_rois else 0.0
        pooled_sharpe = all_sharpes[0] if all_sharpes else 0.0
        t_stat, p_value = 0.0, 1.0

    return KenPomGridPoint(
        kenpom_weight=weight,
        net_diff_coeff=net_coeff,
        sos_coeff=sos_coeff,
        combined_mode=combined,
        seasons_tested=sorted(flat_rois.keys()),
        flat_roi_per_season=flat_rois,
        pooled_flat_roi=pooled_roi,
        pooled_bets=total_bets,
        pooled_sharpe=pooled_sharpe,
        t_stat=float(t_stat),
        p_value=float(p_value),
    )


# -- Baseline --


def run_baseline(
    base_model: object,
    season_data: dict[
        int,
        tuple[list[dict], dict[str, dict], pd.DataFrame | None, pd.DataFrame | None],
    ],
    min_edge: float,
    combined: bool = False,
) -> KenPomGridPoint:
    """Run baseline for comparison.

    KenPom-only mode: Elo-only baseline (no KenPom, no Barttorvik).
    Combined mode: Elo + Barttorvik baseline (no KenPom).
    """
    flat_rois: dict[int, float] = {}
    total_bets = 0
    all_sharpes: list[float] = []
    model_for_season = copy.deepcopy(base_model)

    for season in sorted(season_data.keys()):
        games, odds_lookup, _, bart_df = season_data[season]
        if not odds_lookup:
            continue

        model = copy.deepcopy(model_for_season)
        model.apply_season_regression()

        kwargs = {
            "model": model,
            "games": games,
            "min_edge": min_edge,
            "odds_lookup": odds_lookup,
        }

        if combined and bart_df is not None:
            kwargs["barttorvik_df"] = bart_df
            kwargs["barttorvik_weight"] = BEST_BART_WEIGHT
            kwargs["team_mapper"] = espn_id_to_barttorvik
            kwargs["bart_coeffs"] = BEST_BART_COEFFS

        results = run_backtest_with_features(**kwargs)

        summary = summarize_backtest(results)
        if summary.get("total_bets", 0) > 0:
            flat_rois[season] = summary["flat_roi"]
            total_bets += summary["total_bets"]
            all_sharpes.append(summary["sharpe"])

        update_model = copy.deepcopy(model_for_season)
        update_model.apply_season_regression()
        for game in games:
            update_model.update_game(
                game["home"],
                game["away"],
                game["home_score"],
                game["away_score"],
                game["neutral_site"],
            )
        model_for_season = update_model

    if len(flat_rois) >= 2:
        roi_values = list(flat_rois.values())
        pooled_roi = float(np.mean(roi_values))
        pooled_sharpe = float(np.mean(all_sharpes)) if all_sharpes else 0.0
        t_stat, p_value = stats.ttest_1samp(roi_values, 0)
    else:
        pooled_roi = list(flat_rois.values())[0] if flat_rois else 0.0
        pooled_sharpe = all_sharpes[0] if all_sharpes else 0.0
        t_stat, p_value = 0.0, 1.0

    return KenPomGridPoint(
        kenpom_weight=0.0,
        net_diff_coeff=0.0,
        sos_coeff=0.0,
        combined_mode=combined,
        seasons_tested=sorted(flat_rois.keys()),
        flat_roi_per_season=flat_rois,
        pooled_flat_roi=pooled_roi,
        pooled_bets=total_bets,
        pooled_sharpe=pooled_sharpe,
        t_stat=float(t_stat),
        p_value=float(p_value),
    )


# -- Grid search orchestrator --


def run_grid_search(
    model_path: Path,
    seasons: list[int],
    min_edge: float,
    quick: bool = False,
    combined: bool = False,
) -> tuple[KenPomGridPoint, list[KenPomGridPoint]]:
    """Run the full grid search and return (baseline, grid_results)."""
    saved = load_model(model_path)
    base_model = saved.model

    # Load all season data upfront
    logger.info("Loading data for seasons: %s (combined=%s)", seasons, combined)
    season_data: dict[int, tuple] = {}
    for s in seasons:
        try:
            games, odds, kp_df, bart_df = load_season_data(s, combined=combined)
            season_data[s] = (games, odds, kp_df, bart_df)
            logger.info(
                "Season %d: %d games, %d odds, kenpom=%s, bart=%s",
                s,
                len(games),
                len(odds) if odds else 0,
                f"{len(kp_df)} rows" if kp_df is not None else "None",
                f"{len(bart_df)} rows" if bart_df is not None else "N/A",
            )
        except FileNotFoundError:
            logger.warning("Skipping season %d: data not found", s)

    # Baseline
    mode_label = "Elo+Barttorvik" if combined else "Elo-only"
    logger.info("Running %s baseline...", mode_label)
    baseline = run_baseline(base_model, season_data, min_edge, combined=combined)
    logger.info(
        "Baseline (%s): flat ROI=%.2f%%, %d bets, Sharpe=%.3f",
        mode_label,
        baseline.pooled_flat_roi * 100,
        baseline.pooled_bets,
        baseline.pooled_sharpe,
    )

    # Grid
    grid = build_kenpom_grid(quick=quick)
    logger.info("Running %d KenPom grid points...", len(grid))
    grid_results: list[KenPomGridPoint] = []

    for i, (w, nc, sc) in enumerate(grid, 1):
        t0 = time.time()
        gp = run_single_grid_point(
            base_model,
            season_data,
            w,
            nc,
            sc,
            min_edge,
            combined=combined,
        )
        elapsed = time.time() - t0
        grid_results.append(gp)
        logger.info(
            "[%d/%d] w=%.2f nc=%.3f sc=%.3f -> flat ROI=%.2f%% Sharpe=%.3f p=%.4f (%.1fs)",
            i,
            len(grid),
            w,
            nc,
            sc,
            gp.pooled_flat_roi * 100,
            gp.pooled_sharpe,
            gp.p_value,
            elapsed,
        )

    return baseline, grid_results


# -- Results output --


def save_results(
    baseline: KenPomGridPoint,
    grid_results: list[KenPomGridPoint],
    output_dir: Path,
    combined: bool = False,
) -> None:
    """Save grid search results to CSV and JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sort by pooled flat ROI descending
    ranked = sorted(grid_results, key=lambda g: g.pooled_flat_roi, reverse=True)

    prefix = "kenpom_combined" if combined else "kenpom"

    # CSV
    csv_path = output_dir / f"{prefix}_grid_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "rank",
                "kenpom_weight",
                "net_diff_coeff",
                "sos_coeff",
                "pooled_flat_roi",
                "pooled_bets",
                "pooled_sharpe",
                "t_stat",
                "p_value",
                "seasons",
            ]
        )
        for i, gp in enumerate(ranked, 1):
            writer.writerow(
                [
                    i,
                    gp.kenpom_weight,
                    gp.net_diff_coeff,
                    gp.sos_coeff,
                    f"{gp.pooled_flat_roi:.6f}",
                    gp.pooled_bets,
                    f"{gp.pooled_sharpe:.4f}",
                    f"{gp.t_stat:.4f}",
                    f"{gp.p_value:.6f}",
                    ";".join(str(s) for s in gp.seasons_tested),
                ]
            )
    logger.info("Saved CSV: %s", csv_path)

    # JSON summary
    json_path = output_dir / f"{prefix}_grid_summary.json"
    summary = {
        "mode": "combined" if combined else "kenpom_only",
        "baseline": {
            "pooled_flat_roi": baseline.pooled_flat_roi,
            "pooled_bets": baseline.pooled_bets,
            "pooled_sharpe": baseline.pooled_sharpe,
            "flat_roi_per_season": baseline.flat_roi_per_season,
        },
        "best": {
            "kenpom_weight": ranked[0].kenpom_weight,
            "net_diff_coeff": ranked[0].net_diff_coeff,
            "sos_coeff": ranked[0].sos_coeff,
            "pooled_flat_roi": ranked[0].pooled_flat_roi,
            "pooled_sharpe": ranked[0].pooled_sharpe,
            "p_value": ranked[0].p_value,
            "flat_roi_per_season": ranked[0].flat_roi_per_season,
        },
        "top_5": [
            {
                "kenpom_weight": gp.kenpom_weight,
                "net_diff_coeff": gp.net_diff_coeff,
                "sos_coeff": gp.sos_coeff,
                "pooled_flat_roi": gp.pooled_flat_roi,
                "pooled_sharpe": gp.pooled_sharpe,
                "p_value": gp.p_value,
            }
            for gp in ranked[:5]
        ],
        "grid_size": len(grid_results),
        "seasons": sorted({s for gp in grid_results for s in gp.seasons_tested}),
    }
    if combined:
        summary["barttorvik_fixed"] = {
            "weight": BEST_BART_WEIGHT,
            "net_diff_coeff": BEST_BART_COEFFS.net_diff_coeff,
            "barthag_diff_coeff": BEST_BART_COEFFS.barthag_diff_coeff,
        }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    logger.info("Saved JSON: %s", json_path)


def print_results(
    baseline: KenPomGridPoint,
    grid_results: list[KenPomGridPoint],
    combined: bool = False,
) -> None:
    """Print top 10 grid results and comparison to baseline."""
    ranked = sorted(grid_results, key=lambda g: g.pooled_flat_roi, reverse=True)

    mode_label = "COMBINED (Elo+Barttorvik+KenPom)" if combined else "KENPOM-ONLY (Elo+KenPom)"
    base_label = "Elo+Barttorvik" if combined else "Elo-only"

    print(f"\n{'=' * 100}")
    print(f"KENPOM WEIGHT TUNING RESULTS — {mode_label}")
    print(f"{'=' * 100}")
    print(
        f"\nBaseline ({base_label}): flat ROI={baseline.pooled_flat_roi:+.2%} "
        f"Sharpe={baseline.pooled_sharpe:.3f} "
        f"({baseline.pooled_bets} bets)"
    )

    print(
        f"\n{'Rank':<5} {'Weight':>7} {'NetCoeff':>9} {'SOSCoeff':>9} "
        f"{'FlatROI':>9} {'Sharpe':>8} {'p-value':>9} {'Bets':>7} "
        f"{'vs Base':>9}"
    )
    print("-" * 80)

    for i, gp in enumerate(ranked[:10], 1):
        delta = gp.pooled_flat_roi - baseline.pooled_flat_roi
        sig = "***" if gp.p_value < 0.05 else ("**" if gp.p_value < 0.10 else "")
        print(
            f"{i:<5} {gp.kenpom_weight:>7.2f} {gp.net_diff_coeff:>9.3f} "
            f"{gp.sos_coeff:>9.3f} "
            f"{gp.pooled_flat_roi:>+8.2%} {gp.pooled_sharpe:>8.3f} "
            f"{gp.p_value:>9.4f} {gp.pooled_bets:>7} "
            f"{delta:>+8.2%} {sig}"
        )

    # Best config recommendation
    best = ranked[0]
    print(
        f"\nRECOMMENDED: kenpom_weight={best.kenpom_weight}, "
        f"net_diff_coeff={best.net_diff_coeff}, "
        f"sos_coeff={best.sos_coeff}"
    )
    print(
        f"  flat ROI: {best.pooled_flat_roi:+.2%} "
        f"(baseline: {baseline.pooled_flat_roi:+.2%}, "
        f"improvement: {best.pooled_flat_roi - baseline.pooled_flat_roi:+.2%})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid search for optimal KenPom weight parameters")
    parser.add_argument(
        "--seasons",
        type=int,
        nargs="+",
        default=[2020, 2021, 2022, 2023, 2024, 2025],
    )
    parser.add_argument("--min-edge", type=float, default=THRESHOLDS.MIN_EDGE_SPREAD)
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode: 12 combos on 2024-2025 only",
    )
    parser.add_argument(
        "--combined",
        action="store_true",
        help="Combined mode: Barttorvik (fixed best) + KenPom (searched)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for results (default: data/backtests/)",
    )
    args = parser.parse_args()

    if args.quick:
        args.seasons = [2024, 2025]

    model_path = PROCESSED_DATA_DIR / "ncaab_elo_model.pkl"
    if not model_path.exists():
        logger.error("No trained model at %s", model_path)
        sys.exit(1)

    output_dir = Path(args.output_dir) if args.output_dir else Path("data/backtests")

    baseline, grid_results = run_grid_search(
        model_path=model_path,
        seasons=args.seasons,
        min_edge=args.min_edge,
        quick=args.quick,
        combined=args.combined,
    )

    print_results(baseline, grid_results, combined=args.combined)
    save_results(baseline, grid_results, output_dir, combined=args.combined)


if __name__ == "__main__":
    main()
