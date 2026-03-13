import { useReducer, useCallback, useMemo, useState, useEffect, useRef } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  RadialBarChart, RadialBar, PieChart, Pie, Cell
} from "recharts";

// ============================================================
// CONSTANTS
// ============================================================
const RANKS = ["A","K","Q","J","T","9","8","7","6","5","4","3","2"];
const SUITS = ["s","h","d","c"];
const SUIT_SYM = { s:"♠", h:"♥", d:"♦", c:"♣" };
const DECK = RANKS.flatMap(r => SUITS.map(s => r + s));

function matrixLabel(row, col) {
  if (row === col) return RANKS[row] + RANKS[col];
  if (row < col) return RANKS[row] + RANKS[col] + "s";
  return RANKS[col] + RANKS[row] + "o";
}

function combosFor(hand) {
  if (hand.length === 2) return 6;
  return hand.endsWith("s") ? 4 : 12;
}

// Expand hand category -> specific card combos
function expandHand(hand, deadCards = []) {
  const dead = new Set(deadCards);
  const combos = [];
  if (hand.length === 2) {
    const r = hand[0];
    for (let i = 0; i < 4; i++)
      for (let j = i + 1; j < 4; j++) {
        const a = r + SUITS[i], b = r + SUITS[j];
        if (!dead.has(a) && !dead.has(b)) combos.push([a, b]);
      }
  } else {
    const r1 = hand[0], r2 = hand[1], suited = hand.endsWith("s");
    for (let i = 0; i < 4; i++)
      for (let j = 0; j < 4; j++) {
        if (suited && i !== j) continue;
        if (!suited && i === j) continue;
        const a = r1 + SUITS[i], b = r2 + SUITS[j];
        if (!dead.has(a) && !dead.has(b)) combos.push([a, b]);
      }
  }
  return combos;
}

const TOTAL_COMBOS = 1326;

// ============================================================
// PRESET RANGES
// ============================================================
const PRESETS = {
  "UTG RFI": "AA,KK,QQ,JJ,TT,99,88,77,AKs,AQs,AJs,ATs,A5s,A4s,KQs,KJs,KTs,QJs,QTs,JTs,T9s,98s,87s,76s,AKo,AQo,AJo,KQo",
  "HJ RFI": "AA,KK,QQ,JJ,TT,99,88,77,66,AKs,AQs,AJs,ATs,A9s,A5s,A4s,A3s,KQs,KJs,KTs,K9s,QJs,QTs,Q9s,JTs,J9s,T9s,98s,87s,76s,65s,AKo,AQo,AJo,ATo,KQo,KJo",
  "CO RFI": "AA,KK,QQ,JJ,TT,99,88,77,66,55,AKs,AQs,AJs,ATs,A9s,A8s,A7s,A6s,A5s,A4s,A3s,A2s,KQs,KJs,KTs,K9s,K8s,QJs,QTs,Q9s,JTs,J9s,J8s,T9s,T8s,98s,97s,87s,86s,76s,75s,65s,54s,AKo,AQo,AJo,ATo,A9o,KQo,KJo,KTo,QJo,QTo,JTo",
  "BTN RFI": "AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AKs,AQs,AJs,ATs,A9s,A8s,A7s,A6s,A5s,A4s,A3s,A2s,KQs,KJs,KTs,K9s,K8s,K7s,K6s,K5s,QJs,QTs,Q9s,Q8s,Q7s,JTs,J9s,J8s,J7s,T9s,T8s,T7s,98s,97s,96s,87s,86s,76s,75s,65s,64s,54s,53s,43s,AKo,AQo,AJo,ATo,A9o,A8o,A7o,A6o,A5o,KQo,KJo,KTo,K9o,QJo,QTo,Q9o,JTo,J9o,T9o,98o,87o",
  "SB RFI": "AA,KK,QQ,JJ,TT,99,88,77,66,55,44,AKs,AQs,AJs,ATs,A9s,A8s,A7s,A6s,A5s,A4s,A3s,A2s,KQs,KJs,KTs,K9s,K8s,QJs,QTs,Q9s,JTs,J9s,T9s,98s,87s,76s,65s,54s,AKo,AQo,AJo,ATo,A9o,KQo,KJo,KTo,QJo",
  "BB def vs BTN": "AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AKs,AQs,AJs,ATs,A9s,A8s,A7s,A6s,A5s,A4s,A3s,A2s,KQs,KJs,KTs,K9s,K8s,K7s,K6s,K5s,K4s,K3s,K2s,QJs,QTs,Q9s,Q8s,Q7s,Q6s,Q5s,Q4s,Q3s,JTs,J9s,J8s,J7s,J6s,J5s,T9s,T8s,T7s,T6s,98s,97s,96s,87s,86s,85s,76s,75s,65s,64s,54s,53s,43s,AKo,AQo,AJo,ATo,A9o,A8o,A7o,A6o,A5o,A4o,A3o,KQo,KJo,KTo,K9o,K8o,QJo,QTo,Q9o,JTo,J9o,T9o,98o,87o,76o",
  "BB def vs CO": "AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,AKs,AQs,AJs,ATs,A9s,A8s,A7s,A6s,A5s,A4s,A3s,A2s,KQs,KJs,KTs,K9s,K8s,K7s,K6s,QJs,QTs,Q9s,Q8s,Q7s,JTs,J9s,J8s,J7s,T9s,T8s,T7s,98s,97s,87s,86s,76s,75s,65s,54s,43s,AKo,AQo,AJo,ATo,A9o,A8o,KQo,KJo,KTo,K9o,QJo,QTo,JTo,T9o,98o",
  "3Bet value": "AA,KK,QQ,JJ,AKs,AKo",
  "3Bet bluff": "A5s,A4s,A3s,A2s,76s,65s,54s,K9s,Q9s,J9s",
  "3Bet merged": "AA,KK,QQ,JJ,TT,AKs,AQs,AJs,AKo,AQo",
  "Call 3Bet IP": "TT,99,88,77,66,AQs,AJs,ATs,A9s,KQs,KJs,KTs,QJs,QTs,JTs,T9s,98s,87s,76s,AQo,AJo,KQo",
  "Call 3Bet OOP": "TT,99,88,77,AQs,AJs,ATs,KQs,KJs,QJs,JTs,AQo",
  "4Bet value": "AA,KK,QQ,AKs,AKo",
  "4Bet bluff": "A5s,A4s,A3s,A2s",
};

