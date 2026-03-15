---
name: rangeiq-poker
description: "Expert-level Texas Hold'em GTO domain knowledge for RangeIQ development. Use when: designing or modifying EV tree architecture (buildTree, computeNodeEV, stampEV), debugging equity or Monte Carlo outputs (runMonteCarlo, classifyHand, boardTexture), engineering poker reasoning traces for LLM fine-tuning (Module 4 SYSTEM_PROMPT, JSONL pipeline), evaluating trace quality against solver ground truth, architecting the production fine-tuning dataset, working with bet sizing theory (geometric sizing, polarity index, SPR thresholds), range construction (nut advantage, blocker math, population-calibrated ranges), multi-street EV planning (equity realization, commitment thresholds, range narrowing), or exploitative frequency adjustments (deviation thresholds, population profiles, counter-exploit risk). Covers solver theory, range construction, bet sizing, multi-street planning, exploitative adjustments, and trace quality."
---

# RangeIQ Poker — Domain Knowledge Skill

## Floor

This skill assumes you already have:

- Monte Carlo equity engine (`runMonteCarlo`, 50k iterations, chunked setTimeout)
- Hand evaluation (`evalHand7`, `classifyHand`, `detectDraws`)
- Combo math (`combosFor`, `expandHand`, 6-3-1-0 rule, unseen×unseen multiplication)
- Board texture (`boardTexture`: wetness, connectivity, flushTexture, isPaired)
- EV tree (`buildTree`, `computeNodeEV`, `stampEV`, GTO-seeded frequencies)
- Breakeven math (BE%=S/(S+P), GTO bluff freq, bluff:value ratio)
- PLANES preflop framework, ABC poker baseline
- JSONL trace pipeline (Module 4) with Claude API integration

## NEVER

Violating these destroys EV accuracy, trace quality, or fine-tuning dataset integrity:

- **NEVER treat `equityAssumption` in `buildTree` as position-neutral** — OOP equity realization is ~20% lower than IP; unadjusted equity systematically overstates OOP EV nodes
- **NEVER apply geometric bet sizing on boards where opponent's calling range doesn't span all streets** — the formula assumes three streets of calls; verify range composition before applying
- **NEVER use total range equity (mean) as a proxy for bet sizing decisions** — equity distribution variance (polarity) drives sizing, not equity average; two ranges with identical mean equity can require completely different bet sizes
- **NEVER include all generated traces in the fine-tuning dataset without quality filtering** — low-quality traces at volume shift model calibration toward fluent nonsense; EV alignment and action consistency checks are required gates
- **NEVER adjust exploitatively on samples under 50 hands for >15pp deviations or under 200 hands for 5–15pp deviations** — you are likely adjusting to sampling variance, not a true tendency

## Diagnose Before Loading References

Ask these in order to load only relevant domains:

1. Are you working on EV tree accuracy, equity computation, or solver output interpretation?
   → Load `references/solver-theory-gto.md` + `references/multi-street-planning.md`

2. Are you working on range inputs to Monte Carlo or nut/range advantage metrics?
   → Load `references/range-construction.md`

3. Are you working on bet sizing logic, `betSizings` parameter selection, or overbet nodes?
   → Load `references/bet-sizing-theory.md`

4. Are you working on multi-street EV tree design, commitment thresholds, or equity realization?
   → Load `references/multi-street-planning.md`

5. Are you working on population-calibrated inputs, exploitative frequency adjustments, or deviation thresholds?
   → Load `references/exploitative-adjustments.md`

6. Are you working on Module 4 system prompt quality, trace generation, dataset curation, or fine-tuning pipeline architecture?
   → Load `references/trace-quality-finetuning.md` + `references/solver-theory-gto.md`

**Default fallback:** If the task doesn't clearly match one domain above, load `references/solver-theory-gto.md` + `references/trace-quality-finetuning.md` — these are the two highest-connectivity documents and cover the most common cross-domain questions.

**Multi-domain tasks:** If the task spans bet sizing + range construction (common), load both references. If it spans EV tree + trace quality (also common), load `references/multi-street-planning.md` + `references/trace-quality-finetuning.md`.

## Quick Decision Trees (No Reference Loading Needed)

**EV Tree Debugging — Is the EV output wrong?**
1. Is `equity_is_approximated: true` on the node? → Equity is stale from flop MC; turn/river EV is unreliable
2. Is `villainFoldPct` close to MDF formula output? → It's a heuristic seed, not solver-verified; can deviate 10-20pp on range-asymmetric boards
3. Is `raisePct` = 10? → Hardcoded; actual raise frequency is 3-25% depending on board texture
4. Is hero OOP? → Raw equity overstates OOP EV by ~20%; `equityAssumption` should be position-adjusted
5. Is the board paired with identical wetness score to an unpaired board? → `boardTexture.wetness` collapses distinct strategic categories; check `isPaired` separately

