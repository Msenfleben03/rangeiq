"""Tests for the daily paper betting pipeline.

Tests cover:
- ESPN Scoreboard API fetching
- Prediction generation with Barttorvik
- Auto-recording of paper bets
- Bet settlement
- Weekly review report
- Daily run orchestrator
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ── ESPN Scoreboard fetching ──────────────────────────────────────────────


MOCK_SCOREBOARD_RESPONSE = {
    "events": [
        {
            "id": "401720001",
            "date": "2026-02-17T19:00Z",
            "competitions": [
                {
                    "neutralSite": False,
                    "status": {"type": {"name": "STATUS_SCHEDULED"}},
                    "competitors": [
                        {
                            "homeAway": "home",
                            "score": "0",
                            "team": {
                                "id": "2305",
                                "abbreviation": "DUKE",
                                "displayName": "Duke Blue Devils",
                            },
                        },
                        {
                            "homeAway": "away",
                            "score": "0",
                            "team": {
                                "id": "153",
                                "abbreviation": "UNC",
                                "displayName": "North Carolina Tar Heels",
                            },
                        },
                    ],
                }
            ],
        },
        {
            "id": "401720002",
            "date": "2026-02-17T21:00Z",
            "competitions": [
                {
                    "neutralSite": True,
                    "status": {"type": {"name": "STATUS_FINAL"}},
                    "competitors": [
                        {
                            "homeAway": "home",
                            "score": "75",
                            "team": {
                                "id": "2509",
                                "abbreviation": "UK",
                                "displayName": "Kentucky Wildcats",
                            },
                        },
                        {
                            "homeAway": "away",
                            "score": "70",
                            "team": {
                                "id": "97",
                                "abbreviation": "TENN",
                                "displayName": "Tennessee Volunteers",
                            },
                        },
                    ],
                }
            ],
        },
    ]
}


class TestFetchEspnScoreboard:
    """Tests for fetch_espn_scoreboard()."""

    @patch("scripts.daily_predictions.requests.get")
    def test_basic_fetch(self, mock_get):
        from scripts.daily_predictions import fetch_espn_scoreboard

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SCOREBOARD_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        games = fetch_espn_scoreboard(datetime(2026, 2, 17))

        assert len(games) == 2
        assert games[0]["game_id"] == "401720001"
        assert games[0]["home"] == "DUKE"
        assert games[0]["away"] == "UNC"
        assert games[0]["neutral_site"] is False
        assert games[0]["status"] == "STATUS_SCHEDULED"

    @patch("scripts.daily_predictions.requests.get")
    def test_neutral_site(self, mock_get):
        from scripts.daily_predictions import fetch_espn_scoreboard

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SCOREBOARD_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        games = fetch_espn_scoreboard(datetime(2026, 2, 17))
        assert games[1]["neutral_site"] is True

    @patch("scripts.daily_predictions.requests.get")
    def test_final_scores(self, mock_get):
        from scripts.daily_predictions import fetch_espn_scoreboard

        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_SCOREBOARD_RESPONSE
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        games = fetch_espn_scoreboard(datetime(2026, 2, 17))
        assert games[1]["home_score"] == 75
        assert games[1]["away_score"] == 70

    @patch("scripts.daily_predictions.requests.get")
    def test_api_error_returns_empty(self, mock_get):
        import requests as req
        from scripts.daily_predictions import fetch_espn_scoreboard

        mock_get.side_effect = req.ConnectionError("Connection error")
        games = fetch_espn_scoreboard(datetime(2026, 2, 17))
        assert games == []

    @patch("scripts.daily_predictions.requests.get")
    def test_empty_events(self, mock_get):
        from scripts.daily_predictions import fetch_espn_scoreboard

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"events": []}
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        games = fetch_espn_scoreboard(datetime(2026, 2, 17))
        assert games == []


# ── Prediction generation ─────────────────────────────────────────────────


class TestGeneratePredictions:
    """Tests for generate_predictions()."""

    def _make_mock_model(self):
        model = MagicMock()
        model.predict_win_probability.return_value = 0.65
        model.predict_spread.return_value = -5.5
        return model

    def _make_games(self):
        return [
            {
                "game_id": "401720001",
                "home": "DUKE",
                "away": "UNC",
                "home_name": "Duke Blue Devils",
                "away_name": "North Carolina Tar Heels",
                "neutral_site": False,
                "status": "STATUS_SCHEDULED",
            }
        ]

    def test_basic_prediction_no_odds(self):
        from scripts.daily_predictions import generate_predictions

        model = self._make_mock_model()
        games = self._make_games()

        df = generate_predictions(model, games, orchestrator=None)
        assert len(df) == 1
        assert df.iloc[0]["home_prob"] == 0.65
        assert df.iloc[0]["away_prob"] == pytest.approx(0.35)
        assert df.iloc[0]["predicted_spread"] == -5.5

    def test_barttorvik_adjustment(self):
        from scripts.daily_predictions import generate_predictions

        model = self._make_mock_model()
        games = self._make_games()

        # Create mock barttorvik data
        mock_bart_df = pd.DataFrame({"team": ["Duke", "UNC"]})

        with (
            patch("scripts.daily_predictions.espn_id_to_barttorvik") as mock_mapper,
            patch("scripts.daily_predictions.compute_barttorvik_differentials") as mock_diffs,
        ):
            mock_mapper.side_effect = lambda x: {"DUKE": "Duke", "UNC": "North Carolina"}.get(x)
            mock_diffs.return_value = {
                "net_rating_diff": 10.0,
                "barthag_diff": 0.2,
            }

            df = generate_predictions(
                model,
                games,
                orchestrator=None,
                use_barttorvik=True,
                barttorvik_df=mock_bart_df,
                barttorvik_weight=1.0,
                target_date=datetime(2026, 2, 17),
            )

            # Bart adjustment should move home_prob up
            assert df.iloc[0]["home_prob"] > 0.65
            assert df.iloc[0]["bart_adj"] > 0

    def test_no_barttorvik_when_disabled(self):
        from scripts.daily_predictions import generate_predictions

        model = self._make_mock_model()
        games = self._make_games()

        df = generate_predictions(model, games, orchestrator=None, use_barttorvik=False)
        assert df.iloc[0]["bart_adj"] == 0.0


# ── Auto-recording bets ──────────────────────────────────────────────────


class TestAutoRecordBets:
    """Tests for auto_record_bets_from_predictions()."""

    def _make_predictions_df(self):
        return pd.DataFrame(
            [
                {
                    "game_id": "401720001",
                    "home": "DUKE",
                    "away": "UNC",
                    "home_name": "Duke Blue Devils",
                    "away_name": "North Carolina Tar Heels",
                    "home_prob": 0.65,
                    "away_prob": 0.35,
                    "rec_side": "HOME",
                    "rec_odds": -150,
                    "rec_kelly": 0.02,
                    "rec_stake": 100.0,
                    "home_edge": 0.08,
                    "away_edge": -0.05,
                    "bart_adj": 0.02,
                },
                {
                    "game_id": "401720002",
                    "home": "UK",
                    "away": "TENN",
                    "home_name": "Kentucky Wildcats",
                    "away_name": "Tennessee Volunteers",
                    "home_prob": 0.55,
                    "away_prob": 0.45,
                    "rec_side": None,
                    "rec_odds": None,
                    "rec_kelly": None,
                    "rec_stake": None,
                    "home_edge": 0.03,
                    "away_edge": 0.01,
                    "bart_adj": 0.01,
                },
            ]
        )

    def test_dry_run_returns_bets_without_inserting(self):
        from tracking.logger import auto_record_bets_from_predictions

        db = MagicMock()
        df = self._make_predictions_df()

        recorded = auto_record_bets_from_predictions(
            db,
            df,
            "2026-02-17",
            dry_run=True,
        )

        assert len(recorded) == 1
        assert recorded[0]["selection"] == "Duke Blue Devils ML"
        assert recorded[0]["odds_placed"] == -150
        db.insert_bet.assert_not_called()

    def test_filters_to_recommendations_only(self):
        from tracking.logger import auto_record_bets_from_predictions

        db = MagicMock()
        df = self._make_predictions_df()

        recorded = auto_record_bets_from_predictions(
            db,
            df,
            "2026-02-17",
            dry_run=True,
        )

        # Only the first game has rec_side set
        assert len(recorded) == 1

    def test_empty_df(self):
        from tracking.logger import auto_record_bets_from_predictions

        db = MagicMock()
        recorded = auto_record_bets_from_predictions(
            db,
            pd.DataFrame(),
            "2026-02-17",
        )
        assert recorded == []

    def test_max_bets_limit(self):
        from tracking.logger import auto_record_bets_from_predictions

        db = MagicMock()
        # Create 5 recommendations
        rows = []
        for i in range(5):
            rows.append(
                {
                    "game_id": f"game_{i}",
                    "home": f"TEAM{i}",
                    "away": f"OPP{i}",
                    "home_name": f"Team {i}",
                    "away_name": f"Opp {i}",
                    "home_prob": 0.70,
                    "away_prob": 0.30,
                    "rec_side": "HOME",
                    "rec_odds": -120,
                    "rec_kelly": 0.02,
                    "rec_stake": 80.0,
                    "home_edge": 0.10 - i * 0.01,
                    "away_edge": -0.05,
                    "bart_adj": 0.01,
                }
            )
        df = pd.DataFrame(rows)

        recorded = auto_record_bets_from_predictions(
            db,
            df,
            "2026-02-17",
            dry_run=True,
            max_bets=3,
        )
        assert len(recorded) == 3


# ── Bet settlement ────────────────────────────────────────────────────────


class TestSettlement:
    """Tests for settle_yesterdays_bets()."""

    @patch("scripts.daily_run.ESPNCoreOddsFetcher")
    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_settle_winning_bet(self, mock_fetch, mock_fetcher_cls):
        from scripts.daily_run import settle_yesterdays_bets

        mock_fetch.return_value = [
            {
                "game_id": "401720001",
                "home": "DUKE",
                "away": "UNC",
                "home_name": "Duke Blue Devils",
                "away_name": "North Carolina Tar Heels",
                "home_score": 85,
                "away_score": 72,
                "status": "STATUS_FINAL",
            }
        ]

        # Mock fetcher for CLV pass (returns empty — no closing odds)
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_game_odds.return_value = []
        mock_fetcher_cls.return_value = mock_fetcher

        db = MagicMock()
        db.execute_query.side_effect = lambda q, p=None: (
            [
                {
                    "id": 1,
                    "game_id": "401720001",
                    "selection": "Duke Blue Devils ML",
                    "bet_type": "moneyline",
                    "odds_placed": -150,
                    "stake": 100.0,
                }
            ]
            if "SELECT * FROM bets" in q
            else None
        )

        result = settle_yesterdays_bets(db, "2026-02-16")
        assert result["settled"] == 1

    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_no_pending_bets(self, mock_fetch):
        from scripts.daily_run import settle_yesterdays_bets

        db = MagicMock()
        db.execute_query.return_value = []

        result = settle_yesterdays_bets(db, "2026-02-16")
        assert result["settled"] == 0

    @patch("scripts.daily_run.ESPNCoreOddsFetcher")
    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_game_not_final_yet(self, mock_fetch, mock_fetcher_cls):
        from scripts.daily_run import settle_yesterdays_bets

        mock_fetch.return_value = [
            {
                "game_id": "401720001",
                "home": "DUKE",
                "away": "UNC",
                "home_name": "Duke",
                "home_score": 40,
                "away_score": 35,
                "status": "STATUS_IN_PROGRESS",
            }
        ]

        mock_fetcher_cls.return_value = MagicMock()

        db = MagicMock()
        db.execute_query.side_effect = lambda q, p=None: (
            [
                {
                    "id": 1,
                    "game_id": "401720001",
                    "selection": "Duke ML",
                    "bet_type": "moneyline",
                    "odds_placed": -150,
                    "stake": 100.0,
                }
            ]
            if "SELECT * FROM bets" in q
            else None
        )

        result = settle_yesterdays_bets(db, "2026-02-16")
        assert result["settled"] == 0

    @patch("scripts.daily_run.ESPNCoreOddsFetcher")
    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_settle_calculates_clv(self, mock_fetch, mock_fetcher_cls):
        from pipelines.espn_core_odds_provider import OddsSnapshot
        from scripts.daily_run import settle_yesterdays_bets

        mock_fetch.return_value = [
            {
                "game_id": "401720001",
                "home": "DUKE",
                "away": "UNC",
                "home_name": "Duke Blue Devils",
                "away_name": "North Carolina Tar Heels",
                "home_score": 85,
                "away_score": 72,
                "status": "STATUS_FINAL",
            }
        ]

        # Mock ESPN Core API returning closing odds
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_game_odds.return_value = [
            OddsSnapshot(
                game_id="401720001",
                provider_id=100,
                provider_name="Draft Kings",
                home_moneyline=-160,
                away_moneyline=140,
                spread=-3.5,
                home_spread_odds=-110,
                away_spread_odds=-110,
                over_under=145.5,
                over_odds=-110,
                under_odds=-110,
                home_ml_close=-160,
                away_ml_close=140,
                home_spread_close=-3.5,
                home_spread_odds_close=-112,
                away_spread_close=3.5,
                away_spread_odds_close=-108,
                total_close=146.0,
                over_odds_close=-108,
                under_odds_close=-112,
            )
        ]
        mock_fetcher_cls.return_value = mock_fetcher

        # Track all SQL calls
        updates = []

        def mock_execute(q, p=None):
            if "SELECT * FROM bets" in q:
                return [
                    {
                        "id": 1,
                        "game_id": "401720001",
                        "selection": "Duke Blue Devils ML",
                        "bet_type": "moneyline",
                        "odds_placed": -150,
                        "stake": 100.0,
                    }
                ]
            if "UPDATE bets" in q or "INSERT" in q:
                updates.append((q, p))
            return None

        db = MagicMock()
        db.execute_query.side_effect = mock_execute

        result = settle_yesterdays_bets(db, "2026-02-16")

        assert result["settled"] == 1
        assert result["clv_updated"] >= 1

        # Verify CLV update was called
        clv_updates = [(q, p) for q, p in updates if "odds_closing" in q or "clv" in q]
        assert len(clv_updates) >= 1

    @patch("scripts.daily_run.ESPNCoreOddsFetcher")
    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_settle_clv_graceful_on_missing_odds(self, mock_fetch, mock_fetcher_cls):
        from scripts.daily_run import settle_yesterdays_bets

        mock_fetch.return_value = [
            {
                "game_id": "401720001",
                "home": "DUKE",
                "away": "UNC",
                "home_name": "Duke Blue Devils",
                "away_name": "North Carolina Tar Heels",
                "home_score": 85,
                "away_score": 72,
                "status": "STATUS_FINAL",
            }
        ]

        # ESPN Core API returns no odds
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_game_odds.return_value = []
        mock_fetcher_cls.return_value = mock_fetcher

        db = MagicMock()
        db.execute_query.side_effect = lambda q, p=None: (
            [
                {
                    "id": 1,
                    "game_id": "401720001",
                    "selection": "Duke Blue Devils ML",
                    "bet_type": "moneyline",
                    "odds_placed": -150,
                    "stake": 100.0,
                }
            ]
            if "SELECT * FROM bets" in q
            else None
        )

        result = settle_yesterdays_bets(db, "2026-02-16")

        # Settlement still works even without closing odds
        assert result["settled"] == 1
        assert result["clv_failed"] >= 1

    @patch("scripts.daily_run.ESPNCoreOddsFetcher")
    @patch("scripts.daily_run.fetch_espn_scoreboard")
    def test_settle_stores_closing_snapshot(self, mock_fetch, mock_fetcher_cls):
        from pipelines.espn_core_odds_provider import OddsSnapshot
        from scripts.daily_run import settle_yesterdays_bets

        mock_fetch.return_value = [
            {
                "game_id": "401720001",
                "home": "DUKE",
                "away": "UNC",
                "home_name": "Duke Blue Devils",
                "away_name": "North Carolina Tar Heels",
                "home_score": 85,
                "away_score": 72,
                "status": "STATUS_FINAL",
            }
        ]

        mock_fetcher = MagicMock()
        mock_fetcher.fetch_game_odds.return_value = [
            OddsSnapshot(
                game_id="401720001",
                provider_id=100,
                provider_name="Draft Kings",
                home_moneyline=-160,
                away_moneyline=140,
                home_ml_close=-160,
                away_ml_close=140,
                home_spread_close=-3.5,
                home_spread_odds_close=-112,
                away_spread_close=3.5,
                away_spread_odds_close=-108,
                total_close=146.0,
                over_odds_close=-108,
                under_odds_close=-112,
            )
        ]
        mock_fetcher_cls.return_value = mock_fetcher

        inserts = []

        def mock_execute(q, p=None):
            if "SELECT * FROM bets" in q:
                return [
                    {
                        "id": 1,
                        "game_id": "401720001",
                        "selection": "Duke Blue Devils ML",
                        "bet_type": "moneyline",
                        "odds_placed": -150,
                        "stake": 100.0,
                    }
                ]
            if "INSERT" in q and "odds_snapshots" in q:
                inserts.append((q, p))
            return None

        db = MagicMock()
        db.execute_query.side_effect = mock_execute

        settle_yesterdays_bets(db, "2026-02-16")

        # Verify closing snapshot was stored
        assert len(inserts) >= 1
        insert_params = inserts[0][1]
        assert "closing" in insert_params


# ── Weekly review ─────────────────────────────────────────────────────────


class TestPaperBettingWeeklyReview:
    """Tests for paper_betting_weekly_review()."""

    def test_no_bets(self):
        from tracking.reports import paper_betting_weekly_review

        db = MagicMock()
        db.execute_query.return_value = []

        result = paper_betting_weekly_review(db)
        assert result["total_bets"] == 0

    def test_with_settled_bets(self):
        from tracking.reports import paper_betting_weekly_review

        today = datetime.now().strftime("%Y-%m-%d")
        mock_bets = [
            {
                "result": "win",
                "profit_loss": 80.0,
                "stake": 100.0,
                "clv": 0.02,
                "model_edge": 0.08,
                "game_date": today,
                "created_at": f"{today} 12:00:00",
            },
            {
                "result": "loss",
                "profit_loss": -100.0,
                "stake": 100.0,
                "clv": -0.01,
                "model_edge": 0.06,
                "game_date": today,
                "created_at": f"{today} 14:00:00",
            },
        ]

        db = MagicMock()
        db.execute_query.return_value = mock_bets

        result = paper_betting_weekly_review(db)
        assert result["settled"] == 2
        assert result["wins"] == 1
        assert result["losses"] == 1
        assert result["total_pnl"] == -20.0
        assert result["roi"] == pytest.approx(-0.10)


# ── Prob to American conversion ───────────────────────────────────────────


class TestProbToAmerican:
    """Tests for _prob_to_american()."""

    def test_favorite(self):
        from scripts.daily_predictions import _prob_to_american

        assert _prob_to_american(0.65) < 0  # Negative odds for favorites

    def test_underdog(self):
        from scripts.daily_predictions import _prob_to_american

        assert _prob_to_american(0.35) > 0  # Positive odds for underdogs

    def test_even_money(self):
        from scripts.daily_predictions import _prob_to_american

        assert _prob_to_american(0.50) == -100

    def test_extreme_prob(self):
        from scripts.daily_predictions import _prob_to_american

        assert _prob_to_american(0.0) == 0
        assert _prob_to_american(1.0) == 0


# ── Parse date ────────────────────────────────────────────────────────────


class TestParseDate:
    """Tests for parse_date()."""

    def test_today(self):
        from scripts.daily_predictions import parse_date

        result = parse_date("today")
        assert result.date() == datetime.now().date()

    def test_tomorrow(self):
        from scripts.daily_predictions import parse_date

        result = parse_date("tomorrow")
        assert result.date() == (datetime.now() + timedelta(days=1)).date()

    def test_specific_date(self):
        from scripts.daily_predictions import parse_date

        result = parse_date("2026-02-17")
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 17


# ── PaperBettingConfig ────────────────────────────────────────────────────


class TestPaperBettingConfig:
    """Tests for PaperBettingConfig constants."""

    def test_config_values(self):
        from config.constants import PAPER_BETTING

        assert PAPER_BETTING.MIN_EDGE == 0.075
        assert PAPER_BETTING.BARTTORVIK_WEIGHT == 1.0
        assert PAPER_BETTING.PAPER_BANKROLL == 5000.0
        assert PAPER_BETTING.MAX_BETS_PER_DAY == 10

    def test_espn_url(self):
        from config.constants import PAPER_BETTING

        assert "scoreboard" in PAPER_BETTING.ESPN_SCOREBOARD_URL
        assert "mens-college-basketball" in PAPER_BETTING.ESPN_SCOREBOARD_URL
