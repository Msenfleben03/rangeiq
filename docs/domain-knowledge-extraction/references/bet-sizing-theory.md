# Bet Sizing Theory and Pot Geometry --- The Operational Layer

## Core Concepts

### Geometric Bet Sizing: The Multi-Street Commitment Formula

The geometric bet sizing formula solves for the single bet fraction `b` that, applied on each of `N` remaining streets, grows the pot from current size `P` to exactly the effective stack `S_eff`:

```
b = ((S_eff / P)^(1/N) - 1) / 2
```

The derivation: each street the pot multiplies by `(1 + 2b)` (hero bets `b * pot`, villain calls). After `N` streets: `P * (1 + 2b)^N = S_eff`. Solving for `b` gives the formula above. For a 6bb pot with 100bb effective stacks and 3 streets remaining: `b = ((100/6)^(1/3) - 1) / 2 = 0.78`, or 78% pot --- larger than the common 66% default in `betSizings: [0.33, 0.66, 1.0]`.

**The critical failure mode --- "commits stacks" vs. "calls all three streets":**

The geometric formula assumes villain *calls on every street*. This is the assumption that breaks most frequently and most silently. The formula computes the sizing that *pot-commits* stacks by the river, but pot commitment is a property of the bet-size trajectory, not of opponent behavior. On K-7-2 rainbow where hero has AA, villain's top pair (K9, KT) calls the flop and turn but folds the river to a third barrel ~60-70% of the time in solver outputs. Three-street geometry prices the flop bet at 78% pot to "get stacks in," but villain only pays off two streets worth. The actual value extraction is:

- **Geometric (3-street):** Flop 78%, turn 78%, river 78%. Villain calls flop and turn, folds river. Hero extracts ~2 streets of value at a sizing calibrated for 3 streets --- the flop and turn bets are *larger than optimal for 2-street extraction* because they were sized to build the pot for a river bet that never gets called.
- **Correct (2-street adjusted):** Flop 50-60%, turn 100-120%. Hero extracts 2 streets at sizings calibrated for the actual number of streets villain pays. Total chips extracted is often higher because the turn sizing can be larger (villain is pot-committed after a flop call at moderate sizing) and the flop sizing does not scare away marginal calls.

The gap between "pot committed by river" and "calls all three streets" is quantifiable. On static boards (K-7-2 rainbow, A-8-3 rainbow) where the board runout rarely changes hand rankings, solver outputs show that the top-pair portion of villain's calling range drops off by 40-60% between turn and river. On dynamic boards (T-9-7 two-tone) where draws complete, the drop-off is lower (20-35%) because villain's draws either got there (and now raise) or missed (and fold regardless of sizing). The geometric formula is most wrong on static boards with a single street of hand-strength-dependent calling.

**Operational threshold:** Apply geometric sizing only when villain's range contains hands that call across all `N` streets --- sets, two-pair+, strong draws. When villain's calling range is capped at one pair (common on dry ace-high and king-high boards), reduce `N` by 1 and recalculate. The practical test: does villain's range contain >20% of combos that call a river bet after calling flop and turn? If not, `N` should be 2, not 3.

### Polarity Index as a Bet Sizing Driver

The mathematical relationship between equity distribution variance and optimal bet size derives from the indifference principle operating at the range level.

A **polarized range** (bimodal equity distribution: many combos at >75% equity and many at <25%, few in between) benefits from large bet sizes because:

1. The value hands want to maximize pot size --- they win at showdown against villain's calling range.
2. The air hands want to maximize fold equity --- larger bets force villain to fold a larger fraction of their range.
3. The *absence* of medium-strength hands means hero never faces the problem of overcommitting marginal holdings.
4. Villain's counter-strategy against large bets requires strong hands to call, but hero's value portion beats those strong hands, and hero's air portion was going to lose anyway. Villain cannot profitably mix against large bets from a polar range because calling with bluff-catchers faces too many value combos, and folding concedes too much to the bluffs.

A **merged range** (clustered equity distribution: most combos between 40-65% equity) benefits from small bet sizes because:

1. Large bets isolate hero against the top of villain's range, and most of hero's hands lose to that top portion.
2. Small bets deny villain's draws equity cheaply --- villain must still fold some draws even to a 25-33% pot bet.
3. Medium-strength hands extract thin value from worse medium-strength hands at small sizings but become bluff-catchers at large sizings.
4. The pot stays small, which matches the equity profile: medium equity in a medium pot generates more EV than medium equity in a large pot (where the variance overwhelms the edge).

**The polarity-sizing formula (approximate):** For a range with polarity index `PI` (ratio of value+air combos to total combos, as computed from `classifyHand` buckets):

- `PI > 0.70`: Use 66-100%+ pot (polar). Value hands and bluffs dominate the range.
- `PI 0.50-0.70`: Use 33-66% pot (transitional). Mix of medium and extreme hands.
- `PI < 0.50`: Use 25-33% pot (merged). Medium-strength hands dominate.