**Trace Quality Triage — Should this trace enter the dataset?**
1. Does the trace reference session history ("I've been aggressive")? → REJECT — GTO hallucination
2. Does it classify a draw as "value"? → REJECT — concept-correct, conclusion-wrong
3. Does `frequency_recommendation_pct` diverge >15pp from `ev_tree_line` node frequencies? → REJECT — hallucinated frequency
4. Is `ev_tree_line` null? → Flag as unanchored — no consistency guarantee
5. Does the board texture appear in <15 other traces in the batch? → Flag for coverage gap — under-represented texture

## Domain References

**For solver output interpretation, multi-way EV, abstraction limitations, trace ground truth:**
→ MANDATORY: Read `references/solver-theory-gto.md` completely.
→ Do NOT load: `references/exploitative-adjustments.md` (unrelated context)

**For range composition inputs, nut advantage analysis, blocker-adjusted combo counts:**
→ MANDATORY: Read `references/range-construction.md` completely.
→ Do NOT load: `references/multi-street-planning.md` unless crossing into multi-street equity realization

**For bet sizing parameter selection, polarity index interpretation, overbet design:**
→ MANDATORY: Read `references/bet-sizing-theory.md` completely.
→ Also load: `references/range-construction.md` §Polarity Index for the equity distribution input

**For EV tree architecture, equity realization adjustment, commitment threshold design:**
→ MANDATORY: Read `references/multi-street-planning.md` completely.
→ Also load: `references/bet-sizing-theory.md` §SPR Thresholds

**For frequency adjustment logic, population-calibrated range inputs, deviation thresholds:**
→ MANDATORY: Read `references/exploitative-adjustments.md` completely.
→ Also load: `references/range-construction.md` §Population-Calibrated Ranges

**For Module 4 system prompt engineering, trace quality evaluation, dataset composition:**
→ MANDATORY: Read `references/trace-quality-finetuning.md` completely.
→ Also load: `references/solver-theory-gto.md` §Solver Output Interpretation for Trace Generation

## Quick-Reference: Most Critical Non-Obvious Rules

**Solver Theory:** CFR convergence and practical stability are different — premature solver stopping creates strategy artifacts, not noise. Multi-way spots are conceptually broken in 2-player solvers, not just imprecise. The indifference principle tells you about range brackets, not just the mixed hand.

**Range Construction:** Equity distribution variance (polarity) matters more than equity mean for strategy. The range with higher nut advantage sometimes has lower total equity — this produces counterintuitive bet sizing implications. Blocker effects are probability shifts (reduces combos by X%), not binary events.

**Bet Sizing:** Geometric sizing fails when opponent's calling range doesn't span all streets. Wet board ≠ small bet in all cases — paired boards and monotone boards often invert this. Overbets require specific range asymmetry conditions, not just aggression intent.

**Multi-Street Planning:** `equityAssumption` should be position-adjusted (~20% IP/OOP gap). Range narrowing across streets makes constant equity inputs increasingly wrong at turn/river. `equity_is_approximated: true` is signaling static equity — not an adequate substitute for range-conditional equity.

**Exploitative Adjustments:** Deviation threshold sample sizes are non-trivial: 50 hands minimum for >15pp deviations, 200+ for 5–15pp. Counter-exploit exposure scales with deviation magnitude — aggressive exploits create large counter-exploit windows. Population profiles differ by stake level in predictable, specific ways.

**Trace Quality:** Solver-computed decisions are required as ground truth — expert human annotations are insufficient. Coverage architecture must span 12+ board texture profiles or the fine-tuned model over-bets on under-represented textures. Quality filtering is required before any trace enters the dataset.

## Error Handling

- **Reference file missing:** If a `references/*.md` file doesn't exist, do NOT proceed without it. The reference files contain the expert knowledge — SKILL.md alone provides routing, not domain depth. Alert the user that the reference needs to be regenerated.
- **Task spans all 6 domains:** Do NOT load all references. Use the Quick Decision Trees above for triage, then load at most 2-3 references for the specific sub-questions. Context budget matters more than completeness.
- **Conflicting guidance between references:** SPR threshold tables differ between bet-sizing-theory.md (4-tier, sizing-focused) and multi-street-planning.md (5-tier, commitment-focused). These are complementary, not contradictory — use the table matching your current question.

## Known Dead Ends

- **Monte Carlo as a polarity metric** — aggregate equity from `runMonteCarlo` cannot be used to compute equity distribution variance (polarity); requires combo-level breakdown from `classifyHand` output
- **GTO ranges as opponent range inputs** — using GTO ranges as villain inputs to `runMonteCarlo` produces incorrect equity against real opponents who play non-GTO; use population-calibrated ranges
- **Static equity in turn/river EV nodes** — holding equity constant across streets is known-inaccurate; the `equity_is_approximated` flag documents this but does not fix it; multi-street accuracy requires per-street MC re-runs

## Related Notes

- [[RangeIQ Poker Knowledge Prompt]]
- [[RangeIQ Poker Skill Orchestration Guide]]
- [[RangeIQ CLAUDE]]
- [[NCAA Projection Modeling Knowledge Prompt]]
