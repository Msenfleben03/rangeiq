"""Walk-forward backtesting for MLB Poisson model.

Usage:
    python scripts/mlb_backtest.py                          # Train 2023-2024, test 2025
    python scripts/mlb_backtest.py --test-season 2024       # Train 2023, test 2024
    python scripts/mlb_backtest.py --pitcher-adj            # With pitcher adjustment
    python scripts/mlb_backtest.py --pitcher-adj --calibrated --odds  # Full stack
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from betting.odds_converter import american_to_decimal, american_to_implied_prob, devig_prob
from config.constants import MLB_MODEL
from models.sport_specific.mlb.poisson_model import PoissonModel, compute_pitcher_adj

EDGE_THRESHOLD = 0.03  # Minimum edge to simulate a bet (3%)
KELLY_FRACTION = 0.25  # Quarter Kelly
MAX_BET_FRACTION = 0.03  # 3% bankroll max
BANKROLL = 5000.0

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = PROJECT_ROOT / "data" / "mlb_data.db"


def load_games(db_path: Path) -> pd.DataFrame:
    """Load all final games with starter IDs from the database."""
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql_query(
        "SELECT game_pk, game_date, season, home_team_id, away_team_id, "
        "home_score, away_score, home_starter_id, away_starter_id "
        "FROM games WHERE status = 'final'",
        conn,
    )
    conn.close()
    return df


def load_pitcher_stats(db_path: Path) -> dict[tuple[int, int], dict]:
    """Load pitcher season stats keyed by (player_id, season).

    Returns:
        Dict mapping (player_id, season) to {xfip, ip, games_started}.
    """
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT player_id, season, xfip, ip, games_started "
        "FROM pitcher_season_stats WHERE xfip IS NOT NULL"
    ).fetchall()
    conn.close()

    stats: dict[tuple[int, int], dict] = {}
    for player_id, season, xfip, ip, gs in rows:
        stats[(player_id, season)] = {
            "xfip": xfip,
            "ip": ip or 0.0,
            "games_started": gs or 0,
        }
    return stats


def load_odds(db_path: Path) -> pd.DataFrame:
    """Load odds from the odds table, keeping the best row per game_pk.

    Prefers ESPN BET provider; falls back to first available.
    Returns one row per game_pk with columns:
        game_pk, home_ml_open, away_ml_open, home_ml_close, away_ml_close,
        total_open, total_close.
    """
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql_query(
        "SELECT game_pk, provider, home_ml_open, away_ml_open, "
        "home_ml_close, away_ml_close, total_open, total_close "
        "FROM odds",
        conn,
    )
    conn.close()

    if df.empty:
        return df

    # Prefer rows that have closing ML; within those, prefer non-live provider
    df["has_close"] = df["home_ml_close"].notna()
    df["is_live"] = df["provider"].str.contains("Live", case=False, na=False)
    df_sorted = df.sort_values(["has_close", "is_live"], ascending=[False, True])
    best = df_sorted.drop_duplicates(subset=["game_pk"], keep="first")
    return best[
        [
            "game_pk",
            "home_ml_open",
            "away_ml_open",
            "home_ml_close",
            "away_ml_close",
            "total_open",
            "total_close",
        ]
    ].reset_index(drop=True)


def compute_league_avg_xfip(
    pitcher_stats: dict[tuple[int, int], dict],
    season: int,
    min_gs: int = 5,
) -> float:
    """Compute IP-weighted league-average xFIP for a season.

    Args:
        pitcher_stats: Dict from load_pitcher_stats().
        season: The season to compute for.
        min_gs: Minimum games started to include in the average.

    Returns:
        Weighted average xFIP. Falls back to 4.2 if no data.
    """
    total_weighted = 0.0
    total_ip = 0.0
    for (_, s), val in pitcher_stats.items():
        if s != season:
            continue
        if val["games_started"] < min_gs:
            continue
        ip = val["ip"]
        total_weighted += val["xfip"] * ip
        total_ip += ip

    if total_ip == 0:
        return 4.2  # reasonable default
    return total_weighted / total_ip


def _kelly_stake(
    win_prob: float,
    american_odds: int,
    bankroll: float = BANKROLL,
    kelly_fraction: float = KELLY_FRACTION,
    max_fraction: float = MAX_BET_FRACTION,
) -> float:
    """Compute fractional Kelly stake in dollars.

    Args:
        win_prob: Model probability of winning.
        american_odds: American odds for this side.
        bankroll: Total bankroll.
        kelly_fraction: Fraction of full Kelly to use.
        max_fraction: Maximum stake as fraction of bankroll.

    Returns:
        Stake in dollars (0.0 if Kelly is negative).
    """
    try:
        decimal = american_to_decimal(american_odds)
    except ValueError:
        return 0.0
    b = decimal - 1.0
    if b <= 0:
        return 0.0
    kelly = (b * win_prob - (1 - win_prob)) / b
    if kelly <= 0:
        return 0.0
    fraction = min(kelly * kelly_fraction, max_fraction)
    return fraction * bankroll


def run_backtest(
    games: pd.DataFrame,
    test_season: int,
    pitcher_adj: bool = False,
    pitcher_stats: dict[tuple[int, int], dict] | None = None,
    calibrated: bool = False,
    odds_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Run walk-forward: train on seasons < test_season, predict test_season."""
    train = games[games["season"] < test_season]
    test = games[games["season"] == test_season].copy()

    if len(train) == 0:
        logger.error("No training data for test season %d", test_season)
        return pd.DataFrame()

    if len(test) == 0:
        logger.error("No test data for season %d", test_season)
        return pd.DataFrame()

    logger.info(
        "Training on %d games (seasons %s), testing on %d (%d)",
        len(train),
        sorted(train["season"].unique()),
        len(test),
        test_season,
    )

    model = PoissonModel()
    model.fit(train)

    # Pre-compute league avg xFIP from prior season (temporal safety)
    prior_season = test_season - 1
    league_avg_xfip = 4.2
    if pitcher_adj and pitcher_stats:
        league_avg_xfip = compute_league_avg_xfip(
            pitcher_stats, prior_season, min_gs=MLB_MODEL.PITCHER_MIN_GS_FOR_LEAGUE_AVG
        )
        logger.info(
            "Pitcher adj ON: prior season %d, league avg xFIP = %.3f",
            prior_season,
            league_avg_xfip,
        )

    # Platt calibration on training set predictions
    if calibrated:
        logger.info("Calibrating on %d training games...", len(train))
        train_probs = []
        train_outcomes = []
        for _, trow in train.iterrows():
            h_id = int(trow["home_team_id"])
            a_id = int(trow["away_team_id"])
            if h_id not in model.team_ratings or a_id not in model.team_ratings:
                continue
            if trow["home_score"] == trow["away_score"]:
                continue
            tpred = model.predict(h_id, a_id)
            train_probs.append(tpred["moneyline_home"])
            train_outcomes.append(1 if trow["home_score"] > trow["away_score"] else 0)
        model.calibrate(np.array(train_probs), np.array(train_outcomes))

    # Build odds lookup dict
    odds_by_pk: dict[int, dict] = {}
    if odds_df is not None and not odds_df.empty:
        for _, orow in odds_df.iterrows():
            odds_by_pk[int(orow["game_pk"])] = orow.to_dict()

    results = []
    skipped_ties = 0
    skipped_unknown = 0
    pitcher_found = 0
    pitcher_missing = 0

    for _, row in test.iterrows():
        if row["home_score"] == row["away_score"]:
            skipped_ties += 1
            continue

        home_id = int(row["home_team_id"])
        away_id = int(row["away_team_id"])

        # Skip games with teams not seen in training data
        if home_id not in model.team_ratings or away_id not in model.team_ratings:
            skipped_unknown += 1
            continue

        # Compute pitcher adjustments
        home_padj = 1.0
        away_padj = 1.0
        game_pitcher_found = False

        if pitcher_adj and pitcher_stats:
            home_starter = row.get("home_starter_id")
            away_starter = row.get("away_starter_id")

            if home_starter and not pd.isna(home_starter):
                home_key = (int(home_starter), prior_season)
                home_ps = pitcher_stats.get(home_key)
                if home_ps:
                    home_padj = compute_pitcher_adj(
                        xfip=home_ps["xfip"],
                        league_avg_xfip=league_avg_xfip,
                        ip=home_ps["ip"],
                        stabilization_ip=MLB_MODEL.PITCHER_XFIP_STABILIZATION_IP,
                        clamp_low=MLB_MODEL.PITCHER_XFIP_CLAMP_LOW,
                        clamp_high=MLB_MODEL.PITCHER_XFIP_CLAMP_HIGH,
                    )
                    game_pitcher_found = True

            if away_starter and not pd.isna(away_starter):
                away_key = (int(away_starter), prior_season)
                away_ps = pitcher_stats.get(away_key)
                if away_ps:
                    away_padj = compute_pitcher_adj(
                        xfip=away_ps["xfip"],
                        league_avg_xfip=league_avg_xfip,
                        ip=away_ps["ip"],
                        stabilization_ip=MLB_MODEL.PITCHER_XFIP_STABILIZATION_IP,
                        clamp_low=MLB_MODEL.PITCHER_XFIP_CLAMP_LOW,
                        clamp_high=MLB_MODEL.PITCHER_XFIP_CLAMP_HIGH,
                    )
                    game_pitcher_found = True

        if game_pitcher_found:
            pitcher_found += 1
        elif pitcher_adj:
            pitcher_missing += 1

        pred = model.predict(
            home_id,
            away_id,
            home_pitcher_adj=home_padj,
            away_pitcher_adj=away_padj,
        )
        home_won = row["home_score"] > row["away_score"]
        raw_prob = pred["moneyline_home"]
        cal_prob = model.calibrate_prob(raw_prob) if calibrated else raw_prob

        # Odds integration
        game_pk = int(row["game_pk"])
        odds = odds_by_pk.get(game_pk, {})
        home_ml_open = odds.get("home_ml_open")
        away_ml_open = odds.get("away_ml_open")
        home_ml_close = odds.get("home_ml_close")
        away_ml_close = odds.get("away_ml_close")

        edge_home = None
        edge_away = None
        bet_side = None
        bet_odds = None
        stake = 0.0
        pnl = None
        clv = None

        if home_ml_close is not None and away_ml_close is not None:
            try:
                fair_home_close = devig_prob(int(home_ml_close), int(away_ml_close))
                fair_away_close = 1.0 - fair_home_close
                edge_home = cal_prob - fair_home_close
                edge_away = (1 - cal_prob) - fair_away_close
            except (ValueError, TypeError):
                pass
        elif home_ml_close is not None:
            try:
                edge_home = cal_prob - american_to_implied_prob(int(home_ml_close))
            except (ValueError, TypeError):
                pass
        elif away_ml_close is not None:
            try:
                edge_away = (1 - cal_prob) - american_to_implied_prob(int(away_ml_close))
            except (ValueError, TypeError):
                pass

        # Simulate bet on the side with best edge above threshold
        if edge_home is not None and edge_away is not None:
            best_edge = max(edge_home, edge_away)
        elif edge_home is not None:
            best_edge = edge_home
        elif edge_away is not None:
            best_edge = edge_away
        else:
            best_edge = None

        if best_edge is not None and best_edge >= EDGE_THRESHOLD:
            if (
                edge_home is not None
                and edge_home >= EDGE_THRESHOLD
                and (edge_away is None or edge_home >= edge_away)
            ):
                bet_side = "home"
                bet_odds = int(home_ml_close)
                win_prob = cal_prob
                did_win = home_won
            elif edge_away is not None and edge_away >= EDGE_THRESHOLD:
                bet_side = "away"
                bet_odds = int(away_ml_close)
                win_prob = 1 - cal_prob
                did_win = not home_won
            else:
                bet_side = None

            if bet_side is not None and bet_odds is not None:
                stake = _kelly_stake(win_prob, bet_odds)
                if stake > 0:
                    try:
                        decimal = american_to_decimal(bet_odds)
                        pnl = stake * (decimal - 1) if did_win else -stake
                    except ValueError:
                        stake = 0.0

        # CLV: de-vigged open vs de-vigged close (requires all 4 odds)
        has_all_four = all(
            x is not None for x in [home_ml_open, away_ml_open, home_ml_close, away_ml_close]
        )
        if bet_side == "home" and has_all_four:
            try:
                fair_home_open = devig_prob(int(home_ml_open), int(away_ml_open))
                fair_home_close = devig_prob(int(home_ml_close), int(away_ml_close))
                if fair_home_open > 0:
                    clv = (fair_home_close - fair_home_open) / fair_home_open
            except (ValueError, TypeError):
                pass
        elif bet_side == "away" and has_all_four:
            try:
                fair_away_open = devig_prob(int(away_ml_open), int(home_ml_open))
                fair_away_close = devig_prob(int(away_ml_close), int(home_ml_close))
                if fair_away_open > 0:
                    clv = (fair_away_close - fair_away_open) / fair_away_open
            except (ValueError, TypeError):
                pass

        results.append(
            {
                "game_pk": game_pk,
                "game_date": row["game_date"],
                "home_team_id": home_id,
                "away_team_id": away_id,
                "home_score": row["home_score"],
                "away_score": row["away_score"],
                "pred_home_prob": cal_prob,
                "pred_home_prob_raw": raw_prob,
                "pred_lambda_home": pred["lambda_home"],
                "pred_lambda_away": pred["lambda_away"],
                "home_won": home_won,
                "correct": (cal_prob > 0.5) == home_won,
                "home_pitcher_adj": home_padj,
                "away_pitcher_adj": away_padj,
                # Odds columns
                "home_ml_close": home_ml_close,
                "away_ml_close": away_ml_close,
                "home_ml_open": home_ml_open,
                "away_ml_open": away_ml_open,
                "edge_home": edge_home,
                "edge_away": edge_away,
                "bet_side": bet_side,
                "bet_odds": bet_odds,
                "stake": stake,
                "pnl": pnl,
                "clv": clv,
            }
        )

    if skipped_ties > 0:
        logger.info("Skipped %d tied games", skipped_ties)
    if skipped_unknown > 0:
        logger.warning("Skipped %d games with unknown teams", skipped_unknown)
    if pitcher_adj:
        total_games = pitcher_found + pitcher_missing
        coverage = pitcher_found / total_games * 100 if total_games > 0 else 0
        logger.info("Pitcher coverage: %d/%d (%.1f%%)", pitcher_found, total_games, coverage)

    return pd.DataFrame(results)