**The individual-hand-strength trap:** The most common sizing error --- by humans and LLM-generated traces --- is choosing bet size based on the *specific hand held* rather than the *range composition*. "I have the nuts, so I should bet large" is wrong when the range is merged. If hero bets large only with the nuts and small/checks with everything else, villain reconstructs hero's holding from the sizing. The correct reasoning: "My *range* is polar on this board, so I use a large sizing with my entire betting range, which includes both the nuts and my bluffs." The sizing is a property of the range, not the hand. Individual hand selection (which hands go into the betting range vs. the checking range) happens at the range level; once the betting range is constructed, all hands in it use the same sizing.

This connects directly to the deterministic-mixing anti-pattern from the Solver Theory domain. Choosing sizings by hand strength is the sizing-domain equivalent of choosing frequencies by hand strength --- both reveal information that should remain hidden.

### Board Texture Inversions for Bet Sizing

Standard heuristics map "wet board = small bet" and "dry board = large bet." These are correct ~65% of the time but invert on specific board categories.

**Inversion 1: Paired boards where "wet board = small bet" is wrong.**

On 8-8-5 two-tone, `boardTexture` returns `wetness = 2` (fdScore=2, sdScore=0, pairedScore=-2) --- dry. The standard heuristic says "dry board, bet large." But the *range* interaction tells a different story. Both ranges on a paired board are merged toward medium-strength holdings: anyone with an 8 has trips (strong but vulnerable), anyone without an 8 has an underpair or overcards (medium). Sets and full houses are rare (few combos). The equity distribution is clustered, not bimodal. Solver output: bet small (25-33% pot) at high frequency. The wetness score's `-2` paired adjustment correctly reduces the wetness number, but the strategic implication (small sizing due to merged ranges) is the *opposite* of what "dry = large" predicts.

The deeper issue: `boardTexture.wetness` measures draw density (how many draws exist). Bet sizing is driven by range polarity (how the equity distribution is shaped). These are correlated but not identical. Paired boards have low draw density (dry) but also low range polarity (merged), and the polarity drives the sizing.

**Inversion 2: Monotone boards where the flush-draw holder bets large.**

On 7-4-2 all spades, `wetness = 4` (fdScore=4, sdScore=0, pairedScore=0) --- medium-wet. "Wet = small bet" would suggest 33% pot. But the preflop raiser's range contains concentrated nut flush draws (AXs of spades) plus overpairs, while the caller's range has diluted flush draws (many small suited spade hands) plus underpairs. The raiser's range is *polar* on this board: overpairs (~80% equity) and nut flush draws (~55% equity, but polarized between nut-draw and air) versus complete air (KQo-type hands with ~25% equity). Solver output: bet large (66-100% pot) to deny equity from the many draws in villain's range and to leverage the nut advantage.

The inversion: the range with the best flush draws bets large *into* the flush draw-heavy board, specifically to deny equity from inferior flush draws. Small bets allow villain to realize draw equity cheaply. Large bets force villain to pay a price that exceeds the expected value of their draws.

**Inversion 3: Low-card boards that favor the preflop aggressor.**

On 5-3-2 rainbow, `wetness = 2` (fdScore=0, sdScore=2, pairedScore=0) --- dry. Standard heuristic: "dry low board, ranges miss, small bet." But the preflop raiser's range has overpairs (AA-66 all have ~85% equity) while the caller's range is dominated by overcards (KQ, KJ, QJ with ~25% equity) and some pairs (44, A5s, A3s with ~50%). The raiser's range is highly polar: many overpairs clustered at 85%+ and many air hands (suited broadways) at 25%. Solver output: bet large (66-75% pot) at high frequency.

The heuristic "low cards = fewer draws = small bet" fails because it confuses board draw density with range polarity. Low boards create *more* range polarity for the preflop aggressor (overpairs vs. air), not less.

**The wetness score as necessary-but-not-sufficient input:**

`boardTexture.wetness` captures draw density, which is one axis of the sizing decision. The other axis --- range polarity conditioned on the board --- requires the `classifyHand` distribution across the range (the polarity proxy from the Range Construction domain). Bet sizing decisions that rely on wetness alone will be wrong on the three inversion categories above. The operational path: use wetness as a draw-density signal (determines how much equity denial matters), and use the polarity proxy (from `classifyHand` buckets) as a range-shape signal (determines whether the range supports a large or small sizing). When these two signals disagree --- high wetness but polar range (monotone boards), low wetness but merged range (paired boards) --- polarity should override wetness for sizing selection.

### Overbet Theory: Range Asymmetry Conditions

Overbets (>100% pot) are not aggression tools. They are precision instruments for exploiting specific range asymmetries where one player's range can contain the nuts and the other's cannot.

**Condition 1: Range cap asymmetry.**

When villain's preflop action caps their range --- they flatted a 3-bet (capping at ~QQ/JJ, no AA/KK/AK), or they called from the blinds (capping below 4-bet value range) --- and the board develops in a way that hero's range contains nut combinations villain cannot hold, overbets become correct.

