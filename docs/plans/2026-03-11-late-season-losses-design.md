# Late-Season Losses — Feature Design

## Objective

Engineer game-level features capturing late-season loss patterns that predict
tournament (and late-regular-season) betting edge beyond the current
Elo+Barttorvik baseline. Target: measurable marginal CLV lift in walk-forward
backtesting.

## Decisions (Locked)

| Decision | Resolution |
|----------|-----------|
| COVID handling | Exclude 2020 entirely (no tournament). Include 2021 with `covid_flag=True`; run sensitivity with/without. |
| Window type | Game-count-based (last N games), not calendar-based. |
| Quality thresholds | Continuous barthag weighting, not binary rank cutoffs. |
| Pre-registered windows | 5-game and 10-game. No post-hoc window shopping. |
| Baseline dependency | Verify existing `data/backtests/` results usable before launch. |

## Data Sources

| Source | Path | Join Key |
|--------|------|----------|
| Game results | `data/raw/ncaab/ncaab_games_{season}.parquet` | `season`, `team_id`, `date` |
| Barttorvik ratings (PIT) | `data/external/barttorvik/barttorvik_ratings_{season}.parquet` | `team` ↔ `opponent_id`, `date` ≤ `game_date - 1` |

### Critical Join Logic

Opponent quality for each loss must use **point-in-time Barttorvik data**:

```python
# For each game in the lookback window:
#   1. Get opponent_id from that historical game
#   2. Get opponent's Barttorvik rating on (game_date - 1) or most recent before
#   3. Use THAT barthag for quality weighting — NOT current-date barthag
opp_bart = bart_df[
    (bart_df["team"] == opponent_id) &
    (bart_df["date"] < historical_game_date)
].sort_values("date").iloc[-1]  # most recent snapshot strictly before game
```

## Feature Specifications

### Feature 1: `late_loss_count_5g`

```
Feature: late_loss_count_5g
Research Item: Late-Season Losses
Formula: Count of losses in last 5 completed games (result == 'L')
Window: 5 games (pre-registered). Rationale: ~1.5 weeks of play, captures
        short-term losing streaks without excessive smoothing.
Threshold: Continuous — no threshold. Raw count [0-5].
Source tables: ncaab_games_{season}.parquet
Join logic: Sort team's games by date ascending, .shift(1) the cumulative
            count to prevent same-game leakage.
Leakage check: Assert feature value for game on date D uses only games
               with date < D.
Missing data: NaN for first 5 games of season. Drop from evaluation.
COVID adjustment: 2021 games with >10-day gap from prior game flagged;
                  gap games excluded from window.
```

### Feature 2: `late_loss_count_10g`

```
Feature: late_loss_count_10g
Formula: Count of losses in last 10 completed games
Window: 10 games (pre-registered). Rationale: ~3-4 weeks, captures
        sustained losing patterns vs. one-off upsets.
[All other fields identical to 5g variant]
Missing data: NaN for first 10 games of season.
```

### Feature 3: `loss_margin_mean_10g`

```
Feature: loss_margin_mean_10g
Formula: Mean margin of defeat across losses in last 10 games.
         margin = points_against - points_for (positive = lost by N).
         If no losses in window, value = 0.0.
Window: 10 games (pre-registered).
Source tables: ncaab_games_{season}.parquet
Join logic: Filter to losses in window, compute mean margin, .shift(1).
Leakage check: Same as loss_count features.
Missing data: NaN for first 10 games. 0.0 if no losses in window.
COVID adjustment: Same gap exclusion as above.
```

### Feature 4: `weighted_quality_loss_10g`

```
Feature: weighted_quality_loss_10g
Formula: For each loss in last 10 games, weight by opponent's PIT barthag:
         sum(opp_barthag_pit for each loss) / count(games_in_window)
         Higher value = losses came against stronger opponents.
Window: 10 games (pre-registered).
Threshold: Continuous. No binary cutoff.
Source tables: ncaab_games + barttorvik_ratings (PIT join).
Join logic: For each loss in window, join opponent's most recent Barttorvik
            snapshot where bart.date < game.date. Then sum opponent barthag
            values across losses and divide by total games in window (not
            just losses — this normalizes for loss frequency).
Leakage check: Assert opp_bart.date < game.date for every joined record.
Missing data: NaN if Barttorvik data unavailable for opponent. Drop game
              from numerator and denominator.
COVID adjustment: Same gap exclusion.
```

