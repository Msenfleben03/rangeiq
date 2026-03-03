# MLB Betting Pipeline — Architecture Decision Records (ADR)

## Purpose

Document MLB-specific technical and strategic decisions with rationale.
Cross-sport decisions (CLV metric, Kelly sizing, walk-forward validation, etc.)
are in [`docs/DECISIONS.md`](../DECISIONS.md). This file covers decisions specific
to the MLB Poisson pipeline.

---

## ADR-MLB-001: Poisson Regression, Not Elo, as Primary Model

**Date:** February 2026
**Status:** Accepted
**Context:** NCAAB uses an Elo rating system (team strength updating after each game). Need to
choose the modeling approach for MLB, where the game outcome depends heavily on the starting
pitcher matchup rather than general team-vs-team quality.

### Decision

Use Poisson regression (`λ = exp(Xβ)`) to model expected runs per team per game.
Elo-style ratings are explicitly rejected for MLB.

### Rationale

- **Starting pitcher dominates.** Roughly 35-40% of run prevention comes from the starter alone.
  Elo cannot capture this because it assigns ratings to teams, not pitchers.
- **Poisson is theoretically justified.** Baseball scoring is modeled as discrete independent events
  at low rates — exactly the regime where Poisson is appropriate.
- **Single model, multiple markets.** λ_home and λ_away feed a score matrix P(H=i, A=j),
  from which ML, run line, totals, and F5 probabilities are all derived.
- **Precedent.** FiveThirtyEight, Dixon-Coles, and the Poisson regression literature all use
  Poisson or negative binomial for baseball run modeling.

### Alternatives Considered

- **Elo (NCAAB approach):** Rejects pitcher information; team quality changes slowly relative
  to game-to-game lineup and pitching changes. Insufficient for MLB.
- **Logistic regression on win/loss:** Discards margin information; cannot generate totals or
  run line probabilities without separate models.
- **Negative binomial:** More accurate for overdispersed counts but adds complexity. Deferred.

### Consequences

- Pitcher features are Tier 1 inputs (K-BB%, SIERA, xFIP, Stuff+).
- A score matrix `P(H=i, A=j)` must be computed at prediction time.
- Model outputs λ_home and λ_away; all market odds derived from these.
- Backtest must use prior-season pitcher stats (temporal safety).

**References:** `models/sport_specific/mlb/poisson_model.py`, `docs/mlb/MODEL_ARCHITECTURE.md`

---

## ADR-MLB-002: Separate `mlb_data.db` Database

**Date:** February 2026
**Status:** Accepted
**Context:** MLB data volume and schema are substantially different from NCAAB. The shared
`betting.db` contains bets, predictions, team ratings, and odds for all sports.

### Decision

MLB domain data lives in a dedicated `data/mlb_data.db`. Shared tracking tables
(bets, bankroll_log, predictions, odds_snapshots) remain in `data/betting.db`.

### Rationale

- **Schema complexity.** MLB requires 14 domain tables (games, pitcher_season_stats, lineups,
  park_factors, umpire_stats, weather, odds, etc.) that would bloat the shared schema.
- **game_pk as key.** MLB's canonical game identifier is the MLB Stats API `game_pk` integer,
  which is foreign to the shared `game_id TEXT` pattern.
- **Independent backup.** Either database can be deleted and rebuilt without affecting the other.
- **Query isolation.** MLB backtests join complex pitcher/weather tables; keeping them separate
  prevents accidental cross-sport query contamination.

### Alternatives Considered

- **Single unified db:** Would require extensive namespacing (mlb_ prefix on all tables) and
  makes NCAAB queries more brittle.
- **Sport-specific schema in betting.db:** Rejected — creates monolithic schema that fails
  during migration.

### Consequences

- `mlb_init_db.py` initializes and seeds `mlb_data.db` independently.
- All MLB pipelines pass `db_path = "data/mlb_data.db"` explicitly.
- Shared infrastructure (Kelly sizing, CLV tracking, bets) reads from `betting.db`.

**References:** `scripts/mlb_init_db.py`, `docs/mlb/DATA_DICTIONARY.md`

---

## ADR-MLB-003: game_pk as Canonical Game Identifier

