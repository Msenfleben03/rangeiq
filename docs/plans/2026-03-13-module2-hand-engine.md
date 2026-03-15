# Module 2 Hand Engine Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the full Module 2 poker engine: hand evaluation, Monte Carlo equity, range breakdown, and board texture metrics inside `RangeIQ.jsx`.

**Architecture:** Pure JS functions inserted into `RangeIQ.jsx` between the constants block and state management. `evalHand5` returns a comparable numeric array for showdown resolution. `classifyHand` adds board-relative sub-classification + draw detection for UI display. `runMonteCarlo` chunks via `setTimeout` (5k iterations/chunk) to avoid blocking the artifact renderer.

**Tech Stack:** React (useReducer already wired), recharts BarChart (already imported), pure JS poker logic (no external deps), artifact runtime (no localStorage, no build step).

**Risk areas:**
1. `evalHand5` tiebreaker arrays must be strictly comparable — use JSON string compare if array compare is tricky
2. Monte Carlo card overlap check must exclude board + deadCards + other combo's cards
3. Single-file constraint — all code goes in `RangeIQ.jsx`, no imports

---

## Context

File: `RangeIQ.jsx` — 920 lines. Insert all new functions in the `// POKER ENGINE` section, placed **between line 92 (`totalCombos` function ends) and line 94 (`// STATE MANAGEMENT` comment)**.

Existing utilities to reuse:
- `RANKS` — `["A","K","Q","J","T","9","8","7","6","5","4","3","2"]`
- `SUITS` — `["s","h","d","c"]`
- `DECK` — all 52 cards
- `expandHand(hand, deadCards)` — expands "AKs" → `[["As","Kh"], ...]`

---

## Task 1: Card Rank/Suit Utilities

**Files:**
- Modify: `RangeIQ.jsx` — insert after line 92 (after `totalCombos` function)

**Step 1: Insert utility block**

```js
// ============================================================
// POKER ENGINE — Hand Evaluation & Monte Carlo
// ============================================================
const RANK_VAL = { A:14,K:13,Q:12,J:11,T:10,9:9,8:8,7:7,6:6,5:5,4:4,3:3,2:2 };
function cardRank(c) { return RANK_VAL[c[0]]; }
function cardSuit(c) { return c[1]; }

// All k-combinations from array
function combinations(arr, k) {
  if (k === 0) return [[]];
  if (arr.length < k) return [];
  const [h, ...t] = arr;
  return [
    ...combinations(t, k - 1).map(c => [h, ...c]),
    ...combinations(t, k),
  ];
}
```

**Step 2: Manual verify logic**
- `cardRank("As")` → 14, `cardRank("2c")` → 2
- `combinations([1,2,3], 2)` → `[[1,2],[1,3],[2,3]]`
- `combinations([1,2,3,4,5], 5).length` → 1

---

## Task 2: evalHand5 — Best 5-Card Hand Rank

**Files:**
- Modify: `RangeIQ.jsx` — insert after Task 1 block

**Step 1: Insert `evalHand5`**

Returns `[handRank, ...tiebreakers]` where handRank: 8=SF, 7=quads, 6=FH, 5=flush, 4=straight, 3=trips, 2=two-pair, 1=pair, 0=high-card. Arrays compared element-by-element.

