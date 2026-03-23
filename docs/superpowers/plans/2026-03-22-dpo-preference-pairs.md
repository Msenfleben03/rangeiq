# P1.5 DPO Preference Pair Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED: Use
> superpowers:subagent-driven-development (if subagents available)
> or superpowers:executing-plans to implement this plan. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a DPO preference pair pipeline that matches
accepted and rejected traces by `game_state_key`, scores and
ranks them, and exports Standard DPO/TRL JSONL for fine-tuning.

**Architecture:** Three new pure functions (`scoreTrace`,
`buildPreferencePairs`, `exportDPO`) added to `RangeIQ.jsx`,
plus modifications to `generateTrace` (return value) and
`generateBatch` (adaptive loop with `useRef` accumulators).
Pairs are derived via `useMemo` — no new reducer actions.

**Tech Stack:** React (hooks), single-file artifact
(`RangeIQ.jsx`)

**Spec:** `docs/superpowers/specs/2026-03-22-dpo-preference-pairs-design.md`

---

## Chunk 1: Core Functions

### Task 1: Add `scoreTrace` function

**Files:**

- Modify: `RangeIQ.jsx` — insert after `runAuditor` (line ~2038)

- [ ] **Step 1: Write `scoreTrace`**

Insert immediately after the closing `};` of `runAuditor`
(after line 2038):

```jsx
const scoreTrace = (record, isAccepted) => {
  if (!isAccepted) {
    const len = (record.rejection_reasons || []).length;
    return Math.max(0, Math.min(100, 100 - len * 20));
  }
  const rt = record.reasoning_trace;
  if (!rt) return 0;
  let score = 0;
  // Board diagnosis length
  const diagLen = (rt.board_diagnosis || "").length;
  if (diagLen >= 200) score += 20;
  else if (diagLen >= 100) score += 10;
  // Key combos count
  const comboCount = (rt.key_combos || []).length;
  if (comboCount >= 5) score += 20;
  else if (comboCount >= 3) score += 10;
  // Frequency confidence
  const evals = rt.action_evaluation || [];
  const allHigh = evals.length > 0
    && evals.every(
      e => e.frequency_recommendation?.confidence === "high"
    );
  const anyHigh = evals.some(
    e => e.frequency_recommendation?.confidence === "high"
  );
  if (allHigh) score += 15;
  else if (anyHigh) score += 8;
  // EV tree anchored
  if (record.metadata?.ev_tree_anchored) score += 15;
  // Frequency source
  if (evals.some(e => e.frequency_source === "ev_tree")) {
    score += 15;
  }
  // Freq divergence from tree
  const div = record.metadata?.freq_divergence_from_tree;
  if (div != null && div < 10) score += 15;
  else if (div != null && div < 20) score += 8;
  return Math.min(score, 100);
};
```

- [ ] **Step 2: Verify no syntax errors**

Paste full `RangeIQ.jsx` into a Claude.ai artifact. Confirm
it renders without console errors. Check that existing Module 4
functionality (Generate Trace, Export JSONL) still works.

- [ ] **Step 3: Commit**

```bash
git add RangeIQ.jsx
git commit -m "feat(p1.5): add scoreTrace for DPO pair ranking"
```

---

### Task 2: Add `buildPreferencePairs` function

**Files:**

- Modify: `RangeIQ.jsx` — insert after `scoreTrace`

- [ ] **Step 1: Write `buildPreferencePairs`**

Insert immediately after `scoreTrace`:

```jsx
const buildPreferencePairs = (accepted, rejected) => {
  const groups = new Map();
  const addTo = (arr, field) => {
    arr.forEach(r => {
      const k = r.metadata?.game_state_key;
      if (!k) return;
      if (!groups.has(k)) groups.set(k, { accepted: [], rejected: [] });
      groups.get(k)[field].push(r);
    });
  };
  addTo(accepted, "accepted");
  addTo(rejected, "rejected");

  const pairs = [];
  groups.forEach((g, key) => {
    const qualRej = g.rejected.filter(
      r => (r.rejection_reasons || []).length >= 2
    );
    if (!g.accepted.length || !qualRej.length) return;

    const sortedAcc = [...g.accepted]
      .map(r => ({ r, s: scoreTrace(r, true) }))
      .sort((a, b) => b.s - a.s);
    const sortedRej = [...qualRej]
      .map(r => ({ r, s: scoreTrace(r, false) }))
      .sort((a, b) => a.s - b.s);

    const count = Math.min(sortedAcc.length, sortedRej.length);
    for (let i = 0; i < count; i++) {
      const acc = sortedAcc[i];
      const rej = sortedRej[i];
      if (
        (acc.r.messages?.length ?? 0) < 3
        || (rej.r.messages?.length ?? 0) < 3
      ) continue;
      pairs.push({
        prompt: acc.r.messages[0].content
          + "\n\n" + acc.r.messages[1].content,
        chosen: acc.r.messages[2].content,
        rejected: rej.r.messages[2].content,
        metadata: {
          game_state_key: key,
          chosen_score: acc.s,
          rejected_score: rej.s,
          rejection_reasons: rej.r.rejection_reasons,
          chosen_scenario_id: acc.r.metadata?.scenario_id,
          rejected_scenario_id: rej.r.metadata?.scenario_id,
        },
      });
    }
  });
  return pairs;
};
```

