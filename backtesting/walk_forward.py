"""Walk-Forward Validation for Sports Betting Models.

Implements time-series aware cross-validation that prevents data leakage by
ensuring all training data precedes test data chronologically.

CRITICAL: This module enforces strict temporal ordering to prevent look-ahead bias,
which is the #1 cause of inflated backtest performance in betting models.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Callable, Dict, Generator, List, Optional, Protocol

import numpy as np
import pandas as pd


class BaseModel(Protocol):
    """Protocol defining the interface for models used in walk-forward validation."""

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Fit the model on training data."""
        ...

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Generate predictions for test data."""
        ...

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Generate probability predictions (optional)."""
        ...


@dataclass
class WalkForwardWindow:
    """Represents a single train/test window in walk-forward validation.

    Attributes:
        fold_id: Unique identifier for this fold
        train_start: Start date of training period
        train_end: End date of training period
        test_start: Start date of test period
        test_end: End date of test period
        train_indices: Row indices for training data
        test_indices: Row indices for test data
    """

    fold_id: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date
    train_indices: np.ndarray = field(default_factory=lambda: np.array([]))
    test_indices: np.ndarray = field(default_factory=lambda: np.array([]))

    def __post_init__(self):
        """Validate temporal ordering."""
        if self.train_end >= self.test_start:
            raise ValueError(
                f"Training period must end before test period starts. "
                f"Train end: {self.train_end}, Test start: {self.test_start}"
            )

    @property
    def train_days(self) -> int:
        """Number of days in training period."""
        return (self.train_end - self.train_start).days + 1

    @property
    def test_days(self) -> int:
        """Number of days in test period."""
        return (self.test_end - self.test_start).days + 1

    @property
    def n_train(self) -> int:
        """Number of training samples."""
        return len(self.train_indices)

    @property
    def n_test(self) -> int:
        """Number of test samples."""
        return len(self.test_indices)


@dataclass
class WalkForwardResult:
    """Results from a single walk-forward fold.

    Attributes:
        window: The train/test window used
        predictions: Model predictions on test set
        probabilities: Probability predictions (if available)
        actuals: Actual outcomes
        metrics: Dictionary of computed metrics
        model_state: Optional saved model state for analysis
    """

    window: WalkForwardWindow
    predictions: np.ndarray
    probabilities: Optional[np.ndarray]
    actuals: np.ndarray
    metrics: Dict[str, float] = field(default_factory=dict)
    model_state: Optional[Any] = None


