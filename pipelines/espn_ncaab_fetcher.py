"""NCAAB Data Fetcher using ESPN Hidden API.

Drop-in replacement for NCAABDataFetcher (sportsipy-based) that uses
ESPN's undocumented JSON API instead of HTML scraping.

ESPN API advantages over sportsipy:
    - Structured JSON (no HTML parsing, no DOM breakage)
    - 362 teams in a single request
    - Complete game schedules with scores
    - No documented rate limits (still use polite delays)

Produces identical parquet schema to sportsipy fetcher so
train_ncaab_elo.py works unchanged.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# ESPN API base URL
ESPN_BASE = "http://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball"

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0


def _retry_request(
    url: str,
    params: Optional[dict] = None,
    timeout: float = 20.0,
) -> dict:
    """Make HTTP GET with exponential backoff retry.

    Args:
        url: Request URL.
        params: Query parameters.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response.

    Raises:
        requests.RequestException: After all retries exhausted.
    """
    last_exc: Optional[Exception] = None

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BASE_DELAY * (2**attempt)
                logger.warning(
                    "Request failed (attempt %d/%d): %s — retrying in %.1fs",
                    attempt + 1,
                    MAX_RETRIES,
                    exc,
                    wait,
                )
                time.sleep(wait)

    raise requests.RequestException(f"All {MAX_RETRIES} attempts failed for {url}") from last_exc


class ESPNDataFetcher:
    """Fetches NCAA Basketball data using ESPN Hidden API.

    Drop-in replacement for NCAABDataFetcher. Produces identical
    parquet schema so downstream training pipeline works unchanged.

    Args:
        output_dir: Directory to save raw parquet files.
        delay: Seconds between requests (polite crawling).
    """

    def __init__(
        self,
        output_dir: str = "data/raw/ncaab",
        delay: float = 0.3,
    ) -> None:
        """Initialize ESPN data fetcher with output directory and request delay."""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay

    # ------------------------------------------------------------------
    # Public API (matches NCAABDataFetcher interface)
    # ------------------------------------------------------------------

    def fetch_teams(self, season: int) -> pd.DataFrame:
        """Fetch all D-I teams for a season.

        Args:
            season: Year of season (e.g., 2024 for 2023-24).

        Returns:
            DataFrame with team_id, team_name, conference columns.
        """
        logger.info("Fetching teams for %d via ESPN API...", season)

        data = _retry_request(
            f"{ESPN_BASE}/teams",
            params={"limit": 500, "season": season},
        )

        teams_raw = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])

        team_rows = []
        for entry in teams_raw:
            team = entry.get("team", {})
            team_rows.append(
                {
                    "season": season,
                    "team_id": team.get("abbreviation", ""),
                    "team_name": team.get("displayName", ""),
                    "espn_id": team.get("id", ""),
                    "conference": _extract_conference(team),
                }
            )

        df = pd.DataFrame(team_rows)
        logger.info("Fetched %d teams via ESPN", len(df))
        return df

    def fetch_team_schedule(
        self,
        team_id: str,
        season: int,
        espn_id: str = "",
    ) -> pd.DataFrame:
        """Fetch schedule and results for a specific team.

        Args:
            team_id: Team abbreviation (e.g., 'DUKE').
            season: Year of season.
            espn_id: ESPN numeric team ID (faster lookup).

        Returns:
            DataFrame with game results matching sportsipy schema.
        """
        # ESPN schedule endpoint needs the numeric team ID
        if not espn_id:
            espn_id = self._resolve_espn_id(team_id, season)
            if not espn_id:
                logger.warning("Could not resolve ESPN ID for %s", team_id)
                return pd.DataFrame()

        data = _retry_request(
            f"{ESPN_BASE}/teams/{espn_id}/schedule",
            params={"season": season},
        )

        events = data.get("events", [])
        games = []

        for event in events:
            game = self._parse_event(event, team_id, season)
            if game is not None:
                games.append(game)

        df = pd.DataFrame(games)
        if not df.empty:
            logger.info("Fetched %d games for %s (%d)", len(df), team_id, season)
        return df

    def fetch_season_data(
        self,
        season: int,
        delay: Optional[float] = None,
    ) -> pd.DataFrame:
        """Fetch complete season data for all teams.

        Args:
            season: Year of season.
            delay: Override default delay between requests.

        Returns:
            DataFrame with all games, deduplicated.
        """
        request_delay = delay if delay is not None else self.delay
        logger.info("Fetching complete season %d via ESPN API...", season)

        teams_df = self.fetch_teams(season)
        if teams_df.empty:
            logger.error("No teams found for season %d", season)
            return pd.DataFrame()

        all_games: list[pd.DataFrame] = []
        n_teams = len(teams_df)

        for idx, row in teams_df.iterrows():
            team_id = row["team_id"]
            espn_id = str(row.get("espn_id", ""))

            schedule_df = self.fetch_team_schedule(team_id, season, espn_id=espn_id)
            if not schedule_df.empty:
                all_games.append(schedule_df)

            if request_delay > 0:
                time.sleep(request_delay)

            if (idx + 1) % 50 == 0 or idx + 1 == n_teams:
                logger.info("Progress: %d/%d teams processed", idx + 1, n_teams)

        if not all_games:
            logger.error("No game data collected for season %d", season)
            return pd.DataFrame()

        games_df = pd.concat(all_games, ignore_index=True)

        # Deduplicate: each game appears twice (once per team)
        before = len(games_df)
        games_df = games_df.drop_duplicates(subset=["game_id"], keep="first")
        logger.info(
            "Deduplicated: %d -> %d games (removed %d duplicates)",
            before,
            len(games_df),
            before - len(games_df),
        )

        # Save to parquet
        output_file = self.output_dir / f"ncaab_games_{season}.parquet"
        games_df.to_parquet(output_file, index=False)
        logger.info("Saved %d games to %s", len(games_df), output_file)

        return games_df

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_espn_id(self, team_abbr: str, season: int) -> str:
        """Look up ESPN numeric ID from abbreviation.

        Args:
            team_abbr: Team abbreviation.
            season: Season year.

        Returns:
            ESPN numeric ID as string, or empty string if not found.
        """
        teams_df = self.fetch_teams(season)
        match = teams_df[teams_df["team_id"] == team_abbr]
        if not match.empty:
            return str(match.iloc[0]["espn_id"])
        return ""

    def _parse_event(
        self,
        event: dict,
        team_id: str,
        season: int,
    ) -> Optional[dict]:
        """Parse a single ESPN event into sportsipy-compatible dict.

        Args:
            event: ESPN event JSON.
            team_id: The team whose perspective we're using.
            season: Season year.

        Returns:
            Game dict matching sportsipy schema, or None if incomplete.
        """
        competitions = event.get("competitions", [])
        if not competitions:
            return None

        comp = competitions[0]
        competitors = comp.get("competitors", [])
        if len(competitors) < 2:
            return None

        # Skip incomplete games (schedule endpoint mostly returns completed)
        status_obj = event.get("status") or {}
        status_type = status_obj.get("type", {}) if isinstance(status_obj, dict) else {}
        status_name = status_type.get("name", "")
        # If status is present, require final; if absent, check scores exist
        if status_name and status_name != "STATUS_FINAL":
            return None

        # Identify our team and opponent
        our_team = None
        opp_team = None
        for c in competitors:
            abbr = c.get("team", {}).get("abbreviation", "")
            if abbr == team_id:
                our_team = c
            else:
                opp_team = c

        if our_team is None or opp_team is None:
            return None

        # Extract scores — ESPN returns score as dict or string
        points_for = _extract_score(our_team)
        points_against = _extract_score(opp_team)
        if points_for is None or points_against is None:
            return None

        # Determine location
        home_away = our_team.get("homeAway", "home")
        neutral = comp.get("neutralSite", False)
        if neutral:
            location = "Neutral"
        elif home_away == "home":
            location = "Home"
        else:
            location = "Away"

        # Result
        winner = our_team.get("winner", False)
        result = "W" if winner else "L"

        # Game ID — use ESPN event ID (stable, unique)
        game_id = str(event.get("id", ""))

        # Date
        date_str = event.get("date", "")
        try:
            game_date = pd.to_datetime(date_str).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            game_date = date_str[:10] if len(date_str) >= 10 else ""

        opponent_id = opp_team.get("team", {}).get("abbreviation", "")
        opponent_name = opp_team.get("team", {}).get("displayName", "")

        return {
            "season": season,
            "date": game_date,
            "game_id": game_id,
            "team_id": team_id,
            "opponent_id": opponent_id,
            "opponent_name": opponent_name,
            "location": location,
            "result": result,
            "points_for": points_for,
            "points_against": points_against,
            "conference": _extract_conference_from_competitor(our_team),
        }


def _extract_score(competitor: dict) -> Optional[int]:
    """Extract integer score from ESPN competitor entry.

    ESPN returns score in varying formats:
        - dict: {'value': 71.0, 'displayValue': '71'}
        - str: '71'
        - int: 71

    Args:
        competitor: ESPN competitor JSON.

    Returns:
        Score as int, or None if unavailable.
    """
    raw = competitor.get("score")
    if raw is None:
        return None
    if isinstance(raw, dict):
        # Prefer displayValue (string), fall back to value (float)
        try:
            return int(raw.get("displayValue", raw.get("value", 0)))
        except (ValueError, TypeError):
            return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _extract_conference(team: dict) -> str:
    """Extract conference name from ESPN team object.

    Args:
        team: ESPN team JSON.

    Returns:
        Conference name or empty string.
    """
    groups = team.get("groups", {})
    if isinstance(groups, dict):
        return groups.get("name", "")
    return ""


def _extract_conference_from_competitor(competitor: dict) -> str:
    """Extract conference from competitor entry in event data.

    Args:
        competitor: ESPN competitor JSON from event.

    Returns:
        Conference name or empty string.
    """
    team = competitor.get("team", {})
    # Conference info may be in team.groups or team.conferenceId
    conf_id = team.get("conferenceId", "")
    return str(conf_id) if conf_id else ""
