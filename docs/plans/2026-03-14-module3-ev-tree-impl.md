# Module 3 EV Tree — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the Module 3 stub with a fully functional multi-street EV tree builder that auto-generates from pot/stack/sizing parameters, computes recursive EV at each node, and serializes selected action lines into Module 4 traces.

**Architecture:** Single-file addition to `RangeIQ.jsx`. Pure functions (`buildTree`, `computeNodeEV`) live above the component section. A recursive `TreeNode` component renders the tree. A sticky `BreakevenPanel` component shows BE%/exploitability for the hovered/selected node. Module 4's `buildContext` is updated to include the serialized selected line.

**Tech Stack:** React (`useReducer`, `useState`, `useCallback`), inline styles via `T` theme object, no new deps.

**Design Reference:** `docs/plans/2026-03-14-module3-ev-tree-design.md`

---

## Critical Pre-Implementation Notes

- **No build step.** Verify each task by pasting `RangeIQ.jsx` into a Claude.ai artifact (React). No jest/pytest.
- **Single file constraint.** All code goes in `RangeIQ.jsx`. No imports beyond `react`, `recharts`, `lucide-react`, `lodash`, `d3`.
- **State mutations only through `dispatch`.** Never mutate state directly.
- **Inline styles only.** Use `T.xxx` theme tokens. No Tailwind, no CSS classes.
- **After each task: paste artifact and verify** the stated acceptance criteria before committing.

---

## Task 1: Expand State & Reducer

**Files:**
- Modify: `RangeIQ.jsx:452-455` (initialState evTreeConfig)
- Modify: `RangeIQ.jsx:511-512` (reducer SET_EV_TREE_CONFIG case)

**Step 1: Replace evTreeConfig in initialState**

Find this block (lines 452-455):
```js
  // Module 3 state
  evTreeConfig: {
    potSize: 6, effStack: 100,
    nodes: [] // will be built in Module 3
  },
```

Replace with:
```js
  // Module 3 state
  evTreeConfig: {
    potSize: 6,
    effStack: 100,
    betSizings: [0.33, 0.66, 1.0],
    nodes: [],            // generated tree (array of root child nodes)
    selectedLine: [],     // array of node IDs: root-to-leaf path
    hoveredNodeId: null,
    siblingCollapseEnabled: false,
  },
```

**Step 2: Add new reducer cases** after `SET_EV_TREE_CONFIG` (line 511):
```js
    case "SET_EV_TREE_NODES":
      return { ...state, evTreeConfig: { ...state.evTreeConfig, nodes: action.payload } };
    case "SET_EV_SELECTED_LINE":
      return { ...state, evTreeConfig: { ...state.evTreeConfig, selectedLine: action.payload } };
    case "SET_EV_HOVERED":
      return { ...state, evTreeConfig: { ...state.evTreeConfig, hoveredNodeId: action.payload } };
    case "TOGGLE_EV_NODE_EXPANDED": {
      // Recursively toggle expanded on the node with matching id
      const toggleNode = (nodes, targetId) => nodes.map(n => {
        if (n.id === targetId) return { ...n, expanded: !n.expanded };
        if (n.children?.length) return { ...n, children: toggleNode(n.children, targetId) };
        return n;
      });
      return { ...state, evTreeConfig: {
        ...state.evTreeConfig,
        nodes: toggleNode(state.evTreeConfig.nodes, action.payload)
      }};
    }
    case "UPDATE_EV_NODE_FREQ": {
      // Update villainFoldPct / villainCallPct / heroFoldToRaise on a specific node
      const updateNode = (nodes, targetId, patch) => nodes.map(n => {
        if (n.id === targetId) return { ...n, ...patch };
        if (n.children?.length) return { ...n, children: updateNode(n.children, targetId, patch) };
        return n;
      });
      return { ...state, evTreeConfig: {
        ...state.evTreeConfig,
        nodes: updateNode(state.evTreeConfig.nodes, action.payload.id, action.payload.patch)
      }};
    }
```

**Step 3: Verify (paste artifact)**
- Module 3 tab should still render (the stub) without errors.
- No console errors about unknown action types.

**Step 4: Commit**
```bash
git add RangeIQ.jsx
git commit -m "feat(m3): expand evTreeConfig state + reducer cases"
```

---

## Task 2: `buildTree` Pure Function

**Files:**
- Modify: `RangeIQ.jsx` — add pure function above `// MODULE 3` comment (line 997)

**Step 1: Add helper `makeNodeId`**

Insert directly above the `// MODULE 3` comment:
```js
// ============================================================
// MODULE 3 — HELPERS
// ============================================================
function makeNodeId(parentId, action, sizing) {
  const sizingTag = sizing != null ? `_${Math.round(sizing * 100)}` : "";
  return `${parentId}__${action}${sizingTag}`;
}
```