function parsePreset(str) {
  return new Set(str.split(",").map(s => s.trim()).filter(Boolean));
}

// ============================================================
// PREMIUM / NUT COMBOS (preflop proxy)
// ============================================================
const PREMIUM_HANDS = new Set(["AA","KK","QQ","AKs","AKo"]);

function countPremiums(range) {
  let n = 0;
  for (const h of range) if (PREMIUM_HANDS.has(h)) n += combosFor(h);
  return n;
}

function totalCombos(range) {
  let n = 0;
  for (const h of range) n += combosFor(h);
  return n;
}

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

// Straight check (including A-low wheel: A=1) — module scope so evalHand5 and evalHand7 can share it
function hasStraight(rs) {
  const unique = [...new Set(rs)].sort((a, b) => b - a);
  const withAceLow = unique.includes(14) ? [...unique, 1] : unique;
  const dedup = [...new Set(withAceLow)].sort((a, b) => b - a);
  for (let i = 0; i <= dedup.length - 5; i++) {
    if (dedup[i] - dedup[i + 4] === 4 &&
        new Set(dedup.slice(i, i + 5)).size === 5) {
      return dedup[i];
    }
  }
  return null;
}

// evalHand5: returns [handRank, ...tiebreakers] comparable array
// handRank: 8=SF, 7=quads, 6=FH, 5=flush, 4=straight, 3=trips, 2=two-pair, 1=pair, 0=high-card
function evalHand5(cards) {
  const ranks = cards.map(cardRank).sort((a, b) => b - a);
  const suits = cards.map(cardSuit);

  // Flush check
  const flushSuit = suits.find(s => suits.filter(x => x === s).length >= 5) || null;
  const isFlush = flushSuit !== null;

  const straightHigh = hasStraight(ranks);

  // Group by rank
  const groups = {};
  ranks.forEach(r => { groups[r] = (groups[r] || 0) + 1; });
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

// Best 5-card hand from 7 cards (21 combinations)
function evalHand7(cards7) {
  const combos = combinations(cards7, 5);
  if (!combos.length) return [0];
  return combos
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

function detectDraws(holeCards, board) {
  const draws = [];
  const allCards = [...holeCards, ...board];
  const hasMadeFlush = evalHand7(allCards)[0] >= 5;

  // Flush draws
  const suitCounts = {};
  allCards.forEach(c => { const s = cardSuit(c); suitCounts[s] = (suitCounts[s] || 0) + 1; });
  for (const [suit, count] of Object.entries(suitCounts)) {
    if (count >= 5 || hasMadeFlush) continue;
    if (count === 4) {
      const heroContrib = holeCards.filter(c => cardSuit(c) === suit).length;
      if (heroContrib > 0) {
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

  // Straight draws
  const allRanks = allCards.map(cardRank);
  const uniqueRanks = [...new Set(allRanks)].sort((a, b) => a - b);
  const withAceLow = uniqueRanks.includes(14) ? [1, ...uniqueRanks] : uniqueRanks;
  const dedupRanks = [...new Set(withAceLow)].sort((a, b) => a - b);

  const gutWindows = [];
  for (let lo = 1; lo <= 10; lo++) {
    const window = [lo, lo+1, lo+2, lo+3, lo+4];
    const hits = window.filter(r => dedupRanks.includes(r)).length;
    if (hits === 4) {
      const missing = window.find(r => !dedupRanks.includes(r));
      if (missing === lo || missing === lo + 4) {
        draws.push("OESD");
      } else {
        gutWindows.push(lo);
      }
    }
    if (hits === 3 && board.length <= 4) {
      if (!draws.includes("Backdoor SD")) draws.push("Backdoor SD");
    }
  }

  if (gutWindows.length >= 2) {
    draws.push("Double Gutshot");
  } else if (gutWindows.length === 1) {
    draws.push("Gutshot");
  }

  // Overcard draws
  const boardTop = Math.max(...board.map(cardRank));
  const overcards = holeCards.filter(c => cardRank(c) > boardTop);
  if (overcards.length > 0 && evalHand7([...holeCards, ...board])[0] === 0) {
    draws.push("Overcard Draw");
  }

  return [...new Set(draws)];
}

function classifyHand(holeCards, board) {
  if (!board || board.length < 3) return { category: "Preflop", strength: 0, draws: [] };

  const allCards = [...holeCards, ...board];
  const handVal = evalHand7(allCards);
  const handRank = handVal[0];

  const boardRanks = board.map(cardRank).sort((a, b) => b - a);
  const hRanks = holeCards.map(cardRank).sort((a, b) => b - a);

  let category = "";
  if (handRank === 8) category = "Straight Flush";
  else if (handRank === 7) category = "Quads";
  else if (handRank === 6) category = "Full House";
  else if (handRank === 5) category = "Flush";
  else if (handRank === 4) category = "Straight";
  else if (handRank === 3) category = "Three of a Kind";
  else if (handRank === 2) category = "Two Pair";
  else if (handRank === 1) {
    const pairRank = handVal[1];
    const topBoard = boardRanks[0];
    const isHolePair = hRanks[0] === hRanks[1];
    if (isHolePair) {
      if (pairRank > topBoard) category = "Overpair";
      else if (pairRank < boardRanks[boardRanks.length - 1]) category = "Underpair";
      else category = "Middle Pair";
    } else {
      if (pairRank === topBoard) {
        const kicker = hRanks.find(r => r !== pairRank) || 0;
        category = kicker >= 10 ? "Top Pair (Good Kicker)" : "Top Pair (Weak Kicker)";
      } else if (pairRank === boardRanks[1]) category = "Middle Pair";
      else if (pairRank === boardRanks[boardRanks.length - 1]) category = "Bottom Pair";
      else category = "Pair";
    }
  } else {
    const maxHole = Math.max(...hRanks);
    category = maxHole === 14 ? "Ace High" : "No Made Hand";
  }

  const strength = Math.min(1, (handRank / 8) * 0.85 + ((handVal[1] || 0) / 14) * 0.15);
  const draws = detectDraws(holeCards, board);

  return { category, strength, draws };
}

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
      const shuffled = [...runDeck].sort(() => Math.random() - 0.5);
      const runout = shuffled.slice(0, needed);

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
        equity: {
          hero: (heroEq * 100).toFixed(2),
          villain: (villainEq * 100).toFixed(2),
        }
      }});
      dispatch({ type: "SET_MC_RUNNING", payload: false });
    } else {
      setTimeout(runChunk, 0);
    }
  }

  dispatch({ type: "SET_MC_RUNNING", payload: true });
  setTimeout(runChunk, 0);
}

