# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

RangeIQ is a single-file React artifact (`RangeIQ.jsx`) that runs inside Claude.ai's artifact renderer. It is a professional-grade Texas Hold'em GTO analysis tool that doubles as an LLM fine-tuning data generator. The full spec lives in `Texas_Holdem_GTO_Analysis_App_Prompt.md`.

**Two parallel jobs:**

1. Statistical analysis engine (Flopzilla parity + solver metrics)
2. LLM training data factory (Claude API → JSONL export)

## Directory Note

The directories `scripts/`, `tests/`, `config/`, `data/`, `logs/`, `tracking/`, `dashboards/`, `venv/`, and `archive/` were inherited from a sports-betting project as infrastructure scaffolding. They are **not relevant to RangeIQ development** — ignore them. The `docs/plans/` directory contains design docs and implementation plans for reference. The entire poker codebase is `RangeIQ.jsx`.

The `docs/domain-knowledge-extraction/` directory contains the orchestration workflow and 6 expert-level reference documents for the `rangeiq-poker` skill (deployed to `~/.claude/skills/rangeiq-poker/`). The skill provides domain knowledge for GTO theory, range construction, bet sizing, multi-street planning, exploitative adjustments, and LLM trace quality. Load via the `rangeiq-poker` skill — do not read reference files directly unless the skill routes you there.

## Commands

**Test the artifact**: Paste the contents of `RangeIQ.jsx` into a Claude.ai artifact (React). No build step required.

**Lint markdown** (reference docs):

```sh
pre-commit run markdownlint --all-files
```

**Run all pre-commit hooks** (file hygiene, secret detection):

```sh
pre-commit run --all-files
```

## Current State

### ✅ Done

- **Global architecture**: `useReducer` with single state object, all action types defined
- **Module 1 (Range Builder)**: Fully functional — 13×13 matrix, click+drag, Hero/Villain toggle, 14 presets, combo counters, nut advantage gauge (recharts RadialBarChart)
- **Module 2 (Board & Equity)**: Fully functional — card selector UI, `classifyHand`, `detectDraws` (8 draw types), `runMonteCarlo` (50k iterations, chunked, heroHandFixed mode, per-combo histogram), `boardTexture`, RangeBreakdown bar charts
- **Module 3 (EV Tree)**: Fully functional — auto-generated multi-street tree, recursive EV with corrected GTO seeding, live EV re-stamp on frequency edits, BreakevenPanel, Send to Trace integration, per-street equity via `computeEquityFast`
- **Module 4 (Trace Generator)**: Full API flow — SYSTEM_PROMPT v2, `buildCtx` context serialization, Claude API call, `applyQualityGate` (5-step triage), `rejectedTraces` with `_export_status` tag, batch generation (24-cell `BATCH_BOARD_MATRIX`), `runAuditor` (frequency variance), JSONL export
- **Module 5 (Scenario Library)**: Save/load/tag/export all functional (in-memory)
- **Header**: Persistent with live stats (combos, nut advantage, trace count), module tabs
- **Keyboard shortcuts**: 1-5 module switch, C clear range, R run MC
- **Design system**: Dark theme with all CSS variables applied, monospace numerical output
- **P0 (Analytical Accuracy)**: Per-combo equity histogram, polarity index, per-street equity re-estimation via `computeEquityFast`
- **P1 (Batch + Quality)**: Batch generation, quality gate, SYSTEM_PROMPT v2, trace auditor, rejected trace export

### 🔧 Needs Implementation (priority order)

#### P1.5 — DPO Preference Pair Pipeline

Spec: `docs/superpowers/specs/2026-03-22-dpo-preference-pairs-design.md`
Plan: `docs/superpowers/plans/2026-03-22-dpo-preference-pairs.md`

1. **`scoreTrace`**: Quality score (0-100) for ranking traces within a `game_state_key` group
2. **`buildPreferencePairs`**: 1:1 best-worst matching of accepted vs rejected traces (≥2 rejection reasons), Standard DPO/TRL format
3. **`exportDPO`**: JSONL download of `{prompt, chosen, rejected, metadata}` pairs
4. **Adaptive batch loop**: Per-cell retry up to 5 attempts to ensure ≥1 accepted + ≥1 qualified rejected trace, using `useRef` accumulators to avoid stale closure reads
5. **UI**: Pair counter in stats row, "Export DPO" button (purple)

