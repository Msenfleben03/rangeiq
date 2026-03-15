---
title: "RangeIQ Poker Skill — Extraction Task Tracker"
created: 2026-03-15
modified: 2026-03-15
type: project
status: active
tags:
  - poker/gto/theory
  - workflow/knowledge-extraction
  - projects/rangeiq
---

# RangeIQ Poker Skill — Extraction Task Tracker

> [!abstract] Summary
> Per-domain execution status, quality tier, and cross-domain summaries for the
> RangeIQ poker skill extraction workflow. Updated by the controller after each
> domain completes rubric and cross-domain review.

## Execution Status

| # | Domain Name | Output File | Status | Quality Tier | Notes |
|---|-------------|-------------|--------|--------------|-------|
| 1 | Solver Theory and GTO Equilibrium | `references/solver-theory-gto.md` | ✅ DONE | Practitioner | Rubric: ACCEPT_WITH_DISTINCTION, 0 iterations |
| 2 | Range Construction and Equity Distribution | `references/range-construction.md` | ✅ DONE | Practitioner | Rubric: ACCEPT_WITH_DISTINCTION, 0 iterations; Cross-domain: MINOR_EDITS applied |
| 3 | Bet Sizing Theory and Pot Geometry | `references/bet-sizing-theory.md` | ✅ DONE | Practitioner | Rubric: ACCEPT_WITH_DISTINCTION, 0 iterations; Cross-domain: MINOR_EDITS (2) applied |
| 4 | Multi-Street Planning and EV Architecture | `references/multi-street-planning.md` | ⬜ PENDING | — | — |
| 5 | Exploitative Adjustments and Population Dynamics | `references/exploitative-adjustments.md` | ⬜ PENDING | — | — |
| 6 | LLM Trace Quality and Fine-Tuning Architecture | `references/trace-quality-finetuning.md` | ⬜ PENDING | — | Integration domain |

Status codes: ⬜ PENDING → 🔄 IN PROGRESS → ✅ DONE → ⚠️ DONE_WITH_CONCERNS → 🚫 BLOCKED

## Cross-Domain Summaries

*Controller writes each 200-word summary after a domain passes review. These summaries
are the ONLY domain content passed to subsequent subagents — not the full documents.*

### Domain 1: Solver Theory and GTO Equilibrium

CFR convergence requires street-specific iteration budgets: 500–1k for river nodes, 10k–50k for turn, 50k–200k+ for flop. Premature stopping produces strategy artifacts — hands that appear to mix when they should be pure, with frequencies trending but unsettled. Commercial solver abstraction (card isomorphisms, bet-size bucketing, stack-size rounding) creates predictable distortions on off-suit disconnected boards with awkward runouts, near SPR thresholds, and off-bucket bet sizes like 45% pot. PioSOLVER custom runs and GTO Wizard prebuilt solutions diverge measurably on the same spot due to different abstraction choices. The indifference principle means mixed-strategy hands are EV-equivalent between actions — implementing mixing deterministically by hand strength (rather than randomization) creates detectable patterns. Multi-way pots break the 2-player zero-sum Nash framework: correlational exploitation makes solver multi-way outputs directionally wrong, not just imprecise — RangeIQ's 2-player EV tree is architecturally correct to avoid this. For trace generation, the key solver output fields are EV delta between actions, frequency stability across runouts, and range-wide indifference boundaries — these explain *why* a play is GTO. Traces that copy frequencies without structural reasoning produce fine-tuning noise. GTO strategies are stateless (no session history) — traces referencing "I've been aggressive" signal LLM hallucination. Board texture features like wetness score can produce identical values (e.g., wetness=4) on boards requiring radically different strategies.

### Domain 2: Range Construction and Equity Distribution