```js
function evalHand5(cards) {
  const ranks = cards.map(cardRank).sort((a, b) => b - a);
  const suits = cards.map(cardSuit);
  const rankSet = [...new Set(ranks)];

  // Flush check
  const flushSuit = suits.find(s => suits.filter(x => x === s).length >= 5) || null;
  const isFlush = flushSuit !== null;

  // Straight check (including A-low wheel: A=1)
  function hasStraight(rs) {
    const unique = [...new Set(rs)].sort((a, b) => b - a);
    // Check A-low wheel
    const withAceLow = unique.includes(14) ? [...unique, 1] : unique;
    const dedup = [...new Set(withAceLow)].sort((a, b) => b - a);
    for (let i = 0; i <= dedup.length - 5; i++) {
      if (dedup[i] - dedup[i + 4] === 4 &&
          new Set(dedup.slice(i, i + 5)).size === 5) {
        return dedup[i]; // high card of straight
      }
    }
    return null;
  }
  const straightHigh = hasStraight(ranks);

  // Group by rank
  const groups = {};
  ranks.forEach(r => { groups[r] = (groups[r] || 0) + 1; });
  const counts = Object.values(groups).sort((a, b) => b - a);
  const byCount = (n) => Object.keys(groups)
    .filter(r => groups[r] === n)
    .map(Number)
    .sort((a, b) => b - a);

  const quads = byCount(4);
  const trips = byCount(3);
  const pairs = byCount(2);
  const singles = byCount(1);

  // Straight flush
  if (isFlush && straightHigh) {
    const flushRanks = cards.filter(c => cardSuit(c) === flushSuit).map(cardRank);
    const sfHigh = hasStraight(flushRanks);
    if (sfHigh) return [8, sfHigh];
  }
  // Quads
  if (quads.length) {
    const kicker = [...trips, ...pairs, ...singles].filter(r => r !== quads[0])[0] || 0;
    return [7, quads[0], kicker];
  }
  // Full house
  if (trips.length && pairs.length) return [6, trips[0], pairs[0]];
  if (trips.length >= 2) return [6, trips[0], trips[1]];
  // Flush
  if (isFlush) {
    const fr = cards.filter(c => cardSuit(c) === flushSuit)
      .map(cardRank).sort((a, b) => b - a).slice(0, 5);
    return [5, ...fr];
  }
  // Straight
  if (straightHigh) return [4, straightHigh];
  // Trips
  if (trips.length) {
    const kickers = [...pairs, ...singles].filter(r => r !== trips[0]).slice(0, 2);
    return [3, trips[0], ...kickers];
  }
  // Two pair
  if (pairs.length >= 2) {
    const kicker = singles.find(r => r !== pairs[0] && r !== pairs[1]) || 0;
    return [2, pairs[0], pairs[1], kicker];
  }
  // One pair
  if (pairs.length === 1) {
    const kickers = singles.filter(r => r !== pairs[0]).slice(0, 3);
    return [1, pairs[0], ...kickers];
  }
  // High card
  return [0, ...ranks.slice(0, 5)];
}
```

**Step 2: Manual verification cases**
- Royal flush `["As","Ks","Qs","Js","Ts"]` → `[8, 14]`
- Wheel `["Ah","2s","3d","4c","5h"]` → `[4, 5]`
- Two pair `["As","Ad","Ks","Kd","Qh"]` → `[2, 14, 13, 12]`

---

## Task 3: evalHand7 + compareHands

**Files:**
- Modify: `RangeIQ.jsx` — insert after Task 2 block

**Step 1: Insert functions**

```js
// Best 5-card hand from 7 cards (21 combinations)
function evalHand7(cards7) {
  return combinations(cards7, 5)
    .map(evalHand5)
    .reduce((best, curr) => {
      for (let i = 0; i < Math.max(best.length, curr.length); i++) {
        if ((curr[i] || 0) > (best[i] || 0)) return curr;
        if ((curr[i] || 0) < (best[i] || 0)) return best;
      }
      return best;
    });
}

// Returns 1 if a wins, -1 if b wins, 0 if tie
function compareHands(cards7a, cards7b) {
  const a = evalHand7(cards7a);
  const b = evalHand7(cards7b);
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if ((a[i] || 0) > (b[i] || 0)) return 1;
    if ((a[i] || 0) < (b[i] || 0)) return -1;
  }
  return 0;
}
```

**Step 2: Manual verify**
- `compareHands(["As","Ks","Qs","Js","Ts","2h","3c"], ["Kh","Kd","Kc","Ah","Ad","2d","3d"])` → 1 (royal flush beats full house)

---

## Task 4: classifyHand — Board-Relative Classification

**Files:**
- Modify: `RangeIQ.jsx` — insert after Task 3 block