#### P2 — Module 3 Minor Deferred

1. **siblingCollapse**: Implement actual collapse behavior in `TreeNode` (checkbox exists but prop not consumed)
2. **Controlled sizings input**: Replace `defaultValue` with controlled `value` + `onChange`
3. **Overbet nodes**: Extend `betSizings` default to `[0.33, 0.66, 1.0, 1.5]`; requires capped-range detection for when overbets are structurally justified
4. **SPR-conditioned betSizings**: At SPR <3 collapse to `[1.0]`, SPR 3-6 use `[0.66, 1.0]`, SPR >6 use full array
5. **Position-adjusted equity**: Apply OOP dampening to `equityAssumption` (~80% realization factor for OOP nodes)

#### P3 — Module 1 Enhancements

1. Ctrl+click for partial inclusion % (0-100%) per cell
2. Preflop all-in equity (requires Monte Carlo)
3. Population-calibrated presets: Add `"Pop BB def vs BTN"`, `"Pop CO RFI"`, `"Pop BTN RFI"` reflecting pool deviations

#### P4 — Future: Fine-Tuning Pipeline Infrastructure

1. **Solver output ingestion MCP server**: Read PioSOLVER/GTO Wizard exports (.cfr, .csv), expose as structured data for frequency validation, solver-informed trace generation, and hybrid dataset construction
2. **`range_source` field in trace context**: Track whether villain range is `"gto" | "population" | "custom"` so traces carry provenance
3. **`villainProfile` exploitative mode for `buildTree`**: Accept population stat overrides for fold/call/raise frequencies; store `frequency_source: "gto" | "exploitative"` per node

## Code Conventions

### Single-File Constraint

Everything must be in `RangeIQ.jsx`. No separate CSS, no modules. Available imports:

- `react` (hooks), `recharts`, `lucide-react`, `lodash`, `d3`

### State Management

Single `useReducer` at top level. All mutations through `dispatch`. New actions: `case "NEW_ACTION": return { ...state, newField: action.payload };`

### Styling

