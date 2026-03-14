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
      if (heroContrib >= 1) draws.push("Backdoor FD");
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

function runMonteCarlo(heroRange, villainRange, board, deadCards, dispatch, iterations = 50000, heroHandFixed = null) {
  const CHUNK = 5000;

  // Pre-expand all combos (filter dead cards + board)
  const usedPreflop = new Set([...board, ...deadCards]);
  // heroHandFixed: when set, lock hero to one specific combo instead of sampling the full range
  const heroCombos = heroHandFixed
    ? [heroHandFixed]
    : [...heroRange].flatMap(h => expandHand(h, [...usedPreflop]));
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
      let vc;
      let attempts = 0;
      do {
        vc = villainCombos[Math.floor(Math.random() * villainCombos.length)];
        attempts++;
      } while (vc.some(c => hSet.has(c)) && attempts < 20);
      if (attempts >= 20) continue;

      // Build runout deck (deckArr already excludes board+dead; just filter hc+vc)
      const hcvcSet = new Set([...hc, ...vc]);
      const runDeck = deckArr.filter(c => !hcvcSet.has(c));

      // Deal remaining board cards
      const needed = Math.max(0, 5 - board.length);
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
      const tieEq = total ? ties / total : 0;
      dispatch({ type: "SET_METRICS", payload: {
        equity: {
          hero: heroEq * 100,
          villain: villainEq * 100,
          tie: tieEq * 100,
        },
        histogram: null, // deferred — bucket hero win% into 10% bands
      }});
      dispatch({ type: "SET_MC_RUNNING", payload: false });
    } else {
      setTimeout(runChunk, 0);
    }
  }

  dispatch({ type: "SET_MC_RUNNING", payload: true });
  setTimeout(runChunk, 0);
}

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
  const fdScore = maxSuitCount >= 3 ? 4 : maxSuitCount === 2 ? 2 : 0;
  const sdScore = Math.min(4, connectivity * 2);
  const pairedScore = isPaired ? -2 : 0;
  const wetness = Math.max(0, Math.min(10, fdScore + sdScore + pairedScore));

  return { flushTexture, isPaired, connectivity, wetness };
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
    potSize: 6,
    effStack: 100,
    betSizings: [0.33, 0.66, 1.0],
    nodes: [],
    selectedLine: [],
    hoveredNodeId: null,
    siblingCollapseEnabled: false,
    evTreeLine: null,
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
    case "SET_EV_TREE_NODES":
      return { ...state, evTreeConfig: { ...state.evTreeConfig, nodes: action.payload } };
    case "SET_EV_SELECTED_LINE":
      return { ...state, evTreeConfig: { ...state.evTreeConfig, selectedLine: action.payload } };
    case "SET_EV_HOVERED":
      return { ...state, evTreeConfig: { ...state.evTreeConfig, hoveredNodeId: action.payload } };
    case "TOGGLE_EV_NODE_EXPANDED": {
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
// MODULE 2 — BOARD & EQUITY
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
            <YAxis
              type="category"
              dataKey="cat"
              tick={{ fontSize: 10, fill: T.muted, fontFamily: "monospace" }}
              width={115}
            />
            <Tooltip
              contentStyle={{
                background: T.bgCard,
                border: `1px solid ${T.border}`,
                fontSize: 11,
                fontFamily: "monospace",
              }}
              formatter={(v) => [`${v} combos`, "count"]}
            />
            <Bar dataKey="count" fill={color} radius={[0, 3, 3, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function Module2({ state, dispatch }) {
  const { board, heroHand, deadCards, heroRange, villainRange, mcRunning, metrics } = state;
  const allDead = useMemo(() => [...(heroHand || []), ...deadCards], [heroHand, deadCards]);
  const texture = useMemo(() => boardTexture(board), [board]);

  const heroHandClassification = useMemo(() => {
    if (heroHand && heroHand.length === 2 && board.length >= 3) {
      return classifyHand(heroHand, board);
    }
    return null;
  }, [heroHand, board]);

  return (
    <div>
      {/* Card Selectors */}
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
            <Label>Monte Carlo Equity ({heroHand && heroHand.length === 2 ? heroHand.join("") : totalCombos(heroRange)}h × {totalCombos(villainRange)}v combos)</Label>
            <Btn
              small
              color={T.green}
              disabled={mcRunning || !heroRange.size || !villainRange.size}
              onClick={() => runMonteCarlo(heroRange, villainRange, board, allDead, dispatch, 50000, heroHand && heroHand.length === 2 ? heroHand : null)}
            >
              {mcRunning ? "Running…" : "Run MC (R)"}
            </Btn>
          </div>
          {metrics.equity && (
            <div style={{ display: "flex", gap: 24 }}>
              <Stat label="Hero Equity" value={metrics.equity.hero.toFixed(2) + "%"} color={T.blue} />
              <Stat label="Villain Equity" value={metrics.equity.villain.toFixed(2) + "%"} color={T.red} />
              {metrics.equity.tie > 0.01 && (
                <Stat label="Tie" value={metrics.equity.tie.toFixed(2) + "%"} color={T.muted} />
              )}
            </div>
          )}
          {!metrics.equity && !mcRunning && (
            <div style={{ fontSize: 11, color: T.muted }}>Set hero + villain ranges then run.</div>
          )}
        </Card>
      )}

      {/* Range Breakdowns */}
      {board.length >= 3 && (heroRange.size > 0 || villainRange.size > 0) && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          <Card>
            <RangeBreakdown range={heroRange} board={board} deadCards={allDead} label="Hero" color={T.blue} />
          </Card>
          <Card>
            <RangeBreakdown range={villainRange} board={board} deadCards={allDead} label="Villain" color={T.red} />
          </Card>
        </div>
      )}
    </div>
  );
}