Example: Hero 3-bets from the BTN, villain calls from the BB. Villain's range is capped below AA/KK (those would have 4-bet). Board runs out A-K-7-2. Hero has all AA, KK, AK combinations. Villain has zero of them. Hero's range contains the nuts; villain's range is capped at QQ/JJ/TT and underpairs. The overbet (125-200% pot) is correct because villain's best hands (QQ) have ~5% equity and must fold at any sizing, while villain's bluff-catchers (middle pairs, draws) face the same fold-or-call decision regardless of sizing. The overbet extracts maximum value from villain's few calling hands (77 for a set, A7s/A2s for two-pair) while maximizing fold equity from the rest.

**Condition 2: Blocker-driven range asymmetry.**

When hero holds specific cards that block villain's strongest calling hands. Holding Ah on an Ah-Ks-7d-3c board: hero blocks villain's top pair top kicker (AK, AQ, AJ all need an Ace that hero holds). Villain's calling range is reduced by ~25-35% because the Ace removes key combinations. This creates a range asymmetry where hero knows villain is disproportionately weak, enabling an overbet that extracts maximum value from the remaining calling range.

**Condition 3: Turn/river card that completes hero's range and misses villain's.**

The river card completes a flush that hero's preflop raising range contains (suited broadways) but villain's flatting range has fewer of (villain flat-called with offsuit hands, pairs). The range asymmetry is card-specific, not general.

**The aggression-substitution failure mode:**

Using overbets as general aggression ("I want to put pressure") without confirming range asymmetry conditions. On A-K-7-2 after a single raise (not a 3-bet), *both* players can have AA, KK, AK. No range cap exists. Overbetting here does not exploit asymmetry --- it overcommits hero's medium-strength hands (QQ, JJ) as bluffs against a range that can have the nuts. Solver outputs show overbet frequency near 0% in pots where both ranges are uncapped.

**`buildTree` constraint:** The current `betSizings: [0.33, 0.66, 1.0]` caps bet sizes at 1.0 (100% pot). Overbets require values >1.0 in the `betSizings` array --- e.g., `[0.33, 0.66, 1.0, 1.5, 2.0]`. The architectural change is minimal: `buildTree` already accepts arbitrary sizing values, and the node construction logic (`const S = s * potSize`) handles overbets without modification. The constraint `if (S > effStack - heroInvestment) return` (line 1127) correctly filters sizings that exceed remaining stacks. The changes needed:

1. Add overbet values to `betSizings` in `evTreeConfig` (state change, line 455).
2. Update the bet sizings input UI (line 1539) to accept values >1.0.
3. Adjust GTO seeding: the formula `foldPct = S / (P + 2S)` remains correct for overbets --- at 150% pot, `foldPct = 1.5P / (P + 3P) = 37.5%`, meaning villain must defend 62.5% to prevent exploitation. This is mathematically valid but practically wrong for overbets on capped boards --- when villain's range is capped, their actual fold frequency is much higher than MDF because they lack the strong hands needed to continue. The GTO seed overstates villain's defense frequency for overbets on capped boards, which understates the overbet's EV.

### SPR Thresholds and Bet Sizing Strategy

SPR (Stack-to-Pot Ratio) creates qualitative strategy shifts, not just quantitative scaling. The thresholds are not arbitrary --- they correspond to how many streets of betting the remaining stacks can support at reasonable sizings.

**SPR < 2 (commit-or-fold):**

Stacks are less than 2x the pot. A single bet of ~80% pot commits the remaining stacks. Strategy collapses to: bet/fold (commit with strong hands, fold to aggression) or bet/call (commit and accept the gamble). Mixed strategies, multi-street planning, and draw equity calculations are irrelevant --- there is one decision point. The `buildTree` output at SPR < 2 produces a tree with depth effectively 1 (the first bet commits stacks, so `heroInvestment >= effStack` triggers on the first sizing). The correct `betSizings` at this SPR: `[1.0]` or all-in. Multiple sizings waste tree complexity on distinctions that do not matter when stacks are already committed.

This SPR is common in 3-bet and 4-bet pots. A 4-bet pot with 45bb effective stacks and a pot of 30bb has SPR = 1.5. Loading the default `betSizings: [0.33, 0.66, 1.0]` generates meaningless tree branches --- a 33% pot bet (10bb) leaves 5bb behind, which is an awkward non-committed stack that every solver resolves as "just shove."

**SPR 2--6 (one-committed-street):**

One bet and a call commits or nearly commits the stacks. Strategy has two decision points: the initial bet/check, and the response to aggression. The geometric formula with `N = 1` gives the correct single-street sizing: `b = (S_eff / P - 1) / 2`. At SPR 4 (common in 3-bet pots): `b = (4 - 1) / 2 = 1.5`, suggesting a 150% pot overbet. This is the SPR range where overbets are most natural --- they accomplish the geometric goal in one street without needing multi-street planning.

**SPR 6--15 (standard multi-street):**

This is the normal post-flop play zone. Two to three streets of betting are available. The geometric formula with `N = 2` or `N = 3` produces useful sizing guidance. All three default `betSizings` are relevant. This is where `buildTree` produces the most strategically meaningful output.