**Date:** February 2026
**Status:** Accepted
**Context:** Multiple data sources (MLB Stats API, pybaseball, ESPN Core) identify games
differently. Need a single canonical key.

### Decision

MLB Stats API `game_pk` (integer) is the canonical game identifier in `mlb_data.db`.

### Rationale

- **MLB Stats API is authoritative.** All game data (schedules, lineups, box scores)
  originates from the official MLB Stats API.
- **Stable integer.** `game_pk` is permanent and never changes after assignment.
- **Pybaseball agrees.** Statcast data also exposes `game_pk`, enabling direct joins.
- **Odds mapping.** ESPN Core API game IDs are mapped to `game_pk` during ingestion.

### Alternatives Considered

- **ESPN game ID:** ESPN identifies MLB games differently and is not authoritative.
- **Date + teams composite key:** Not unique (doubleheaders exist; both games same date/teams).

### Consequences

- All foreign keys in `mlb_data.db` reference `game_pk INTEGER`.
- Odds backfill must translate ESPN game IDs → `game_pk` during ingestion.
- Any new data source requires a `game_pk` mapping step before loading.

---

## ADR-MLB-004: All-Free Data Sources

**Date:** February 2026
**Status:** Accepted
**Context:** MLB data is available from many sources at varying costs. Need to decide on
data strategy given zero startup cost constraint.

### Decision

Use exclusively free data sources for the MLB pipeline:

| Source | Data | Access |
|--------|------|--------|
| MLB Stats API | Schedules, lineups, box scores, rosters | Free, no key |
| pybaseball | Statcast, FanGraphs (ZiPS/Steamer), Lahman | Free, scraping |
| Open-Meteo | Historical + forecast weather | Free API, no key |
| ESPN Core API | Historical odds (2023+) | Free, unofficial |

### Rationale

- **Zero startup costs rule.** No paid subscriptions until model demonstrates positive CLV.
- **MLB Stats API is comprehensive.** Pitch-by-pitch, batter/pitcher splits, park dimensions
  — all free through `https://statsapi.mlb.com/`.
- **pybaseball is maintained.** Active development, wraps FanGraphs and Baseball Reference.
- **Open-Meteo has history.** Provides historical weather for backtesting (unlike most weather APIs).

### Alternatives Considered

- **Baseball Savant direct:** Overlaps with Statcast via pybaseball; pybaseball is easier.
- **PECOTA (Baseball Prospectus, $30/year):** Better calibrated projections but paid.
  Revisit after model demonstrates positive CLV.
- **Odds API ($20-50/month):** Better historical odds coverage. ESPN Core API is free
  alternative with 60-90% coverage on 2-3 major providers.

### Consequences

- ZiPS/Steamer projections depend on FanGraphs data availability (no guaranteed SLA).
- ESPN Core API odds coverage varies by season/provider (~65-99%).
- Must implement caching aggressively (pybaseball scraping has rate limits).

---

## ADR-MLB-005: Historical Depth 2023–2025 (3 Seasons)

**Date:** February 2026
**Status:** Accepted
**Context:** How many seasons of historical data to use for training and backtesting.

### Decision

Use 2023-2025 (3 seasons). Pre-2023 data is a stretch goal only.

### Rationale

- **Pitcher ecosystem changed post-2022.** Universal DH introduced in 2022; pitching
  metrics are not strictly comparable to pre-2022 seasons.
- **Statcast quality improved.** 2020 (pandemic season) and 2021 have data quality issues.
- **3 seasons is sufficient for walk-forward.** Train on 2023-2024, test on 2025 is a
  valid out-of-sample test with ~2,500 games.
- **pybaseball rate limits.** Fetching 6+ seasons is slow and risks blocking.

### Alternatives Considered

- **2020-2025 (6 seasons):** Includes pandemic/shortened seasons with anomalous data.
- **2022-2025 (4 seasons):** Extra year for training. DH introduced mid-2022 makes it
  a partial season. Deferred.

### Consequences

- Walk-forward: train 2023-2024, test 2025 (primary configuration).
- Walk-forward: train 2023, test 2024 (secondary check).
- Pre-2023 backfill would require separate data pipeline work.

---

## ADR-MLB-006: Prior-Season xFIP as Pitcher Adjustment