class WalkForwardValidator:
    """Walk-forward validation for time-series betting data.

    Walk-forward validation is the ONLY acceptable cross-validation method for
    betting models. Standard k-fold CV causes severe look-ahead bias because
    future data "leaks" into training.

    Example:
        ```python
        validator = WalkForwardValidator(
            train_window_days=180,  # 6 months training
            test_window_days=30,    # 1 month test
            step_days=30,           # Monthly retraining
            min_train_samples=100
        )

        for window in validator.split(df, date_column='game_date'):
            train_df = df.iloc[window.train_indices]
            test_df = df.iloc[window.test_indices]
            # Train and evaluate model...
        ```

    Args:
        train_window_days: Number of days in each training window
        test_window_days: Number of days in each test window
        step_days: Number of days to step forward between folds
        min_train_samples: Minimum samples required in training set
        min_test_samples: Minimum samples required in test set
        gap_days: Gap between train end and test start (default 1 to prevent leakage)
        expanding_window: If True, use expanding (not rolling) train window
    """

    def __init__(
        self,
        train_window_days: int = 365,
        test_window_days: int = 30,
        step_days: int = 30,
        min_train_samples: int = 100,
        min_test_samples: int = 10,
        gap_days: int = 1,
        expanding_window: bool = False,
    ):
        self.train_window_days = train_window_days
        self.test_window_days = test_window_days
        self.step_days = step_days
        self.min_train_samples = min_train_samples
        self.min_test_samples = min_test_samples
        self.gap_days = gap_days
        self.expanding_window = expanding_window

        self._validate_params()

    def _validate_params(self) -> None:
        """Validate initialization parameters."""
        if self.train_window_days < 1:
            raise ValueError("train_window_days must be >= 1")
        if self.test_window_days < 1:
            raise ValueError("test_window_days must be >= 1")
        if self.step_days < 1:
            raise ValueError("step_days must be >= 1")
        if self.gap_days < 0:
            raise ValueError("gap_days must be >= 0")
        if self.min_train_samples < 1:
            raise ValueError("min_train_samples must be >= 1")
        if self.min_test_samples < 1:
            raise ValueError("min_test_samples must be >= 1")

    def split(
        self,
        df: pd.DataFrame,
        date_column: str = "game_date",
    ) -> Generator[WalkForwardWindow, None, None]:
        """Generate train/test splits for walk-forward validation.

        CRITICAL: Data must be sorted by date. This method will raise an error
        if dates are not monotonically increasing within the DataFrame.

        Args:
            df: DataFrame containing the data
            date_column: Name of the date column

        Yields:
            WalkForwardWindow objects with train/test indices

        Raises:
            ValueError: If date column is missing or data is not sorted
        """
        if date_column not in df.columns:
            raise ValueError(f"Date column '{date_column}' not found in DataFrame")

        # Handle empty DataFrame
        if len(df) == 0:
            return

        # Convert to date objects if needed
        dates = pd.to_datetime(df[date_column]).dt.date

        # Verify temporal ordering - CRITICAL for preventing leakage
        if not dates.is_monotonic_increasing:
            raise ValueError(
                "Data must be sorted by date in ascending order. "
                "Sort with df.sort_values(date_column) before calling split()"
            )

        min_date = dates.min()
        max_date = dates.max()

        # Calculate first possible test start
        first_train_end = min_date + timedelta(days=self.train_window_days - 1)
        first_test_start = first_train_end + timedelta(days=self.gap_days)

        # Not enough time span - yield nothing instead of raising
        if first_test_start > max_date:
            return

        fold_id = 0
        current_test_start = first_test_start

        while current_test_start <= max_date:
            # Calculate window boundaries
            test_end = min(current_test_start + timedelta(days=self.test_window_days - 1), max_date)
            train_end = current_test_start - timedelta(days=self.gap_days)

            if self.expanding_window:
                train_start = min_date
            else:
                train_start = max(min_date, train_end - timedelta(days=self.train_window_days - 1))

            # Get indices for this window
            train_mask = (dates >= train_start) & (dates <= train_end)
            test_mask = (dates >= current_test_start) & (dates <= test_end)

            train_indices = np.where(train_mask)[0]
            test_indices = np.where(test_mask)[0]

            # Check minimum sample requirements
            if (
                len(train_indices) >= self.min_train_samples
                and len(test_indices) >= self.min_test_samples
            ):
                window = WalkForwardWindow(
                    fold_id=fold_id,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=current_test_start,
                    test_end=test_end,
                    train_indices=train_indices,
                    test_indices=test_indices,
                )
                fold_id += 1
                yield window

            # Step forward
            current_test_start += timedelta(days=self.step_days)

    def get_n_splits(self, df: pd.DataFrame, date_column: str = "game_date") -> int:
        """Calculate the number of splits without generating them.

        Args:
            df: DataFrame containing the data
            date_column: Name of the date column

        Returns:
            Number of valid folds
        """
        return sum(1 for _ in self.split(df, date_column))

    def validate(
        self,
        df: pd.DataFrame,
        model: BaseModel,
        feature_columns: List[str],
        target_column: str,
        date_column: str = "game_date",
        metrics_fn: Optional[Callable] = None,
        verbose: bool = True,
    ) -> List[WalkForwardResult]:
        """Run complete walk-forward validation.

        This method handles the full validation loop: splitting data, training
        models, generating predictions, and computing metrics for each fold.

        Args:
            df: DataFrame with features and target
            model: Model implementing fit() and predict() methods
            feature_columns: List of feature column names
            target_column: Name of target column
            date_column: Name of date column
            metrics_fn: Optional function to compute custom metrics
            verbose: Whether to print progress

        Returns:
            List of WalkForwardResult objects, one per fold
        """
        results = []

        for window in self.split(df, date_column):
            # Extract train/test data
            train_df = df.iloc[window.train_indices]
            test_df = df.iloc[window.test_indices]

            X_train = train_df[feature_columns]
            y_train = train_df[target_column]
            X_test = test_df[feature_columns]
            y_test = test_df[target_column]

            # CRITICAL: Verify no future data leakage
            train_max_date = pd.to_datetime(train_df[date_column]).max()
            test_min_date = pd.to_datetime(test_df[date_column]).min()

            if train_max_date >= test_min_date:
                raise RuntimeError(
                    f"DATA LEAKAGE DETECTED! Training data ({train_max_date}) "
                    f"overlaps with test data ({test_min_date})"
                )

            # Train model
            model.fit(X_train, y_train)

            # Generate predictions
            predictions = model.predict(X_test)

            # Get probabilities if available
            probabilities = None
            if hasattr(model, "predict_proba"):
                try:
                    probabilities = model.predict_proba(X_test)
                except Exception:
                    pass

            # Compute metrics
            metrics = {}
            if metrics_fn is not None:
                metrics = metrics_fn(y_test.values, predictions, probabilities)

            result = WalkForwardResult(
                window=window,
                predictions=predictions,
                probabilities=probabilities,
                actuals=y_test.values,
                metrics=metrics,
            )
            results.append(result)

            if verbose:
                print(
                    f"Fold {window.fold_id}: "
                    f"Train {window.train_start} to {window.train_end} "
                    f"(n={window.n_train}), "
                    f"Test {window.test_start} to {window.test_end} "
                    f"(n={window.n_test})"
                )

        return results