def print_report(results: pd.DataFrame, test_season: int, pitcher_adj: bool = False) -> None:
    """Print backtest summary."""
    if results.empty:
        print(f"No results for season {test_season}")
        return

    n = len(results)
    correct = results["correct"].sum()
    accuracy = correct / n

    # Log loss
    eps = 1e-10
    probs = results["pred_home_prob"].clip(eps, 1 - eps)
    actuals = results["home_won"].astype(float)
    log_loss = -(actuals * np.log(probs) + (1 - actuals) * np.log(1 - probs)).mean()

    # Calibration
    results = results.copy()
    results["prob_bin"] = pd.cut(results["pred_home_prob"], bins=10)
    cal = results.groupby("prob_bin", observed=True).agg(
        pred_avg=("pred_home_prob", "mean"),
        actual_avg=("home_won", "mean"),
        count=("home_won", "count"),
    )

    model_label = "v1+pitcher" if pitcher_adj else "v1"
    print(f"\n{'=' * 60}")
    print(f"MLB Poisson Model {model_label} -- Backtest {test_season}")
    print(f"{'=' * 60}")
    print(f"Games:      {n}")
    print(f"Accuracy:   {accuracy:.1%} ({correct}/{n})")
    print(f"Log Loss:   {log_loss:.4f}")

    # Pitcher coverage stats
    if pitcher_adj and "home_pitcher_adj" in results.columns:
        has_adj = (results["home_pitcher_adj"] != 1.0) | (results["away_pitcher_adj"] != 1.0)
        n_adj = has_adj.sum()
        print(f"\nPitcher Adj: {n_adj}/{n} games ({n_adj / n:.1%} coverage)")
        if n_adj > 0:
            adj_vals = pd.concat([results["home_pitcher_adj"], results["away_pitcher_adj"]])
            adj_vals = adj_vals[adj_vals != 1.0]
            print(
                f"  Adj range: [{adj_vals.min():.3f}, {adj_vals.max():.3f}], "
                f"mean={adj_vals.mean():.3f}"
            )

    print("\nCalibration:")
    print(f"{'Predicted':>12} {'Actual':>10} {'Count':>8}")
    print(f"{'-' * 32}")
    for _, row in cal.iterrows():
        print(f"{row['pred_avg']:>12.1%} {row['actual_avg']:>10.1%} {int(row['count']):>8}")

    # Odds / betting section
    if "pnl" in results.columns and results["home_ml_close"].notna().any():
        odds_games = results["home_ml_close"].notna().sum()
        bets = results[results["stake"] > 0].copy()
        print(f"\n{'=' * 60}")
        print(f"Odds Coverage: {odds_games}/{n} games ({odds_games / n:.1%})")
        if not bets.empty:
            n_bets = len(bets)
            total_staked = bets["stake"].sum()
            total_pnl = bets["pnl"].sum()
            roi = total_pnl / total_staked if total_staked > 0 else 0.0
            wins = (bets["pnl"] > 0).sum()
            win_rate = wins / n_bets
            print(f"\nBets placed ({EDGE_THRESHOLD:.0%} edge threshold):")
            print(f"  Count:       {n_bets} ({n_bets / odds_games:.1%} of games with odds)")
            print(f"  Win rate:    {win_rate:.1%} ({wins}/{n_bets})")
            print(f"  Total staked: ${total_staked:.0f}")
            print(f"  Net PnL:     ${total_pnl:+.0f}")
            print(f"  ROI:         {roi:+.1%}")
            # CLV (subset with opening odds)
            clv_bets = bets[bets["clv"].notna()]
            if not clv_bets.empty:
                avg_clv = clv_bets["clv"].mean()
                print(f"  Avg CLV:     {avg_clv:+.2%} ({len(clv_bets)} bets with open/close)")
            # Edge distribution
            all_edges = pd.concat(
                [
                    results["edge_home"].dropna(),
                    results["edge_away"].dropna(),
                ]
            )
            pos_edges = all_edges[all_edges >= EDGE_THRESHOLD]
            print("\nEdge distribution (games with odds, home+away):")
            print(f"  Games with any odds: {odds_games}")
            print(f"  Edges >= {EDGE_THRESHOLD:.0%}: {len(pos_edges)}")
            if len(pos_edges) > 0:
                print(f"  Avg positive edge: {pos_edges.mean():+.2%}")
        else:
            print(f"No bets met {EDGE_THRESHOLD:.0%} edge threshold")

    print(f"{'=' * 60}")