**Date:** February 2026
**Status:** Accepted
**Context:** Need to incorporate starting pitcher quality into the Poisson model without
leaking future information.

### Decision

Use prior-season xFIP (not current-season) for pitcher adjustments during backtesting.
Apply stabilization weighting (IP-based) and clamp adjustment to ±30%.

### Rationale

- **Temporal safety.** Current-season xFIP is unavailable at game time in April/May.
  Using prior-season avoids look-ahead bias in backtests.
- **xFIP beats ERA.** CMU study (2024) confirmed xFIP is the single most predictive
  pitcher feature for run prevention. FIP and xFIP outperform ERA by removing BABIP luck.
- **Stabilization matters.** xFIP stabilizes after ~400+ IP. A stabilization weight
  `IP / (IP + stabilization_IP)` shrinks low-IP pitchers toward league average.
- **Clamp prevents overfit.** Max ±30% adjustment on λ prevents extreme outliers
  from dominating model output.

### Current Limitation (Known Gap)

Prior-season-only xFIP cannot capture within-season development or decline.
**Roadmap item #5**: blend toward current-season as season progresses
(April: 90% projections / 10% current → July+: 20%/80%).

### Implementation

```python
# In compute_pitcher_adj():
relative_xfip = xfip / league_avg_xfip
weight = min(1.0, ip / STABILIZATION_IP)
raw_adj = 1.0 - weight * (1.0 - 1.0 / relative_xfip)
return max(CLAMP_LOW, min(CLAMP_HIGH, raw_adj))  # [0.7, 1.3]
```

### Consequences

- Pitcher adjustment applied to `λ_home` and `λ_away` at prediction time.
- 97.4% pitcher coverage in 2024 backtest; 94.2% in 2025 backtest.
- Accuracy improves +1.0-2.0pp with pitcher adjustment vs baseline.

**References:** `models/sport_specific/mlb/poisson_model.py:compute_pitcher_adj()`

---

## ADR-MLB-007: Platt Calibration on Training Set Predictions

**Date:** February 2026
**Status:** Accepted
**Context:** The raw Poisson model is overconfident — predicted probabilities near 0.6-0.65
don't match actual outcomes. Need calibration before using for Kelly bet sizing.

### Decision

Apply Platt calibration (logistic regression on training set predictions and outcomes)
before generating test set predictions. Calibration fits on training games within the
walk-forward window.

### Rationale

- **Model overconfidence.** Raw Poisson assigns 65% win prob to teams that win at 59%.
  Uncalibrated probabilities inflate edge calculations.
- **Platt calibration is appropriate.** Logistic regression sigmoid transform fits well
  when the uncalibrated score is monotonically ordered (which Poisson moneyline prob is).
- **Training set calibration (no leakage).** Calibrator is fit on the same training window
  used to fit the Poisson model. Test set sees only the calibrated transform.
- **Significant improvement.** Platt calibration reduces log loss by 0.011 (0.6974 → 0.6867)
  and improves accuracy by +2.0pp (54.1% → 56.1%) on 2025 test season.

### Implementation

```python
# In run_backtest():
train_probs = [model.predict(h, a)["moneyline_home"] for each training game]
train_outcomes = [1 if home_won else 0]
model.calibrate(train_probs, train_outcomes)  # Fits sklearn LogisticRegression

# At prediction time:
cal_prob = model.calibrate_prob(raw_prob)  # Applies fitted transform
```

### Alternatives Considered

- **Isotonic regression:** Monotone but non-parametric; can overfit on small calibration sets.
  Platt is more robust for 2,000-5,000 training games.
- **Temperature scaling:** Single parameter; less flexible than Platt for strong miscalibration.
- **No calibration:** Leaves ~10pp overconfidence uncorrected, biasing Kelly stake upward.

### Consequences

- `--calibrated` flag required for full-stack runs (`--pitcher-adj --calibrated --odds`).
- Calibration uses training games where both teams were seen and game had no tie.
- Calibration refits on each walk-forward split.

**References:** `models/sport_specific/mlb/poisson_model.py:calibrate()`, `calibrate_prob()`

---

## ADR-MLB-008: Multiplicative De-Vig for CLV and Edge