**Step 1: Insert `classifyHand`**

```js
// classifyHand(holeCards, board)
// Returns { category: string, strength: number (0-1), draws: string[] }
function classifyHand(holeCards, board) {
  if (!board || board.length < 3) return { category: "Preflop", strength: 0, draws: [] };

  const allCards = [...holeCards, ...board];
  const handVal = evalHand7(allCards);
  const handRank = handVal[0];

  const boardRanks = board.map(cardRank).sort((a, b) => b - a);
  const hRanks = holeCards.map(cardRank).sort((a, b) => b - a);

  let category = "";
  // Made hand category from hand rank
  if (handRank === 8) category = "Straight Flush";
  else if (handRank === 7) category = "Quads";
  else if (handRank === 6) category = "Full House";
  else if (handRank === 5) category = "Flush";
  else if (handRank === 4) category = "Straight";
  else if (handRank === 3) category = "Three of a Kind";
  else if (handRank === 2) {
    category = "Two Pair";
  } else if (handRank === 1) {
    // Sub-classify pair
    const pairRank = handVal[1];
    const topBoard = boardRanks[0];
    const isHolePair = hRanks[0] === hRanks[1];
    if (isHolePair) {
      if (pairRank > topBoard) category = "Overpair";
      else if (pairRank === boardRanks[boardRanks.length - 1]) category = "Underpair";
      else category = "Middle Pair";
    } else {
      // Paired with board
      if (pairRank === topBoard) {
        // Top pair — classify kicker
        const kicker = hRanks.find(r => r !== pairRank) || 0;
        category = kicker >= 10 ? "Top Pair (Good Kicker)" : "Top Pair (Weak Kicker)";
      } else if (pairRank === boardRanks[1]) category = "Middle Pair";
      else if (pairRank === boardRanks[boardRanks.length - 1]) category = "Bottom Pair";
      else category = "Pair";
    }
  } else {
    // No made hand — check for ace high, etc.
    const maxHole = Math.max(...hRanks);
    if (maxHole === 14) category = "Ace High";
    else category = "No Made Hand";
  }

  // Strength: normalize hand rank to 0-1
  // handRank 0-8 → crude strength + tiebreaker component
  const strength = Math.min(1, (handRank / 8) * 0.85 + (handVal[1] || 0) / 14 * 0.15);

  const draws = detectDraws(holeCards, board);

  return { category, strength, draws };
}
```

---

## Task 5: detectDraws

**Files:**
- Modify: `RangeIQ.jsx` — insert immediately before `classifyHand` (Task 4 block)

**Step 1: Insert `detectDraws`**