**Step 2: Add `buildTree`**
```js
function buildTree({
  potSize,        // bb, pot before hero acts
  effStack,       // bb, effective stack remaining
  betSizings,     // [0.33, 0.66, 1.0]
  equity,         // 0-1, hero equity
  street = "flop",
  depth = 0,
  parentId = "root",
  heroInvestment = 0,
}) {
  const STREETS = ["flop", "turn", "river"];
  if (depth >= 3 || heroInvestment >= effStack) return [];

  const nextStreet = STREETS[depth + 1] || "river";
  const nodes = [];

  // ── CHECK NODE ──
  const checkId = makeNodeId(parentId, "check", null);
  const checkChildren = [];

  // Villain checks behind → showdown
  checkChildren.push({
    id: makeNodeId(checkId, "check_behind", null),
    street,
    action: "check_behind",
    label: "Check behind (showdown)",
    betSize: 0, betSizeBb: 0,
    potAfter: potSize, heroInvestmentAfter: heroInvestment,
    villainFoldPct: 0, villainCallPct: 100, villainRaisePct: 0,
    heroFoldToRaise: 0,
    equityAssumption: equity, equity_is_approximated: street !== "flop",
    ev: null, expanded: false, children: [], isLeaf: true,
  });

  // Villain leads each sizing (donk bets)
  betSizings.forEach(s => {
    const S = s * potSize;
    const leadId = makeNodeId(checkId, "villain_bet", s);
    // GTO hero call frequency (pot odds)
    const heroPotOdds = potSize / (potSize + 2 * S);
    const foldPct = (1 - heroPotOdds) * 100;
    const callPct = heroPotOdds * 100;
    const heroCallChildren = buildTree({
      potSize: potSize + 2 * S, effStack, betSizings, equity,
      street: nextStreet, depth: depth + 1,
      parentId: leadId, heroInvestment: heroInvestment + S,
    });
    checkChildren.push({
      id: leadId, street, action: "villain_bet",
      label: `Villain bets ${Math.round(s * 100)}%`,
      betSize: s, betSizeBb: S,
      potAfter: potSize + S, heroInvestmentAfter: heroInvestment,
      villainFoldPct: 0, villainCallPct: 0, villainRaisePct: 0,
      heroFoldToRaise: foldPct,
      equityAssumption: equity, equity_is_approximated: street !== "flop",
      ev: null, expanded: false, isLeaf: false,
      children: [
        { id: makeNodeId(leadId, "hero_fold", null), street, action: "hero_fold",
          label: "Hero folds", betSize: 0, betSizeBb: 0,
          potAfter: potSize + S, heroInvestmentAfter: heroInvestment,
          villainFoldPct: 0, villainCallPct: 100, villainRaisePct: 0,
          heroFoldToRaise: 0, equityAssumption: equity,
          equity_is_approximated: street !== "flop",
          ev: null, expanded: false, children: [], isLeaf: true },
        { id: makeNodeId(leadId, "hero_call", null), street, action: "hero_call",
          label: "Hero calls", betSize: 0, betSizeBb: 0,
          potAfter: potSize + 2 * S, heroInvestmentAfter: heroInvestment + S,
          villainFoldPct: 0, villainCallPct: 100, villainRaisePct: 0,
          heroFoldToRaise: 0, equityAssumption: equity,
          equity_is_approximated: nextStreet !== "flop",
          ev: null, expanded: false, isLeaf: heroCallChildren.length === 0,
          children: heroCallChildren },
      ],
    });
  });

  nodes.push({
    id: checkId, street, action: "check", label: "Check",
    betSize: 0, betSizeBb: 0,
    potAfter: potSize, heroInvestmentAfter: heroInvestment,
    villainFoldPct: 0, villainCallPct: 0, villainRaisePct: 0,
    heroFoldToRaise: 0,
    equityAssumption: equity, equity_is_approximated: street !== "flop",
    ev: null, expanded: true, isLeaf: false, children: checkChildren,
  });

  // ── BET NODES ──
  betSizings.forEach(s => {
    const S = s * potSize;
    if (S > effStack - heroInvestment) return; // can't over-bet stack
    const betId = makeNodeId(parentId, "bet", s);

    // GTO villain frequencies
    const foldPct = S / (potSize + S) * 100;
    const callPct = potSize / (potSize + S) * 100;
    const raisePct = 0;

    // Raise sizing default: 2.5x hero's bet
    const R = S * 2.5;
    const heroFoldToRaise = (1 - (R - S) / (potSize + R)) * 100;

    // Call subtree (next street)
    const callChildren = buildTree({
      potSize: potSize + 2 * S, effStack, betSizings, equity,
      street: nextStreet, depth: depth + 1,
      parentId: makeNodeId(betId, "villain_call", null),
      heroInvestment: heroInvestment + S,
    });

    nodes.push({
      id: betId, street, action: "bet",
      label: `Bet ${Math.round(s * 100)}% pot (${S.toFixed(1)} bb)`,
      betSize: s, betSizeBb: S,
      potAfter: potSize + S, heroInvestmentAfter: heroInvestment + S,
      villainFoldPct: foldPct, villainCallPct: callPct, villainRaisePct: raisePct,
      heroFoldToRaise,
      equityAssumption: equity, equity_is_approximated: street !== "flop",
      ev: null, expanded: true, isLeaf: false,
      children: [
        // Villain folds (hero wins pot)
        { id: makeNodeId(betId, "villain_fold", null), street, action: "villain_fold",
          label: "Villain folds", betSize: 0, betSizeBb: 0,
          potAfter: potSize + S, heroInvestmentAfter: heroInvestment + S,
          villainFoldPct: 0, villainCallPct: 0, villainRaisePct: 0,
          heroFoldToRaise: 0, equityAssumption: equity,
          equity_is_approximated: street !== "flop",
          ev: null, expanded: false, children: [], isLeaf: true },
        // Villain calls
        { id: makeNodeId(betId, "villain_call", null), street, action: "villain_call",
          label: "Villain calls", betSize: 0, betSizeBb: 0,
          potAfter: potSize + 2 * S, heroInvestmentAfter: heroInvestment + S,
          villainFoldPct: 0, villainCallPct: 0, villainRaisePct: 0,
          heroFoldToRaise: 0, equityAssumption: equity,
          equity_is_approximated: nextStreet !== "flop",
          ev: null, expanded: false, isLeaf: callChildren.length === 0,
          children: callChildren },
        // Villain raises → hero fold or call
        { id: makeNodeId(betId, "villain_raise", null), street, action: "villain_raise",
          label: `Villain raises to ${R.toFixed(1)} bb`,
          betSize: R / potSize, betSizeBb: R,
          potAfter: potSize + S + R, heroInvestmentAfter: heroInvestment + S,
          villainFoldPct: 0, villainCallPct: 0, villainRaisePct: 0,
          heroFoldToRaise,
          equityAssumption: equity, equity_is_approximated: street !== "flop",
          ev: null, expanded: false, isLeaf: false,
          children: [
            { id: makeNodeId(betId, "hero_fold_raise", null), street, action: "hero_fold",
              label: "Hero folds to raise", betSize: 0, betSizeBb: 0,
              potAfter: potSize + S + R, heroInvestmentAfter: heroInvestment + S,
              villainFoldPct: 0, villainCallPct: 100, villainRaisePct: 0,
              heroFoldToRaise: 0, equityAssumption: equity,
              equity_is_approximated: street !== "flop",
              ev: null, expanded: false, children: [], isLeaf: true },
            { id: makeNodeId(betId, "hero_call_raise", null), street, action: "hero_call",
              label: "Hero calls raise", betSize: 0, betSizeBb: 0,
              potAfter: potSize + 2 * R, heroInvestmentAfter: heroInvestment + R,
              villainFoldPct: 0, villainCallPct: 100, villainRaisePct: 0,
              heroFoldToRaise: 0, equityAssumption: equity,
              equity_is_approximated: nextStreet !== "flop",
              ev: null, expanded: false, children: [], isLeaf: true },
          ]},
      ],
    });
  });

  return nodes;
}
```