def main() -> None:
    """CLI entry point for MLB walk-forward backtest."""
    parser = argparse.ArgumentParser(description="MLB Poisson model walk-forward backtest")
    parser.add_argument(
        "--test-season",
        type=int,
        default=2025,
        help="Season to test on (trains on all prior)",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default=str(DB_PATH),
        help="Path to mlb_data.db",
    )
    parser.add_argument(
        "--pitcher-adj",
        action="store_true",
        default=False,
        help="Enable starting pitcher xFIP adjustment",
    )
    parser.add_argument(
        "--calibrated",
        action="store_true",
        default=False,
        help="Apply Platt calibration on training set predictions",
    )
    parser.add_argument(
        "--odds",
        action="store_true",
        default=False,
        help="Load odds table and compute edge/ROI/CLV",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path)
    games = load_games(db_path)
    logger.info(
        "Loaded %d games across seasons %s",
        len(games),
        sorted(games["season"].unique()),
    )

    # Load pitcher stats if needed
    pitcher_stats = None
    if args.pitcher_adj:
        pitcher_stats = load_pitcher_stats(db_path)
        logger.info("Loaded %d pitcher-season stat rows", len(pitcher_stats))

    # Load odds if requested
    odds_df = None
    if args.odds:
        odds_df = load_odds(db_path)
        logger.info("Loaded %d odds rows", len(odds_df))

    results = run_backtest(
        games,
        args.test_season,
        pitcher_adj=args.pitcher_adj,
        pitcher_stats=pitcher_stats,
        calibrated=args.calibrated,
        odds_df=odds_df,
    )
    print_report(results, args.test_season, pitcher_adj=args.pitcher_adj)

    # Save results
    out_dir = PROJECT_ROOT / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = ""
    if args.pitcher_adj:
        suffix += "_pitcher"
    if args.calibrated:
        suffix += "_calibrated"
    if args.odds:
        suffix += "_odds"
    out_path = out_dir / f"mlb_backtest_{args.test_season}{suffix}.parquet"
    results.to_parquet(out_path, index=False)
    logger.info("Saved results to %s", out_path)


if __name__ == "__main__":
    main()
