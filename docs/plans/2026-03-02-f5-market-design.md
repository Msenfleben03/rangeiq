# F5 Market Implementation — Design Document

**Date:** 2026-03-02
**Session:** 41
**Status:** Approved — ready for implementation
**Roadmap item:** #2 (post CLV/edge de-vig fix)

---

## Scope (Session 41)

Sections 1–3 only. Section 4 (Pinnacle odds via The Odds API) deferred until F5 accuracy
backtest confirms improvement over full-game predictions.

| Section | Deliverable | Deferred? |
|---------|-------------|-----------|
| 1 | F5 score data layer | No |
| 2 | F5 model output | No |
| 3 | F5 backtest + accuracy | No |
| 4 | Pinnacle live odds (The Odds API) | Yes — after positive accuracy confirmed |

---

## Motivation

The current Poisson model has 94–97% starting pitcher coverage but no bullpen model.
Full-game backtest: -3.0% ROI, -1.74% de-vigged CLV (2025). Hypothesis: F5 markets settle
before the bullpen enters, eliminating the model's primary blind spot and yielding better
CLV vs the sharp market.

---

## Section 1: Data Layer

### DB Changes

Two new nullable columns on the existing `games` table in `mlb_data.db`:

```sql
ALTER TABLE games ADD COLUMN home_f5_score INTEGER;
ALTER TABLE games ADD COLUMN away_f5_score INTEGER;
```

### F5 Score Definition

Sum of runs in innings 1–5 from the MLB Stats API linescore.
Innings with no entry (game ended early, rain, etc.) count as 0.

### Backfill Script

**File:** `scripts/mlb_backfill_f5_scores.py`

- Fetches `statsapi.game_linescore(game_pk)` for all `status = 'final'` games where
  `home_f5_score IS NULL`
- Sums `linescore.innings[0:5]` for home and away runs
- 100ms throttle between API calls (~12 min for 7,505 games)
- Idempotent: skips games already populated
- Checkpoints progress every 500 games (logs count, continues on resume)
- Handles early-ended games gracefully (partial innings = 0)

### F5 Ties

`home_f5_score == away_f5_score` after 5 innings occurs ~20–25% of the time.
Record the tie. Excluded from accuracy calculation (treated as pushes, same as full-game
ties today).

---

## Section 2: Model Layer

### New Output Keys in `PoissonModel.predict()`

```python
{
    # existing keys unchanged
    "lambda_home": float,
    "lambda_away": float,
    "moneyline_home": float,
    "run_line_home": float,
    "total_over": float,
    # new keys
    "lambda_f5_home": float,    # expected home runs through 5 innings
    "lambda_f5_away": float,    # expected away runs through 5 innings
    "f5_moneyline_home": float, # P(home leads after 5 innings), ties excluded
}
```

### F5 Lambda Formula

```python
F5_FRACTION = 5 / 9       # base: 5 of 9 innings
F5_BUMP = 1.02            # first-inning scoring bump (~0.6 vs 0.48 avg per inning)
F5_SCALE = F5_FRACTION * F5_BUMP  # ≈ 0.567

lambda_f5_home = lambda_home * F5_SCALE
lambda_f5_away = lambda_away * F5_SCALE
```

Source: `docs/mlb/research/poisson-regression-mlb.md` — "first innings average roughly
0.6 runs, higher than the 0.48 overall per-inning average."

### F5 Probability Derivation

Reuses existing functions — no new code for the math:

```python
f5_matrix = build_score_matrix(lambda_f5_home, lambda_f5_away)
f5_prob = moneyline_prob(f5_matrix)  # ties already excluded by moneyline_prob()
```

### F5 Calibration (Evidence-Based — Session 41)

**Do NOT apply the full-game Platt calibrator to F5 predictions.**

Research confirmed (NeurIPS 2020 TransCal; Walsh/Joshi 2024) that the full-game calibrator
over-shrinks F5 probabilities toward 0.5. Mechanism: the Platt slope A absorbs post-5th-
inning noise from full-game training labels; when applied to F5 (no bullpen noise), it
continues shrinking past the correct value.

**Phase 1** (now → ~500 F5 outcomes): Raw Poisson probability. Less biased than wrong
calibrator. Log all raw F5 probs and outcomes from day 1.

**Phase 2** (after ~500 resolved F5 bets, ~1–1.5 seasons): Fit dedicated F5 calibrator.
Experiment: 5-fold walk-forward, 3 conditions (raw / full-game transferred / F5-specific),
Brier score metric. Adopt F5 calibrator if improvement ≥ 0.003 vs transferred.

