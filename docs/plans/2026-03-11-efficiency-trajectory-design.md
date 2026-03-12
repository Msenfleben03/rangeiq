# Efficiency Trajectory — Feature Design

## Objective

Engineer features capturing team offensive/defensive efficiency trends from
Barttorvik point-in-time snapshots. Target: momentum/trajectory signals that
static end-of-season ratings miss, yielding marginal CLV lift in walk-forward
backtesting beyond the Elo+Barttorvik baseline.

## Decisions (Locked)

| Decision | Resolution |
|----------|-----------|
| COVID handling | Exclude 2020 entirely. Include 2021 with `covid_flag=True`; sensitivity analysis. |
| Window type | Snapshot-count-based (last N Barttorvik snapshots), not calendar-based. |
| Pre-registered windows | 10-snapshot and 20-snapshot. No post-hoc tuning. |
| Baseline dependency | Verify existing `data/backtests/` results before launch. |
| Season boundary | Slopes clamped to current season. No cross-season computation. |

## Data Sources

| Source | Path | Key Fields |
|--------|------|------------|
| Barttorvik ratings (PIT) | `data/external/barttorvik/barttorvik_ratings_{season}.parquet` | `team`, `date`, `adj_o`, `adj_d`, `adj_tempo`, `barthag`, `rank` |
| Game schedule (for alignment) | `data/raw/ncaab/ncaab_games_{season}.parquet` | `team_id`, `date`, `game_id` |

### Critical Join Logic

Features are computed per team per game date. For each game:

```python
# Get all Barttorvik snapshots for this team, strictly before game date
team_snapshots = bart_df[
    (bart_df["team"] == team_id) &
    (bart_df["date"] < game_date)        # STRICT less-than
].sort_values("date")

# Take last N snapshots for slope computation
window = team_snapshots.tail(n_snapshots)

# Validate minimum data points
if len(window) < min_points:
    return np.nan  # insufficient data for valid slope
```

### Season Boundary Clamping

```python
# Filter to current season only — no cross-season slopes
season_start = team_snapshots[team_snapshots["date"] >= season_start_date]
window = season_start.tail(n_snapshots)
```

Season start dates must be defined per year (first Barttorvik snapshot date
for that season in the data).

## Feature Specifications

### Feature 1: `adj_o_slope_10s`

```
Feature: adj_o_slope_10s
Research Item: Efficiency Trajectory
Formula: OLS slope of adj_o over last 10 Barttorvik snapshots.
         slope = linregress(x=range(10), y=adj_o_values).slope
         Units: adj_o points per snapshot interval.
         Positive slope = offense improving.
Window: 10 snapshots (pre-registered). Rationale: at ~2-3 day update
        cadence, 10 snapshots ≈ 20-30 days ≈ 7-10 games of information.
Threshold: Continuous — no threshold.
Source tables: barttorvik_ratings_{season}.parquet
Join logic: bart.date < game_date (strict). Last 10 snapshots in
            current season. .shift(1) applied after merge to game schedule.
Leakage check: Assert max(snapshot.date) < game_date for every computation.
Missing data: NaN if <5 snapshots available in current season.
              Min 5 required for valid OLS (pre-registered minimum).
COVID adjustment: 2021 — if gap >10 days between consecutive snapshots,
                  insert NaN break. Slope computed only on contiguous runs.
```

### Feature 2: `adj_d_slope_10s`

```
Feature: adj_d_slope_10s
Formula: OLS slope of adj_d over last 10 snapshots.
         SIGN CONVENTION: Multiply slope by -1 so positive = improving defense.
         Raw adj_d declining (opponent scoring less) is good; after flip,
         positive slope = defense getting better.
Window: 10 snapshots (pre-registered).
[All other fields identical to adj_o_slope_10s]
```

### Feature 3: `net_efficiency_slope_10s`