**SPR > 15 (implied-odds dominant):**

Deep stacks relative to the pot. Implied odds dominate: hands that can make the nuts (sets, flushes, straights) gain value because the remaining stacks allow large payoffs when they hit. Speculative hands (suited connectors, small pocket pairs) increase in value. The geometric formula with `N = 3` and SPR 20 gives `b = ((20)^(1/3) - 1) / 2 = 0.86`, or 86% pot per street. But at this SPR, the geometric formula is unreliable because villain's calling range varies dramatically street to street --- deep stacks allow villain to float and outmaneuver on later streets, breaking the "calls all streets" assumption.

**The single-raise-to-3-bet sizing error:**

The most common SPR-related implementation failure is applying single-raised pot bet sizing logic to 3-bet pots. In a single-raised pot (open 2.5bb, call from BB), the pot is ~6bb with ~97.5bb stacks remaining: SPR ~16. In a 3-bet pot (open 2.5bb, 3-bet to 8bb, call), the pot is ~17bb with ~92bb stacks remaining: SPR ~5.4. The SPR drop from 16 to 5.4 shifts the entire strategic framework from "three streets of maneuvering" to "one committed street." Using the same `betSizings` for both situations produces meaningless EV trees for the 3-bet pot.

**Operational path:** `buildTree` receives `potSize` and `effStack`, from which SPR is trivially computed (`effStack / potSize`). Conditioning `betSizings` on SPR:

- SPR < 2: `[1.0]` (all-in only)
- SPR 2-6: `[0.5, 0.75, 1.0, 1.5]` (include overbets, skip tiny sizings)
- SPR 6-15: `[0.33, 0.66, 1.0]` (current default, correct for this range)
- SPR > 15: `[0.25, 0.33, 0.66, 1.0]` (add small sizing for probing bets)

This SPR-conditional sizing selection is not currently implemented. The user manually specifies `betSizings` regardless of SPR.

### The Donk Bet Paradox

GTO solvers assign donk bets (OOP non-aggressor leading into the preflop raiser) at low frequency: 3-8% of the time on most boards. This low frequency reflects the equilibrium fact that the preflop raiser has range advantage and nut advantage on most board textures, making it unprofitable for the caller to lead into a stronger range.

However, solver-derived donk bet frequencies are among the least practiced counter-strategies in the player pool. Facing a donk bet, most players in the NL25-NL500 pool respond with:

1. **Over-folding** (~55-65% fold frequency vs. GTO ~35-45%): Players interpret the unusual line as strength and fold too much.
2. **Under-raising** (~5-8% raise frequency vs. GTO ~15-20%): Players are unsure how to respond and default to calling or folding.
3. **Flat-calling with nutted hands** (slowplaying sets/two-pair instead of raising): The non-standard line disrupts prepared strategies, causing suboptimal responses.

The boards where donk betting is most exploitable against this population response:

**Paired boards (7-7-3, 5-5-2):** The preflop caller's range contains more 7x and 5x hands than the raiser's range. The caller has range advantage and sometimes nut advantage (trips) on these boards. The solver-approved donk bet frequency is ~8-15% here (already higher than the 3-8% average), but exploitatively it can rise to 25-35% against opponents who fold too much and call too passively when they do continue.

**Low connected boards (5-4-3, 6-5-3):** The BB caller's range hits these boards harder than the EP/MP raiser's range. Two-pair, sets, and made straights are disproportionately in the caller's range. The raiser's overpairs are vulnerable but unlikely to fold to a small donk bet, creating an ideal thin value spot.

**Boards where the preflop aggressor's range whiffs (8-3-2 rainbow):** The raiser's range is almost entirely overcards (AK, AQ, KQ). A donk bet from the caller forces the raiser to continue with air or fold. Since the raiser has so much air, the donk bet extracts fold equity from hands that would have c-bet and folded to a check-raise anyway --- but the donk bet does it for a cheaper price (33% pot donk vs. a check-raise costing 2-3x more).

**Trace generation implications:** Solver training data underrepresents donk bet spots because (a) solvers assign them low frequency, producing few training examples, and (b) the donk bet's profitability is largely exploitative (derives from population response patterns), which GTO traces cannot capture. Traces that include donk betting at exploitative frequencies without labeling them as exploitative contaminate the GTO training signal. Traces that omit donk betting entirely miss a strategically important line. The correct approach for trace quality: include donk bet traces at solver frequency with explicit labeling that the frequency is exploitable higher against populations that under-adjust, and flag the board textures where the exploitation gap is largest.

---

## Failure Modes and Anti-Patterns

### 1. Geometric Sizing on Boards Where Villain Calls Fewer Streets Than N (Severity: Critical)

**Trigger:** User sets `betSizings` using the geometric formula for 3 streets on a static board (A-8-3 rainbow, K-7-2 rainbow) where villain's top-pair range pays off only 2 streets.

**What it looks like:** The flop bet is 75-80% pot (geometric for 3 streets). Villain calls with top pair. The turn bet is 75-80% pot. Villain folds top pair ~60% of the time. Hero extracted less total value than they would have with a 50% flop / 100% turn sizing, because the large flop sizing eliminated marginal callers that would have called a smaller bet and then paid off a larger turn bet.

