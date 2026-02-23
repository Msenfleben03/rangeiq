"""
KenPom/Barttorvik Staleness Analysis
=====================================
Quantifies how much predictive power is lost by using year-end (N-1) ratings
versus point-in-time ratings for within-season predictions.

Three analysis sections:
  1. Within-season rating drift: correlation and absolute change from first to
     last snapshot across all D1 teams and seasons.
  2. Predictive power: year-end N-1 vs point-in-time net rating differential
     correlated against actual game margin.
  3. Staleness penalty: percentage of R^2 lost, broken out by month of season.

Usage:
    venv/Scripts/python.exe scripts/kenpom_staleness_analysis.py
"""

import os
import sys
import warnings

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BART_DIR = os.path.join(BASE, "data", "external", "barttorvik")
RAW_DIR = os.path.join(BASE, "data", "raw", "ncaab")
SEASONS = [2020, 2021, 2022, 2023, 2024, 2025]

sys.path.insert(0, BASE)
from pipelines.team_name_mapping import espn_id_to_barttorvik  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_dates(df: pd.DataFrame, col: str = "date") -> pd.DataFrame:
    """Normalize datetime column to microsecond resolution (avoids merge_asof dtype mismatch)."""
    df[col] = pd.to_datetime(df[col]).dt.tz_localize(None).astype("datetime64[us]")
    return df


def load_barttorvik(season: int) -> pd.DataFrame:
    """Load Barttorvik daily ratings for a season with net rating computed."""
    path = os.path.join(BART_DIR, f"barttorvik_ratings_{season}.parquet")
    df = pd.read_parquet(path)
    df["net"] = df["adj_o"] - df["adj_d"]
    df = _normalize_dates(df)
    return df


def load_bt_net(season: int) -> pd.DataFrame:
    """Load Barttorvik net ratings sorted for merge_asof lookups."""
    bt = load_barttorvik(season)
    return bt[["team", "date", "net"]].sort_values(["team", "date"]).reset_index(drop=True)


def load_games(season: int) -> pd.DataFrame:
    """Load NCAAB game results with margin and Barttorvik team name columns."""
    path = os.path.join(RAW_DIR, f"ncaab_games_{season}.parquet")
    df = pd.read_parquet(path)
    df = _normalize_dates(df)
    df["margin"] = df["points_for"] - df["points_against"]
    df["team_bt"] = df["team_id"].map(espn_id_to_barttorvik)
    df["opp_bt"] = df["opponent_id"].map(espn_id_to_barttorvik)
    return df


def season_end_ratings(bt: pd.DataFrame) -> pd.DataFrame:
    """Return the final (year-end) snapshot for each team in a season."""
    last_date = bt["date"].max()
    return bt[bt["date"] == last_date][["team", "adj_o", "adj_d", "net", "rank"]].copy()


def season_start_ratings(bt: pd.DataFrame) -> pd.DataFrame:
    """Return the first snapshot of the season for each team."""
    first_date = bt["date"].min()
    return bt[bt["date"] == first_date][["team", "adj_o", "adj_d", "net", "rank"]].copy()


def season_end_net_dict(bt_net: pd.DataFrame) -> dict[str, float]:
    """Return {team: final_net_rating} from a pre-loaded bt_net DataFrame."""
    last = bt_net.groupby("team")["date"].max().reset_index().rename(columns={"date": "last_date"})
    merged = last.merge(bt_net, left_on=["team", "last_date"], right_on=["team", "date"])
    return merged.set_index("team")["net"].to_dict()


