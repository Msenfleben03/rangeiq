"""Train NCAAB Elo Model on Historical Data.

Loads raw parquet data for seasons 2020-2025, processes games chronologically,
applies season regression between years, and outputs a trained model.

Outputs:
    - data/processed/ncaab_elo_ratings_current.csv  (human-readable)
    - data/processed/ncaab_elo_model.pkl            (pickled model state)
    - team_ratings table entries via database

Usage:
    python scripts/train_ncaab_elo.py
    python scripts/train_ncaab_elo.py --start 2020 --end 2025
    python scripts/train_ncaab_elo.py --validate  # Print top 25 + sanity checks
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from config.constants import ELO
from config.settings import (
    DATABASE_PATH,
    NCAAB_SEASONS_END,
    NCAAB_SEASONS_START,
    PROCESSED_DATA_DIR,
    RAW_DATA_DIR,
)
from models.model_persistence import (
    ModelMetadata,
    export_ratings_csv,
    export_ratings_db,
    save_model,
)
from models.sport_specific.ncaab.team_ratings import NCAABEloModel
from tracking.database import BettingDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_season_data(season: int) -> pd.DataFrame:
    """Load raw parquet data for a single season.

    Args:
        season: Season year (e.g., 2024 for 2023-24).

    Returns:
        DataFrame with game data, sorted by date.

    Raises:
        FileNotFoundError: If parquet file does not exist.
    """
    path = RAW_DATA_DIR / "ncaab" / f"ncaab_games_{season}.parquet"
    if not path.exists():
        raise FileNotFoundError(
            f"No data for season {season}. Run scripts/fetch_historical_data.py first."
        )

    df = pd.read_parquet(path)
    logger.info("Loaded season %d: %d games", season, len(df))
    return df


def prepare_games_for_elo(df: pd.DataFrame) -> list[dict]:
    """Convert raw game DataFrame to list of dicts for Elo processing.

    The raw data from sportsipy uses team_id/opponent_id perspective.
    We need to deduplicate and create home/away format.

    Args:
        df: Raw game data from sportsipy.

    Returns:
        List of game dicts with home/away/scores, sorted by date.
    """
    games = []
    seen_game_ids: set[str] = set()

    for _, row in df.iterrows():
        game_id = row.get("game_id", "")
        if not game_id or game_id in seen_game_ids:
            continue
        seen_game_ids.add(game_id)

        # Determine home/away from location field
        location = str(row.get("location", "")).strip().lower()
        team_id = str(row.get("team_id", ""))
        opponent_id = str(row.get("opponent_id", ""))
        points_for = row.get("points_for")
        points_against = row.get("points_against")

        # Skip games with missing scores
        if pd.isna(points_for) or pd.isna(points_against):
            continue

        points_for = int(points_for)
        points_against = int(points_against)

        # Parse date
        game_date = row.get("date")
        if isinstance(game_date, str):
            try:
                game_date = pd.to_datetime(game_date)
            except (ValueError, TypeError):
                continue

        if location == "home":
            games.append(
                {
                    "game_id": game_id,
                    "date": game_date,
                    "home": team_id,
                    "away": opponent_id,
                    "home_score": points_for,
                    "away_score": points_against,
                    "neutral_site": False,
                }
            )
        elif location == "away":
            games.append(
                {
                    "game_id": game_id,
                    "date": game_date,
                    "home": opponent_id,
                    "away": team_id,
                    "home_score": points_against,
                    "away_score": points_for,
                    "neutral_site": False,
                }
            )
        else:
            # Neutral site — treat first team as "home" for data purposes
            games.append(
                {
                    "game_id": game_id,
                    "date": game_date,
                    "home": team_id,
                    "away": opponent_id,
                    "home_score": points_for,
                    "away_score": points_against,
                    "neutral_site": True,
                }
            )

    # Sort chronologically
    games.sort(key=lambda g: g["date"])
    logger.info("Prepared %d unique games for Elo processing", len(games))
    return games


def extract_conferences(df: pd.DataFrame) -> dict[str, str]:
    """Extract team-to-conference mapping from teams data.

    Args:
        df: Raw data that may contain conference column.

    Returns:
        Mapping of team_id -> conference name.
    """
    conferences: dict[str, str] = {}
    if "conference" in df.columns:
        for _, row in df.iterrows():
            team_id = str(row.get("team_id", ""))
            conf = row.get("conference")
            if team_id and conf and not pd.isna(conf):
                conferences[team_id] = str(conf)
    return conferences


def train_model(
    start_season: int,
    end_season: int,
) -> tuple[NCAABEloModel, dict]:
    """Train NCAAB Elo model on historical data.

    Processes seasons chronologically, applying regression between years.

    Args:
        start_season: First season year.
        end_season: Last season year (inclusive).

    Returns:
        Tuple of (trained model, training stats dict).
    """
    model = NCAABEloModel(
        k_factor=ELO.K_FACTOR_NCAAB,
        initial_rating=ELO.INITIAL_RATING,
        home_advantage=ELO.HOME_ADVANTAGE_NCAAB,
        mov_cap=ELO.MOV_CAP_NCAAB,
        regression_factor=ELO.REGRESSION_FACTOR_NCAAB,
    )

    stats = {
        "seasons_processed": [],
        "total_games": 0,
        "games_per_season": {},
    }

    seasons = list(range(start_season, end_season + 1))

    for i, season in enumerate(seasons):
        # Apply regression between seasons (not before first)
        if i > 0:
            pre_regression_count = len(model.ratings)
            model.apply_season_regression()
            logger.info(
                "Applied season regression (%d teams, factor=%.2f)",
                pre_regression_count,
                model.regression_factor,
            )

        # Load and prepare season data
        try:
            df = load_season_data(season)
        except FileNotFoundError as e:
            logger.error("Skipping season %d: %s", season, e)
            continue

        # Extract conferences from data
        conferences = extract_conferences(df)
        for team_id, conf in conferences.items():
            model.set_conference(team_id, conf)

        # Prepare games and process
        games = prepare_games_for_elo(df)

        for game in games:
            model.update_game(
                home_team=game["home"],
                away_team=game["away"],
                home_score=game["home_score"],
                away_score=game["away_score"],
                neutral_site=game["neutral_site"],
            )

        stats["seasons_processed"].append(season)
        stats["games_per_season"][season] = len(games)
        stats["total_games"] += len(games)

        logger.info(
            "Season %d: processed %d games (%d teams rated)",
            season,
            len(games),
            len(model.ratings),
        )

    return model, stats


def validate_model(model: NCAABEloModel) -> bool:
    """Run sanity checks on the trained model.

    Args:
        model: Trained NCAABEloModel.

    Returns:
        True if all checks pass.
    """
    passed = True

    # Check team count
    n_teams = len(model.ratings)
    if n_teams < 300:
        logger.warning("Only %d teams rated (expected ~350 D-I)", n_teams)
        passed = False
    else:
        logger.info("Team count: %d (OK)", n_teams)

    # Check rating bounds
    ratings = list(model.ratings.values())
    min_r, max_r = min(ratings), max(ratings)
    if min_r < ELO.MIN_RATING or max_r > ELO.MAX_RATING:
        logger.error(
            "Ratings out of bounds: [%.1f, %.1f] (expected [%.1f, %.1f])",
            min_r,
            max_r,
            ELO.MIN_RATING,
            ELO.MAX_RATING,
        )
        passed = False
    else:
        logger.info("Rating range: [%.1f, %.1f] (OK)", min_r, max_r)

    # Check mean is reasonable
    mean_r = sum(ratings) / len(ratings)
    if abs(mean_r - ELO.MEAN_RATING) > 50:
        logger.warning("Mean rating %.1f deviates from expected %.1f", mean_r, ELO.MEAN_RATING)
    else:
        logger.info("Mean rating: %.1f (OK)", mean_r)

    # Print top 25
    df = model.to_dataframe()
    print(f"\n{'=' * 60}")
    print("TOP 25 TEAMS BY ELO RATING")
    print(f"{'=' * 60}")
    for i, row in df.head(25).iterrows():
        print(
            f"  {i + 1:>2}. {row['team_id']:<20s} {row['elo_rating']:>7.1f}  "
            f"({row['conference']}, {row['games_played']} games)"
        )

    return passed


def main() -> None:
    """Entry point for model training."""
    parser = argparse.ArgumentParser(description="Train NCAAB Elo model")
    parser.add_argument(
        "--start",
        type=int,
        default=NCAAB_SEASONS_START,
        help=f"First season (default: {NCAAB_SEASONS_START})",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=NCAAB_SEASONS_END,
        help=f"Last season (default: {NCAAB_SEASONS_END})",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        default=True,
        help="Run sanity checks after training (default: True)",
    )
    parser.add_argument(
        "--no-db",
        action="store_true",
        help="Skip database export",
    )
    args = parser.parse_args()

    # Train
    model, stats = train_model(args.start, args.end)

    if not stats["seasons_processed"]:
        logger.error("No seasons processed. Run fetch_historical_data.py first.")
        sys.exit(1)

    # Validate
    if args.validate:
        valid = validate_model(model)
        if not valid:
            logger.warning("Model validation had warnings — review output above")

    # Save outputs
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Save pickled model
    metadata = ModelMetadata(
        model_name="ncaab_elo_v1",
        sport="ncaab",
        seasons_used=stats["seasons_processed"],
        game_count=stats["total_games"],
        team_count=len(model.ratings),
        config_snapshot={
            "k_factor": model.k_factor,
            "home_advantage": model.home_advantage,
            "mov_cap": model.mov_cap,
            "regression_factor": model.regression_factor,
            "tournament_k_factor": model.tournament_k_factor,
        },
    )
    pkl_path = PROCESSED_DATA_DIR / "ncaab_elo_model.pkl"
    save_model(model, pkl_path, metadata)

    # 2. Export CSV
    csv_path = PROCESSED_DATA_DIR / "ncaab_elo_ratings_current.csv"
    export_ratings_csv(model, csv_path, sport="ncaab")

    # 3. Export to database
    if not args.no_db:
        db = BettingDatabase(str(DATABASE_PATH))
        last_season = stats["seasons_processed"][-1]
        export_ratings_db(model, db, sport="ncaab", season=last_season)

    # Summary
    print(f"\n{'=' * 60}")
    print("TRAINING SUMMARY")
    print(f"{'=' * 60}")
    print(f"Seasons: {stats['seasons_processed']}")
    print(f"Total games: {stats['total_games']:,}")
    print(f"Teams rated: {len(model.ratings)}")
    print(f"Model saved: {pkl_path}")
    print(f"Ratings CSV: {csv_path}")
    for season, count in stats["games_per_season"].items():
        print(f"  {season}: {count:,} games")


if __name__ == "__main__":
    main()