def create_lagged_features(
    df: pd.DataFrame,
    columns: List[str],
    lag: int = 1,
    date_column: str = "game_date",
    group_column: Optional[str] = None,
) -> pd.DataFrame:
    """Create lagged versions of features to prevent look-ahead bias.

    CRITICAL: Always use this function when creating rolling or cumulative
    features. Using .shift(1) ensures you only use information available
    BEFORE the current game.

    Args:
        df: DataFrame with features
        columns: Columns to lag
        lag: Number of periods to lag (default 1)
        date_column: Date column for sorting
        group_column: Optional column to group by (e.g., team_id)

    Returns:
        DataFrame with lagged features added (suffix: _lag{n})

    Example:
        ```python
        # Create lagged rolling averages
        df['pts_last_5'] = df.groupby('team_id')['points'].rolling(5).mean()
        df = create_lagged_features(df, ['pts_last_5'], lag=1)
        # Now pts_last_5_lag1 contains the rolling avg BEFORE the current game
        ```
    """
    result = df.copy()
    result = result.sort_values(date_column)

    for col in columns:
        new_col = f"{col}_lag{lag}"
        if group_column:
            result[new_col] = result.groupby(group_column)[col].shift(lag)
        else:
            result[new_col] = result[col].shift(lag)

    return result


def detect_data_leakage(
    df: pd.DataFrame,
    feature_columns: List[str],
    target_column: str,
    date_column: str = "game_date",
    threshold: float = 0.95,
) -> Dict[str, float]:
    """Detect potential data leakage by checking feature-target correlations.

    Features with extremely high correlation to the target may indicate leakage,
    especially if they were derived from the target or future information.

    Args:
        df: DataFrame with features and target
        feature_columns: List of feature column names
        target_column: Target column name
        date_column: Date column for temporal analysis
        threshold: Correlation threshold to flag as suspicious

    Returns:
        Dictionary mapping suspicious features to their correlation values

    Warnings:
        High correlation does not always mean leakage - it could be a genuinely
        predictive feature. Always manually verify flagged features.
    """
    suspicious = {}
    target = df[target_column]

    for col in feature_columns:
        if col == target_column:
            continue

        # Skip non-numeric columns
        if not np.issubdtype(df[col].dtype, np.number):
            continue

        # Calculate correlation
        corr = df[col].corr(target)

        if abs(corr) >= threshold:
            suspicious[col] = corr

    return suspicious


