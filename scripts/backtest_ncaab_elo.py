"""Walk-Forward Backtest for NCAAB Elo Model.

Loads a trained model, holds out the most recent season for testing,
and runs a walk-forward backtest: for each game date, predict -> evaluate
-> update ratings.

Uses real ESPN odds data when available (default), or simulated odds
with --simulate flag.

Usage:
    python scripts/backtest_ncaab_elo.py
    python scripts/backtest_ncaab_elo.py --test-season 2025 --min-edge 0.02
    python scripts/backtest_ncaab_elo.py --simulate  # Use simulated odds (legacy)
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
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
from features.sport_specific.ncaab.advanced_features import NCABBFeatureEngine
from models.model_persistence import load_model
from models.sport_specific.ncaab.team_ratings import NCAABEloModel
from features.sport_specific.ncaab.breadwinner import (
    BreadwinnerScores,
    get_breadwinner_adjustment,
)
from pipelines.barttorvik_fetcher import compute_barttorvik_differentials
from pipelines.kenpom_fetcher import compute_kenpom_differentials

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class BarttovikCoeffs:
    """Coefficients for Barttorvik probability adjustment.

    net_diff_coeff: Multiplier on (AdjO - AdjD) differential.
        Typical diff ~10pts, target ~3% adj. Default 0.003.
    barthag_diff_coeff: Multiplier on Barthag differential.
        Typical diff ~0.1-0.3, target ~1-3% adj. Default 0.1.
    """

    net_diff_coeff: float = 0.003
    barthag_diff_coeff: float = 0.1


@dataclass
class KenPomCoeffs:
    """Coefficients for KenPom probability adjustment.

    net_diff_coeff: Multiplier on AdjEM differential.
        Typical diff ~5-15pts. Default 0.005.
    sos_coeff: Multiplier on SOS-AdjEM differential.
        Optional schedule strength adjustment. Default 0.0 (disabled).
    """

    net_diff_coeff: float = 0.005
    sos_coeff: float = 0.0


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

        # Detect NCAA Tournament games
        season_type = row.get("season_type")
        is_tournament = False
        if season_type is not None and not pd.isna(season_type):
            is_tournament = int(season_type) == 3
        elif location not in ("home", "away"):
            # Date-based heuristic for data without season_type
            if hasattr(game_date, "month"):
                is_tournament = (
                    game_date.month == 3 and game_date.day >= 14
                ) or game_date.month == 4

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
                "is_tournament": is_tournament,
            }
        )

    games.sort(key=lambda g: g["date"])
    return games


def load_odds_data(season: int, provider_id: int = 58) -> dict[str, dict]:
    """Load real odds data and index by game_id.

    Args:
        season: Season year (e.g. 2025).
        provider_id: ESPN provider ID (58=ESPN BET, 100=DraftKings).

    Returns:
        Dict mapping game_id -> odds dict with opening/closing lines.
    """
    odds_path = Path("data/odds") / f"ncaab_odds_{season}.parquet"
    if not odds_path.exists():
        logger.warning("No odds file found at %s", odds_path)
        return {}

    df = pd.read_parquet(odds_path)
    provider_df = df[df["provider_id"] == provider_id]

    if provider_df.empty:
        # Try any available provider
        logger.warning("Provider %d not found, using first available", provider_id)
        provider_df = df.drop_duplicates(subset=["game_id"], keep="first")

    odds_lookup: dict[str, dict] = {}
    for _, row in provider_df.iterrows():
        game_id = str(row["game_id"])
        odds_lookup[game_id] = {
            "home_ml_open": row.get("home_ml_open"),
            "away_ml_open": row.get("away_ml_open"),
            "home_ml_close": row.get("home_ml_close"),
            "away_ml_close": row.get("away_ml_close"),
            "home_moneyline": row.get("home_moneyline"),
            "away_moneyline": row.get("away_moneyline"),
            "spread": row.get("spread"),
            "home_spread_close": row.get("home_spread_close"),
        }

    logger.info(
        "Loaded %d games with real odds (provider %d) for season %d",
        len(odds_lookup),
        provider_id,
        season,
    )
    return odds_lookup


def _get_real_odds(
    odds_lookup: dict[str, dict], game_id: str
) -> tuple[int | None, int | None, int | None, int | None]:
    """Extract opening and closing moneylines for a game.

    Returns:
        (home_ml_open, away_ml_open, home_ml_close, away_ml_close)
        Any value may be None if not available.
    """
    entry = odds_lookup.get(str(game_id))
    if entry is None:
        return None, None, None, None

    home_open = entry["home_ml_open"]
    away_open = entry["away_ml_open"]
    home_close = entry["home_ml_close"]
    away_close = entry["away_ml_close"]

    # Fall back to current moneyline if open/close missing
    if pd.isna(home_open):
        home_open = entry["home_moneyline"]
    if pd.isna(away_open):
        away_open = entry["away_moneyline"]
    if pd.isna(home_close):
        home_close = entry["home_moneyline"]
    if pd.isna(away_close):
        away_close = entry["away_moneyline"]

    # Convert to int if valid (0 is invalid for American odds)
    def _to_int(v: float | None) -> int | None:
        if v is None or pd.isna(v):
            return None
        val = int(v)
        if val == 0:
            return None
        return val

    return _to_int(home_open), _to_int(away_open), _to_int(home_close), _to_int(away_close)


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
    odds_lookup: dict[str, dict] | None = None,
    use_simulated: bool = False,
    kelly_sizer=None,
) -> pd.DataFrame:
    """Run walk-forward backtest.

    For each game: predict -> get odds -> check edge -> size bet ->
    record -> update model.

    Args:
        model: Trained NCAABEloModel.
        games: Chronologically sorted game list.
        min_edge: Minimum edge to place a bet.
        kelly_fraction: Kelly fraction for sizing.
        max_bet: Maximum bet as fraction of bankroll.
        bankroll: Starting bankroll.
        odds_lookup: Dict mapping game_id -> odds dict (real odds).
        use_simulated: If True, use simulated odds instead of real.

    Returns:
        DataFrame of backtest results.
    """
    np.random.seed(42)  # Reproducibility
    results = []
    current_bankroll = bankroll
    skipped_no_odds = 0

    for game in games:
        home = game["home"]
        away = game["away"]
        home_score = game["home_score"]
        away_score = game["away_score"]
        neutral = game["neutral_site"]
        game_id = game["game_id"]
        is_tourn = game.get("is_tournament", False)

        # 1. PREDICT (before seeing result)
        home_win_prob = model.predict_win_probability(home, away, neutral)
        predicted_spread = model.predict_spread(home, away, neutral)

        # 2. GET ODDS (real or simulated)
        if use_simulated or odds_lookup is None:
            market_odds_home = simulate_market_odds(home_win_prob)
            market_odds_away = simulate_market_odds(1 - home_win_prob)
            closing_odds_home = simulate_closing_odds(market_odds_home)
            closing_odds_away = simulate_closing_odds(market_odds_away)
        else:
            home_open, away_open, home_close, away_close = _get_real_odds(odds_lookup, game_id)
            if home_open is None or away_open is None:
                # No odds for this game — still update model, skip betting
                model.update_game(
                    home, away, home_score, away_score, neutral, is_tournament=is_tourn
                )
                skipped_no_odds += 1
                continue
            market_odds_home = home_open
            market_odds_away = away_open
            closing_odds_home = home_close if home_close is not None else home_open
            closing_odds_away = away_close if away_close is not None else away_open

        # 3. CALCULATE EDGE (both sides)
        home_edge = calculate_edge(home_win_prob, market_odds_home)
        away_edge = calculate_edge(1 - home_win_prob, market_odds_away)

        # 4. PICK BEST SIDE (if either qualifies)
        if abs(home_edge) >= min_edge or abs(away_edge) >= min_edge:
            if home_edge > away_edge and home_edge >= min_edge:
                bet_side = "home"
                bet_prob = home_win_prob
                bet_odds = market_odds_home
                closing_odds = closing_odds_home
                won = home_score > away_score
            elif away_edge >= min_edge:
                bet_side = "away"
                bet_prob = 1 - home_win_prob
                bet_odds = market_odds_away
                closing_odds = closing_odds_away
                won = away_score > home_score
            else:
                # Home edge is negative but above threshold on abs, skip
                model.update_game(
                    home, away, home_score, away_score, neutral, is_tournament=is_tourn
                )
                continue

            # 5. SIZE BET (Kelly)
            decimal_odds = american_to_decimal(bet_odds)
            if kelly_sizer is not None:
                stake = kelly_sizer.size_bet(
                    model_prob=bet_prob,
                    edge=max(home_edge, away_edge),
                    american_odds=bet_odds,
                )
            else:
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
                        "game_id": game_id,
                        "date": game["date"],
                        "home": home,
                        "away": away,
                        "home_score": home_score,
                        "away_score": away_score,
                        "bet_side": bet_side,
                        "model_prob": bet_prob,
                        "edge": max(home_edge, away_edge),
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
        model.update_game(home, away, home_score, away_score, neutral, is_tournament=is_tourn)

    if skipped_no_odds > 0:
        logger.info("Skipped %d games with no odds data", skipped_no_odds)

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

    # ROI (Kelly-compound)
    roi = total_pnl / total_staked if total_staked > 0 else 0

    # Flat-stake ROI: mean of per-bet returns (the valid metric for significance)
    per_bet_returns = df["profit_loss"] / df["stake"]
    flat_roi = float(per_bet_returns.mean())

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
        "flat_roi": flat_roi,
        "avg_clv": avg_clv,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
        "final_bankroll": df["bankroll"].iloc[-1] if not df.empty else initial_bankroll,
        "avg_edge": df["edge"].mean(),
        "avg_stake": df["stake"].mean(),
    }


def _build_team_game_logs(
    games: list[dict],
    model: NCAABEloModel,
) -> dict[str, pd.DataFrame]:
    """Build per-team game logs from the game list for feature computation.

    Each team's log contains one row per game with point_diff, opp_elo, date.
    Games are added chronologically — the returned DataFrames grow as the
    backtest loop progresses (call _append_game_to_logs to extend).

    Args:
        games: Chronologically sorted game list.
        model: Model to look up opponent Elo ratings.

    Returns:
        Empty dict (populated incrementally during backtest).
    """
    return {}


def _append_game_to_logs(
    logs: dict[str, list[dict]],
    game: dict,
    model: NCAABEloModel,
) -> None:
    """Append a completed game to both teams' rolling logs.

    Called AFTER model.update_game() so the log reflects post-game state
    but features computed from the log use .shift(1) so the current game
    is never included in its own features.
    """
    home, away = game["home"], game["away"]
    home_score, away_score = game["home_score"], game["away_score"]
    game_date = game["date"]

    for team, opp, pts_for, pts_against in [
        (home, away, home_score, away_score),
        (away, home, away_score, home_score),
    ]:
        if team not in logs:
            logs[team] = []
        logs[team].append(
            {
                "date": game_date,
                "team_id": team,
                "point_diff": pts_for - pts_against,
                "opp_elo": model.get_rating(opp),
            }
        )


def _get_team_features(
    logs: dict[str, list[dict]],
    team: str,
    engine: NCABBFeatureEngine,
) -> pd.Series | None:
    """Get the latest feature values for a team from their game log.

    Returns None if the team has insufficient history.
    """
    if team not in logs or len(logs[team]) < 2:
        return None

    team_df = pd.DataFrame(logs[team])
    features = engine.compute_all(team_df)

    # Return the last row (latest features, which are lagged by shift(1))
    last_row = features.iloc[-1]
    if last_row.isna().all():
        return None
    return last_row


def run_backtest_with_features(
    model: NCAABEloModel,
    games: list[dict],
    feature_engine: NCABBFeatureEngine | None = None,
    feature_weight: float = 0.0,
    barttorvik_df: pd.DataFrame | None = None,
    barttorvik_weight: float = 0.0,
    team_mapper: Callable[[str], str | None] | None = None,
    bart_coeffs: BarttovikCoeffs | None = None,
    kenpom_df: pd.DataFrame | None = None,
    kenpom_weight: float = 0.0,
    kenpom_mapper: Callable[[str], str | None] | None = None,
    kenpom_coeffs: KenPomCoeffs | None = None,
    breadwinner_lookup: dict[str, BreadwinnerScores] | None = None,
    breadwinner_weight: float = 0.0,
    breadwinner_coeff: float = 0.01,
    breadwinner_variant: str = "top1",
    breadwinner_include_centers: bool = True,
    min_edge: float = 0.02,
    kelly_fraction: float = 0.25,
    max_bet: float = 0.03,
    bankroll: float = 5000.0,
    odds_lookup: dict[str, dict] | None = None,
    use_simulated: bool = False,
    kelly_sizer=None,
) -> pd.DataFrame:
    """Run walk-forward backtest with optional feature adjustments.

    Wraps run_backtest() logic but injects feature-based probability
    adjustments between Elo prediction and edge calculation.

    The adjusted probability is:
        adjusted_prob = clamp(elo_prob + feature_adj + barttorvik_adj + kenpom_adj + bw_adj, 0.01, 0.99)

    where feature_adjustment is derived from matchup differentials in:
    - Opponent-quality-weighted margin (form quality)
    - Rolling volatility (consistency)
    - Rest day advantage

    And barttorvik_adjustment is derived from:
    - Net rating differential (AdjO - AdjD)
    - Barthag differential (overall team quality)

    And breadwinner_adjustment compresses predictions toward 50% for
    teams with concentrated player production (high variance teams).

    When weights=0 or lookups=None, those adjustments are skipped.

    Args:
        model: Trained NCAABEloModel (WILL BE MUTATED — deepcopy before calling).
        games: Chronologically sorted game list.
        feature_engine: Feature engine instance (None = skip feature adj).
        feature_weight: Weight for feature adjustment (0.0 = no adjustment).
        barttorvik_df: Season ratings DataFrame for PIT lookup.
        barttorvik_weight: Weight for Barttorvik adjustment (0.0 = no adjustment).
        team_mapper: Callable mapping ESPN team_id -> Barttorvik name.
        breadwinner_lookup: Dict mapping team -> BreadwinnerScores.
        breadwinner_weight: Weight for breadwinner adjustment (0.0 = skip).
        breadwinner_coeff: Variance compression coefficient.
        breadwinner_variant: "top1", "top2", or "hhi".
        breadwinner_include_centers: If False, skip center breadwinners.
        min_edge: Minimum edge to place a bet.
        kelly_fraction: Kelly fraction for sizing.
        max_bet: Maximum bet as fraction of bankroll.
        bankroll: Starting bankroll.
        odds_lookup: Dict mapping game_id -> odds dict.
        use_simulated: If True, use simulated odds.

    Returns:
        DataFrame of backtest results.
    """
    np.random.seed(42)
    results = []
    current_bankroll = bankroll
    skipped_no_odds = 0
    team_logs: dict[str, list[dict]] = {}

    use_features = feature_engine is not None and feature_weight != 0.0
    use_barttorvik = (
        barttorvik_df is not None and barttorvik_weight != 0.0 and team_mapper is not None
    )
    use_kenpom = kenpom_df is not None and kenpom_weight != 0.0 and kenpom_mapper is not None

    for game in games:
        home = game["home"]
        away = game["away"]
        home_score = game["home_score"]
        away_score = game["away_score"]
        neutral = game["neutral_site"]
        game_id = game["game_id"]
        is_tourn = game.get("is_tournament", False)

        # 1. PREDICT (Elo baseline)
        home_win_prob = model.predict_win_probability(home, away, neutral)
        predicted_spread = model.predict_spread(home, away, neutral)

        # 1b. FEATURE ADJUSTMENT (if enabled)
        feature_adj = 0.0
        if use_features:
            home_feats = _get_team_features(team_logs, home, feature_engine)
            away_feats = _get_team_features(team_logs, away, feature_engine)

            if home_feats is not None and away_feats is not None:
                diffs = NCABBFeatureEngine.compute_matchup_differentials(home_feats, away_feats)

                # Combine differentials into single adjustment
                # Positive oq_margin_diff => home has better quality-adjusted form
                # Negative vol_diff => home is more consistent (lower vol)
                # Positive rest_days_diff => home is more rested
                adj_components = []
                oq = diffs.get("oq_margin_10_diff", np.nan)
                if pd.notna(oq):
                    adj_components.append(oq * 0.003)  # ~0.3% per point

                vol = diffs.get("vol_5_diff", np.nan)
                if pd.notna(vol):
                    adj_components.append(-vol * 0.002)  # Lower vol = advantage

                rest = diffs.get("rest_days_diff", np.nan)
                if pd.notna(rest):
                    adj_components.append(rest * 0.005)  # ~0.5% per rest day

                decay = diffs.get("decay_margin_10_diff", np.nan)
                if pd.notna(decay):
                    adj_components.append(decay * 0.002)  # Recent form

                # Back-to-back penalty
                if diffs.get("home_b2b", 0) == 1.0:
                    adj_components.append(-0.02)  # -2% for B2B
                if diffs.get("away_b2b", 0) == 1.0:
                    adj_components.append(0.02)  # +2% for opponent B2B

                if adj_components:
                    feature_adj = sum(adj_components)

            # Apply adjustment
            home_win_prob = max(0.01, min(0.99, home_win_prob + feature_weight * feature_adj))

        # 1c. BARTTORVIK ADJUSTMENT (if enabled)
        bart_adj = 0.0
        if use_barttorvik:
            home_bart = team_mapper(home)
            away_bart = team_mapper(away)
            if home_bart and away_bart:
                game_date = game["date"]
                if hasattr(game_date, "date"):
                    game_date = game_date.date()
                diffs = compute_barttorvik_differentials(
                    barttorvik_df,
                    home_bart,
                    away_bart,
                    game_date,
                )
                if diffs:
                    coeffs = bart_coeffs or BarttovikCoeffs()
                    net_diff = diffs.get("net_rating_diff", 0)
                    barthag_diff = diffs.get("barthag_diff", 0)
                    bart_adj = (
                        net_diff * coeffs.net_diff_coeff + barthag_diff * coeffs.barthag_diff_coeff
                    )

            home_win_prob = max(0.01, min(0.99, home_win_prob + barttorvik_weight * bart_adj))

        # 1d. KENPOM ADJUSTMENT (if enabled)
        kp_adj = 0.0
        if use_kenpom:
            home_kp = kenpom_mapper(home)
            away_kp = kenpom_mapper(away)
            if home_kp and away_kp:
                game_date = game["date"]
                if hasattr(game_date, "date"):
                    game_date = game_date.date()
                kp_diffs = compute_kenpom_differentials(
                    kenpom_df,
                    home_kp,
                    away_kp,
                    game_date,
                )
                if kp_diffs:
                    kp_c = kenpom_coeffs or KenPomCoeffs()
                    adj_em_diff = kp_diffs.get("adj_em_diff", 0)
                    sos_diff = kp_diffs.get("sos_adj_em_diff", 0)
                    kp_adj = adj_em_diff * kp_c.net_diff_coeff + sos_diff * kp_c.sos_coeff

            home_win_prob = max(0.01, min(0.99, home_win_prob + kenpom_weight * kp_adj))

        # 1e. BREADWINNER ADJUSTMENT (if enabled)
        if breadwinner_lookup and breadwinner_weight != 0.0:
            # Map ESPN team IDs to Barttorvik names for lookup
            home_bw_name = team_mapper(home) if team_mapper else home
            away_bw_name = team_mapper(away) if team_mapper else away
            if home_bw_name and away_bw_name:
                bw_adj = get_breadwinner_adjustment(
                    home=home_bw_name,
                    away=away_bw_name,
                    home_prob=home_win_prob,
                    lookup=breadwinner_lookup,
                    coeff=breadwinner_coeff,
                    variant=breadwinner_variant,
                    include_centers=breadwinner_include_centers,
                )
                home_win_prob = max(0.01, min(0.99, home_win_prob + breadwinner_weight * bw_adj))

        # 2. GET ODDS
        if use_simulated or odds_lookup is None:
            market_odds_home = simulate_market_odds(
                model.predict_win_probability(home, away, neutral)
            )
            market_odds_away = simulate_market_odds(
                1 - model.predict_win_probability(home, away, neutral)
            )
            closing_odds_home = simulate_closing_odds(market_odds_home)
            closing_odds_away = simulate_closing_odds(market_odds_away)
        else:
            home_open, away_open, home_close, away_close = _get_real_odds(odds_lookup, game_id)
            if home_open is None or away_open is None:
                model.update_game(
                    home, away, home_score, away_score, neutral, is_tournament=is_tourn
                )
                _append_game_to_logs(team_logs, game, model)
                skipped_no_odds += 1
                continue
            market_odds_home = home_open
            market_odds_away = away_open
            closing_odds_home = home_close if home_close is not None else home_open
            closing_odds_away = away_close if away_close is not None else away_open

        # 3. CALCULATE EDGE
        home_edge = calculate_edge(home_win_prob, market_odds_home)
        away_edge = calculate_edge(1 - home_win_prob, market_odds_away)

        # 4. PICK BEST SIDE
        if abs(home_edge) >= min_edge or abs(away_edge) >= min_edge:
            if home_edge > away_edge and home_edge >= min_edge:
                bet_side = "home"
                bet_prob = home_win_prob
                bet_odds = market_odds_home
                closing_odds = closing_odds_home
                won = home_score > away_score
            elif away_edge >= min_edge:
                bet_side = "away"
                bet_prob = 1 - home_win_prob
                bet_odds = market_odds_away
                closing_odds = closing_odds_away
                won = away_score > home_score
            else:
                model.update_game(
                    home, away, home_score, away_score, neutral, is_tournament=is_tourn
                )
                _append_game_to_logs(team_logs, game, model)
                continue

            # 5. SIZE BET
            decimal_odds = american_to_decimal(bet_odds)
            if kelly_sizer is not None:
                stake = kelly_sizer.size_bet(
                    model_prob=bet_prob,
                    edge=max(home_edge, away_edge),
                    american_odds=bet_odds,
                )
            else:
                bet_fraction = fractional_kelly(bet_prob, decimal_odds, kelly_fraction, max_bet)
                stake = current_bankroll * bet_fraction

            if stake > 0:
                if won:
                    profit = stake * (decimal_odds - 1)
                    result_str = "win"
                else:
                    profit = -stake
                    result_str = "loss"

                clv = calculate_clv(bet_odds, closing_odds)
                current_bankroll += profit

                results.append(
                    {
                        "game_id": game_id,
                        "date": game["date"],
                        "home": home,
                        "away": away,
                        "home_score": home_score,
                        "away_score": away_score,
                        "bet_side": bet_side,
                        "model_prob": bet_prob,
                        "edge": max(home_edge, away_edge),
                        "odds_placed": bet_odds,
                        "odds_closing": closing_odds,
                        "stake": stake,
                        "result": result_str,
                        "profit_loss": profit,
                        "clv": clv,
                        "bankroll": current_bankroll,
                        "predicted_spread": predicted_spread,
                        "feature_adj": feature_adj,
                        "bart_adj": bart_adj,
                        "kp_adj": kp_adj,
                    }
                )

        # 8. UPDATE MODEL and logs (always)
        model.update_game(home, away, home_score, away_score, neutral, is_tournament=is_tourn)
        _append_game_to_logs(team_logs, game, model)

    if skipped_no_odds > 0:
        logger.info("Skipped %d games with no odds data", skipped_no_odds)

    return pd.DataFrame(results)


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward backtest for NCAAB Elo")
    parser.add_argument("--test-season", type=int, default=2025)
    parser.add_argument("--min-edge", type=float, default=THRESHOLDS.MIN_EDGE_SPREAD)
    parser.add_argument("--kelly", type=float, default=BANKROLL.KELLY_FRACTION_DEFAULT)
    parser.add_argument("--max-bet", type=float, default=BANKROLL.MAX_BET_FRACTION)
    parser.add_argument("--bankroll", type=float, default=BANKROLL.TOTAL_BANKROLL)
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Use simulated odds instead of real ESPN data (legacy mode)",
    )
    parser.add_argument(
        "--barttorvik",
        action="store_true",
        help="Include Barttorvik efficiency ratings as features",
    )
    parser.add_argument(
        "--barttorvik-weight",
        type=float,
        default=1.0,
        help="Weight for Barttorvik probability adjustment (default: 1.0)",
    )
    parser.add_argument(
        "--kenpom",
        action="store_true",
        help="Include KenPom efficiency ratings as features",
    )
    parser.add_argument(
        "--kenpom-weight",
        type=float,
        default=1.0,
        help="Weight for KenPom probability adjustment (default: 1.0)",
    )
    parser.add_argument(
        "--calibrated-kelly",
        action="store_true",
        help="Use Platt-calibrated Kelly sizing instead of raw model prob",
    )
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

    # Load real odds (unless --simulate)
    odds_lookup = None
    if not args.simulate:
        odds_lookup = load_odds_data(args.test_season)
        if not odds_lookup:
            logger.warning(
                "No real odds data for season %d. Falling back to simulated odds.",
                args.test_season,
            )
    else:
        logger.info("Using simulated odds (--simulate flag)")

    odds_mode = "simulated" if args.simulate or not odds_lookup else "real"

    # Load Barttorvik data (if requested)
    barttorvik_df = None
    bart_mapper = None
    if args.barttorvik:
        from pipelines.barttorvik_fetcher import load_cached_season
        from pipelines.team_name_mapping import espn_id_to_barttorvik

        barttorvik_df = load_cached_season(args.test_season)
        if barttorvik_df is None:
            logger.error(
                "No Barttorvik data for season %d. Run fetch_barttorvik_data.py first.",
                args.test_season,
            )
            sys.exit(1)
        bart_mapper = espn_id_to_barttorvik
        logger.info(
            "Loaded Barttorvik ratings: %d rows, weight=%.2f",
            len(barttorvik_df),
            args.barttorvik_weight,
        )

    # Load KenPom data (if requested)
    kenpom_df = None
    kp_mapper = None
    if args.kenpom:
        from pipelines.kenpom_fetcher import load_cached_season as load_kenpom_cached
        from pipelines.team_name_mapping import espn_id_to_kenpom

        kenpom_df = load_kenpom_cached(args.test_season)
        if kenpom_df is None:
            logger.error(
                "No KenPom data for season %d. Run fetch_kenpom_data.py first.",
                args.test_season,
            )
            sys.exit(1)
        kp_mapper = espn_id_to_kenpom
        logger.info(
            "Loaded KenPom ratings: %d rows, weight=%.2f",
            len(kenpom_df),
            args.kenpom_weight,
        )

    # Build calibrated Kelly sizer (if requested)
    kelly_sizer = None
    if args.calibrated_kelly:
        from betting.odds_converter import KellySizer, build_calibration_data

        backtest_dir = Path("data/backtests")
        try:
            model_probs, outcomes = build_calibration_data(backtest_dir)
            kelly_sizer = KellySizer(
                kelly_fraction=args.kelly,
                max_bet_fraction=args.max_bet,
                bankroll=args.bankroll,
            )
            kelly_sizer.calibrate(model_probs, outcomes)
            logger.info("Calibrated Kelly sizer on %d bets", len(model_probs))
        except FileNotFoundError:
            logger.warning("No calibration data; falling back to raw Kelly")

    # Run backtest
    if args.barttorvik or args.kenpom:
        results = run_backtest_with_features(
            model=model,
            games=games,
            barttorvik_df=barttorvik_df,
            barttorvik_weight=args.barttorvik_weight if args.barttorvik else 0.0,
            team_mapper=bart_mapper,
            kenpom_df=kenpom_df,
            kenpom_weight=args.kenpom_weight if args.kenpom else 0.0,
            kenpom_mapper=kp_mapper,
            min_edge=args.min_edge,
            kelly_fraction=args.kelly,
            max_bet=args.max_bet,
            bankroll=args.bankroll,
            odds_lookup=odds_lookup,
            use_simulated=args.simulate,
            kelly_sizer=kelly_sizer,
        )
    else:
        results = run_backtest(
            model=model,
            games=games,
            min_edge=args.min_edge,
            kelly_fraction=args.kelly,
            max_bet=args.max_bet,
            bankroll=args.bankroll,
            odds_lookup=odds_lookup,
            use_simulated=args.simulate,
            kelly_sizer=kelly_sizer,
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
    print(f"Odds source: {odds_mode.upper()}")
    if odds_mode == "real" and odds_lookup:
        games_with_odds = sum(1 for g in games if str(g["game_id"]) in odds_lookup)
        print(f"Games with odds: {games_with_odds}/{len(games)}")
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
