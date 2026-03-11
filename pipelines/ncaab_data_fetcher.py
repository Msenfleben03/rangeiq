"""NCAAB Data Fetcher.

Fetches NCAA Men's Basketball game data, team statistics,
and schedules for model training and prediction.

NOTE: sportsipy is broken as of 2025. fetch_games_by_date() now uses the
ESPN Site API scoreboard directly. Other methods (fetch_teams, fetch_team_schedule,
fetch_season_data) still depend on sportsipy and will fail — migrate as needed.
"""

import pandas as pd
import requests
from datetime import datetime
from typing import Dict, List, Optional
import logging
from pathlib import Path
import time

# sportsipy is broken since 2025 — import silently so fetch_games_by_date
# (ESPN-based) still works even when sportsipy is unavailable.
try:
    from sportsipy.ncaab.teams import Teams
    from sportsipy.ncaab.schedule import Schedule

    _SPORTSIPY_AVAILABLE = True
except Exception:
    Teams = None  # type: ignore[assignment,misc]
    Schedule = None  # type: ignore[assignment,misc]
    _SPORTSIPY_AVAILABLE = False

ESPN_SITE_BASE = "https://site.api.espn.com/apis/site/v2/sports"
_NCAAB_SCOREBOARD = f"{ESPN_SITE_BASE}/basketball/mens-college-basketball/scoreboard"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_score(competitor: dict) -> Optional[int]:
    """Extract integer score from ESPN competitor dict."""
    score = competitor.get("score", {})
    if isinstance(score, dict):
        val = score.get("value") or score.get("displayValue")
    else:
        val = score
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