// ============================================================
// STATE MANAGEMENT
// ============================================================
const initialState = {
  heroRange: new Set(),
  villainRange: new Set(),
  activeRange: "hero", // "hero" | "villain"
  heroHand: null,       // [card, card] | null
  board: [],            // up to 5 cards
  deadCards: [],
  metrics: { equity: null, ra: null, na: null, pi: null, wetness: null },
  evTree: null,
  traceQueue: [],
  scenarios: [],
  activeModule: 1,
  mcRunning: false,
  // Module 3 state
  evTreeConfig: {
    potSize: 6, effStack: 100,
    nodes: [] // will be built in Module 3
  },
  // Module 4 state
  lastTrace: null,
  traceError: null,
  batchProgress: null,
};

function reducer(state, action) {
  switch (action.type) {
    case "SET_MODULE":
      return { ...state, activeModule: action.payload };
    case "SET_ACTIVE_RANGE":
      return { ...state, activeRange: action.payload };
    case "TOGGLE_HAND": {
      const key = action.payload;
      const rangeKey = state.activeRange === "hero" ? "heroRange" : "villainRange";
      const next = new Set(state[rangeKey]);
      next.has(key) ? next.delete(key) : next.add(key);
      return { ...state, [rangeKey]: next };
    }
    case "SET_RANGE": {
      const rangeKey = state.activeRange === "hero" ? "heroRange" : "villainRange";
      return { ...state, [rangeKey]: new Set(action.payload) };
    }
    case "CLEAR_RANGE": {
      const rangeKey = state.activeRange === "hero" ? "heroRange" : "villainRange";
      return { ...state, [rangeKey]: new Set() };
    }
    case "LOAD_PRESET": {
      const rangeKey = state.activeRange === "hero" ? "heroRange" : "villainRange";
      return { ...state, [rangeKey]: parsePreset(PRESETS[action.payload]) };
    }
    case "SET_BOARD":
      return { ...state, board: action.payload };
    case "SET_HERO_HAND":
      return { ...state, heroHand: action.payload };
    case "SET_DEAD_CARDS":
      return { ...state, deadCards: action.payload };
    case "SET_METRICS":
      return { ...state, metrics: { ...state.metrics, ...action.payload } };
    case "SET_MC_RUNNING":
      return { ...state, mcRunning: action.payload };
    case "ADD_TRACE":
      return { ...state, traceQueue: [...state.traceQueue, action.payload], lastTrace: action.payload };
    case "SET_LAST_TRACE":
      return { ...state, lastTrace: action.payload };
    case "SET_TRACE_ERROR":
      return { ...state, traceError: action.payload };
    case "CLEAR_TRACES":
      return { ...state, traceQueue: [] };
    case "SAVE_SCENARIO":
      return { ...state, scenarios: [...state.scenarios, action.payload] };
    case "LOAD_SCENARIO": {
      const s = action.payload;
      return { ...state, heroRange: new Set(s.heroRange), villainRange: new Set(s.villainRange), board: s.board || [], heroHand: s.heroHand || null };
    }
    case "SET_EV_TREE_CONFIG":
      return { ...state, evTreeConfig: { ...state.evTreeConfig, ...action.payload } };
    case "SET_BATCH_PROGRESS":
      return { ...state, batchProgress: action.payload };
    default:
      return state;
  }
}

// ============================================================
// THEME (CSS-in-JS via inline styles, uses Tailwind where possible)
// ============================================================
const T = {
  bgPrimary: "#0d1117",
  bgCard: "#161b22",
  bgElevated: "#21262d",
  border: "#30363d",
  blue: "#58a6ff",
  green: "#3fb950",
  red: "#f85149",
  yellow: "#d29922",
  purple: "#bc8cff",
  text: "#e6edf3",
  muted: "#8b949e",
};