- [ ] **Step 2: Verify no syntax errors**

Paste into artifact, confirm renders. No new UI yet — this is
a pure function with no callers.

- [ ] **Step 3: Commit**

```bash
git add RangeIQ.jsx
git commit -m "feat(p1.5): add buildPreferencePairs for DPO matching"
```

---

### Task 3: Add `exportDPO` function

**Files:**

- Modify: `RangeIQ.jsx` — insert after `buildPreferencePairs`
  (before existing `exportJSONL` at line ~2040)

- [ ] **Step 1: Write `exportDPO`**

Insert after `buildPreferencePairs`:

```jsx
const exportDPO = (pairs) => {
  const lines = pairs.map(p => JSON.stringify(p)).join("\n");
  const blob = new Blob([lines], { type: "application/jsonl" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `rangeiq-dpo-pairs-${
    new Date().toISOString().slice(0, 10)
  }.jsonl`;
  a.click();
  URL.revokeObjectURL(url);
};
```

- [ ] **Step 2: Verify no syntax errors**

Paste into artifact, confirm renders.

- [ ] **Step 3: Commit**

```bash
git add RangeIQ.jsx
git commit -m "feat(p1.5): add exportDPO for JSONL download"
```

---

## Chunk 2: UI Integration

### Task 4: Add `useMemo`, stats counter, and Export DPO button

**Files:**

- Modify: `RangeIQ.jsx` — three locations in Module4 component

- [ ] **Step 1: Add `useMemo` for `dpoPairs`**

Find the `tier2Count` line (line ~1808, immediately after
`coveredCells`):

```jsx
const tier2Count = traceQueue.filter(...)...;
```

Insert immediately after `tier2Count`:

```jsx
const dpoPairs = useMemo(
  () => buildPreferencePairs(traceQueue, rejectedTraces),
  [traceQueue, rejectedTraces]
);
```

- [ ] **Step 2: Add DPO pair count to stats row**

Find the stats row (line ~2079-2081). Replace:

```jsx
        {" · "}Coverage: <span style={{ color: coveredCells >= 20 ? T.green : coveredCells >= 12 ? T.yellow : T.red }}>{coveredCells}/24 cells ≥15</span>
```

With:

```jsx
        {" · "}Pairs: <span style={{ color: dpoPairs.length > 0 ? T.purple : T.muted }}>{dpoPairs.length}</span>
        {" · "}Coverage: <span style={{ color: coveredCells >= 20 ? T.green : coveredCells >= 12 ? T.yellow : T.red }}>{coveredCells}/24 cells ≥15</span>
```

- [ ] **Step 3: Add Export DPO button to action bar**

Find the Export JSONL button (line ~2067):

```jsx
        <Btn onClick={exportJSONL} disabled={traceQueue.length === 0} color={T.yellow}>Export JSONL (E)</Btn>
```

Insert immediately after it:

```jsx
        <Btn onClick={() => exportDPO(dpoPairs)} disabled={dpoPairs.length === 0} color={T.purple}>Export DPO ({dpoPairs.length})</Btn>
```

- [ ] **Step 4: Verify in artifact**

Paste into artifact. Confirm:

1. Stats row shows `Pairs: 0` in muted color
2. "Export DPO (0)" button appears, disabled (purple outline)
3. All existing buttons still work

- [ ] **Step 5: Commit**

```bash
git add RangeIQ.jsx
git commit -m "feat(p1.5): add DPO pair counter and export button to Module 4 UI"
```

---

## Chunk 3: Adaptive Batch Loop

### Task 5: Modify `generateTrace` to return result indicator

**Files:**

- Modify: `RangeIQ.jsx:1905-1985` — `generateTrace` function