```
Feature: net_efficiency_slope_10s
Formula: OLS slope of (adj_o - adj_d) over last 10 snapshots.
         Captures overall efficiency trajectory in one number.
         Positive slope = team getting better on net.
Window: 10 snapshots (pre-registered).
[All other fields identical to adj_o_slope_10s]
Note: This is NOT simply adj_o_slope - adj_d_slope because OLS slope
      of a difference ≠ difference of OLS slopes when computed on
      different subsets (missing data handling may differ).
      Compute directly on the net series.
```

### Feature 4: `barthag_delta_10s`

```
Feature: barthag_delta_10s
Formula: barthag(most_recent_snapshot) - barthag(10th_most_recent_snapshot)
         Simple difference, no regression. Captures raw power rating change.
Window: 10 snapshots (pre-registered).
Source tables: barttorvik_ratings_{season}.parquet
Join logic: Same PIT logic. Most recent snapshot and 10th-back snapshot,
            both strictly before game_date.
Leakage check: Same assertion.
Missing data: NaN if <10 snapshots available.
COVID adjustment: Same contiguity check as slope features.
```

### Feature 5: `barthag_delta_20s`

```
Feature: barthag_delta_20s
Formula: barthag(most_recent) - barthag(20th_most_recent_snapshot)
         Longer-window version capturing sustained trajectory.
Window: 20 snapshots (pre-registered). Rationale: ~40-60 days,
        captures multi-month trends vs. the 10s short-term signal.
[All other fields identical to barthag_delta_10s]
Missing data: NaN if <20 snapshots. Will be NaN for ~first 6-8 weeks
              of season. Expected and acceptable.
```

### Feature 6: `rank_change_20s`

```
Feature: rank_change_20s
Formula: rank(20th_most_recent_snapshot) - rank(most_recent_snapshot)
         Positive value = team has risen in rankings (improving).
         Note: subtraction order is REVERSED from barthag_delta
         because lower rank = better.
Window: 20 snapshots (pre-registered).
Source tables: barttorvik_ratings — `rank` column.
Join logic: Same PIT logic.
Leakage check: Same assertion.
Missing data: NaN if <20 snapshots.
Normalization: Raw rank difference. No normalization needed — rank
               scale is consistent (1-362) across seasons.
```

## Barttorvik Snapshot Frequency Audit

Before computing any features, the agent must audit snapshot frequency:

```python
for season in [2021, 2022, 2023, 2024, 2025, 2026]:
    df = pd.read_parquet(f"barttorvik_ratings_{season}.parquet")
    unique_dates = df["date"].nunique()
    date_range = (df["date"].max() - df["date"].min()).days
    avg_gap = date_range / unique_dates
    max_gap = df.groupby("team")["date"].diff().max()
    print(f"{season}: {unique_dates} snapshots over {date_range} days, "
          f"avg gap {avg_gap:.1f}d, max gap {max_gap.days}d")
```

If any season has avg_gap > 5 days or max_gap > 14 days, flag in report
and document impact on slope reliability.

## Evaluation Criteria — Convergence-Based Promotion Gate

> **Rationale:** CLV data exists only for 2024-2025 (2021-2023 have simulated
> odds with zero-variance CLV). The original CLV-only gate requiring lift in
> ≥4/5 seasons was structurally unfair. This convergence-based gate uses
> multiple complementary metrics to give features a fair trial across all
> seasons. Adopted after 3-agent consensus review (session 57).

