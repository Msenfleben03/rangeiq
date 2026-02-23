"""Grid Search for Barttorvik Weight Tuning.

Searches over barttorvik_weight, net_diff_coeff, and barthag_diff_coeff
to find the combination that maximizes flat-stake ROI while maintaining
statistical significance.

Full grid: 5 weights x 4 net_coeffs x 4 barthag_coeffs = 80 combos.
Quick mode: 12 combos on [2024, 2025] only (~12 min).

Usage:
    python scripts/tune_barttorvik_weights.py --quick
    python scripts/tune_barttorvik_weights.py --seasons 2020 2021 2022 2023 2024 2025
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
from pipelines.barttorvik_fetcher import load_cached_season
from pipelines.team_name_mapping import espn_id_to_barttorvik
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
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Best real provider per season
BEST_PROVIDER: dict[int, int] = {
    2020: 40,  # DraftKings
    2021: 36,  # Unibet
    2022: 43,  # Caesars PA
    2023: 58,  # ESPN BET
    2024: 36,  # Unibet
    2025: 58,  # ESPN BET
}


@dataclass
class GridPoint:
    """A single grid search point with results."""

    barttorvik_weight: float
    net_diff_coeff: float
    barthag_diff_coeff: float
    seasons_tested: list[int]
    flat_roi_per_season: dict[int, float]
    pooled_flat_roi: float
    pooled_bets: int
    pooled_sharpe: float
    t_stat: float
    p_value: float


# -- Grid construction --

FULL_WEIGHTS = [0.25, 0.5, 0.75, 1.0, 1.5]
FULL_NET_COEFFS = [0.001, 0.002, 0.003, 0.005]
FULL_BARTHAG_COEFFS = [0.05, 0.1, 0.15, 0.2]

QUICK_WEIGHTS = [0.5, 1.0, 1.5]
QUICK_NET_COEFFS = [0.002, 0.003]
QUICK_BARTHAG_COEFFS = [0.1, 0.15]


def build_grid(quick: bool = False) -> list[tuple[float, float, float]]:
    """Build the parameter grid as list of (weight, net_coeff, barthag_coeff)."""
    if quick:
        return list(product(QUICK_WEIGHTS, QUICK_NET_COEFFS, QUICK_BARTHAG_COEFFS))
    return list(product(FULL_WEIGHTS, FULL_NET_COEFFS, FULL_BARTHAG_COEFFS))


# -- Data loading --


def load_season_data(
    season: int,
) -> tuple[list[dict], dict[str, dict], pd.DataFrame | None]:
    """Load games, odds, and Barttorvik data for a season."""
    df_raw = load_test_season(season)
    games = prepare_test_games(df_raw)
    provider = BEST_PROVIDER.get(season, 58)
    odds_lookup = load_odds_data(season, provider_id=provider)
    bart_df = load_cached_season(season)
    return games, odds_lookup, bart_df


# -- Single grid point evaluation --


def run_single_grid_point(
    base_model: object,
    season_data: dict[int, tuple[list[dict], dict[str, dict], pd.DataFrame | None]],
    weight: float,
    net_coeff: float,
    barthag_coeff: float,
    min_edge: float,
) -> GridPoint:
    """Evaluate a single parameter combination across all loaded seasons."""
    coeffs = BarttovikCoeffs(
        net_diff_coeff=net_coeff,
        barthag_diff_coeff=barthag_coeff,
    )
    flat_rois: dict[int, float] = {}
    total_bets = 0
    all_sharpes: list[float] = []
    model_for_season = copy.deepcopy(base_model)

    for season in sorted(season_data.keys()):
        games, odds_lookup, bart_df = season_data[season]
        if not odds_lookup or bart_df is None:
            continue

        model = copy.deepcopy(model_for_season)
        model.apply_season_regression()

        results = run_backtest_with_features(
            model=model,
            games=games,
            barttorvik_df=bart_df,
            barttorvik_weight=weight,
            team_mapper=espn_id_to_barttorvik,
            bart_coeffs=coeffs,
            min_edge=min_edge,
            odds_lookup=odds_lookup,
        )

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

    return GridPoint(
        barttorvik_weight=weight,
        net_diff_coeff=net_coeff,
        barthag_diff_coeff=barthag_coeff,
        seasons_tested=sorted(flat_rois.keys()),
        flat_roi_per_season=flat_rois,
        pooled_flat_roi=pooled_roi,
        pooled_bets=total_bets,
        pooled_sharpe=pooled_sharpe,
        t_stat=float(t_stat),
        p_value=float(p_value),
    )


# -- Baseline (no Barttorvik) --


def run_baseline(
    base_model: object,
    season_data: dict[int, tuple[list[dict], dict[str, dict], pd.DataFrame | None]],
    min_edge: float,
) -> GridPoint:
    """Run Elo-only baseline for comparison."""
    flat_rois: dict[int, float] = {}
    total_bets = 0
    all_sharpes: list[float] = []
    model_for_season = copy.deepcopy(base_model)

    for season in sorted(season_data.keys()):
        games, odds_lookup, _ = season_data[season]
        if not odds_lookup:
            continue

        model = copy.deepcopy(model_for_season)
        model.apply_season_regression()

        results = run_backtest_with_features(
            model=model,
            games=games,
            min_edge=min_edge,
            odds_lookup=odds_lookup,
        )

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

    return GridPoint(
        barttorvik_weight=0.0,
        net_diff_coeff=0.0,
        barthag_diff_coeff=0.0,
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
) -> tuple[GridPoint, list[GridPoint]]:
    """Run the full grid search and return (baseline, grid_results)."""
    saved = load_model(model_path)
    base_model = saved.model

    # Load all season data upfront
    logger.info("Loading data for seasons: %s", seasons)
    season_data: dict[int, tuple] = {}
    for s in seasons:
        try:
            games, odds, bart = load_season_data(s)
            season_data[s] = (games, odds, bart)
            logger.info(
                "Season %d: %d games, %d odds entries, bart=%s",
                s,
                len(games),
                len(odds) if odds else 0,
                f"{len(bart)} rows" if bart is not None else "None",
            )
        except FileNotFoundError:
            logger.warning("Skipping season %d: data not found", s)

    # Baseline
    logger.info("Running Elo-only baseline...")
    baseline = run_baseline(base_model, season_data, min_edge)
    logger.info(
        "Baseline: flat ROI=%.2f%%, %d bets, Sharpe=%.3f",
        baseline.pooled_flat_roi * 100,
        baseline.pooled_bets,
        baseline.pooled_sharpe,
    )

    # Grid
    grid = build_grid(quick=quick)
    logger.info("Running %d grid points...", len(grid))
    grid_results: list[GridPoint] = []

    for i, (w, nc, bc) in enumerate(grid, 1):
        t0 = time.time()
        gp = run_single_grid_point(
            base_model,
            season_data,
            w,
            nc,
            bc,
            min_edge,
        )
        elapsed = time.time() - t0
        grid_results.append(gp)
        logger.info(
            "[%d/%d] w=%.2f nc=%.3f bc=%.2f -> flat ROI=%.2f%% " "Sharpe=%.3f p=%.4f (%.1fs)",
            i,
            len(grid),
            w,
            nc,
            bc,
            gp.pooled_flat_roi * 100,
            gp.pooled_sharpe,
            gp.p_value,
            elapsed,
        )

    return baseline, grid_results


# -- Results output --


def save_results(
    baseline: GridPoint,
    grid_results: list[GridPoint],
    output_dir: Path,
) -> None:
    """Save grid search results to CSV and JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Sort by pooled flat ROI descending
    ranked = sorted(grid_results, key=lambda g: g.pooled_flat_roi, reverse=True)

    # CSV
    csv_path = output_dir / "barttorvik_grid_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "rank",
                "bart_weight",
                "net_diff_coeff",
                "barthag_diff_coeff",
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
                    gp.barttorvik_weight,
                    gp.net_diff_coeff,
                    gp.barthag_diff_coeff,
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
    json_path = output_dir / "barttorvik_grid_summary.json"
    summary = {
        "baseline": {
            "pooled_flat_roi": baseline.pooled_flat_roi,
            "pooled_bets": baseline.pooled_bets,
            "pooled_sharpe": baseline.pooled_sharpe,
            "flat_roi_per_season": baseline.flat_roi_per_season,
        },
        "best": {
            "barttorvik_weight": ranked[0].barttorvik_weight,
            "net_diff_coeff": ranked[0].net_diff_coeff,
            "barthag_diff_coeff": ranked[0].barthag_diff_coeff,
            "pooled_flat_roi": ranked[0].pooled_flat_roi,
            "pooled_sharpe": ranked[0].pooled_sharpe,
            "p_value": ranked[0].p_value,
            "flat_roi_per_season": ranked[0].flat_roi_per_season,
        },
        "top_5": [
            {
                "barttorvik_weight": gp.barttorvik_weight,
                "net_diff_coeff": gp.net_diff_coeff,
                "barthag_diff_coeff": gp.barthag_diff_coeff,
                "pooled_flat_roi": gp.pooled_flat_roi,
                "pooled_sharpe": gp.pooled_sharpe,
                "p_value": gp.p_value,
            }
            for gp in ranked[:5]
        ],
        "grid_size": len(grid_results),
        "seasons": sorted({s for gp in grid_results for s in gp.seasons_tested}),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    logger.info("Saved JSON: %s", json_path)


def print_results(baseline: GridPoint, grid_results: list[GridPoint]) -> None:
    """Print top 10 grid results and comparison to baseline."""
    ranked = sorted(grid_results, key=lambda g: g.pooled_flat_roi, reverse=True)

    print(f"\n{'=' * 100}")
    print("BARTTORVIK WEIGHT TUNING RESULTS")
    print(f"{'=' * 100}")
    print(
        f"\nBaseline (Elo-only): flat ROI={baseline.pooled_flat_roi:+.2%} "
        f"Sharpe={baseline.pooled_sharpe:.3f} "
        f"({baseline.pooled_bets} bets)"
    )

    print(
        f"\n{'Rank':<5} {'Weight':>7} {'NetCoeff':>9} {'BartCoeff':>10} "
        f"{'FlatROI':>9} {'Sharpe':>8} {'p-value':>9} {'Bets':>7} "
        f"{'vs Base':>9}"
    )
    print("-" * 80)

    for i, gp in enumerate(ranked[:10], 1):
        delta = gp.pooled_flat_roi - baseline.pooled_flat_roi
        sig = "***" if gp.p_value < 0.05 else ("**" if gp.p_value < 0.10 else "")
        print(
            f"{i:<5} {gp.barttorvik_weight:>7.2f} {gp.net_diff_coeff:>9.3f} "
            f"{gp.barthag_diff_coeff:>10.2f} "
            f"{gp.pooled_flat_roi:>+8.2%} {gp.pooled_sharpe:>8.3f} "
            f"{gp.p_value:>9.4f} {gp.pooled_bets:>7} "
            f"{delta:>+8.2%} {sig}"
        )

    # Best config recommendation
    best = ranked[0]
    print(
        f"\nRECOMMENDED: barttorvik_weight={best.barttorvik_weight}, "
        f"net_diff_coeff={best.net_diff_coeff}, "
        f"barthag_diff_coeff={best.barthag_diff_coeff}"
    )
    print(
        f"  flat ROI: {best.pooled_flat_roi:+.2%} "
        f"(baseline: {baseline.pooled_flat_roi:+.2%}, "
        f"improvement: {best.pooled_flat_roi - baseline.pooled_flat_roi:+.2%})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Grid search for optimal Barttorvik weight parameters"
    )
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
    )

    print_results(baseline, grid_results)
    save_results(baseline, grid_results, output_dir)


if __name__ == "__main__":
    main()
