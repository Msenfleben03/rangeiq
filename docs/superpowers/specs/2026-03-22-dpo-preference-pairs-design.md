# P1.5 — DPO Preference Pair Pipeline

**Date**: 2026-03-22
**Status**: Draft
**Module**: 4 (Trace Generator)
**Priority**: P1.5 (between analytical accuracy and module 3 deferred)

## Problem

RangeIQ generates supervised fine-tuning (SFT) traces via Module 4.
SFT teaches the model *what* good output looks like, but cannot teach
it *why* one output is better than another. Direct Preference
Optimization (DPO) requires paired examples — a chosen (good) and
rejected (bad) response to the same prompt — to train the model to
prefer higher-quality reasoning traces.

The quality gate already partitions traces into accepted
(`traceQueue`) and rejected (`rejectedTraces`). This pipeline turns
that partition into structured DPO training pairs.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Export format | Standard DPO/TRL | Widest trainer compat |
| Matching strategy | 1:1 best-worst by quality score | High contrast, no inflation |
| Minimum contrast | Rejected needs >= 2 reasons | Filters borderline rejects |
| Batch strategy | Adaptive per cell, cap 5 | Guarantees pairs |
| UI placement | Button + counter in action bar | Minimal surface |

**Format**: `{prompt, chosen, rejected}` — compatible with
HuggingFace TRL, OpenRLHF, and Axolotl.

## Architecture

### New Functions

#### `scoreTrace(record, isAccepted) -> number`

Pure function. Returns 0-100 quality score for ranking within a
`game_state_key` group.

**Accepted trace scoring (higher = better):**

Each signal group uses else-if semantics — only the highest
matching tier awards points. Max score: 100.

| Signal group | Tier | Pts |
|-------------|------|-----|
| Board diagnosis length | >= 200 chars | 20 |
| | else >= 100 chars | 10 |
| Key combos count | >= 5 | 20 |
| | else >= 3 | 10 |
| Frequency confidence | all `"high"` | 15 |
| | else any `"high"` | 8 |
| EV tree anchored | `true` | 15 |
| Frequency source | any `=== "ev_tree"` | 15 |
| Freq divergence | < 10 | 15 |
| | else < 20 | 8 |

Source access patterns:

- Board diagnosis: `record.reasoning_trace.board_diagnosis.length`
- Key combos: `record.reasoning_trace.key_combos.length`
- Confidence: check via `.every()` / `.some()` on
  `(record.reasoning_trace.action_evaluation || [])`
  accessing `e.frequency_recommendation?.confidence`
- EV anchored: `record.metadata.ev_tree_anchored`
- Freq source: `.some(e => e.frequency_source === "ev_tree")`
  on `action_evaluation`
- Divergence: `record.metadata.freq_divergence_from_tree`

**Precondition**: `record.reasoning_trace` must be non-null. This
is guaranteed because rejected traces with
`rejection_reasons.length < 2` are pre-filtered before scoring
(the `insufficient_combos_explicit` path produces exactly 1
reason, so those records — which may lack `reasoning_trace` —
never reach `scoreTrace`). Final score clamped via
`Math.min(score, 100)` as a safety net.

**Rejected trace scoring (lower = worse, used for sorting):**

Score = `100 - (rejection_reasons.length * 20)`, clamped to
`[0, 100]`. More rejection reasons = lower score = paired first
against the best accepted trace.

#### `buildPreferencePairs(traceQueue, rejectedTraces) -> DPOPair[]`

Pure function. No side effects, no dispatch calls.

```typescript
// Type shape (not actual TS — for documentation only)
type DPOPair = {
  prompt: string;    // system prompt + "\n\n" + user context JSON
  chosen: string;    // accepted trace assistant text
  rejected: string;  // rejected trace assistant text
  metadata: {
    game_state_key: string;
    chosen_score: number;
    rejected_score: number;
    rejection_reasons: string[];
    chosen_scenario_id: string;
    rejected_scenario_id: string;
  };
};
```

