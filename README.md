# RangeIQ

**Professional-grade Texas Hold'em GTO analysis tool + LLM training data factory.**

RangeIQ is a single-page React application with two parallel jobs:

1. **Statistical Analysis Engine** — Flopzilla-class range/equity analysis extended with solver-grade metrics (range advantage, nut advantage, polarity index, multi-street EV trees, combo density, blocker impact).

2. **LLM Training Data Factory** — Generates structured expert GTO reasoning traces from live game state via Claude API, packaged as JSONL fine-tuning datasets compatible with Anthropic, OpenAI, and Hugging Face pipelines.

Built for advanced players and AI researchers. No beginner coaching layer.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  RangeIQ (single React component, useReducer state)     │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│ Module 1 │ Module 2 │ Module 3 │ Module 4 │  Module 5   │
│ Range    │ Board &  │ EV Tree  │ Trace    │  Scenario   │
│ Builder  │ Equity   │          │ Generator│  Library    │
├──────────┴──────────┴──────────┴──────────┴─────────────┤
│  Shared State (useReducer)                              │
│  heroRange, villainRange, board, heroHand, deadCards,   │
│  metrics, evTree, traceQueue, scenarios, activeModule   │
├─────────────────────────────────────────────────────────┤
│  Utilities: expandHand(), combosFor(), DECK, PRESETS    │
└─────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  Monte Carlo Engine            Anthropic API
  (50k iterations,              (claude-sonnet-4)
   chunked setTimeout)          Trace generation
```

## Modules

### Module 1 — Preflop Range Builder ✅

13×13 hand matrix for Hero and Villain ranges with click-to-toggle, click+drag selection, 14 preset ranges, combo/VPIP counters, and a preflop nut advantage gauge.

### Module 2 — Board & Equity Analysis 🔧

Card selector UI for board/hero hand/dead cards is built. Remaining work:

- Monte Carlo equity engine (50k iterations, chunked `setTimeout`)
- Hand classifier: `classifyHand(holeCards, board)` → category + strength 0–1
- Made hand breakdown (quads → no made hand) + draw detection
- Range advantage / nut advantage / polarity index (post-board)
- Board texture metrics (wetness, connectivity, static/dynamic)
- Combo & blocker engine with impact tables
- Equity distribution histogram + runout equity graph (recharts)

### Module 3 — Multi-Street EV Tree 🔧

Pot/stack inputs wired. Remaining work:

- Recursive tree builder UI with add-node interaction
- `computeNodeEV(node, pot, heroInvestment)` recursive function
- Expandable/collapsible tree visualization (indented cards)
- Breakeven analysis panel per betting node
- Frequency exploitability score (GTO bluff:value ratio comparison)
- EV breakdown pie chart (fold equity / showdown equity / implied equity)

### Module 4 — LLM Reasoning Trace Generator ✅ (core flow)

Full API integration: context serialization → Claude API call → JSONL record packaging → export download. Remaining work:

- Batch generation mode (multi-board, multi-range iteration with progress bar)
- Trace quality indicators (coverage, specificity, consistency scores)

### Module 5 — Scenario Library ✅

Save/load/tag/export scenarios. In-memory for prototype.

---

## Tech Stack

| Layer         | Choice                                    |
|---------------|-------------------------------------------|
| Framework     | React (hooks only, single file)           |
| State         | `useReducer` with single state object     |
| Styling       | Inline styles, dark theme CSS variables   |
| Charts        | recharts (BarChart, RadialBarChart, Pie)  |
| Equity engine | Monte Carlo simulation (TODO)             |
| AI            | Anthropic API (`claude-sonnet-4`)         |
| Export        | JSONL (Blob download), JSON scenarios     |

## Design System

Dark analyst theme. All CSS variable values:

```
--bg-primary:    #0d1117
--bg-card:       #161b22
--bg-elevated:   #21262d
--border:        #30363d
--accent-blue:   #58a6ff   (Hero)
--accent-green:  #3fb950   (+EV, confirms)
--accent-red:    #f85149   (Villain, -EV, hearts/diamonds)
--accent-yellow: #d29922   (warnings, premiums)
--accent-purple: #bc8cff   (overlap)
--text-primary:  #e6edf3
--text-muted:    #8b949e
```

Monospace font for all numerical output. 2 decimal places everywhere.

## Keyboard Shortcuts

| Key | Action              |
|-----|---------------------|
| 1–5 | Switch modules     |
| C   | Clear active range |
| G   | Generate trace (M4)|
| E   | Export JSONL (M4)  |
| R   | Run Monte Carlo    |

## Statistical Formulas

**Range Advantage:**
`RA = (Hero_strong - Villain_strong) / Total_strong`
Strong = sets+, two pair+, nut draws. Signed output.

**Nut Advantage:**
`NA = (Hero_nut - Villain_nut) / (Hero_nut + Villain_nut)`
Nut = top 15% hand strength on specific board.

**Polarity Index:**
`PI = StdDev(hand_strength_distribution)`
High = polarized (large bet sizes). Low = merged (small/medium).

**Wetness Score (0–10):**
`WS = (FD_combos/max_FD)×4 + (SD_combos/max_SD)×4 + (paired ? 2 : 0)`

**EV Tree Node:**
`EV(node) = Σ[ P(action_i) × EV(outcome_i) ]`
Base: `EV = Hero_eq × final_pot - (1 - Hero_eq) × hero_investment`

**Breakeven %:**
`BE% = Bet / (Bet + Pot)`

**GTO Bluff:Value:**
`Optimal_bluff_ratio = S / (S + P)`

## JSONL Output Schema

Each trace record:

```json
{
  "messages": [
    { "role": "system", "content": "GTO expert system prompt..." },
    { "role": "user", "content": "{serialized game state + metrics}" },
    { "role": "assistant", "content": "{reasoning trace JSON}" }
  ],
  "metadata": {
    "scenario_id": "uuid",
    "street": "flop",
    "hero_equity": 54.2,
    "range_advantage": 0.18,
    "nut_advantage": 0.34,
    "optimal_action": "bet",
    "source": "RangeIQ-synthetic-v1",
    "generated_at": "ISO timestamp"
  }
}
```

Compatible with Anthropic fine-tuning, OpenAI fine-tuning, and HuggingFace `load_dataset`.

## Post-MVP Extension Path

- [ ] WASM equity engine (PokerHandEval port) for exact enumeration
- [ ] Multi-street runout simulation (full turn + river equity trees)
- [ ] HUD stat import (PT4/HM3 export paste)
- [ ] Solver output import (PioSOLVER .cfr parser)
- [ ] Active learning loop: flag low-confidence traces for human review
- [ ] Trace quality classifier: fine-tuned model scores traces before export
- [ ] Ctrl+click partial inclusion % on matrix cells
- [ ] Persistent storage (localStorage or file-backed)

## Reference Material

This project draws on concepts from:

- **PokerBench** (AAAI 2025) — solver-computed optimal decisions dataset
- **SplitSuit / Red Chip Poker** — PLANES preflop framework, combo/blocker math, bluffing breakeven analysis, EV calculation methodology
- **Flopzilla** — hand-vs-range equity and range composition analysis
- **PioSOLVER** — GTO solver output format and metric vocabulary
