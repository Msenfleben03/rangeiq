# Experiment Registry

Central catalog of all research experiments, feature evaluations, and model
investigations. Every experiment gets an entry regardless of outcome — rejected
experiments are as valuable as adopted ones.

**How to add:** Copy the template at the bottom, fill in all fields, append to
the appropriate sport section. Link artifacts. Update the summary table.

---

## Summary Table

| ID | Name | Sport | Date | Decision | Key Finding |
|----|------|-------|------|----------|-------------|
| EXP-001 | Advanced Feature Research | NCAAB | 2026-02-16 | PARTIAL | 3/6 features adopted (vol, OQ margin, rest days) |
| EXP-002 | KenPom Integration | NCAAB | 2026-02 | REJECT | 98.9% redundant with Barttorvik |
| EXP-003 | Barttorvik Weight Tuning | NCAAB | 2026-02 | ADOPT | +27.09% pooled ROI; weights locked |
| EXP-004 | A/B Feature Comparison | NCAAB | 2026-02 | ADOPT | Barttorvik significant (p=0.007); features marginal (p=0.128) |
| EXP-005 | Breadwinner Metric | NCAAB | 2026-02 | REJECT | No ROI correlation across 192 parameter combos |
| EXP-006 | Late-Season Losses | NCAAB | 2026-03-11 | REJECT | Negative ROI lift all 5 seasons; baseline already prices signal |
| EXP-007 | Efficiency Trajectory | NCAAB | 2026-03-11 | REJECT | OLS slopes are noise; market already prices trajectory |
| EXP-008 | Combined Tournament Features | NCAAB | 2026-03-11 | REJECT | 0/5 primary gates pass; hard block triggered (ρ<0) |
| EXP-009 | Convergence Promotion Gate | Framework | 2026-03-11 | ADOPT | Replaces CLV-only gate; handles missing-CLV seasons |
| EXP-010 | MLB Poisson v1 | MLB | 2026-02-26 | IN PROGRESS | 56.1% acc; only home_fav CLV positive (+2.08%) |
| EXP-011 | Data Sources Survey | Infra | 2026-02 | REFERENCE | SBRO down; OddsHarvester best scraper; Pinnacle CLV TBD |

---

## NCAAB Experiments

### EXP-001: Advanced Feature Research