**Algorithm:**

1. **Group by key**: Partition `traceQueue` and `rejectedTraces`
   by `metadata.game_state_key` into
   `Map<string, {accepted: [], rejected: []}>`.
2. **Filter rejected**: For each group, remove rejected traces
   with `rejection_reasons.length < 2`.
3. **Skip empty groups**: If a group has 0 accepted or 0
   qualified-rejected, skip it.
4. **Score and rank**: Score accepted traces descending (best
   first). Score rejected traces ascending (worst first).
5. **Zip 1:1**: Pair `accepted[0]` with `rejected[0]`,
   `accepted[1]` with `rejected[1]`, etc. Unpaired leftovers
   are discarded.
6. **Format**: For each pair, extract:
   - `prompt`: `messages[0].content + "\n\n" + messages[1].content`
     (system + user) — identical for both since they share the
     same `game_state_key`
   - `chosen`: accepted `messages[2].content`
   - `rejected`: rejected `messages[2].content`

**Edge cases:**

- `game_state_key` is empty string: skip group.
- Rejected trace with `rejection_reasons.length < 2`: already
  filtered in step 2. This naturally excludes
  `insufficient_combos_explicit` traces (exactly 1 reason).
  Those traces DO have a full `messages` array — the `record`
  is fully constructed before `applyQualityGate` is called —
  but they lack sufficient contrast for DPO training.
- Guard on `record.messages?.length >= 3` before accessing
  `messages[2].content` as defensive safety, even though all
  current code paths produce a complete messages array.

#### `exportDPO(pairs) -> void`

Downloads `rangeiq-dpo-pairs-<YYYY-MM-DD>.jsonl` via Blob URL.
One JSON line per pair. Same pattern as existing `exportJSONL`.

### Modified Function

#### `generateBatch()` — Adaptive Loop

Current behavior: iterate 24-cell matrix, generate 1 trace per
cell (up to `batchCellCap`).

New behavior per cell:

**Stale closure problem**: React `dispatch` enqueues state
updates; the updated `traceQueue`/`rejectedTraces` arrays are
only available on the next render. Inside an async loop, the
closed-over state is stale. We solve this with local `useRef`
accumulators that mirror dispatches within the batch run.

```jsx
// Add refs at the top of Module4:
const batchAcceptedRef = useRef(new Map());
const batchRejectedRef = useRef(new Map());

// Reset at batch start:
batchAcceptedRef.current = new Map();
batchRejectedRef.current = new Map();
```

Modified `generateTrace` returns a result indicator so the batch
loop can update refs:

```pseudocode
for each cell in BATCH_BOARD_MATRIX:
  if coverageMap[cell.cell] >= 30: continue
  attempts = 0
  cellKey = computeGameStateKey(cell)

  while attempts < 5:
    if batchStopRef.current: break

    hasAccepted = batchAcceptedRef.get(cellKey) > 0
    hasQualifiedRejected = batchRejectedRef.get(cellKey) > 0
    if hasAccepted AND hasQualifiedRejected: break

    result = await generateTrace({...cellOverrides})
    attempts++

    if result === "accepted":
      batchAcceptedRef.increment(cellKey)
    else if result === "rejected_qualified":
      batchRejectedRef.increment(cellKey)

    dispatch SET_BATCH_PROGRESS with {
      currentCell, cellIndex, totalCells,
      attempt: attempts
    }
```

**`generateTrace` return value**: Currently returns `void`.
Modify to return
`"accepted" | "rejected_qualified" | "rejected_unqualified" | "error"`
based on quality gate outcome. The existing dispatch calls remain
unchanged — the return value is additional information for the
batch loop.

**Important**: The `game_state_key` for a batch cell is
deterministic (same hero/villain ranges + generated board + pot +
stack), so all traces within a cell share the same key.