def add_pit_column(
    games_df: pd.DataFrame, bt_net: pd.DataFrame, team_col: str, result_col: str
) -> pd.DataFrame:
    """
    Vectorized point-in-time rating lookup using merge_asof.

    For each game, find the most recent Barttorvik net rating for the team
    identified by team_col that was published BEFORE the game date.
    Uses direction='backward' which is strictly less-than-or-equal, so we
    subtract one microsecond from the game date to enforce strict less-than.
    """
    games_subset = games_df[["game_id", "date", team_col]].copy()
    # Shift game date back by 1 microsecond to enforce strict less-than
    games_subset["_lookup_date"] = games_subset["date"] - pd.Timedelta(microseconds=1)

    result_parts = []
    for team_name, grp in games_subset.groupby(team_col):
        bt_team = bt_net[bt_net["team"] == team_name][["date", "net"]].sort_values("date")
        if bt_team.empty:
            grp = grp.copy()
            grp[result_col] = np.nan
            result_parts.append(grp[["game_id", team_col, result_col]])
            continue
        grp_sorted = grp.sort_values("_lookup_date")
        merged = pd.merge_asof(
            grp_sorted[["game_id", "_lookup_date", team_col]].rename(
                columns={"_lookup_date": "date"}
            ),
            bt_team,
            on="date",
            direction="backward",
        )
        merged = merged.rename(columns={"net": result_col})
        result_parts.append(merged[["game_id", team_col, result_col]])

    return pd.concat(result_parts).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Section 1: Within-season drift
# ---------------------------------------------------------------------------