```js
function detectDraws(holeCards, board) {
  const draws = [];
  const allCards = [...holeCards, ...board];
  const allRanks = allCards.map(cardRank);
  const holeSuits = holeCards.map(cardSuit);
  const boardSuits = board.map(cardSuit);

  // Flush draws: count suits across all 7-card window (but only hole+board available)
  const suitCounts = {};
  allCards.forEach(c => { const s = cardSuit(c); suitCounts[s] = (suitCounts[s] || 0) + 1; });
  for (const [suit, count] of Object.entries(suitCounts)) {
    if (count >= 5) break; // already a flush (made hand handles it)
    if (count === 4) {
      // Check if hero hole cards contribute
      const heroContrib = holeCards.filter(c => cardSuit(c) === suit).length;
      if (heroContrib > 0) {
        // Nut flush draw if hero holds the Ace of that suit
        const hasNutFD = holeCards.some(c => cardSuit(c) === suit && cardRank(c) === 14);
        draws.push(hasNutFD ? "Nut Flush Draw" : "Flush Draw");
      }
    }
    if (count === 3 && board.length <= 4) {
      const heroContrib = holeCards.filter(c => cardSuit(c) === suit).length;
      const boardContrib = board.filter(c => cardSuit(c) === suit).length;
      if (heroContrib >= 1 && boardContrib >= 2) draws.push("Backdoor FD");
    }
  }

  // Straight draws: work with all ranks + ace-low
  const uniqueRanks = [...new Set(allRanks)].sort((a, b) => a - b);
  const withAceLow = uniqueRanks.includes(14) ? [1, ...uniqueRanks] : uniqueRanks;
  const dedupRanks = [...new Set(withAceLow)].sort((a, b) => a - b);

  // Scan every 5-rank window for draws
  for (let lo = 1; lo <= 10; lo++) {
    const window = [lo, lo+1, lo+2, lo+3, lo+4];
    const hits = window.filter(r => dedupRanks.includes(r)).length;
    if (hits === 4) {
      const missing = window.find(r => !dedupRanks.includes(r));
      if (missing === lo || missing === lo + 4) draws.push("OESD");
      else draws.push("Gutshot");
    }
    if (hits === 3 && board.length <= 4) {
      draws.push("Backdoor SD");
      break; // only flag once
    }
  }

  // Double gutshot: two different gutshot windows
  const gutWindows = [];
  for (let lo = 1; lo <= 10; lo++) {
    const window = [lo, lo+1, lo+2, lo+3, lo+4];
    const hits = window.filter(r => dedupRanks.includes(r)).length;
    if (hits === 4) {
      const missing = window.find(r => !dedupRanks.includes(r));
      if (missing !== lo && missing !== lo + 4) gutWindows.push(lo);
    }
  }
  if (gutWindows.length >= 2) {
    // Replace individual gutshots with double gutshot
    const idx = draws.lastIndexOf("Gutshot");
    if (idx !== -1) draws.splice(draws.indexOf("Gutshot"), 2, "Double Gutshot");
  }

  // Overcard draws (hole card > all board ranks, no pair yet)
  const boardTop = Math.max(...board.map(cardRank));
  const overcards = holeCards.filter(c => cardRank(c) > boardTop);
  if (overcards.length > 0 && evalHand7([...holeCards, ...board])[0] === 0) {
    draws.push("Overcard Draw");
  }

  return [...new Set(draws)]; // deduplicate
}
```

---

## Task 6: runMonteCarlo — Chunked Equity Engine

**Files:**
- Modify: `RangeIQ.jsx` — insert after Task 3 block (compareHands)

**Step 1: Insert `runMonteCarlo`**

```js
function runMonteCarlo(heroRange, villainRange, board, deadCards, dispatch, iterations = 50000) {
  const CHUNK = 5000;

  // Pre-expand all combos (filter dead cards + board)
  const usedPreflop = new Set([...board, ...deadCards]);
  const heroCombos = [...heroRange].flatMap(h => expandHand(h, [...usedPreflop]));
  const villainCombos = [...villainRange].flatMap(h => expandHand(h, [...usedPreflop]));

  if (!heroCombos.length || !villainCombos.length) {
    dispatch({ type: "SET_MC_RUNNING", payload: false });
    return;
  }

  // Remaining deck for runout
  const deckArr = DECK.filter(c => !usedPreflop.has(c));

  let heroWins = 0, villainWins = 0, ties = 0;
  const histogram = new Array(10).fill(0); // hero win% in 10% buckets
  let done = 0;

  function runChunk() {
    const end = Math.min(done + CHUNK, iterations);
    for (let i = done; i < end; i++) {
      // Pick random hero combo
      const hc = heroCombos[Math.floor(Math.random() * heroCombos.length)];
      // Pick random villain combo — no card overlap
      const hSet = new Set(hc);
      const vcFiltered = villainCombos.filter(vc => !vc.some(c => hSet.has(c)));
      if (!vcFiltered.length) continue;
      const vc = vcFiltered[Math.floor(Math.random() * vcFiltered.length)];

      // Build runout deck (exclude hc + vc + board + dead)
      const usedAll = new Set([...board, ...deadCards, ...hc, ...vc]);
      const runDeck = deckArr.filter(c => !usedAll.has(c));

      // Deal remaining board cards
      const needed = 5 - board.length;
      const runout = [];
      const shuffled = [...runDeck].sort(() => Math.random() - 0.5);
      for (let j = 0; j < needed; j++) runout.push(shuffled[j]);

      const fullBoard = [...board, ...runout];
      const result = compareHands([...hc, ...fullBoard], [...vc, ...fullBoard]);

      if (result === 1) heroWins++;
      else if (result === -1) villainWins++;
      else ties++;
    }
    done = end;

    if (done >= iterations) {
      const total = heroWins + villainWins + ties;
      const heroEq = total ? (heroWins + ties * 0.5) / total : 0;
      const villainEq = total ? (villainWins + ties * 0.5) / total : 0;
      dispatch({ type: "SET_METRICS", payload: {
        equity: { hero: (heroEq * 100).toFixed(2), villain: (villainEq * 100).toFixed(2) }
      }});
      dispatch({ type: "SET_MC_RUNNING", payload: false });
    } else {
      setTimeout(runChunk, 0);
    }
  }

  dispatch({ type: "SET_MC_RUNNING", payload: true });
  setTimeout(runChunk, 0);
}
```