Implementation: `--f5-calibrated` flag stubbed but disabled with a warning until threshold.

---

## Section 3: Backtest Layer

### New CLI Flag

`python scripts/mlb_backtest.py --f5 --pitcher-adj --odds`

When `--f5` is active:
- Bet simulation uses `pred["f5_moneyline_home"]` (raw, uncalibrated)
- Full-game odds remain the CLV proxy (ESPN Core de-vigged close)
- Backtest output labels explicitly: `"CLV proxy — Pinnacle full-game close (F5-specific odds unavailable)"`

### New Accuracy Metric

`f5_correct` — did F5 model predict the correct leader after 5 innings?
Requires `home_f5_score != away_f5_score`. Ties excluded (pushes).

Primary hypothesis to validate: `f5_accuracy > full_game_accuracy`.

### Output Changes

| Metric | Description |
|--------|-------------|
| F5 accuracy | % correct F5 predictions (ties excluded) |
| Full-game accuracy (same run) | Delta comparison on same games |
| F5 bets placed | Using F5 prob + full-game closing odds proxy |
| F5 win rate | Actual win rate on placed bets |
| F5 ROI | Net P&L / total staked |
| F5 proxy CLV | De-vigged full-game close vs open (labeled as proxy) |
| F5 tie rate | % of games tied after 5 innings |

### 4-Cell Filter

`away_fav` bets suppressed from the start (ADR-MLB-011: worst CLV cell, -0.76% to -0.22%
across 2024–2025, worst ROI both years). Applied as default for `--f5` runs.

### Output File Naming

`data/processed/mlb_backtest_{season}_f5_pitcher_odds.parquet`
(No `_calibrated` suffix — F5 uses raw prob in Phase 1.)

---

## Key Constraints

| Constraint | Source |
|-----------|--------|
| ESPN Core has no F5 odds | Verified Session 41 — `OddsSnapshot` has no F5 fields |
| Pinnacle full-game close = CLV proxy | Approved design choice (Option C) |
| No shared calibrator for F5 | Evidence: NeurIPS 2020, Walsh/Joshi 2024 |
| away_fav filter on by default | ADR-MLB-011 (4-cell diagnostic) |
| Listed pitcher rule | market-strategies.md: bet is void if starter changes |
| Section 4 deferred | Await positive F5 accuracy before Pinnacle API setup |

---

## Section 4: Deferred (Pinnacle Full-Game Odds via The Odds API)

**Trigger:** Positive F5 accuracy result from Section 3 backtest.

When ready:
- New file: `pipelines/odds_api_provider.py`
- `OddsAPIProvider` class, sport `baseball_mlb`, bookmaker `pinnacle`, market `h2h`
- 2 calls/day (open + close) = ~60/month of 500 free-tier budget
- Two new columns on `odds` table: `pinnacle_home_ml`, `pinnacle_away_ml`
- Quota guard: skip fetch if `X-Requests-Remaining < 50`
- Replaces ESPN Core proxy with actual Pinnacle odds for ongoing CLV tracking

---

## Files to Create / Modify

| File | Change |
|------|--------|
| `scripts/mlb_backfill_f5_scores.py` | New — F5 score backfill |
| `models/sport_specific/mlb/poisson_model.py` | Add F5 lambda + `f5_moneyline_home` to `predict()` |
| `scripts/mlb_backtest.py` | Add `--f5` flag + F5 accuracy metric + output changes |
| `data/mlb_data.db` | Schema migration: `home_f5_score`, `away_f5_score` |
| `docs/mlb/DECISIONS.md` | ADR-MLB-010 updated (done Session 41) |
| `tests/test_mlb_poisson_model.py` | New tests for F5 lambda + `f5_moneyline_home` |
| `tests/test_mlb_backfill_f5_scores.py` | New tests for F5 backfill script |

---

## Success Criteria

- [ ] F5 scores backfilled for all 7,505 historical games (≥95% coverage)
- [ ] `predict()` returns `f5_moneyline_home` for all existing test cases
- [ ] F5 accuracy > full-game accuracy on 2025 test season
- [ ] F5 backtest report labels CLV proxy correctly
- [ ] `away_fav` bets filtered by default in `--f5` mode
- [ ] All existing tests still pass

---

## References

- ADR-MLB-010: `docs/mlb/DECISIONS.md`
- ADR-MLB-011: `docs/mlb/DECISIONS.md`
- Market strategies: `docs/mlb/research/market-strategies.md`
- Poisson + F5 research: `docs/mlb/research/poisson-regression-mlb.md`
- Calibration research: NeurIPS 2020 TransCal, Walsh/Joshi 2024 (Machine Learning with Applications)