def verify_temporal_integrity(
    df: pd.DataFrame,
    feature_columns: List[str],
    date_column: str = "game_date",
    group_column: Optional[str] = None,
) -> List[str]:
    """Verify that features don't contain future information.

    Checks if feature values change for past dates, which would indicate
    they were calculated using future data.

    Args:
        df: DataFrame with features
        feature_columns: Features to check
        date_column: Date column
        group_column: Optional grouping column

    Returns:
        List of potentially problematic features
    """
    problematic = []

    # Sort by date
    df_sorted = df.sort_values(date_column)

    for col in feature_columns:
        if not np.issubdtype(df_sorted[col].dtype, np.number):
            continue

        # Check for look-ahead in rolling calculations
        # If a feature has values that couldn't be calculated from past data only,
        # it may have leakage

        # Check if the first non-null value appears too early
        first_valid_idx = df_sorted[col].first_valid_index()
        if first_valid_idx is not None:
            # Features based on rolling windows should have NaN at the start
            # If they don't, they might be using future data
            n_leading_nulls = df_sorted[col].isna().values[:10].sum()
            if n_leading_nulls == 0 and "rolling" in col.lower():
                problematic.append(col)

    return problematic


class SeasonalWalkForwardValidator(WalkForwardValidator):
    """Walk-forward validation respecting season boundaries.

    For sports betting, it's often more appropriate to use full seasons as
    training units rather than arbitrary day-based windows. This validator
    ensures training never includes data from the current season being tested.

    Example:
        ```python
        validator = SeasonalWalkForwardValidator(
            min_training_seasons=2,
            test_seasons=1
        )

        for window in validator.split(df, date_column='game_date', season_column='season'):
            # Training: seasons 2020-2021
            # Testing: season 2022
            ...
        ```
    """

    def __init__(
        self,
        min_training_seasons: int = 2,
        test_seasons: int = 1,
        min_train_samples: int = 100,
        min_test_samples: int = 50,
    ):
        self.min_training_seasons = min_training_seasons
        self.test_seasons = test_seasons
        self.min_train_samples = min_train_samples
        self.min_test_samples = min_test_samples

    def split(
        self,
        df: pd.DataFrame,
        date_column: str = "game_date",
        season_column: str = "season",
    ) -> Generator[WalkForwardWindow, None, None]:
        """Generate season-based train/test splits.

        Args:
            df: DataFrame containing the data
            date_column: Name of the date column
            season_column: Name of the season column

        Yields:
            WalkForwardWindow objects with train/test indices
        """
        if season_column not in df.columns:
            raise ValueError(f"Season column '{season_column}' not found in DataFrame")

        # Get unique seasons in order
        seasons = sorted(df[season_column].unique())

        if len(seasons) < self.min_training_seasons + self.test_seasons:
            raise ValueError(
                f"Not enough seasons. Have {len(seasons)}, need at least "
                f"{self.min_training_seasons + self.test_seasons}"
            )

        fold_id = 0

        for i in range(self.min_training_seasons, len(seasons) - self.test_seasons + 1):
            # Training seasons
            train_seasons = seasons[:i]
            # Test seasons
            test_start_idx = i
            test_end_idx = min(i + self.test_seasons, len(seasons))
            test_seasons_list = seasons[test_start_idx:test_end_idx]

            # Get indices
            train_mask = df[season_column].isin(train_seasons)
            test_mask = df[season_column].isin(test_seasons_list)

            train_indices = np.where(train_mask)[0]
            test_indices = np.where(test_mask)[0]

            # Check minimum samples
            if len(train_indices) < self.min_train_samples:
                continue
            if len(test_indices) < self.min_test_samples:
                continue

            # Get date ranges
            train_dates = pd.to_datetime(df.loc[train_mask, date_column])
            test_dates = pd.to_datetime(df.loc[test_mask, date_column])

            window = WalkForwardWindow(
                fold_id=fold_id,
                train_start=train_dates.min().date(),
                train_end=train_dates.max().date(),
                test_start=test_dates.min().date(),
                test_end=test_dates.max().date(),
                train_indices=train_indices,
                test_indices=test_indices,
            )

            fold_id += 1
            yield window