- **Date:** 2026-02-16
- **Decision:** PARTIAL ADOPT (3 of 6)
- **Hypothesis:** Rolling game-level features (volatility, OQ margin, rest,
  decay, Hurst, Jensen's alpha) improve Elo model predictions.
- **Methodology:** 5 parallel research agents scored 6 features on a 6-dimension
  matrix (predictive lift, data availability, effort, bias risk, redundancy,
  evidence). Cross-feature synthesis and priority ranking.
- **Results:**
  - Rolling Volatility (5g, 10g): **GO** — 28/30 score
  - OQ-Weighted Margin: **GO** — 24/30
  - Rest Days / B2B: **GO** — 26/30
  - Time Decay: **CAUTION** — 20/30 (modifier only)
  - Hurst Exponent: **SKIP** — 12/30 (sample size too small)
  - Jensen's Alpha: **SKIP** — 9/30 (circular metric)
- **Key Learning:** Simple, interpretable features (volatility, rest) score
  higher than complex statistical measures (Hurst, Jensen's alpha).
- **Artifacts:**
  - Report: `docs/ADVANCED_FEATURES_RESEARCH.md`
  - Implementation: `features/sport_specific/ncaab/advanced_features.py`
  - Backtest integration: `scripts/backtest_ncaab_elo.py` (`run_backtest_with_features`)

---

### EXP-002: KenPom Integration

- **Date:** 2026-02 (Session 9)
- **Decision:** REJECT
- **Hypothesis:** KenPom efficiency ratings add predictive value beyond
  Barttorvik.
- **Methodology:** Variance overlap analysis, staleness penalty measurement
  (year-end vs point-in-time R² loss).
- **Results:**
  - 98.9% variance overlap with Barttorvik — measuring the same construct
  - 41-63% R² loss from staleness (year-end vs PIT)
  - No marginal lift when Barttorvik already included
- **Key Learning:** When two data sources measure the same underlying construct,
  adding the second is pure noise. Check redundancy BEFORE building features.
- **Artifacts:**
  - Tuning script: `scripts/tune_kenpom_weights.py`
  - Test: `tests/test_tune_kenpom.py`
  - Backtest support: `scripts/backtest_ncaab_elo.py` (`--kenpom` flag)

---

### EXP-003: Barttorvik Weight Tuning

- **Date:** 2026-02
- **Decision:** ADOPT
- **Hypothesis:** Barttorvik efficiency ratings improve Elo predictions when
  combined with optimal weighting.
- **Methodology:** Grid search over barttorvik_weight × net_diff_coeff ×
  barthag_diff_coeff (80 combinations). Walk-forward OOS evaluation.
- **Results:**
  - Optimal: `net_diff_coeff=0.003, barthag_diff_coeff=0.1, weight=1.0`
  - Pooled flat ROI: **+27.09%** (5 seasons 2021-2025), p=0.0001
  - Per-season: 2021 +20.95% | 2022 +29.26% | 2023 +29.86% | 2024 +27.80% | 2025 +27.57%
- **Key Learning:** PIT Barttorvik ratings provide consistent marginal lift
  over pure Elo. Coefficients are stable across seasons.
- **Artifacts:**
  - Tuning: `scripts/tune_barttorvik_weights.py`
  - Integration: `pipelines/barttorvik_fetcher.py`
  - Coefficients: `scripts/backtest_ncaab_elo.py` (`BarttovikCoeffs` dataclass)

---

### EXP-004: A/B Feature Comparison

- **Date:** 2026-02
- **Decision:** ADOPT (Barttorvik config)
- **Hypothesis:** Systematic A/B comparison of Elo alone vs Elo+features vs
  Elo+Barttorvik vs Elo+Barttorvik+features.
- **Methodology:** Paired t-tests across all 4 configurations.
- **Results:**
  - Config A (Elo baseline): reference
  - Config B (Elo + advanced features): p=0.128 (marginal)
  - Config C (Elo + Barttorvik): **p=0.007** (significant)
  - Config D (Elo + Barttorvik + features): p=0.009 (significant)
- **Key Learning:** Barttorvik is the primary driver of lift. Advanced features
  add marginal value on top. Config C (Elo+Barttorvik) is the production model.
- **Artifacts:**
  - Script: `scripts/ab_compare_features.py`

---

### EXP-005: Breadwinner Metric

- **Date:** 2026-02
- **Decision:** REJECT (DISABLED)
- **Hypothesis:** Teams with concentrated offensive production (high USG%
  concentration) are higher variance, and predictions should be compressed
  toward 50% for these teams.
- **Methodology:** Grid search over 192 parameter combinations (4 weights ×
  4 coefficients × 2 variants × 2 center modes × 3 cutoffs).
- **Results:** No meaningful ROI correlation across any parameter combination.
- **Key Learning:** Roster concentration might matter for individual game
  variance but doesn't predict systematic betting edge. The market already
  prices star-dependency risk.
- **Artifacts:**
  - Feature: `features/sport_specific/ncaab/breadwinner.py` (DISABLED)
  - Tuning: `scripts/tune_breadwinner_weights.py`
  - Backtest hook: `scripts/backtest_ncaab_elo.py` (breadwinner params exist but weight=0)

---

### EXP-006: Late-Season Losses

- **Date:** 2026-03-11 (Session 57)
- **Decision:** REJECT
- **Hypothesis:** Late-season loss patterns (frequency, margin, opponent quality,
  home/away) predict tournament and late-season betting edge beyond baseline.
- **Methodology:** 6 features with game-count windows (5g, 10g), PIT Barttorvik
  opponent quality weighting, shift(1) leakage prevention. Walk-forward OOS
  evaluation with Kelly re-sizing.
- **Features Tested:**
  - `late_loss_count_5g`, `late_loss_count_10g` — rolling loss count
  - `loss_margin_mean_10g` — mean margin of defeat
  - `weighted_quality_loss_10g` — loss weighted by opponent barthag
  - `bad_loss_weighted_10g` — loss weighted by (1 - opponent barthag)
  - `home_loss_rate_10g` — home loss rate
- **Results:**
  - Univariate CLV correlations significant in 2025 only (`weighted_quality_loss_10g`
    r=-0.138, p=0.0001; `late_loss_count_10g` r=-0.118, p=0.0005)
  - Walk-forward ROI lift: **negative all 5 seasons** (worst: -47% in 2025)
  - Brier worsens in 4/5 seasons
  - Edge-outcome ρ negative pooled → hard block triggered
- **Key Learning:** The Elo+Barttorvik baseline already captures late-season
  loss signals through Barttorvik rating updates. Adding loss features as
  probability adjustments introduces noise. Univariate CLV correlations
  (in-sample) don't imply marginal predictive value (OOS).
- **Artifacts:**
  - Features: `features/sport_specific/ncaab/late_season_losses.py`
  - Pipeline: `scripts/research_late_season_losses.py`
  - Design: `docs/plans/2026-03-11-late-season-losses-design.md`
  - Report: `docs/research/late_season_losses_report.md`
  - Tests: `tests/test_late_season_losses.py` (22 tests)

---

### EXP-007: Efficiency Trajectory

- **Date:** 2026-03-11 (Session 57)
- **Decision:** REJECT
- **Hypothesis:** Team efficiency trends (OLS slopes of adj_o, adj_d, net
  efficiency, barthag deltas, rank changes) capture momentum signals that
  static ratings miss.
- **Methodology:** 6 features from Barttorvik PIT snapshots with 10/20-snapshot
  windows, season boundary clamping, MIN_SLOPE_POINTS=5 enforcement.
- **Features Tested:**
  - `adj_o_slope_10s`, `adj_d_slope_10s` — OLS efficiency slopes
  - `net_efficiency_slope_10s` — net efficiency trend
  - `barthag_delta_10s`, `barthag_delta_20s` — simple differences
  - `rank_change_20s` — rank movement
- **Results:**
  - Only `barthag_delta_10s` shows significance (2025: r=+0.062, p=0.023)
  - OLS slope features are noise across all seasons
  - 6 redundancy pairs (|r|>0.7) within the trajectory feature set
  - Walk-forward evaluation: negative ROI lift, worse Brier scores
- **Key Learning:** Barttorvik ratings are updated frequently enough that their
  current value already reflects trajectory. OLS slopes on 10 snapshots are
  statistically fragile. Efficiency trajectory is a derivative of information
  the model already has.
- **Artifacts:**
  - Features: `features/sport_specific/ncaab/efficiency_trajectory.py`
  - Pipeline: `scripts/research_efficiency_trajectory.py`
  - Design: `docs/plans/2026-03-11-efficiency-trajectory-design.md`
  - Report: `docs/research/efficiency_trajectory_report.md`
  - Tests: `tests/test_efficiency_trajectory.py` (11 tests)

---

### EXP-008: Combined Tournament Features (Consolidation)

- **Date:** 2026-03-11
- **Decision:** REJECT
- **Hypothesis:** Combining late-season loss and efficiency trajectory features
  provides complementary signal that improves the model.
- **Methodology:** Merged 12 features, cross-correlation + VIF analysis,
  walk-forward OOS evaluation with convergence-based promotion gate.
- **Results:**
  - 8 redundancy pairs (|r|>0.7), multiple inf VIF values
  - Candidate set (5 features): REJECT — 0/5 primary gates pass
  - Full set (12 features): REJECT — 0/5 primary gates pass, hard block
  - The `weighted_quality_loss_10g` feature (unlocked by ESPN→Barttorvik
    crosswalk) is the strongest single signal but still insufficient
- **Key Learning:** When the baseline model already incorporates the underlying
  data source (Barttorvik), derived features from that same source are unlikely
  to add marginal value. The crosswalk was worth building (reusable infra) but
  the features it unlocked don't pass promotion.
- **Artifacts:**
  - Consolidation: `scripts/research_consolidation.py`
  - Evaluation: `scripts/research_evaluation.py`
  - Crosswalk: `data/reference/espn_barttorvik_crosswalk.csv`
  - Reports: `docs/research/consolidated_tournament_research.md`,
    `docs/research/promotion_gate_evaluation.md`
  - Shared utils: `features/sport_specific/ncaab/research_utils.py`
  - Tests: `tests/test_research_utils.py` (9 tests)

---

### EXP-009: Convergence-Based Promotion Gate

- **Date:** 2026-03-11
- **Decision:** ADOPT (framework)
- **Hypothesis:** A multi-metric convergence gate (ROI lift + Brier + structural
  checks) is more fair and robust than a CLV-only gate when CLV data is sparse.
- **Methodology:** 3 parallel evaluation agents stress-tested the proposal:
  Agent 1 (metric validity), Agent 2 (blind spots), Agent 3 (statistical power).
  Consensus synthesis produced final gate specification.
- **Results:**
  - All 3 agents: "Adopt with modifications"
  - Power analysis: +2% ROI lift at detection boundary — convergence preferred
  - Brier must be on betted subset (not all games) to complement ROI
  - Edge-outcome ρ reinstated as structural check (2/3 agents favored)
  - Walk-forward OOS computation is existentially critical
- **Gate Specification:**
  - Primary (ALL pass): pooled ROI lift >0%, 3/5 season consistency, do-no-harm
    (-5%), Brier improvement, Brier consistency, sample size ≥200
  - Structural (≥1 pass): edge-outcome ρ >0, edge-bucket monotonicity
  - Hard blocks: ρ <0 → REJECT, augmented-only ROI <-10% → REJECT
- **Key Learning:** Designing the evaluation framework before running the
  evaluation prevents post-hoc rationalization. The gate correctly rejected
  features that showed in-sample promise but OOS failure.
- **Artifacts:**
  - Design docs updated: `docs/plans/2026-03-11-*-design.md` (both)
  - Evaluation script: `scripts/research_evaluation.py`
  - Gate output: `docs/research/promotion_gate_evaluation.md`

---

## MLB Experiments

### EXP-010: MLB Poisson v1

- **Date:** 2026-02-26
- **Decision:** IN PROGRESS (paused for NCAAB tournament)
- **Hypothesis:** Poisson regression on team run-scoring rates produces
  profitable MLB betting model.
- **Methodology:** Log-linear Poisson with park factors, pitcher adjustments.
  Backtest on 2023-2025 (7,505 games, 98.1% odds coverage).
- **Results (preliminary):**
  - Overall accuracy: 56.1%
  - Only positive CLV cell: home favorites (+2.08%)
  - All other cells: negative CLV
- **Next Steps:** Strategy decision → lineup wRC+ → park factor lambda → xFIP
  blending. On hold until after NCAAB tournament.
- **Artifacts:**
  - Research: `docs/mlb/research/` (11 files)
  - Plan: `docs/plans/2026-02-26-poisson-model-v1.md`
  - Database: `mlb_data.db`

---

## Infrastructure Experiments

### EXP-011: Data Sources Survey

- **Date:** 2026-02 (Session 50)
- **Decision:** REFERENCE (ongoing)
- **Hypothesis:** Better odds data sources exist than ESPN BET closing lines.
- **Methodology:** Surveyed 25+ free and paid odds data sources.
- **Results:**
  - SBRO: DOWN (404)
  - OddsHarvester: best OddsPortal scraper
  - Scottfree Analytics: $139 one-time CSV
  - Pinnacle recalculation may improve CLV measurement
- **Pending Actions:** Emails to logical7@cox.net and api@pinnacle.com
- **Artifacts:**
  - Memory: `memory/data_sources_research.md`
  - Reports: `docs/reports/` (6 LLM-assisted research reports)

---

## Experiment Template

Copy this template for new experiments:

```markdown
### EXP-NNN: [Name]

- **Date:** YYYY-MM-DD
- **Decision:** ADOPT | REJECT | PARTIAL | IN PROGRESS | REFERENCE
- **Hypothesis:** [What you expected to find or improve]
- **Methodology:** [How you tested — data, technique, sample size, validation]
- **Results:**
  - [Quantitative findings with numbers]
  - [Statistical significance if applicable]
  - [Comparison to baseline]
- **Key Learning:** [The insight that applies to FUTURE experiments — why it
  worked or didn't, what the result tells us about the domain]
- **Artifacts:**
  - [File paths to code, reports, data, tests]
```

**Guidelines:**

- Assign the next sequential ID (EXP-NNN)
- Always include quantitative results, not just pass/fail
- The "Key Learning" field is the most important — it's what prevents repeating
  mistakes and guides future research direction
- Link ALL artifacts so nothing gets lost
- Update the summary table at the top
- Decision meanings:
  - **ADOPT**: Integrated into production model or workflow
  - **REJECT**: Tested rigorously, does not improve model
  - **PARTIAL**: Some components adopted, others rejected
  - **IN PROGRESS**: Still running or paused
  - **REFERENCE**: Informational, not a model change