// ============================================================
// MODULE 3 — HELPERS
// ============================================================
function makeNodeId(parentId, action, sizing) {
  const sizingTag = sizing != null ? `_${Math.round(sizing * 100)}` : "";
  return `${parentId}__${action}${sizingTag}`;
}

function buildTree({
  potSize,
  effStack,
  betSizings,
  equity,
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
    if (S > effStack - heroInvestment) return;
    const betId = makeNodeId(parentId, "bet", s);

    const foldPct = S / (potSize + S) * 100;
    const callPct = potSize / (potSize + S) * 100;
    const raisePct = 0;

    const R = S * 2.5;
    const heroFoldToRaise = (1 - (R - S) / (potSize + R)) * 100;

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
        { id: makeNodeId(betId, "villain_fold", null), street, action: "villain_fold",
          label: "Villain folds", betSize: 0, betSizeBb: 0,
          potAfter: potSize + S, heroInvestmentAfter: heroInvestment + S,
          villainFoldPct: 0, villainCallPct: 0, villainRaisePct: 0,
          heroFoldToRaise: 0, equityAssumption: equity,
          equity_is_approximated: street !== "flop",
          ev: null, expanded: false, children: [], isLeaf: true },
        { id: makeNodeId(betId, "villain_call", null), street, action: "villain_call",
          label: "Villain calls", betSize: 0, betSizeBb: 0,
          potAfter: potSize + 2 * S, heroInvestmentAfter: heroInvestment + S,
          villainFoldPct: 0, villainCallPct: 0, villainRaisePct: 0,
          heroFoldToRaise: 0, equityAssumption: equity,
          equity_is_approximated: nextStreet !== "flop",
          ev: null, expanded: false, isLeaf: callChildren.length === 0,
          children: callChildren },
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

function computeNodeEV(node) {
  const eq = node.equityAssumption;
  const pot = node.potAfter;
  const inv = node.heroInvestmentAfter;

  // ── LEAF NODES ──
  if (node.isLeaf) {
    switch (node.action) {
      case "villain_fold":  return pot;
      case "hero_fold":     return -inv;
      case "check_behind":
      case "hero_call":
      case "villain_call":  return eq * pot - (1 - eq) * inv;
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

  // ── CHECK NODES ──
  if (node.action === "check") {
    if (!node.children?.length) return eq * pot - (1 - eq) * inv;
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

  // Fallthrough
  if (node.children?.length) {
    return Math.max(...node.children.map(computeNodeEV));
  }
  return eq * pot - (1 - eq) * inv;
}

function stampEV(nodes) {
  return nodes.map(n => {
    const children = n.children?.length ? stampEV(n.children) : [];
    const withChildren = { ...n, children };
    return { ...withChildren, ev: computeNodeEV(withChildren) };
  });
}

function buildAncestorChain(leafId) {
  const parts = leafId.split("__");
  const chain = [];
  for (let i = 1; i <= parts.length; i++) {
    chain.push(parts.slice(0, i).join("__"));
  }
  return chain;
}

function TreeNode({ node, depth, selectedLine, dispatch, siblingCollapse }) {
  const isSelected = selectedLine.includes(node.id);
  const evColor = node.ev === null ? T.muted
    : node.ev > 0.5 ? T.green
    : node.ev < -0.5 ? T.red
    : T.yellow;

  const approxBadge = node.equity_is_approximated
    ? <span style={{ color: T.yellow, fontSize: 10, marginLeft: 4 }}>⚠approx</span>
    : null;

  const raiseComputed = Math.max(0, 100 - node.villainFoldPct - node.villainCallPct);

  const handleSelectLine = () => {
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
        {!node.isLeaf && (
          <span
            style={{ color: T.muted, fontSize: 10, width: 12, userSelect: "none" }}
            onClick={e => { e.stopPropagation(); dispatch({ type: "TOGGLE_EV_NODE_EXPANDED", payload: node.id }); }}
          >
            {node.expanded ? "▾" : "▸"}
          </span>
        )}
        {node.isLeaf && <span style={{ width: 12 }} />}

        <span style={{ color: T.text, fontSize: 12, flex: 1, fontFamily: "monospace" }}>
          {node.label}
          {approxBadge}
        </span>

        <span style={{ color: T.muted, fontSize: 11, fontFamily: "monospace", width: 70, textAlign: "right" }}>
          pot {node.potAfter.toFixed(1)} bb
        </span>

        <span style={{ color: evColor, fontSize: 12, fontFamily: "monospace", width: 70, textAlign: "right" }}>
          {node.ev !== null ? `EV ${node.ev.toFixed(2)}` : "—"}
        </span>

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

        {node.action === "villain_raise" && (
          <span style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <input type="number" min={0} max={100} value={Math.round(node.heroFoldToRaise)}
              onChange={e => handleFreqChange("heroFoldToRaise", e.target.value)}
              style={{ width: 44, background: T.bgElevated, color: T.text, border: `1px solid ${T.border}`, borderRadius: 3, padding: "1px 4px", fontSize: 10, fontFamily: "monospace" }}
            />
            <span style={{ color: T.muted, fontSize: 10 }}>hFold%</span>
          </span>
        )}

        {node.isLeaf && (
          <Btn
            onClick={e => { e.stopPropagation(); handleSelectLine(); }}
            style={{ fontSize: 10, padding: "1px 6px", marginLeft: 4 }}
          >
            Select
          </Btn>
        )}
      </div>

      {node.expanded && !node.isLeaf && node.children?.map(child => (
        <TreeNode key={child.id} node={child} depth={depth + 1}
          selectedLine={selectedLine} dispatch={dispatch}
          siblingCollapse={siblingCollapse} />
      ))}
    </div>
  );
}

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
  const P = node.potAfter - S;
  const bePct = S > 0 ? S / (P + S) : null;
  const gtoBluffFreq = S > 0 ? S / (S + P) : null;
  const bluffValueRatio = S > 0 ? S / P : null;

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
  const stateRef = useRef(state);
  useEffect(() => { stateRef.current = state; }, [state]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      const num = parseInt(e.key);
      if (num >= 1 && num <= 5) dispatch({ type: "SET_MODULE", payload: num });
      if (e.key === "c" || e.key === "C") dispatch({ type: "CLEAR_RANGE" });
      if (e.key === "r" || e.key === "R") {
        const s = stateRef.current;
        if (s.activeModule === 2 && !s.mcRunning && s.board.length >= 3 && s.heroRange.size && s.villainRange.size) {
          const dead = [...(s.heroHand || []), ...s.deadCards];
          const hFixed = s.heroHand && s.heroHand.length === 2 ? s.heroHand : null;
          runMonteCarlo(s.heroRange, s.villainRange, s.board, dead, dispatch, 50000, hFixed);
        }
      }
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