// ============================================================
// SMALL UI COMPONENTS
// ============================================================
function Btn({ children, onClick, active, small, disabled, color }) {
  const bg = active ? (color || T.blue) : T.bgElevated;
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: bg,
        color: active ? "#fff" : T.text,
        border: `1px solid ${active ? bg : T.border}`,
        borderRadius: 4,
        padding: small ? "2px 8px" : "6px 14px",
        fontSize: small ? 11 : 13,
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.5 : 1,
        fontFamily: "monospace",
        transition: "all 0.15s",
      }}
    >
      {children}
    </button>
  );
}

function Card({ children, style }) {
  return (
    <div style={{
      background: T.bgCard, border: `1px solid ${T.border}`,
      borderRadius: 6, padding: 12, ...style
    }}>
      {children}
    </div>
  );
}

function Label({ children }) {
  return <span style={{ color: T.muted, fontSize: 11, fontFamily: "monospace", textTransform: "uppercase", letterSpacing: 1 }}>{children}</span>;
}

function Stat({ label, value, color }) {
  return (
    <div style={{ textAlign: "center" }}>
      <Label>{label}</Label>
      <div style={{ fontSize: 20, fontFamily: "monospace", fontWeight: 700, color: color || T.text, marginTop: 2 }}>{value}</div>
    </div>
  );
}

// ============================================================
// MODULE 1 — PREFLOP RANGE BUILDER
// ============================================================
function RangeMatrix({ range, onToggle, otherRange }) {
  const [dragging, setDragging] = useState(false);
  const [dragMode, setDragMode] = useState(null); // "add" | "remove"

  const handleMouseDown = (hand) => {
    const mode = range.has(hand) ? "remove" : "add";
    setDragging(true);
    setDragMode(mode);
    onToggle(hand);
  };

  const handleMouseEnter = (hand) => {
    if (!dragging) return;
    const inRange = range.has(hand);
    if (dragMode === "add" && !inRange) onToggle(hand);
    if (dragMode === "remove" && inRange) onToggle(hand);
  };

  const handleMouseUp = () => {
    setDragging(false);
    setDragMode(null);
  };

  useEffect(() => {
    window.addEventListener("mouseup", handleMouseUp);
    return () => window.removeEventListener("mouseup", handleMouseUp);
  }, []);

  return (
    <div
      style={{ display: "grid", gridTemplateColumns: "repeat(13, 1fr)", gap: 1, userSelect: "none" }}
      onMouseLeave={() => setDragging(false)}
    >
      {Array.from({ length: 13 }, (_, r) =>
        Array.from({ length: 13 }, (_, c) => {
          const hand = matrixLabel(r, c);
          const inHero = range.has(hand);
          const inOther = otherRange.has(hand);
          const isPair = r === c;
          const isSuited = r < c;

          let bg = T.bgElevated;
          if (inHero && inOther) bg = T.purple;
          else if (inHero) bg = T.blue;
          else if (inOther) bg = "rgba(248,81,73,0.25)";

          return (
            <div
              key={hand}
              onMouseDown={() => handleMouseDown(hand)}
              onMouseEnter={() => handleMouseEnter(hand)}
              style={{
                background: bg,
                border: `1px solid ${inHero ? (inOther ? T.purple : T.blue) : T.border}`,
                borderRadius: 2,
                padding: "3px 0",
                textAlign: "center",
                fontSize: 10,
                fontFamily: "monospace",
                color: inHero ? "#fff" : (isPair ? T.text : isSuited ? T.green : T.muted),
                cursor: "pointer",
                fontWeight: inHero ? 700 : 400,
                lineHeight: "16px",
                transition: "background 0.1s",
              }}
            >
              {hand}
            </div>
          );
        })
      )}
    </div>
  );
}

function RangeStats({ range, label }) {
  const combos = totalCombos(range);
  const pct = ((combos / TOTAL_COMBOS) * 100).toFixed(1);
  const premiums = countPremiums(range);
  return (
    <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
      <Stat label={`${label} Combos`} value={combos} />
      <Stat label="% of Hands" value={`${pct}%`} />
      <Stat label="VPIP ≈" value={`${pct}%`} />
      <Stat label="Premiums" value={premiums} color={T.yellow} />
    </div>
  );
}

function NutAdvantageGauge({ heroRange, villainRange }) {
  const hp = countPremiums(heroRange);
  const vp = countPremiums(villainRange);
  const total = hp + vp;
  const score = total > 0 ? ((hp / total) * 100).toFixed(1) : "—";
  const data = [{ name: "Hero", value: total > 0 ? hp / total * 100 : 0, fill: T.blue }];

  return (
    <Card style={{ marginTop: 8 }}>
      <Label>Preflop Nut Advantage (AA/KK/QQ/AKs/AKo)</Label>
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 6 }}>
        <div style={{ width: 80, height: 80 }}>
          <ResponsiveContainer>
            <RadialBarChart innerRadius="60%" outerRadius="100%" data={data} startAngle={180} endAngle={0}>
              <RadialBar dataKey="value" cornerRadius={4} fill={T.blue} background={{ fill: T.bgElevated }} />
            </RadialBarChart>
          </ResponsiveContainer>
        </div>
        <div>
          <div style={{ fontSize: 22, fontFamily: "monospace", fontWeight: 700, color: T.blue }}>{score}%</div>
          <div style={{ fontSize: 11, color: T.muted }}>Hero nut advantage</div>
          <div style={{ fontSize: 11, color: T.muted, marginTop: 2 }}>Hero: {hp} | Villain: {vp}</div>
        </div>
      </div>
    </Card>
  );
}