**Step 3: Verify (paste artifact)**
- No errors on load.
- The function is not called yet so no visual change — that's fine.

**Step 4: Commit**
```bash
git add RangeIQ.jsx
git commit -m "feat(m3): buildTree — recursive tree generation with GTO seeding"
```

---

## Task 3: `computeNodeEV` Pure Function

**Files:**
- Modify: `RangeIQ.jsx` — add below `buildTree`, above `// MODULE 3` comment

**Step 1: Add `computeNodeEV`**
```js
function computeNodeEV(node) {
  const eq = node.equityAssumption;
  const pot = node.potAfter;
  const inv = node.heroInvestmentAfter;

  // ── LEAF NODES ──
  if (node.isLeaf) {
    switch (node.action) {
      case "villain_fold":  return pot;                              // hero wins pot
      case "hero_fold":     return -inv;                            // hero loses investment
      case "check_behind":
      case "hero_call":
      case "villain_call":  return eq * pot - (1 - eq) * inv;      // showdown
      default:              return eq * pot - (1 - eq) * inv;
    }
  }

  // ── BET NODES (villain responds) ──
  if (node.action === "bet" || node.action === "villain_bet") {
    const foldChild  = node.children.find(c => c.action === "villain_fold");
    const callChild  = node.children.find(c => c.action === "villain_call");
    const raiseChild = node.children.find(c => c.action === "villain_raise");

    const foldEV  = foldChild  ? computeNodeEV(foldChild)  : 0;
    const callEV  = callChild  ? computeNodeEV(callChild)  : 0;

    let raiseEV = 0;
    if (raiseChild) {
      const heroFold = node.heroFoldToRaise / 100;
      const heroFoldChild = raiseChild.children.find(c => c.id.includes("hero_fold"));
      const heroCallChild = raiseChild.children.find(c => c.id.includes("hero_call"));
      const heroFoldEV = heroFoldChild ? computeNodeEV(heroFoldChild) : 0;
      const heroCallEV = heroCallChild ? computeNodeEV(heroCallChild) : 0;
      raiseEV = heroFold * heroFoldEV + (1 - heroFold) * heroCallEV;
    }

    const fP = node.villainFoldPct / 100;
    const cP = node.villainCallPct / 100;
    const rP = node.villainRaisePct / 100;
    return fP * foldEV + cP * callEV + rP * raiseEV;
  }

  // ── CHECK NODES (hero checks, villain may bet or check) ──
  if (node.action === "check") {
    if (!node.children?.length) return eq * pot - (1 - eq) * inv;
    // Display all child EVs; return best available action EV
    const childEVs = node.children.map(computeNodeEV);
    return Math.max(...childEVs);
  }

  // ── VILLAIN BET RESPONSE (hero faces bet) ──
  if (node.action === "villain_bet") {
    const heroFold = node.heroFoldToRaise / 100;
    const foldChild = node.children.find(c => c.action === "hero_fold");
    const callChild = node.children.find(c => c.action === "hero_call");
    const foldEV = foldChild ? computeNodeEV(foldChild) : 0;
    const callEV = callChild ? computeNodeEV(callChild) : 0;
    return heroFold * foldEV + (1 - heroFold) * callEV;
  }

  // Fallthrough: recurse into children, return best
  if (node.children?.length) {
    return Math.max(...node.children.map(computeNodeEV));
  }
  return eq * pot - (1 - eq) * inv;
}

// Walk tree and stamp ev on every node (mutates a deep clone)
function stampEV(nodes) {
  return nodes.map(n => {
    const children = n.children?.length ? stampEV(n.children) : [];
    const withChildren = { ...n, children };
    return { ...withChildren, ev: computeNodeEV(withChildren) };
  });
}
```