```
Research Item: Efficiency Trajectory
─────────────────────────────────────────────
PRIMARY GATES (ALL must pass):
  1. Pooled ROI lift > 0% (walk-forward OOS, flat-stake)
  2. Per-season consistency: positive ROI lift in >= 3/5 seasons
  3. Do-no-harm: no season with ROI lift < -5%
  4. Brier improvement on betted subset (walk-forward OOS)
  5. Brier per-season consistency: improved in >= 3/5 seasons
  6. Sample size: >= 200 bets per test season

STRUCTURAL GATES (at least 1 must pass):
  7. Edge-outcome Spearman rho > 0 (pooled)
  8. Edge-bucket monotonicity (median split)

HARD BLOCKS (any triggers REJECT):
  - Edge-outcome rho < 0 → REJECT
  - Augmented-only bets ROI < -10% → REJECT
  - Removing 2021 flips ROI sign → NEEDS_REVIEW

SUPPLEMENTAL (informational, non-blocking):
  - VIF < 5 for all selected features
  - No feature correlated >0.7 with existing model features
    or with Late-Season Losses features
  - In-sample ROI <= 2x OOS ROI
  - CLV lift (where CLV data exists: 2024-2025 only)

Computation notes:
  - Brier score must be computed on betted subset, not all games
  - Walk-forward OOS is existentially critical — no in-sample metrics
  - Convergence across multiple weak signals preferred over single threshold
```

## Agent Execution Contract

```
Agent: efficiency-trajectory-researcher
─────────────────────────────────────────
READS:
  data/external/barttorvik/barttorvik_ratings_{2021..2026}.parquet
  data/raw/ncaab/ncaab_games_{2021..2026}.parquet  (for game schedule alignment)
  data/backtests/ncaab_elo_backtest_{2021..2025}.parquet  (baseline)

WRITES:
  data/research/efficiency_trajectory_features_{season}.parquet
    Schema: season, game_date, game_id, team_id, adj_o_slope_10s,
            adj_d_slope_10s, net_efficiency_slope_10s,
            barthag_delta_10s, barthag_delta_20s, rank_change_20s
  docs/research/efficiency_trajectory_report.md
    Contents: snapshot frequency audit, feature distributions,
              correlation matrix (internal + vs baseline features),
              univariate CLV lift per feature, walk-forward results,
              COVID sensitivity, season-boundary handling stats,
              recommendation

FAILURE HANDLING:
  If Barttorvik data too sparse for a season (<30 unique dates):
  skip season, log warning, continue.
  If <4 valid seasons after exclusions: ABORT, report insufficient data.

RUNTIME: Autonomous. No user input until final report.
```

## Consolidation Step

After both agents complete, a consolidation step runs:

```
Consolidation Agent
───────────────────
READS:
  data/research/late_season_loss_features_{2021..2025}.parquet
  data/research/efficiency_trajectory_features_{2021..2025}.parquet
  data/backtests/ncaab_elo_backtest_{2021..2025}.parquet

PERFORMS:
  1. Merge both feature sets on (season, game_date, game_id, team_id)
  2. Cross-correlation matrix: all 12 features + existing model features
  3. VIF analysis — flag any feature with VIF > 5
  4. Combined walk-forward backtest: Elo+Bart+BestLossFeatures+BestTrajectoryFeatures
  5. Marginal CLV lift of combined vs. individual vs. baseline
  6. Gatekeeper pre-check (all 5 dimensions)

WRITES:
  data/research/combined_features_backtest.parquet
  docs/research/consolidated_tournament_research.md
    Contents: cross-correlation matrix, VIF table, combined backtest
              results, feature selection recommendation, Gatekeeper
              pre-check results, final recommendation for production

FAILURE HANDLING:
  If one agent produced no results: run consolidation on the other alone.
  If both failed: report data insufficiency.
```

## Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Barttorvik snapshot includes same-day results | Strict `bart.date < game_date` join |
| Cross-season slope contamination | Clamp to current season start date |
| OLS on insufficient data points | Minimum 5 snapshots required; NaN below |
| Barttorvik update frequency varies by season | Audit step before feature computation |
| COVID-2021 multi-week pauses | Contiguity check; break slopes at >10-day gaps |
| Window parameter overfitting | Pre-registered 10s/20s only |
| Multicollinearity with loss features | VIF check at consolidation; drop r > 0.7 |