- [ ] **Step 1: Add return values to `generateTrace`**

The function currently returns nothing. Add return statements
at each exit point.

Find the `insufficient_combos_explicit` dispatch
(line ~1863):

```jsx
      dispatch({ type: "ADD_REJECTED_TRACE", payload: { ...record, rejection_reasons: ["insufficient_combos_explicit"] } });
      return false;
```

Replace `return false;` with:

```jsx
      return "rejected_unqualified";
```

Find the quality gate rejection dispatch (line ~1898-1900):

```jsx
      dispatch({ type: "ADD_REJECTED_TRACE", payload: { ...record, rejection_reasons: reasons } });
      return false;
```

Replace `return false;` with:

```jsx
      return reasons.length >= 2 ? "rejected_qualified" : "rejected_unqualified";
```

**Wait** — the rejection dispatch is inside `applyQualityGate`,
not in `generateTrace` directly. The flow is:

1. `applyQualityGate` dispatches and returns `false`
2. `generateTrace` checks the return (line 1979):
   `if (applyQualityGate(trace, record)) { dispatch ADD_TRACE }`

So modify `applyQualityGate` to return the reason count, and
use that in `generateTrace`.

Find `applyQualityGate` return statements:

At line 1864 (insufficient path):

```jsx
      return false;
```

Change to:

```jsx
      return { accepted: false, reasonCount: 1 };
```

At line 1900 (multi-reason rejection):

```jsx
      return false;
```

Change to:

```jsx
      return { accepted: false, reasonCount: reasons.length };
```

At line 1902 (passed gate):

```jsx
    return true;
```

Change to:

```jsx
    return { accepted: true, reasonCount: 0 };
```

Now update `generateTrace` to use the new return shape. Find
line 1979:

```jsx
      if (applyQualityGate(trace, record)) {
        dispatch({ type: "ADD_TRACE", payload: record });
      }
    } catch (err) {
      dispatch({ type: "SET_TRACE_ERROR", payload: err.message });
    }
```

Replace with:

```jsx
      const gate = applyQualityGate(trace, record);
      if (gate.accepted) {
        dispatch({ type: "ADD_TRACE", payload: record });
        return "accepted";
      }
      return gate.reasonCount >= 2
        ? "rejected_qualified"
        : "rejected_unqualified";
    } catch (err) {
      dispatch({ type: "SET_TRACE_ERROR", payload: err.message });
      return "error";
    }
```

- [ ] **Step 2: Verify in artifact**

Paste into artifact. Generate a single trace manually. Confirm
it still works (the return value is unused until the batch
loop is updated). Check console for errors.

- [ ] **Step 3: Commit**

```bash
git add RangeIQ.jsx
git commit -m "feat(p1.5): add return value to generateTrace and applyQualityGate"
```

---

### Task 6: Add ref accumulators and adaptive batch loop

**Files:**

- Modify: `RangeIQ.jsx:1794,1987-2017` — refs and
  `generateBatch`

- [ ] **Step 1: Add `useRef` accumulators**

Find `batchStopRef` declaration (line ~1794):

```jsx
  const batchStopRef = useRef(false);
```

Insert immediately after:

```jsx
  const batchAcceptedRef = useRef(new Map());
  const batchRejectedRef = useRef(new Map());
```

- [ ] **Step 2: Rewrite `generateBatch` with adaptive loop**

Replace the entire `generateBatch` function (lines 1987-2017):

