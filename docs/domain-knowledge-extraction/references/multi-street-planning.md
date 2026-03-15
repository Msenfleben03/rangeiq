# Multi-Street Planning and EV Architecture --- The Operational Layer

## Core Concepts

### Equity Realization as a Position-Dependent Multiplier

Raw Monte Carlo equity measures how often a hand wins at showdown against a range, assuming both players check every street to the river. This assumption is catastrophically wrong for multi-street EV computation because it ignores who controls the pot-growing and pot-limiting decisions.

**The quantified gap:** In-position (IP) hands realize approximately 105--115% of their raw equity. Out-of-position (OOP) hands realize approximately 60--80% of their raw equity. The delta depends on board texture and hand category:

- **Nut hands (top set, nut flush):** Equity realization is near-symmetric (95--105% regardless of position) because the hand is strong enough to extract value or win a large pot from either position. The information disadvantage matters less when you are never making a mistake.
- **Medium-strength hands (top pair good kicker, overpair on wet board):** This is where the position gap is widest. IP realizes ~110%, OOP realizes ~65--75%. The OOP player faces an unresolvable problem: betting folds out worse and gets called by better, checking invites a bet that forces a marginal call-or-fold. IP can pot-control by checking back with these exact hands, realizing their equity for free.
- **Drawing hands (flush draws, OESDs):** OOP draws realize ~70--85% of raw equity due to the ability to lead (donk bet or check-raise as a semi-bluff), but the range of realization is wider --- some draws realize far less when they face bets on every street without completing. IP draws realize ~100--110% because checking back preserves the option to see cheap cards.
- **Air (no pair, no draw, below bottom pair):** Realization is asymmetric in the opposite direction: OOP air realizes *more* fold equity via donk bets and check-raises than IP air via delayed c-bets. However, this only applies when villain's range is wide enough to fold --- against narrow continuing ranges, both positions realize ~0% with air.

**Board texture modulation of the realization gap:**

- **Dry static boards (K-7-2 rainbow, A-8-3 rainbow):** The gap narrows to ~10% (IP ~105%, OOP ~95%) because the board doesn't change. Both players can accurately evaluate their hand on every street. The OOP disadvantage of "not knowing where you stand" is minimized when the board tells you clearly.
- **Wet dynamic boards (J-T-8 two-tone, 9-8-7 monotone):** The gap widens to ~25--30% (IP ~115%, OOP ~70--85%). Every turn card reshuffles hand strengths. The IP player can react to the new information; the OOP player must act first without knowing the IP player's reaction.
- **Paired boards:** The gap is intermediate (~15%) but non-obvious: the pairing reduces draw density, which should narrow the gap, but it also creates a set-mining dynamic where the IP player's ability to check back marginal hands becomes more valuable.

**Implementation consequence for `computeNodeEV`:** The `equityAssumption` parameter is currently a single scalar passed into `buildTree` and propagated unchanged to every node. It should be position-adjusted before entry. A first-order correction: multiply raw MC equity by a realization factor `R_pos` where `R_pos = 1.10` for IP and `R_pos = 0.75` for OOP as baseline defaults, then modulate by board wetness: `R_pos_adjusted = R_pos + (0.05 * (5 - wetness) / 5)` for OOP (dry boards push toward 1.0), `R_pos_adjusted = R_pos + (0.05 * wetness / 5)` for IP (wet boards amplify IP advantage). This is a heuristic, not a solver result, but it corrects the largest systematic error in multi-street EV by ~5--15% of pot in typical spots.

### The Commitment Threshold and Retroactive Planning

A postflop decision is not a single choice --- it is a conditional plan that constrains all future actions. The failure to model this is the single largest architectural gap in street-independent EV computation.

**SPR-based commitment thresholds:**