### State Changes

No new reducer actions. DPO pairs are computed on-demand:

```jsx
const dpoPairs = useMemo(
  () => buildPreferencePairs(traceQueue, rejectedTraces),
  [traceQueue, rejectedTraces]
);
```

This keeps the state minimal — pairs are a derived view, not
stored data. At current scale (<500 traces), recomputing on every
dispatch is negligible. If tracing extends to thousands, move to
on-demand computation triggered by an explicit "Build Pairs"
action.

### UI Changes

**Stats row** — add between "Rejected" and "Coverage":

```jsx
Pairs: <span style={{
  color: dpoPairs.length > 0 ? T.purple : T.muted
}}>{dpoPairs.length}</span>
```

**Action bar** — add after "Export JSONL" button:

```jsx
<Btn
  onClick={() => exportDPO(dpoPairs)}
  disabled={dpoPairs.length === 0}
  color={T.purple}
>
  Export DPO ({dpoPairs.length})
</Btn>
```

Purple color distinguishes DPO from SFT export (yellow).

### Batch Progress Display

Update batch progress text to show per-cell attempt count.
Requires extending `SET_BATCH_PROGRESS` payload to include
`attempt`:

```jsx
dispatch({
  type: "SET_BATCH_PROGRESS",
  payload: { currentCell, cellIndex, totalCells, attempt }
});
```

Display:

```text
Cell 5/24: dry_rainbow_unpaired (attempt 3/5)
```

## DPO JSONL Record Schema

Each line in the exported file:

```json
{
  "prompt": "<SYSTEM_PROMPT_V2>\n\n<user context JSON>",
  "chosen": "<accepted assistant JSON response>",
  "rejected": "<rejected assistant JSON response>",
  "metadata": {
    "game_state_key": "AKs,QQ|87s,65s|Ah7d2c|6|100",
    "chosen_score": 85,
    "rejected_score": 20,
    "rejection_reasons": [
      "insufficient_key_combos",
      "short_board_diagnosis"
    ],
    "chosen_scenario_id": "uuid-1",
    "rejected_scenario_id": "uuid-2"
  }
}
```

## Non-Goals

- **DPO training loop**: This pipeline produces the dataset.
  Training happens externally.
- **Pair editing UI**: No manual accept/reject override. Quality
  gate is the sole arbiter.
- **Cross-key pairing**: Traces are only paired within the same
  `game_state_key`. Cross-scenario pairing would break the "same
  prompt" DPO requirement.
- **Storing pairs in state**: Pairs are derived via `useMemo`,
  not persisted in the reducer.
- **Prompt versioning**: `game_state_key` does not include a
  prompt version hash. All traces in a session use the same
  `SYSTEM_PROMPT_V2` constant, so this is safe within a single
  session. Traces are ephemeral (in-memory only, cleared on page
  refresh), so cross-session mismatch is not a concern.

## Testing Strategy

Since RangeIQ is a single-file artifact with no test harness,
validation is manual:

1. **Unit logic**: `scoreTrace` and `buildPreferencePairs` are
   pure functions — test via console in the artifact
2. **Integration**: Generate a small batch (2-3 cells), verify
   pair count matches expectations, export and inspect JSONL
3. **Edge cases**: Generate with a scenario that consistently
   passes quality gate (expect 0 pairs), verify graceful handling
4. **Adaptive batch**: Run batch, observe per-cell attempt counts
   in progress display, verify early termination when pair exists

## File Impact

Single file: `RangeIQ.jsx`

- ~40 lines: `scoreTrace` function
- ~40 lines: `buildPreferencePairs` function
- ~10 lines: `exportDPO` function
- ~25 lines: `generateBatch` adaptive loop + ref accumulators
- ~5 lines: `generateTrace` return value addition
- ~10 lines: `useMemo` + stats row + button + progress in JSX
- **Total: ~130 lines added/modified**