**Date:** March 2026
**Status:** Accepted
**Context:** Early backtest reports showed CLV of -1.23% and edge of +8.15%. These were
computed against raw implied probabilities (which include sportsbook vig). True market
probabilities are lower, making both metrics vig-inflated.

### Decision

All CLV and edge calculations use multiplicative de-vig (Pinnacle standard):

```python
# devig_prob(american_side, american_other) -> fair probability
fair_home = raw_home / (raw_home + raw_away)

# Edge against de-vigged close
edge = cal_prob - fair_home_close

# CLV: de-vigged open vs de-vigged close
clv = (fair_home_close - fair_home_open) / fair_home_open
```

**Requires all 4 odds** (home + away at open AND close) — CLV sample shrinks from ~5,100 bets
to ~1,040–1,415 bets per season.

### Rationale

- **Vig inflation is ~2pp.** For -110/-110 markets, raw implied is 52.38% vs fair 50.00% —
  a 2.38pp difference that inflates edge and deflates CLV distortion.
- **Multiplicative de-vig is the Pinnacle standard.** Used by CLV literature, sharp books,
  and betting research (Walsh/Joshi 2024, Huemann).
- **Preserves comparison across books.** Different vig levels (-105 to -115) normalize to
  the same fair probability space.

### Impact on Reported Metrics (2025 test season)

| Metric | Before (vig-inflated) | After (de-vigged) |
|--------|----------------------|-------------------|
| Avg CLV | -1.23% | -1.74% |
| Avg edge | +8.15% | +8.05% |
| ROI | -2.1% | -3.0% |

### Alternatives Considered

- **Additive de-vig (equal vig removal):** Less accurate for asymmetric markets (heavy
  favorites/-130 or more). Multiplicative better preserves relative probability.
- **Use only one side's implied prob:** Simpler but misses market consensus; ignored.

### Consequences

- `devig_prob()` added to `betting/odds_converter.py` (shared across sports).
- NCAAB `calculate_clv()` is unchanged (different function, NCAAB-specific).
- CLV now requires all 4 odds (reduces CLV sample size significantly).
- `EDGE_THRESHOLD = 3%` remains unchanged; edges are slightly larger in de-vigged space.

**References:** `betting/odds_converter.py:devig_prob()`, commit `486fcd5`

---

## ADR-MLB-009: ESPN Core API for Historical MLB Odds

**Date:** February–March 2026
**Status:** Accepted
**Context:** MLB backtesting needs historical moneyline odds (2023-2025). Same ESPN Core API
used for NCAAB odds, but the response format differs.

### Decision

Use ESPN Core API as primary historical odds source for MLB. Same provider, different
parsing: MLB returns **inline odds data** (no `$ref` indirection).

### Rationale

- **Already integrated.** `pipelines/espn_core_odds_provider.py` handles NCAAB.
  Adding MLB-specific parsing reuses authentication and rate-limiting.
- **High coverage.** 2023: 98.3%, 2025: 98.7% (2024: 63.7% — ESPN gap year).
- **Free.** No API key needed for ESPN Core.

### Implementation Difference vs NCAAB

```python
# NCAAB: follows $ref list of provider URLs
# MLB: odds are inlined in the game response (no $ref needed)
# ESPNCoreOddsFetcher.fetch_game_odds() handles both formats
```

### Alternatives Considered

- **Odds API ($20-50/month):** Better coverage for 2024 (ESPN gap year). Deferred until
  model demonstrates positive CLV.
- **The Odds API free tier:** Limited to 500 requests/month — insufficient for backfill.

### Consequences

- 2024 season has only 63.7% odds coverage (ESPN Core gap year). Some bets are unplaceable.
- `mlb_backfill_odds.py` handles idempotent odds loading (INSERT OR REPLACE).
- CLV further restricted to games with all 4 odds (open + close for both sides).

**References:** `pipelines/espn_core_odds_provider.py:fetch_game_odds()`,
`scripts/mlb_backfill_odds.py`

---

## ADR-MLB-010: F5 Market as Primary Betting Target

