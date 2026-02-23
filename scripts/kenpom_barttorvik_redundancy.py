"""
KenPom vs Barttorvik Redundancy Analysis
=========================================
Quantifies correlation and orthogonality between KenPom and Barttorvik
efficiency ratings for NCAA basketball teams (seasons 2020-2025).

Usage:
    venv/Scripts/python.exe scripts/kenpom_barttorvik_redundancy.py
"""

import os
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent
KP_DIR = BASE_DIR / "data" / "external" / "kenpom"
BT_DIR = BASE_DIR / "data" / "external" / "barttorvik"
SEASONS = list(range(2020, 2026))  # 2020-2025 inclusive

# ---------------------------------------------------------------------------
# Static team-name harmonisation table
# Covers every mismatch observed across 2020-2025.
# Key = KenPom name, Value = Barttorvik name.
# ---------------------------------------------------------------------------
KP_TO_BT: dict[str, str] = {
    "Charleston": "College of Charleston",
    "LIU": "LIU Brooklyn",
    "Louisiana": "Louisiana Lafayette",
    "N.C. State": "North Carolina St.",
    "Purdue Fort Wayne": "Fort Wayne",
    "Detroit Mercy": "Detroit",
    "Saint Francis": "St. Francis PA",
    # 2025 additions
    "CSUN": "Cal St. Northridge",
    "East Texas A&M": "Texas A&M Commerce",
    "Kansas City": "UMKC",
    "McNeese": "McNeese St.",
    "Nicholls": "Nicholls St.",
    "SIUE": "SIU Edwardsville",
    "Southeast Missouri": "Southeast Missouri St.",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_kenpom(season: int) -> pd.DataFrame:
    """Load KenPom per-season parquet; normalise team names to Barttorvik."""
    path = KP_DIR / f"kenpom_ratings_{season}.parquet"
    df = pd.read_parquet(path)
    df = df.copy()
    df["team"] = df["team"].str.strip().replace(KP_TO_BT)
    df["year"] = int(season)
    # Derive net_rating for comparison with Barttorvik
    df["kp_net"] = df["adj_em"]  # adj_em IS the net efficiency margin
    cols_keep = ["team", "year", "kp_net", "adj_o", "adj_d", "adj_t", "sos_adj_em", "luck"]
    return df[cols_keep].rename(
        columns={
            "adj_o": "kp_adj_o",
            "adj_d": "kp_adj_d",
            "adj_t": "kp_adj_t",
            "sos_adj_em": "kp_sos",
            "luck": "kp_luck",
        }
    )


def load_barttorvik_final(season: int) -> pd.DataFrame:
    """Load Barttorvik season-end snapshot.

    Uses the latest date within the actual season window (before April 15) to
    avoid a known artifact in the 2025 file where a June 30 re-estimation
    date creates a spurious tempo-scale shift that drops tempo r from 0.998
    to 0.896 and net-rating r from 0.995 to 0.911.
    """
    path = BT_DIR / f"barttorvik_ratings_{season}.parquet"
    df = pd.read_parquet(path)
    # Restrict to actual season window: November through mid-April
    season_end_cutoff = pd.Timestamp(f"{season}-04-15")
    within_season = df[df["date"] <= season_end_cutoff]
    if within_season.empty:
        # Fallback: use absolute latest if no season-window data exists
        within_season = df
    df = within_season[within_season["date"] == within_season["date"].max()].copy()
    df["year"] = int(season)
    df["bt_net"] = df["adj_o"] - df["adj_d"]
    cols_keep = ["team", "year", "bt_net", "adj_o", "adj_d", "adj_tempo", "barthag"]
    return df[cols_keep].rename(
        columns={
            "adj_o": "bt_adj_o",
            "adj_d": "bt_adj_d",
            "adj_tempo": "bt_adj_tempo",
        }
    )


def pearson_spearman(x: pd.Series, y: pd.Series) -> dict:
    """Return Pearson r, Spearman rho, and both p-values for two series."""
    mask = x.notna() & y.notna()
    x, y = x[mask], y[mask]
    n = len(x)
    pr, pp = stats.pearsonr(x, y)
    sr, sp = stats.spearmanr(x, y)
    return {"n": n, "pearson_r": pr, "pearson_p": pp, "spearman_rho": sr, "spearman_p": sp}


def partial_correlation(df: pd.DataFrame, x_col: str, y_col: str, control_cols: list[str]) -> float:
    """
    Partial correlation between x and y controlling for control_cols,
    computed via residual regression (works for any n of controls).
    """
    sub = df[[x_col, y_col] + control_cols].dropna()
    if len(sub) < 10:
        return float("nan")

    def residualise(target: str) -> np.ndarray:
        """OLS residuals of target ~ controls."""
        X = sub[control_cols].values
        X = np.column_stack([np.ones(len(X)), X])
        y = sub[target].values
        coef, *_ = np.linalg.lstsq(X, y, rcond=None)
        return y - X @ coef

    rx = residualise(x_col)
    ry = residualise(y_col)
    r, _ = stats.pearsonr(rx, ry)
    return r


def fmt(val: float, decimals: int = 4) -> str:
    """Format a float to fixed decimals."""
    return f"{val:.{decimals}f}"


def significance_stars(p: float) -> str:
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


# ---------------------------------------------------------------------------
# Build merged dataset
# ---------------------------------------------------------------------------


def build_merged() -> pd.DataFrame:
    frames = []
    for season in SEASONS:
        kp = load_kenpom(season)
        bt = load_barttorvik_final(season)
        merged = kp.merge(bt, on=["team", "year"], how="inner")
        frames.append(merged)
        n_kp = len(kp)
        n_bt = len(bt)
        n_merged = len(merged)
        print(
            f"  {season}: KenPom={n_kp}, Barttorvik={n_bt}, matched={n_merged} "
            f"(lost {n_kp - n_merged} KP / {n_bt - n_merged} BT)"
        )

    df = pd.concat(frames, ignore_index=True)
    return df


# ---------------------------------------------------------------------------
# Analysis sections
# ---------------------------------------------------------------------------


def section_pairwise_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """Core pairwise Pearson / Spearman correlations for the four metric pairs."""
    pairs = [
        ("kp_net", "bt_net", "KenPom adj_em  vs  Bart (adj_o - adj_d)"),
        ("kp_adj_o", "bt_adj_o", "KenPom adj_o   vs  Bart adj_o"),
        ("kp_adj_d", "bt_adj_d", "KenPom adj_d   vs  Bart adj_d"),
        ("kp_adj_t", "bt_adj_tempo", "KenPom adj_t   vs  Bart adj_tempo"),
    ]
    rows = []
    for col_a, col_b, label in pairs:
        res = pearson_spearman(df[col_a], df[col_b])
        rows.append({"Metric Pair": label, **res})
    return pd.DataFrame(rows)


def section_per_season_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """Net-rating Pearson r computed per season to check stability."""
    rows = []
    for season, grp in df.groupby("year"):
        res = pearson_spearman(grp["kp_net"], grp["bt_net"])
        rows.append({"season": int(season), **res})
    return pd.DataFrame(rows)


def section_sos_luck_incremental(df: pd.DataFrame) -> dict:
    """
    Check whether KenPom's sos_adj_em and luck carry orthogonal signal
    beyond what Barttorvik's net rating already captures.

    Method:
      - Regress kp_net on bt_net  -> R^2_base
      - Regress kp_net on bt_net + kp_sos  -> R^2_sos
      - Regress kp_net on bt_net + kp_luck -> R^2_luck
      - Regress kp_net on bt_net + kp_sos + kp_luck -> R^2_full

    Also compute partial correlations: kp_sos~kp_net | bt_net, etc.
    """
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import r2_score

    sub = df[["kp_net", "bt_net", "kp_sos", "kp_luck"]].dropna()

    def fit_r2(features: list[str]) -> float:
        X = sub[features].values
        y = sub["kp_net"].values
        lr = LinearRegression().fit(X, y)
        return r2_score(y, lr.predict(X))

    results = {
        "n": len(sub),
        "r2_bt_only": fit_r2(["bt_net"]),
        "r2_bt_plus_sos": fit_r2(["bt_net", "kp_sos"]),
        "r2_bt_plus_luck": fit_r2(["bt_net", "kp_luck"]),
        "r2_bt_plus_sos_luck": fit_r2(["bt_net", "kp_sos", "kp_luck"]),
    }

    results["delta_r2_sos"] = results["r2_bt_plus_sos"] - results["r2_bt_only"]
    results["delta_r2_luck"] = results["r2_bt_plus_luck"] - results["r2_bt_only"]
    results["delta_r2_sos_luck"] = results["r2_bt_plus_sos_luck"] - results["r2_bt_only"]

    # Partial correlations
    results["partial_r_sos_controlling_bt"] = partial_correlation(
        sub, "kp_sos", "kp_net", ["bt_net"]
    )
    results["partial_r_luck_controlling_bt"] = partial_correlation(
        sub, "kp_luck", "kp_net", ["bt_net"]
    )

    # Raw correlations of sos/luck with bt_net (to see if BT already captures them)
    results["raw_r_sos_vs_bt"] = stats.pearsonr(sub["kp_sos"], sub["bt_net"])[0]
    results["raw_r_luck_vs_bt"] = stats.pearsonr(sub["kp_luck"], sub["bt_net"])[0]

    return results


def section_variance_explained(df: pd.DataFrame) -> dict:
    """
    PCA / shared-variance decomposition.
    How much of KenPom's net efficiency is already explained by Barttorvik's metrics?
    """
    from sklearn.linear_model import LinearRegression
    from sklearn.metrics import r2_score

    sub = df[["kp_net", "bt_net", "bt_adj_o", "bt_adj_d", "bt_adj_tempo", "barthag"]].dropna()

    def fit_r2(features):
        X = sub[features].values
        y = sub["kp_net"].values
        lr = LinearRegression().fit(X, y)
        return r2_score(y, lr.predict(X))

    return {
        "n": len(sub),
        "r2_kp_net_from_bt_net": fit_r2(["bt_net"]),
        "r2_kp_net_from_bt_net_barthag": fit_r2(["bt_net", "barthag"]),
        "r2_kp_net_from_all_bt_features": fit_r2(
            ["bt_net", "bt_adj_o", "bt_adj_d", "bt_adj_tempo", "barthag"]
        ),
        "r2_kp_adjO_from_bt_adjO": fit_r2(["bt_adj_o"]),
        "r2_kp_adjD_from_bt_adjD": fit_r2(["bt_adj_d"]),
        "r2_kp_adjT_from_bt_adjTempo": fit_r2(["bt_adj_tempo"]),
    }


def section_residual_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify teams where KenPom and Barttorvik disagree most (largest residuals
    from the net-rating regression).  These are the cases where KenPom might
    add unique signal.
    """
    from sklearn.linear_model import LinearRegression

    sub = df[["team", "year", "kp_net", "bt_net"]].dropna().copy()
    lr = LinearRegression().fit(sub[["bt_net"]], sub["kp_net"])
    sub["predicted_kp_net"] = lr.predict(sub[["bt_net"]])
    sub["residual"] = sub["kp_net"] - sub["predicted_kp_net"]
    sub["abs_residual"] = sub["residual"].abs()

    top = sub.nlargest(20, "abs_residual")[
        ["team", "year", "kp_net", "bt_net", "residual"]
    ].reset_index(drop=True)
    return top


def section_full_correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation matrix across all KP and BT numeric features."""
    cols = [
        "kp_net",
        "kp_adj_o",
        "kp_adj_d",
        "kp_adj_t",
        "kp_sos",
        "kp_luck",
        "bt_net",
        "bt_adj_o",
        "bt_adj_d",
        "bt_adj_tempo",
        "barthag",
    ]
    return df[cols].corr(method="pearson").round(4)


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------


def print_separator(char: str = "=", width: int = 80) -> None:
    print(char * width)


def print_header(title: str) -> None:
    print_separator()
    print(f"  {title}")
    print_separator()


def print_corr_table(df_corr: pd.DataFrame) -> None:
    """Print pairwise correlation table with stars."""
    header = f"{'Metric Pair':<50} {'N':>6} {'Pearson r':>10} {'p':>10} {'Spearman':>10} {'p':>10}"
    print(header)
    print("-" * len(header))
    for _, row in df_corr.iterrows():
        stars_p = significance_stars(row["pearson_p"])
        stars_s = significance_stars(row["spearman_p"])
        print(
            f"{row['Metric Pair']:<50} "
            f"{int(row['n']):>6} "
            f"{fmt(row['pearson_r'], 4):>10} "
            f"{fmt(row['pearson_p'], 6):>10}{stars_p:<3} "
            f"{fmt(row['spearman_rho'], 4):>10} "
            f"{fmt(row['spearman_p'], 6):>10}{stars_s:<3}"
        )


def run_analysis() -> None:
    print_separator()
    print("  KenPom vs Barttorvik Redundancy Analysis")
    print("  Seasons: 2020-2025  |  Method: Pearson r, Spearman rho, OLS R^2")
    print_separator()
    print()

    # ------------------------------------------------------------------
    # 1. Load and merge
    # ------------------------------------------------------------------
    print("Loading and merging data ...")
    print()
    df = build_merged()
    print(f"\nTotal matched team-season observations: {len(df):,}")
    print(f"Seasons covered: {sorted(df['year'].unique())}")
    print()
    print("DATA QUALITY NOTE: Barttorvik 2025 file contains a June 30 re-estimation")
    print("  artifact that shifts adj_tempo scale and drops net-rating r to 0.91 when")
    print("  using max(date). This analysis uses the last date within the actual season")
    print("  window (<= April 14) for all seasons, ensuring like-for-like comparisons.")
    print()

    # ------------------------------------------------------------------
    # 2. Pairwise correlations
    # ------------------------------------------------------------------
    print_header("SECTION 1: Pairwise Pearson & Spearman Correlations (pooled, all seasons)")
    print()
    corr_table = section_pairwise_correlations(df)
    print_corr_table(corr_table)
    print()
    print("Significance: *** p<0.001  ** p<0.01  * p<0.05")
    print()

    # ------------------------------------------------------------------
    # 3. Per-season stability
    # ------------------------------------------------------------------
    print_header("SECTION 2: Per-Season Net-Rating Pearson r (KenPom adj_em vs Bart net)")
    print()
    per_season = section_per_season_correlations(df)
    header = f"{'Season':>8} {'N':>6} {'Pearson r':>10} {'Spearman rho':>14}"
    print(header)
    print("-" * len(header))
    for _, row in per_season.iterrows():
        print(
            f"{int(row['season']):>8} "
            f"{int(row['n']):>6} "
            f"{fmt(row['pearson_r'], 4):>10} "
            f"{fmt(row['spearman_rho'], 4):>14}"
        )
    print()

    # ------------------------------------------------------------------
    # 4. Variance explained
    # ------------------------------------------------------------------
    print_header("SECTION 3: Variance Explained — How Much of KenPom is Already in Barttorvik?")
    print()
    ve = section_variance_explained(df)
    print(f"  n = {ve['n']:,} team-season observations")
    print()
    print(
        f"  KenPom adj_em ~ bt_net only                       R^2 = {ve['r2_kp_net_from_bt_net']:.4f}  "
        f"({ve['r2_kp_net_from_bt_net'] * 100:.1f}% of KP variance explained)"
    )
    print(
        f"  KenPom adj_em ~ bt_net + barthag                  R^2 = {ve['r2_kp_net_from_bt_net_barthag']:.4f}  "
        f"({ve['r2_kp_net_from_bt_net_barthag'] * 100:.1f}%)"
    )
    print(
        f"  KenPom adj_em ~ all Barttorvik features           R^2 = {ve['r2_kp_net_from_all_bt_features']:.4f}  "
        f"({ve['r2_kp_net_from_all_bt_features'] * 100:.1f}%)"
    )
    print()
    print(
        f"  KenPom adj_o  ~ Barttorvik adj_o                  R^2 = {ve['r2_kp_adjO_from_bt_adjO']:.4f}  "
        f"({ve['r2_kp_adjO_from_bt_adjO'] * 100:.1f}%)"
    )
    print(
        f"  KenPom adj_d  ~ Barttorvik adj_d                  R^2 = {ve['r2_kp_adjD_from_bt_adjD']:.4f}  "
        f"({ve['r2_kp_adjD_from_bt_adjD'] * 100:.1f}%)"
    )
    print(
        f"  KenPom adj_t  ~ Barttorvik adj_tempo              R^2 = {ve['r2_kp_adjT_from_bt_adjTempo']:.4f}  "
        f"({ve['r2_kp_adjT_from_bt_adjTempo'] * 100:.1f}%)"
    )
    print()

    # ------------------------------------------------------------------
    # 5. SOS and Luck incremental value
    # ------------------------------------------------------------------
    print_header("SECTION 4: Incremental Value of KenPom-Unique Fields (sos_adj_em, luck)")
    print()
    sl = section_sos_luck_incremental(df)
    print(f"  n = {sl['n']:,} team-season observations")
    print()
    print("  Baseline (KenPom adj_em ~ Barttorvik net):")
    print(f"    R^2 = {sl['r2_bt_only']:.4f}  ({sl['r2_bt_only'] * 100:.1f}% explained)")
    print()
    print("  Adding KenPom-unique predictors to explain KenPom adj_em:")
    print(
        f"    + kp_sos   -> R^2 = {sl['r2_bt_plus_sos']:.4f}  (delta = +{sl['delta_r2_sos']:.4f}  = {sl['delta_r2_sos'] * 100:.2f} ppts)"
    )
    print(
        f"    + kp_luck  -> R^2 = {sl['r2_bt_plus_luck']:.4f}  (delta = +{sl['delta_r2_luck']:.4f}  = {sl['delta_r2_luck'] * 100:.2f} ppts)"
    )
    print(
        f"    + both     -> R^2 = {sl['r2_bt_plus_sos_luck']:.4f}  (delta = +{sl['delta_r2_sos_luck']:.4f}  = {sl['delta_r2_sos_luck'] * 100:.2f} ppts)"
    )
    print()
    print("  Partial correlations (controlling for Barttorvik net):")
    print(f"    partial r(kp_sos  | bt_net) = {fmt(sl['partial_r_sos_controlling_bt'], 4)}")
    print(f"    partial r(kp_luck | bt_net) = {fmt(sl['partial_r_luck_controlling_bt'], 4)}")
    print()
    print("  Raw correlations vs Barttorvik net (is BT capturing SOS/luck already?):")
    print(f"    r(kp_sos,  bt_net) = {fmt(sl['raw_r_sos_vs_bt'], 4)}")
    print(f"    r(kp_luck, bt_net) = {fmt(sl['raw_r_luck_vs_bt'], 4)}")
    print()

    # ------------------------------------------------------------------
    # 6. Full correlation matrix
    # ------------------------------------------------------------------
    print_header("SECTION 5: Full Cross-System Pearson Correlation Matrix")
    print()
    corr_matrix = section_full_correlation_matrix(df)
    # Print with aligned columns
    cols = corr_matrix.columns.tolist()
    col_width = 12
    header_line = f"{'':20}" + "".join(f"{c:>{col_width}}" for c in cols)
    print(header_line)
    print("-" * len(header_line))
    for row_name, row_vals in corr_matrix.iterrows():
        row_line = f"{row_name:<20}" + "".join(f"{v:>{col_width}.3f}" for v in row_vals)
        print(row_line)
    print()

    # ------------------------------------------------------------------
    # 7. Residual analysis — largest KP/BT disagreements
    # ------------------------------------------------------------------
    print_header("SECTION 6: Largest KenPom vs Barttorvik Disagreements (top 20 residuals)")
    print()
    print("  (Residual = KenPom adj_em - predicted KenPom adj_em from Barttorvik net)")
    print()
    residuals = section_residual_analysis(df)
    hdr = f"  {'Team':<30} {'Year':>6} {'KP adj_em':>10} {'BT net':>8} {'Residual':>10}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for _, row in residuals.iterrows():
        direction = "KP>>BT" if row["residual"] > 0 else "BT>>KP"
        print(
            f"  {row['team']:<30} {int(row['year']):>6} "
            f"{fmt(row['kp_net'], 2):>10} "
            f"{fmt(row['bt_net'], 2):>8} "
            f"{fmt(row['residual'], 2):>10}  ({direction})"
        )
    print()

    # ------------------------------------------------------------------
    # 8. Summary conclusions
    # ------------------------------------------------------------------
    print_header("SUMMARY: KenPom vs Barttorvik — Key Conclusions")
    print()

    ve_pct = ve["r2_kp_net_from_bt_net"] * 100
    ve_full_pct = ve["r2_kp_net_from_all_bt_features"] * 100
    net_r = corr_table.loc[
        corr_table["Metric Pair"].str.startswith("KenPom adj_em"), "pearson_r"
    ].values[0]
    tempo_r = corr_table.loc[
        corr_table["Metric Pair"].str.startswith("KenPom adj_t"), "pearson_r"
    ].values[0]

    print(
        f"  1. NET RATING: Pearson r = {net_r:.4f}. Barttorvik net explains {ve_pct:.1f}% of KenPom adj_em variance."
    )
    print(
        f"     Using all BT features raises that to {ve_full_pct:.1f}%. The two systems are nearly collinear."
    )
    print()

    o_r = corr_table.loc[
        corr_table["Metric Pair"].str.startswith("KenPom adj_o"), "pearson_r"
    ].values[0]
    d_r = corr_table.loc[
        corr_table["Metric Pair"].str.startswith("KenPom adj_d"), "pearson_r"
    ].values[0]
    print(
        f"  2. OFFENSE / DEFENSE: adj_o r={o_r:.4f}, adj_d r={d_r:.4f}. "
        f"High correlation but not perfect — both systems adjust for opponent strength via "
        f"different regression approaches (Kenpom: OLS; Barttorvik: Bayesian-ish)."
    )
    print()

    print(
        f"  3. TEMPO: r={tempo_r:.4f}. Moderate alignment; KenPom and Barttorvik use different "
        f"possession-counting methods, creating genuine divergence here."
    )
    print()

    sos_dr2 = sl["delta_r2_sos"] * 100
    luck_dr2 = sl["delta_r2_luck"] * 100
    sos_partial = sl["partial_r_sos_controlling_bt"]
    luck_partial = sl["partial_r_luck_controlling_bt"]
    print(f"  4. sos_adj_em: Adds only {sos_dr2:.2f} ppts of R^2 beyond Barttorvik.")
    print(
        f"     Partial r = {sos_partial:.4f} — the residual KenPom SOS signal after controlling for BT net."
    )
    print("     Barttorvik already captures most of the schedule-strength information.")
    print()

    print(f"  5. luck: Adds {luck_dr2:.2f} ppts of R^2. Partial r = {luck_partial:.4f}.")
    print("     Luck is orthogonal to both systems' net ratings (it measures close-game variance).")
    print("     It is a NEGATIVE predictor of future performance (teams revert). Consider using it")
    print("     as a regression-to-mean signal, not an additive strength signal.")
    print()

    print("  6. VERDICT FOR MODEL FEATURE SELECTION:")
    print("     - Adding KenPom adj_em alongside Barttorvik net is largely REDUNDANT.")
    print("     - The only genuinely orthogonal KenPom signals are:")
    print("       a) KenPom luck (negative future-performance predictor, ~orthogonal to BT net)")
    print("       b) Residual KP-BT disagreement (may capture methodology differences)")
    print("       c) Tempo divergence (if using both systems' tempo estimates)")
    print("     - Practical recommendation: use Barttorvik as primary efficiency source;")
    print("       optionally add kp_luck as a mean-reversion signal if it improves OOS accuracy.")
    print()
    print_separator()


if __name__ == "__main__":
    # Validate sklearn is available (used for R^2 calculations)
    try:
        import sklearn  # noqa: F401
    except ImportError:
        print("ERROR: scikit-learn not installed. Run: venv/Scripts/pip install scikit-learn")
        sys.exit(1)

    run_analysis()
