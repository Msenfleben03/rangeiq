# Project: Sports Betting Model Development

Build profitable projection models for NCAAB and MLB achieving positive ROI
through systematic Closing Line Value (CLV) capture.

## Tech Stack

Python 3.11+, pandas, scikit-learn, statsmodels, SQLite, pytest.
See `docs/CODEMAPS/` for module-level architecture. See `docs/RUNBOOK.md` for daily ops.

## Active Tasks

### Phase 7-8 (Mar 7-20): Live testing + MLB data

- [ ] Begin live paper betting tracking (daily_run.py)
- [ ] Backfill 2026 odds (0% coverage currently)
- [ ] NCAAB tournament prep — Selection Sunday Mar 16
- [ ] Schema overhaul Tasks 2-8 — `docs/plans/2026-03-05-schema-overhaul.md`
- [ ] Injury/Divergence overhaul — `docs/plans/2026-02-28-injury-divergence-system.md`

After tournament: MLB pipeline activation (strategy decision, lineup wRC+, park factors).

## Domain Knowledge — CRITICAL

**CLV > Win Rate.** Closing Line Value is the PRIMARY success metric. A bettor who
consistently gets better odds than closing lines WILL profit long-term.

- **De-vig**: `fair_prob = raw_implied / (raw_home + raw_away)`
- **CLV**: `(prob_closing - prob_placed) / prob_placed` — positive = beat the market
- **Kelly**: `(b * p - q) / b * fraction` — use 0.25 fraction (full Kelly too aggressive)
- All formulas in `betting/odds_converter.py`

**Market inefficiency priority:** Player props > small conference > derivatives > main lines

## Gatekeeper — Model Validation

No model reaches production without passing the 5-dimension Gatekeeper
(`backtesting/validators/gatekeeper.py`). **Run when model looks too good.**

| Blocking Check | Threshold |
|----------------|-----------|
| Temporal: no leakage | 0 leaky features |
| Statistical: sample size | >= 200 bets |
| Statistical: Sharpe | >= 0.5 |
| Overfit: in-sample ROI | <= 15% |
| Betting: CLV | >= 1.5% |
| Betting: ruin probability | <= 5% |

## Database

Two SQLite databases. Schema auto-created by `BettingDatabase()` in `tracking/database.py`.
Full schema: `docs/DATA_DICTIONARY.md`.

- **ncaab_betting.db**: bets, bankroll_log, predictions, team_ratings, odds_snapshots,
  barttorvik_ratings, kenpom_ratings, game_log
- **mlb_data.db**: games, game_pitchers, pitcher_stats, lineups, odds_snapshots,
  bets, predictions, park_factors (key: `game_pk`)

No `sport` column — file name identifies sport.

## Bankroll & Sizing

| Parameter | Value |
|-----------|-------|
| Total bankroll | $5,000 (static paper) |
| Kelly fraction | 0.25 (quarter) |
| Max bet | 5% ($250) |
| Min bet | $10 |
| Daily exposure cap | 20% ($1,000) |
| Weekly loss limit | 25% ($1,250) → reduce sizing 50% |
| Monthly loss limit | 40% ($2,000) → pause, full review |

Sized via `KellySizer` with Platt-calibrated probabilities. See `betting/odds_converter.py`.

## Key Results

- **NCAAB Elo+Barttorvik**: OOS flat ROI +27.09% pooled (5 seasons), p=0.0001
- **MLB Poisson v1**: 56.1% acc, home_fav CLV +2.08% (only positive CLV cell)

## Known Dead Ends (do NOT revisit)

| Item | Reason |
|------|--------|
| `sportsipy` library | BROKEN since 2025 — use ESPN API |
| KenPom via cbbdata | Auth BLOCKED (upstream issue #14) — use kenpompy |
| `breadwinner.py` metric | DISABLED — no ROI correlation |
| KenPom year-end as feature | 98.9% redundant with Barttorvik |
| Hurst exponent / Jensen's alpha | Sample size too small / circular |
| Barttorvik 2026 before Feb 17 | Unrecoverable |
| ECC Continuous Learning v2 | INCOMPATIBLE with Windows |
| `test_logger.py` 8 failures | Pre-existing schema mismatch — known, not a blocker |

## Notes for Claude Code

- **Always consider**: "Could this leak future information?"
- Flag overfitting/data leakage risks proactively
- Suggest tests for new functionality
- Default to simpler implementations first
- Run Gatekeeper before approving any model for deployment
- Understand sharp vs soft books, walk-forward vs random CV
- See `docs/CODEMAPS/` for file-level architecture before modifying unfamiliar modules