**Step 2: Verify (paste artifact)**
- No errors on load.

**Step 3: Commit**
```bash
git add RangeIQ.jsx
git commit -m "feat(m3): computeNodeEV + stampEV — recursive EV computation"
```

---

## Task 4: `TreeNode` Recursive Renderer

**Files:**
- Modify: `RangeIQ.jsx` — add component above `// MODULE 3` comment

**Step 1: Add `TreeNode` component**
```js
function TreeNode({ node, depth, selectedLine, dispatch, siblingCollapse }) {
  const isSelected = selectedLine.includes(node.id);
  const evColor = node.ev === null ? T.muted
    : node.ev > 0.5 ? T.green
    : node.ev < -0.5 ? T.red
    : T.yellow;

  const approxBadge = node.equity_is_approximated
    ? <span style={{ color: T.yellow, fontSize: 10, marginLeft: 4 }}>⚠approx</span>
    : null;

  // Derived: raise% = 100 - fold - call (clamped)
  const raiseComputed = Math.max(0, 100 - node.villainFoldPct - node.villainCallPct);

  const handleSelectLine = () => {
    // Build ancestor chain by dispatching new selectedLine ending at this node
    // The line is tracked externally; here we just dispatch the new leaf
    dispatch({ type: "SET_EV_SELECTED_LINE", payload: buildAncestorChain(node.id) });
  };

  const handleFreqChange = (field, val) => {
    const num = Math.min(100, Math.max(0, +val));
    dispatch({ type: "UPDATE_EV_NODE_FREQ", payload: { id: node.id, patch: { [field]: num } } });
  };

  const rowBg = isSelected ? `${T.blue}22` : "transparent";
  const indentPx = depth * 20;

  return (
    <div>
      <div
        style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "3px 6px", marginLeft: indentPx,
          background: rowBg, borderRadius: 4, cursor: "pointer",
          borderLeft: isSelected ? `2px solid ${T.blue}` : "2px solid transparent",
        }}
        onMouseEnter={() => dispatch({ type: "SET_EV_HOVERED", payload: node.id })}
        onMouseLeave={() => dispatch({ type: "SET_EV_HOVERED", payload: null })}
      >
        {/* Expand/collapse toggle */}
        {!node.isLeaf && (
          <span
            style={{ color: T.muted, fontSize: 10, width: 12, userSelect: "none" }}
            onClick={e => { e.stopPropagation(); dispatch({ type: "TOGGLE_EV_NODE_EXPANDED", payload: node.id }); }}
          >
            {node.expanded ? "▾" : "▸"}
          </span>
        )}
        {node.isLeaf && <span style={{ width: 12 }} />}

        {/* Action label */}
        <span style={{ color: T.text, fontSize: 12, flex: 1, fontFamily: "monospace" }}>
          {node.label}
          {approxBadge}
        </span>

        {/* Pot */}
        <span style={{ color: T.muted, fontSize: 11, fontFamily: "monospace", width: 70, textAlign: "right" }}>
          pot {node.potAfter.toFixed(1)} bb
        </span>

        {/* EV */}
        <span style={{ color: evColor, fontSize: 12, fontFamily: "monospace", width: 70, textAlign: "right" }}>
          {node.ev !== null ? `EV ${node.ev.toFixed(2)}` : "—"}
        </span>

        {/* Freq inputs (only on bet/check_behind nodes, not pure leaves like villain_fold) */}
        {(node.action === "bet" || node.action === "villain_bet") && (
          <span style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <input type="number" min={0} max={100} value={Math.round(node.villainFoldPct)}
              onChange={e => handleFreqChange("villainFoldPct", e.target.value)}
              style={{ width: 40, background: T.bgElevated, color: T.text, border: `1px solid ${T.border}`, borderRadius: 3, padding: "1px 4px", fontSize: 10, fontFamily: "monospace" }}
            />
            <span style={{ color: T.muted, fontSize: 10 }}>F%</span>
            <input type="number" min={0} max={100} value={Math.round(node.villainCallPct)}
              onChange={e => handleFreqChange("villainCallPct", e.target.value)}
              style={{ width: 40, background: T.bgElevated, color: T.text, border: `1px solid ${T.border}`, borderRadius: 3, padding: "1px 4px", fontSize: 10, fontFamily: "monospace" }}
            />
            <span style={{ color: T.muted, fontSize: 10 }}>C%</span>
            <span style={{ color: T.muted, fontSize: 10, width: 30, textAlign: "right", fontFamily: "monospace" }}>
              {raiseComputed}R%
            </span>
          </span>
        )}

        {/* HeroFoldToRaise input on raise nodes */}
        {node.action === "villain_raise" && (
          <span style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <input type="number" min={0} max={100} value={Math.round(node.heroFoldToRaise)}
              onChange={e => handleFreqChange("heroFoldToRaise", e.target.value)}
              style={{ width: 44, background: T.bgElevated, color: T.text, border: `1px solid ${T.border}`, borderRadius: 3, padding: "1px 4px", fontSize: 10, fontFamily: "monospace" }}
            />
            <span style={{ color: T.muted, fontSize: 10 }}>hFold%</span>
          </span>
        )}

        {/* Select line button */}
        {node.isLeaf && (
          <Btn
            onClick={e => { e.stopPropagation(); handleSelectLine(); }}
            style={{ fontSize: 10, padding: "1px 6px", marginLeft: 4 }}
          >
            Select
          </Btn>
        )}
      </div>

      {/* Children */}
      {node.expanded && !node.isLeaf && node.children?.map(child => (
        <TreeNode key={child.id} node={child} depth={depth + 1}
          selectedLine={selectedLine} dispatch={dispatch}
          siblingCollapse={siblingCollapse} />
      ))}
    </div>
  );
}
```