- **SPR < 2 (typical 4-bet pots, some 3-bet pots):** (Note: bet-sizing-theory.md uses a coarser four-tier SPR table focused on sizing strategy selection; this five-tier table describes commitment behavior specifically and the two classifications are complementary, not contradictory.) Any call on the flop commits you to calling the remaining stack on any turn/river. The mathematical argument: if you call a half-pot bet on the flop at SPR 2, the remaining SPR is ~0.5. Villain can shove the turn for less than the pot. You need ~33% equity to call. Any hand that had enough equity to call the flop bet has at least that much on the turn (folding the flop-calling range loses the equity you already invested). "Call flop, fold turn" at SPR < 2 is dominated by "fold flop" in almost all cases --- the exception is when a specific card dramatically kills your equity (completing a four-flush you don't hold), which affects <10% of runouts.
- **SPR 2--4 (typical 3-bet pots IP vs OOP):** A flop call commits you to calling one more street in most cases. Two calls (flop + turn) commit you to the river. The critical decision is whether to call the flop at all --- once you do, the "call flop, fold turn" line is -EV against competent opponents because they can bet any two cards on the turn knowing you've capped your range by not raising the flop. The mathematical proof: at SPR 3, a 66% pot bet on the flop leaves SPR ~1.2 after calling. Villain shoves turn for slightly over pot. You need ~40% equity. But the hands in your flop-calling range that have <40% equity on the turn are the ones where the turn card was bad --- and villain knows this and can bluff those turns with impunity because you've committed ~40% of your stack and folding forfeits that investment.
- **SPR 4--8 (typical single-raised pots IP):** The first call does not commit you. "Call flop, evaluate turn" is a legitimate strategy. But "call flop, call turn, fold river" becomes the dominated line: at SPR 6, after calling 66% pot bets on flop and turn, you've invested ~55% of your effective stack and are getting ~2.8:1 on a river call. Folding gives villain a guaranteed profit on their bluffs.
- **SPR 8--13 (deeper single-raised pots):** Full multi-street planning is essential. No single call commits you, but the *sequence* of calls creates implicit commitment. The key planning question: "If I call here and villain bets the turn, what is my plan?" If the answer is "fold most turns," the flop call was likely -EV.
- **SPR > 13 (deep-stacked, limped pots):** Implied odds dominate. Set-mining, suited connector play, and speculative hands gain EV from the depth. Commitment thresholds are irrelevant because no single bet can force commitment.

**The retroactive planning failure in `buildTree`:** The current implementation generates street-by-street children with independent frequency decisions. A node on the turn does not "know" that its parent was a flop call that committed hero to a specific plan. The `heroInvestment` field tracks cumulative money invested but is not used to constrain decision frequencies --- a turn node still offers hero_fold as a full-frequency option even when folding is dominated by the flop call that preceded it. This is architecturally correct for a general EV calculator (it *should* show the fold option), but the GTO-seeded frequencies should reflect the commitment reality: at SPR < 4, `heroFoldToRaise` on the turn after a flop call should be seeded much lower (5--15%) than the default pot-odds formula produces, because folding after committing is the exploitable line.

### Range Narrowing and Street-Conditional Equity

The range that reaches the turn is not the preflop range. It is the subset of the preflop range that found a flop call (or raise) profitable. This subset has systematically different equity properties than the original range.

**How ranges narrow by street:**

- **Flop:** The preflop range splits into betting range, calling range, and folding range. The folding range is typically the bottom ~30--40% of the preflop range (air and weak backdoor draws). The continuing range retains all made hands, strong draws, and selected backdoor draws.
- **Turn:** The flop-calling range splits again. The turn folding range is hands that were drawing and missed (e.g., flush draws when a non-flush turn card arrives, OESDs that didn't complete, backdoor draws that lost their third card). The continuing range is enriched in made hands and live draws.
- **River:** The turn-calling range splits a final time. By the river, both ranges are heavily concentrated in made hands. The draw density is zero. The calling range is almost entirely "hands that believe they're best" plus bluff-catchers.

**The equity shift magnitude:** On a typical flop like J-T-7 two-tone, the preflop raiser's range might have 52% equity against the BB calling range. After the BB calls a c-bet, the BB's *continuing* range gains equity --- it is now 48--52% rather than 42--48% against the raiser's full range, because the BB folded hands with <35% equity and retained hands with >45% equity. By the turn, if both players continue, the equity is typically within 5 points of 50-50 because both ranges have been filtered to hands that can compete. This is the "convergence toward 50% equity" that multi-street play produces.

**The specific failure in `buildTree`:** The `equity` parameter is set once at tree construction time and propagated to every node via `equityAssumption`. A flop node and its turn grandchild use the same equity value. This is what `equity_is_approximated: true` flags on non-flop nodes --- it signals that the equity used is stale. The directional error is predictable: `equityAssumption` on turn and river nodes overstates the range equity differential. If hero has 55% equity on the flop, hero's turn equity (conditional on both players continuing) is closer to 52%. Using 55% on the turn inflates `computeNodeEV` by approximately `(0.55 - 0.52) * potAfter`, which for a 10bb pot is 0.3bb per node --- small in isolation but compounding across the tree to produce ~1--3bb total EV distortion.

**Modeling the correction:** The ideal fix is per-street MC re-estimation where `runMonteCarlo` is called with the narrowed ranges (hero's continuing range and villain's continuing range) at each street transition. The practical approximation: apply a dampening factor to equity on later streets. `equity_turn = equity_flop * 0.95 + 0.50 * 0.05` (regress toward 50% by 5% per street). `equity_river = equity_turn * 0.90 + 0.50 * 0.10` (regress by 10%). This captures the convergence-toward-equilibrium effect without the computational cost of per-street MC.

### The Blocker Cascade Across Streets

On the flop, blockers affect combo counts in a straightforward way: holding the A of spades on a two-spade board reduces villain's nut flush draw combos. The base combinatorial framework for these calculations — specifically how holding specific cards shifts villain's range distribution by calculable percentages — is defined in range-construction.md (Blocker Effects as Probability Shifts section). By the river, the blocker cascade is dramatically more complex because the *continuing range* has been filtered by actions, and blockers interact with the filtering.

**Street-by-street blocker evolution:**

- **Flop:** Hero holds A-5 of spades on K-9-4 with two spades. Villain's range includes flush draws (A-Xs, suited connectors with a spade). Hero's A of spades blocks ~50% of villain's nut flush draw combos. The blocker effect on fold equity is moderate: villain's continuing range is slightly less draw-heavy than raw combo counts suggest, so villain folds slightly more often to a c-bet.
- **Turn (spade):** The flush completes. But hero's As means villain cannot have the nut flush. The blocker value inverts: instead of reducing villain's draw combos (which no longer exist --- the draw completed or missed), the As now blocks villain's *made nut flush* combos. If villain bets, they are less likely to have the nuts. Hero's bluff-catching ability increases.
- **Turn (non-spade):** Villain's flush draws remain live. But the continuing range on the turn is enriched in flush draws (villain called the flop with draws), so the blocker's effect on the continuing range is *amplified* compared to the flop. Hero's As now blocks a larger percentage of villain's remaining range because the non-draw hands that would dilute the blocker effect have partially folded on the flop.
- **River:** The ultimate blocker value depends on the specific runout. On a brick river after a non-spade turn, villain's range is heavily polarized: made hands that called twice, and flush draws that are now busted. Hero's As blocks villain's busted nut-flush-draw bluffs --- which means villain has fewer natural bluffs, and their river bet is more weighted toward value. This is the "blocker paradox": the card that gave hero bluff equity on the flop (by blocking villain's draws) now reduces hero's bluff-catching equity on the river (by blocking villain's natural bluffs).

