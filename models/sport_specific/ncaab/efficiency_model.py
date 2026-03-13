"""NCAAB Efficiency-based win probability model.

Logistic regression on Barttorvik efficiency differentials.
Implements the same interface as NCAABEloModel for drop-in compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

import numpy as np


@dataclass
class NCAABEfficiencyModel:
    """Logistic regression on Barttorvik adj_o/adj_d/barthag differentials.

    Attributes:
        lr: Fitted sklearn LogisticRegression.
        scaler: Fitted StandardScaler (trained on training data only).
        platt: Fitted Platt calibration LogisticRegression.
        crosswalk: Dict mapping ESPN abbrev -> Barttorvik team name.
        ratings: Dict mapping Barttorvik team name -> feature dict.
    """

    lr: Any
    scaler: Any
    platt: Any
    crosswalk: Dict[str, str]
    ratings: Dict[str, Dict[str, float]] = field(default_factory=dict)

    FEATURE_ORDER = [
        "adj_o_diff",
        "adj_d_diff",
        "barthag_diff",
        "adj_tempo_diff",
        "wab_diff",
        "home_flag",
    ]

    def _get_team_ratings(self, espn_id: str) -> Dict[str, float]:
        bt_name = self.crosswalk.get(espn_id)
        if bt_name is None:
            raise KeyError(
                f"ESPN ID '{espn_id}' not in crosswalk. "
                "Run scripts/update_crosswalk.py to add missing teams."
            )
        ratings = self.ratings.get(bt_name)
        if ratings is None:
            raise KeyError(
                f"Barttorvik name '{bt_name}' (from ESPN ID '{espn_id}') "
                "not in ratings. Check that the Barttorvik snapshot is loaded."
            )
        return ratings

    def predict_win_probability(
        self,
        home_team: str,
        away_team: str,
        neutral_site: bool = False,
        **kwargs: Any,
    ) -> float:
        """Return calibrated probability of home team winning.

        Args:
            home_team: ESPN team abbreviation (e.g., 'DUKE').
            away_team: ESPN team abbreviation.
            neutral_site: If True, home_flag=0 (tournament/neutral games).
            **kwargs: Absorbed for drop-in NCAABEloModel compatibility.

        Returns:
            Float in (0, 1) — Platt-calibrated win probability for home team.
        """
        home = self._get_team_ratings(home_team)
        away = self._get_team_ratings(away_team)

        features = np.array(
            [
                [
                    home["adj_o"] - away["adj_o"],  # adj_o_diff
                    away["adj_d"] - home["adj_d"],  # adj_d_diff (inverted: lower=better defense)
                    home["barthag"] - away["barthag"],  # barthag_diff
                    home["adj_tempo"] - away["adj_tempo"],  # adj_tempo_diff
                    home["wab"] - away["wab"],  # wab_diff
                    0.0 if neutral_site else 1.0,  # home_flag
                ]
            ]
        )

        X_scaled = self.scaler.transform(features)
        raw_prob = self.lr.predict_proba(X_scaled)[0, 1]
        cal_prob = self.platt.predict_proba([[raw_prob]])[0, 1]
        return float(cal_prob)

    def predict_spread(
        self,
        home_team: str,
        away_team: str,
        neutral_site: bool = False,
        **kwargs: Any,
    ) -> float:
        """Not implemented — efficiency model outputs ML probability only."""
        raise NotImplementedError(
            "NCAABEfficiencyModel does not output spreads. "
            "Use predict_win_probability() and convert via KellySizer."
        )

    def load_barttorvik_snapshot(self, df: Any) -> None:
        """Load the most recent Barttorvik snapshot into self.ratings.

        Call this at the start of each daily_run.py session with the
        freshest Barttorvik parquet slice.

        Args:
            df: DataFrame with columns [team, adj_o, adj_d, barthag, adj_tempo, wab].
                Should already be filtered to the single most recent snapshot date.
        """
        self.ratings = {
            row["team"]: {
                "adj_o": row["adj_o"],
                "adj_d": row["adj_d"],
                "barthag": row["barthag"],
                "adj_tempo": row["adj_tempo"],
                "wab": row["wab"],
            }
            for _, row in df.iterrows()
        }