**Step 2: Add `buildAncestorChain` helper** (above TreeNode):

This helper reconstructs the ancestor chain for a given leaf ID. The node ID encodes the path (each segment separated by `__`), so we can split it:

```js
function buildAncestorChain(leafId) {
  // IDs are constructed as root__action1__action2__...
  // Each prefix is a valid ancestor node ID
  const parts = leafId.split("__");
  const chain = [];
  for (let i = 1; i <= parts.length; i++) {
    chain.push(parts.slice(0, i).join("__"));
  }
  return chain;
}
```

**Step 3: Verify (paste artifact)**
- No errors. TreeNode not rendered yet.

**Step 4: Commit**
```bash
git add RangeIQ.jsx
git commit -m "feat(m3): TreeNode recursive renderer + buildAncestorChain"
```

---

## Task 5: `BreakevenPanel` Component

**Files:**
- Modify: `RangeIQ.jsx` — add above `// MODULE 3` comment

**Step 1: Add `BreakevenPanel`**
```js
function BreakevenPanel({ node }) {
  if (!node) {
    return (
      <Card style={{ width: 220, minHeight: 160, flexShrink: 0 }}>
        <Label>Breakeven Analysis</Label>
        <div style={{ color: T.muted, fontSize: 12, marginTop: 12 }}>
          Hover a bet node to see analysis.
        </div>
      </Card>
    );
  }

  const S = node.betSizeBb;
  const P = node.potAfter - S; // pot before bet
  const bePct = S > 0 ? S / (P + S) : null;
  const gtoBluffFreq = S > 0 ? S / (S + P) : null;
  const bluffValueRatio = S > 0 ? S / P : null;

  // Actual bluff% approximation from fold%: if villain folds foldPct, hero needs
  // to bluff at most gtoBluffFreq fraction of betting range to be unexploitable
  const actualBluffFreq = gtoBluffFreq; // placeholder — no bluff/value split in tree
  const exploitGap = gtoBluffFreq !== null
    ? Math.abs(actualBluffFreq - gtoBluffFreq)
    : null;

  const evColor = node.ev === null ? T.muted
    : node.ev > 0.5 ? T.green
    : node.ev < -0.5 ? T.red
    : T.yellow;

  return (
    <Card style={{ width: 220, minHeight: 160, flexShrink: 0 }}>
      <Label>Breakeven Analysis</Label>
      <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
        <div style={{ fontFamily: "monospace", fontSize: 12 }}>
          <span style={{ color: T.muted }}>Node: </span>
          <span style={{ color: T.text }}>{node.label}</span>
        </div>
        <div style={{ fontFamily: "monospace", fontSize: 12 }}>
          <span style={{ color: T.muted }}>EV: </span>
          <span style={{ color: evColor }}>{node.ev?.toFixed(2) ?? "—"} bb</span>
        </div>
        {bePct !== null && (
          <>
            <div style={{ fontFamily: "monospace", fontSize: 12 }}>
              <span style={{ color: T.muted }}>BE%: </span>
              <span style={{ color: T.text }}>{(bePct * 100).toFixed(1)}%</span>
            </div>
            <div style={{ fontFamily: "monospace", fontSize: 12 }}>
              <span style={{ color: T.muted }}>GTO bluff freq: </span>
              <span style={{ color: T.text }}>{(gtoBluffFreq * 100).toFixed(1)}%</span>
            </div>
            <div style={{ fontFamily: "monospace", fontSize: 12 }}>
              <span style={{ color: T.muted }}>Bluff:Value ratio: </span>
              <span style={{ color: T.text }}>{bluffValueRatio?.toFixed(2)} : 1</span>
            </div>
          </>
        )}
        {node.equity_is_approximated && (
          <div style={{ color: T.yellow, fontSize: 10, marginTop: 4 }}>
            ⚠ Equity approximated (multi-street)
          </div>
        )}
      </div>
    </Card>
  );
}
```