---

## Task 7: Board Texture Metrics

**Files:**
- Modify: `RangeIQ.jsx` — insert after `runMonteCarlo`

**Step 1: Insert `boardTexture`**

```js
function boardTexture(board) {
  if (!board || board.length < 3) return null;

  const ranks = board.map(cardRank);
  const suits = board.map(cardSuit);

  // Flush texture
  const suitCounts = {};
  suits.forEach(s => { suitCounts[s] = (suitCounts[s] || 0) + 1; });
  const maxSuitCount = Math.max(...Object.values(suitCounts));
  const flushTexture = maxSuitCount >= 3 ? "Monotone" : maxSuitCount === 2 ? "Two-Tone" : "Rainbow";

  // Paired board
  const rankCounts = {};
  ranks.forEach(r => { rankCounts[r] = (rankCounts[r] || 0) + 1; });
  const isPaired = Object.values(rankCounts).some(c => c >= 2);

  // Connectivity: count adjacent rank pairs on board
  const sortedRanks = [...new Set(ranks)].sort((a, b) => a - b);
  let connectivity = 0;
  for (let i = 0; i < sortedRanks.length - 1; i++) {
    if (sortedRanks[i + 1] - sortedRanks[i] <= 2) connectivity++;
  }

  // Wetness score (0-10)
  // FD contribution: monotone=4, two-tone=2, rainbow=0
  const fdScore = maxSuitCount >= 3 ? 4 : maxSuitCount === 2 ? 2 : 0;
  // SD contribution: connectivity 0-2
  const sdScore = Math.min(4, connectivity * 2);
  // Paired board reduces wetness
  const pairedScore = isPaired ? -2 : 0;
  const wetness = Math.max(0, Math.min(10, fdScore + sdScore + pairedScore));

  return { flushTexture, isPaired, connectivity, wetness };
}
```

---

## Task 8: Range Breakdown Panel Component

**Files:**
- Modify: `RangeIQ.jsx` — insert as new component before `Module2`

**Step 1: Insert `RangeBreakdown` component**

```jsx
function RangeBreakdown({ range, board, deadCards, label, color }) {
  const breakdown = useMemo(() => {
    if (!board || board.length < 3 || !range || range.size === 0) return null;
    const allDead = [...board, ...deadCards];
    const cats = {};
    for (const hand of range) {
      const combos = expandHand(hand, allDead);
      for (const combo of combos) {
        const { category } = classifyHand(combo, board);
        cats[category] = (cats[category] || 0) + 1;
      }
    }
    const total = Object.values(cats).reduce((a, b) => a + b, 0);
    return Object.entries(cats)
      .map(([cat, count]) => ({ cat, count, pct: total ? (count / total * 100).toFixed(1) : 0 }))
      .sort((a, b) => b.count - a.count);
  }, [range, board, deadCards]);

  if (!breakdown) return null;

  return (
    <div>
      <Label>{label} Range Breakdown</Label>
      <div style={{ marginTop: 6, height: breakdown.length * 22 + 20 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={breakdown}
            layout="vertical"
            margin={{ top: 0, right: 40, left: 120, bottom: 0 }}
          >
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="cat" tick={{ fontSize: 10, fill: T.muted, fontFamily: "monospace" }} width={115} />
            <Tooltip
              contentStyle={{ background: T.bgCard, border: `1px solid ${T.border}`, fontSize: 11, fontFamily: "monospace" }}
              formatter={(v) => [`${v} combos`, "count"]}
            />
            <Bar dataKey="count" fill={color} radius={[0, 3, 3, 0]}>
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
```

