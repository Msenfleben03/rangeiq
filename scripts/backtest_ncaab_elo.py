"""Walk-Forward Backtest for NCAAB Elo Model.

Loads a trained model, holds out the most recent season for testing,
and runs a walk-forward backtest: for each game date, predict -> evaluate
-> update ratings.

Simulates bet selection with edge filtering, Kelly sizing, and CLV tracking.

Usage:
    python scripts/backtest_ncaab_elo.py
    python scripts/backtest_ncaab_elo.py --test-season 2025 --min-edge 0.02
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from betting.odds_converter import (
    american_to_decimal,
    american_to_implied_prob,
    calculate_clv,
    calculate_edge,
    fractional_kelly,
)
from config.constants import BANKROLL, THRESHOLDS
from config.settings import PROCESSED_DATA_DIR, RAW_DATA_DIR
from models.model_persistence import load_model
from models.sport_specific.ncaab.team_ratings import NCAABEloModel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_test_season(season: int) -> pd.DataFrame:
    """Load raw data for the test season."""
    path = RAW_DATA_DIR / "ncaab" / f"ncaab_games_{season}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"No data for test season {season}: {path}")
    df = pd.read_parquet(path)
    logger.info("Loaded test season %d: %d rows", season, len(df))
    return df


def prepare_test_games(df: pd.DataFrame) -> list[dict]:
    """Convert raw data to game dicts, deduplicating by game_id."""
    games = []
    seen: set[str] = set()

    for _, row in df.iterrows():
        game_id = row.get("game_id", "")
        if not game_id or game_id in seen:
            continue
        seen.add(game_id)

        location = str(row.get("location", "")).strip().lower()
        team_id = str(row.get("team_id", ""))
        opponent_id = str(row.get("opponent_id", ""))
        points_for = row.get("points_for")
        points_against = row.get("points_against")

        if pd.isna(points_for) or pd.isna(points_against):
            continue

        game_date = row.get("date")
        if isinstance(game_date, str):
            try:
                game_date = pd.to_datetime(game_date)
            except (ValueError, TypeError):
                continue

        if location == "home":
            home, away = team_id, opponent_id
            home_score, away_score = int(points_for), int(points_against)
            neutral = False
        elif location == "away":
            home, away = opponent_id, team_id
            home_score, away_score = int(points_against), int(points_for)
            neutral = False
        else:
            home, away = team_id, opponent_id
            home_score, away_score = int(points_for), int(points_against)
            neutral = True

        games.append(
            {
                "game_id": game_id,
                "date": game_date,
                "home": home,
                "away": away,
                "home_score": home_score,
                "away_score": away_score,
                "neutral_site": neutral,
            }
        )

    games.sort(key=lambda g: g["date"])
    return games


def simulate_market_odds(win_prob: float, vig: float = 0.05) -> int:
    """Simulate realistic American market odds from a true probability.

    Adds vig and random noise to create a synthetic market line.

    Args:
        win_prob: True win probability.
        vig: Vig/juice to add (default 5%).

    Returns:
        Simulated American odds.
    """
    # Add vig to implied probability
    implied = win_prob + vig / 2
    implied = max(0.05, min(0.95, implied))

    # Add small random noise (market inefficiency)
    noise = np.random.normal(0, 0.015)
    implied = max(0.05, min(0.95, implied + noise))

    # Convert to American
    if implied >= 0.5:
        return int(-100 * implied / (1 - implied))
    else:
        return int(100 * (1 - implied) / implied)


def simulate_closing_odds(opening_odds: int) -> int:
    """Simulate closing odds from opening odds.

    Lines typically move 1-3 points toward the sharp side.

    Args:
        opening_odds: Opening American odds.

    Returns:
        Simulated closing American odds.
    """
    # Small random movement
    move = np.random.normal(0, 3)
    prob = american_to_implied_prob(opening_odds)
    closing_prob = max(0.05, min(0.95, prob + move / 100))

    if closing_prob >= 0.5:
        return int(-100 * closing_prob / (1 - closing_prob))
    else:
        return int(100 * (1 - closing_prob) / closing_prob)


def run_backtest(
    model: NCAABEloModel,
    games: list[dict],
    min_edge: float = 0.02,
    kelly_fraction: float = 0.25,
    max_bet: float = 0.03,
    bankroll: float = 5000.0,
) -> pd.DataFrame:
    """Run walk-forward backtest.

    For each game: predict -> simulate odds -> check edge -> size bet ->
    record -> update model.

    Args:
        model: Trained NCAABEloModel.
        games: Chronologically sorted game list.
        min_edge: Minimum edge to place a bet.
        kelly_fraction: Kelly fraction for sizing.
        max_bet: Maximum bet as fraction of bankroll.
        bankroll: Starting bankroll.

    Returns:
        DataFrame of backtest results.
    """
    np.random.seed(42)  # Reproducibility
    results = []
    current_bankroll = bankroll

    for game in games:
        home = game["home"]
        away = game["away"]
        home_score = game["home_score"]
        away_score = game["away_score"]
        neutral = game["neutral_site"]

        # 1. PREDICT (before seeing result)
        home_win_prob = model.predict_win_probability(home, away, neutral)
        predicted_spread = model.predict_spread(home, away, neutral)

        # 2. SIMULATE MARKET ODDS (realistic)
        market_odds_home = simulate_market_odds(home_win_prob)
        closing_odds_home = simulate_closing_odds(market_odds_home)

        # 3. CALCULATE EDGE
        edge = calculate_edge(home_win_prob, market_odds_home)

        # 4. CHECK IF BET QUALIFIES
        if abs(edge) >= min_edge:
            # Determine bet side
            if edge > 0:
                # Bet on home
                bet_side = "home"
                bet_prob = home_win_prob
                bet_odds = market_odds_home
                closing_odds = closing_odds_home
                won = home_score > away_score
            else:
                # Bet on away
                bet_side = "away"
                bet_prob = 1 - home_win_prob
                # Invert odds for away
                away_prob = 1 - american_to_implied_prob(market_odds_home)
                if away_prob >= 0.5:
                    bet_odds = int(-100 * away_prob / (1 - away_prob))
                else:
                    bet_odds = int(100 * (1 - away_prob) / away_prob)
                closing_prob = 1 - american_to_implied_prob(closing_odds_home)
                if closing_prob >= 0.5:
                    closing_odds = int(-100 * closing_prob / (1 - closing_prob))
                else:
                    closing_odds = int(100 * (1 - closing_prob) / closing_prob)
                won = away_score > home_score

            # 5. SIZE BET (Kelly)
            decimal_odds = american_to_decimal(bet_odds)
            bet_fraction = fractional_kelly(bet_prob, decimal_odds, kelly_fraction, max_bet)
            stake = current_bankroll * bet_fraction

            if stake > 0:
                # 6. CALCULATE P/L
                if won:
                    profit = stake * (decimal_odds - 1)
                    result_str = "win"
                else:
                    profit = -stake
                    result_str = "loss"

                # 7. CLV
                clv = calculate_clv(bet_odds, closing_odds)

                current_bankroll += profit

                results.append(
                    {
                        "game_id": game["game_id"],
                        "date": game["date"],
                        "home": home,
                        "away": away,
                        "home_score": home_score,
                        "away_score": away_score,
                        "bet_side": bet_side,
                        "model_prob": bet_prob,
                        "edge": abs(edge),
                        "odds_placed": bet_odds,
                        "odds_closing": closing_odds,
                        "stake": stake,
                        "result": result_str,
                        "profit_loss": profit,
                        "clv": clv,
                        "bankroll": current_bankroll,
                        "predicted_spread": predicted_spread,
                    }
                )

        # 8. UPDATE MODEL (always, regardless of bet)
        model.update_game(home, away, home_score, away_score, neutral)

    df = pd.DataFrame(results)
    return df


def summarize_backtest(df: pd.DataFrame, initial_bankroll: float = 5000.0) -> dict:
    """Calculate summary statistics from backtest results."""
    if df.empty:
        return {"error": "No bets placed"}

    total_bets = len(df)
    wins = (df["result"] == "win").sum()
    losses = (df["result"] == "loss").sum()
    total_pnl = df["profit_loss"].sum()
    total_staked = df["stake"].sum()
    avg_clv = df["clv"].mean()
    win_rate = wins / total_bets

    # ROI
    roi = total_pnl / total_staked if total_staked > 0 else 0

    # Sharpe ratio (annualized, ~150 betting days)
    daily_pnl = df.groupby(df["date"].dt.date)["profit_loss"].sum()
    if len(daily_pnl) > 1 and daily_pnl.std() > 0:
        sharpe = (daily_pnl.mean() / daily_pnl.std()) * np.sqrt(150)
    else:
        sharpe = 0.0

    # Max drawdown
    cumulative = df["profit_loss"].cumsum()
    running_max = cumulative.cummax()
    drawdown = cumulative - running_max
    max_drawdown = drawdown.min()

    return {
        "total_bets": total_bets,
        "wins": int(wins),
        "losses": int(losses),
        "win_rate": win_rate,
        "total_pnl": total_pnl,
        "total_staked": total_staked,
        "roi": roi,
        "avg_clv": avg_clv,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "final_bankroll": df["bankroll"].iloc[-1] if not df.empty else initial_bankroll,
        "avg_edge": df["edge"].mean(),
        "avg_stake": df["stake"].mean(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward backtest for NCAAB Elo")
    parser.add_argument("--test-season", type=int, default=2025)
    parser.add_argument("--min-edge", type=float, default=THRESHOLDS.MIN_EDGE_SPREAD)
    parser.add_argument("--kelly", type=float, default=BANKROLL.KELLY_FRACTION_DEFAULT)
    parser.add_argument("--max-bet", type=float, default=BANKROLL.MAX_BET_FRACTION)
    parser.add_argument("--bankroll", type=float, default=BANKROLL.TOTAL_BANKROLL)
    args = parser.parse_args()

    # Load trained model
    model_path = PROCESSED_DATA_DIR / "ncaab_elo_model.pkl"
    if not model_path.exists():
        logger.error("No trained model found. Run train_ncaab_elo.py first.")
        sys.exit(1)

    saved = load_model(model_path)
    model = saved.model
    logger.info("Loaded model with %d teams", len(model.ratings))

    # Apply regression before test season
    model.apply_season_regression()

    # Load test season
    df_raw = load_test_season(args.test_season)
    games = prepare_test_games(df_raw)
    logger.info("Prepared %d test games for season %d", len(games), args.test_season)

    # Run backtest
    results = run_backtest(
        model=model,
        games=games,
        min_edge=args.min_edge,
        kelly_fraction=args.kelly,
        max_bet=args.max_bet,
        bankroll=args.bankroll,
    )

    # Save results
    output_dir = Path("data/backtests")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"ncaab_elo_backtest_{args.test_season}.parquet"
    results.to_parquet(output_path, index=False)
    logger.info("Saved backtest results to %s", output_path)

    # Summary
    summary = summarize_backtest(results, args.bankroll)

    print(f"\n{'=' * 60}")
    print(f"BACKTEST RESULTS — NCAAB Elo ({args.test_season} season)")
    print(f"{'=' * 60}")
    print(f"Total bets:     {summary['total_bets']}")
    print(f"Win rate:        {summary['win_rate']:.1%}")
    print(f"Total P/L:      ${summary['total_pnl']:+.2f}")
    print(f"ROI:             {summary['roi']:.2%}")
    print(f"Avg CLV:         {summary['avg_clv']:.3%}")
    print(f"Sharpe ratio:    {summary['sharpe']:.2f}")
    print(f"Max drawdown:   ${summary['max_drawdown']:.2f}")
    print(f"Final bankroll: ${summary['final_bankroll']:.2f}")
    print(f"Avg edge:        {summary['avg_edge']:.2%}")
    print(f"Avg stake:      ${summary['avg_stake']:.2f}")

    # Check Gatekeeper-relevant thresholds
    print(f"\n{'=' * 60}")
    print("GATEKEEPER CHECK PREVIEW")
    print(f"{'=' * 60}")
    checks = {
        "Sample size >= 200": summary["total_bets"] >= 200,
        "Sharpe >= 0.5": summary["sharpe"] >= 0.5,
        "In-sample ROI <= 15%": summary["roi"] <= 0.15,
        "Avg CLV >= 1.5%": summary["avg_clv"] >= 0.015,
    }
    for check, passed in checks.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {check}")


if __name__ == "__main__":
    main()
