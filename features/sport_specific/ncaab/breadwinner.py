"""Breadwinner Metric — Player Production Concentration.

Measures how concentrated a team's offensive production is among its
top players. Teams heavily reliant on 1-2 elite scorers exhibit higher
game-to-game variance, which is exploitable in betting markets.

The metric uses USG% concentration (offensive) and DBPM (defensive)
from Barttorvik player data. A quality filter restricts the signal
to top-50 teams in both adjusted offensive and defensive efficiency.

Key formulas:
    bw_top1_usg_share = top1_usg / sum(rotation_usg)
    bw_top2_usg_share = top2_usg / sum(rotation_usg)
    bw_hhi = sum((usg_i / total_usg)^2)  # Herfindahl index

Variance-based probability adjustment:
    adjusted_prob = prob + coeff * (0.5 - prob) * bw_score
    # Compresses extreme predictions toward 50% for breadwinner teams

Usage:
    from features.sport_specific.ncaab.breadwinner import (
        build_breadwinner_lookup,
        get_breadwinner_adjustment,
    )
    lookup = build_breadwinner_lookup(player_df, barttorvik_df)
    adj = get_breadwinner_adjustment(
        home="Houston", away="Duke", home_prob=0.72,
        lookup=lookup, coeff=0.01,
    )
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd

from pipelines.player_stats_fetcher import CENTER_POSITIONS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Breadwinner Scores (per-team)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BreadwinnerScores:
    """Breadwinner concentration scores for a single team."""

    team: str
    top1_usg_share: float  # Top player's USG% / total rotation USG%
    top2_usg_share: float  # Top 2 players' USG% / total rotation USG%
    usg_hhi: float  # Herfindahl-Hirschman Index of USG% concentration
    top1_dbpm: float  # Top USG% player's defensive BPM
    is_center: bool  # Is top USG% player a center (C or PF/C)?
    eligible: bool  # Passes quality filter (top-50 O and D)?
    rotation_size: int  # Number of rotation players used


def compute_breadwinner_scores(
    team_player_df: pd.DataFrame,
    team: str,
    rotation_size: int = 8,
) -> BreadwinnerScores | None:
    """Compute breadwinner concentration scores for a single team.

    Args:
        team_player_df: DataFrame of player stats for ONE team,
            must have columns: player, usg, pos, mpg, dbpm.
        team: Team name.
        rotation_size: Number of top-minutes players to consider.

    Returns:
        BreadwinnerScores dataclass, or None if insufficient data.
    """
    if team_player_df.empty:
        return None

    required_cols = {"usg", "mpg"}
    if not required_cols.issubset(team_player_df.columns):
        return None

    # Get rotation: top N by minutes
    rotation = team_player_df.nlargest(rotation_size, "mpg").copy()
    if len(rotation) < 2:
        return None

    # Filter out zero-USG players (walk-ons, etc.)
    rotation = rotation[rotation["usg"] > 0]
    if len(rotation) < 2:
        return None

    total_usg = rotation["usg"].sum()
    if total_usg <= 0:
        return None

    # Sort by USG% descending for top-1/top-2 extraction
    rotation = rotation.sort_values("usg", ascending=False)

    top1_usg = float(rotation["usg"].iloc[0])
    top2_usg = float(rotation["usg"].iloc[:2].sum())

    top1_usg_share = top1_usg / total_usg
    top2_usg_share = top2_usg / total_usg

    # Herfindahl-Hirschman Index: sum of squared shares
    shares = rotation["usg"] / total_usg
    usg_hhi = float((shares**2).sum())

    # Top player's defensive BPM
    top1_dbpm = 0.0
    if "dbpm" in rotation.columns:
        dbpm_val = rotation["dbpm"].iloc[0]
        top1_dbpm = float(dbpm_val) if pd.notna(dbpm_val) else 0.0

    # Center flag
    is_center = False
    if "pos" in rotation.columns:
        top_pos = str(rotation["pos"].iloc[0])
        is_center = top_pos in CENTER_POSITIONS

    return BreadwinnerScores(
        team=team,
        top1_usg_share=top1_usg_share,
        top2_usg_share=top2_usg_share,
        usg_hhi=usg_hhi,
        top1_dbpm=top1_dbpm,
        is_center=is_center,
        eligible=True,  # Set by build_breadwinner_lookup
        rotation_size=len(rotation),
    )


# ---------------------------------------------------------------------------
# Quality Filter
# ---------------------------------------------------------------------------


def compute_efficiency_ranks(barttorvik_df: pd.DataFrame) -> pd.DataFrame:
    """Compute adj_o and adj_d ranks from latest Barttorvik snapshot.

    Uses the most recent date entry per team. Higher adj_o is better (rank=1),
    lower adj_d is better (rank=1).

    Args:
        barttorvik_df: Barttorvik ratings with team, adj_o, adj_d, date columns.

    Returns:
        DataFrame with team, adj_o_rank, adj_d_rank columns.
    """
    if barttorvik_df.empty:
        return pd.DataFrame(columns=["team", "adj_o_rank", "adj_d_rank"])

    # Get latest snapshot per team
    if "date" in barttorvik_df.columns:
        latest_idx = barttorvik_df.groupby("team")["date"].idxmax()
        latest = barttorvik_df.loc[latest_idx].copy()
    else:
        latest = barttorvik_df.drop_duplicates("team", keep="last").copy()

    # Rank: higher adj_o is better (rank 1 = best offense)
    if "adj_o" in latest.columns:
        latest["adj_o_rank"] = latest["adj_o"].rank(ascending=False).astype(int)
    else:
        latest["adj_o_rank"] = 999

    # Rank: lower adj_d is better (rank 1 = best defense)
    if "adj_d" in latest.columns:
        latest["adj_d_rank"] = latest["adj_d"].rank(ascending=True).astype(int)
    else:
        latest["adj_d_rank"] = 999

    return latest[["team", "adj_o_rank", "adj_d_rank"]].reset_index(drop=True)


def is_breadwinner_eligible(
    team: str,
    rank_df: pd.DataFrame,
    quality_cutoff: int = 50,
) -> bool:
    """Check if team is top-N in BOTH adj_o and adj_d.

    Args:
        team: Team name (Barttorvik naming).
        rank_df: DataFrame with team, adj_o_rank, adj_d_rank columns.
        quality_cutoff: Must be <= this rank in both metrics.

    Returns:
        True if team passes the quality filter.
    """
    if rank_df.empty:
        return False

    team_row = rank_df[rank_df["team"] == team]
    if team_row.empty:
        return False

    adj_o_rank = int(team_row["adj_o_rank"].iloc[0])
    adj_d_rank = int(team_row["adj_d_rank"].iloc[0])

    return adj_o_rank <= quality_cutoff and adj_d_rank <= quality_cutoff


# ---------------------------------------------------------------------------
# Season-Wide Lookup Table
# ---------------------------------------------------------------------------


def build_breadwinner_lookup(
    player_df: pd.DataFrame,
    barttorvik_df: pd.DataFrame,
    rotation_size: int = 8,
    quality_cutoff: int = 50,
) -> dict[str, BreadwinnerScores]:
    """Build breadwinner lookup for all teams in a season.

    Args:
        player_df: Full season player stats (from PlayerStatsFetcher).
        barttorvik_df: Barttorvik team ratings (for quality filter).
        rotation_size: Top N players by minutes per team.
        quality_cutoff: Top-N rank cutoff for both O and D.

    Returns:
        Dict mapping team name -> BreadwinnerScores.
        Only includes teams that pass the quality filter.
    """
    if player_df.empty:
        return {}

    # Compute efficiency ranks for quality filter
    rank_df = compute_efficiency_ranks(barttorvik_df)

    lookup: dict[str, BreadwinnerScores] = {}
    teams = player_df["team"].unique()

    for team in teams:
        # Check quality filter
        eligible = is_breadwinner_eligible(team, rank_df, quality_cutoff)

        team_players = player_df[player_df["team"] == team]
        scores = compute_breadwinner_scores(team_players, team, rotation_size=rotation_size)

        if scores is not None:
            # Override eligibility based on quality filter
            scores = BreadwinnerScores(
                team=scores.team,
                top1_usg_share=scores.top1_usg_share,
                top2_usg_share=scores.top2_usg_share,
                usg_hhi=scores.usg_hhi,
                top1_dbpm=scores.top1_dbpm,
                is_center=scores.is_center,
                eligible=eligible,
                rotation_size=scores.rotation_size,
            )
            lookup[team] = scores

    eligible_count = sum(1 for s in lookup.values() if s.eligible)
    logger.info(
        "Built breadwinner lookup: %d teams total, %d eligible (top-%d O+D)",
        len(lookup),
        eligible_count,
        quality_cutoff,
    )
    return lookup


# ---------------------------------------------------------------------------
# Matchup Breadwinner Adjustment
# ---------------------------------------------------------------------------


def get_breadwinner_adjustment(
    home: str,
    away: str,
    home_prob: float,
    lookup: dict[str, BreadwinnerScores],
    coeff: float = 0.01,
    variant: str = "top1",
    include_centers: bool = True,
) -> float:
    """Compute breadwinner-based probability adjustment.

    Uses variance-based compression: breadwinner teams' predictions
    are compressed toward 50% (selling favorites, buying underdogs).

    The adjustment is applied to the HOME team's win probability.

    Formula:
        bw_score = home_metric - away_metric  (concentration differential)
        adj = coeff * (0.5 - home_prob) * bw_score

    When home is more concentrated (higher bw_score):
        - If home_prob > 0.5 (favorite): adj is NEGATIVE (sell the fav)
        - If home_prob < 0.5 (underdog): adj is POSITIVE (buy the dog)

    Args:
        home: Home team name (Barttorvik naming).
        away: Away team name (Barttorvik naming).
        home_prob: Current home win probability (0-1).
        lookup: Breadwinner lookup from build_breadwinner_lookup().
        coeff: Variance compression coefficient.
        variant: "top1" or "top2" — which concentration measure.
        include_centers: If False, skip adjustment when breadwinner is a center.

    Returns:
        Probability adjustment to add to home_prob. Can be positive or negative.
        Returns 0.0 if either team is not in lookup or not eligible.
    """
    home_scores = lookup.get(home)
    away_scores = lookup.get(away)

    # Both teams must be in lookup AND eligible
    if home_scores is None or away_scores is None:
        return 0.0
    if not home_scores.eligible or not away_scores.eligible:
        return 0.0

    # Center dampening
    if not include_centers:
        if home_scores.is_center or away_scores.is_center:
            return 0.0

    # Select concentration metric
    if variant == "top2":
        home_metric = home_scores.top2_usg_share
        away_metric = away_scores.top2_usg_share
    elif variant == "hhi":
        home_metric = home_scores.usg_hhi
        away_metric = away_scores.usg_hhi
    else:  # "top1" default
        home_metric = home_scores.top1_usg_share
        away_metric = away_scores.top1_usg_share

    # Concentration differential (positive = home more concentrated)
    bw_score = home_metric - away_metric

    # Variance-based compression toward 50%
    adjustment = coeff * (0.5 - home_prob) * bw_score

    return adjustment
