# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

RangeIQ is a single-file React artifact (`RangeIQ.jsx`) that runs inside Claude.ai's artifact renderer. It is a professional-grade Texas Hold'em GTO analysis tool that doubles as an LLM fine-tuning data generator. The full spec lives in `Texas_Holdem_GTO_Analysis_App_Prompt.md`.

**Two parallel jobs:**
1. Statistical analysis engine (Flopzilla parity + solver metrics)
2. LLM training data factory (Claude API → JSONL export)

## Directory Note

The directories `scripts/`, `tests/`, `docs/`, `config/`, `data/`, `logs/`, `tracking/`, `dashboards/`, `venv/`, and `archive/` were inherited from a sports-betting project as infrastructure scaffolding. They are **not relevant to RangeIQ development** — ignore them. The entire poker codebase is `RangeIQ.jsx`.

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
- **Module 2 (Board & Equity)**: Card selector UI working (board, hero hand, dead cards with exclusion logic)
- **Module 4 (Trace Generator)**: Full API flow — context serialization, Claude API call, JSONL record packaging, export download, error handling
- **Module 5 (Scenario Library)**: Save/load/tag/export all functional (in-memory)
- **Header**: Persistent with live stats (combos, nut advantage, trace count), module tabs
- **Keyboard shortcuts**: 1-5 module switch, C clear range
- **Design system**: Dark theme with all CSS variables applied, monospace numerical output

### 🔧 Needs Implementation (priority order)

#### P0 — Module 2 Core Engine
This is the foundation everything else depends on.

1. **`classifyHand(holeCards, board)`** — The critical function.
   - Input: 2 hole cards + 3-5 board cards
   - Output: `{ category: string, strength: number (0-1), draws: string[] }`
   - Categories (strongest → weakest): Quads, Full House, Flush, Straight, Three of a Kind, Two Pair, Overpair, Top Pair (good/weak kicker), Middle Pair, Bottom Pair, Underpair, Ace High, No Made Hand
   - Draws: Nut Flush Draw, Flush Draw, OESD, Double Gutshot, Gutshot, Overcard Draw, Backdoor FD, Backdoor SD
   - **Pure poker logic — no external deps.** Implement from scratch using rank/suit comparisons. Do NOT import a poker library.

2. **`runMonteCarlo(heroRange, villainRange, board, deadCards, iterations=50000)`**
   - Chunk into 5000-iteration batches via `setTimeout` to avoid blocking UI
   - For each iteration: pick random hero combo from range, random villain combo (no overlap), deal remaining board cards, evaluate both hands, track wins/ties
   - Return: `{ heroEq, villainEq, tieEq, histogram: number[10] }`
   - Set `mcRunning` state during execution, clear when done
   - The histogram buckets hero winning % into 10% bands

3. **Range breakdown panel** — Iterate all villain combos, call `classifyHand()` on each, group by category, display as horizontal bar chart (recharts)

4. **Board texture metrics:**
   - Wetness: `(FD_combos/max_FD)×4 + (SD_combos/max_SD)×4 + (paired ? 2 : 0)`
   - Connectivity: count of rank-adjacent board cards
   - Flush texture: monotone / two-tone / rainbow

5. **Post-board range/nut advantage:**
   - RA: compare hero vs villain strong combo counts (sets+, two pair+, nut draws)
   - NA: compare top 15% hand strength combos between ranges
   - PI: standard deviation of hand strength distribution per range

6. **Blocker engine:**
   - Apply 6-3-1-0 rule for pocket pairs
   - Unpaired: `unseen(rank_A) × unseen(rank_B)`
   - Hero hole card blocker impact

#### P1 — Module 3 EV Tree
1. **Tree data structure**: Each node: `{ street, action, betSize, villainFoldPct, villainCallPct, villainRaisePct, equityAssumption, children[] }`
2. **`computeNodeEV(node, pot, heroInvestment)`**: Recursive. Base case = showdown: `heroEq × finalPot - (1 - heroEq) × heroInvestment`
3. **Tree builder UI**: Add-node buttons at each leaf, expandable/collapsible with indentation
4. **Per-node breakeven panel**: `BE% = bet / (bet + pot)`
5. **Frequency exploitability**: Compare actual bluff:value ratio to `S/(S+P)` optimal
6. **EV breakdown pie chart**: fold equity vs showdown equity vs implied equity

#### P2 — Module 4 Enhancements
1. **Batch generation**: Multi-board × multi-range iteration, 500ms delay between API calls, progress bar
2. **Trace quality indicators**: Coverage score, specificity, consistency

#### P3 — Module 1 Enhancements
1. Ctrl+click for partial inclusion % (0-100%) per cell
2. Preflop all-in equity (requires Monte Carlo)

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

All computed metrics: **2 decimal places** (`.toFixed(2)`). Monospace font for numbers.

### API Calls
Model: `claude-sonnet-4-20250514`. No API key needed (artifact runtime injects it). Always parse `data.content[0].text` and handle JSON parse errors.

## Key Utilities Already Built

```js
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
```

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

## Reference Files (domain context, not code)

- `Texas_Holdem_GTO_Analysis_App_Prompt.md` — full spec (source of truth)
- `ABC_Poker_The_Simple_Strategy_In_2026__SplitSuit_Poker.md` — ABC strategy, default ranges
- `Poker_Bluffing_Made_Easy_In_2026__SplitSuit.md` — BE%, fold frequency, multi-street bluffs
- `Poker_Combos___Blockers_101_In_2026__SplitSuit_Poker.md` — 6-3-1-0 rule, combo counting
- `The_Preflop_Poker_Checklist_In_2026__SplitSuit_Poker.md` — PLANES framework, SPR
- `Why_A_Poker_Math_Approach_Is_Best_In_2026__SplitSuit_Poker.md` — EV, BE%, frequencies