---

## Task 9: Wire Module2 — Replace Stub with Full UI

**Files:**
- Modify: `RangeIQ.jsx` — replace the `Module2` function body (lines 483–570)

**Step 1: Replace Module2 with wired version**

Find the existing Module2 function and replace it:

```jsx
function Module2({ state, dispatch }) {
  const { board, heroHand, deadCards, heroRange, villainRange, mcRunning, metrics } = state;
  const allDead = [...(heroHand || []), ...deadCards];
  const texture = useMemo(() => boardTexture(board), [board]);

  const heroHandClassification = useMemo(() => {
    if (heroHand && heroHand.length === 2 && board.length >= 3) {
      return classifyHand(heroHand, board);
    }
    return null;
  }, [heroHand, board]);

  return (
    <div>
      {/* Card Selectors row */}
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap", marginBottom: 16 }}>
        <CardSelector
          label="Board (3-5 cards)"
          selected={board}
          max={5}
          deadCards={allDead}
          onSelect={(c) => dispatch({ type: "SET_BOARD", payload: [...board, c] })}
          onRemove={(i) => dispatch({ type: "SET_BOARD", payload: board.filter((_, j) => j !== i) })}
        />
        <CardSelector
          label="Hero Hand (2 cards)"
          selected={heroHand || []}
          max={2}
          deadCards={[...board, ...deadCards]}
          onSelect={(c) => dispatch({ type: "SET_HERO_HAND", payload: [...(heroHand || []), c] })}
          onRemove={(i) => dispatch({ type: "SET_HERO_HAND", payload: (heroHand || []).filter((_, j) => j !== i) })}
        />
        <CardSelector
          label="Dead Cards"
          selected={deadCards}
          max={10}
          deadCards={[...board, ...(heroHand || [])]}
          onSelect={(c) => dispatch({ type: "SET_DEAD_CARDS", payload: [...deadCards, c] })}
          onRemove={(i) => dispatch({ type: "SET_DEAD_CARDS", payload: deadCards.filter((_, j) => j !== i) })}
        />
      </div>

      {/* Board Texture */}
      {texture && (
        <Card style={{ marginBottom: 12 }}>
          <Label>Board Texture</Label>
          <div style={{ display: "flex", gap: 24, marginTop: 8, flexWrap: "wrap" }}>
            <Stat label="Wetness" value={texture.wetness.toFixed(1)} color={texture.wetness >= 7 ? T.red : texture.wetness >= 4 ? T.yellow : T.green} />
            <Stat label="Connectivity" value={texture.connectivity} />
            <Stat label="Flush" value={texture.flushTexture} color={texture.flushTexture === "Monotone" ? T.red : texture.flushTexture === "Two-Tone" ? T.yellow : T.muted} />
            <Stat label="Paired" value={texture.isPaired ? "Yes" : "No"} color={texture.isPaired ? T.yellow : T.muted} />
          </div>
        </Card>
      )}

      {/* Hero hand classification */}
      {heroHandClassification && (
        <Card style={{ marginBottom: 12 }}>
          <Label>Hero Hand Strength</Label>
          <div style={{ display: "flex", gap: 24, marginTop: 8, flexWrap: "wrap" }}>
            <Stat label="Category" value={heroHandClassification.category} color={T.blue} />
            <Stat label="Strength" value={(heroHandClassification.strength * 100).toFixed(0) + "%"} color={T.blue} />
            {heroHandClassification.draws.length > 0 && (
              <div style={{ textAlign: "center" }}>
                <Label>Draws</Label>
                <div style={{ fontSize: 11, color: T.yellow, fontFamily: "monospace", marginTop: 2 }}>
                  {heroHandClassification.draws.join(", ")}
                </div>
              </div>
            )}
          </div>
        </Card>
      )}

      {/* Equity + MC button */}
      {board.length >= 3 && (
        <Card style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <Label>Monte Carlo Equity ({totalCombos(heroRange)}h × {totalCombos(villainRange)}v combos)</Label>
            <Btn
              small
              color={T.green}
              disabled={mcRunning || !heroRange.size || !villainRange.size}
              onClick={() => runMonteCarlo(heroRange, villainRange, board, [...(heroHand || []), ...deadCards], dispatch)}
            >
              {mcRunning ? "Running…" : "Run MC (R)"}
            </Btn>
          </div>
          {metrics.equity && (
            <div style={{ display: "flex", gap: 24 }}>
              <Stat label="Hero Equity" value={`${metrics.equity.hero}%`} color={T.blue} />
              <Stat label="Villain Equity" value={`${metrics.equity.villain}%`} color={T.red} />
            </div>
          )}
          {!metrics.equity && !mcRunning && (
            <div style={{ fontSize: 11, color: T.muted }}>Set hero + villain ranges, then run.</div>
          )}
        </Card>
      )}

      {/* Range Breakdowns */}
      {board.length >= 3 && (heroRange.size > 0 || villainRange.size > 0) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Card>
            <RangeBreakdown range={heroRange} board={board} deadCards={[...(heroHand || []), ...deadCards]} label="Hero" color={T.blue} />
          </Card>
          <Card>
            <RangeBreakdown range={villainRange} board={board} deadCards={[...(heroHand || []), ...deadCards]} label="Villain" color={T.red} />
          </Card>
        </div>
      )}
    </div>
  );
}
```

