"""MLB Stats API client for schedules, lineups, rosters, and probable pitchers.

Primary data source for daily pipeline operations. Free, unauthenticated,
rate-limit-friendly.

Base URL: https://statsapi.mlb.com/api/v1/
Library: pip install MLB-StatsAPI

Key endpoints:
    - /schedule: daily games with probable pitchers
    - /game/{game_pk}/feed/live: play-by-play, lineups, scoring
    - /teams: roster, standings
    - /people/{player_id}: player details, stats

game_pk is the universal game identifier used across all MLB tables.

References:
    - API docs: docs/mlb/DATA_SOURCES.md
    - Pipeline design: docs/mlb/PIPELINE_DESIGN.md
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import statsapi  # type: ignore[import-untyped]

    _HAS_STATSAPI = True
except ImportError:
    _HAS_STATSAPI = False
    logger.warning("MLB-StatsAPI not installed. Run: pip install MLB-StatsAPI")


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------


@dataclass
class MLBGame:
    """Minimal game record from the schedule endpoint."""

    game_pk: int
    game_date: date
    status: str  # "Final", "Scheduled", "Postponed", etc.
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_starter_id: Optional[int] = None
    home_starter_name: Optional[str] = None
    away_starter_id: Optional[int] = None
    away_starter_name: Optional[str] = None
    venue: Optional[str] = None
    game_time_utc: Optional[datetime] = None


@dataclass
class MLBLineup:
    """Confirmed batting order for one team in one game."""

    game_pk: int
    team_id: int
    confirmed: bool
    batters: list[dict[str, Any]] = field(default_factory=list)
    # Each batter dict: {player_id, full_name, batting_order, position}


@dataclass
class MLBGameResult:
    """Final score and box score summary."""

    game_pk: int
    home_score: int
    away_score: int
    home_team_id: int
    away_team_id: int
    innings: int
    status: str  # "Final" / "Final: Suspended" / etc.
    home_starter_id: Optional[int] = None
    away_starter_id: Optional[int] = None
    home_starter_ip: Optional[float] = None
    away_starter_ip: Optional[float] = None


@dataclass
class MLBPlayer:
    """Player summary record."""

    player_id: int
    full_name: str
    position: Optional[str] = None
    bats: Optional[str] = None
    throws: Optional[str] = None
    current_team_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class MLBStatsAPIClient:
    """Thin wrapper around MLB-StatsAPI for structured data retrieval.

    All public methods return typed data containers. The library handles
    HTTP, retries, and JSON parsing. This class adds structure, error
    handling, and rate limiting.

    Args:
        request_delay: Seconds to sleep between API calls (default 0.5).
    """

    _SPORT_ID = 1  # MLB

    def __init__(self, request_delay: float = 0.5) -> None:
        """Initialize client and verify MLB-StatsAPI is installed.

        Args:
            request_delay: Seconds to sleep between API calls (default 0.5).
        """
        if not _HAS_STATSAPI:
            raise ImportError("MLB-StatsAPI is required. Install with: pip install MLB-StatsAPI")
        self._delay = request_delay

    def _sleep(self) -> None:
        """Rate-limit between requests."""
        time.sleep(self._delay)

    # ------------------------------------------------------------------
    # Schedule / Games
    # ------------------------------------------------------------------

    def fetch_schedule(self, game_date: date) -> list[MLBGame]:
        """Fetch all MLB games for a given date.

        Args:
            game_date: The date to fetch.

        Returns:
            List of MLBGame records (may be empty if no games).
        """
        date_str = game_date.strftime("%Y-%m-%d")
        logger.debug("Fetching schedule for %s", date_str)
        try:
            data = statsapi.schedule(date=date_str, sportId=self._SPORT_ID)
        except Exception as exc:
            logger.error("schedule() failed for %s: %s", date_str, exc)
            return []
        finally:
            self._sleep()

        games = []
        for g in data:
            try:
                games.append(self._parse_schedule_game(g))
            except Exception as exc:
                logger.warning("Failed to parse game %s: %s", g.get("game_id"), exc)
        logger.info("Fetched %d games for %s", len(games), date_str)
        return games

    def fetch_probable_pitchers(self, game_date: date) -> dict[int, dict[str, Any]]:
        """Fetch probable starters for each game on a given date.

        Args:
            game_date: The date to check.

        Returns:
            Dict keyed by game_pk → {home: {id, name}, away: {id, name}}.
        """
        games = self.fetch_schedule(game_date)
        result: dict[int, dict[str, Any]] = {}
        for game in games:
            result[game.game_pk] = {
                "home": {"id": game.home_starter_id, "name": game.home_starter_name},
                "away": {"id": game.away_starter_id, "name": game.away_starter_name},
            }
        return result

    # ------------------------------------------------------------------
    # Game details
    # ------------------------------------------------------------------

    def fetch_confirmed_lineups(self, game_pk: int) -> list[MLBLineup]:
        """Fetch confirmed batting orders for both teams.

        Args:
            game_pk: MLB game identifier.

        Returns:
            List of 0, 1, or 2 MLBLineup records (one per team when available).
        """
        logger.debug("Fetching lineups for game_pk=%d", game_pk)
        try:
            boxscore = statsapi.boxscore_data(game_pk)
        except Exception as exc:
            logger.error("boxscore_data(%d) failed: %s", game_pk, exc)
            return []
        finally:
            self._sleep()

        lineups = []
        for side in ("home", "away"):
            team_data = boxscore.get(side, {})
            team_id = team_data.get("team", {}).get("id")
            if not team_id:
                continue
            batters_raw = team_data.get("battingOrder", [])
            players_map = team_data.get("players", {})
            batters: list[dict[str, Any]] = []
            for order_idx, player_key in enumerate(batters_raw, start=1):
                player_info = players_map.get(str(player_key), {})
                person = player_info.get("person", {})
                pos = player_info.get("position", {}).get("abbreviation", "")
                batters.append(
                    {
                        "player_id": person.get("id"),
                        "full_name": person.get("fullName", ""),
                        "batting_order": order_idx,
                        "position": pos,
                    }
                )
            confirmed = len(batters) == 9
            lineups.append(
                MLBLineup(
                    game_pk=game_pk,
                    team_id=team_id,
                    confirmed=confirmed,
                    batters=batters,
                )
            )
        return lineups

    def fetch_game_result(self, game_pk: int) -> Optional[MLBGameResult]:
        """Fetch final score and starter info for a completed game.

        Args:
            game_pk: MLB game identifier.

        Returns:
            MLBGameResult if the game is final, None otherwise.
        """
        logger.debug("Fetching result for game_pk=%d", game_pk)
        try:
            boxscore = statsapi.boxscore_data(game_pk)
        except Exception as exc:
            logger.error("boxscore_data(%d) failed: %s", game_pk, exc)
            return None
        finally:
            self._sleep()

        try:
            return self._parse_boxscore_result(game_pk, boxscore)
        except Exception as exc:
            logger.warning("Failed to parse result for game_pk=%d: %s", game_pk, exc)
            return None

    def fetch_umpire_assignment(self, game_pk: int) -> Optional[str]:
        """Fetch the home plate umpire name for a game.

        Args:
            game_pk: MLB game identifier.

        Returns:
            Umpire full name string, or None if unavailable.
        """
        logger.debug("Fetching umpire for game_pk=%d", game_pk)
        try:
            data = statsapi.get("game", {"gamePk": game_pk})
        except Exception as exc:
            logger.error("get(game, %d) failed: %s", game_pk, exc)
            return None
        finally:
            self._sleep()

        officials = data.get("liveData", {}).get("boxscore", {}).get("officials", [])
        for official in officials:
            if official.get("officialType") == "Home Plate":
                return official.get("official", {}).get("fullName")
        return None

    # ------------------------------------------------------------------
    # Roster / Players
    # ------------------------------------------------------------------

    def fetch_roster(self, team_id: int, season: int) -> list[MLBPlayer]:
        """Fetch 40-man roster for a team.

        Args:
            team_id: MLBAM team ID.
            season: Season year (e.g., 2025).

        Returns:
            List of MLBPlayer records.
        """
        logger.debug("Fetching roster: team_id=%d season=%d", team_id, season)
        try:
            data = statsapi.roster(team_id, season=season, rosterType="40Man")
        except Exception as exc:
            logger.error("roster(%d, %d) failed: %s", team_id, season, exc)
            return []
        finally:
            self._sleep()

        players = []
        for row in data.split("\n"):
            row = row.strip()
            if not row:
                continue
            # statsapi.roster() returns a formatted string, not structured data.
            # Use get("people") endpoint for structured data instead.
            logger.debug("Roster row: %s", row)

        # Fall back to structured endpoint
        try:
            raw = statsapi.get(
                "team_roster",
                {"teamId": team_id, "season": season, "rosterType": "40Man"},
            )
        except Exception as exc:
            logger.error("team_roster(%d, %d) failed: %s", team_id, season, exc)
            return []
        finally:
            self._sleep()

        for entry in raw.get("roster", []):
            person = entry.get("person", {})
            pos = entry.get("position", {}).get("abbreviation", "")
            players.append(
                MLBPlayer(
                    player_id=person.get("id", 0),
                    full_name=person.get("fullName", ""),
                    position=pos,
                    current_team_id=team_id,
                )
            )
        logger.info(
            "Fetched %d roster entries for team %d season %d",
            len(players),
            team_id,
            season,
        )
        return players

    def fetch_player(self, player_id: int) -> Optional[MLBPlayer]:
        """Fetch detailed player record including bats/throws.

        Args:
            player_id: MLBAM player ID.

        Returns:
            MLBPlayer record or None.
        """
        logger.debug("Fetching player: player_id=%d", player_id)
        try:
            raw = statsapi.get("person", {"personId": player_id})
        except Exception as exc:
            logger.error("person(%d) failed: %s", player_id, exc)
            return None
        finally:
            self._sleep()

        people = raw.get("people", [])
        if not people:
            return None
        p = people[0]
        pos = p.get("primaryPosition", {}).get("abbreviation", "")
        bats_code = p.get("batSide", {}).get("code", "")
        throws_code = p.get("pitchHand", {}).get("code", "")
        current_team = p.get("currentTeam", {}).get("id")
        return MLBPlayer(
            player_id=p.get("id", player_id),
            full_name=p.get("fullName", ""),
            position=pos or None,
            bats=bats_code or None,
            throws=throws_code or None,
            current_team_id=current_team,
        )

    # ------------------------------------------------------------------
    # Private parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_schedule_game(raw: dict[str, Any]) -> MLBGame:
        """Parse one game record from statsapi.schedule() output."""
        game_pk = int(raw["game_id"])
        game_date_str = raw.get("game_date", "")
        game_date = datetime.strptime(game_date_str, "%Y-%m-%d").date()

        status = raw.get("status", "")
        home_id = int(raw.get("home_id", 0))
        away_id = int(raw.get("away_id", 0))
        home_score_raw = raw.get("home_score")
        away_score_raw = raw.get("away_score")

        # Probable pitchers (may be 0 if not yet assigned)
        home_prob_id = raw.get("home_probable_pitcher_id") or None
        home_prob_name = raw.get("home_probable_pitcher") or None
        away_prob_id = raw.get("away_probable_pitcher_id") or None
        away_prob_name = raw.get("away_probable_pitcher") or None

        # Game time (UTC ISO string)
        game_time_str = raw.get("game_datetime")
        game_time: Optional[datetime] = None
        if game_time_str:
            try:
                game_time = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
            except ValueError:
                pass

        return MLBGame(
            game_pk=game_pk,
            game_date=game_date,
            status=status,
            home_team_id=home_id,
            home_team_name=raw.get("home_name", ""),
            away_team_id=away_id,
            away_team_name=raw.get("away_name", ""),
            home_score=int(home_score_raw) if home_score_raw is not None else None,
            away_score=int(away_score_raw) if away_score_raw is not None else None,
            home_starter_id=int(home_prob_id) if home_prob_id else None,
            home_starter_name=home_prob_name,
            away_starter_id=int(away_prob_id) if away_prob_id else None,
            away_starter_name=away_prob_name,
            venue=raw.get("venue_name"),
            game_time_utc=game_time,
        )

    @staticmethod
    def _parse_boxscore_result(game_pk: int, boxscore: dict[str, Any]) -> MLBGameResult:
        """Parse boxscore_data() output into MLBGameResult."""
        home = boxscore.get("home", {})
        away = boxscore.get("away", {})

        home_score = int(home.get("teamStats", {}).get("batting", {}).get("runs", 0))
        away_score = int(away.get("teamStats", {}).get("batting", {}).get("runs", 0))
        home_team_id = int(home.get("team", {}).get("id", 0))
        away_team_id = int(away.get("team", {}).get("id", 0))

        # Find starters (battingOrder position 0 = pitcher who started)
        home_starter_id: Optional[int] = None
        away_starter_id: Optional[int] = None
        home_starter_ip: Optional[float] = None
        away_starter_ip: Optional[float] = None

        for side, starter_id_ref, starter_ip_ref in [
            (home, "home_starter_id", "home_starter_ip"),
            (away, "away_starter_id", "away_starter_ip"),
        ]:
            for _key, p in side.get("players", {}).items():
                stats = p.get("stats", {}).get("pitching", {})
                if p.get("gameStatus", {}).get("isCurrentPitcher") is False:
                    if (
                        stats.get("note", "").startswith("W")
                        or p.get("allPositions", [{}])[0].get("type") == "Pitcher"
                    ):
                        pid = p.get("person", {}).get("id")
                        ip_str = stats.get("inningsPitched", "0.0")
                        try:
                            ip = float(ip_str)
                        except ValueError:
                            ip = 0.0
                        if side is home:
                            home_starter_id = pid
                            home_starter_ip = ip
                        else:
                            away_starter_id = pid
                            away_starter_ip = ip
                        break

        info = boxscore.get("gameBoxInfo", [])
        innings = 9
        status = "Final"
        for item in info:
            if "inning" in item.get("label", "").lower():
                try:
                    innings = int(item.get("value", "9"))
                except ValueError:
                    pass

        return MLBGameResult(
            game_pk=game_pk,
            home_score=home_score,
            away_score=away_score,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
            innings=innings,
            status=status,
            home_starter_id=home_starter_id,
            away_starter_id=away_starter_id,
            home_starter_ip=home_starter_ip,
            away_starter_ip=away_starter_ip,
        )