### Feature 5: `bad_loss_weighted_10g`

```
Feature: bad_loss_weighted_10g
Formula: For each loss in last 10 games, weight by (1 - opp_barthag_pit):
         sum((1 - opp_barthag_pit) for each loss) / count(games_in_window)
         Higher value = losses came against weaker opponents (bad losses).
Window: 10 games (pre-registered).
Threshold: Continuous. Inverse of quality_loss — captures "how bad" the
           losses are rather than "how good" the opponents were.
Source tables: Same as weighted_quality_loss_10g.
Join logic: Same PIT join.
Leakage check: Same assertion.
Missing data: Same policy.
```

### Feature 6: `home_loss_rate_10g`

```
Feature: home_loss_rate_10g
Formula: (home losses in last 10 games) / (home games in last 10 games).
         Captures teams losing at home as a distress signal.
Window: 10 games (pre-registered).
Source tables: ncaab_games — filter location == 'Home' within window.
Join logic: .shift(1) on the computed rate.
Leakage check: Same date assertion.
Missing data: NaN if no home games in window (rare but possible for
              teams with heavy road stretches). Do not fill.
COVID adjustment: Same gap exclusion.
Neutral site handling: Exclude neutral-site games from numerator and
                       denominator. Tournament games are neutral.
```

## Evaluation Criteria — Convergence-Based Promotion Gate

> **Rationale:** CLV data exists only for 2024-2025 (2021-2023 have simulated
> odds with zero-variance CLV). The original CLV-only gate requiring lift in
> ≥4/5 seasons was structurally unfair. This convergence-based gate uses
> multiple complementary metrics to give features a fair trial across all
> seasons. Adopted after 3-agent consensus review (session 57).

```
Research Item: Late-Season Losses
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
  - In-sample ROI <= 2x OOS ROI
  - CLV lift (where CLV data exists: 2024-2025 only)

Computation notes:
  - Brier score must be computed on betted subset, not all games
  - Walk-forward OOS is existentially critical — no in-sample metrics
  - Convergence across multiple weak signals preferred over single threshold
```

## Agent Execution Contract

```
Agent: late-season-losses-researcher
─────────────────────────────────────
READS:
  data/raw/ncaab/ncaab_games_{2021..2026}.parquet
  data/external/barttorvik/barttorvik_ratings_{2021..2026}.parquet
  data/backtests/ncaab_elo_backtest_{2021..2025}.parquet  (baseline)

WRITES:
  data/research/late_season_loss_features_{season}.parquet
    Schema: season, game_date, game_id, team_id, late_loss_count_5g,
            late_loss_count_10g, loss_margin_mean_10g,
            weighted_quality_loss_10g, bad_loss_weighted_10g,
            home_loss_rate_10g
  docs/research/late_season_losses_report.md
    Contents: feature distributions, correlation matrix, univariate
              CLV lift per feature, walk-forward results table,
              COVID sensitivity analysis, recommendation

FAILURE HANDLING:
  If PIT join fails for a season (missing Barttorvik data): skip season,
  log warning, continue with remaining seasons.
  If <4 valid seasons after exclusions: ABORT, report insufficient data.

RUNTIME: Autonomous. No user input until final report.
```

## Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| PIT rank leakage | Assertion: `opp_bart.date < game.date` on every joined record |
| COVID game gaps | Exclude games with >10-day gap from prior game in 2021 |
| Window overfitting | Pre-registered 5g/10g only. No window tuning. |
| Multicollinearity | Report VIF; drop features with r > 0.7 vs existing |
| Small tournament sample | Evaluate on full-season games; tournament is validation only |