**The combinatorial tracking requirement:** At each street transition in `buildTree`, the villainCallPct, villainFoldPct, and villainRaisePct implicitly define which *portion* of villain's range takes each action. But the current implementation treats these as scalar percentages of a uniform range. In reality, the calling portion has a different composition than the folding portion. The villain_call child should inherit not just a reduced frequency but a *different equity landscape* because villain's calling range on the flop (strong made hands + draws) has different equity on the turn than villain's folded range (air + weak hands) would have had. This is the fundamental gap: `equityAssumption` should change not just for convergence-toward-50% reasons, but because the *specific composition* of the surviving range changes the equity distribution.

### Implied Odds vs. Reverse Implied Odds at Depth

Standard implied odds calculation: `(pot + future_winnings) / call_amount > 1 / equity_to_improve`. This fails to account for the hands that *beat you even after you improve*.

**Reverse implied odds dominate in these conditions:**

1. **Drawing to non-nut hands on boards with better draws available:**
   - Middle flush draw (e.g., T-high flush draw) on a two-tone board where A-high and K-high flush draws are in villain's range. You complete your flush ~19% of the time, but when you do, villain also completes a better flush ~25--35% of those times (depending on range composition). Your effective equity when the flush completes is not 100% but ~65--75%. At deep stacks (SPR > 8), the money lost when you make your flush but villain makes a better one can exceed the money won when you make yours and villain has a worse hand.
   - Straight draws on paired boards: completing the straight when villain has a full house is a catastrophic loss. If the board is 8-8-6 and you hold 7-5, making the straight on a 4 or 9 still loses to any trip 8s or better, which constitutes a significant portion of villain's continuing range on a paired board.