**Step 2: Verify (paste artifact)** — no errors.

**Step 3: Commit**
```bash
git add RangeIQ.jsx
git commit -m "feat(m3): BreakevenPanel component"
```

---

## Task 6: Replace Module3 Stub with Full UI

**Files:**
- Modify: `RangeIQ.jsx:997-1052` — replace entire `Module3` function

**Step 1: Replace `Module3`**

Find the entire Module3 function (lines 997-1052) and replace with:

```js
// ============================================================
// MODULE 3 — MULTI-STREET EV TREE
// ============================================================
function Module3({ state, dispatch }) {
  const { evTreeConfig, metrics } = state;
  const { potSize, effStack, betSizings, nodes, selectedLine, hoveredNodeId, siblingCollapseEnabled } = evTreeConfig;

  // Equity source: prefer MC result, fall back to 0.5
  const equity = metrics.equity?.hero != null ? metrics.equity.hero / 100 : 0.5;
  const equityLabel = metrics.equity?.hero != null
    ? `MC: ${metrics.equity.hero.toFixed(1)}%`
    : "Default: 50.0%";

  // Find hovered node (for BreakevenPanel)
  const findNode = (nodeList, id) => {
    for (const n of nodeList) {
      if (n.id === id) return n;
      if (n.children?.length) {
        const found = findNode(n.children, id);
        if (found) return found;
      }
    }
    return null;
  };
  const hoveredNode = hoveredNodeId ? findNode(nodes, hoveredNodeId) : null;

  const handleBuild = () => {
    const sizings = betSizings;
    const raw = buildTree({ potSize, effStack, betSizings: sizings, equity, street: "flop" });
    const stamped = stampEV(raw);
    dispatch({ type: "SET_EV_TREE_NODES", payload: stamped });
    dispatch({ type: "SET_EV_SELECTED_LINE", payload: [] });
  };

  const handleSizingsChange = (val) => {
    const parsed = val.split(",").map(s => parseFloat(s.trim())).filter(n => !isNaN(n) && n > 0 && n <= 3);
    if (parsed.length) dispatch({ type: "SET_EV_TREE_CONFIG", payload: { betSizings: parsed } });
  };

  // Check if selectedLine ends at a leaf
  const lastSelectedId = selectedLine[selectedLine.length - 1];
  const lastSelectedNode = lastSelectedId ? findNode(nodes, lastSelectedId) : null;
  const lineComplete = lastSelectedNode?.isLeaf === true;

  const handleSendToTrace = () => {
    if (!lineComplete) return;
    const line = selectedLine.map(id => {
      const n = findNode(nodes, id);
      if (!n) return null;
      return {
        id: n.id,
        street: n.street,
        action: n.action,
        bet_size_fraction: n.betSize,
        bet_size_bb: parseFloat(n.betSizeBb.toFixed(2)),
        pot_after_bb: parseFloat(n.potAfter.toFixed(2)),
        hero_investment_bb: parseFloat(n.heroInvestmentAfter.toFixed(2)),
        villain_fold_pct: n.villainFoldPct,
        villain_call_pct: n.villainCallPct,
        villain_raise_pct: Math.max(0, 100 - n.villainFoldPct - n.villainCallPct),
        equity: parseFloat(n.equityAssumption.toFixed(4)),
        equity_is_approximated: n.equity_is_approximated,
        ev_bb: n.ev !== null ? parseFloat(n.ev.toFixed(4)) : null,
      };
    }).filter(Boolean);

    dispatch({ type: "SET_EV_TREE_CONFIG", payload: { evTreeLine: line } });
    dispatch({ type: "SET_MODULE", payload: 4 });
  };

  return (
    <div style={{ display: "flex", gap: 16 }}>
      {/* Main column */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Control panel */}
        <div style={{ display: "flex", gap: 10, marginBottom: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
          <Card style={{ flex: "0 0 auto" }}>
            <Label>Pot (bb)</Label>
            <input type="number" value={potSize}
              onChange={e => dispatch({ type: "SET_EV_TREE_CONFIG", payload: { potSize: +e.target.value } })}
              style={{ background: T.bgElevated, color: T.text, border: `1px solid ${T.border}`, borderRadius: 4, padding: "4px 8px", width: 70, fontFamily: "monospace" }}
            />
          </Card>
          <Card style={{ flex: "0 0 auto" }}>
            <Label>Stack (bb)</Label>
            <input type="number" value={effStack}
              onChange={e => dispatch({ type: "SET_EV_TREE_CONFIG", payload: { effStack: +e.target.value } })}
              style={{ background: T.bgElevated, color: T.text, border: `1px solid ${T.border}`, borderRadius: 4, padding: "4px 8px", width: 70, fontFamily: "monospace" }}
            />
          </Card>
          <Card style={{ flex: "1 1 160px" }}>
            <Label>Bet Sizings (fractions)</Label>
            <input type="text" defaultValue={betSizings.join(", ")}
              onBlur={e => handleSizingsChange(e.target.value)}
              style={{ background: T.bgElevated, color: T.text, border: `1px solid ${T.border}`, borderRadius: 4, padding: "4px 8px", width: "100%", fontFamily: "monospace", boxSizing: "border-box" }}
            />
          </Card>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <span style={{ fontSize: 11, color: T.muted, fontFamily: "monospace" }}>
              Equity: <span style={{ color: metrics.equity?.hero != null ? T.green : T.muted }}>{equityLabel}</span>
            </span>
            <Btn onClick={handleBuild} style={{ background: T.blue, color: "#fff" }}>
              Build Tree
            </Btn>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" id="sibCollapseToggle"
              checked={siblingCollapseEnabled}
              onChange={e => dispatch({ type: "SET_EV_TREE_CONFIG", payload: { siblingCollapseEnabled: e.target.checked } })}
            />
            <label htmlFor="sibCollapseToggle" style={{ color: T.muted, fontSize: 11 }}>Auto-collapse siblings</label>
          </div>
        </div>

        {/* Tree */}
        {nodes.length === 0 ? (
          <Card>
            <div style={{ color: T.muted, fontSize: 12, textAlign: "center", padding: 24 }}>
              Set pot size, stack, and sizings, then click <strong style={{ color: T.text }}>Build Tree</strong>.
            </div>
          </Card>
        ) : (
          <Card style={{ maxHeight: 520, overflowY: "auto" }}>
            {nodes.map(node => (
              <TreeNode key={node.id} node={node} depth={0}
                selectedLine={selectedLine} dispatch={dispatch}
                siblingCollapse={siblingCollapseEnabled} />
            ))}
          </Card>
        )}

        {/* Send to Trace button */}
        {nodes.length > 0 && (
          <div style={{ marginTop: 10, display: "flex", gap: 10, alignItems: "center" }}>
            <Btn
              onClick={handleSendToTrace}
              disabled={!lineComplete}
              style={{
                background: lineComplete ? T.green : T.bgElevated,
                color: lineComplete ? "#000" : T.muted,
                opacity: lineComplete ? 1 : 0.5,
              }}
            >
              Send to Trace →
            </Btn>
            {!lineComplete && selectedLine.length > 0 && (
              <span style={{ color: T.yellow, fontSize: 11 }}>Select a complete line (end at leaf)</span>
            )}
            {selectedLine.length === 0 && (
              <span style={{ color: T.muted, fontSize: 11 }}>Click "Select" on a leaf node to choose a line</span>
            )}
          </div>
        )}
      </div>

      {/* Sticky side panel */}
      <div style={{ position: "sticky", top: 0, alignSelf: "flex-start" }}>
        <BreakevenPanel node={hoveredNode} />
      </div>
    </div>
  );
}
```