function Module1({ state, dispatch }) {
  const { heroRange, villainRange, activeRange } = state;
  const currentRange = activeRange === "hero" ? heroRange : villainRange;
  const otherRange = activeRange === "hero" ? villainRange : heroRange;

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 280px", gap: 16 }}>
      {/* Left: Matrix */}
      <div>
        {/* Range toggle & presets */}
        <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
          <Btn active={activeRange === "hero"} onClick={() => dispatch({ type: "SET_ACTIVE_RANGE", payload: "hero" })} color={T.blue}>Hero</Btn>
          <Btn active={activeRange === "villain"} onClick={() => dispatch({ type: "SET_ACTIVE_RANGE", payload: "villain" })} color={T.red}>Villain</Btn>
          <span style={{ color: T.border }}>|</span>
          <Btn small onClick={() => dispatch({ type: "CLEAR_RANGE" })}>Clear</Btn>
          <select
            style={{
              background: T.bgElevated, color: T.text, border: `1px solid ${T.border}`,
              borderRadius: 4, padding: "4px 8px", fontSize: 12, fontFamily: "monospace"
            }}
            value=""
            onChange={(e) => {
              if (e.target.value) dispatch({ type: "LOAD_PRESET", payload: e.target.value });
            }}
          >
            <option value="">Load Preset…</option>
            {Object.keys(PRESETS).map(k => <option key={k} value={k}>{k}</option>)}
          </select>
        </div>
        <RangeMatrix range={currentRange} onToggle={(h) => dispatch({ type: "TOGGLE_HAND", payload: h })} otherRange={otherRange} />
      </div>

      {/* Right: Stats */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <Card>
          <Label>Hero Range</Label>
          <div style={{ marginTop: 6 }}><RangeStats range={heroRange} label="Hero" /></div>
        </Card>
        <Card>
          <Label>Villain Range</Label>
          <div style={{ marginTop: 6 }}><RangeStats range={villainRange} label="Villain" /></div>
        </Card>
        <Card>
          <Label>Equity Advantage (preflop all-in)</Label>
          <div style={{ marginTop: 6, display: "flex", gap: 16 }}>
            <Stat label="Hero Combos" value={totalCombos(heroRange)} color={T.blue} />
            <Stat label="Villain Combos" value={totalCombos(villainRange)} color={T.red} />
          </div>
          <div style={{ fontSize: 11, color: T.muted, marginTop: 6 }}>
            Delta: {totalCombos(heroRange) - totalCombos(villainRange)} combos
          </div>
        </Card>
        <NutAdvantageGauge heroRange={heroRange} villainRange={villainRange} />
      </div>
    </div>
  );
}