**Detection:** Compare the product of villain's street-by-street calling probability against the geometric assumption. If `call_flop * call_turn * call_river < 0.3` for villain's bluff-catcher range, the geometric formula overcounts streets. Currently no automated detection in RangeIQ --- this requires per-street range analysis that `buildTree`'s static equity cannot provide. The `equity_is_approximated` flag is a necessary warning; extending it with a `street_payoff_depth` estimate (how many streets villain's median calling hand continues) would enable automated geometric correction.

### 2. Polarity-Sizing Mismatch from Hand-Level Reasoning (Severity: Critical)

**Trigger:** Trace generates reasoning like "we have the nuts, so we bet large" or "we have a weak hand, so we bet small" --- choosing sizing by hand strength rather than range polarity.

**What it looks like:** The trace appears sophisticated. The sizing is sometimes correct by coincidence (the nuts on a polar board should bet large). But the *reasoning* is wrong: sizing is a range property, not a hand property. The trace teaches the LLM to vary sizing by hand strength, creating exploitable sizing tells (large bet = strong, small bet = weak).

**Detection:** Search generated traces for sizing reasoning that references the specific hand held rather than the range distribution. Phrases: "with our strong hand," "since we only have a draw," "our hand is too weak for a large bet." Correct reasoning references "our range is polarized on this board" or "our range is merged, favoring a small sizing with our entire betting range."

### 3. SPR-Blind Bet Sizing (Severity: High)

**Trigger:** Using `betSizings: [0.33, 0.66, 1.0]` in a 3-bet pot where SPR is 4-5. The 33% pot bet is meaningless (commits ~8% of remaining stack, accomplishing nothing strategically) and the 66% pot bet puts hero in an awkward stack-to-bet ratio on the turn.

**What it looks like:** The EV tree has three bet sizing branches that are all strategically equivalent (all commit stacks within one more bet), but the tree treats them as producing different strategic outcomes. The `computeNodeEV` weights each by different villain response frequencies, creating a false granularity that does not exist at low SPR.

**Detection:** Compute `SPR = effStack / potSize` before building the tree. If SPR < 3 and `betSizings` includes values below 0.5, flag as misspecified. If SPR < 2 and `betSizings` includes more than one value, flag as unnecessary complexity.

### 4. Overbet at 100% Pot Cap (Severity: High)