**Step 2: Verify (paste artifact)**
- Click Module 3 tab — control panel renders.
- Click "Build Tree" with default pot=6, stack=100 — tree appears with Check and Bet nodes.
- Expand nodes — children appear.
- EV values display in green/yellow/red.
- Hovering a bet node updates the BreakevenPanel on the right.
- Click "Select" on a leaf — Send to Trace button activates.
- Click "Send to Trace" — switches to Module 4 tab.

**Step 3: Commit**
```bash
git add RangeIQ.jsx
git commit -m "feat(m3): full Module3 UI — control panel, tree, breakeven panel, Send to Trace"
```

---

## Task 7: Wire ev_tree_line into Module 4 `buildContext`

**Files:**
- Modify: `RangeIQ.jsx:1061-1083` — update `buildContext` in Module4

**Step 1: Find `buildContext` in Module4 (around line 1061)**

Find this section:
```js
    decision_context: {
      action_facing: null,
      available_actions: ["fold","check","call","bet_half","bet_pot","raise"],
    }
```

Replace with:
```js
    decision_context: {
      action_facing: null,
      available_actions: ["fold","check","call","bet_half","bet_pot","raise"],
      ev_tree_line: state.evTreeConfig.evTreeLine ?? null,
    }
```

**Step 2: Verify (paste artifact)**
- Generate a trace after selecting an EV tree line in Module 3.
- The exported JSONL record should include `decision_context.ev_tree_line` as an array of node objects.
- Each node object should include `equity_is_approximated`.