// ============================================================
// MODULE 2 — BOARD & EQUITY (STUB WITH CARD SELECTOR)
// ============================================================
function CardSelector({ selected, onSelect, onRemove, max, deadCards = [], label }) {
  const [open, setOpen] = useState(false);
  const used = new Set([...selected, ...deadCards]);
  return (
    <div>
      <Label>{label}</Label>
      <div style={{ display: "flex", gap: 4, marginTop: 4, flexWrap: "wrap" }}>
        {selected.map((c, i) => (
          <span
            key={i}
            onClick={() => onRemove(i)}
            style={{
              background: T.bgElevated, border: `1px solid ${T.border}`, borderRadius: 3,
              padding: "2px 6px", fontFamily: "monospace", fontSize: 13, cursor: "pointer",
              color: RED_SUITS.has(c[1]) ? T.red : T.text
            }}
          >
            {c[0]}{SUIT_SYM[c[1]]}
          </span>
        ))}
        {selected.length < max && (
          <Btn small onClick={() => setOpen(!open)}>+ Add</Btn>
        )}
      </div>
      {open && selected.length < max && (
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(13, 1fr)", gap: 2,
          marginTop: 6, background: T.bgCard, border: `1px solid ${T.border}`,
          borderRadius: 4, padding: 6, maxWidth: 400
        }}>
          {DECK.map(card => {
            const disabled = used.has(card);
            return (
              <div
                key={card}
                onClick={() => { if (!disabled) { onSelect(card); setOpen(false); } }}
                style={{
                  fontSize: 10, fontFamily: "monospace", textAlign: "center",
                  padding: "2px 0", borderRadius: 2, cursor: disabled ? "default" : "pointer",
                  opacity: disabled ? 0.2 : 1,
                  color: RED_SUITS.has(card[1]) ? T.red : T.text,
                  background: T.bgElevated,
                }}
              >
                {card[0]}{SUIT_SYM[card[1]]}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

const RED_SUITS = new Set(["h", "d"]);

function Module2({ state, dispatch }) {
  const { board, heroHand, deadCards, heroRange, villainRange, mcRunning, metrics } = state;

  // TODO: Monte Carlo equity engine (50k iterations, chunked)
  // TODO: Hand category breakdown for villain range vs board
  // TODO: Range/nut advantage post-board
  // TODO: Board texture metrics (wetness, connectivity, static/dynamic)
  // TODO: Combo & blocker engine
  // TODO: Equity distribution histogram (recharts BarChart)

  return (
    <div>
      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        <CardSelector
          label="Board (3-5 cards)"
          selected={board}
          max={5}
          deadCards={[...(heroHand || []), ...deadCards]}
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

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
        <Card>
          <Label>Statistical Breakdown</Label>
          <div style={{ color: T.muted, fontSize: 12, marginTop: 8, lineHeight: 1.6 }}>
            <p>→ Monte Carlo engine (50k iterations, chunked setTimeout)</p>
            <p>→ Made hand category breakdown (quads → no made hand)</p>
            <p>→ Draw detection (NFD, FD, OESD, gutshot, backdoors)</p>
            <p>→ Combo count + % of range + EV weight per category</p>
            <p style={{ marginTop: 8 }}>
              <strong style={{ color: T.yellow }}>Entry point:</strong> Implement <code>runMonteCarlo(heroRange, villainRange, board, deadCards)</code>
              → returns {{ heroEq, villainEq, tieEq, histogram[] }}
            </p>
            <p>
              <strong style={{ color: T.yellow }}>Key fn:</strong> <code>classifyHand(holeCards, board)</code>
              → returns hand category + strength score 0-1
            </p>
          </div>
        </Card>

        <Card>
          <Label>Board Texture & Metrics</Label>
          <div style={{ color: T.muted, fontSize: 12, marginTop: 8, lineHeight: 1.6 }}>
            <p>→ Wetness Score (0-10): FD/SD density + paired board</p>
            <p>→ Connectivity Score: rank-adjacent card count</p>
            <p>→ Monotone / Two-tone / Rainbow</p>
            <p>→ Static vs. Dynamic classification</p>
            <p>→ Post-board Range Advantage & Nut Advantage</p>
            <p>→ Polarity Index (stddev of hand strength distribution)</p>
            <p>→ Blocker impact table per board card</p>
          </div>
        </Card>
      </div>

      {board.length >= 3 && (
        <Card style={{ marginTop: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <Label>Equity Computation</Label>
            <Btn small onClick={() => {/* TODO: trigger MC */}} disabled={mcRunning}>
              {mcRunning ? "Running…" : "Run Monte Carlo (R)"}
            </Btn>
          </div>
          <div style={{ color: T.muted, fontSize: 12, marginTop: 6 }}>
            Board set. Wire up <code>runMonteCarlo()</code> to compute equity across {totalCombos(heroRange)} hero × {totalCombos(villainRange)} villain combos.
          </div>
        </Card>
      )}
    </div>
  );
}

// ============================================================
// MODULE 3 — MULTI-STREET EV TREE (STUB)
// ============================================================
function Module3({ state, dispatch }) {
  const { evTreeConfig } = state;

  // TODO: Recursive EV tree builder UI
  // TODO: computeNodeEV(node, pot, heroInvestment) recursive function
  // TODO: Expandable/collapsible tree visualization
  // TODO: Breakeven analysis panel per betting node
  // TODO: Frequency exploitability score
  // TODO: EV breakdown pie chart (fold eq / showdown eq / implied eq)

  return (
    <div>
      <div style={{ display: "flex", gap: 16, marginBottom: 12 }}>
        <Card style={{ flex: 1 }}>
          <Label>Pot Size (bb)</Label>
          <input
            type="number" value={evTreeConfig.potSize}
            onChange={(e) => dispatch({ type: "SET_EV_TREE_CONFIG", payload: { potSize: +e.target.value } })}
            style={{ background: T.bgElevated, color: T.text, border: `1px solid ${T.border}`, borderRadius: 4, padding: "4px 8px", width: 80, fontFamily: "monospace" }}
          />
        </Card>
        <Card style={{ flex: 1 }}>
          <Label>Effective Stack (bb)</Label>
          <input
            type="number" value={evTreeConfig.effStack}
            onChange={(e) => dispatch({ type: "SET_EV_TREE_CONFIG", payload: { effStack: +e.target.value } })}
            style={{ background: T.bgElevated, color: T.text, border: `1px solid ${T.border}`, borderRadius: 4, padding: "4px 8px", width: 80, fontFamily: "monospace" }}
          />
        </Card>
      </div>

      <Card>
        <Label>EV Tree Architecture</Label>
        <div style={{ color: T.muted, fontSize: 12, marginTop: 8, lineHeight: 1.8 }}>
          <p><strong style={{ color: T.green }}>Tree Structure:</strong> Flop → Turn → River, recursive</p>
          <p>Each node: Action (Check/Bet/Raise/Fold) + Villain frequency %</p>
          <p><strong style={{ color: T.yellow }}>EV Formula:</strong></p>
          <pre style={{ background: T.bgPrimary, padding: 8, borderRadius: 4, fontSize: 11, marginTop: 4 }}>
{`EV(node) = Σ[ P(action_i) × EV(outcome_i) ]
EV(fold)     = pot  (Hero wins)
EV(call)     = recurse to next street
EV(showdown) = Hero_eq × final_pot - (1 - Hero_eq) × hero_investment
EV(raise)    = fold_to_raise% × pot + (1 - fold%) × EV(call)`}
          </pre>
          <p style={{ marginTop: 8 }}><strong style={{ color: T.yellow }}>Breakeven:</strong> BE% = Bet / (Bet + Pot)</p>
          <p><strong style={{ color: T.yellow }}>Bluff:Value Ratio:</strong> S / (S + P) = optimal bluff frequency</p>
          <p style={{ marginTop: 8 }}>Build interactive tree with add-node buttons at each leaf.</p>
          <p>Color-code: <span style={{ color: T.green }}>+EV green</span> / <span style={{ color: T.yellow }}>≈0 yellow</span> / <span style={{ color: T.red }}>-EV red</span></p>
        </div>
      </Card>
    </div>
  );
}

// ============================================================
// MODULE 4 — TRACE GENERATOR (STUB WITH API WIRING)
// ============================================================
function Module4({ state, dispatch }) {
  const { traceQueue, lastTrace, traceError, heroRange, villainRange, board, heroHand, metrics } = state;

  // Serialize current state for API call
  const buildContext = () => ({
    scenario_id: crypto.randomUUID(),
    game_state: {
      hero_range: [...heroRange].join(","),
      villain_range: [...villainRange].join(","),
      hero_hand: heroHand,
      board,
      pot_size_bb: state.evTreeConfig.potSize,
      effective_stack_bb: state.evTreeConfig.effStack,
      street: board.length === 0 ? "preflop" : board.length === 3 ? "flop" : board.length === 4 ? "turn" : "river",
    },
    computed_metrics: {
      hero_equity_pct: metrics.equity?.hero ?? null,
      range_advantage_score: metrics.ra ?? null,
      nut_advantage_score: metrics.na ?? null,
      polarity_index_hero: metrics.pi?.hero ?? null,
      wetness_score: metrics.wetness ?? null,
    },
    decision_context: {
      action_facing: null,
      available_actions: ["fold","check","call","bet_half","bet_pot","raise"],
    }
  });

  const SYSTEM_PROMPT = `You are a GTO-trained poker expert with deep knowledge of solver outputs, range construction, and multi-street planning. You are generating a reasoning trace that will be used to fine-tune an LLM on expert poker decision-making.

Given the game state and computed metrics below, produce a structured reasoning trace. The trace must:
1. Diagnose the board texture and its impact on both ranges
2. Quantify range advantage and nut advantage and explain strategic implications
3. Identify the key combos driving each metric
4. Evaluate the EV of each available action
5. Select the optimal action with explicit frequency recommendations
6. Identify 3 exploitable tendencies in the villain's range
7. State one counter-adjustment

Output ONLY valid JSON matching this schema - no preamble, no markdown:
{"reasoning_trace":{"board_diagnosis":"","range_dynamics":{"hero_assessment":"","villain_assessment":"","key_metric_drivers":[]},"action_evaluation":[{"action":"","ev_estimate_bb":0,"rationale":"","frequency_recommendation_pct":0}],"optimal_action":{"action":"","frequency_pct":0,"sizing_pct_pot":null,"primary_justification":""},"exploitability_notes":[],"counter_adjustment":{"villain_adjustment":"","hero_response":""}}}`;

  const generateTrace = async () => {
    const context = buildContext();
    dispatch({ type: "SET_TRACE_ERROR", payload: null });
    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 2000,
          system: SYSTEM_PROMPT,
          messages: [{ role: "user", content: JSON.stringify(context) }],
        }),
      });
      const data = await res.json();
      const text = data.content?.[0]?.text || "";
      const trace = JSON.parse(text);

      const record = {
        messages: [
          { role: "system", content: SYSTEM_PROMPT },
          { role: "user", content: JSON.stringify(context) },
          { role: "assistant", content: text },
        ],
        metadata: {
          scenario_id: context.scenario_id,
          street: context.game_state.street,
          hero_equity: context.computed_metrics.hero_equity_pct,
          range_advantage: context.computed_metrics.range_advantage_score,
          nut_advantage: context.computed_metrics.nut_advantage_score,
          optimal_action: trace.reasoning_trace?.optimal_action?.action || "unknown",
          source: "RangeIQ-synthetic-v1",
          generated_at: new Date().toISOString(),
        }
      };
      dispatch({ type: "ADD_TRACE", payload: record });
    } catch (err) {
      dispatch({ type: "SET_TRACE_ERROR", payload: err.message });
    }
  };

  const exportJSONL = () => {
    const lines = traceQueue.map(r => JSON.stringify(r)).join("\n");
    const blob = new Blob([lines], { type: "application/jsonl" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rangeiq-traces-${new Date().toISOString().slice(0, 10)}.jsonl`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <Btn onClick={generateTrace} color={T.green}>Generate Trace (G)</Btn>
        <Btn onClick={exportJSONL} disabled={traceQueue.length === 0} color={T.yellow}>Export JSONL (E)</Btn>
        <Btn onClick={() => dispatch({ type: "CLEAR_TRACES" })} disabled={traceQueue.length === 0}>Clear Queue</Btn>
        <span style={{ fontFamily: "monospace", fontSize: 12, color: T.muted, alignSelf: "center" }}>
          {traceQueue.length} traces (~{(JSON.stringify(traceQueue).length / 1024).toFixed(1)}KB)
        </span>
      </div>

      {traceError && (
        <Card style={{ borderColor: T.red, marginBottom: 12 }}>
          <span style={{ color: T.red, fontSize: 12, fontFamily: "monospace" }}>Error: {traceError}</span>
        </Card>
      )}

      {lastTrace && (
        <Card>
          <Label>Latest Trace</Label>
          <pre style={{
            background: T.bgPrimary, padding: 8, borderRadius: 4,
            fontSize: 10, color: T.text, fontFamily: "monospace",
            maxHeight: 400, overflow: "auto", marginTop: 6, whiteSpace: "pre-wrap"
          }}>
            {JSON.stringify(lastTrace, null, 2)}
          </pre>
        </Card>
      )}

      {/* TODO: Batch generation mode */}
      {/* TODO: Trace quality indicators (coverage, specificity, consistency) */}
    </div>
  );
}

// ============================================================
// MODULE 5 — SCENARIO LIBRARY (STUB)
// ============================================================
function Module5({ state, dispatch }) {
  const [name, setName] = useState("");
  const [tags, setTags] = useState("");

  const save = () => {
    if (!name) return;
    dispatch({
      type: "SAVE_SCENARIO",
      payload: {
        name, tags: tags.split(",").map(s => s.trim()),
        heroRange: [...state.heroRange],
        villainRange: [...state.villainRange],
        board: state.board,
        heroHand: state.heroHand,
        evTreeConfig: state.evTreeConfig,
        savedAt: new Date().toISOString(),
      }
    });
    setName("");
    setTags("");
  };

  const exportLib = () => {
    const blob = new Blob([JSON.stringify(state.scenarios, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `rangeiq-scenarios-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div>
      <Card style={{ marginBottom: 12 }}>
        <Label>Save Current State</Label>
        <div style={{ display: "flex", gap: 8, marginTop: 6, flexWrap: "wrap" }}>
          <input
            placeholder="Scenario name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ background: T.bgElevated, color: T.text, border: `1px solid ${T.border}`, borderRadius: 4, padding: "4px 8px", fontFamily: "monospace", fontSize: 12, flex: 1 }}
          />
          <input
            placeholder="Tags (comma-separated)"
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            style={{ background: T.bgElevated, color: T.text, border: `1px solid ${T.border}`, borderRadius: 4, padding: "4px 8px", fontFamily: "monospace", fontSize: 12, flex: 1 }}
          />
          <Btn onClick={save} color={T.green}>Save</Btn>
          <Btn onClick={exportLib} disabled={state.scenarios.length === 0}>Export JSON</Btn>
        </div>
      </Card>

      {state.scenarios.length === 0 ? (
        <div style={{ color: T.muted, fontSize: 12, fontFamily: "monospace", textAlign: "center", padding: 32 }}>
          No saved scenarios. Build a game state and save it here.
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {state.scenarios.map((s, i) => (
            <Card key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontFamily: "monospace", fontSize: 13, color: T.text }}>{s.name}</div>
                <div style={{ fontSize: 10, color: T.muted }}>
                  {s.tags.join(", ")} · {s.heroRange.length} hero / {s.villainRange.length} villain hands · Board: {s.board.length ? s.board.join(" ") : "none"}
                </div>
              </div>
              <Btn small onClick={() => dispatch({ type: "LOAD_SCENARIO", payload: s })}>Load</Btn>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================
// HEADER & APP SHELL
// ============================================================
const MODULE_NAMES = ["Range Builder", "Board & Equity", "EV Tree", "Trace Gen", "Scenarios"];

export default function RangeIQ() {
  const [state, dispatch] = useReducer(reducer, initialState);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      const num = parseInt(e.key);
      if (num >= 1 && num <= 5) dispatch({ type: "SET_MODULE", payload: num });
      if (e.key === "c" || e.key === "C") dispatch({ type: "CLEAR_RANGE" });
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const hCombos = totalCombos(state.heroRange);
  const vCombos = totalCombos(state.villainRange);
  const hPrem = countPremiums(state.heroRange);
  const vPrem = countPremiums(state.villainRange);
  const naScore = (hPrem + vPrem) > 0 ? ((hPrem / (hPrem + vPrem)) * 100).toFixed(1) : "—";

  return (
    <div style={{
      background: T.bgPrimary, color: T.text, minHeight: "100vh",
      fontFamily: "'JetBrains Mono', 'Fira Code', 'SF Mono', monospace"
    }}>
      {/* HEADER */}
      <div style={{
        background: T.bgCard, borderBottom: `1px solid ${T.border}`,
        padding: "8px 16px", display: "flex", alignItems: "center", gap: 16,
        position: "sticky", top: 0, zIndex: 100,
      }}>
        <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: -0.5 }}>
          <span style={{ color: T.blue }}>Range</span><span style={{ color: T.text }}>IQ</span>
        </div>

        {/* Module tabs */}
        <div style={{ display: "flex", gap: 2 }}>
          {MODULE_NAMES.map((name, i) => (
            <button
              key={i}
              onClick={() => dispatch({ type: "SET_MODULE", payload: i + 1 })}
              style={{
                background: state.activeModule === i + 1 ? T.bgElevated : "transparent",
                color: state.activeModule === i + 1 ? T.text : T.muted,
                border: "none", padding: "6px 12px", borderRadius: 4,
                fontSize: 12, cursor: "pointer", fontFamily: "monospace",
              }}
            >
              <span style={{ color: T.muted, marginRight: 4 }}>{i + 1}</span>{name}
            </button>
          ))}
        </div>

        {/* Live stats */}
        <div style={{ marginLeft: "auto", display: "flex", gap: 16, fontSize: 11 }}>
          <span>H:<span style={{ color: T.blue }}>{hCombos}</span></span>
          <span>V:<span style={{ color: T.red }}>{vCombos}</span></span>
          <span>NA:<span style={{ color: T.yellow }}>{naScore}%</span></span>
          <span>Traces:<span style={{ color: T.green }}>{state.traceQueue.length}</span></span>
        </div>
      </div>

      {/* CONTENT */}
      <div style={{ padding: 16, maxWidth: 1200, margin: "0 auto" }}>
        {state.activeModule === 1 && <Module1 state={state} dispatch={dispatch} />}
        {state.activeModule === 2 && <Module2 state={state} dispatch={dispatch} />}
        {state.activeModule === 3 && <Module3 state={state} dispatch={dispatch} />}
        {state.activeModule === 4 && <Module4 state={state} dispatch={dispatch} />}
        {state.activeModule === 5 && <Module5 state={state} dispatch={dispatch} />}
      </div>
    </div>
  );
}