2. **SPR thresholds where RIOL dominates:**
   - At SPR < 6, reverse implied odds rarely dominate because the remaining stack is not deep enough to create large losses when you improve but are beaten. The maximum additional loss is ~3--4x pot.
   - At SPR 6--10, RIOL begins to matter for non-nut draws. The middle flush draw example: calling a 66% pot bet on the flop with 9 outs (19% to improve) requires implied odds of ~4:1. You get this from the remaining stack. But ~30% of the time you improve, you lose an additional 3--5x pot to a better flush. Net implied odds after RIOL adjustment: ~2.8:1. The call becomes marginal to -EV.
   - At SPR > 12, RIOL can dominate outright for non-nut draws. The full implied odds calculation must discount winning improvements by the probability and magnitude of reverse-implied-odds scenarios.

3. **The `runMonteCarlo` failure mode:** MC equity counts a win as a win regardless of how the hand plays out post-improvement. Hero makes a T-high flush and wins at showdown? Full win credit. Hero makes a T-high flush and faces a pot-sized bet? MC doesn't model this --- it assumed both players check to showdown. The equity is correct in a check-to-showdown sense but wrong in a "how much money do I actually win/lose" sense. Multi-street EV computation in `computeNodeEV` partially compensates (it models future betting), but the `equityAssumption` input doesn't distinguish between "equity from nut hands" and "equity from second-best hands," so the compensation is incomplete.

### Multi-Street Bluff Coherence

A bluff that succeeds is one where the betting sequence on all previous streets is consistent with a value hand in the bluffer's range. The failure mode is constructing bluffs backward from the current street without verifying that the story is forward-coherent.

**Forward coherence requirements:**

- **Flop:** The bluffing hand must be in hero's range on this board. If hero opened from UTG, a bluff with 7-6 offsuit on A-K-Q rainbow is not coherent because 7-6o is not in a UTG range. A bluff with A-5s is coherent because it's in the UTG range and interacts with the board (A-high, potential flush draw if suited to the board).
- **Turn:** The bluffing hand must have a plausible reason to have bet or called the flop. If hero c-bet the flop, the turn bluff hand must look like something that would c-bet (most hands in a c-betting range, but specifically overcards, gutshots, backdoor draws). If a new card arrives on the turn, the bluff gains credibility if it "could have hit" --- e.g., hero bets A-5 on K-9-4 flop, turn is a 5. Hero can now barrel credibly because the 5 could have given hero two pair with K-5 or 9-5 suited (which are in some ranges).
- **River:** The final barrel must represent a hand that bet all previous streets for value. The key question: "What value hands in my range took this exact line?" If the answer is "only the nuts," the bluff needs to be very rare (because villain knows the value range is tiny and can call wider). If the answer is "top pair, overpairs, two pair, sets," the bluff can be more frequent because villain cannot call with everything.

**Runout types that enhance or destroy bluff credibility:**

