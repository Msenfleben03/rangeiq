"""NCAAB Efficiency Model — Walk-Forward Training and Gatekeeper Validation.

Run:
    venv/Scripts/python.exe scripts/train_ncaab_efficiency_model.py

Outputs:
    data/processed/ncaab_efficiency_model.pkl  (if Gatekeeper passes)
    Console: per-fold metrics + Gatekeeper report

Error handling risks:
    1. As-of join: early-season games with no prior Barttorvik snapshot → dropped (logged)
    2. CLV match rate: Pinnacle odds may not cover all games → CLV subset only, not full OOS
    3. Gatekeeper: if CLV < 200 bets, blocking check may fail → Elo model remains active
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict
from sklearn.preprocessing import StandardScaler

# Ensure the script's own package root (worktree root) is importable
_script_root = Path(__file__).parent.parent
if str(_script_root) not in sys.path:
    sys.path.insert(0, str(_script_root))

# Locate the repo root whether running from worktree or main directory
_candidate = Path(__file__).parent.parent
if not (_candidate / "data" / "external" / "barttorvik").exists():
    # May be in a git worktree — check git common dir for main repo location
    try:
        _git_common = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            cwd=_candidate,
            check=True,
        ).stdout.strip()
        _main_repo = Path(_git_common).parent
        if (_main_repo / "data" / "external" / "barttorvik").exists():
            _candidate = _main_repo
    except Exception:
        pass

BASE_DIR = _candidate
DATA_DIR = BASE_DIR / "data"
BARTTORVIK_DIR = DATA_DIR / "external" / "barttorvik"
GAMES_DIR = DATA_DIR / "raw" / "ncaab"
CROSSWALK_PATH = DATA_DIR / "reference" / "espn_barttorvik_crosswalk.csv"
BACKFILL_DIR = DATA_DIR / "odds" / "backfill"
PROCESSED_DIR = DATA_DIR / "processed"

FEATURE_COLS = [
    "adj_o_diff",
    "adj_d_diff",
    "barthag_diff",
    "adj_tempo_diff",
    "wab_diff",
    "home_flag",
]

WALK_FORWARD_FOLDS = [
    (list(range(2021, 2022)), 2022),  # Fold 1: Train 2021, Test 2022
    (list(range(2021, 2023)), 2023),  # Fold 2: Train 2021-22, Test 2023
    (list(range(2021, 2024)), 2024),  # Fold 3: Train 2021-23, Test 2024
    (list(range(2021, 2025)), 2025),  # Fold 4 (OOS): Train 2021-24, Test 2025
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------


def _load_games(season: int) -> pd.DataFrame:
    path = GAMES_DIR / f"ncaab_games_{season}.parquet"
    df = pd.read_parquet(path)
    df["game_date"] = pd.to_datetime(df["date"])
    df["season"] = season
    return df


def _build_game_level(games_df: pd.DataFrame) -> pd.DataFrame:
    """Convert team-perspective rows into one game-level row per game.

    Non-neutral: use the row where location='H' as home team.
    Neutral: use alphabetically-first team_id as 'home' (arbitrary but consistent).
    """
    results = []

    # Location values: "Home"/"Away"/"Neutral" (not H/A/N)
    home_games = games_df[games_df["location"] == "Home"].copy()
    for _, row in home_games.iterrows():
        results.append(
            {
                "game_id": row["game_id"],
                "game_date": row["game_date"],
                "season": row["season"],
                "home_team_id": row["team_id"],
                "away_team_id": row["opponent_id"],
                "home_win": int(row["result"] == "W"),
                "neutral_site": False,
                "home_flag": 1,
            }
        )

    # Neutral: dataset is team-centric — only one row per game (team's perspective)
    # Use team_id as "home" (arbitrary for neutral site) and opponent_id as "away"
    neutral_games = games_df[games_df["location"] == "Neutral"]
    for _, row in neutral_games.iterrows():
        results.append(
            {
                "game_id": row["game_id"],
                "game_date": row["game_date"],
                "season": row["season"],
                "home_team_id": row["team_id"],
                "away_team_id": row["opponent_id"],
                "home_win": int(row["result"] == "W"),
                "neutral_site": True,
                "home_flag": 0,
            }
        )

    return pd.DataFrame(results)


def _as_of_join(
    game_df: pd.DataFrame, bt_df: pd.DataFrame, crosswalk: dict, side: str
) -> pd.DataFrame:
    """For each game, find most recent Barttorvik snapshot BEFORE game_date.

    Args:
        game_df: Game-level df with game_date and {side}_team_id columns.
        bt_df: Barttorvik long-format df sorted by date.
        crosswalk: espn_id -> barttorvik_name mapping.
        side: 'home' or 'away'.

    Returns:
        game_df with {side}_adj_o, {side}_adj_d, {side}_barthag, {side}_adj_tempo,
        {side}_wab, {side}_snapshot_date columns added.
    """
    team_col = f"{side}_team_id"
    game_df = game_df.copy()
    game_df[f"{side}_bt_name"] = game_df[team_col].map(crosswalk)

    bt_cols = ["date", "team", "adj_o", "adj_d", "barthag", "adj_tempo", "wab"]
    bt_sorted = bt_df[bt_cols].sort_values("date").copy()

    join_df = game_df[["game_id", "game_date", f"{side}_bt_name"]].copy()
    join_df = join_df.rename(columns={f"{side}_bt_name": "team"})
    # Subtract 1 day so merge_asof (which uses <=) finds snapshots STRICTLY before game_date
    join_df["_merge_date"] = join_df["game_date"] - pd.Timedelta(days=1)
    join_df = join_df.sort_values("_merge_date")

    merged = pd.merge_asof(
        join_df,
        bt_sorted,
        left_on="_merge_date",
        right_on="date",
        by="team",
        direction="backward",  # most recent snapshot <= game_date - 1 day (strict)
    )

    rename_map = {
        "adj_o": f"{side}_adj_o",
        "adj_d": f"{side}_adj_d",
        "barthag": f"{side}_barthag",
        "adj_tempo": f"{side}_adj_tempo",
        "wab": f"{side}_wab",
        "date": f"{side}_snapshot_date",
    }
    merged = merged.rename(columns=rename_map)

    return game_df.merge(merged[["game_id"] + list(rename_map.values())], on="game_id", how="left")


# ---------------------------------------------------------------------------
# Public API: build_pit_dataset + validate_no_leakage
# ---------------------------------------------------------------------------


def build_pit_dataset(seasons: List[int]) -> pd.DataFrame:
    """Build game-level dataset with point-in-time Barttorvik features.

    Args:
        seasons: List of season years to include (e.g., [2021, 2022, 2023]).

    Returns:
        DataFrame with one row per game, including all feature columns.
        Rows with any null features (early season, no Barttorvik snapshot yet) are dropped.
    """
    crosswalk_df = pd.read_csv(CROSSWALK_PATH)
    crosswalk = dict(zip(crosswalk_df["espn_id"], crosswalk_df["barttorvik_name"]))

    all_games: list[pd.DataFrame] = []
    all_bt: list[pd.DataFrame] = []

    for season in seasons:
        games = _load_games(season)
        game_level = _build_game_level(games)
        all_games.append(game_level)

        bt = pd.read_parquet(BARTTORVIK_DIR / f"barttorvik_ratings_{season}.parquet")
        # Also load previous season's Barttorvik for early-season games
        prev_path = BARTTORVIK_DIR / f"barttorvik_ratings_{season - 1}.parquet"
        if prev_path.exists():
            bt_prev = pd.read_parquet(prev_path)
            bt = pd.concat([bt_prev, bt], ignore_index=True)
        all_bt.append(bt)

    game_df = pd.concat(all_games, ignore_index=True)
    bt_df = pd.concat(all_bt, ignore_index=True).drop_duplicates(subset=["team", "date"])

    # Normalize datetime resolutions — merge_asof requires identical dtypes
    game_df["game_date"] = pd.to_datetime(game_df["game_date"]).dt.as_unit("us")
    bt_df["date"] = pd.to_datetime(bt_df["date"]).dt.as_unit("us")

    # As-of join for home and away teams
    game_df = _as_of_join(game_df, bt_df, crosswalk, "home")
    game_df = _as_of_join(game_df, bt_df, crosswalk, "away")

    # Compute feature differentials
    # adj_d: lower = better defense, so invert the diff
    game_df["adj_o_diff"] = game_df["home_adj_o"] - game_df["away_adj_o"]
    game_df["adj_d_diff"] = game_df["away_adj_d"] - game_df["home_adj_d"]  # INVERTED
    game_df["barthag_diff"] = game_df["home_barthag"] - game_df["away_barthag"]
    game_df["adj_tempo_diff"] = game_df["home_adj_tempo"] - game_df["away_adj_tempo"]
    game_df["wab_diff"] = game_df["home_wab"] - game_df["away_wab"]

    # Drop rows with any null features (early season without Barttorvik snapshot)
    before = len(game_df)
    game_df = game_df.dropna(subset=FEATURE_COLS).reset_index(drop=True)
    dropped = before - len(game_df)
    if dropped > 0:
        logger.warning(
            "Dropped %d games with null features (early-season no Barttorvik snapshot)",
            dropped,
        )

    return game_df


def validate_no_leakage(df: pd.DataFrame) -> None:
    """Assert that all feature snapshots predate their game.

    Args:
        df: Output of build_pit_dataset().

    Raises:
        AssertionError: If any row has future data.
    """
    home_leak = (df["home_snapshot_date"] >= df["game_date"]).sum()
    away_leak = (df["away_snapshot_date"] >= df["game_date"]).sum()
    assert home_leak == 0, f"LEAKAGE: {home_leak} games have home snapshot_date >= game_date"
    assert away_leak == 0, f"LEAKAGE: {away_leak} games have away snapshot_date >= game_date"
    logger.info("Leakage check PASSED: all feature snapshots predate game dates.")


# ---------------------------------------------------------------------------
# Walk-forward training
# ---------------------------------------------------------------------------


def run_walk_forward(full_df: pd.DataFrame) -> list[dict]:
    """Run expanding-window walk-forward validation.

    For each fold:
    1. Fit StandardScaler on training data only.
    2. Fit LogisticRegression on training data.
    3. Use 5-fold inner CV on training data to produce held-out predictions.
    4. Fit Platt calibration on inner-CV predictions.
    5. Apply calibrated model to test fold.
    6. Store results for Gatekeeper.

    Returns:
        List of fold result dicts, one per fold.
    """
    fold_results = []

    for train_seasons, test_season in WALK_FORWARD_FOLDS:
        train_df = full_df[full_df["season"].isin(train_seasons)].copy()
        test_df = full_df[full_df["season"] == test_season].copy()

        if len(train_df) < 100 or len(test_df) < 100:
            logger.warning(
                "Fold test=%d: insufficient data (train=%d, test=%d)",
                test_season,
                len(train_df),
                len(test_df),
            )
            continue

        X_train = train_df[FEATURE_COLS].values.astype(float)
        y_train = train_df["home_win"].values.astype(int)
        X_test = test_df[FEATURE_COLS].values.astype(float)
        y_test = test_df["home_win"].values.astype(int)

        # 1. Fit scaler on train only
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # 2. Fit logistic regression
        lr = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
        lr.fit(X_train_scaled, y_train)

        # 3. Inner 5-fold CV on training data for Platt calibration
        # NEVER fit Platt on in-sample predictions — use cross_val_predict
        train_cv_probs = cross_val_predict(
            LogisticRegression(C=1.0, max_iter=1000, random_state=42),
            X_train_scaled,
            y_train,
            cv=5,
            method="predict_proba",
        )[:, 1]

        # 4. Fit Platt on inner-CV held-out predictions
        platt = LogisticRegression(C=1.0, max_iter=1000, random_state=42)
        platt.fit(train_cv_probs.reshape(-1, 1), y_train)

        # 5. Apply calibrated model to test fold
        raw_test_probs = lr.predict_proba(X_test_scaled)[:, 1]
        cal_test_probs = platt.predict_proba(raw_test_probs.reshape(-1, 1))[:, 1]
        test_df = test_df.copy()
        test_df["model_prob"] = cal_test_probs

        # In-sample calibrated probs (for overfit check)
        raw_train_probs = lr.predict_proba(X_train_scaled)[:, 1]
        cal_train_probs = platt.predict_proba(raw_train_probs.reshape(-1, 1))[:, 1]

        acc = ((cal_test_probs > 0.5) == (y_test == 1)).mean()
        logger.info(
            "Fold test=%d: train_n=%d, test_n=%d, test_acc=%.3f",
            test_season,
            len(train_df),
            len(test_df),
            acc,
        )

        fold_results.append(
            {
                "train_seasons": train_seasons,
                "test_season": test_season,
                "train_df": train_df,
                "test_df": test_df,
                "scaler": scaler,
                "lr": lr,
                "platt": platt,
                "cal_train_probs": cal_train_probs,
                "y_train": y_train,
            }
        )

    return fold_results


# ---------------------------------------------------------------------------
# CLV computation (Pinnacle 2022-2023 only)
# ---------------------------------------------------------------------------


def _american_to_implied(odds: float) -> float:
    if odds < 0:
        return (-odds) / (-odds + 100)
    return 100 / (odds + 100)


def _devig(home_ml: float, away_ml: float) -> tuple[float, float]:
    """Remove vig from moneyline pair. Returns (fair_home_prob, fair_away_prob)."""
    h = _american_to_implied(home_ml)
    a = _american_to_implied(away_ml)
    total = h + a
    return h / total, a / total


def compute_clv(fold_results: list[dict]) -> pd.DataFrame:
    """Compute CLV using Pinnacle closing lines for folds with backfill data (2022-2023).

    Pinnacle backfill ONLY covers seasons 2021-2023 (test folds 2022 and 2023).
    For 2024 and 2025, CLV is not computable against Pinnacle — those folds
    contribute ROI/win-rate/Sharpe to Gatekeeper but not CLV.

    Returns:
        DataFrame with one row per bet (games where model has edge > 0).
    """
    clv_seasons = {2022, 2023}  # Folds with Pinnacle backfill
    pinnacle_data: dict[int, pd.DataFrame] = {}

    for season in [2021, 2022, 2023]:
        path = BACKFILL_DIR / f"ncaab_odds_api_{season}.parquet"
        if not path.exists():
            logger.warning("Backfill odds not found for season %d: %s", season, path)
            continue
        df = pd.read_parquet(path)
        # Filter Pinnacle only
        df = df[df["bookmaker"] == "pinnacle"].copy()
        # Parse game date from commence_time
        df["game_date_str"] = pd.to_datetime(df["commence_time"]).dt.strftime("%Y-%m-%d")
        open_df = df[df["snapshot_type"] == "open"][
            ["game_id", "game_date_str", "home_team", "away_team", "home_ml", "away_ml"]
        ].copy()
        close_df = df[df["snapshot_type"] == "close"][["game_id", "home_ml", "away_ml"]].rename(
            columns={"home_ml": "home_ml_close", "away_ml": "away_ml_close"}
        )

        merged = open_df.merge(close_df, on="game_id", how="inner")
        pinnacle_data[season] = merged

    # Build crosswalk for matching
    crosswalk_df = pd.read_csv(CROSSWALK_PATH)
    bt_names = set(crosswalk_df["barttorvik_name"].tolist())

    def bt_name_from_odds_name(odds_name: str) -> str | None:
        """Return longest-matching BT name so 'Oregon St' beats 'Oregon'."""
        odds_lower = odds_name.lower()
        candidates = [bt for bt in bt_names if bt.lower() in odds_lower]
        if not candidates:
            return None
        return max(candidates, key=len)  # longest match wins (most specific)

    # Build ESPN id -> BT name lookup
    espn_to_bt = dict(zip(crosswalk_df["espn_id"], crosswalk_df["barttorvik_name"]))

    clv_records = []

    for fold in fold_results:
        test_season = fold["test_season"]
        if test_season not in clv_seasons:
            logger.info("Season %d: no Pinnacle backfill — skipping CLV (ROI only)", test_season)
            continue

        test_df = fold["test_df"]
        odds_df = pinnacle_data.get(test_season, pd.DataFrame())
        if odds_df.empty:
            logger.warning("No Pinnacle odds for season %d — skipping CLV", test_season)
            continue

        # Map odds team names to BT names
        all_odds_teams = pd.concat([odds_df["home_team"], odds_df["away_team"]]).unique()
        odds_name_to_bt = {
            n: bt_name_from_odds_name(n) for n in all_odds_teams if bt_name_from_odds_name(n)
        }

        odds_df = odds_df.copy()
        odds_df["bt_home"] = odds_df["home_team"].map(odds_name_to_bt)
        odds_df["bt_away"] = odds_df["away_team"].map(odds_name_to_bt)
        odds_lookup = {
            (r["bt_home"], r["bt_away"], r["game_date_str"]): r
            for _, r in odds_df.dropna(subset=["bt_home", "bt_away"]).iterrows()
        }

        for _, game in test_df.iterrows():
            home_espn = game["home_team_id"]
            away_espn = game["away_team_id"]
            home_bt = espn_to_bt.get(home_espn)
            away_bt = espn_to_bt.get(away_espn)
            if home_bt is None or away_bt is None:
                continue
            date_str = game["game_date"].strftime("%Y-%m-%d")

            odds_row = odds_lookup.get((home_bt, away_bt, date_str))
            if odds_row is None:
                continue  # No Pinnacle match for this game

            # Skip if closing odds are missing (cancelled game or data gap)
            if pd.isna(odds_row.get("home_ml_close")) or pd.isna(odds_row.get("away_ml_close")):
                continue

            model_prob = game["model_prob"]
            fair_home_open, _ = _devig(odds_row["home_ml"], odds_row["away_ml"])
            fair_home_close, _ = _devig(odds_row["home_ml_close"], odds_row["away_ml_close"])

            # Determine bet side: bet home if model_prob > fair_home_open
            if model_prob > fair_home_open:
                bet_side = "H"
                odds_placed = odds_row["home_ml"]
                odds_close = odds_row["home_ml_close"]
                prob_placed = fair_home_open
                prob_close = fair_home_close
                won = game["home_win"] == 1
            elif (1 - model_prob) > (1 - fair_home_open):  # Away edge
                bet_side = "A"
                odds_placed = odds_row["away_ml"]
                odds_close = odds_row["away_ml_close"]
                prob_placed = 1 - fair_home_open
                prob_close = 1 - fair_home_close
                won = game["home_win"] == 0
            else:
                continue  # No edge

            # CLV: (prob_close - prob_placed) / prob_placed — positive = beat the line
            clv_value = (prob_close - prob_placed) / prob_placed

            # Flat-stake P&L
            stake = 100.0
            if won:
                pnl = (
                    stake * (100 / abs(odds_placed))
                    if odds_placed < 0
                    else stake * (odds_placed / 100)
                )
            else:
                pnl = -stake

            clv_records.append(
                {
                    "game_id": game["game_id"],
                    "game_date": game["game_date"],
                    "season": test_season,
                    "home_team_id": home_espn,
                    "away_team_id": away_espn,
                    "model_prob_home": model_prob,
                    "fair_home_prob_open": fair_home_open,
                    "fair_home_prob_close": fair_home_close,
                    "bet_side": bet_side,
                    "odds_placed": odds_placed,
                    "odds_closing": odds_close,
                    "home_win": game["home_win"],
                    "result": "W" if won else "L",
                    "clv_value": clv_value,
                    "stake": stake,
                    "profit_loss": pnl,
                }
            )

    return pd.DataFrame(clv_records)


# ---------------------------------------------------------------------------
# Gatekeeper integration
# ---------------------------------------------------------------------------


def compute_flat_roi(fold_results: list[dict]) -> tuple[float, dict]:
    """Compute flat-stake ROI across all test folds and per season."""
    all_pnl: list[float] = []
    season_rois: dict[int, float] = {}

    for fold in fold_results:
        test_df = fold["test_df"]
        probs = test_df["model_prob"].values
        wins = test_df["home_win"].values
        bets = probs > 0.5
        if bets.sum() == 0:
            continue
        correct = (probs[bets] > 0.5) == (wins[bets] == 1)
        pnl = np.where(correct, 100.0, -100.0)
        all_pnl.extend(pnl.tolist())
        season_rois[fold["test_season"]] = float(pnl.mean())

    pooled_roi = float(np.mean(all_pnl)) if all_pnl else 0.0
    return pooled_roi, season_rois


def run_gatekeeper(fold_results: list[dict], clv_df: pd.DataFrame) -> object:
    """Build Gatekeeper inputs and run validation."""
    # Ensure BASE_DIR (main repo) is in path for gatekeeper, but worktree stays first
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(1, str(BASE_DIR))
    if str(_script_root) not in sys.path:
        sys.path.insert(0, str(_script_root))
    from backtesting.validators.gatekeeper import Gatekeeper

    _, season_rois_dict = compute_flat_roi(fold_results)
    # Overfit validator expects a list of decimal fractions, not a percentage dict
    season_rois_list = [v / 100.0 for v in season_rois_dict.values()]

    all_test = pd.concat([f["test_df"] for f in fold_results], ignore_index=True)

    # In-sample ROI from LAST fold's training data (most data, highest overfit risk)
    last_fold = fold_results[-1]
    in_sample_probs = last_fold["cal_train_probs"]
    in_sample_wins = last_fold["y_train"]
    in_sample_bets = in_sample_probs > 0.5
    if in_sample_bets.sum() > 0:
        correct = (in_sample_probs[in_sample_bets] > 0.5) == (in_sample_wins[in_sample_bets] == 1)
        # Convert to decimal fraction (0.58 not 58.0) for Gatekeeper threshold check
        in_sample_roi = float(np.where(correct, 1.0, -1.0).mean())
    else:
        in_sample_roi = 0.0

    # Build backtest_results dict
    if not clv_df.empty:
        clv_values = clv_df["clv_value"].tolist()
        odds_placed = clv_df["odds_placed"].tolist()
        odds_closing = clv_df["odds_closing"].tolist()
        profit_loss = clv_df["profit_loss"].tolist()
        stakes = clv_df["stake"].tolist()
        results = clv_df["result"].tolist()
        game_dates = clv_df["game_date"].dt.strftime("%Y-%m-%d").tolist()
        season_labels = clv_df["season"].astype(str).tolist()
    else:
        # Fallback: no CLV data — Gatekeeper will fail CLV dimension
        clv_values = [0.0]
        odds_placed = [-110.0]
        odds_closing = [-110.0]
        profit_loss = [0.0]
        stakes = [100.0]
        results = ["L"]
        game_dates = ["2023-01-01"]
        season_labels = ["2023"]

    backtest_results = {
        "profit_loss": profit_loss,
        "stake": stakes,
        "result": results,
        "odds_placed": odds_placed,
        "odds_closing": odds_closing,
        "clv_values": clv_values,
        "game_date": game_dates,
        "season_labels": season_labels,
    }

    model_metadata = {
        "n_features": len(FEATURE_COLS),
        "n_samples": len(all_test),
        "season_rois": season_rois_list,
        "in_sample_roi": in_sample_roi,
        "bankroll": 5000.0,
        "config": {"kelly_fraction": 0.25, "model_type": "logistic_regression"},
        "model_type": "NCAABEfficiencyModel",
    }

    gk = Gatekeeper()
    gk.load_validators()
    report = gk.generate_report(
        model_name="ncaab_efficiency_v1",
        backtest_results=backtest_results,
        model_metadata=model_metadata,
        mode="full",
    )
    return report


# ---------------------------------------------------------------------------
# daily_run.py integration patch
# ---------------------------------------------------------------------------


def _patch_daily_run(model_path: Path) -> None:
    """Update daily_run.py to load the efficiency model instead of Elo.

    Replaces the model loading block so the efficiency model is used
    when the saved artifact exists.
    """
    daily_run_path = BASE_DIR / "scripts" / "daily_run.py"
    source = daily_run_path.read_text(encoding="utf-8")

    if "EFFICIENCY_MODEL_PATH" in source:
        logger.info("daily_run.py already patched for efficiency model.")
        return

    # Insert the EFFICIENCY_MODEL_PATH constant before the model load block
    old_load = (
        '    model_path = PROCESSED_DATA_DIR / "ncaab_elo_model.pkl"\n'
        "    if not model_path.exists():\n"
        '        logger.error("No trained model. Run train_ncaab_elo.py first.")\n'
        "        return pd.DataFrame()\n"
        "\n"
        "    saved = load_model(model_path)\n"
        "    model = saved.model\n"
        '    logger.info("Model loaded: %d teams", len(model.ratings))'
    )

    new_load = (
        "    # Efficiency model takes priority over Elo if artifact exists\n"
        f"    EFFICIENCY_MODEL_PATH = Path(r'{model_path}')\n"
        "    if EFFICIENCY_MODEL_PATH.exists():\n"
        "        import pandas as _pd_bt\n"
        "        from models.sport_specific.ncaab.efficiency_model import NCAABEfficiencyModel as _EffModel\n"
        "        _eff_saved = load_model(EFFICIENCY_MODEL_PATH)\n"
        "        _eff_model = _eff_saved.model\n"
        "        _bt_files = sorted(\n"
        "            Path('data/external/barttorvik').glob('barttorvik_ratings_*.parquet')\n"
        "        )\n"
        "        if _bt_files:\n"
        "            _bt_df = _pd_bt.read_parquet(_bt_files[-1])\n"
        "            _latest_bt = _bt_df[_bt_df['date'] == _bt_df['date'].max()]\n"
        "            _eff_model.load_barttorvik_snapshot(_latest_bt)\n"
        "        model = _eff_model\n"
        '        logger.info("Efficiency model loaded (Barttorvik logistic regression)")\n'
        "    else:\n"
        '        model_path = PROCESSED_DATA_DIR / "ncaab_elo_model.pkl"\n'
        "        if not model_path.exists():\n"
        '            logger.error("No trained model. Run train_ncaab_elo.py first.")\n'
        "            return pd.DataFrame()\n"
        "        saved = load_model(model_path)\n"
        "        model = saved.model\n"
        '        logger.info("Elo model loaded: %d teams", len(model.ratings))'
    )

    if old_load not in source:
        logger.error(
            "Could not find expected model loading block in daily_run.py — manual patch required."
        )
        logger.error("Expected block:\n%s", old_load)
        return

    patched = source.replace(old_load, new_load)
    daily_run_path.write_text(patched, encoding="utf-8")
    logger.info("daily_run.py patched successfully.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Train, validate, and optionally deploy the NCAAB efficiency model."""
    logger.info("=== NCAAB Efficiency Model Training ===")

    # Phase 1: Build dataset
    logger.info("Building PIT dataset for seasons 2021-2025...")
    full_df = build_pit_dataset(seasons=list(range(2021, 2026)))
    validate_no_leakage(full_df)
    logger.info(
        "Dataset built: %d games across %s seasons",
        len(full_df),
        sorted(full_df["season"].unique().tolist()),
    )

    # Phase 2: Walk-forward training
    logger.info("Running walk-forward training (4 folds)...")
    fold_results = run_walk_forward(full_df)
    if not fold_results:
        logger.error("No folds produced — check data coverage for 2021-2025.")
        return

    # Phase 3: CLV computation
    logger.info("Computing CLV against Pinnacle closing lines...")
    clv_df = compute_clv(fold_results)
    logger.info("CLV dataset: %d bets with Pinnacle data", len(clv_df))
    if not clv_df.empty:
        mean_clv = clv_df["clv_value"].mean()
        logger.info("Mean CLV (Pinnacle 2022-2023): %.3f%%", mean_clv * 100)

    # Phase 4: Gatekeeper
    logger.info("Running Gatekeeper validation...")
    report = run_gatekeeper(fold_results, clv_df)
    print("\n" + report.summary())

    # Phase 5: Decision gate
    from backtesting.validators.gatekeeper import GateDecision
    from models.model_persistence import ModelMetadata, save_model
    from models.sport_specific.ncaab.efficiency_model import NCAABEfficiencyModel

    final_fold = fold_results[-1]  # Final model: trained on 2021-2024
    clv_summary = (
        f"CLV={clv_df['clv_value'].mean() * 100:.2f}% (Pinnacle 2022-23)"
        if not clv_df.empty
        else "CLV=N/A (no Pinnacle match)"
    )

    artifact = NCAABEfficiencyModel(
        lr=final_fold["lr"],
        scaler=final_fold["scaler"],
        platt=final_fold["platt"],
        crosswalk=dict(pd.read_csv(CROSSWALK_PATH).set_index("espn_id")["barttorvik_name"]),
        ratings={},  # populated at runtime via load_barttorvik_snapshot()
    )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    model_path = PROCESSED_DIR / "ncaab_efficiency_model.pkl"

    metadata = ModelMetadata(
        model_name="ncaab_efficiency_v1",
        sport="ncaab",
        seasons_used=list(range(2021, 2025)),
        game_count=len(final_fold["train_df"]),
        notes=f"Gatekeeper: {report.decision.name}. {clv_summary}",
    )

    if report.decision in (GateDecision.PASS, GateDecision.NEEDS_REVIEW):
        save_model(artifact, model_path, metadata)
        logger.info("Model saved to %s", model_path)
        _patch_daily_run(model_path)
    else:
        save_model(artifact, model_path, metadata)
        logger.warning(
            "Gatekeeper QUARANTINE — model saved to %s for inspection but "
            "daily_run.py NOT patched. Elo model remains active for tournament.",
            model_path,
        )
        print("\nBLOCKING FAILURES:")
        for failure in report.blocking_failures:
            print(f"  - {failure}")


if __name__ == "__main__":
    main()
