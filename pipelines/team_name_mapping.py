"""ESPN <-> Barttorvik <-> KenPom team name mapping.

Maps ESPN team abbreviations (e.g., 'HOU') to Barttorvik T-Rank team names
(e.g., 'Houston') and KenPom team names. Uses a combination of:
1. Automatic matching via opponent_name in ESPN game data
2. Manual overrides for known discrepancies

Usage:
    from pipelines.team_name_mapping import (
        espn_id_to_barttorvik,
        barttorvik_to_kenpom,
        espn_id_to_kenpom,
        build_espn_barttorvik_mapping,
    )

    bart_name = espn_id_to_barttorvik("HOU")  # "Houston"
    kp_name = barttorvik_to_kenpom("McNeese St.")  # "McNeese"
    kp_name = espn_id_to_kenpom("HOU")  # "Houston"
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Manual overrides for ESPN -> Barttorvik name mismatches
# These are teams where automatic matching fails because:
# 1. The team never appears as an opponent_id in ESPN data
# 2. The ESPN name format differs from Barttorvik naming
# ---------------------------------------------------------------------------

MANUAL_OVERRIDES: dict[str, str] = {
    # Teams that never appear as opponent_id (play non-D1 opponents only in dataset)
    "AAMU": "Alabama A&M",
    "ACU": "Abilene Christian",
    "AF": "Air Force",
    "AKR": "Akron",
    "ALA": "Alabama",
    "AMER": "American",
    "APP": "Appalachian St.",
    "APSU": "Austin Peay",
    "ASU": "Arizona St.",
    "BRWN": "Brown",
    "CAM": "Campbell",
    "CHSO": "Charleston Southern",
    "CLE": "Cleveland St.",
    "COPP": "Coppin St.",
    # Teams with name format mismatches
    "BCU": "Bethune Cookman",
    "CONN": "Connecticut",
    "ETAM": "East Texas A&M",
    "GRAM": "Grambling St.",
    "GWEB": "Gardner Webb",
    "HAW": "Hawaii",
    "IUIN": "IU Indy",
    "L-MD": "Loyola MD",
    "LIU": "LIU",
    "M-OH": "Miami OH",
    "MIA": "Miami FL",
    "MCN": "McNeese St.",
    "MISS": "Mississippi",
    "NCSU": "N.C. State",
    "NICH": "Nicholls St.",
    "OMA": "Nebraska Omaha",
    "PENN": "Penn",
    "SELA": "Southeastern Louisiana",
    "SHSU": "Sam Houston St.",
    "SJSU": "San Jose St.",
    "STMN": "St. Thomas",
    "UALB": "Albany",
    "UAPB": "Arkansas Pine Bluff",
    "UIC": "Illinois Chicago",
    "ULM": "Louisiana Monroe",
    "UTM": "Tennessee Martin",
    # Ambiguous abbreviations (shared with non-D1 teams that overwrite in data)
    "LOU": "Louisville",
    "MAN": "Manhattan",
}

# Module-level cache for the mapping
_MAPPING_CACHE: dict[str, str] | None = None


def _strip_mascot(full_name: str, bart_names: set[str]) -> str | None:
    """Strip mascot suffix from ESPN full name to get Barttorvik name.

    Tries dropping 1-3 trailing words and checking against known Barttorvik
    names. Also tries State -> St. substitution.

    Args:
        full_name: ESPN full team name (e.g., 'Houston Cougars').
        bart_names: Set of valid Barttorvik team names.

    Returns:
        Matching Barttorvik name or None.
    """
    parts = full_name.split()
    for n_drop in range(1, min(4, len(parts))):
        candidate = " ".join(parts[:-n_drop])
        if candidate in bart_names:
            return candidate
        # Try State -> St. substitution
        candidate_st = candidate.replace(" State", " St.")
        if candidate_st in bart_names:
            return candidate_st
    return None


def build_espn_barttorvik_mapping(
    espn_data_dir: Path = Path("data/raw/ncaab"),
    bart_data_dir: Path = Path("data/external/barttorvik"),
) -> dict[str, str]:
    """Build mapping from ESPN team IDs to Barttorvik team names.

    Uses ESPN game data (opponent_name field) and Barttorvik ratings
    to automatically match teams, with manual overrides for edge cases.

    Args:
        espn_data_dir: Directory containing ESPN game parquet files.
        bart_data_dir: Directory containing Barttorvik ratings parquet files.

    Returns:
        Dict mapping ESPN team_id -> Barttorvik team name.
    """
    # Load Barttorvik team names from the most recent season
    bart_files = sorted(bart_data_dir.glob("barttorvik_ratings_*.parquet"))
    if not bart_files:
        logger.warning("No Barttorvik data found in %s", bart_data_dir)
        return dict(MANUAL_OVERRIDES)

    bart_df = pd.read_parquet(bart_files[-1])
    bart_names = set(bart_df["team"].unique())

    # Load ESPN game data to get opponent_id -> opponent_name
    espn_files = sorted(espn_data_dir.glob("ncaab_games_*.parquet"))
    if not espn_files:
        logger.warning("No ESPN data found in %s", espn_data_dir)
        return dict(MANUAL_OVERRIDES)

    id_to_fullname: dict[str, str] = {}
    all_team_ids: set[str] = set()

    for f in espn_files:
        df = pd.read_parquet(f)
        all_team_ids.update(df["team_id"].unique())
        for _, row in df.iterrows():
            opp_id = row.get("opponent_id")
            opp_name = row.get("opponent_name")
            if opp_id and opp_name and isinstance(opp_name, str):
                id_to_fullname[opp_id] = opp_name

    # Build mapping: automatic matching via mascot stripping
    mapping: dict[str, str] = {}
    unmatched: list[str] = []

    for tid in sorted(all_team_ids):
        # Check manual overrides first
        if tid in MANUAL_OVERRIDES:
            if MANUAL_OVERRIDES[tid] in bart_names:
                mapping[tid] = MANUAL_OVERRIDES[tid]
                continue
            else:
                logger.debug(
                    "Manual override %s -> %s not in Barttorvik",
                    tid,
                    MANUAL_OVERRIDES[tid],
                )

        # Try automatic matching via opponent_name
        if tid in id_to_fullname:
            bart_name = _strip_mascot(id_to_fullname[tid], bart_names)
            if bart_name:
                mapping[tid] = bart_name
                continue

        unmatched.append(tid)

    if unmatched:
        logger.debug(
            "%d ESPN teams unmatched to Barttorvik: %s",
            len(unmatched),
            unmatched[:10],
        )

    logger.info(
        "ESPN->Barttorvik mapping: %d matched, %d unmatched out of %d teams",
        len(mapping),
        len(unmatched),
        len(all_team_ids),
    )
    return mapping


def espn_id_to_barttorvik(espn_id: str) -> str | None:
    """Look up Barttorvik team name for an ESPN team ID.

    Uses a cached mapping that's built once on first call.

    Args:
        espn_id: ESPN team abbreviation (e.g., 'HOU', 'DUKE').

    Returns:
        Barttorvik team name or None if not found.
    """
    global _MAPPING_CACHE  # noqa: PLW0603
    if _MAPPING_CACHE is None:
        _MAPPING_CACHE = build_espn_barttorvik_mapping()
    return _MAPPING_CACHE.get(espn_id)


# ---------------------------------------------------------------------------
# Barttorvik <-> KenPom name mapping
# KenPom and Barttorvik use very similar team names (359/365 match).
# Only 6 mismatches need manual handling.
# ---------------------------------------------------------------------------

# Barttorvik name -> KenPom name (for the few that differ)
BARTTORVIK_TO_KENPOM_OVERRIDES: dict[str, str] = {
    "Cal St. Northridge": "CSUN",
    "McNeese St.": "McNeese",
    "Nicholls St.": "Nicholls",
    "SIU Edwardsville": "SIUE",
    "Southeast Missouri St.": "Southeast Missouri",
    "UMKC": "Kansas City",
}

# Reverse mapping: KenPom name -> Barttorvik name
KENPOM_TO_BARTTORVIK_OVERRIDES: dict[str, str] = {
    v: k for k, v in BARTTORVIK_TO_KENPOM_OVERRIDES.items()
}


def barttorvik_to_kenpom(bart_name: str) -> str:
    """Convert a Barttorvik team name to KenPom team name.

    Most names are identical. Only 6 teams have different names.

    Args:
        bart_name: Barttorvik team name.

    Returns:
        KenPom team name (same as input for most teams).
    """
    return BARTTORVIK_TO_KENPOM_OVERRIDES.get(bart_name, bart_name)


def kenpom_to_barttorvik(kp_name: str) -> str:
    """Convert a KenPom team name to Barttorvik team name.

    Args:
        kp_name: KenPom team name.

    Returns:
        Barttorvik team name (same as input for most teams).
    """
    return KENPOM_TO_BARTTORVIK_OVERRIDES.get(kp_name, kp_name)


def espn_id_to_kenpom(espn_id: str) -> str | None:
    """Look up KenPom team name for an ESPN team ID.

    Chains ESPN -> Barttorvik -> KenPom conversion.

    Args:
        espn_id: ESPN team abbreviation (e.g., 'HOU', 'DUKE').

    Returns:
        KenPom team name or None if not found.
    """
    bart_name = espn_id_to_barttorvik(espn_id)
    if bart_name is None:
        return None
    return barttorvik_to_kenpom(bart_name)
