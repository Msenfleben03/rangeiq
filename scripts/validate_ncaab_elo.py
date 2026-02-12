"""
Validate NCAAB ELO Model with the 5-Dimension Gatekeeper.

This script runs the NCAAB ELO model through the full validation pipeline:
1. TEMPORAL - Check for look-ahead bias and data leakage
2. STATISTICAL - Verify sample size, Sharpe, significance
3. OVERFIT - Detect overfitting patterns
4. BETTING - Validate CLV, vig assumptions, Kelly sizing
5. GATEKEEPER - Final aggregated decision (PASS/QUARANTINE)

Usage:
    python scripts/validate_ncaab_elo.py [--synthetic]
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backtesting.validators import (  # noqa: E402
    Gatekeeper,
    GateDecision,
)
from models.sport_specific.ncaab.team_ratings import NCAABEloModel  # noqa: E402


def generate_synthetic_backtest(
    n_games: int = 500,
    n_seasons: int = 3,
    clv_mean: float = 0.018,
    clv_std: float = 0.025,
    win_rate: float = 0.53,
    seed: int = 42,
) -> pd.DataFrame:
    """Generate synthetic backtest data for validation testing.

    Args:
        n_games: Total number of games to simulate.
        n_seasons: Number of seasons to spread games across.
        clv_mean: Mean CLV (positive = profitable).
        clv_std: Standard deviation of CLV.
        win_rate: Win rate of the betting strategy.
        seed: Random seed for reproducibility.

    Returns:
        DataFrame with columns matching Gatekeeper expectations.
    """
    np.random.seed(seed)

    # Generate dates across seasons
    base_date = datetime(2022, 11, 1)
    dates = []
    games_per_season = n_games // n_seasons
    remainder = n_games % n_seasons

    for season in range(n_seasons):
        season_start = base_date + timedelta(days=365 * season)
        season_games = games_per_season + (1 if season < remainder else 0)
        for i in range(season_games):
            game_date = season_start + timedelta(days=np.random.randint(0, 150))
            dates.append(game_date)

    dates = sorted(dates)

    # Generate CLV values (key metric)
    clv_values = np.random.normal(clv_mean, clv_std, n_games)

    # Generate win/loss outcomes
    outcomes = np.random.binomial(1, win_rate, n_games)

    # Generate stakes (fixed for simplicity)
    stakes = np.full(n_games, 100.0)

    # Calculate P/L based on outcomes and odds
    odds_placed = np.random.choice([-110, -105, +100, +105, +110], n_games)
    profit_loss = []
    for i in range(n_games):
        if outcomes[i] == 1:  # Win
            if odds_placed[i] > 0:
                profit_loss.append(stakes[i] * odds_placed[i] / 100)
            else:
                profit_loss.append(stakes[i] * 100 / abs(odds_placed[i]))
        else:  # Loss
            profit_loss.append(-stakes[i])

    profit_loss = np.array(profit_loss)

    # Generate closing odds (derived from placed odds + CLV)
    odds_closing = odds_placed.copy().astype(float)
    for i in range(n_games):
        # Adjust closing odds based on CLV
        if odds_placed[i] < 0:
            odds_closing[i] = odds_placed[i] - clv_values[i] * 100
        else:
            odds_closing[i] = odds_placed[i] - clv_values[i] * 100

    # Generate team names
    teams = [
        "duke",
        "unc",
        "kansas",
        "kentucky",
        "gonzaga",
        "michigan",
        "villanova",
        "baylor",
        "purdue",
        "arizona",
    ]
    home_teams = np.random.choice(teams, n_games)
    away_teams = np.random.choice(teams, n_games)

    # Generate model predictions (features for temporal validation)
    model_prob = np.random.uniform(0.45, 0.65, n_games)
    model_spread = np.random.uniform(-15, 15, n_games)

    # Create season labels
    season_labels = []
    for d in dates:
        if d.month >= 11:
            season_labels.append(f"{d.year}-{d.year + 1}")
        else:
            season_labels.append(f"{d.year - 1}-{d.year}")

    df = pd.DataFrame(
        {
            "game_date": dates,
            "season": season_labels,
            "home_team": home_teams,
            "away_team": away_teams,
            "model_probability": model_prob,
            "model_spread": model_spread,
            "odds_placed": odds_placed,
            "odds_closing": odds_closing,
            "stake": stakes,
            "result": outcomes,
            "profit_loss": profit_loss,
            "clv": clv_values,
        }
    )

    return df


def extract_model_metadata(model: NCAABEloModel, df: pd.DataFrame) -> dict:
    """Extract metadata about the model for validation.

    Args:
        model: The NCAAB ELO model instance.
        df: Backtest results DataFrame.

    Returns:
        Dictionary of model metadata.
    """
    # Feature count (for overfitting checks)
    # ELO model uses: rating_a, rating_b, home_advantage, conference_adj, margin_history
    n_features = 5

    # Sample size
    n_samples = len(df)

    # Calculate in-sample ROI
    total_stake = df["stake"].sum()
    total_profit = df["profit_loss"].sum()
    in_sample_roi = total_profit / total_stake if total_stake > 0 else 0

    # Get season-by-season ROI
    season_rois = []
    for season in df["season"].unique():
        season_df = df[df["season"] == season]
        s_stake = season_df["stake"].sum()
        s_profit = season_df["profit_loss"].sum()
        if s_stake > 0:
            season_rois.append(s_profit / s_stake)

    return {
        "model_name": "ncaab_elo_v1",
        "model_type": "elo",
        "n_features": n_features,
        "n_samples": n_samples,
        "in_sample_roi": in_sample_roi,
        "season_rois": season_rois,
        "config": {
            "k_factor": model.k_factor,
            "home_advantage": model.home_advantage,
            "mov_cap": model.mov_cap,
            "regression_factor": model.regression_factor,
            "assumed_vig": -110,
        },
    }


def extract_backtest_results(df: pd.DataFrame) -> dict:
    """Extract backtest results for Gatekeeper validation.

    Args:
        df: Backtest results DataFrame.

    Returns:
        Dictionary of backtest results.
    """
    return {
        "profit_loss": df["profit_loss"].tolist(),
        "stake": df["stake"].tolist(),
        "clv_values": df["clv"].tolist(),
        "game_date": df["game_date"].tolist(),
        "result": df["result"].tolist(),
        "odds_placed": df["odds_placed"].tolist(),
        "odds_closing": df["odds_closing"].tolist(),
        "season": df["season"].tolist(),
        "bankroll": 5000,
        "bet_sizes": df["stake"].tolist(),
    }


def run_validation(use_synthetic: bool = True, mode: str = "fast") -> None:
    """Run the full validation pipeline on NCAAB ELO model.

    Args:
        use_synthetic: If True, use synthetic data. Otherwise, load real data.
        mode: "fast" for tiered early-termination (default), "full" for all validators.
    """
    print("=" * 70)
    print("NCAAB ELO MODEL VALIDATION")
    print("=" * 70)
    print()

    # Initialize the model
    print("[1/5] Initializing NCAAB ELO model...")
    model = NCAABEloModel()
    print(f"      K-factor: {model.k_factor}")
    print(f"      Home advantage: {model.home_advantage}")
    print(f"      MOV cap: {model.mov_cap}")
    print(f"      Regression factor: {model.regression_factor}")
    print()

    # Generate or load backtest data
    print("[2/5] Preparing backtest data...")
    if use_synthetic:
        print("      Using SYNTHETIC data for demonstration")
        df = generate_synthetic_backtest(
            n_games=500,
            n_seasons=3,
            clv_mean=0.018,  # 1.8% CLV (above 1.5% threshold)
            clv_std=0.025,
            win_rate=0.53,
        )
    else:
        # TODO: Load real backtest data
        raise NotImplementedError("Real data loading not yet implemented")

    print(f"      Total games: {len(df)}")
    print(f"      Date range: {df['game_date'].min().date()} to {df['game_date'].max().date()}")
    print(f"      Seasons: {df['season'].nunique()}")
    print()

    # Extract metadata and results
    model_metadata = extract_model_metadata(model, df)
    backtest_results = extract_backtest_results(df)

    # Quick stats
    total_stake = sum(backtest_results["stake"])
    total_profit = sum(backtest_results["profit_loss"])
    roi = total_profit / total_stake * 100
    avg_clv = np.mean(backtest_results["clv_values"]) * 100
    win_rate = np.mean(backtest_results["result"]) * 100

    print("[3/5] Backtest Summary:")
    print(f"      Total stake: ${total_stake:,.0f}")
    print(f"      Total P/L: ${total_profit:,.2f}")
    print(f"      ROI: {roi:.2f}%")
    print(f"      Win rate: {win_rate:.1f}%")
    print(f"      Avg CLV: {avg_clv:.2f}%")
    print()

    # Initialize Gatekeeper
    print(f"[4/5] Running Gatekeeper validation pipeline (mode={mode})...")
    gatekeeper = Gatekeeper()
    gatekeeper.load_validators()

    # Generate the report
    report = gatekeeper.generate_report(
        model_name="ncaab_elo_v1",
        backtest_results=backtest_results,
        model_metadata=model_metadata,
        mode=mode,
    )

    # Display results
    print()
    print("=" * 70)
    print("[5/5] GATEKEEPER REPORT")
    print("=" * 70)
    print()
    print(report.summary())

    # Decision
    print()
    print("-" * 70)
    if report.decision == GateDecision.PASS:
        print("🟢 DECISION: PASS - Model approved for deployment")
    elif report.decision == GateDecision.QUARANTINE:
        print("🔴 DECISION: QUARANTINE - Model requires fixes")
        print()
        print("Blocking failures:")
        for failure in report.blocking_failures:
            print(f"   ❌ {failure}")
        print()
        print("Recommended fixes:")
        print(gatekeeper.explain_failure(report))
    else:
        print("🟡 DECISION: NEEDS_REVIEW - Model has warnings")
        print()
        print("Warnings:")
        for warning in report.warnings:
            print(f"   ⚠️ {warning}")

    print()
    print("=" * 70)
    print("Validation complete.")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate NCAAB ELO model")
    parser.add_argument(
        "--synthetic",
        action="store_true",
        default=True,
        help="Use synthetic data (default: True)",
    )
    parser.add_argument(
        "--mode",
        choices=["fast", "full"],
        default="fast",
        help="Validation mode: 'fast' (tiered early-termination) or 'full' (all validators). Default: fast",
    )
    args = parser.parse_args()

    run_validation(use_synthetic=args.synthetic, mode=args.mode)
