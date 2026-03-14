# Module 3 EV Tree — Design Document

**Date:** 2026-03-14
**Status:** Approved

---

## Overview

Module 3 implements a multi-street EV tree builder for Texas Hold'em post-flop analysis.
The tree auto-generates from configurable parameters (pot, stack, bet sizings) and computes
recursive EV at each node. Its primary outputs are:

1. Per-node EV in bb, BE%, and exploitability score for in-session analysis
2. Serialized action-line JSON that feeds Module 4 trace generation for model training

The long-term value of this module is **throughput of structured training data**: one board +
range set → dozens of distinct EV-annotated action lines, each a valid JSONL trace.

---

## Data Model

### Node Shape

```js
{
  id: string,                    // e.g. "flop-bet66-villain_call-turn_check"
  street: "flop"|"turn"|"river",
  action: "check"|"bet"|"raise"|"fold"|"call",
  betSize: number,               // fraction of pot (0.33, 0.66, 1.0), 0 for check
  betSizeBb: number,             // absolute bb, derived
  potAfter: number,              // pot in bb after this action resolves
  heroInvestmentAfter: number,   // cumulative hero investment after this action
  villainFoldPct: number,        // 0-100, user-editable
  villainCallPct: number,        // 0-100, user-editable
  villainRaisePct: number,       // derived: 100 - fold - call (clamped >= 0)
  heroFoldToRaise: number,       // 0-100, derived from pot odds, user-editable
  equityAssumption: number,      // hero equity (0-1), from MC if available
  equity_is_approximated: boolean, // true when street !== "flop"
  ev: number | null,             // computed by computeNodeEV, null until built
  expanded: boolean,             // UI collapse state
  children: [node, ...]          // recursive
}
```

### State Shape (additions to evTreeConfig)

```js
evTreeConfig: {
  potSize: 6,           // bb, user-configurable
  effStack: 100,        // bb, user-configurable
  betSizings: [0.33, 0.66, 1.0],  // fractions, user-editable as comma-separated input
  nodes: [],            // root children (the generated tree)
  selectedLine: [],     // array of node IDs representing chosen root-to-leaf path
  siblingCollapseEnabled: false,  // toggle, default OFF
}
```

---

## Tree Generation

### `buildTree(params)` — called on "Build Tree" click

```
params: { potSize, effStack, betSizings, equity, street, depth }
```

Max depth = 3 (flop → turn → river). Stops recursing when:
- `depth >= 3`
- `heroInvestmentAfter >= effStack` (stack committed)

**Root children at each street:** Check node + one Bet node per sizing.

**Check node children:** Check-behind (showdown leaf) + one Bet node per sizing (villain leads).

**Bet node children:** three villain responses:
- Fold (leaf) — `potAfter = potBefore + herosBet, villainFolds`
- Call (recurses to next street) — `potAfter = potBefore + 2×herosBet`
- Raise (spawns hero-response pair)

**Villain response sizing:** Raise defaults to 2× hero's bet (standard min-raise). User-editable.

**Default villain frequencies (GTO seeding):**
```
foldPct  = S / (P + S)      // S = bet size, P = pot before hero bets
callPct  = P / (P + S)      // villain's pot odds
raisePct = 0                // user adjusts from callPct
```
Where raise% reduces callPct: `callPct = P/(P+S) - raisePct`, clamped >= 0.

**Default heroFoldToRaise:**
```
heroFoldToRaise = 1 − (R−S) / (P+R)
```
R = villain raise size (total), S = hero's original bet, P = pot before hero's bet.
Derived from hero's pot odds facing the raise. User-editable per raise node.

---

## Pot and Investment Propagation

`buildTree` computes and stores `potAfter` and `heroInvestmentAfter` on every node.