Inline styles using the `T` theme object — no Tailwind (artifact renderer doesn't compile it):

```js
T.bgPrimary  // #0d1117
T.bgCard     // #161b22
T.bgElevated // #21262d
T.border     // #30363d
T.blue       // #58a6ff  (Hero color)
T.green      // #3fb950  (+EV, success)
T.red        // #f85149  (Villain, -EV, red suits)
T.yellow     // #d29922  (warnings, premiums)
T.purple     // #bc8cff  (overlap)
T.text       // #e6edf3
T.muted      // #8b949e
```

### Shared Components

- `Btn` — standard button with active/disabled states
- `Card` — container with bgCard background + border
- `Label` — uppercase muted label
- `Stat` — centered label + large value display
- `CardSelector` — card picker with dead-card exclusion
- `TreeNode` — recursive EV tree row renderer (Module 3)
- `BreakevenPanel` — sticky BE%/GTO metrics side panel (Module 3)

All computed metrics: **2 decimal places** (`.toFixed(2)`). Monospace font for numbers.

### API Calls

Model: `claude-sonnet-4-20250514`. No API key needed (artifact runtime injects it). Always parse `data.content[0].text` and handle JSON parse errors.

## Key Utilities Already Built

```js
// ── Range & card utilities ──
RANKS          // ["A","K","Q","J","T","9","8","7","6","5","4","3","2"]
SUITS          // ["s","h","d","c"]
DECK           // all 52 cards as ["As","Ah",...,"2c"]
matrixLabel(row, col)  // → "AKs", "TT", "87o" etc
combosFor(hand)        // → 6 (pair), 4 (suited), 12 (offsuit)
expandHand(hand, deadCards)  // → [[card,card],...] specific combos
totalCombos(rangeSet)  // → integer total combo count
countPremiums(rangeSet) // → combo count of AA/KK/QQ/AKs/AKo
parsePreset(str)       // → Set from comma-separated hand string
PRESETS                // object of all 14 preset range strings

// ── Hand evaluation (Module 2) ──
classifyHand(holeCards, board)  // → { category, strength, draws[] }
detectDraws(holeCards, board)   // → string[] of draw types
evalHand7(cards)                // → { rank, tiebreak[] } for 7-card hand
compareHands(h1, h2)            // → 1 / -1 / 0
runMonteCarlo(heroRange, villainRange, board, deadCards, iterations, dispatch, heroHand)
boardTexture(board)             // → { wetness, connectivity, flushTexture }

// ── Per-street equity (P0) ──
computeEquityFast(heroCombos, villainCombos, board, N)
  // → quick equity estimate for turn/river re-estimation in buildTree

// ── EV Tree (Module 3) ──
makeNodeId(parentId, action, sizing)  // → deterministic node ID
buildTree({ potSize, effStack, betSizings, equity, street, depth, parentId, heroInvestment })
  // → array of root-child nodes with GTO-seeded frequencies
computeNodeEV(node)             // → EV in bb (recursive)
stampEV(nodes)                  // → nodes array with ev stamped on every node
buildAncestorChain(leafId)      // → array of ancestor node IDs (root → leaf)

// ── Trace Pipeline (Module 4) ──
BATCH_BOARD_MATRIX             // 24-cell coverage matrix (12 textures × 2 SPR)
SYSTEM_PROMPT_V2               // Tier 2 expert prompt for trace generation
buildCtx(board, pot, stack, equity, texture, spr)  // → context object for API call
applyQualityGate(trace, record)  // → {accepted, reasonCount}; dispatches ADD_REJECTED_TRACE on fail
generateTrace({ overrides })   // → "accepted"|"rejected_qualified"|"rejected_unqualified"|"error"
generateBatch()                // → adaptive loop over BATCH_BOARD_MATRIX
runAuditor()                   // → groups traces by game_state_key, computes freq variance
exportJSONL()                  // → download accepted traces as JSONL
```

## Module 3 — EV Tree Architecture

### Node shape

```js
{
  id: string,                    // deterministic: "root__bet_66__villain_call__..."
  street: "flop"|"turn"|"river",
  action: string,                // "check"|"bet"|"villain_bet"|"villain_fold"|"villain_call"|"villain_raise"|"hero_fold"|"hero_call"|"check_behind"
  betSize: number,               // fraction of pot (0.33, 0.66, 1.0)
  betSizeBb: number,             // absolute bb
  potAfter: number,              // pot in bb after this action resolves
  heroInvestmentAfter: number,   // cumulative hero investment
  villainFoldPct: number,        // editable, GTO-seeded
  villainCallPct: number,        // editable, GTO-seeded
  villainRaisePct: number,       // editable, seeded at 10
  heroFoldToRaise: number,       // editable, seeded from pot odds formula
  equityAssumption: number,      // 0-1, from MC if available else 0.5
  equity_is_approximated: boolean, // true when street !== "flop"
  ev: number | null,             // null until stampEV runs
  expanded: boolean,
  isLeaf: boolean,
  children: [node, ...]
}
```

### GTO seeding formulas

```
Villain fold% (hero bets S into pot P):   S / (P + 2S)
Villain call% (hero bets S into pot P):   (P + S) / (P + 2S)
Raise% default:                           10 (adjustedCallPct = callPct - 10)
heroFoldToRaise (raise size R):           1 − (R−S) / (P + 2R)
```

### Trace serialization

Module 3 selected line is stored in `state.evTreeConfig.evTreeLine` and included in Module 4's `decision_context.ev_tree_line`. Each node in the serialized line includes `equity_is_approximated: true` when `street !== "flop"` — training data consumers must respect this flag.

## Poker Logic Notes

**Hand evaluation priority** — check in order, first match wins:
straight flush → quads → full house → flush → straight → three of a kind → two pair → one pair → high card

Sub-classify one pair: overpair / top pair / middle pair / bottom pair / underpair by comparing hole card ranks to board ranks.

**Rank ordering**: A=14, K=13, Q=12, J=11, T=10, 9-2 face value. Ace also low for A-2-3-4-5 straight.

**Flush detection**: Count suits across all 7 cards. ≥5 of one suit = flush. Draws: 4 to a flush = FD, 3 to a flush with 2 board cards of that suit = backdoor FD.

**Straight detection**: Convert to rank numbers, sort, deduplicate, find runs of 5. Draws: 4 consecutive = OESD, 4-card span with 1 gap = gutshot, two gaps in 5-card span = double gutshot.

**Monte Carlo**: Per iteration — pick random hero combo, random villain combo (no card overlap with each other, board, or dead cards). Deal remaining board cards. Evaluate both 7-card hands. After all iterations divide by total.

## Common Gotchas

1. **Card overlap**: Always filter dead cards when expanding ranges. `expandHand(hand, deadCards)` handles this.
2. **Ace-low straights**: Include Ace as both 14 and 1 when checking straights.
3. **Matrix orientation**: Row < Col = suited, Row > Col = offsuit, Row == Col = pair. `matrixLabel()` handles this.
4. **Monte Carlo blocking UI**: MUST chunk via `setTimeout` (5k iterations/chunk). A tight loop of 50k will freeze the artifact.
5. **No localStorage**: Artifacts cannot use localStorage/sessionStorage. All persistence is in-memory React state only.
6. **recharts sizing**: Always wrap charts in `<ResponsiveContainer>` with explicit width/height on the parent div.
7. **EV tree equity**: `equity_is_approximated = true` on all nodes where `street !== "flop"`. Static equity is intentional for the prototype — do not attempt per-street MC re-estimation without flagging it clearly.
8. **EV re-stamp**: `UPDATE_EV_NODE_FREQ` calls `stampEV` after patching — EV updates live. `buildTree` + `stampEV` are the two entry points; never mutate node EVs directly.
9. **villain_bet vs bet in computeNodeEV**: `"bet"` (hero bets) and `"villain_bet"` (villain donks) are handled by separate branches. Do not merge these conditions — they have different child structures.
10. **Stale closures in async loops**: `dispatch` enqueues React state updates — closed-over arrays (`traceQueue`, `rejectedTraces`) are stale inside async batch loops. Use `useRef` accumulators to track within-batch state. See `batchAcceptedRef`/`batchRejectedRef` in `generateBatch`.
11. **Quality gate return shape**: `applyQualityGate` returns `{accepted: bool, reasonCount: number}`, not a plain boolean. Always destructure the result.

## Design Docs

- `docs/superpowers/specs/` — approved design specs (brainstormed + reviewed)
- `docs/superpowers/plans/` — implementation plans (task-level, with code)
- `docs/plans/` — legacy design docs (Module 3)

## Reference Files (domain context, not code)

- `Texas_Holdem_GTO_Analysis_App_Prompt.md` — full spec (source of truth)
- `ABC_Poker_The_Simple_Strategy_In_2026__SplitSuit_Poker.md` — ABC strategy, default ranges
- `Poker_Bluffing_Made_Easy_In_2026__SplitSuit.md` — BE%, fold frequency, multi-street bluffs
- `Poker_Combos___Blockers_101_In_2026__SplitSuit_Poker.md` — 6-3-1-0 rule, combo counting
- `The_Preflop_Poker_Checklist_In_2026__SplitSuit_Poker.md` — PLANES framework, SPR
- `Why_A_Poker_Math_Approach_Is_Best_In_2026__SplitSuit_Poker.md` — EV, BE%, frequencies
- `docs/plans/2026-03-14-module3-ev-tree-design.md` — Module 3 approved design doc
- `docs/plans/2026-03-14-module3-ev-tree-impl.md` — Module 3 implementation plan

**Expert domain knowledge** (access via `rangeiq-poker` skill, not directly):
- `docs/domain-knowledge-extraction/references/solver-theory-gto.md` — CFR convergence, abstraction distortions, indifference principle, trace generation interpretation
- `docs/domain-knowledge-extraction/references/range-construction.md` — equity distribution/polarity, nut advantage asymmetry, blocker math, population ranges
- `docs/domain-knowledge-extraction/references/bet-sizing-theory.md` — geometric sizing, polarity-sizing, SPR thresholds, overbet theory, donk bets
- `docs/domain-knowledge-extraction/references/multi-street-planning.md` — equity realization, commitment thresholds, range narrowing, blocker cascade, bluff coherence
- `docs/domain-knowledge-extraction/references/exploitative-adjustments.md` — deviation thresholds, population profiles, counter-exploit risk, Bayesian range updates
- `docs/domain-knowledge-extraction/references/trace-quality-finetuning.md` — fluency-accuracy gap, coverage architecture, SYSTEM_PROMPT engineering, dataset curation
