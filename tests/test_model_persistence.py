"""Tests for model persistence utilities."""

from __future__ import annotations

import json
import pickle
import sqlite3

import pytest

from models.model_persistence import (
    ModelMetadata,
    SavedModel,
    export_ratings_csv,
    export_ratings_db,
    load_model,
    save_model,
)


# ============================================================================
# Fixtures
# ============================================================================


class FakeModel:
    """Minimal model stand-in with ratings dict and to_dataframe()."""

    def __init__(self, ratings: dict[str, float] | None = None):
        self.ratings = ratings or {"duke": 1650.0, "unc": 1600.0, "kansas": 1550.0}
        self.conferences = {"duke": "ACC", "unc": "ACC", "kansas": "Big 12"}

    def to_dataframe(self):
        import pandas as pd

        rows = [
            {
                "team_id": tid,
                "elo_rating": r,
                "conference": self.conferences.get(tid, "Unknown"),
                "games_played": 30,
            }
            for tid, r in self.ratings.items()
        ]
        return pd.DataFrame(rows).sort_values("elo_rating", ascending=False)


@pytest.fixture
def fake_model():
    return FakeModel()


@pytest.fixture
def metadata():
    return ModelMetadata(
        model_name="test_model",
        sport="ncaab",
        seasons_used=[2023, 2024],
        game_count=5000,
        team_count=3,
    )


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary SQLite database with team_ratings table."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE team_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sport TEXT NOT NULL,
            team_id TEXT NOT NULL,
            team_name TEXT NOT NULL,
            season INTEGER NOT NULL,
            rating_type TEXT NOT NULL,
            rating_value REAL NOT NULL,
            UNIQUE(sport, team_id, season, rating_type)
        )"""
    )
    conn.commit()
    conn.close()
    return db_path


# ============================================================================
# Tests: save_model / load_model
# ============================================================================


class TestSaveLoadModel:
    def test_save_creates_pkl_file(self, tmp_path, fake_model, metadata):
        path = tmp_path / "model.pkl"
        result = save_model(fake_model, path, metadata)
        assert result == path
        assert path.exists()
        assert path.stat().st_size > 0

    def test_save_creates_meta_json(self, tmp_path, fake_model, metadata):
        path = tmp_path / "model.pkl"
        save_model(fake_model, path, metadata)
        meta_path = path.with_suffix(".meta.json")
        assert meta_path.exists()

        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        assert meta["model_name"] == "test_model"
        assert meta["sport"] == "ncaab"
        assert meta["game_count"] == 5000

    def test_round_trip_preserves_model(self, tmp_path, fake_model, metadata):
        path = tmp_path / "model.pkl"
        save_model(fake_model, path, metadata)
        loaded = load_model(path)

        assert isinstance(loaded, SavedModel)
        assert loaded.model.ratings == fake_model.ratings
        assert loaded.metadata.model_name == "test_model"
        assert loaded.metadata.seasons_used == [2023, 2024]

    def test_load_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_model(tmp_path / "nonexistent.pkl")

    def test_load_legacy_model_no_metadata(self, tmp_path):
        """Test loading a raw pickled model without SavedModel wrapper."""
        path = tmp_path / "legacy.pkl"
        with open(path, "wb") as f:
            pickle.dump({"ratings": {"duke": 1600}}, f)

        loaded = load_model(path)
        assert isinstance(loaded, SavedModel)
        assert loaded.metadata.model_name == "unknown"

    def test_save_creates_parent_dirs(self, tmp_path, fake_model, metadata):
        path = tmp_path / "deep" / "nested" / "model.pkl"
        save_model(fake_model, path, metadata)
        assert path.exists()

    def test_metadata_auto_sets_training_date(self):
        meta = ModelMetadata(model_name="test", sport="ncaab")
        assert meta.training_date  # should be non-empty


# ============================================================================
# Tests: export_ratings_csv
# ============================================================================


class TestExportRatingsCSV:
    def test_creates_csv_with_correct_columns(self, tmp_path, fake_model):
        path = tmp_path / "ratings.csv"
        export_ratings_csv(fake_model, path)
        assert path.exists()

        import pandas as pd

        df = pd.read_csv(path)
        assert "rank" in df.columns
        assert "sport" in df.columns
        assert "team_id" in df.columns
        assert "elo_rating" in df.columns

    def test_csv_is_sorted_by_rating(self, tmp_path, fake_model):
        path = tmp_path / "ratings.csv"
        export_ratings_csv(fake_model, path)

        import pandas as pd

        df = pd.read_csv(path)
        ratings = df["elo_rating"].tolist()
        assert ratings == sorted(ratings, reverse=True)

    def test_csv_has_correct_team_count(self, tmp_path, fake_model):
        path = tmp_path / "ratings.csv"
        export_ratings_csv(fake_model, path)

        import pandas as pd

        df = pd.read_csv(path)
        assert len(df) == 3

    def test_export_from_ratings_dict_only(self, tmp_path):
        """Test export when model only has ratings dict (no to_dataframe)."""

        class MinimalModel:
            ratings = {"a": 1600.0, "b": 1500.0}

        path = tmp_path / "ratings.csv"
        export_ratings_csv(MinimalModel(), path)

        import pandas as pd

        df = pd.read_csv(path)
        assert len(df) == 2

    def test_unsupported_model_raises(self, tmp_path):
        with pytest.raises(TypeError):
            export_ratings_csv("not_a_model", tmp_path / "fail.csv")


# ============================================================================
# Tests: export_ratings_db
# ============================================================================


class TestExportRatingsDB:
    def test_inserts_ratings(self, tmp_db, fake_model):
        from tracking.database import BettingDatabase

        db = BettingDatabase(str(tmp_db))
        count = export_ratings_db(fake_model, db, sport="ncaab", season=2025)
        assert count == 3

        rows = db.execute_query("SELECT * FROM team_ratings WHERE sport = 'ncaab'")
        assert len(rows) == 3

    def test_upsert_updates_existing(self, tmp_db, fake_model):
        from tracking.database import BettingDatabase

        db = BettingDatabase(str(tmp_db))
        export_ratings_db(fake_model, db, sport="ncaab", season=2025)

        # Update a rating and re-export
        fake_model.ratings["duke"] = 1700.0
        export_ratings_db(fake_model, db, sport="ncaab", season=2025)

        rows = db.execute_query(
            "SELECT rating_value FROM team_ratings WHERE team_id = 'duke' AND season = 2025"
        )
        assert len(rows) == 1
        assert rows[0]["rating_value"] == 1700.0

    def test_correct_rating_values(self, tmp_db, fake_model):
        from tracking.database import BettingDatabase

        db = BettingDatabase(str(tmp_db))
        export_ratings_db(fake_model, db, sport="ncaab", season=2025)

        for team_id, expected_rating in fake_model.ratings.items():
            rows = db.execute_query(
                "SELECT rating_value FROM team_ratings WHERE team_id = ?",
                (team_id,),
            )
            assert rows[0]["rating_value"] == expected_rating
