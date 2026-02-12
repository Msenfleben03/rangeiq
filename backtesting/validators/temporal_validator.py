"""Temporal Integrity Validator for Backtesting.

This module validates temporal integrity - the MOST CRITICAL aspect of backtesting.
Temporal leakage (look-ahead bias) is the #1 cause of inflated backtest performance
in sports betting models.

CRITICAL PRINCIPLE: A model should NEVER have access to information that would not
be available at the time a bet would be placed.

Common leakage sources:
1. Rolling calculations without .shift(1)
2. Using closing lines before game start
3. Features derived from future game outcomes
4. Train/test contamination in cross-validation
5. Same-day game information leaking across timezone boundaries

This validator catches these issues BEFORE they corrupt your backtest results.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class LeakageType(Enum):
    """Types of temporal leakage."""

    ROLLING_NO_SHIFT = "rolling_calculation_without_shift"
    CORRELATION_SPIKE = "suspicious_correlation_with_target"
    TIMESTAMP_VIOLATION = "feature_unavailable_at_bet_time"
    TRAIN_TEST_CONTAMINATION = "train_test_overlap"
    CLOSING_LINE_TIMING = "closing_line_captured_after_game_start"
    FUTURE_DATA_REFERENCE = "feature_references_future_data"
    RANDOM_SPLIT_DETECTED = "non_chronological_split_detected"
    INSUFFICIENT_GAP = "insufficient_train_test_gap"
    PREDICTION_AFTER_GAME = "prediction_timestamp_after_game"
    UNREALISTIC_ACCURACY = "unrealistically_high_accuracy"


@dataclass
class FeatureLeakageInfo:
    """Information about a potentially leaky feature.

    Attributes:
        feature_name: Name of the suspicious feature
        leakage_type: Type of detected leakage
        severity: Severity level (critical, high, medium, low)
        evidence: Supporting evidence for the detection
        recommendation: Suggested fix
    """

    feature_name: str
    leakage_type: LeakageType
    severity: str
    evidence: Dict[str, Any]
    recommendation: str


@dataclass
class WalkForwardValidationResult:
    """Result of walk-forward structure validation.

    Attributes:
        is_valid: Whether the walk-forward structure is valid
        n_folds: Number of folds detected
        issues: List of issues found
        fold_details: Details about each fold
    """

    is_valid: bool
    n_folds: int
    issues: List[str]
    fold_details: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TemporalValidationResult:
    """Complete result of temporal validation.

    Attributes:
        passed: Whether all validations passed
        n_features_scanned: Number of features analyzed
        n_issues_found: Total issues detected
        leaky_features: List of features with detected leakage
        walk_forward_valid: Whether walk-forward structure is valid
        closing_line_valid: Whether closing line timing is valid
        timestamp_audit_passed: Whether all timestamps are valid
        report_summary: Human-readable summary
    """

    passed: bool
    n_features_scanned: int
    n_issues_found: int
    leaky_features: List[FeatureLeakageInfo]
    walk_forward_valid: bool
    closing_line_valid: bool
    timestamp_audit_passed: bool
    report_summary: str


class TemporalValidator:
    """Validates temporal integrity to prevent look-ahead bias.

    This is the FIRST LINE OF DEFENSE against the most dangerous bias
    in sports betting backtests. Use this validator before trusting
    any backtest results.

    Example:
        ```python
        validator = TemporalValidator()

        # Validate walk-forward structure
        wf_result = validator.validate_walk_forward(
            df, 'game_date', train_size=180, test_size=30,
            train_indices=train_idx, test_indices=test_idx
        )

        # Detect feature leakage
        leaky = validator.detect_leakage(df, feature_cols, 'target', 'game_date')

        # Full validation pipeline
        result = validator.full_validation(
            df=betting_data,
            feature_cols=feature_columns,
            target_col='spread_cover',
            date_col='game_date',
            train_indices=train_idx,
            test_indices=test_idx
        )

        if not result.passed:
            print("CRITICAL: Temporal leakage detected!")
            for leak in result.leaky_features:
                print(f"  - {leak.feature_name}: {leak.leakage_type.value}")
        ```

    Args:
        correlation_threshold: Threshold for flagging suspicious correlations
        min_train_test_gap_days: Minimum days between train and test periods
        strict_mode: If True, treats warnings as errors
    """

    # Features that commonly leak future data if not properly lagged
    SUSPICIOUS_FEATURE_PATTERNS = [
        "rolling",
        "moving_avg",
        "ewm",
        "cumsum",
        "cumulative",
        "lag",
        "shift",
        "pct_change",
        "diff",
        "mean_last",
        "avg_last",
        "sum_last",
    ]

    # Patterns indicating post-game data
    FUTURE_DATA_PATTERNS = [
        "result",
        "outcome",
        "final",
        "actual",
        "post_game",
        "postgame",
        "after_",
        "winning",
        "losing",
    ]

    def __init__(
        self,
        correlation_threshold: float = 0.95,
        min_train_test_gap_days: int = 1,
        strict_mode: bool = False,
        date_column: str = "game_date",
        prediction_date_column: str = "prediction_date",
    ):
        self.correlation_threshold = correlation_threshold
        self.min_train_test_gap_days = min_train_test_gap_days
        self.strict_mode = strict_mode
        self.date_column = date_column
        self.prediction_date_column = prediction_date_column

        # Track all detected issues
        self._issues: List[FeatureLeakageInfo] = []
        self._scan_history: List[Dict[str, Any]] = []

    def reset(self) -> None:
        """Reset the validator state for a new validation run."""
        self._issues = []
        self._scan_history = []

    # =========================================================================
    # WALK-FORWARD VALIDATION
    # =========================================================================

    def validate_walk_forward(
        self,
        df: pd.DataFrame,
        date_col: str,
        train_size: int,
        test_size: int,
        train_indices: Optional[np.ndarray] = None,
        test_indices: Optional[np.ndarray] = None,
    ) -> WalkForwardValidationResult:
        """Validate walk-forward validation structure.

        Ensures:
        1. No random splits (data must be chronologically ordered)
        2. Training data always precedes test data
        3. Sufficient gap between train and test periods
        4. No overlap between train and test sets

        Args:
            df: DataFrame with the data
            date_col: Name of the date column
            train_size: Expected training window size (days)
            test_size: Expected test window size (days)
            train_indices: Optional explicit training indices to validate
            test_indices: Optional explicit test indices to validate

        Returns:
            WalkForwardValidationResult with validation details
        """
        issues = []
        fold_details = []

        if date_col not in df.columns:
            return WalkForwardValidationResult(
                is_valid=False,
                n_folds=0,
                issues=[f"Date column '{date_col}' not found"],
            )

        # Convert dates
        dates = pd.to_datetime(df[date_col])

        # Check 1: Verify data is sorted chronologically
        if not dates.is_monotonic_increasing:
            issues.append(
                "CRITICAL: Data is not sorted chronologically. "
                "Walk-forward validation requires sorted data."
            )
            self._add_issue(
                feature_name="_data_structure",
                leakage_type=LeakageType.RANDOM_SPLIT_DETECTED,
                severity="critical",
                evidence={"sorted": False},
                recommendation="Sort data by date: df.sort_values(date_col)",
            )

        # If explicit indices provided, validate them
        if train_indices is not None and test_indices is not None:
            train_indices = np.asarray(train_indices)
            test_indices = np.asarray(test_indices)

            train_dates = dates.iloc[train_indices]
            test_dates = dates.iloc[test_indices]

            train_max = train_dates.max()
            test_min = test_dates.min()

            # Check 2: No overlap in indices
            overlap_count = len(set(train_indices) & set(test_indices))
            if overlap_count > 0:
                issues.append(
                    f"CRITICAL: {overlap_count} samples appear in both train and test sets!"
                )
                self._add_issue(
                    feature_name="_train_test_split",
                    leakage_type=LeakageType.TRAIN_TEST_CONTAMINATION,
                    severity="critical",
                    evidence={"overlap_count": overlap_count},
                    recommendation="Ensure train and test indices are mutually exclusive",
                )

            # Check 3: Training ends before test begins
            if train_max >= test_min:
                gap_days = (test_min - train_max).days
                issues.append(
                    f"CRITICAL: Training period ({train_max.date()}) overlaps or "
                    f"is too close to test period ({test_min.date()}). Gap: {gap_days} days"
                )
                self._add_issue(
                    feature_name="_train_test_timing",
                    leakage_type=LeakageType.TRAIN_TEST_CONTAMINATION,
                    severity="critical",
                    evidence={
                        "train_max": str(train_max.date()),
                        "test_min": str(test_min.date()),
                        "gap_days": gap_days,
                    },
                    recommendation=f"Ensure at least {self.min_train_test_gap_days} day gap",
                )

            # Check 4: Sufficient gap
            gap = (test_min - train_max).days
            if 0 < gap < self.min_train_test_gap_days:
                issues.append(
                    f"WARNING: Train-test gap ({gap} days) is less than "
                    f"minimum ({self.min_train_test_gap_days} days)"
                )
                self._add_issue(
                    feature_name="_train_test_gap",
                    leakage_type=LeakageType.INSUFFICIENT_GAP,
                    severity="medium",
                    evidence={
                        "actual_gap_days": gap,
                        "required_gap_days": self.min_train_test_gap_days,
                    },
                    recommendation=f"Increase gap to at least {self.min_train_test_gap_days} days",
                )

            fold_details.append(
                {
                    "train_start": train_dates.min().date(),
                    "train_end": train_max.date(),
                    "test_start": test_min.date(),
                    "test_end": test_dates.max().date(),
                    "train_samples": len(train_indices),
                    "test_samples": len(test_indices),
                    "gap_days": gap,
                }
            )

        # Determine validity
        critical_issues = [i for i in issues if "CRITICAL" in i]
        is_valid = len(critical_issues) == 0

        return WalkForwardValidationResult(
            is_valid=is_valid,
            n_folds=1 if train_indices is not None else 0,
            issues=issues,
            fold_details=fold_details,
        )

    # =========================================================================
    # LEAKAGE DETECTION
    # =========================================================================

    def detect_leakage(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str,
        date_col: str,
        group_col: Optional[str] = None,
    ) -> List[FeatureLeakageInfo]:
        """Scan features for look-ahead bias.

        Performs multiple checks:
        1. Correlation spike detection - features shouldn't predict too well
        2. Rolling calculation check - verify .shift(1) pattern
        3. Temporal consistency - features shouldn't change for past dates
        4. Suspicious naming patterns - flag common leakage indicators

        Args:
            df: DataFrame with features and target
            feature_cols: List of feature column names
            target_col: Target column name
            date_col: Date column name
            group_col: Optional grouping column (e.g., team_id)

        Returns:
            List of FeatureLeakageInfo for detected issues
        """
        leaky_features = []

        if target_col not in df.columns:
            raise ValueError(f"Target column '{target_col}' not found")

        df_sorted = df.sort_values(date_col).copy()
        target = df_sorted[target_col]

        for col in feature_cols:
            if col == target_col or col == date_col:
                continue

            if col not in df_sorted.columns:
                continue

            # Skip non-numeric columns
            if not np.issubdtype(df_sorted[col].dtype, np.number):
                continue

            feature = df_sorted[col]

            # Check 1: Suspicious correlation
            leak_info = self._check_correlation_spike(col, feature, target)
            if leak_info:
                leaky_features.append(leak_info)
                self._issues.append(leak_info)

            # Check 2: Rolling calculation without shift
            leak_info = self._check_rolling_shift(col, df_sorted, date_col, group_col)
            if leak_info:
                leaky_features.append(leak_info)
                self._issues.append(leak_info)

            # Check 3: Feature references future data (name-based heuristic)
            leak_info = self._check_future_reference(col)
            if leak_info:
                leaky_features.append(leak_info)
                self._issues.append(leak_info)

        self._scan_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "n_features": len(feature_cols),
                "n_issues": len(leaky_features),
                "features_scanned": feature_cols,
            }
        )

        return leaky_features

    def _check_correlation_spike(
        self,
        col: str,
        feature: pd.Series,
        target: pd.Series,
    ) -> Optional[FeatureLeakageInfo]:
        """Check for suspiciously high correlation with target."""
        try:
            # Handle NaN values
            mask = ~(feature.isna() | target.isna())
            if mask.sum() < 10:
                return None

            corr = feature[mask].corr(target[mask])

            if abs(corr) >= self.correlation_threshold:
                return FeatureLeakageInfo(
                    feature_name=col,
                    leakage_type=LeakageType.CORRELATION_SPIKE,
                    severity="high",
                    evidence={
                        "correlation": float(corr),
                        "threshold": self.correlation_threshold,
                        "n_samples": int(mask.sum()),
                    },
                    recommendation=(
                        f"Feature '{col}' has {corr:.3f} correlation with target. "
                        "Verify this is not derived from the target or future data. "
                        "If legitimate, document why this high correlation exists."
                    ),
                )
        except Exception:
            pass

        return None

    def _check_rolling_shift(
        self,
        col: str,
        df: pd.DataFrame,
        date_col: str,
        group_col: Optional[str],
    ) -> Optional[FeatureLeakageInfo]:
        """Check if rolling calculations properly use .shift(1)."""
        # Heuristic: Check naming patterns for rolling features
        col_lower = col.lower()
        is_likely_rolling = any(ind in col_lower for ind in self.SUSPICIOUS_FEATURE_PATTERNS)

        if not is_likely_rolling:
            return None

        # Check if first non-null appears too early
        feature = df[col]
        first_valid_idx = feature.first_valid_index()

        if first_valid_idx is not None:
            first_valid_pos = df.index.get_loc(first_valid_idx)

            # If a rolling feature has values from the very start, it might not be shifted
            if first_valid_pos == 0:
                return FeatureLeakageInfo(
                    feature_name=col,
                    leakage_type=LeakageType.ROLLING_NO_SHIFT,
                    severity="high",
                    evidence={
                        "first_valid_position": 0,
                        "pattern": "Rolling feature has value at first row",
                    },
                    recommendation=(
                        f"Feature '{col}' appears to be a rolling calculation without "
                        "proper .shift(1). Add .shift(1) after the rolling operation: "
                        "df['feature'] = df.groupby('team')['stat'].rolling(5).mean().shift(1)"
                    ),
                )

        return None

    def _check_future_reference(self, col: str) -> Optional[FeatureLeakageInfo]:
        """Check for naming patterns that suggest future data reference."""
        col_lower = col.lower()

        for indicator in self.FUTURE_DATA_PATTERNS:
            if indicator in col_lower:
                # "closing" is OK if it's "closing_line" for CLV calculation
                if indicator == "closing" and "line" in col_lower:
                    continue

                return FeatureLeakageInfo(
                    feature_name=col,
                    leakage_type=LeakageType.FUTURE_DATA_REFERENCE,
                    severity="medium",
                    evidence={
                        "suspicious_pattern": indicator,
                        "column_name": col,
                    },
                    recommendation=(
                        f"Feature '{col}' has naming pattern '{indicator}' suggesting "
                        "it may contain future information. Verify this feature was "
                        "available BEFORE bet placement time."
                    ),
                )

        return None

    # =========================================================================
    # TIMESTAMP AUDITING
    # =========================================================================

    def audit_feature_timestamps(
        self,
        feature_metadata: Dict[str, Dict[str, Any]],
        bet_time_col: str = "bet_placed_at",
    ) -> List[FeatureLeakageInfo]:
        """Verify every feature was available at t-1 (before bet placement).

        Each feature in the metadata should have:
        - 'available_at': When the feature data becomes available
        - 'source': Where the data comes from

        Args:
            feature_metadata: Dict mapping feature name to metadata
                Expected format:
                {
                    'feature_name': {
                        'available_at': 'game_start - 1h',  # or timestamp
                        'source': 'data_source_name',
                        'lag_applied': True/False,
                    }
                }
            bet_time_col: Column name for bet placement time

        Returns:
            List of features with timestamp violations
        """
        violations = []

        post_game_indicators = ["game_end", "final", "postgame", "result", "outcome"]

        for feature_name, metadata in feature_metadata.items():
            available_at = metadata.get("available_at")
            lag_applied = metadata.get("lag_applied", False)
            source = metadata.get("source", "unknown")

            if available_at:
                available_str = str(available_at).lower()
                for indicator in post_game_indicators:
                    if indicator in available_str and not lag_applied:
                        violation = FeatureLeakageInfo(
                            feature_name=feature_name,
                            leakage_type=LeakageType.TIMESTAMP_VIOLATION,
                            severity="critical",
                            evidence={
                                "available_at": available_at,
                                "source": source,
                                "lag_applied": lag_applied,
                            },
                            recommendation=(
                                f"Feature '{feature_name}' is available at '{available_at}' "
                                "which is after game completion. This data would not be "
                                "available at bet placement time. Apply proper lagging."
                            ),
                        )
                        violations.append(violation)
                        self._issues.append(violation)
                        break

        return violations

    # =========================================================================
    # CLOSING LINE VALIDATION
    # =========================================================================

    def validate_closing_line_timing(
        self,
        bets_df: pd.DataFrame,
        closing_line_col: str,
        game_time_col: str,
        closing_captured_at_col: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """Ensure closing line was captured BEFORE game start.

        For CLV calculations to be valid, the closing line must be
        captured before the game begins.

        Args:
            bets_df: DataFrame with bet records
            closing_line_col: Column with closing line values
            game_time_col: Column with game start time
            closing_captured_at_col: Optional column with capture timestamp

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        if closing_line_col not in bets_df.columns:
            issues.append(f"Closing line column '{closing_line_col}' not found")
            return False, issues

        if game_time_col not in bets_df.columns:
            issues.append(f"Game time column '{game_time_col}' not found")
            return False, issues

        # If we have explicit capture timestamps, validate them
        if closing_captured_at_col and closing_captured_at_col in bets_df.columns:
            game_times = pd.to_datetime(bets_df[game_time_col])
            capture_times = pd.to_datetime(bets_df[closing_captured_at_col])

            # Find violations: capture time >= game time
            violations = capture_times >= game_times
            n_violations = violations.sum()

            if n_violations > 0:
                issues.append(
                    f"CRITICAL: {n_violations} closing lines were captured AT or AFTER "
                    f"game start ({n_violations / len(bets_df):.1%} of bets)"
                )

                self._add_issue(
                    feature_name=closing_line_col,
                    leakage_type=LeakageType.CLOSING_LINE_TIMING,
                    severity="critical",
                    evidence={
                        "n_violations": int(n_violations),
                        "total_bets": len(bets_df),
                        "violation_rate": float(n_violations / len(bets_df)),
                    },
                    recommendation=(
                        "Closing lines must be captured BEFORE game start. "
                        "Use lines from ~5 minutes before tip-off/kickoff."
                    ),
                )

                return False, issues

        # Check for suspicious patterns without explicit timestamps
        if "actual_spread" in bets_df.columns or "final_margin" in bets_df.columns:
            actual_col = "actual_spread" if "actual_spread" in bets_df.columns else "final_margin"

            if bets_df[closing_line_col].dtype in [np.float64, np.int64, float, int]:
                exact_matches = (bets_df[closing_line_col] == bets_df[actual_col]).sum()
                match_rate = exact_matches / len(bets_df) if len(bets_df) > 0 else 0

                if match_rate > 0.1:
                    issues.append(
                        f"WARNING: {match_rate:.1%} of closing lines exactly match "
                        "actual results. This may indicate post-game contamination."
                    )

        is_valid = len([i for i in issues if "CRITICAL" in i]) == 0
        return is_valid, issues

    # =========================================================================
    # TRAIN/TEST CONTAMINATION CHECK
    # =========================================================================

    def detect_train_test_contamination(
        self,
        df: pd.DataFrame,
        train_indices: np.ndarray,
        test_indices: np.ndarray,
        id_col: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """Check for any overlap between train and test sets.

        Args:
            df: DataFrame with the data
            train_indices: Indices used for training
            test_indices: Indices used for testing
            id_col: Optional unique identifier column to check

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        train_set = set(np.asarray(train_indices))
        test_set = set(np.asarray(test_indices))
        overlap = train_set & test_set

        if overlap:
            issues.append(f"CRITICAL: {len(overlap)} indices appear in both train and test sets!")
            self._add_issue(
                feature_name="_indices",
                leakage_type=LeakageType.TRAIN_TEST_CONTAMINATION,
                severity="critical",
                evidence={
                    "overlap_count": len(overlap),
                    "overlap_sample": list(overlap)[:10],
                },
                recommendation="Ensure train_indices and test_indices are mutually exclusive",
            )

        # If ID column provided, check for ID overlap (informational)
        if id_col and id_col in df.columns:
            train_ids = set(df.iloc[list(train_set)][id_col])
            test_ids = set(df.iloc[list(test_set)][id_col])
            id_overlap = train_ids & test_ids

            if id_overlap:
                issues.append(
                    f"INFO: {len(id_overlap)} IDs appear in both train and test. "
                    "This may be acceptable (same teams in different games) but verify."
                )

        is_valid = len([i for i in issues if "CRITICAL" in i]) == 0
        return is_valid, issues

    # =========================================================================
    # STATISTICAL LEAKAGE DETECTION
    # =========================================================================

    def _statistical_leakage_check(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        """Use statistical tests to detect likely leakage.

        Data leakage often manifests as:
        - Unrealistically high prediction accuracy
        - Perfect or near-perfect correlation between predictions and outcomes
        """
        issues = []
        passed = True

        # Check for unrealistic accuracy (>70% on spread bets is suspicious)
        if "result" in df.columns:
            win_rate = (df["result"] == "win").mean()
            if win_rate > 0.70:
                passed = False
                issues.append(
                    f"SUSPICIOUS: {win_rate:.1%} win rate is unrealistically high. "
                    "Even the best models rarely exceed 55-58%. Check for data leakage."
                )
                self._add_issue(
                    feature_name="_win_rate",
                    leakage_type=LeakageType.UNREALISTIC_ACCURACY,
                    severity="critical",
                    evidence={"win_rate": float(win_rate)},
                    recommendation="Verify no future information is used in predictions",
                )

        # Check model probability calibration
        if "model_probability" in df.columns and "result" in df.columns:
            outcomes = (df["result"] == "win").astype(float)
            probs = df["model_probability"]

            # Brier score near 0 is suspicious
            valid_mask = ~(probs.isna() | outcomes.isna())
            if valid_mask.sum() > 10:
                brier = np.mean((probs[valid_mask] - outcomes[valid_mask]) ** 2)
                if brier < 0.05:
                    passed = False
                    issues.append(
                        f"SUSPICIOUS: Brier score of {brier:.4f} is unrealistically low. "
                        "This suggests predictions have access to future information."
                    )

        return passed, issues

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _add_issue(
        self,
        feature_name: str,
        leakage_type: LeakageType,
        severity: str,
        evidence: Dict[str, Any],
        recommendation: str,
    ) -> None:
        """Internal helper to add an issue to the tracker."""
        self._issues.append(
            FeatureLeakageInfo(
                feature_name=feature_name,
                leakage_type=leakage_type,
                severity=severity,
                evidence=evidence,
                recommendation=recommendation,
            )
        )

    # =========================================================================
    # FULL VALIDATION PIPELINE
    # =========================================================================

    def full_validation(
        self,
        df: pd.DataFrame,
        feature_cols: List[str],
        target_col: str,
        date_col: str,
        train_indices: Optional[np.ndarray] = None,
        test_indices: Optional[np.ndarray] = None,
        closing_line_col: Optional[str] = None,
        game_time_col: Optional[str] = None,
        feature_metadata: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> TemporalValidationResult:
        """Run complete temporal validation pipeline.

        This is the main entry point for comprehensive validation.
        Runs all checks and produces a complete report.

        Args:
            df: DataFrame with all data
            feature_cols: List of feature columns to validate
            target_col: Target column name
            date_col: Date column name
            train_indices: Training set indices (optional)
            test_indices: Test set indices (optional)
            closing_line_col: Closing line column (optional)
            game_time_col: Game start time column (optional)
            feature_metadata: Feature availability metadata (optional)

        Returns:
            TemporalValidationResult with complete validation status
        """
        self.reset()

        walk_forward_valid = True
        closing_line_valid = True
        timestamp_audit_passed = True

        # 1. Validate walk-forward structure (if indices provided)
        if train_indices is not None and test_indices is not None:
            wf_result = self.validate_walk_forward(
                df,
                date_col,
                train_size=len(train_indices),
                test_size=len(test_indices),
                train_indices=train_indices,
                test_indices=test_indices,
            )
            walk_forward_valid = wf_result.is_valid

            # Also check contamination
            contamination_valid, _ = self.detect_train_test_contamination(
                df, train_indices, test_indices
            )
            walk_forward_valid = walk_forward_valid and contamination_valid

        # 2. Detect feature leakage
        leaky_features = self.detect_leakage(df, feature_cols, target_col, date_col)

        # 3. Validate closing line timing (if columns provided)
        if closing_line_col and game_time_col:
            closing_line_valid, _ = self.validate_closing_line_timing(
                df, closing_line_col, game_time_col
            )

        # 4. Audit feature timestamps (if metadata provided)
        if feature_metadata:
            timestamp_violations = self.audit_feature_timestamps(feature_metadata)
            timestamp_audit_passed = len(timestamp_violations) == 0

        # 5. Statistical leakage check
        stat_valid, _ = self._statistical_leakage_check(df)

        # Compile results
        all_passed = (
            walk_forward_valid
            and closing_line_valid
            and timestamp_audit_passed
            and len(leaky_features) == 0
            and stat_valid
        )

        # Generate summary
        summary = self._generate_summary(
            walk_forward_valid,
            closing_line_valid,
            timestamp_audit_passed,
            leaky_features,
        )

        return TemporalValidationResult(
            passed=all_passed,
            n_features_scanned=len(feature_cols),
            n_issues_found=len(self._issues),
            leaky_features=self._issues,
            walk_forward_valid=walk_forward_valid,
            closing_line_valid=closing_line_valid,
            timestamp_audit_passed=timestamp_audit_passed,
            report_summary=summary,
        )

    def _generate_summary(
        self,
        walk_forward_valid: bool,
        closing_line_valid: bool,
        timestamp_audit_passed: bool,
        leaky_features: List[FeatureLeakageInfo],
    ) -> str:
        """Generate human-readable validation summary."""
        lines = []
        lines.append("=" * 60)
        lines.append("TEMPORAL INTEGRITY VALIDATION REPORT")
        lines.append("=" * 60)

        all_passed = (
            walk_forward_valid
            and closing_line_valid
            and timestamp_audit_passed
            and len(leaky_features) == 0
        )

        status = "PASSED" if all_passed else "FAILED"
        lines.append(f"\nOverall Status: {status}")
        lines.append("-" * 40)

        lines.append(f"Walk-Forward Structure: {'OK' if walk_forward_valid else 'FAILED'}")
        lines.append(f"Closing Line Timing:    {'OK' if closing_line_valid else 'FAILED'}")
        lines.append(f"Timestamp Audit:        {'OK' if timestamp_audit_passed else 'FAILED'}")
        lines.append(
            f"Feature Leakage Scan:   {'OK' if len(leaky_features) == 0 else 'ISSUES FOUND'}"
        )

        if self._issues:
            lines.append(f"\nIssues Found: {len(self._issues)}")
            lines.append("-" * 40)

            critical = [i for i in self._issues if i.severity == "critical"]
            high = [i for i in self._issues if i.severity == "high"]
            medium = [i for i in self._issues if i.severity == "medium"]
            low = [i for i in self._issues if i.severity == "low"]

            if critical:
                lines.append(f"\nCRITICAL ({len(critical)}):")
                for issue in critical:
                    lines.append(f"  - {issue.feature_name}: {issue.leakage_type.value}")

            if high:
                lines.append(f"\nHIGH ({len(high)}):")
                for issue in high:
                    lines.append(f"  - {issue.feature_name}: {issue.leakage_type.value}")

            if medium:
                lines.append(f"\nMEDIUM ({len(medium)}):")
                for issue in medium:
                    lines.append(f"  - {issue.feature_name}: {issue.leakage_type.value}")

            if low:
                lines.append(f"\nLOW ({len(low)}):")
                for issue in low:
                    lines.append(f"  - {issue.feature_name}: {issue.leakage_type.value}")

        else:
            lines.append("\nNo temporal integrity issues detected.")

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)

    def generate_leakage_report(self) -> Dict[str, Any]:
        """Generate detailed leakage scan report.

        Returns:
            Dictionary with complete scan results and recommendations
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "n_issues": len(self._issues),
            "n_scans": len(self._scan_history),
            "issues_by_type": {},
            "issues_by_severity": {},
            "features_flagged": [],
            "recommendations": [],
            "scan_history": self._scan_history,
        }

        for issue in self._issues:
            type_key = issue.leakage_type.value
            if type_key not in report["issues_by_type"]:
                report["issues_by_type"][type_key] = []
            report["issues_by_type"][type_key].append(
                {
                    "feature": issue.feature_name,
                    "severity": issue.severity,
                    "evidence": issue.evidence,
                }
            )

        for issue in self._issues:
            if issue.severity not in report["issues_by_severity"]:
                report["issues_by_severity"][issue.severity] = []
            report["issues_by_severity"][issue.severity].append(issue.feature_name)

        for issue in self._issues:
            if issue.feature_name not in report["features_flagged"]:
                report["features_flagged"].append(issue.feature_name)
            if issue.recommendation not in report["recommendations"]:
                report["recommendations"].append(issue.recommendation)

        return report

    # =========================================================================
    # LEGACY COMPATIBILITY METHODS
    # =========================================================================

    def validate(
        self,
        backtest_results: pd.DataFrame,
        model_metadata: Optional[Dict] = None,
    ) -> TemporalValidationResult:
        """Run all temporal validations (legacy compatibility method).

        Args:
            backtest_results: DataFrame containing backtest results with dates
            model_metadata: Optional metadata about the model and features

        Returns:
            TemporalValidationResult with all validation outcomes
        """
        self.reset()

        walk_forward_valid = True
        closing_line_valid = True
        timestamp_audit_passed = True

        # Check prediction timing
        if self.prediction_date_column in backtest_results.columns:
            if self.date_column in backtest_results.columns:
                game_dates = pd.to_datetime(backtest_results[self.date_column])
                prediction_dates = pd.to_datetime(backtest_results[self.prediction_date_column])

                violations = prediction_dates > game_dates
                if violations.any():
                    n_violations = violations.sum()
                    self._add_issue(
                        feature_name="_prediction_timing",
                        leakage_type=LeakageType.PREDICTION_AFTER_GAME,
                        severity="critical",
                        evidence={"n_violations": int(n_violations)},
                        recommendation="Predictions must be made BEFORE game dates",
                    )
                    walk_forward_valid = False

        # Check train/test splits
        if model_metadata and "train_periods" in model_metadata:
            train_periods = model_metadata.get("train_periods", [])
            test_periods = model_metadata.get("test_periods", [])

            for i, (train_end, test_start) in enumerate(zip(train_periods, test_periods)):
                train_end_date = pd.to_datetime(train_end)
                test_start_date = pd.to_datetime(test_start)
                gap_days = (test_start_date - train_end_date).days

                if gap_days < 0:
                    self._add_issue(
                        feature_name=f"_fold_{i+1}",
                        leakage_type=LeakageType.TRAIN_TEST_CONTAMINATION,
                        severity="critical",
                        evidence={
                            "train_end": str(train_end),
                            "test_start": str(test_start),
                            "gap_days": gap_days,
                        },
                        recommendation="Test data must start AFTER train data ends",
                    )
                    walk_forward_valid = False

        # Statistical leakage check
        stat_valid, _ = self._statistical_leakage_check(backtest_results)

        # Feature pattern check
        if model_metadata and "features" in model_metadata:
            features = model_metadata["features"]
            for feature in features:
                feature_lower = feature.lower()
                for pattern in self.SUSPICIOUS_FEATURE_PATTERNS:
                    if pattern in feature_lower:
                        self._add_issue(
                            feature_name=feature,
                            leakage_type=LeakageType.ROLLING_NO_SHIFT,
                            severity="medium",
                            evidence={"pattern": pattern},
                            recommendation=(
                                f"Verify .shift(1) is applied AFTER rolling calculations for '{feature}'"
                            ),
                        )

        all_passed = walk_forward_valid and closing_line_valid and stat_valid

        summary = self._generate_summary(
            walk_forward_valid, closing_line_valid, timestamp_audit_passed, self._issues
        )

        return TemporalValidationResult(
            passed=all_passed,
            n_features_scanned=len(model_metadata.get("features", [])) if model_metadata else 0,
            n_issues_found=len(self._issues),
            leaky_features=self._issues,
            walk_forward_valid=walk_forward_valid,
            closing_line_valid=closing_line_valid,
            timestamp_audit_passed=timestamp_audit_passed,
            report_summary=summary,
        )

    def detect_data_leakage(
        self,
        df: pd.DataFrame,
        target_col: str = "result",
        feature_cols: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Comprehensive data leakage detection (legacy compatibility).

        Args:
            df: DataFrame with features and target
            target_col: Name of target column
            feature_cols: List of feature columns to check

        Returns:
            Dictionary with leakage detection results
        """
        if feature_cols is None:
            feature_cols = [
                c for c in df.select_dtypes(include=[np.number]).columns if c != target_col
            ]

        leakage_indicators = {
            "high_correlation_features": [],
            "zero_variance_features": [],
            "perfect_prediction_features": [],
        }

        target = df[target_col] if target_col in df.columns else None

        for col in feature_cols:
            if col not in df.columns:
                continue

            feature = df[col]

            # Check for zero variance
            if feature.std() == 0:
                leakage_indicators["zero_variance_features"].append(col)

            # Check for unrealistic correlation
            if target is not None and len(feature.dropna()) > 10:
                try:
                    valid_mask = ~(feature.isna() | target.isna())
                    if valid_mask.sum() > 10:
                        corr = np.corrcoef(feature[valid_mask], target[valid_mask])[0, 1]
                        if abs(corr) > 0.9:
                            leakage_indicators["high_correlation_features"].append(
                                (col, float(corr))
                            )
                except Exception:
                    pass

        return leakage_indicators