**Date:** March 2026
**Status:** Proposed (Roadmap Item #2)
**Context:** Full-game moneyline and totals include bullpen performance, which the current
Poisson model does not predict. Bullpen blind spot causes negative CLV on full-game lines.

### Decision

Implement First 5 Innings (F5) moneyline and totals as the primary betting market. Full-game
lines are secondary until a bullpen model is built.

### Rationale

- **Eliminates bullpen blind spot.** F5 markets settle after the starter exits (typically 5
  innings). The model has high starter coverage (94-97%) but no bullpen model.
- **Pitcher-centric model fits F5 best.** If starting pitchers are the primary driver of
  prediction accuracy, F5 maximizes that advantage.
- **Market inefficiency.** F5 markets have fewer sharp bettors than full-game lines; books
  set F5 lines algorithmically from full-game lines, creating exploitable gaps.
- **Validated in research.** `docs/mlb/research/market-strategies.md` identifies F5 as the
  best fit for current model architecture.

### Current State

Model not yet implemented for F5. Poisson model outputs λ_home and λ_away for the full game.
F5 lambda is roughly 55% of full-game lambda (starter typically pitches 5+ innings).

### Implementation Plan

1. Add F5 lambda parameters to `PoissonModel.predict()`.
2. Add F5 odds columns to `mlb_data.db` odds table.
3. Backfill F5 odds from ESPN Core API.
4. Extend backtest to simulate F5 bets.

### Alternatives Considered

- **Full-game moneyline only:** Current state. Negative CLV suggests model has no edge
  without bullpen adjustment.
- **Totals:** Requires weather + park factors + umpire data (Phase 2).

### Consequences

- F5 backtest will show higher CLV than full-game (hypothesis to be validated).
- Requires separate odds data (F5 lines != full-game lines).
- Full-game betting remains as backup if F5 shows positive CLV first.

---

## ADR-MLB-011: 4-Cell Diagnostic (Home/Away × Favorite/Underdog)

**Date:** March 2026
**Status:** Accepted
**Context:** Overall backtest metrics (ROI -3%, CLV -1.74%) mask structural patterns.
Need to identify which bet types generate edge vs which are systematic drags.

### Decision

Segment all placed bets into 4 cells and report CLV, ROI, win rate, and edge percentiles
per cell. Cells defined by: bet side (home/away) × market role (favorite/underdog).

### Results (2024–2025, `--pitcher-adj --calibrated --odds`)

| Cell | 2024 CLV | 2024 ROI | 2025 CLV | 2025 ROI | Signal |
|------|----------|----------|----------|----------|--------|
| home_fav | +1.00% | -1.6% | +2.09% | -6.8% | **Positive CLV — keep** |
| home_dog | -1.16% | +3.3% | -2.78% | +5.0% | Mixed — small n |
| away_fav | -0.76% | -8.6% | -0.22% | -9.9% | **Negative CLV — avoid** |
| away_dog | -3.17% | -1.2% | -5.82% | +3.4% | **Strongly negative CLV** |

### Decision Rule (derived)

- **home_fav**: Bet when model has edge; only cell with consistently positive de-vigged CLV.
- **away_fav**: Avoid — worst CLV and worst ROI across both seasons.
- **home_dog / away_dog**: Monitor; sample too small (<200 bets/year) for reliable conclusions.

### Rationale

- De-vigged CLV is a leading indicator of long-term profitability (ADR-001).
- Cell segmentation reveals that overall negative CLV is driven primarily by away_fav
  and away_dog bets where the model systematically misprices market.

### Consequences

- `compute_cell_breakdown()` and `format_cell_markdown()` added to `scripts/mlb_backtest.py`.
- Diagnostic output saved to `docs/mlb/4-cell-diagnostic-{season}.md` on each run.
- Future model iterations should target improving home_fav CLV and eliminating away_fav bets.

**References:** `scripts/mlb_backtest.py`, `docs/mlb/4-cell-diagnostic-2024.md`,
`docs/mlb/4-cell-diagnostic-2025.md`, commit `408accd`

---

## Template for New MLB Decisions

```markdown
## ADR-MLB-XXX: [Title]

**Date:** [Date]
**Status:** Proposed / Accepted / Deprecated / Superseded
**Context:** [What problem are we solving, specific to MLB?]

### Decision
[What did we decide?]

### Rationale
[Why did we make this decision?]

### Alternatives Considered
- [Alternative 1]: [Why rejected]
- [Alternative 2]: [Why rejected]

### Consequences
[What are the implications?]

**References:** [Files, commits, plan docs]
```