Equity distribution shape (polarity) drives bet sizing, not aggregate equity. `runMonteCarlo` returns mean equity, destroying the bimodal/merged distribution that determines optimal sizing. A polarity proxy from `classifyHand` buckets (value/marginal/air) approximates this: ratio >0.70 = polar (large bets), <0.50 = merged (small bets). Two Pair classification must be board-texture-conditioned — value on dry boards (wetness<3), marginal on wet. Nut advantage diverges from range advantage on specific textures: monotone low boards, ace-high dry boards, and K-high disconnected boards where the raiser has nut concentration but lower total equity — large sizings are correct despite equity disadvantage. OOP nut advantage is worth less due to 60-80% equity realization vs 100-110% IP. Preflop A5s-over-A8s in EP ranges is about range construction roles (wheel equity, nut-low blockers, domination resistance), not hand strength. Blocker effects are continuous probability shifts: A5s reduces villain's continuing range ~25% vs K5s's ~15%, yielding ~3-5% more fold equity. Population ranges deviate systematically from GTO: BB defense ~42-48% vs GTO 55-60%, EP 3-bet ~6-8% vs GTO 10-12%. Using GTO villain ranges in `runMonteCarlo` when modeling real opponents produces equity calibrated to phantom opponents. The `histogram: null` field in MC output is the key gap — implementing per-combo equity tracking enables polarity index and postflop nut advantage computation.

### Domain 3: Bet Sizing Theory and Pot Geometry

Geometric bet sizing formula `b = ((S_eff/P)^(1/N) - 1) / 2` assumes villain calls all N streets. This breaks on static boards (K-7-2, A-8-3 rainbow) where top-pair calling drops 40-60% between turn and river — use N-1 and recalculate. Threshold: does >20% of villain's range call a river bet after calling flop+turn? If not, reduce N. Polarity index drives sizing: PI >0.70 = large (66-100%), PI 0.50-0.70 = medium (33-66%), PI <0.50 = small (25-33%). The "wet board = small bet" heuristic inverts on paired boards (merged ranges despite high wetness), monotone boards (flush-draw-heavy range bets large to deny equity), and low-card boards favoring preflop aggressor's overpair concentration. Overbets (>100% pot) require capped villain range + uncapped hero range — `buildTree` caps at 1.0x and needs `betSizings` extension to [0.33, 0.66, 1.0, 1.5]. SPR thresholds change strategy regime: <2 = commit, 2-6 = one-street commit, 6-15 = standard multi-street, >15 = implied-odds dominant. 3-bet pots have SPR 3-5x lower than single-raised pots — same-sizing logic fails across pot types. Donk bets are GTO at 3-8% but exploitatively profitable at higher frequencies on paired/low boards where preflop caller has range advantage. The `computeNodeEV` max operator on check-node children conflates hero's and villain's decisions — villain-action children should be frequency-weighted.

### Domain 4: Multi-Street Planning and EV Architecture

*(Write after Domain 4 passes cross-domain review)*

### Domain 5: Exploitative Adjustments and Population Dynamics

*(Write after Domain 5 passes cross-domain review)*

## Quality Checkpoint Log

*Controller records rubric iterations and cross-domain outcomes here.*

| Domain | Rubric Iterations | Cross-Domain Outcome | Issues Resolved |
|--------|------------------|---------------------|-----------------|
| 1 | 0 | N/A (foundation) | None |
| 2 | 0 | MINOR_EDITS (4 cross-refs applied) | Indifference principle link, deterministic-mixing warning, equity realization note, approximation flag ref |
| 3 | 0 | MINOR_EDITS (2 cross-refs applied) | Two Pair wetness bucketing in PI calc, raisePct=10 distortion ref |
| 4 | — | — | — |
| 5 | — | — | — |
| 6 | — | — | — |

## Final Quality Checklist

Before calling the skill complete:

- [ ] All 6 reference files exist in `references/`
- [ ] Every file achieved Expert tier minimum on rubric review
- [ ] Cross-domain reviewer approved bidirectional references for domains 2–6
- [ ] No file contains content below the floor (no definitions of table-stakes concepts)
- [ ] Each "Implementation Notes" section names specific RangeIQ functions/modules
- [ ] Each "Looks Right But Isn't" section has at least 2 deployment-specific traps
- [ ] `SKILL.md` routes to specific reference files per task — no "load everything" guidance
- [ ] skill-judge evaluation passes at 90+/120

## Related Notes

- [[RangeIQ Poker Knowledge Prompt]]
- [[RangeIQ Poker Skill Orchestration Guide]]
- [[RangeIQ Poker Skill Session Context]]