**Trigger:** `betSizings` maxes at 1.0 (100% pot). On boards with clear range cap asymmetry (3-bet pots, 4-bet pots where one player's range is capped), the optimal sizing is 125-200% pot. Capping at 100% leaves 15-40% EV on the table in capped-range spots.

**What it looks like:** The EV tree's maximum bet node shows positive EV. But the EV of an overbet node (not present in the tree) would be higher, sometimes by 30-50%. The tree appears to have found the best action, but it searched a restricted action space.

**Detection:** When the board + preflop action creates a clear range cap (villain flatted a 3-bet or 4-bet), and `max(betSizings) <= 1.0`, flag that overbet nodes are missing. The range cap condition is: villain's action preflop (call, not raise) removes the top of their range. Currently, RangeIQ does not track the preflop action sequence --- only the resulting range is loaded. Adding a `villain_preflop_action` field to trace context would enable this detection.

### 5. Wetness-Driven Sizing Without Polarity Check (Severity: Medium)

**Trigger:** Using `boardTexture.wetness` as the sole sizing driver. "Wetness 6 = wet = small bet." On boards where wetness is high but range polarity is also high (monotone boards), this produces the wrong sizing.

**What it looks like:** Small bet on a monotone board where solver output recommends large bet. The trace says "wet board, so we use a small sizing to deny equity cheaply." The reasoning has the right concept (deny equity) but the wrong application (denying equity on a monotone board requires large bets because villain's draws have ~35-45% equity, and a small bet gives them better-than-breakeven odds to continue).

**Detection:** Cross-check `boardTexture.wetness` against the polarity proxy from `classifyHand` distribution. When wetness > 4 but polarity index > 0.65, the sizing recommendation should follow polarity (large), not wetness (small).

### 6. Donk Bet Frequency Treated as Pure-GTO (Severity: Medium)

**Trigger:** Trace includes donk bets at population-exploitative frequencies (20-30%) but frames them as GTO-optimal.

**What it looks like:** "The GTO play here is to lead 25% pot." Solver frequency for this spot is 5-8%. The 25% frequency is profitable against the population but is not equilibrium. Training an LLM on traces that call exploitative frequencies "GTO" creates a model that blends the frameworks without distinction.

**Detection:** Donk bet frequencies in traces should be compared against solver baselines for the board class. Frequencies >12% should be flagged for review as potentially exploitative.

---

## Implementation Notes

### `buildTree` Bet Sizing Extensions

**Current state (line 1125-1196):** `betSizings` from `evTreeConfig.betSizings` (default `[0.33, 0.66, 1.0]`) drives all hero bet nodes. The `forEach` loop constructs one tree branch per sizing. The constraint `if (S > effStack - heroInvestment) return` correctly prunes sizings that exceed remaining stacks.

**Overbet support:** No code changes needed in `buildTree` itself. The function already handles arbitrary sizing values. Changes required:

1. `evTreeConfig.betSizings` (line 455): change default or allow user to add values >1.0.
2. GTO seeding (line 1130): `foldPct = S / (P + 2S) * 100` remains mathematically valid for overbets but produces MDF-based seeds that underestimate actual fold frequency on capped boards. A `villain_range_capped` boolean flag on the tree or node level could adjust the seed: when capped, multiply `foldPct` by 1.3-1.5 as a heuristic correction (actual correction is board-specific and requires solver data, but 30-50% upward adjustment approximates solver outputs for common capped spots).

**SPR-conditional sizings:** Compute `const spr = effStack / potSize` before calling `buildTree`. Use the SPR thresholds (< 2, 2-6, 6-15, > 15) to either auto-select `betSizings` or validate user-specified ones with a warning. This logic belongs in the Module 3 component (line 1478 where `buildTree` is called), not in `buildTree` itself.

### Geometric Sizing Computation

Not currently implemented. A utility function:

```js
function geometricSizing(potSize, effStack, streets) {
  return (Math.pow(effStack / potSize, 1 / streets) - 1) / 2;
}
```

This returns a fraction of pot (e.g., 0.78 for 78% pot). It could be displayed in Module 3's `BreakevenPanel` alongside the current BE%/GTO metrics, as "Geometric sizing for N streets." The `streets` parameter should default to the number of streets remaining from the current node's `street` field (flop=3, turn=2, river=1).

### Polarity-Aware Sizing Recommendation

The polarity proxy from the Range Construction domain (`classifyHand` distribution into value/marginal/air buckets) is the input. The sizing recommendation is the output:

1. Run `classifyHand` across all hero combos on the current board (already done in Module 2's range breakdown chart).
2. Compute polarity index: `PI = (value_count + air_count) / total_combos`. Note: Two Pair combos must be assigned to value bucket when `boardTexture.wetness < 3` and to marginal bucket when `boardTexture.wetness >= 3` before computing PI — see range-construction.md Trap 1 for the board-texture-conditioned bucket assignment rule.
3. Map PI to sizing recommendation: PI > 0.70 = large (66-100%), PI 0.50-0.70 = medium (33-66%), PI < 0.50 = small (25-33%).
4. Cross-check against `boardTexture.wetness` for inversion detection (paired boards, monotone boards).
5. Store recommendation in `metrics` and include in Module 4's `buildContext`.

**State field:** `metrics.pi` (line 445) is declared but null. Populating `metrics.pi.hero` with `{ value_pct, marginal_pct, air_pct, polarity_proxy, sizing_recommendation }` enables both the UI display and trace context.

### `computeNodeEV` and Sizing Sensitivity

**Current behavior (line 1201-1265):** EV computation uses `villainFoldPct / 100`, `villainCallPct / 100`, and `villainRaisePct / 100` as weights. These are GTO-seeded from the sizing formula and then user-editable via `UPDATE_EV_NODE_FREQ`.

**The sizing sensitivity gap:** The EV of different sizing branches should be *compared* to identify the optimal sizing. Currently, the user eyeballs the EV of each bet node. Implementing `optimalSizing = betNodes.reduce((best, n) => n.ev > best.ev ? n : best)` in the Module 3 UI would highlight the highest-EV sizing. This is a display change, not a computation change --- the data is already in `nodes`.

### Donk Bet Nodes in `buildTree`

**Current behavior (lines 1074-1112):** `buildTree` already generates villain-bet (donk) nodes under the check node at each sizing in `betSizings`. The GTO seeding for donk bets uses pot odds to derive `heroFoldToRaise` (line 1078: `foldPct = (1 - heroPotOdds) * 100`), which determines hero's response. The donk bet's frequency is implicitly controlled by the check node's child selection logic in `computeNodeEV` (line 1244-1248: `Math.max(...childEVs)` picks the highest-EV child of the check node, which is typically hero betting, not villain donking).

**The gap:** `computeNodeEV` for check nodes takes the `max` of children, which assumes hero chooses the highest-EV option. But when hero checks, it is *villain* who decides whether to check behind or donk bet. The `max` operator is wrong for children where villain acts --- it should weight by villain's action frequency. Currently, the villain_bet nodes exist in the tree but their EV is only selected if it exceeds the check-behind EV, which conflates hero's decision (check vs. bet) with villain's decision (donk vs. check behind). Additionally, the villain raise frequency input to all EV sizing comparisons uses the hardcoded `raisePct = 10` across all board textures — the systematic bias this introduces (undercounting raises on wet boards, overcounting on dry) is documented in range-construction.md Trap 3 and solver-theory-gto.md Implementation Notes; any sizing sensitivity analysis in the EV tree inherits this distortion.

### `boardTexture` Output and Sizing Decisions

**Current state (lines 402-433):** Returns `{ flushTexture, isPaired, connectivity, wetness }`. No direct sizing signal.

**Extension for sizing:** Add `rangePolarityHint` derived from board properties:

- `isPaired && wetness < 4`: "merged" (both ranges cluster around medium-strength)
- `flushTexture === "Monotone"`: "polar_if_raiser" (raiser's range is polar; caller's is merged toward draws)
- `connectivity >= 2 && !isPaired`: "dynamic" (equity distributions shift dramatically on turn/river)
- Default: derive from wetness (wetness > 4 = "wet_merged", wetness < 3 = "dry_polar")

This hint would flow into Module 4's trace context as `board_sizing_profile`, giving the LLM an additional signal for sizing reasoning.

---

## "Looks Right But Isn't" Traps

### Trap 1: Geometric Sizing That Extracts Less Than Non-Geometric

On K-7-2 rainbow (SPR 16), the geometric formula for 3 streets gives `b = 0.78`. Hero bets 78% pot on flop, 78% on turn, 78% on river. This *looks* optimal because it "gets stacks in." But solver outputs for this exact board show the optimal line is: flop 33% pot (small, to keep villain's entire top-pair range calling), turn 75% pot (larger, villain is now pot-committed with top pair), river 125-150% pot (overbet, villain calls with top pair because pot odds after two streets of investment make folding -EV). Total chips extracted: ~80bb over 3 streets. The geometric line at 78/78/78: villain folds top pair on the turn ~45% of the time (the sizing is too large for a hand that's "just top pair" on a static board), extracting ~55bb over 2.5 streets.

**Why it looks right:** The geometric formula is mathematically elegant and "gets stacks in by the river." The sizing appears aggressive and purposeful. The EV tree built with 78% bet sizes shows positive EV at every node.

**Why it's wrong:** The formula assumes villain's calling range is static across streets. On static boards, villain's *hand strength* is static, but their *willingness to continue* is not. Top pair on the flop is a comfortable call. Top pair on the turn facing a second 78% bet starts to look like a marginal bluff-catcher. The solver's escalating line (small-medium-large) exploits the psychology and pot-odds dynamics of multi-street play; the geometric line ignores them.

### Trap 2: "Wet Board = Small Bet" on Monotone Ace-High

Board: A-8-4 all hearts. `boardTexture` returns `wetness = 4` (fdScore=4, sdScore=0, pairedScore=0). "Medium-wet, bet small to deny equity."

Hero (UTG RFI range) has: AA (2 combos with hearts), AKhh/AQhh (nut flush draws), KK/QQ/JJ (overpairs without hearts), plus missed hands. Hero's range is highly polar: overpairs and nut flush draws at 65-85% equity, missed hands at 15-25% equity. Villain (BB defense) has: many heart draws (any two hearts), Ax hands (top pair), 88/44 (sets). Villain's range is continuous: sets at 85%, top pair at 55-65%, flush draws at 40-50%, air at 20%.

The solver output: hero bets 66-75% pot at ~60% frequency. The large sizing is correct because (a) hero's range is polar, (b) villain's flush draws have 35-45% equity and get breakeven-or-better odds against a 33% pot bet, and (c) hero's overpairs need to charge draws the maximum price.

**Why it looks right:** "Wet board, small bet" is one of the most repeated heuristics in poker education. The wetness score confirms the board is moderately wet. Small bets "protect our range" and "keep villain's range wide."

**Why it's wrong:** The heuristic confuses the goal. On this board, hero *wants* villain's range narrow --- specifically, wants to fold out the mediocre flush draws (8h5h, 6h3h) that have 35% equity but can't call a large bet. Keeping villain's range wide (via a small bet) allows them to realize their draw equity cheaply, which costs hero EV. The polarity of hero's range --- lots of hands that want a big pot (overpairs, nut flush draws) and lots that don't care (air) --- supports the large sizing.

### Trap 3: SPR-Correct Sizing in a Tree Built for the Wrong SPR

A 3-bet pot: hero opens 2.5bb, villain 3-bets to 8bb, hero calls. Pot is ~17bb. Effective stacks are 92bb remaining. SPR = 5.4. The user correctly recognizes this is a low-SPR spot and sets `betSizings: [0.5, 0.75, 1.0]`. `buildTree` generates the tree. `computeNodeEV` computes EVs. Everything looks correct.

The trap: `buildTree` uses `depth = 0` starting from the flop and recurses up to `depth >= 3`. At SPR 5.4 with a 75% pot bet on the flop (12.75bb), the pot becomes ~42.5bb with ~79.25bb remaining. SPR on the turn is now 79.25/42.5 = 1.86. The tree correctly generates turn nodes, but the *turn bet sizings* are the same `[0.5, 0.75, 1.0]` used on the flop. At SPR 1.86, the only strategically meaningful turn sizing is all-in. The tree generates three turn sizing branches that all effectively commit stacks (0.5 * 42.5 = 21.25bb, leaving 58bb behind in a 85bb pot --- effectively committed), creating three nodes with nearly identical EV but different displayed sizings.

**Why it looks right:** The tree has realistic-looking turn and river branches. EVs are computed. Sizings are displayed. Nothing flags as an error.

**Why it's wrong:** The tree branches consume UI space and cognitive load without providing strategic information. Worse, if the user edits villain's response frequencies differently across the three nearly-identical turn sizing branches, the EV differences create a false impression of sizing sensitivity that does not exist at this SPR. The fix: `buildTree` should receive per-street `betSizings` or compute SPR at each recursive call and adjust sizings accordingly --- `if (effStack - heroInvestment) / potSize < 2, betSizings = [1.0]` as a tree-pruning rule.

### Trap 4: MDF-Seeded Fold Frequency for Overbets on Uncapped Boards

If a user adds `1.5` to `betSizings`, the GTO seed produces `foldPct = 1.5P / (P + 3P) = 37.5%`. This means villain "should" fold 37.5% to a 150% pot overbet. On a board where villain's range is capped (they flatted a 3-bet, cannot have the nuts), this might even *understimate* villain's fold frequency --- they fold 50%+ because they lack hands strong enough to call. The EV tree correctly shows the overbet as profitable.

But on an uncapped board (single-raised pot, villain has full range including AA/KK/sets), the 37.5% fold frequency is too high. Villain's range contains enough nutted hands that their actual fold frequency is 15-25%. The EV tree shows the overbet as profitable based on the 37.5% seed, but the real EV is negative because villain calls (and wins) far more often than the seed assumes.

**Why it looks right:** The MDF formula is correct. The math checks out. The node shows positive EV. The user sees "overbet = +EV" and generates a trace recommending overbets on uncapped boards.

**Why it's wrong:** MDF-derived seeds assume villain defends at the mathematically minimal frequency. On uncapped boards facing overbets, villain defends *above* MDF because their range contains hands too strong to fold. The MDF seed is a floor, not a ceiling, for villain's calling frequency --- and on uncapped boards, the actual frequency is well above the floor. The trace teaches the LLM that overbets are profitable on any board, when they are only profitable on boards with range asymmetry.

---

## Connections to Adjacent Domains

### Range Construction and Equity Distribution (bidirectional)

**From Bet Sizing to Range Construction:** The polarity index --- the key input to sizing decisions --- is computed from range composition on a specific board. The `classifyHand` distribution (value/marginal/air buckets) from the Range Construction domain is the data source for sizing recommendations. Without the polarity proxy, sizing decisions fall back on board texture alone, which produces the inversion errors documented above.

**From Range Construction to Bet Sizing:** Range construction decisions (which hands are in the preflop range) determine postflop polarity. The A5s-over-A8s EP construction decision (documented in range-construction.md) affects postflop polarity on specific boards: on 5-4-3, A5s makes the nut straight, shifting hero's equity distribution toward bimodal (strong hands + air), increasing polarity and justifying larger sizings. A8s on the same board is air, which also increases polarity but in the wrong direction --- more air without more value hands does not increase the polarity index because the air bucket grows without a corresponding value bucket. The range construction choices upstream directly constrain which bet sizings are available downstream.

The `histogram: null` field in `runMonteCarlo` (documented in range-construction.md as the key implementation gap) is the bridge between these domains. Once per-combo equity tracking is implemented, polarity index flows naturally into sizing recommendations without relying on the `classifyHand` proxy. The priority of implementing the equity histogram is higher for bet sizing accuracy than for range analysis, because sizing decisions amplify small errors across the entire pot.

### Solver Theory and GTO Equilibrium (bidirectional)

**From Bet Sizing to Solver Theory:** Bet size bucketing in commercial solvers (documented in solver-theory-gto.md under "Bet-size bucketing distortions") directly affects the sizing recommendations that flow into RangeIQ. The geometric sizing of 78% pot for a specific board may fall between the 66% and 100% solver buckets, producing a strategy that is correct for neither sizing. When RangeIQ's `betSizings` array uses solver-standard buckets (33%, 66%, 100%), the tree output is compatible with solver data for those buckets. Adding non-standard sizings (45%, 78%, 120%) produces trees with no solver reference point for validation, creating an unfalsifiable output that "looks reasonable" but cannot be checked against ground truth.

**From Solver Theory to Bet Sizing:** The GTO seeding formulas in `buildTree` (MDF-derived fold frequencies) produce bet sizing EVs that reflect equilibrium defense, not actual defense. Solver theory provides the understanding that these seeds are *floor* estimates of villain's defense frequency. On boards where villain's range is strong relative to the sizing (ace-high boards where villain has many strong Ax hands), actual defense exceeds MDF by 10-20 percentage points. On boards where villain's range is weak (low disconnected boards where villain has mostly overcards), actual defense is near or below MDF. The systematic bias in MDF seeds is board-texture-dependent, and correcting it requires the board texture classification from `boardTexture` combined with range composition analysis from the Range Construction domain. The three domains --- Solver Theory (what the seed represents), Range Construction (what villain's actual range contains), and Bet Sizing (what the correct sizing is given the above) --- form a dependency chain where errors in any one propagate through the others.
