"""Incremental Walk-Forward Backtest for NCAAB Elo Model.

For each test season N in [2021..2025], trains on [2020..N-1] and tests
on season N.  This prevents data leakage from training on future seasons
and produces a more realistic evaluation of out-of-sample performance.

Optionally compares results to the all-data model (trained 2020-2025).

Usage:
    python scripts/incremental_backtest.py
    python scripts/incremental_backtest.py --barttorvik
    python scripts/incremental_backtest.py --test-seasons 2024 2025 --save-models
    python scripts/incremental_backtest.py --compare-alldata
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
from scipy import stats

from config.constants import THRESHOLDS
from config.settings import PROCESSED_DATA_DIR
from models.model_persistence import ModelMetadata, load_model, save_model
from pipelines.barttorvik_fetcher import load_cached_season
from pipelines.kenpom_fetcher import load_cached_season as load_kenpom_cached
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
from scripts.train_ncaab_elo import train_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Best real provider per season (from odds backfill analysis)
BEST_PROVIDER: dict[int, int] = {
    2020: 40,  # DraftKings
    2021: 36,  # Unibet
    2022: 43,  # Caesars PA
    2023: 58,  # ESPN BET
    2024: 36,  # Unibet
    2025: 58,  # ESPN BET
}

ALL_SEASONS = [2020, 2021, 2022, 2023, 2024, 2025]


@dataclass
class FoldResult:
    """Results from a single train/test fold."""

    test_season: int
    train_seasons: list[int]
    total_bets: int
    wins: int
    losses: int
    win_rate: float
    flat_roi: float
    kelly_roi: float
    sharpe: float
    avg_clv: float
    max_drawdown: float
    final_bankroll: float
    train_time_sec: float
    backtest_time_sec: float


def run_single_fold(
    test_season: int,
    train_start: int,
    use_barttorvik: bool = False,
    bart_coeffs: BarttovikCoeffs | None = None,
    barttorvik_weight: float = 1.0,
    use_kenpom: bool = False,
    kenpom_coeffs: KenPomCoeffs | None = None,
    kenpom_weight: float = 1.0,
    min_edge: float = 0.05,
    save_model_flag: bool = False,
    output_dir: Path | None = None,
) -> FoldResult:
    """Run a single incremental fold: train on [train_start..test_season-1], test on test_season.

    Args:
        test_season: Season to hold out for testing.
        train_start: First season for training.
        use_barttorvik: Whether to include Barttorvik adjustments.
        bart_coeffs: Barttorvik coefficient overrides.
        barttorvik_weight: Weight for Barttorvik probability adjustment.
        min_edge: Minimum edge threshold for bets.
        save_model_flag: If True, save the trained model for this fold.
        output_dir: Directory for saving models and results.

    Returns:
        FoldResult with test season performance metrics.
    """
    train_end = test_season - 1
    train_seasons = list(range(train_start, train_end + 1))

    logger.info(
        "=== Fold: train [%d..%d], test %d ===",
        train_start,
        train_end,
        test_season,
    )

    # 1. TRAIN on [train_start..train_end]
    t0 = time.time()
    model, train_stats = train_model(train_start, train_end)
    train_time = time.time() - t0
    logger.info(
        "Training complete: %d games, %d teams (%.1fs)",
        train_stats["total_games"],
        len(model.ratings),
        train_time,
    )

    # Save model if requested
    if save_model_flag and output_dir:
        model_dir = output_dir / "models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / f"ncaab_elo_fold_{test_season}.pkl"
        metadata = ModelMetadata(
            model_name=f"ncaab_elo_fold_{test_season}",
            sport="ncaab",
            seasons_used=train_seasons,
            game_count=train_stats["total_games"],
            team_count=len(model.ratings),
            config_snapshot={
                "k_factor": model.k_factor,
                "home_advantage": model.home_advantage,
                "fold_type": "incremental",
                "test_season": test_season,
            },
        )
        save_model(model, model_path, metadata)
        logger.info("Saved fold model: %s", model_path)

    # 2. PREPARE TEST DATA
    model.apply_season_regression()

    df_raw = load_test_season(test_season)
    games = prepare_test_games(df_raw)

    provider = BEST_PROVIDER.get(test_season, 58)
    odds_lookup = load_odds_data(test_season, provider_id=provider)

    # Load Barttorvik if requested
    bart_df = None
    if use_barttorvik:
        bart_df = load_cached_season(test_season)
        if bart_df is None:
            logger.warning("No Barttorvik data for season %d, skipping adjustment", test_season)

    # Load KenPom if requested
    kp_df = None
    if use_kenpom:
        kp_df = load_kenpom_cached(test_season)
        if kp_df is None:
            logger.warning("No KenPom data for season %d, skipping adjustment", test_season)

    # 3. BACKTEST
    t0 = time.time()
    results = run_backtest_with_features(
        model=model,
        games=games,
        barttorvik_df=bart_df if use_barttorvik else None,
        barttorvik_weight=barttorvik_weight if use_barttorvik else 0.0,
        team_mapper=espn_id_to_barttorvik if use_barttorvik else None,
        bart_coeffs=bart_coeffs,
        kenpom_df=kp_df if use_kenpom else None,
        kenpom_weight=kenpom_weight if use_kenpom else 0.0,
        kenpom_mapper=espn_id_to_kenpom if use_kenpom else None,
        kenpom_coeffs=kenpom_coeffs,
        min_edge=min_edge,
        odds_lookup=odds_lookup,
    )
    backtest_time = time.time() - t0

    summary = summarize_backtest(results)

    if summary.get("error"):
        logger.warning("No bets for season %d: %s", test_season, summary["error"])
        return FoldResult(
            test_season=test_season,
            train_seasons=train_seasons,
            total_bets=0,
            wins=0,
            losses=0,
            win_rate=0.0,
            flat_roi=0.0,
            kelly_roi=0.0,
            sharpe=0.0,
            avg_clv=0.0,
            max_drawdown=0.0,
            final_bankroll=5000.0,
            train_time_sec=train_time,
            backtest_time_sec=backtest_time,
        )

    return FoldResult(
        test_season=test_season,
        train_seasons=train_seasons,
        total_bets=summary["total_bets"],
        wins=summary["wins"],
        losses=summary["losses"],
        win_rate=summary["win_rate"],
        flat_roi=summary["flat_roi"],
        kelly_roi=summary["roi"],
        sharpe=summary["sharpe"],
        avg_clv=summary["avg_clv"],
        max_drawdown=summary["max_drawdown"],
        final_bankroll=summary["final_bankroll"],
        train_time_sec=train_time,
        backtest_time_sec=backtest_time,
    )


def run_incremental_backtest(
    test_seasons: list[int],
    train_start: int = 2020,
    use_barttorvik: bool = False,
    bart_coeffs: BarttovikCoeffs | None = None,
    barttorvik_weight: float = 1.0,
    use_kenpom: bool = False,
    kenpom_coeffs: KenPomCoeffs | None = None,
    kenpom_weight: float = 1.0,
    min_edge: float = 0.05,
    save_models: bool = False,
    output_dir: Path | None = None,
) -> list[FoldResult]:
    """Run incremental walk-forward backtest across multiple test seasons.

    Args:
        test_seasons: Seasons to use as test sets.
        train_start: First season for training data.
        use_barttorvik: Whether to include Barttorvik adjustments.
        bart_coeffs: Barttorvik coefficient overrides.
        barttorvik_weight: Weight for Barttorvik probability adjustment.
        min_edge: Minimum edge threshold for bets.
        save_models: If True, save each fold's trained model.
        output_dir: Directory for saving outputs.

    Returns:
        List of FoldResult objects, one per test season.
    """
    fold_results: list[FoldResult] = []

    for test_season in sorted(test_seasons):
        if test_season <= train_start:
            logger.warning(
                "Skipping test season %d: must be after train_start %d",
                test_season,
                train_start,
            )
            continue

        fold = run_single_fold(
            test_season=test_season,
            train_start=train_start,
            use_barttorvik=use_barttorvik,
            bart_coeffs=bart_coeffs,
            barttorvik_weight=barttorvik_weight,
            use_kenpom=use_kenpom,
            kenpom_coeffs=kenpom_coeffs,
            kenpom_weight=kenpom_weight,
            min_edge=min_edge,
            save_model_flag=save_models,
            output_dir=output_dir,
        )
        fold_results.append(fold)

    return fold_results


def compare_with_alldata(
    fold_results: list[FoldResult],
    use_barttorvik: bool = False,
    bart_coeffs: BarttovikCoeffs | None = None,
    barttorvik_weight: float = 1.0,
    use_kenpom: bool = False,
    kenpom_coeffs: KenPomCoeffs | None = None,
    kenpom_weight: float = 1.0,
    min_edge: float = 0.05,
) -> list[FoldResult]:
    """Run the same test seasons using the all-data model for comparison.

    Loads the production model (trained on all 2020-2025 data) and backtests
    each test season. This shows the "optimistic" performance with data leakage.

    Args:
        fold_results: Incremental fold results (for test season list).
        use_barttorvik: Whether to include Barttorvik adjustments.
        bart_coeffs: Barttorvik coefficient overrides.
        barttorvik_weight: Weight for Barttorvik probability adjustment.
        min_edge: Minimum edge threshold.

    Returns:
        List of FoldResult for the all-data model.
    """
    model_path = PROCESSED_DATA_DIR / "ncaab_elo_model.pkl"
    if not model_path.exists():
        logger.error("No all-data model at %s", model_path)
        return []

    saved = load_model(model_path)
    base_model = saved.model

    alldata_results: list[FoldResult] = []
    model_for_season = copy.deepcopy(base_model)

    for fold in fold_results:
        test_season = fold.test_season

        model = copy.deepcopy(model_for_season)
        model.apply_season_regression()

        df_raw = load_test_season(test_season)
        games = prepare_test_games(df_raw)
        provider = BEST_PROVIDER.get(test_season, 58)
        odds_lookup = load_odds_data(test_season, provider_id=provider)

        bart_df = None
        if use_barttorvik:
            bart_df = load_cached_season(test_season)

        kp_df = None
        if use_kenpom:
            kp_df = load_kenpom_cached(test_season)

        t0 = time.time()
        results = run_backtest_with_features(
            model=model,
            games=games,
            barttorvik_df=bart_df if use_barttorvik else None,
            barttorvik_weight=barttorvik_weight if use_barttorvik else 0.0,
            team_mapper=espn_id_to_barttorvik if use_barttorvik else None,
            bart_coeffs=bart_coeffs,
            kenpom_df=kp_df if use_kenpom else None,
            kenpom_weight=kenpom_weight if use_kenpom else 0.0,
            kenpom_mapper=espn_id_to_kenpom if use_kenpom else None,
            kenpom_coeffs=kenpom_coeffs,
            min_edge=min_edge,
            odds_lookup=odds_lookup,
        )
        backtest_time = time.time() - t0

        summary = summarize_backtest(results)

        alldata_results.append(
            FoldResult(
                test_season=test_season,
                train_seasons=ALL_SEASONS,
                total_bets=summary.get("total_bets", 0),
                wins=summary.get("wins", 0),
                losses=summary.get("losses", 0),
                win_rate=summary.get("win_rate", 0.0),
                flat_roi=summary.get("flat_roi", 0.0),
                kelly_roi=summary.get("roi", 0.0),
                sharpe=summary.get("sharpe", 0.0),
                avg_clv=summary.get("avg_clv", 0.0),
                max_drawdown=summary.get("max_drawdown", 0.0),
                final_bankroll=summary.get("final_bankroll", 5000.0),
                train_time_sec=0.0,
                backtest_time_sec=backtest_time,
            )
        )

        # Advance model through this season's games for next iteration
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

    return alldata_results


def print_results(
    fold_results: list[FoldResult],
    alldata_results: list[FoldResult] | None = None,
) -> None:
    """Print formatted results table."""
    print(f"\n{'=' * 100}")
    print("INCREMENTAL WALK-FORWARD BACKTEST RESULTS")
    print(f"{'=' * 100}")

    header = (
        f"{'Season':<8} {'Train':<16} {'Bets':>5} {'W-L':>7} "
        f"{'WinRate':>8} {'FlatROI':>9} {'Sharpe':>8} {'CLV':>7} "
        f"{'MaxDD':>8} {'Time':>6}"
    )
    print(header)
    print("-" * 95)

    total_bets = 0
    all_rois: list[float] = []

    for fold in fold_results:
        train_range = f"[{fold.train_seasons[0]}..{fold.train_seasons[-1]}]"
        wl = f"{fold.wins}-{fold.losses}"
        dd = f"${fold.max_drawdown:.0f}" if fold.max_drawdown != 0 else "$0"
        total_time = fold.train_time_sec + fold.backtest_time_sec

        print(
            f"{fold.test_season:<8} {train_range:<16} {fold.total_bets:>5} "
            f"{wl:>7} {fold.win_rate:>7.1%} {fold.flat_roi:>+8.2%} "
            f"{fold.sharpe:>8.3f} {fold.avg_clv:>6.2%} "
            f"{dd:>8} {total_time:>5.0f}s"
        )

        total_bets += fold.total_bets
        if fold.total_bets > 0:
            all_rois.append(fold.flat_roi)

    # Pooled statistics
    if len(all_rois) >= 2:
        pooled_roi = float(np.mean(all_rois))
        t_stat, p_value = stats.ttest_1samp(all_rois, 0)
        print("-" * 95)
        print(
            f"{'POOLED':<8} {'':16} {total_bets:>5} "
            f"{'':>7} {'':>8} {pooled_roi:>+8.2%} "
            f"{'':>8} {'':>7} "
            f"{'':>8} {'':>6}"
        )
        print(f"\nPooled flat ROI: {pooled_roi:+.2%}")
        print(f"t-stat: {t_stat:.3f}, p-value: {p_value:.4f} (two-sided)")
        one_sided_p = p_value / 2 if t_stat > 0 else 1 - p_value / 2
        print(f"One-sided p-value: {one_sided_p:.4f}")

    # Comparison with all-data model
    if alldata_results:
        print(f"\n{'=' * 100}")
        print("COMPARISON: INCREMENTAL vs ALL-DATA MODEL")
        print(f"{'=' * 100}")
        print(
            f"{'Season':<8} {'Incr ROI':>10} {'AllData ROI':>12} "
            f"{'Delta':>8} {'Incr Bets':>10} {'AD Bets':>8}"
        )
        print("-" * 60)

        for inc, ad in zip(fold_results, alldata_results):
            delta = inc.flat_roi - ad.flat_roi
            print(
                f"{inc.test_season:<8} {inc.flat_roi:>+9.2%} "
                f"{ad.flat_roi:>+11.2%} {delta:>+7.2%} "
                f"{inc.total_bets:>10} {ad.total_bets:>8}"
            )

        inc_rois = [f.flat_roi for f in fold_results if f.total_bets > 0]
        ad_rois = [f.flat_roi for f in alldata_results if f.total_bets > 0]
        if inc_rois and ad_rois:
            print(f"\nIncremental pooled: {np.mean(inc_rois):+.2%}")
            print(f"All-data pooled:    {np.mean(ad_rois):+.2%}")
            print(f"Delta:              {np.mean(inc_rois) - np.mean(ad_rois):+.2%}")


def save_results(
    fold_results: list[FoldResult],
    alldata_results: list[FoldResult] | None,
    output_dir: Path,
    use_barttorvik: bool,
    use_kenpom: bool = False,
) -> None:
    """Save results to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = ""
    if use_barttorvik:
        suffix += "_bart"
    if use_kenpom:
        suffix += "_kenpom"
    json_path = output_dir / f"incremental_backtest{suffix}.json"

    data = {
        "method": "incremental_walk_forward",
        "barttorvik": use_barttorvik,
        "kenpom": use_kenpom,
        "folds": [
            {
                "test_season": f.test_season,
                "train_seasons": f.train_seasons,
                "total_bets": f.total_bets,
                "wins": f.wins,
                "losses": f.losses,
                "win_rate": f.win_rate,
                "flat_roi": f.flat_roi,
                "kelly_roi": f.kelly_roi,
                "sharpe": f.sharpe,
                "avg_clv": f.avg_clv,
                "max_drawdown": f.max_drawdown,
                "final_bankroll": f.final_bankroll,
                "train_time_sec": f.train_time_sec,
                "backtest_time_sec": f.backtest_time_sec,
            }
            for f in fold_results
        ],
    }

    rois = [f.flat_roi for f in fold_results if f.total_bets > 0]
    if len(rois) >= 2:
        t_stat, p_value = stats.ttest_1samp(rois, 0)
        data["pooled"] = {
            "flat_roi": float(np.mean(rois)),
            "t_stat": float(t_stat),
            "p_value": float(p_value),
            "total_bets": sum(f.total_bets for f in fold_results),
        }

    if alldata_results:
        data["alldata_comparison"] = [
            {
                "test_season": f.test_season,
                "flat_roi": f.flat_roi,
                "total_bets": f.total_bets,
                "sharpe": f.sharpe,
            }
            for f in alldata_results
        ]

    with open(json_path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2)
    logger.info("Saved results: %s", json_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Incremental walk-forward backtest for NCAAB Elo")
    parser.add_argument(
        "--test-seasons",
        type=int,
        nargs="+",
        default=[2021, 2022, 2023, 2024, 2025],
        help="Seasons to use as test sets (default: 2021-2025)",
    )
    parser.add_argument(
        "--train-start",
        type=int,
        default=2020,
        help="First season for training (default: 2020)",
    )
    parser.add_argument(
        "--barttorvik",
        action="store_true",
        help="Include Barttorvik efficiency rating adjustments",
    )
    parser.add_argument(
        "--barttorvik-weight",
        type=float,
        default=1.0,
        help="Weight for Barttorvik adjustment (default: 1.0)",
    )
    parser.add_argument(
        "--kenpom",
        action="store_true",
        help="Include KenPom efficiency rating adjustments",
    )
    parser.add_argument(
        "--kenpom-weight",
        type=float,
        default=1.0,
        help="Weight for KenPom adjustment (default: 1.0)",
    )
    parser.add_argument(
        "--min-edge",
        type=float,
        default=THRESHOLDS.MIN_EDGE_SPREAD,
        help="Minimum edge to place a bet",
    )
    parser.add_argument(
        "--save-models",
        action="store_true",
        help="Save each fold's trained model to disk",
    )
    parser.add_argument(
        "--compare-alldata",
        action="store_true",
        help="Also run test seasons with all-data model for comparison",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory (default: data/backtests/)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else Path("data/backtests")

    logger.info("Starting incremental backtest")
    logger.info("  Test seasons: %s", args.test_seasons)
    logger.info("  Train start:  %d", args.train_start)
    logger.info("  Barttorvik:   %s (weight=%.2f)", args.barttorvik, args.barttorvik_weight)
    logger.info("  KenPom:       %s (weight=%.2f)", args.kenpom, args.kenpom_weight)
    logger.info("  Min edge:     %.2f%%", args.min_edge * 100)

    t_total = time.time()

    fold_results = run_incremental_backtest(
        test_seasons=args.test_seasons,
        train_start=args.train_start,
        use_barttorvik=args.barttorvik,
        barttorvik_weight=args.barttorvik_weight,
        use_kenpom=args.kenpom,
        kenpom_weight=args.kenpom_weight,
        min_edge=args.min_edge,
        save_models=args.save_models,
        output_dir=output_dir,
    )

    alldata_results = None
    if args.compare_alldata:
        logger.info("Running all-data model comparison...")
        alldata_results = compare_with_alldata(
            fold_results,
            use_barttorvik=args.barttorvik,
            barttorvik_weight=args.barttorvik_weight,
            use_kenpom=args.kenpom,
            kenpom_weight=args.kenpom_weight,
            min_edge=args.min_edge,
        )

    total_time = time.time() - t_total

    # Output
    print_results(fold_results, alldata_results)
    save_results(fold_results, alldata_results, output_dir, args.barttorvik, args.kenpom)

    print(f"\nTotal runtime: {total_time:.0f}s ({total_time / 60:.1f} min)")

    # Save fold-5 (last fold) model as production model if --save-models
    if args.save_models and fold_results:
        last_fold = fold_results[-1]
        prod_src = output_dir / "models" / f"ncaab_elo_fold_{last_fold.test_season}.pkl"
        prod_dst = PROCESSED_DATA_DIR / "ncaab_elo_model_incremental.pkl"
        if prod_src.exists():
            import shutil

            shutil.copy2(prod_src, prod_dst)
            logger.info("Production model (fold-%d): %s", last_fold.test_season, prod_dst)


if __name__ == "__main__":
    main()
