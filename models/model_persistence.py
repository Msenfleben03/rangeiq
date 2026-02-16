"""Model Persistence Utilities.

Save, load, and export trained models with metadata tracking.
Supports pickle serialization, CSV export for human review,
and database export for the team_ratings table.
"""

from __future__ import annotations

import json
import logging
import pickle
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ModelMetadata:
    """Metadata attached to a saved model."""

    model_name: str
    sport: str
    training_date: str = ""
    seasons_used: list[int] = field(default_factory=list)
    game_count: int = 0
    team_count: int = 0
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        """Set default training date to current timestamp if not provided."""
        if not self.training_date:
            self.training_date = datetime.now(timezone.utc).isoformat()


@dataclass
class SavedModel:
    """Container for a model and its metadata."""

    model: Any
    metadata: ModelMetadata


def save_model(
    model: Any,
    path: str | Path,
    metadata: ModelMetadata,
) -> Path:
    """Save a model with metadata to disk.

    Args:
        model: The model object (must be picklable).
        path: File path for the .pkl output.
        metadata: Metadata describing the training run.

    Returns:
        Path to the saved file.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = SavedModel(model=model, metadata=metadata)

    with open(path, "wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

    logger.info("Model saved to %s (%d bytes)", path, path.stat().st_size)

    # Save metadata sidecar as JSON for easy inspection
    meta_path = path.with_suffix(".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(asdict(metadata), f, indent=2, default=str)

    return path


def load_model(path: str | Path) -> SavedModel:
    """Load a model and its metadata from disk.

    Args:
        path: Path to the .pkl file.

    Returns:
        SavedModel containing the model and metadata.

    Raises:
        FileNotFoundError: If the model file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Model file not found: {path}")

    with open(path, "rb") as f:
        payload = pickle.load(f)  # noqa: S301  # nosec B301

    if isinstance(payload, SavedModel):
        logger.info(
            "Loaded model '%s' (trained %s, %d games)",
            payload.metadata.model_name,
            payload.metadata.training_date,
            payload.metadata.game_count,
        )
        return payload

    # Backwards compatibility: raw model without metadata wrapper
    logger.warning("Loaded legacy model without metadata from %s", path)
    return SavedModel(
        model=payload,
        metadata=ModelMetadata(model_name="unknown", sport="unknown"),
    )


def export_ratings_csv(
    model: Any,
    path: str | Path,
    sport: str = "ncaab",
) -> Path:
    """Export model ratings to CSV for human review.

    Args:
        model: Model with a to_dataframe() method or ratings dict.
        path: Output CSV path.
        sport: Sport identifier for the export.

    Returns:
        Path to the saved CSV.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if hasattr(model, "to_dataframe"):
        df = model.to_dataframe()
    elif hasattr(model, "ratings"):
        records = [{"team_id": tid, "elo_rating": rating} for tid, rating in model.ratings.items()]
        df = pd.DataFrame(records).sort_values("elo_rating", ascending=False)
    else:
        raise TypeError(f"Model type {type(model)} has no ratings to export")

    df.insert(0, "sport", sport)
    df.insert(0, "rank", range(1, len(df) + 1))
    df.to_csv(path, index=False)
    logger.info("Exported %d team ratings to %s", len(df), path)
    return path


def export_ratings_db(
    model: Any,
    db: Any,
    sport: str,
    season: int,
    rating_type: str = "elo",
) -> int:
    """Insert model ratings into the team_ratings database table.

    Args:
        model: Model with ratings dict and optional conferences dict.
        db: BettingDatabase instance.
        sport: Sport identifier (e.g., 'ncaab').
        season: Season year.
        rating_type: Type of rating (default 'elo').

    Returns:
        Number of ratings inserted/updated.
    """
    from datetime import date as date_type

    count = 0
    today = date_type.today().isoformat()

    with db.get_cursor() as cursor:
        for team_id, rating_value in model.ratings.items():
            cursor.execute(
                """INSERT INTO team_ratings
                    (team_id, sport, season, rating_type, rating_value, as_of_date)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(team_id, season, rating_type, as_of_date)
                DO UPDATE SET
                    rating_value = excluded.rating_value
                """,
                (team_id, sport, season, rating_type, rating_value, today),
            )
            count += 1

    logger.info(
        "Exported %d %s ratings to database (sport=%s, season=%d)",
        count,
        rating_type,
        sport,
        season,
    )
    return count