| Event | potAfter | heroInvestmentAfter |
|---|---|---|
| Hero bets S into pot P | P + S | prev + S |
| Villain calls hero's bet S | P + 2S | unchanged |
| Villain raises to R | P + S + R | unchanged (hero hasn't acted yet) |
| Hero folds to raise | P + S + R | prev (hero loses this amount) |
| Hero calls raise (adds R−S) | P + 2R | prev + (R−S) |
| Check/check (showdown) | P unchanged | unchanged |

`computeNodeEV` uses `node.potAfter` and `node.heroInvestmentAfter` directly — no caller
needs to thread these through the recursive signature.

---

## EV Computation

### `computeNodeEV(node, equity)` — recursive, post-order

```
Leaf nodes:
  fold (villain folds to hero bet):
    EV = node.potAfter (hero wins pot)

  fold (hero folds to villain raise):
    EV = −node.heroInvestmentAfter

  call/showdown:
    EV = equity × node.potAfter − (1−equity) × node.heroInvestmentAfter

Internal bet node:
  foldEV  = computeNodeEV(foldChild, equity)
  callEV  = computeNodeEV(callChild, equity)
  raiseEV = heroFoldToRaise × computeNodeEV(heroFoldChild, equity)
           + (1−heroFoldToRaise) × computeNodeEV(heroCallChild, equity)

  EV = (foldPct/100) × foldEV
     + (callPct/100) × callEV
     + (raisePct/100) × raiseEV

Check node:
  checkBehindEV = computeNodeEV(showdownLeaf, equity)
  leadBetEV     = max(computeNodeEV(betChild, equity) for each sizing)
  EV = max(checkBehindEV, leadBetEV)  [or display both, not auto-select]
```

**Equity source priority:**
1. Module 2 MC result (heroEq from runMonteCarlo) if available
2. Default 0.50

**Multi-street equity:** Same equity value used at all depths. `equity_is_approximated = true`
on all nodes where `street !== "flop"`. This flag appears in both UI and serialized JSON.

---

## UI Components

### Control Panel (top)
- Pot size (bb) + Effective stack (bb) — existing inputs
- Bet sizings: text input, comma-separated fractions (e.g. `0.33, 0.66, 1.0`)
- Equity source badge: `MC: 51.3%` or `Default: 50.0%`
- **"Build Tree"** button → runs buildTree + computeNodeEV
- Sibling collapse toggle (default OFF)

### Tree Renderer — recursive `TreeNode` component
- Root children visible on load; all others collapsed (user expands)
- Each node row: `[indent] [action+sizing label] [potAfter bb] [BE%] [EV bb] [⚠ if approximated]`
- Frequency inputs inline: fold% + call% (two free fields); raise% = 100−fold−call, shown read-only
- `heroFoldToRaise` input appears on raise nodes only
- Click node: expand/collapse children
- Click+Shift (or separate "Select" button): add node to selectedLine (enforces ancestor chain)
- Selected line highlighted in blue

### Breakeven Panel (sticky right side, updates on node hover/select)
- BE% = S / (P + S) for bet nodes
- GTO bluff frequency = S / (S + P) — labeled "GTO bluff freq", not "bluff:value ratio"
- Bluff:value ratio = S/P — shown separately
- Exploitability indicator: green if actual bluff% ≈ GTO, red if over/under by >10pp

### selectedLine Enforcement
- Clicking a node as "selected" auto-selects entire ancestor chain
- Deselects any nodes outside the new path
- "Send to Trace" disabled unless selectedLine ends at a leaf
- "Send to Trace" serializes line to Module 4 context and switches to Module 4

---

## Trace Serialization (Module 4 integration)

Each node in selectedLine serializes to:

```json
{
  "id": "flop-bet66-villain_call",
  "street": "flop",
  "action": "bet",
  "bet_size_fraction": 0.66,
  "bet_size_bb": 3.96,
  "pot_after_bb": 9.96,
  "hero_investment_bb": 4.98,
  "villain_fold_pct": 40.0,
  "villain_call_pct": 60.0,
  "villain_raise_pct": 0.0,
  "equity": 0.513,
  "equity_is_approximated": false,
  "ev_bb": 2.14
}
```

`equity_is_approximated: true` on all nodes where `street !== "flop"`.
The full `selectedLine` array is added to the trace's `game_context.ev_tree_line` field.

---

## Deferred (not in this implementation)

- Equity re-estimation per street (requires per-street MC runs)
- Rebuild preserving user-overridden frequencies by node ID
- Batch line enumeration (enumerate all root-to-leaf paths for bulk trace export)
- EV breakdown pie chart (fold equity vs showdown equity vs implied equity)