```jsx
  const generateBatch = async () => {
    if (!heroRange.size || !villainRange.size) return;
    batchStopRef.current = false;
    batchAcceptedRef.current = new Map();
    batchRejectedRef.current = new Map();
    dispatch({ type: "SET_BATCH_RUNNING", payload: true });
    dispatch({ type: "SET_TRACE_ERROR", payload: null });
    try {
      for (let i = 0; i < BATCH_BOARD_MATRIX.length; i++) {
        if (batchStopRef.current) break;
        const cell = BATCH_BOARD_MATRIX[i];
        if ((coverageMap[cell.cell] || 0) >= 30) continue;

        const cellHeroCombos = [...heroRange].flatMap(
          h => expandHand(h, cell.board)
        );
        const cellVillainCombos = [...villainRange].flatMap(
          h => expandHand(h, cell.board)
        );
        if (!cellHeroCombos.length || !cellVillainCombos.length)
          continue;

        const equity = computeEquityFast(
          cellHeroCombos, cellVillainCombos, cell.board, 500
        ) * 100;
        const cellKey = `${[...heroRange].sort().join(",")}`
          + `|${[...villainRange].sort().join(",")}`
          + `|${cell.board.join("")}`
          + `|${cell.potSize}|${cell.effStack}`;

        let attempts = 0;
        while (attempts < 5) {
          if (batchStopRef.current) break;
          const hasAcc =
            (batchAcceptedRef.current.get(cellKey) || 0) > 0;
          const hasRej =
            (batchRejectedRef.current.get(cellKey) || 0) > 0;
          if (hasAcc && hasRej) break;

          dispatch({ type: "SET_BATCH_PROGRESS", payload: {
            currentCell: cell.cell,
            cellIndex: i + 1,
            totalCells: BATCH_BOARD_MATRIX.length,
            attempt: attempts + 1,
          }});

          const result = await generateTrace({
            boardOverride: cell.board,
            potSizeOverride: cell.potSize,
            effStackOverride: cell.effStack,
            equityOverride: equity,
            textureOverride: boardTexture(cell.board),
            batchCell: cell.cell,
          });
          attempts++;

          if (result === "accepted") {
            batchAcceptedRef.current.set(
              cellKey,
              (batchAcceptedRef.current.get(cellKey) || 0) + 1
            );
          } else if (result === "rejected_qualified") {
            batchRejectedRef.current.set(
              cellKey,
              (batchRejectedRef.current.get(cellKey) || 0) + 1
            );
          }

          await new Promise(r => setTimeout(r, 500));
        }
      }
    } finally {
      dispatch({ type: "SET_BATCH_RUNNING", payload: false });
      dispatch({ type: "SET_BATCH_PROGRESS", payload: null });
    }
  };
```

- [ ] **Step 3: Update batch progress display**

Find the batch progress display (line ~2088-2089):

```jsx
            Cell {batchProgress.cellIndex}/{batchProgress.totalCells}: <span style={{ color: T.text }}>{batchProgress.currentCell}</span>
```

Replace with:

```jsx
            Cell {batchProgress.cellIndex}/{batchProgress.totalCells}: <span style={{ color: T.text }}>{batchProgress.currentCell}</span>
            {batchProgress.attempt && <span> (attempt {batchProgress.attempt}/5)</span>}
```

- [ ] **Step 4: Verify in artifact**

Paste into artifact. Test:

1. Click "Batch Generate" — should show attempt counters
2. Verify batch stops early on a cell if accept + reject exist
3. Verify "Stop Batch" button still works
4. Check the DPO pair counter updates after batch completes

- [ ] **Step 5: Commit**

```bash
git add RangeIQ.jsx
git commit -m "feat(p1.5): adaptive batch loop with ref accumulators for DPO pair generation"
```

---

## Chunk 4: Final Integration

### Task 7: End-to-end verification and CLAUDE.md update

**Files:**

- Verify: `RangeIQ.jsx` — full artifact test
- Modify: `CLAUDE.md` — update priority queue

- [ ] **Step 1: Full integration test**

Paste full `RangeIQ.jsx` into Claude.ai artifact. Run through:

1. Set hero range (e.g., UTG RFI preset), villain range
   (e.g., BB Defend preset)
2. Run Module 2 Monte Carlo
3. Build EV tree in Module 3
4. In Module 4, click "Batch Generate" for 2-3 cells
5. Verify `Pairs: N` updates in stats row (N > 0 if any
   accepted+rejected match)
6. Click "Export DPO" — verify JSONL downloads
7. Open JSONL, verify schema matches spec: `prompt`, `chosen`,
   `rejected`, `metadata` fields all present
8. Verify `chosen_score` > `rejected_score` in each pair
9. Verify `rejection_reasons` array has >= 2 entries per pair

- [ ] **Step 2: Update CLAUDE.md priority queue**

In `CLAUDE.md`, find the P1 section under
`### 🔧 Needs Implementation (priority order)` and add
P1.5 as completed. Move the P1.5 description from "needs
implementation" to the "Done" section:

Add under `### ✅ Done`:

```markdown
- **Module 4 P1.5 (DPO Pairs)**: `scoreTrace`,
  `buildPreferencePairs`, `exportDPO`, adaptive batch loop
  with ref accumulators, DPO pair counter + export button
```

Remove or mark P1.5 as done in the priority queue.

- [ ] **Step 3: Commit**

```bash
git add RangeIQ.jsx CLAUDE.md
git commit -m "feat(p1.5): complete DPO preference pair pipeline — score, match, export"
```