- **Enhancing:** Overcards that hit the preflop raiser's range (A or K on the turn after a low flop), completing flush draws that are in hero's range, pairing the top card (enhances set and two-pair combinations in hero's betting range).
- **Destroying:** Pairing the bottom or middle card (hero's range rarely contains these specific pairs), completing a draw that hero's range wouldn't have been drawing to (e.g., a straight completes on the river via a card that connects the bottom of the board, and hero's range wouldn't have open-ended on the flop), brick runouts that don't change anything (the lack of a scare card means hero's bluff doesn't gain any new "story").

**The EV tree failure mode:** In `computeNodeEV`, a bluff bet on the river is evaluated as: `villainFoldPct * pot + villainCallPct * (eq * pot - (1-eq) * inv)`. The `villainFoldPct` is set by GTO seeding from `S / (P + 2S)`, which is bet-size-dependent but not story-dependent. This is the same sizing-independence property documented in bet-sizing-theory.md (Donk Bet Paradox and Failure Mode 6); the multi-street context amplifies rather than changes the underlying mechanism. Two river bluffs of the same size get the same villainFoldPct even if one tells a coherent three-street story and the other doesn't. The current architecture cannot model this because story coherence is a *range-level* property (which hands took this line?) not a *node-level* property (what is the bet size?). This is fundamentally correct for a GTO engine (at equilibrium, villain folds at the frequency that makes hero indifferent) but wrong for exploitative modeling or trace generation (where the story determines whether the bluff is part of a balanced range or an isolated bluff that villain should call).

**For trace generation specifically:** Any trace that includes a multi-street bluff *must* include the range context at each decision point: "Hero's range on this turn after betting the flop includes {value hands} and {draws/bluffs}. The turn card changed the range composition by {completing X draws, bricking Y draws}. Hero's continued bet represents {remaining value hands + surviving draws}." Without this context, the trace trains the LLM to evaluate bluffs in isolation, which produces incoherent multi-street bluffing.

## Failure Modes and Anti-Patterns

### Severity 1: Static Equity Across Streets (Currently Active)

**Trigger:** `buildTree` receives a single `equity` parameter and propagates it to all nodes on all streets via `equityAssumption`.

**What it looks like:** Turn and river EV calculations use flop equity, overstating hero's equity advantage (or disadvantage) by 3--8 percentage points. A hand with 55% flop equity is modeled as having 55% turn and river equity when the true conditional equity is closer to 51--53%.

**Detection:** Compare `computeNodeEV` output for a turn node against a manual calculation where equity is regressed toward 50%. If the delta exceeds 0.5bb, the static equity assumption is producing meaningful error.

**Magnitude:** ~1--3bb total EV distortion across a full flop-to-river tree at 100bb effective stacks. Systematically biases toward action (calling and betting) because overstated equity makes marginal decisions look profitable.

### Severity 2: No Position-Adjusted Equity Realization

**Trigger:** `equityAssumption` is raw MC equity regardless of whether hero is IP or OOP.

**What it looks like:** OOP hero EV is overstated by ~10--20% of pot on wet boards. IP hero EV is slightly understated. The effect is invisible in the tree visualization because the numbers look "close enough," but it compounds: a 3-street line with 5% overstatement per street produces a cumulative ~15% EV error at the terminal node.

**Detection:** Run the same scenario IP and OOP. If `computeNodeEV` returns the same value (differing only by the direct strategic choices, not by the equity input), the position adjustment is missing.

**Magnitude:** 2--5bb systematic error per hand at 100bb stacks on medium-wet boards. Largest on boards with high draw density (J-T-8 two-tone, 9-7-5 monotone).

### Severity 3: Independent Street Evaluation (Commitment Not Modeled)

**Trigger:** `heroFoldToRaise` and `villainFoldPct` are computed from bet-sizing formulas independently at each node, without reference to prior actions in the line.

**What it looks like:** At SPR 3 in a 3-bet pot, `buildTree` generates a turn hero_fold node with a pot-odds-derived fold frequency of ~40%. But hero already called a flop bet, investing ~30% of effective stack. Folding the turn after this investment is almost always dominated. The tree suggests "fold 40% to turn bet" when the correct frequency is closer to 5--15%.

**Detection:** Inspect turn hero_fold nodes in low-SPR trees. If `heroFoldToRaise > 20` after a flop call that committed >25% of effective stack, the commitment adjustment is missing.

### Severity 4: RIOL Not Discounted in Equity

**Trigger:** `runMonteCarlo` credits full wins for non-nut improving hands without stack-depth weighting.

**What it looks like:** Middle flush draws and non-nut straight draws show inflated equity. A T-high flush draw on a two-spade board might show 38% MC equity, but the equity-with-RIOL-discount at SPR > 8 is closer to 30--33% because ~25% of completions lose a large pot to better flushes.

**Detection:** Compare MC equity for nut draws vs. non-nut draws on the same board. If the gap is <5%, RIOL is not being accounted for. Solver outputs show 8--15% equity gap between nut and non-nut flush draws on typical boards.

### Severity 5: Bluff Coherence Not Modeled

**Trigger:** `villainFoldPct` on bet nodes is sizing-derived, not story-derived.

**What it looks like:** The EV tree computes identical fold equity for a coherent three-barrel bluff and an incoherent one-street stab. This is GTO-correct (at equilibrium) but produces misleading trace data when used for LLM training, because the trace implies all bluffs of a given size have equal success rates.

**Detection:** This is invisible in the EV tree itself. It manifests in generated traces: if traces include river bluffs without upstream range context, the bluff coherence failure is present.

## Implementation Notes

### `buildTree` — Equity Propagation Correction

The equity parameter should accept an optional `equityDampening` coefficient. At each `depth` increment (street transition), apply: `equity_next = equity * (1 - dampening) + 0.50 * dampening`. Default `dampening = 0.05`. This is a one-line change at the recursive call sites (lines ~1080, ~1138 in current `RangeIQ.jsx`):

```
equity: equity * (1 - dampening) + 0.50 * dampening,
```

This transforms the current behavior (constant equity across streets) into a convergent model (equity regresses toward 50% on later streets), which is directionally correct for all common scenarios.

### `buildTree` — Position-Aware Construction

Add a `heroPosition` parameter (`"IP"` or `"OOP"`). Use it to modulate `equityAssumption` at node creation:

- IP: `equityAssumption: equity * 1.08` (capped at 0.95)
- OOP: `equityAssumption: equity * 0.82` (floored at 0.15)

These multipliers are conservative defaults. The `boardTexture` function already returns `wetness` (0--10 scale), which can further modulate: `realization_factor = base_factor + (wetness - 5) * 0.01 * direction` where `direction = +1` for IP (wetter boards amplify IP advantage) and `direction = -1` for OOP.

### `computeNodeEV` — Commitment-Adjusted Fold Frequencies

Add a pre-computation check: if `node.heroInvestmentAfter / effStack > 0.25` and the action is `hero_fold`, scale the fold frequency by `max(0.1, 1 - (node.heroInvestmentAfter / effStack))`. This reduces fold frequency as hero's committed stack fraction increases, reflecting the commitment reality. The 0.1 floor prevents complete elimination of the fold option (there are always runouts bad enough to fold even when committed).

### `runMonteCarlo` — Histogram for RIOL Detection

The `histogram: null` field in MC output is the key integration point. Implementing per-combo equity tracking enables RIOL detection: after MC completes, partition hero's winning combos into "nut wins" (hand rank category is the best possible on this board) and "non-nut wins." If the non-nut-win fraction exceeds 40% of total wins, flag the spot as RIOL-sensitive. This flag can then modulate `equityAssumption` downward for non-nut draw categories in `buildTree`.

### Trace Serialization — Multi-Street Context

`state.evTreeConfig.evTreeLine` currently serializes each node with its `equity_is_approximated` flag. For multi-street bluff coherence, extend the serialization to include:

- `committed_fraction: node.heroInvestmentAfter / effStack` — allows the trace consumer to evaluate commitment context
- `street_equity_delta: equity_this_street - equity_previous_street` — allows detection of equity-shifting runouts (even when the equity itself is approximated, the delta flags dynamic boards)
- `line_coherence: "value" | "bluff" | "mixed"` — derived from whether the terminal node's `equityAssumption` exceeds 50% (value), falls below 40% (bluff), or is in between (mixed). This is a coarse signal but prevents the worst trace-generation failure (training on bluffs presented as value or vice versa)

The `num_players` gap and `seed_confidence` gap documented in solver-theory-gto.md Implementation Notes (buildContext section) should be resolved in the same serialization pass as these additions to avoid divergent context objects.

### `boardTexture` — Runout Impact Classification

`boardTexture` currently analyzes the flop. For multi-street planning, it should accept a `previousBoard` parameter and return a `delta` object: `{ flushCompleted: boolean, straightCompleted: boolean, paired: boolean, overcard: boolean, brick: boolean }`. This delta drives both equity adjustment and bluff-coherence evaluation at the turn and river nodes.

## "Looks Right But Isn't" Traps

### Trap 1: "Call Flop, Evaluate Turn" at Low SPR

**The trap:** At SPR 3--4, the EV tree shows a positive EV for the flop call node (hero calling villain's c-bet). The user concludes the call is profitable. But the EV is computed assuming hero plays optimally on the turn, which in this SPR range means calling again (because folding is dominated after committing ~30% of stack). The flop call EV is really "flop call + turn call + river call" EV disguised as a single-street decision. If the user *actually* plans to fold the turn on bad cards (a common human tendency), the real EV of their flop call is substantially lower --- often negative. The tree shows the GTO-optimal continuation, not the human's likely continuation.

**Why it's invisible:** The EV number on the flop call node is technically correct given optimal future play. Nothing in the UI signals that "this number assumes you are committed to calling all three streets."

**Detection:** Check whether `heroFoldToRaise` on the turn node following a flop call is >30% when `heroInvestmentAfter / effStack > 0.25`. If so, the tree is allowing a fold that commitment theory says should be near-zero, and the flop call EV is silently inflated.

### Trap 2: Equity Convergence Makes All Turn Decisions Look Marginal

**The trap:** Because ranges narrow across streets and equity converges toward 50%, turn and river nodes in the EV tree all tend to show EVs clustered near zero (slight positive or slight negative). This makes every turn decision look "close" and "marginal." The user or LLM consumer concludes that turn play doesn't matter much --- either action is approximately break-even. In reality, the EV differences on the turn are *amplified* by the pot size: a 2% equity edge on a 15bb turn pot is 0.3bb, but the same 2% edge on a 45bb turn pot (after flop betting) is 0.9bb. The convergence-toward-50% equity obscures the absolute EV differences.

**Why it's invisible:** The `ev` field on turn nodes shows small numbers (0.5--2.0bb) regardless of whether the decision is genuinely marginal or critically important. The user pattern-matches "small EV = doesn't matter" when the correct interpretation is "small equity edge * large pot = meaningful EV."

**Detection:** Normalize EV by pot size at each node: `ev_normalized = node.ev / node.potAfter`. If normalized EVs differ by >0.03 between actions (bet vs. check, call vs. fold), the decision is significant even though the raw EV difference looks small.

### Trap 3: GTO-Seeded Fold Frequencies Are Exploitable in Non-Equilibrium

**The trap:** `buildTree` seeds `villainFoldPct` using the formula `S / (P + 2S)`, which is the GTO-optimal fold frequency. Against a GTO opponent, this is the correct assumption. Against a population that overfolds (which pool data consistently shows: population folds ~5--8% more than GTO on flop and turn c-bets), the seeded frequency understates hero's bluff profitability by ~5--8%. The EV tree suggests a bluff is break-even when it is actually +EV. Conversely, against a population that underfolds on the river (station tendencies increase on final street), the seeded frequency overstates bluff profitability.

**Why it's invisible:** The GTO seed looks correct because it *is* correct at equilibrium. The error is in applying equilibrium assumptions to a non-equilibrium context. The tree produces "GTO-correct, population-wrong" EV outputs that the user interprets as "this bluff breaks even" when the population-adjusted truth is "this bluff prints money" or "this bluff bleeds money."

**Detection:** Not detectable from the tree alone. Requires population fold-frequency data as an external input. If `villainFoldPct` is never manually adjusted above or below GTO seed by the user, the tree output is GTO-only and should be labeled as such in trace exports.

### Trap 4: `computeNodeEV` Check-Node Max Conflates Hero Choice with Mixed Strategies

**The trap:** At line ~1246--1247, the check node returns `Math.max(...childEVs)`. This is correct when all children are hero's choices (hero decides whether to check-behind or bet after villain checks). But in practice, check-node children include both hero-initiative actions (hero bets after villain checks) and villain-initiative actions (villain leads after hero checks). Taking the max across both conflates "hero's best response when villain checks" with "hero's best response when villain bets" into a single maximized value. The correct computation for a check node depends on who acts next: if hero acts, max is correct; if villain acts, frequency-weighting (not max) is correct.

**Why it's invisible:** The EV output is always at least as high as the correct value (max >= weighted average), so the tree never shows a suspiciously low number that would trigger investigation. It simply overstates the check-line EV, making checking look more attractive than it is.

**Detection:** Compare check-node EV against bet-node EV. If the check node EV exceeds the best bet node EV despite hero having a significant equity advantage, the max-over-villain-actions inflation may be the cause.

## Connections to Adjacent Domains

### Bidirectional: Bet Sizing Theory and Pot Geometry

**From Bet Sizing to Multi-Street Planning:** The geometric bet sizing formula `b = ((S_eff/P)^(1/N) - 1) / 2` determines `betSizings` input to `buildTree`. But N (number of remaining streets where villain calls) is itself a multi-street planning output: you need to estimate how many streets villain calls before computing the sizing, but the sizing determines how many streets villain calls. The resolution is iterative: start with N = remaining streets, compute sizing, estimate villain's continuing frequency at that size, reduce N if >20% of villain's range folds before the final street, recompute. This loop is not currently implemented --- `betSizings` is a static input.

**From Multi-Street Planning to Bet Sizing:** The commitment threshold analysis feeds back into bet sizing: at SPR < 4, a single sizing (all-in or near-all-in) is often correct because the geometric sizing would be >75% pot, and the difference between 75% and 100% is negligible at that stack depth. The `betSizings: [0.33, 0.66, 1.0]` default in `buildTree` should be SPR-conditioned: at SPR < 3, collapse to `[1.0]`; at SPR 3--6, use `[0.66, 1.0]`; at SPR > 6, use the full array.

### Bidirectional: Range Construction and Equity Distribution

**From Range Construction to Multi-Street Planning:** The polarity index (from Domain 2) determines bluff-to-value ratio, which is a multi-street planning input. The specific polarity proxy calculation (classifyHand distribution into value/marginal/air buckets, with Two Pair assigned to marginal when boardTexture.wetness >= 3) is defined in range-construction.md Trap 1 and should be used without modification here. A polar range (PI > 0.70) supports large multi-street bets because the range contains mostly nuts and air --- the middle is thin. A merged range (PI < 0.50) supports small single-street bets because the range is concentrated in medium-strength hands that want to see a cheap showdown. The transition from polar to merged across streets (ranges become less polar as draws resolve and medium hands become more prominent) means the optimal sizing decreases from flop to river on most runouts --- contradicting the common heuristic of "bet bigger on later streets."

**From Multi-Street Planning to Range Construction:** Commitment thresholds retroactively constrain preflop range construction. At 100bb, opening 7-6s from the CO is profitable because the implied-odds-rich hand can navigate multi-street play profitably. At 40bb, the same hand loses its multi-street advantage (SPR is too low for the draws to pay off), and the preflop open becomes -EV. The `PRESETS` ranges in RangeIQ are calibrated for 100bb play and become progressively less accurate as effective stacks decrease. A stack-conditioned preset system would narrow preflop ranges at shorter stacks, reflecting the multi-street planning reality that speculative hands need depth.

### Bidirectional: Solver Theory and GTO Equilibrium

**From Solver Theory to Multi-Street Planning:** Solver convergence artifacts (Domain 1: false mixing, oscillating strategies) concentrate on turn and river nodes where ranges are narrow and equity differences are small. A solver that hasn't converged on the river (Domain 1 documents this at <1,000 iterations) produces river frequencies that feed back into turn EV computation, which feeds into flop EV computation. The multi-street amplification of solver noise is multiplicative, not additive: a 5% river frequency error produces a ~2% turn EV error and a ~1% flop EV error, but across a full tree with many branches, these errors don't cancel --- they accumulate in whichever direction the solver was drifting. For `buildTree`, this means GTO-seeded frequencies (which approximate converged solver output) are more reliable on the flop than on later streets, reinforcing the correctness of the `equity_is_approximated` flag's street-based logic.

**From Multi-Street Planning to Solver Theory:** The commitment threshold analysis provides a sanity check on solver outputs. If a solver recommends folding the turn after calling the flop in a spot with SPR < 4, the solver either hasn't converged (the fold frequency should be near-zero) or the flop call was itself a mistake (the solver should have recommended folding the flop). This is a diagnostic tool for identifying premature-stopping artifacts in commercial solver solutions.
