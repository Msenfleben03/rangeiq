"""Grid Search for Breadwinner Metric Tuning.

Searches over breadwinner_coeff, breadwinner_variant, include_centers,
and quality_cutoff to find the combination that maximizes flat-stake ROI
over the current best Barttorvik configuration (baseline).

The breadwinner metric measures USG% concentration — teams reliant on
1-2 elite scorers have higher variance, exploitable for buying underdogs
and selling favorites.

Quick grid: 32 combos (4 coeffs x 2 variants x 2 center_modes x 2 cutoffs)
Full grid: 192 combos (4 weights x 4 coeffs x 2 variants x 2 centers x 3 cutoffs)

Usage:
    python scripts/tune_breadwinner_weights.py --quick
    python scripts/tune_breadwinner_weights.py --seasons 2020 2021 2022 2023 2024 2025
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

from config.constants import PAPER_BETTING, THRESHOLDS
from config.settings import PROCESSED_DATA_DIR
from features.sport_specific.ncaab.breadwinner import build_breadwinner_lookup
from models.model_persistence import load_model
from pipelines.barttorvik_fetcher import load_cached_season
from pipelines.player_stats_fetcher import load_cached_players
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

# Best real provider per season (from Barttorvik tuning)
BEST_PROVIDER: dict[int, int] = {
    2020: 40,  # DraftKings
    2021: 36,  # Unibet
    2022: 43,  # Caesars PA
    2023: 58,  # ESPN BET
    2024: 36,  # Unibet
    2025: 58,  # ESPN BET
}


@dataclass
class BreadwinnerGridPoint:
    """A single grid search point with results."""

    breadwinner_weight: float
    breadwinner_coeff: float
    breadwinner_variant: str
    include_centers: bool
    quality_cutoff: int
    seasons_tested: list[int]
    flat_roi_per_season: dict[int, float]
    pooled_flat_roi: float
    pooled_bets: int
    pooled_sharpe: float
    t_stat: float
    p_value: float


# -- Grid construction --

FULL_WEIGHTS = [0.5, 1.0, 2.0, 5.0]
FULL_COEFFS = [0.5, 1.0, 2.0, 5.0]
FULL_VARIANTS = ["top1", "top2"]
FULL_CENTER_MODES = [True, False]
FULL_QUALITY_CUTOFFS = [30, 50, 75]

QUICK_WEIGHTS = [1.0]  # Fix weight, vary the rest
QUICK_COEFFS = [0.5, 1.0, 2.0, 5.0]
QUICK_VARIANTS = ["top1", "top2"]
QUICK_CENTER_MODES = [True, False]
QUICK_QUALITY_CUTOFFS = [50]  # Fix at 50


def build_grid(
    quick: bool = False,
) -> list[tuple[float, float, str, bool, int]]:
    """Build parameter grid as list of (weight, coeff, variant, centers, cutoff)."""
    if quick:
        return list(
            product(
                QUICK_WEIGHTS,
                QUICK_COEFFS,
                QUICK_VARIANTS,
                QUICK_CENTER_MODES,
                QUICK_QUALITY_CUTOFFS,
            )
        )
    return list(
        product(
            FULL_WEIGHTS,
            FULL_COEFFS,
            FULL_VARIANTS,
            FULL_CENTER_MODES,
            FULL_QUALITY_CUTOFFS,
        )
    )


# -- Data loading --


def load_season_data(
    season: int,
) -> tuple[list[dict], dict[str, dict], pd.DataFrame | None, pd.DataFrame | None]:
    """Load games, odds, Barttorvik, and player data for a season."""
    df_raw = load_test_season(season)
    games = prepare_test_games(df_raw)
    provider = BEST_PROVIDER.get(season, 58)
    odds_lookup = load_odds_data(season, provider_id=provider)
    bart_df = load_cached_season(season)
    player_df = load_cached_players(season)
    return games, odds_lookup, bart_df, player_df


# -- Single grid point evaluation --


def run_single_grid_point(
    base_model: object,
    season_data: dict[int, tuple],
    weight: float,
    coeff: float,
    variant: str,
    include_centers: bool,
    quality_cutoff: int,
    min_edge: float,
    bart_weight: float,
    bart_coeffs: BarttovikCoeffs,
) -> BreadwinnerGridPoint:
    """Evaluate a single breadwinner parameter combination across seasons."""
    flat_rois: dict[int, float] = {}
    total_bets = 0
    all_sharpes: list[float] = []
    model_for_season = copy.deepcopy(base_model)

    for season in sorted(season_data.keys()):
        games, odds_lookup, bart_df, player_df = season_data[season]
        if not odds_lookup or bart_df is None:
            continue

        # Build breadwinner lookup for this season
        bw_lookup = {}
        if player_df is not None and not player_df.empty:
            bw_lookup = build_breadwinner_lookup(
                player_df,
                bart_df,
                rotation_size=8,
                quality_cutoff=quality_cutoff,
            )

        model = copy.deepcopy(model_for_season)
        model.apply_season_regression()

        results = run_backtest_with_features(
            model=model,
            games=games,
            barttorvik_df=bart_df,
            barttorvik_weight=bart_weight,
            team_mapper=espn_id_to_barttorvik,
            bart_coeffs=bart_coeffs,
            breadwinner_lookup=bw_lookup if bw_lookup else None,
            breadwinner_weight=weight,
            breadwinner_coeff=coeff,
            breadwinner_variant=variant,
            breadwinner_include_centers=include_centers,
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

    return BreadwinnerGridPoint(
        breadwinner_weight=weight,
        breadwinner_coeff=coeff,
        breadwinner_variant=variant,
        include_centers=include_centers,
        quality_cutoff=quality_cutoff,
        seasons_tested=sorted(flat_rois.keys()),
        flat_roi_per_season=flat_rois,
        pooled_flat_roi=pooled_roi,
        pooled_bets=total_bets,
        pooled_sharpe=pooled_sharpe,
        t_stat=float(t_stat),
        p_value=float(p_value),
    )


# -- Baseline (Elo + Barttorvik, no breadwinner) --


def run_baseline(
    base_model: object,
    season_data: dict[int, tuple],
    min_edge: float,
    bart_weight: float,
    bart_coeffs: BarttovikCoeffs,
) -> BreadwinnerGridPoint:
    """Run Elo + Barttorvik baseline (no breadwinner) for comparison."""
    flat_rois: dict[int, float] = {}
    total_bets = 0
    all_sharpes: list[float] = []
    model_for_season = copy.deepcopy(base_model)

    for season in sorted(season_data.keys()):
        games, odds_lookup, bart_df, _ = season_data[season]
        if not odds_lookup or bart_df is None:
            continue

        model = copy.deepcopy(model_for_season)
        model.apply_season_regression()

        results = run_backtest_with_features(
            model=model,
            games=games,
            barttorvik_df=bart_df,
            barttorvik_weight=bart_weight,
            team_mapper=espn_id_to_barttorvik,
            bart_coeffs=bart_coeffs,
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

    return BreadwinnerGridPoint(
        breadwinner_weight=0.0,
        breadwinner_coeff=0.0,
        breadwinner_variant="none",
        include_centers=True,
        quality_cutoff=0,
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
) -> tuple[BreadwinnerGridPoint, list[BreadwinnerGridPoint]]:
    """Run the full breadwinner grid search."""
    saved = load_model(model_path)
    base_model = saved.model

    # Use best Barttorvik config from previous tuning
    bart_weight = PAPER_BETTING.BARTTORVIK_WEIGHT
    bart_coeffs = BarttovikCoeffs(
        net_diff_coeff=PAPER_BETTING.BARTTORVIK_NET_DIFF_COEFF,
        barthag_diff_coeff=PAPER_BETTING.BARTTORVIK_BARTHAG_DIFF_COEFF,
    )
    logger.info(
        "Using Barttorvik config: weight=%.2f, nc=%.3f, bc=%.2f",
        bart_weight,
        bart_coeffs.net_diff_coeff,
        bart_coeffs.barthag_diff_coeff,
    )

    # Load all season data upfront
    logger.info("Loading data for seasons: %s", seasons)
    season_data: dict[int, tuple] = {}
    for s in seasons:
        try:
            games, odds, bart, players = load_season_data(s)
            season_data[s] = (games, odds, bart, players)
            logger.info(
                "Season %d: %d games, %d odds, bart=%s, players=%s",
                s,
                len(games),
                len(odds) if odds else 0,
                f"{len(bart)} rows" if bart is not None else "None",
                f"{len(players)} rows" if players is not None else "None",
            )
        except FileNotFoundError:
            logger.warning("Skipping season %d: data not found", s)

    # Baseline (Elo + Barttorvik, no breadwinner)
    logger.info("Running Elo + Barttorvik baseline (no breadwinner)...")
    baseline = run_baseline(base_model, season_data, min_edge, bart_weight, bart_coeffs)
    logger.info(
        "Baseline: flat ROI=%+.2f%%, %d bets, Sharpe=%.3f",
        baseline.pooled_flat_roi * 100,
        baseline.pooled_bets,
        baseline.pooled_sharpe,
    )

    # Grid
    grid = build_grid(quick=quick)
    logger.info("Running %d grid points...", len(grid))
    grid_results: list[BreadwinnerGridPoint] = []

    for i, (w, c, v, centers, cutoff) in enumerate(grid, 1):
        t0 = time.time()
        gp = run_single_grid_point(
            base_model,
            season_data,
            weight=w,
            coeff=c,
            variant=v,
            include_centers=centers,
            quality_cutoff=cutoff,
            min_edge=min_edge,
            bart_weight=bart_weight,
            bart_coeffs=bart_coeffs,
        )
        elapsed = time.time() - t0
        grid_results.append(gp)
        logger.info(
            "[%d/%d] w=%.1f c=%.3f v=%s ctr=%s cut=%d -> "
            "flat ROI=%+.2f%% Sharpe=%.3f p=%.4f (%.1fs)",
            i,
            len(grid),
            w,
            c,
            v,
            centers,
            cutoff,
            gp.pooled_flat_roi * 100,
            gp.pooled_sharpe,
            gp.p_value,
            elapsed,
        )

    return baseline, grid_results


# -- Results output --


def save_results(
    baseline: BreadwinnerGridPoint,
    grid_results: list[BreadwinnerGridPoint],
    output_dir: Path,
) -> None:
    """Save grid search results to CSV and JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ranked = sorted(grid_results, key=lambda g: g.pooled_flat_roi, reverse=True)

    # CSV
    csv_path = output_dir / "breadwinner_grid_results.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "rank",
                "bw_weight",
                "bw_coeff",
                "bw_variant",
                "include_centers",
                "quality_cutoff",
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
                    gp.breadwinner_weight,
                    gp.breadwinner_coeff,
                    gp.breadwinner_variant,
                    gp.include_centers,
                    gp.quality_cutoff,
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
    json_path = output_dir / "breadwinner_grid_summary.json"
    best = ranked[0] if ranked else None
    summary = {
        "baseline": {
            "description": "Elo + Barttorvik (no breadwinner)",
            "pooled_flat_roi": baseline.pooled_flat_roi,
            "pooled_bets": baseline.pooled_bets,
            "pooled_sharpe": baseline.pooled_sharpe,
            "flat_roi_per_season": baseline.flat_roi_per_season,
        },
        "best": {
            "breadwinner_weight": best.breadwinner_weight,
            "breadwinner_coeff": best.breadwinner_coeff,
            "breadwinner_variant": best.breadwinner_variant,
            "include_centers": best.include_centers,
            "quality_cutoff": best.quality_cutoff,
            "pooled_flat_roi": best.pooled_flat_roi,
            "pooled_sharpe": best.pooled_sharpe,
            "p_value": best.p_value,
            "flat_roi_per_season": best.flat_roi_per_season,
            "improvement_over_baseline": (best.pooled_flat_roi - baseline.pooled_flat_roi),
        }
        if best
        else {},
        "top_5": [
            {
                "breadwinner_weight": gp.breadwinner_weight,
                "breadwinner_coeff": gp.breadwinner_coeff,
                "breadwinner_variant": gp.breadwinner_variant,
                "include_centers": gp.include_centers,
                "quality_cutoff": gp.quality_cutoff,
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


def print_results(
    baseline: BreadwinnerGridPoint,
    grid_results: list[BreadwinnerGridPoint],
) -> None:
    """Print top 10 grid results and comparison to baseline."""
    ranked = sorted(grid_results, key=lambda g: g.pooled_flat_roi, reverse=True)

    print(f"\n{'=' * 110}")
    print("BREADWINNER METRIC TUNING RESULTS")
    print(f"{'=' * 110}")
    print(
        f"\nBaseline (Elo+Barttorvik, no BW): flat ROI={baseline.pooled_flat_roi:+.2%} "
        f"Sharpe={baseline.pooled_sharpe:.3f} ({baseline.pooled_bets} bets)"
    )

    print(
        f"\n{'Rank':<5} {'Wgt':>4} {'Coeff':>6} {'Var':>5} {'Ctr':>4} "
        f"{'Cut':>4} {'FlatROI':>9} {'Sharpe':>8} {'p-val':>8} "
        f"{'Bets':>6} {'vs Base':>9}"
    )
    print("-" * 85)

    for i, gp in enumerate(ranked[:10], 1):
        delta = gp.pooled_flat_roi - baseline.pooled_flat_roi
        sig = "***" if gp.p_value < 0.05 else ("**" if gp.p_value < 0.10 else "")
        ctr_str = "Y" if gp.include_centers else "N"
        print(
            f"{i:<5} {gp.breadwinner_weight:>4.1f} {gp.breadwinner_coeff:>6.3f} "
            f"{gp.breadwinner_variant:>5} {ctr_str:>4} {gp.quality_cutoff:>4} "
            f"{gp.pooled_flat_roi:>+8.2%} {gp.pooled_sharpe:>8.3f} "
            f"{gp.p_value:>8.4f} {gp.pooled_bets:>6} "
            f"{delta:>+8.2%} {sig}"
        )

    if ranked:
        best = ranked[0]
        print(
            f"\nRECOMMENDED: weight={best.breadwinner_weight}, "
            f"coeff={best.breadwinner_coeff}, variant={best.breadwinner_variant}, "
            f"centers={best.include_centers}, cutoff={best.quality_cutoff}"
        )
        delta = best.pooled_flat_roi - baseline.pooled_flat_roi
        print(
            f"  flat ROI: {best.pooled_flat_roi:+.2%} "
            f"(baseline: {baseline.pooled_flat_roi:+.2%}, "
            f"improvement: {delta:+.2%})"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid search for breadwinner metric parameters")
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
        help="Quick mode: 16 combos (fix weight=1.0, cutoff=50)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory for results (default: data/backtests/)",
    )
    parser.add_argument(
        "--fetch-players",
        action="store_true",
        help="Fetch player data from API before running (requires API key)",
    )
    args = parser.parse_args()

    if args.quick:
        args.seasons = [2024, 2025]

    # Optionally fetch player data first
    if args.fetch_players:
        from pipelines.player_stats_fetcher import PlayerStatsFetcher

        fetcher = PlayerStatsFetcher()
        for s in args.seasons:
            logger.info("Fetching player stats for season %d...", s)
            fetcher.fetch_season(s)
        fetcher.close()

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