---

## Task 10: Keyboard Shortcut — R for Run Monte Carlo

**Files:**
- Modify: `RangeIQ.jsx` — find the keyboard handler `useEffect` in `RangeIQ` component (around line 851)

**Step 1: Add `R` shortcut**

Find:
```js
if (e.key === "c" || e.key === "C") dispatch({ type: "CLEAR_RANGE" });
```

Replace with:
```js
if (e.key === "c" || e.key === "C") dispatch({ type: "CLEAR_RANGE" });
if ((e.key === "r" || e.key === "R") && state.activeModule === 2 && !state.mcRunning) {
  if (state.board.length >= 3 && state.heroRange.size && state.villainRange.size) {
    runMonteCarlo(state.heroRange, state.villainRange, state.board,
      [...(state.heroHand || []), ...state.deadCards], dispatch);
  }
}
```

Note: The `handler` closure doesn't have `state` in scope in the current implementation. Fix by moving the `dispatch` calls for the `r` key into a `useCallback` or by accessing state via a ref. Simplest fix: use a `stateRef`:

Find the `useEffect` keyboard handler and add before it:
```js
const stateRef = useRef(state);
useEffect(() => { stateRef.current = state; }, [state]);
```

Then in the handler, use `stateRef.current` instead of `state`.

---

## Verification Checklist

After all tasks are inserted and saved:

1. Paste `RangeIQ.jsx` into a Claude.ai artifact (React renderer)
2. Load `BTN RFI` preset for Hero, `BB def vs BTN` for Villain
3. Set board: `Ah 7s 2c`
4. Click "Run MC" → should see ~60% hero equity within 10 seconds
5. Hero hand `As Kh` → should show "Top Pair (Good Kicker)"
6. Board texture: Rainbow, Wetness ≈ 0, Connectivity 0
7. Range breakdown bars should appear for both hero and villain

---

## Execution Options

Plan complete and saved to `docs/plans/2026-03-13-module2-hand-engine.md`.

**1. Subagent-Driven (this session)** — Dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** — Open new session with executing-plans, batch execution with checkpoints

Which approach?