def analyze_within_season_drift() -> pd.DataFrame:
    """
    For each season, compute:
    - Pearson r between first-day and last-day net rating (team level)
    - Spearman r between first-day and last-day rank
    - Mean absolute change in net rating
    - 90th-percentile absolute change in net rating
    """
    rows = []
    for season in SEASONS:
        bt = load_barttorvik(season)

        first = season_start_ratings(bt).rename(columns={"net": "net_start", "rank": "rank_start"})
        last = season_end_ratings(bt).rename(columns={"net": "net_end", "rank": "rank_end"})

        merged = first.merge(last, on="team", how="inner")
        if len(merged) < 50:
            continue

        pearson_r, pearson_p = stats.pearsonr(merged["net_start"], merged["net_end"])
        spearman_r, spearman_p = stats.spearmanr(
            merged["rank_start"].fillna(merged["rank_start"].max()),
            merged["rank_end"].fillna(merged["rank_end"].max()),
        )
        abs_change = (merged["net_end"] - merged["net_start"]).abs()

        rows.append(
            {
                "season": season,
                "n_teams": len(merged),
                "pearson_r": round(pearson_r, 4),
                "pearson_p": round(pearson_p, 6),
                "spearman_r": round(spearman_r, 4),
                "spearman_p": round(spearman_p, 6),
                "mean_abs_change_net": round(abs_change.mean(), 3),
                "median_abs_change_net": round(abs_change.median(), 3),
                "p90_abs_change_net": round(abs_change.quantile(0.90), 3),
                "max_abs_change_net": round(abs_change.max(), 3),
                "date_start": bt["date"].min().strftime("%Y-%m-%d"),
                "date_end": bt["date"].max().strftime("%Y-%m-%d"),
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Section 2: Predictive power comparison
# ---------------------------------------------------------------------------


def build_game_features() -> pd.DataFrame:
    """
    For each D1-mapped game across all seasons, compute:
    - net_diff_yearend: net rating diff using year-end N-1 Barttorvik
    - net_diff_pit:     net rating diff using point-in-time N Barttorvik
    - margin:           actual game margin (team perspective: points_for - points_against)

    Returns a flat DataFrame with one row per game-team observation.
    Only includes rows where both team and opponent are mapped to Barttorvik.

    Uses vectorized merge_asof for PIT lookups (~6s per season vs ~10min row-by-row).
    Skips season 2020 because season N-1=2019 Barttorvik data is not available.
    """
    # Pre-load bt_net DataFrames (date + net only, sorted for merge_asof)
    bt_net_cache: dict[int, pd.DataFrame] = {}
    for s in SEASONS:
        bt_net_cache[s] = load_bt_net(s)

    season_frames = []
    for season in SEASONS:
        if season == 2020:
            # No 2019 Barttorvik archive available
            continue
        prev_season = season - 1
        if prev_season not in bt_net_cache:
            continue

        print(f"  Processing season {season}...", flush=True)
        games = load_games(season)

        # Drop rows missing Barttorvik mapping on either side
        bt_teams = set(bt_net_cache[season]["team"].unique())
        yearend = season_end_net_dict(bt_net_cache[prev_season])

        games_valid = games.dropna(subset=["team_bt", "opp_bt"]).copy()
        games_valid = games_valid[
            games_valid["team_bt"].isin(yearend)
            & games_valid["opp_bt"].isin(yearend)
            & games_valid["team_bt"].isin(bt_teams)
            & games_valid["opp_bt"].isin(bt_teams)
        ].copy()

        if games_valid.empty:
            continue

        # Year-end differential (vectorized map)
        games_valid["net_ye_team"] = games_valid["team_bt"].map(yearend)
        games_valid["net_ye_opp"] = games_valid["opp_bt"].map(yearend)
        games_valid["net_diff_yearend"] = games_valid["net_ye_team"] - games_valid["net_ye_opp"]

        # Point-in-time differential (vectorized merge_asof per team group)
        bt_curr = bt_net_cache[season]
        team_pit = add_pit_column(games_valid, bt_curr, "team_bt", "pit_team")
        opp_pit = add_pit_column(games_valid, bt_curr, "opp_bt", "pit_opp")

        games_valid = games_valid.merge(
            team_pit[["game_id", "team_bt", "pit_team"]], on=["game_id", "team_bt"]
        )
        games_valid = games_valid.merge(
            opp_pit[["game_id", "opp_bt", "pit_opp"]], on=["game_id", "opp_bt"]
        )
        games_valid["net_diff_pit"] = games_valid["pit_team"] - games_valid["pit_opp"]

        keep_cols = [
            "season",
            "date",
            "game_id",
            "team_id",
            "team_bt",
            "opp_bt",
            "location",
            "margin",
            "net_diff_yearend",
            "net_diff_pit",
        ]
        season_frames.append(games_valid[keep_cols])

    df = pd.concat(season_frames, ignore_index=True)
    df["month"] = df["date"].dt.month
    return df


def analyze_predictive_power(df: pd.DataFrame) -> dict:
    """
    Compute R^2 of net_diff_yearend vs net_diff_pit for predicting margin.
    Also compute per-month and per-season breakdowns.
    """
    df_pit = df.dropna(subset=["net_diff_pit"])

    def r2(x: pd.Series, y: pd.Series) -> float:
        mask = x.notna() & y.notna()
        if mask.sum() < 10:
            return np.nan
        slope, intercept, r, p, se = stats.linregress(x[mask], y[mask])
        return float(r**2)

    def pearson(x: pd.Series, y: pd.Series) -> tuple[float, float]:
        mask = x.notna() & y.notna()
        if mask.sum() < 10:
            return np.nan, np.nan
        r, p = stats.pearsonr(x[mask], y[mask])
        return float(r), float(p)

    # Overall
    r2_ye = r2(df["net_diff_yearend"], df["margin"])
    r2_pit = r2(df_pit["net_diff_pit"], df_pit["margin"])
    r_ye, p_ye = pearson(df["net_diff_yearend"], df["margin"])
    r_pit, p_pit = pearson(df_pit["net_diff_pit"], df_pit["margin"])

    # Per-season
    season_rows = []
    for season, grp in df.groupby("season"):
        grp_pit = grp.dropna(subset=["net_diff_pit"])
        season_rows.append(
            {
                "season": season,
                "n_games": len(grp),
                "r2_yearend": round(r2(grp["net_diff_yearend"], grp["margin"]), 5),
                "r2_pit": round(r2(grp_pit["net_diff_pit"], grp_pit["margin"]), 5),
                "r_yearend": round(pearson(grp["net_diff_yearend"], grp["margin"])[0], 4),
                "r_pit": round(pearson(grp_pit["net_diff_pit"], grp_pit["margin"])[0], 4),
            }
        )

    # Per-month (pooled across seasons)
    month_rows = []
    # NCAAB season: Nov=11, Dec=12, Jan=1, Feb=2, Mar=3, Apr=4
    month_order = [11, 12, 1, 2, 3, 4]
    month_names = {11: "Nov", 12: "Dec", 1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr"}
    for month in month_order:
        grp = df[df["month"] == month]
        grp_pit = grp.dropna(subset=["net_diff_pit"])
        if len(grp) < 20:
            continue
        r2_ye_m = r2(grp["net_diff_yearend"], grp["margin"])
        r2_pit_m = r2(grp_pit["net_diff_pit"], grp_pit["margin"])
        month_rows.append(
            {
                "month": month,
                "month_name": month_names[month],
                "n_games": len(grp),
                "r2_yearend": round(r2_ye_m, 5),
                "r2_pit": round(r2_pit_m, 5) if not np.isnan(r2_pit_m) else np.nan,
                "r_yearend": round(pearson(grp["net_diff_yearend"], grp["margin"])[0], 4),
                "r_pit": round(pearson(grp_pit["net_diff_pit"], grp_pit["margin"])[0], 4)
                if not np.isnan(pearson(grp_pit["net_diff_pit"], grp_pit["margin"])[0])
                else np.nan,
            }
        )

    return {
        "overall": {
            "n_games_yearend": int(df["net_diff_yearend"].notna().sum()),
            "n_games_pit": int(df_pit["net_diff_pit"].notna().sum()),
            "r2_yearend": round(r2_ye, 5),
            "r2_pit": round(r2_pit, 5),
            "r_yearend": round(r_ye, 4),
            "r_pit": round(r_pit, 4),
            "p_yearend": round(p_ye, 8),
            "p_pit": round(p_pit, 8),
        },
        "per_season": pd.DataFrame(season_rows),
        "per_month": pd.DataFrame(month_rows),
    }


# ---------------------------------------------------------------------------
# Section 3: Staleness penalty
# ---------------------------------------------------------------------------


def analyze_staleness_penalty(df: pd.DataFrame, power_results: dict) -> pd.DataFrame:
    """
    Compute staleness penalty per month:
    - penalty_r2_pct: percentage of R^2 lost vs point-in-time
    - penalty_r2_abs: absolute R^2 difference
    Also compute a decay model: how does predictive power erode as the
    year-end rating ages through the season?
    """
    month_df = power_results["per_month"].copy()
    month_df["penalty_r2_abs"] = month_df["r2_pit"] - month_df["r2_yearend"]
    month_df["penalty_r2_pct"] = (
        (month_df["r2_pit"] - month_df["r2_yearend"]) / month_df["r2_pit"] * 100
    ).round(2)
    month_df["penalty_r_abs"] = month_df["r_pit"] - month_df["r_yearend"]

    # Approximate months since year-end: Nov=1, Dec=2, Jan=3, Feb=4, Mar=5, Apr=6
    months_since = {11: 1, 12: 2, 1: 3, 2: 4, 3: 5, 4: 6}
    month_df["months_since_yearend"] = month_df["month"].map(months_since)

    return month_df


def compute_rating_age_bins(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bin games by days-into-season (days since the season opener for that season).

    Note: year-end N-1 ratings are always ~200+ days old at the start of season N
    (April end -> November start), so binning by absolute staleness from year-end
    collapses to one bucket. Instead we bin by position within the current season:
    how far into season N is the game being predicted?

    This directly captures the within-season degradation of using a fixed year-end
    snapshot versus updating with point-in-time data.
    """
    # Get season opener date for each season
    season_start_dates = {}
    for season in SEASONS:
        if season == 2020:
            continue
        bt = load_barttorvik(season)
        season_start_dates[season] = bt["date"].min()

    df = df.copy()
    df["season_start"] = df["season"].map(season_start_dates)
    df["days_into_season"] = (df["date"] - df["season_start"]).dt.days

    # Bin by days into season: roughly 4-week buckets
    bins = [-1, 30, 60, 90, 120, 9999]
    labels = [
        "Wk1-4 (0-30d)",
        "Wk5-8 (31-60d)",
        "Wk9-12 (61-90d)",
        "Wk13-16 (91-120d)",
        "Wk17+ (121+d)",
    ]
    df["stale_bin"] = pd.cut(df["days_into_season"], bins=bins, labels=labels, right=True)

    rows = []
    for bin_label in labels:
        grp = df[df["stale_bin"] == bin_label]
        grp_pit = grp.dropna(subset=["net_diff_pit"])
        if len(grp) < 20:
            continue
        mask_ye = grp["net_diff_yearend"].notna() & grp["margin"].notna()
        if mask_ye.sum() < 10:
            r2_ye = np.nan
        else:
            _, _, r_ye, _, _ = stats.linregress(
                grp.loc[mask_ye, "net_diff_yearend"],
                grp.loc[mask_ye, "margin"],
            )
            r2_ye = r_ye**2

        if len(grp_pit) >= 10:
            _, _, r_pit, _, _ = stats.linregress(grp_pit["net_diff_pit"], grp_pit["margin"])
            r2_pit = r_pit**2
        else:
            r2_pit = np.nan

        rows.append(
            {
                "stale_bin": bin_label,
                "n_games": len(grp),
                "median_days_into_season": int(grp["days_into_season"].median()),
                "r2_yearend": round(r2_ye, 5) if not np.isnan(r2_ye) else np.nan,
                "r2_pit": round(r2_pit, 5) if not np.isnan(r2_pit) else np.nan,
                "penalty_r2_pct": (
                    round((r2_pit - r2_ye) / r2_pit * 100, 2)
                    if not np.isnan(r2_ye) and not np.isnan(r2_pit) and r2_pit > 0
                    else np.nan
                ),
            }
        )

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def print_section(title: str) -> None:
    width = 72
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)


def main() -> None:
    print("KENPOM / BARTTORVIK STALENESS ANALYSIS")
    print("Quantifying predictive power loss: year-end N-1 vs point-in-time")
    print(f"Seasons analyzed: {SEASONS}")

    # ------------------------------------------------------------------
    # Section 1: Within-season drift
    # ------------------------------------------------------------------
    print_section("SECTION 1: WITHIN-SEASON RATING DRIFT (Barttorvik proxy)")
    print("How stable are net efficiency ratings from opening day to season end?")
    print()

    drift = analyze_within_season_drift()
    print(drift.to_string(index=False))

    print()
    print("Summary statistics (across seasons):")
    print(
        f"  Mean Pearson r (start vs end):  {drift['pearson_r'].mean():.4f}"
        f"  (all p < 0.001 expected)"
    )
    print(f"  Mean Spearman r (start vs end): {drift['spearman_r'].mean():.4f}")
    print(f"  Mean absolute net change:       {drift['mean_abs_change_net'].mean():.3f} pts/100")
    print(f"  Median absolute net change:     {drift['median_abs_change_net'].mean():.3f} pts/100")
    print(f"  P90 absolute net change:        {drift['p90_abs_change_net'].mean():.3f} pts/100")
    print()
    print("Interpretation:")
    print(
        f"  Pearson r ~ {drift['pearson_r'].mean():.3f} means year-end ratings explain"
        f" ~{drift['pearson_r'].mean() ** 2 * 100:.1f}% of variance in final ratings."
    )
    print(
        f"  A team's net rating shifts on average {drift['mean_abs_change_net'].mean():.2f}"
        " pts/100 over the season."
    )
    print(
        f"  10% of teams shift by more than {drift['p90_abs_change_net'].mean():.2f}"
        " pts/100 — large enough to flip spread predictions."
    )

    # ------------------------------------------------------------------
    # Section 2: Predictive power comparison (slow — builds game features)
    # ------------------------------------------------------------------
    print_section("SECTION 2: PREDICTIVE POWER — Year-end N-1 vs Point-in-Time")
    print("Building game feature matrix (this may take ~60s)...")

    game_df = build_game_features()
    print(f"  Game observations loaded: {len(game_df):,}")
    print(f"  With valid PIT ratings:   {game_df['net_diff_pit'].notna().sum():,}")
    print()

    power = analyze_predictive_power(game_df)
    ov = power["overall"]

    print("OVERALL (pooled across all seasons):")
    print(f"  {'Metric':<30}  {'Year-end N-1':>14}  {'Point-in-Time':>14}")
    print(f"  {'-' * 60}")
    print(f"  {'N games':<30}  {ov['n_games_yearend']:>14,}  {ov['n_games_pit']:>14,}")
    print(f"  {'Pearson r (margin)':<30}  {ov['r_yearend']:>14.4f}  {ov['r_pit']:>14.4f}")
    print(f"  {'R^2 (margin)':<30}  {ov['r2_yearend']:>14.5f}  {ov['r2_pit']:>14.5f}")
    print(f"  {'p-value':<30}  {ov['p_yearend']:>14.2e}  {ov['p_pit']:>14.2e}")

    r2_gain_pct = (ov["r2_pit"] - ov["r2_yearend"]) / ov["r2_pit"] * 100
    print()
    print(
        f"  Point-in-time R^2 gain over year-end: "
        f"{ov['r2_pit'] - ov['r2_yearend']:+.5f} ({r2_gain_pct:+.2f}%)"
    )

    print()
    print("PER SEASON:")
    per_s = power["per_season"].copy()
    per_s["r2_gain_pct"] = ((per_s["r2_pit"] - per_s["r2_yearend"]) / per_s["r2_pit"] * 100).round(
        2
    )
    print(per_s.to_string(index=False))

    print()
    print("PER MONTH (pooled across seasons):")
    per_m = power["per_month"].copy()
    per_m["r2_gain_pct"] = ((per_m["r2_pit"] - per_m["r2_yearend"]) / per_m["r2_pit"] * 100).round(
        2
    )
    print(per_m.to_string(index=False))

    # ------------------------------------------------------------------
    # Section 3: Staleness penalty
    # ------------------------------------------------------------------
    print_section("SECTION 3: STALENESS PENALTY BREAKDOWN")

    penalty_month = analyze_staleness_penalty(game_df, power)
    print("PENALTY BY MONTH INTO SEASON:")
    print(
        f"  {'Month':<6} {'N games':>8} {'R2 YE':>9} {'R2 PiT':>9}"
        f" {'Penalty (abs)':>14} {'Penalty (%)':>12}"
    )
    print(f"  {'-' * 65}")
    for _, r in penalty_month.iterrows():
        print(
            f"  {r['month_name']:<6} {r['n_games']:>8,} {r['r2_yearend']:>9.5f}"
            f" {r['r2_pit']:>9.5f} {r['penalty_r2_abs']:>14.5f} {r['penalty_r2_pct']:>11.2f}%"
        )

    print()
    print("PENALTY BY POSITION IN SEASON (days from season opener):")
    stale_df = compute_rating_age_bins(game_df)
    print(stale_df.to_string(index=False))

    # ------------------------------------------------------------------
    # Summary conclusion
    # ------------------------------------------------------------------
    print_section("SUMMARY CONCLUSIONS")
    mean_penalty = penalty_month["penalty_r2_pct"].mean()
    early_penalty = penalty_month.loc[
        penalty_month["month_name"].isin(["Nov", "Dec"]), "penalty_r2_pct"
    ].mean()
    late_penalty = penalty_month.loc[
        penalty_month["month_name"].isin(["Feb", "Mar"]), "penalty_r2_pct"
    ].mean()

    print(f"  Overall mean R^2 staleness penalty:      {mean_penalty:.2f}%")
    print(f"  Early season (Nov-Dec) penalty:          {early_penalty:.2f}%")
    print(f"  Late season (Feb-Mar) penalty:           {late_penalty:.2f}%")
    print()
    print(
        f"  Barttorvik within-season rating stability (mean Pearson r): "
        f"{drift['pearson_r'].mean():.4f}"
    )
    print(
        f"  Rank stability (mean Spearman r):                           "
        f"{drift['spearman_r'].mean():.4f}"
    )
    print()
    print("  Practical conclusion:")
    if abs(mean_penalty) < 5:
        print("  Year-end ratings are a LOW-staleness proxy: penalty < 5% of R^2.")
        print("  Using season N-1 year-end ratings for all of season N is defensible.")
    elif abs(mean_penalty) < 15:
        print("  Year-end ratings are a MODERATE-staleness proxy: penalty 5-15% of R^2.")
        print("  Consider blending year-end N-1 with any available current-season data.")
    else:
        print("  Year-end ratings carry a HIGH staleness penalty: > 15% of R^2.")
        print("  Point-in-time ratings provide meaningfully better predictions.")
        print("  Migrating to point-in-time Barttorvik is strongly recommended.")


if __name__ == "__main__":
    main()