**Step 3: Commit**
```bash
git add RangeIQ.jsx
git commit -m "feat(m4): wire ev_tree_line into trace context from Module 3 selectedLine"
```

---

## Task 8: Add `evTreeLine` to initialState & reducer

**Files:**
- Modify: `RangeIQ.jsx:452-455` — evTreeConfig initialState

**Step 1: Add `evTreeLine: null` to evTreeConfig**

In the evTreeConfig block added in Task 1, add:
```js
    evTreeLine: null,       // serialized selectedLine for Module 4
```

**Step 2: Verify (paste artifact)** — `state.evTreeConfig.evTreeLine` is always defined (no `undefined` access errors).

**Step 3: Commit**
```bash
git add RangeIQ.jsx
git commit -m "fix(m3): initialize evTreeLine in evTreeConfig state"
```

---

## Verification Checklist

Before calling Module 3 complete, verify all of the following in the artifact:

- [ ] Build Tree renders Check + Bet nodes at flop depth
- [ ] Expanding bet node shows Villain Fold / Villain Call / Villain Raise children
- [ ] EV values are non-null and color-coded after Build Tree
- [ ] Hovering a bet node shows BE%, GTO bluff freq, bluff:value ratio in side panel
- [ ] Frequency inputs (F%, C%, derived R%) update live; EV does NOT auto-recompute (requires another Build Tree click — acceptable for prototype)
- [ ] `⚠approx` badge appears on turn and river depth nodes
- [ ] Clicking "Select" on a leaf populates selectedLine and enables "Send to Trace"
- [ ] "Send to Trace" switches to Module 4 tab
- [ ] Module 4 trace context includes `decision_context.ev_tree_line` with `equity_is_approximated` per node
- [ ] Sibling collapse toggle in control panel exists (default OFF)
- [ ] No console errors at any point

---

## Known Limitations (document, don't fix now)

- EV does not auto-recompute when villain frequencies are manually edited — user must rebuild
- Equity is static across all streets (equity_is_approximated flag handles disclosure)
- Raise sizing is fixed at 2.5x; not yet configurable per node
- No batch line enumeration (all root-to-leaf paths) — deferred to P2
