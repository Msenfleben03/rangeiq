"""Tests for the Unified NCAAB Fetcher.

Covers:
    - Single-pass scores + odds fetching
    - Incremental mode (only new games)
    - Skip list for known-empty games
    - Best-provider selection
    - Enriched parquet schema
    - Edge cases (no odds, no scores, empty season)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from pipelines.espn_core_odds_provider import OddsSnapshot
from pipelines.unified_fetcher import (
    ODDS_COLUMNS,
    UnifiedNCAABFetcher,
    _load_skip_list,
    _pick_best_provider,
    _save_skip_list,
    _snapshot_to_flat_dict,
    _snapshots_to_dataframe,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SCORES_DF = pd.DataFrame(
    [
        {
            "season": 2025,
            "date": "2025-01-15",
            "game_id": "401700001",
            "team_id": "DUKE",
            "opponent_id": "UNC",
            "opponent_name": "North Carolina",
            "location": "Home",
            "result": "W",
            "points_for": 78,
            "points_against": 72,
            "conference": "2",
        },
        {
            "season": 2025,
            "date": "2025-01-16",
            "game_id": "401700002",
            "team_id": "KU",
            "opponent_id": "KSU",
            "opponent_name": "Kansas State",
            "location": "Away",
            "result": "L",
            "points_for": 65,
            "points_against": 70,
            "conference": "8",
        },
        {
            "season": 2025,
            "date": "2025-01-17",
            "game_id": "401700003",
            "team_id": "SMALL",
            "opponent_id": "TINY",
            "opponent_name": "Tiny College",
            "location": "Home",
            "result": "W",
            "points_for": 85,
            "points_against": 60,
            "conference": "99",
        },
    ]
)


def _make_snapshot(
    game_id: str,
    provider_id: int = 58,
    provider_name: str = "ESPN BET",
    home_ml: int = -150,
    away_ml: int = 130,
    spread: float = -3.5,
    home_ml_close: int | None = -145,
    away_ml_close: int | None = 125,
) -> OddsSnapshot:
    """Create a test OddsSnapshot."""
    return OddsSnapshot(
        game_id=game_id,
        provider_id=provider_id,
        provider_name=provider_name,
        spread=spread,
        over_under=148.5,
        home_moneyline=home_ml,
        away_moneyline=away_ml,
        home_spread_odds=-110,
        away_spread_odds=-110,
        over_odds=-110,
        under_odds=-110,
        home_spread_open=-4.0,
        away_spread_open=4.0,
        home_spread_odds_open=-105,
        away_spread_odds_open=-115,
        home_ml_open=-160,
        away_ml_open=140,
        total_open=150.0,
        over_odds_open=-108,
        under_odds_open=-112,
        home_spread_close=-3.5,
        away_spread_close=3.5,
        home_spread_odds_close=-112,
        away_spread_odds_close=-108,
        home_ml_close=home_ml_close,
        away_ml_close=away_ml_close,
        total_close=149.0,
        over_odds_close=-110,
        under_odds_close=-110,
    )


# ---------------------------------------------------------------------------
# TestPickBestProvider
# ---------------------------------------------------------------------------


class TestPickBestProvider:
    """Tests for _pick_best_provider."""

    def test_empty_list(self) -> None:
        assert _pick_best_provider([]) is None

    def test_single_provider(self) -> None:
        snap = _make_snapshot("401700001")
        result = _pick_best_provider([snap])
        assert result is snap

    def test_filters_live_provider(self) -> None:
        pre_game = _make_snapshot("401700001", provider_id=58)
        live = _make_snapshot("401700001", provider_id=59, provider_name="ESPN BET Live")
        result = _pick_best_provider([live, pre_game])
        assert result.provider_id == 58

    def test_prefers_closing_data(self) -> None:
        with_close = _make_snapshot("401700001", home_ml_close=-145)
        without_close = _make_snapshot("401700001", home_ml_close=None)
        result = _pick_best_provider([without_close, with_close])
        assert result.home_ml_close == -145

    def test_fallback_to_live_if_only_option(self) -> None:
        live = _make_snapshot("401700001", provider_id=59)
        result = _pick_best_provider([live])
        assert result.provider_id == 59


# ---------------------------------------------------------------------------
# TestSnapshotToFlatDict
# ---------------------------------------------------------------------------


class TestSnapshotToFlatDict:
    """Tests for _snapshot_to_flat_dict."""

    def test_none_returns_all_none(self) -> None:
        result = _snapshot_to_flat_dict(None)
        assert set(result.keys()) == set(ODDS_COLUMNS)
        assert all(v is None for v in result.values())

    def test_valid_snapshot(self) -> None:
        snap = _make_snapshot("401700001")
        result = _snapshot_to_flat_dict(snap)
        assert result["spread"] == -3.5
        assert result["home_moneyline"] == -150
        assert result["away_moneyline"] == 130
        assert result["odds_provider"] == "ESPN BET"
        assert result["home_ml_close"] == -145
        assert result["total_open"] == 150.0

    def test_all_odds_columns_present(self) -> None:
        snap = _make_snapshot("401700001")
        result = _snapshot_to_flat_dict(snap)
        for col in ODDS_COLUMNS:
            assert col in result


# ---------------------------------------------------------------------------
# TestSnapshotsToDataframe
# ---------------------------------------------------------------------------


class TestSnapshotsToDataframe:
    """Tests for _snapshots_to_dataframe."""

    def test_empty_results(self) -> None:
        result = _snapshots_to_dataframe({})
        assert result.empty

    def test_single_game_multi_provider(self) -> None:
        results = {
            "401700001": [
                _make_snapshot("401700001", provider_id=58),
                _make_snapshot("401700001", provider_id=59),
            ]
        }
        df = _snapshots_to_dataframe(results)
        assert len(df) == 2
        assert set(df["provider_id"]) == {58, 59}

    def test_multi_game(self) -> None:
        results = {
            "401700001": [_make_snapshot("401700001")],
            "401700002": [_make_snapshot("401700002")],
        }
        df = _snapshots_to_dataframe(results)
        assert len(df) == 2
        assert set(df["game_id"]) == {"401700001", "401700002"}


# ---------------------------------------------------------------------------
# TestSkipList
# ---------------------------------------------------------------------------


class TestSkipList:
    """Tests for skip list persistence."""

    def test_save_and_load(self, tmp_path: Path) -> None:
        skip_dir = tmp_path / "skip_lists"
        with patch("pipelines.unified_fetcher.SKIP_LIST_DIR", skip_dir):
            ids = {"401700003", "401700004", "401700005"}
            _save_skip_list(2025, ids)
            loaded = _load_skip_list(2025)
            assert loaded == ids

    def test_load_nonexistent(self, tmp_path: Path) -> None:
        with patch("pipelines.unified_fetcher.SKIP_LIST_DIR", tmp_path / "missing"):
            result = _load_skip_list(2025)
            assert result == set()

    def test_empty_skip_list(self, tmp_path: Path) -> None:
        skip_dir = tmp_path / "skip_lists"
        with patch("pipelines.unified_fetcher.SKIP_LIST_DIR", skip_dir):
            _save_skip_list(2025, set())
            loaded = _load_skip_list(2025)
            assert loaded == set()


# ---------------------------------------------------------------------------
# TestUnifiedFetcher
# ---------------------------------------------------------------------------


class TestUnifiedFetcher:
    """Integration tests for UnifiedNCAABFetcher."""

    @patch("pipelines.unified_fetcher.ESPNCoreOddsFetcher")
    @patch("pipelines.unified_fetcher.ESPNDataFetcher")
    def test_fetch_season_with_odds(
        self,
        mock_score_cls: MagicMock,
        mock_odds_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Full season fetch with odds enrichment."""
        raw_dir = tmp_path / "raw"
        odds_dir = tmp_path / "odds"

        # Mock score fetcher
        mock_score = MagicMock()
        mock_score_cls.return_value = mock_score
        mock_score.fetch_season_data.return_value = SAMPLE_SCORES_DF.copy()

        # Mock odds fetcher
        mock_odds = MagicMock()
        mock_odds_cls.return_value = mock_odds
        mock_odds.fetch_game_odds.side_effect = lambda gid: (
            [_make_snapshot(gid)] if gid in ("401700001", "401700002") else []
        )

        with patch("pipelines.unified_fetcher.SKIP_LIST_DIR", tmp_path / "skip"):
            fetcher = UnifiedNCAABFetcher(
                raw_dir=str(raw_dir),
                odds_dir=str(odds_dir),
            )
            df = fetcher.fetch_season(2025, with_odds=True)

        # Should have all 3 games
        assert len(df) == 3

        # Games 1 and 2 should have odds
        game1 = df[df["game_id"] == "401700001"].iloc[0]
        assert game1["home_moneyline"] == -150
        assert game1["home_ml_close"] == -145
        assert game1["odds_provider"] == "ESPN BET"

        # Game 3 (small conference) should have None odds
        game3 = df[df["game_id"] == "401700003"].iloc[0]
        assert pd.isna(game3["home_moneyline"])

        # Enriched parquet should exist
        parquet_path = raw_dir / "ncaab_games_2025.parquet"
        assert parquet_path.exists()
        saved = pd.read_parquet(parquet_path)
        assert "home_moneyline" in saved.columns
        assert "odds_provider" in saved.columns

    @patch("pipelines.unified_fetcher.ESPNCoreOddsFetcher")
    @patch("pipelines.unified_fetcher.ESPNDataFetcher")
    def test_fetch_season_no_odds(
        self,
        mock_score_cls: MagicMock,
        mock_odds_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Scores-only mode skips odds fetching."""
        raw_dir = tmp_path / "raw"
        odds_dir = tmp_path / "odds"

        mock_score = MagicMock()
        mock_score_cls.return_value = mock_score
        mock_score.fetch_season_data.return_value = SAMPLE_SCORES_DF.copy()

        fetcher = UnifiedNCAABFetcher(
            raw_dir=str(raw_dir),
            odds_dir=str(odds_dir),
        )
        df = fetcher.fetch_season(2025, with_odds=False)

        # Should have all 3 games with odds columns (all None)
        assert len(df) == 3
        assert "home_moneyline" in df.columns
        assert df["home_moneyline"].isna().all()

        # Odds fetcher should never be called
        mock_odds_cls.assert_not_called()

    @patch("pipelines.unified_fetcher.ESPNCoreOddsFetcher")
    @patch("pipelines.unified_fetcher.ESPNDataFetcher")
    def test_incremental_mode(
        self,
        mock_score_cls: MagicMock,
        mock_odds_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Incremental mode only fetches odds for new games."""
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir(parents=True)
        odds_dir = tmp_path / "odds"

        # Pre-populate with 2 existing games (one with odds, one without)
        existing_df = SAMPLE_SCORES_DF.iloc[:2].copy()
        existing_df["home_moneyline"] = [-150, None]
        for col in ODDS_COLUMNS:
            if col not in existing_df.columns:
                existing_df[col] = None
        existing_df.to_parquet(raw_dir / "ncaab_games_2025.parquet", index=False)

        # Score fetcher returns all 3 games (including new game_id 401700003)
        mock_score = MagicMock()
        mock_score_cls.return_value = mock_score
        mock_score.fetch_season_data.return_value = SAMPLE_SCORES_DF.copy()

        # Odds fetcher should only be called for new games
        mock_odds = MagicMock()
        mock_odds_cls.return_value = mock_odds
        mock_odds.fetch_game_odds.return_value = []

        with patch("pipelines.unified_fetcher.SKIP_LIST_DIR", tmp_path / "skip"):
            fetcher = UnifiedNCAABFetcher(
                raw_dir=str(raw_dir),
                odds_dir=str(odds_dir),
            )
            df = fetcher.fetch_season(2025, incremental=True)

        # Should have all 3 games
        assert len(df) == 3

    @patch("pipelines.unified_fetcher.ESPNCoreOddsFetcher")
    @patch("pipelines.unified_fetcher.ESPNDataFetcher")
    def test_skip_list_used(
        self,
        mock_score_cls: MagicMock,
        mock_odds_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Skip list prevents re-fetching known-empty games."""
        raw_dir = tmp_path / "raw"
        odds_dir = tmp_path / "odds"
        skip_dir = tmp_path / "skip"

        # Pre-populate skip list with game 3
        with patch("pipelines.unified_fetcher.SKIP_LIST_DIR", skip_dir):
            _save_skip_list(2025, {"401700003"})

        mock_score = MagicMock()
        mock_score_cls.return_value = mock_score
        mock_score.fetch_season_data.return_value = SAMPLE_SCORES_DF.copy()

        mock_odds = MagicMock()
        mock_odds_cls.return_value = mock_odds
        mock_odds.fetch_game_odds.side_effect = lambda gid: [_make_snapshot(gid)]

        with patch("pipelines.unified_fetcher.SKIP_LIST_DIR", skip_dir):
            fetcher = UnifiedNCAABFetcher(
                raw_dir=str(raw_dir),
                odds_dir=str(odds_dir),
            )
            fetcher.fetch_season(2025, use_skip_list=True)

        # Should NOT have fetched odds for game 3 (in skip list)
        called_ids = [call.args[0] for call in mock_odds.fetch_game_odds.call_args_list]
        assert "401700003" not in called_ids
        assert "401700001" in called_ids
        assert "401700002" in called_ids

    @patch("pipelines.unified_fetcher.ESPNDataFetcher")
    def test_empty_season(
        self,
        mock_score_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Empty season returns empty DataFrame."""
        raw_dir = tmp_path / "raw"
        odds_dir = tmp_path / "odds"

        mock_score = MagicMock()
        mock_score_cls.return_value = mock_score
        mock_score.fetch_season_data.return_value = pd.DataFrame()

        fetcher = UnifiedNCAABFetcher(
            raw_dir=str(raw_dir),
            odds_dir=str(odds_dir),
        )
        df = fetcher.fetch_season(2025)

        assert df.empty

    @patch("pipelines.unified_fetcher.ESPNCoreOddsFetcher")
    @patch("pipelines.unified_fetcher.ESPNDataFetcher")
    def test_raw_odds_parquet_saved(
        self,
        mock_score_cls: MagicMock,
        mock_odds_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Raw odds parquet with all providers is saved separately."""
        raw_dir = tmp_path / "raw"
        odds_dir = tmp_path / "odds"

        mock_score = MagicMock()
        mock_score_cls.return_value = mock_score
        mock_score.fetch_season_data.return_value = SAMPLE_SCORES_DF.copy()

        # Return 2 providers for game 1
        mock_odds = MagicMock()
        mock_odds_cls.return_value = mock_odds
        mock_odds.fetch_game_odds.side_effect = lambda gid: (
            [
                _make_snapshot(gid, provider_id=58, provider_name="ESPN BET"),
                _make_snapshot(gid, provider_id=100, provider_name="DraftKings"),
            ]
            if gid == "401700001"
            else []
        )

        with patch("pipelines.unified_fetcher.SKIP_LIST_DIR", tmp_path / "skip"):
            fetcher = UnifiedNCAABFetcher(
                raw_dir=str(raw_dir),
                odds_dir=str(odds_dir),
            )
            fetcher.fetch_season(2025)

        # Raw odds parquet should have 2 rows (2 providers for game 1)
        odds_path = odds_dir / "ncaab_odds_2025.parquet"
        assert odds_path.exists()
        odds_df = pd.read_parquet(odds_path)
        assert len(odds_df) == 2
        assert set(odds_df["provider_id"]) == {58, 100}


# ---------------------------------------------------------------------------
# TestCurrentSeason
# ---------------------------------------------------------------------------


class TestCurrentSeason:
    """Tests for current_ncaab_season helper."""

    def test_import(self) -> None:
        from scripts.fetch_season_data import current_ncaab_season  # noqa: F401