class NCAABDataFetcher:
    """Fetches NCAA Basketball data using sportsipy.

    Provides methods to download team data, schedules, and
    game results for specified seasons.
    """

    def __init__(self, output_dir: str = "data/raw/ncaab"):
        """Initialize NCAAB data fetcher.

        Args:
            output_dir: Directory to save raw data files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch_teams(self, season: int) -> pd.DataFrame:
        """Fetch all teams for a season.

        Args:
            season: Year of season (e.g., 2024 for 2023-24 season)

        Returns:
            DataFrame with team information
        """
        logger.info(f"Fetching teams for {season} season...")

        try:
            teams = Teams(year=season)
            team_data = []

            for team in teams:
                team_info = {
                    "season": season,
                    "team_id": team.abbreviation,
                    "team_name": team.name,
                    "conference": team.conference,
                    "wins": team.wins,
                    "losses": team.losses,
                    "win_percentage": team.win_percentage,
                    "simple_rating_system": team.simple_rating_system,
                    "strength_of_schedule": team.strength_of_schedule,
                    "offensive_rating": team.offensive_rating,
                    "defensive_rating": team.defensive_rating,
                    "pace": team.pace,
                    "field_goal_percentage": team.field_goal_percentage,
                    "three_point_percentage": team.three_point_percentage,
                    "free_throw_percentage": team.free_throw_percentage,
                    "total_rebounds": team.total_rebounds,
                    "assists": team.assists,
                    "turnovers": team.turnovers,
                }
                team_data.append(team_info)

            df = pd.DataFrame(team_data)
            logger.info(f"Fetched {len(df)} teams")
            return df

        except Exception as e:
            logger.error(f"Error fetching teams: {e}")
            raise

    def fetch_team_schedule(self, team_id: str, season: int) -> pd.DataFrame:
        """Fetch schedule and results for a specific team.

        Args:
            team_id: Team abbreviation (e.g., 'DUKE')
            season: Year of season

        Returns:
            DataFrame with game results
        """
        logger.info(f"Fetching schedule for {team_id} ({season})...")

        try:
            schedule = Schedule(team_id, year=season)
            games = []

            for game in schedule:
                game_info = {
                    "season": season,
                    "date": game.date,
                    "game_id": game.boxscore_index,
                    "team_id": team_id,
                    "opponent_id": game.opponent_abbr,
                    "opponent_name": game.opponent_name,
                    "location": game.location,
                    "result": game.result,
                    "points_for": game.points_scored,
                    "points_against": game.points_allowed,
                    "field_goals": game.field_goals,
                    "field_goal_attempts": game.field_goal_attempts,
                    "three_pointers": game.three_point_field_goals,
                    "three_point_attempts": game.three_point_field_goal_attempts,
                    "free_throws": game.free_throws,
                    "free_throw_attempts": game.free_throw_attempts,
                    "offensive_rebounds": game.offensive_rebounds,
                    "total_rebounds": game.total_rebounds,
                    "assists": game.assists,
                    "steals": game.steals,
                    "blocks": game.blocks,
                    "turnovers": game.turnovers,
                    "personal_fouls": game.personal_fouls,
                }
                games.append(game_info)

            df = pd.DataFrame(games)
            logger.info(f"Fetched {len(df)} games for {team_id}")
            return df

        except Exception as e:
            logger.error(f"Error fetching schedule for {team_id}: {e}")
            return pd.DataFrame()

    def fetch_games_by_date(self, date: datetime) -> List[Dict]:
        """Fetch all completed games on a specific date via ESPN scoreboard API.

        Args:
            date: Date to fetch games for.

        Returns:
            List of game dicts with keys: date, home_team, home_abbr, home_score,
            away_team, away_abbr, away_score, game_id.
        """
        date_str = date.strftime("%Y%m%d")
        logger.info("Fetching ESPN scoreboard for %s...", date.strftime("%Y-%m-%d"))

        try:
            resp = requests.get(
                _NCAAB_SCOREBOARD,
                params={"dates": date_str, "limit": 500, "groups": "50"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error("Error fetching ESPN scoreboard for %s: %s", date.strftime("%Y-%m-%d"), e)
            return []

        game_list: List[Dict] = []
        for event in data.get("events", []):
            game_id = str(event.get("id", ""))
            competitions = event.get("competitions", [])
            if not competitions:
                continue
            comp = competitions[0]

            # Only include completed games
            status_type = event.get("status", {}).get("type", {})
            if status_type.get("name", "") != "STATUS_FINAL":
                continue

            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue

            home: Optional[Dict] = None
            away: Optional[Dict] = None
            for c in competitors:
                if c.get("homeAway") == "home":
                    home = c
                else:
                    away = c

            if home is None or away is None:
                continue

            home_score = _parse_score(home)
            away_score = _parse_score(away)
            if home_score is None or away_score is None:
                continue

            game_list.append(
                {
                    "date": date,
                    "game_id": game_id,
                    "home_team": home.get("team", {}).get("displayName", ""),
                    "home_abbr": home.get("team", {}).get("abbreviation", ""),
                    "home_score": home_score,
                    "away_team": away.get("team", {}).get("displayName", ""),
                    "away_abbr": away.get("team", {}).get("abbreviation", ""),
                    "away_score": away_score,
                }
            )

        logger.info("Fetched %d completed games for %s", len(game_list), date.strftime("%Y-%m-%d"))
        return game_list

    def fetch_season_data(self, season: int, delay: float = 1.0) -> pd.DataFrame:
        """Fetch complete season data for all teams.

        Args:
            season: Year of season
            delay: Delay between requests (seconds) to avoid rate limiting

        Returns:
            DataFrame with all games
        """
        logger.info(f"Fetching complete season data for {season}...")

        # Get all teams
        teams_df = self.fetch_teams(season)

        all_games = []
        for idx, row in teams_df.iterrows():
            team_id = row["team_id"]

            # Fetch team schedule
            schedule_df = self.fetch_team_schedule(team_id, season)

            if not schedule_df.empty:
                all_games.append(schedule_df)

            # Rate limiting delay
            if delay > 0:
                time.sleep(delay)

            logger.info(f"Progress: {idx + 1}/{len(teams_df)} teams processed")

        # Combine all games
        if all_games:
            games_df = pd.concat(all_games, ignore_index=True)

            # Remove duplicates (each game appears twice, once for each team)
            games_df = games_df.drop_duplicates(subset=["game_id"], keep="first")

            # Save to disk
            output_file = self.output_dir / f"ncaab_games_{season}.parquet"
            games_df.to_parquet(output_file, index=False)
            logger.info(f"Saved {len(games_df)} games to {output_file}")

            return games_df

        return pd.DataFrame()

    def fetch_multiple_seasons(self, start_season: int, end_season: int) -> pd.DataFrame:
        """Fetch data for multiple seasons.

        Args:
            start_season: First season year
            end_season: Last season year (inclusive)

        Returns:
            DataFrame with all seasons combined
        """
        all_seasons = []

        for season in range(start_season, end_season + 1):
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Processing {season} season")
            logger.info(f"{'=' * 60}")

            season_df = self.fetch_season_data(season)

            if not season_df.empty:
                all_seasons.append(season_df)

        if all_seasons:
            combined_df = pd.concat(all_seasons, ignore_index=True)

            # Save combined data
            output_file = self.output_dir / f"ncaab_games_{start_season}_{end_season}.parquet"
            combined_df.to_parquet(output_file, index=False)
            logger.info(f"\nSaved combined dataset to {output_file}")

            return combined_df

        return pd.DataFrame()


if __name__ == "__main__":
    # Example usage: Fetch recent season data
    fetcher = NCAABDataFetcher()

    # Fetch 2024 season (2023-24)
    season_data = fetcher.fetch_season_data(2024, delay=1.0)

    print(f"\nFetched {len(season_data)} games")
    print("\nSample data:")
    print(season_data.head())

    # Show data summary
    print(f"\nData shape: {season_data.shape}")
    print(f"\nColumns: {list(season_data.columns)}")
