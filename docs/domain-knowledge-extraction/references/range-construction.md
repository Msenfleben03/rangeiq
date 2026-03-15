# Range Construction and Equity Distribution --- The Operational Layer

## Core Concepts

### Equity Distribution Shape vs. Aggregate Equity

Two ranges with 52% aggregate equity against each other on the same board can require completely different strategies. The driver is the *variance* of per-combo equity across the range, not the mean.

Consider Hero holding a UTG RFI range on K-7-2 rainbow. The range contains AA-TT (overpairs, ~80-95% equity each), AK (top pair top kicker, ~75%), then a cliff to suited connectors like 98s-76s (~25-35% equity). The equity *distribution* is bimodal: a cluster of strong hands near 80%+ and a cluster of weak hands near 30%. Meanwhile, a CO RFI range on J-T-8 two-tone has equity distributed more continuously: sets and two-pair at 70-80%, top pair hands at 55-65%, flush draws at 45-55%, pair+draw combos at 40-50%. Both ranges might average 52% equity against a BB defense range, but the first demands large bet sizes (the bimodal distribution means strong hands want to build the pot and weak hands want maximum fold equity), while the second demands small bet sizes (the continuous distribution means most hands have similar EV from betting and checking, and large bets isolate you against the top of villain's range).

**The polarity index** measures this distribution shape. It is commonly described as "how polarized the range is," but operationally it measures the *bimodality coefficient* of the equity distribution --- the degree to which the range clusters at the extremes (>75% and <25% equity) versus the middle. A polarity index of 0.8 means the range is heavily bimodal; 0.3 means it is continuous/merged.

**Approximating polarity from `classifyHand` output:** The `classifyHand` function returns `{ category, strength, draws }` for each combo. Group the categories into three buckets: (1) value = {Straight Flush, Quads, Full House, Flush, Straight, Three of a Kind, Overpair, Top Pair (Good Kicker)}, (2) marginal = {Top Pair (Weak Kicker), Middle Pair, Two Pair}, (3) air = {Bottom Pair, Underpair, Pair, Ace High, No Made Hand}. The polarity proxy is `(value_combos + air_combos) / total_combos`. When this ratio exceeds ~0.70, the range is polar enough to support large bet sizes. When it falls below ~0.50, the range is merged and large bets self-exploit. Two Pair lands in "marginal" because on most boards it is too strong to fold but too weak to stack off against value-heavy betting ranges --- it behaves like a bluff-catcher, not a value hand, which is the non-obvious classification that most heuristic implementations get wrong.

**What `runMonteCarlo` destroys:** The function returns `heroEq` (aggregate), which is the mean of the per-combo equity distribution. The distribution shape --- the actual strategic driver --- is collapsed into a single number. The `histogram: null` field (line 390) is a deferred feature that would bucket hero combos by win percentage into 10% bands. Implementing this histogram would recover the distribution shape and enable polarity index computation directly from Monte Carlo output rather than the `classifyHand` proxy.

### Nut Advantage Diverging from Range Advantage

Nut advantage and range advantage (equity advantage) are treated as correlated metrics. They usually are. The cases where they diverge are the strategically critical spots.

**The specific board pattern:** Monotone or two-tone boards with one high card and two low cards (e.g., A-5-3 with two spades, K-4-2 with two hearts). On A-5-3 two-spade, the preflop raiser has all the AA, AK, AQ, A5s sets --- massive nut advantage. But the BB defender, who called with a wide range including all suited Ax, many suited connectors, and small pocket pairs, has *higher total equity* because their range contains more flush draws (every suited spade hand), more two-pair combinations (A5o, A3o, 53s), and more sets (55, 33). The BB might have 52-54% aggregate equity (range advantage) while the preflop raiser has 70%+ of the nut combinations (nut advantage).

**The strategic implication:** The preflop raiser should use large bet sizes (66-100%+ pot) despite having lower total equity. The large sizing is correct *because* of the nut advantage --- it leverages the top-of-range concentration to pressure villain's many medium-strength hands (flush draws without the nut flush draw, weak aces, small pairs) that cannot profitably continue against large bets but would happily continue against small ones. The failure mode is using range advantage (equity metric) as the proxy for "who should be aggressive" --- equity says the BB has the advantage, but nut advantage says the raiser should be the aggressor with large sizings.

This divergence is further complicated by equity realization: nut advantage held OOP is worth less than the same nut advantage held IP, because OOP players realize approximately 60–80% of their raw equity versus ~100–110% IP (see solver-theory-gto reference, Trap 2). The large-sizing recommendation from nut advantage applies most cleanly when the nut-advantaged player is IP or the nuts are so far ahead that equity realization loss is insufficient to overcome the sizing advantage.

**Board texture signatures that reliably produce this divergence:**

1. **Monotone low boards** (e.g., 7-4-2 all spades): Raiser has overpairs and nut flush draw concentration; caller has flush draw density but lower flush draws.
2. **Ace-high dry boards with a backdoor flush** (e.g., A-7-3 rainbow or A-7-3 with two of one suit): Raiser has AA, AK, AQ with nut kickers; caller has wider Ax distribution plus small sets.
3. **King-high boards with disconnected low cards** (e.g., K-6-2 rainbow): Raiser has all KK, AK, KQ; caller has KT-K8 type hands that are dominated by raiser's king-x holdings.

The `NutAdvantageGauge` component (line 715) uses `countPremiums` to compute nut advantage from preflop premium hands (AA/KK/QQ/AKs/AKo). This is a *preflop* proxy. Postflop nut advantage is board-dependent and requires re-evaluation against the specific board. The gap: RangeIQ does not recompute nut advantage postflop. A board like 7-4-2 monotone dramatically shifts nut advantage toward the range with more nut flush draws, which may not be the range with more preflop premiums.

### Preflop Range Construction: Why A5s-A2s Over A8s-A9s in EP

The UTG RFI preset (line 56) includes A5s and A4s but excludes A6s-A9s. This is not arbitrary.

**The range construction role, not hand strength:** A5s-A2s serve three functions that A8s-A9s cannot:

1. **Wheel straight equity.** A5s can make the nut straight (A-2-3-4-5) on boards where no other hand in the EP opening range can. This adds a structurally unique nutted combination to runouts that otherwise leave the EP range capped. A8s-A9s make no unique straights --- their straight potential overlaps with Broadway hands already in the range.

2. **Nut-low blocker effect.** Holding A5s blocks opponent from having AA (reduces by 50%), AKs of that suit, and A5 combinations. The critical point: A5s blocks the *calling* range of opponents who 3-bet AA/AK and call with suited Ax. A8s also blocks AA, but A8s's straight equity duplicates what T9s and 98s already provide.

3. **Domination asymmetry.** A5s is rarely dominated by hands it needs to bluff against. When A5s 3-bets as a bluff, opponent's continuing range is AA/KK/QQ/AK --- hands that do not dominate A5s in the way they dominate A8s. Specifically, AK dominates A8s (A8 is outkicked and has no unique equity source), but AK does not dominate A5s in the same way because A5s retains wheel equity that AK cannot block. When A8s bluffs and gets called, it has ~25% equity against the calling range; A5s has ~30% equity because of the wheel outs.

**The failure mode:** Interpreting "A5s is in the GTO range and A8s is not" as "A5s is a stronger hand than A8s." A8s has higher raw preflop equity against a random hand (~58% vs ~56%). The inclusion is about range *composition* --- filling structural holes and avoiding domination --- not about individual hand strength.

### Merged vs. Polarized Range Composition and Bet Sizing Constraints

Range composition constrains bet sizing at the range level. A player can hold the nuts on a given board, but if their *range* is merged (dominated by medium-strength hands), using a large bet size with the nuts exploits their own range because villain can profitably call large bets knowing that most of hero's range cannot support the sizing. The structural reason is the indifference principle (see solver-theory-gto reference): when a range is merged, most hands are near the indifference boundary between betting and checking. A large bet sizing shifts the EV delta between actions, forcing indifferent hands to the wrong side of the boundary — either overcommitting marginal hands as value or abandoning equity with hands strong enough to extract from a smaller bet.

**Specific board runouts that force merging:**

1. **Single-raised pot, A-K-Q rainbow.** Both ranges hit this board hard. The raiser's range contains AK, AQ, KQ, AA, KK, QQ (all strong), but also AJ, AT, KJ, KT, QJ (all middle pair or worse). The caller's range similarly contains AQ, KQ, AJ, KJ, QJ, KT. On this board, >60% of both ranges are medium-strength (one pair, good kicker). The board is "equity-neutral" --- both ranges have similar distributions. The correct strategy is predominantly checking or using a small sizing (25-33% pot) because large bets only get called by hands that beat most of your range.

2. **Low paired boards in single-raised pots** (e.g., 7-7-3 rainbow). The raiser's range misses this board almost entirely --- very few 7x hands in a UTG/HJ opening range. The caller's range also mostly misses but may have more 7x (suited 76, 87, 97). Both ranges are merged around "overcards with no pair," making large bets ineffective. However, the raiser's overpairs (AA-88) are still nutted, creating a small polar component. The solver solution: bet small (~25-33% pot) at high frequency, leveraging the slight nut advantage without overcommitting with the merged portion of the range.

3. **Turn cards that equalize equity distributions.** A flop of T-7-4 two-tone allows the raiser to bet large (polar range: overpairs, sets vs. air). If the turn is a 2 of the off-suit (T-7-4-2, no flush), the raiser's range stays polar and can continue betting large. But if the turn completes the flush (e.g., 8 of the flush suit), the raiser's range becomes merged: overpairs that were nutted are now vulnerable, flush draws in the caller's range have arrived, and the raiser's strong hands (sets, two-pair) now face a range that includes many flushes. The raiser's range goes from polar to merged in one card, and the sizing must drop from 66-100% pot to 25-50% pot or a check.

**Detection in RangeIQ:** The `classifyHand` distribution across the range (as described in polarity proxy above) can flag merged states. When the "marginal" bucket exceeds 50% of the range's combos, large bet sizes are structurally incorrect regardless of which specific hand hero holds.

### Blocker Effects as Probability Shifts

Blocker analysis is commonly binary: "I block the nuts" or "I don't block the nuts." The operational reality is continuous: holding specific cards shifts opponent's range distribution by calculable percentages.

**Combinatorial impact of holding an Ace:**

- Opponent's AA combinations: from 6 to 3 (50% reduction).
- Opponent's AKo combinations: from 12 to 8 (33% reduction) if you hold one Ace; if you hold Ax where x != K, AKo goes from 12 to 9 (25% reduction with respect to the specific suit).
- Opponent's AKs combinations: from 4 to 3 (25% reduction).
- Opponent's Axs combinations (specific suit): from 4 to 3 if your Ace is the same suit, 4 to 3 if different suit (blocks one A combo).

**Why A5s is a better 3-bet bluff than K5s:**

The question is not "what do I block that villain has." The question is "how does holding these cards change the probability distribution of villain's response to my 3-bet?"

Villain's 3-bet calling/4-bet range against a 3-bet from the blinds typically includes: AA, KK, QQ, AKs, AKo (value), and the calling range includes TT-JJ, AQs, AJs, KQs, some suited connectors. Holding A5s:

- Reduces villain's AA from 6 to 3 combos (key --- AA is the strongest 4-bet hand).
- Reduces villain's AKo from 12 to 9 combos.
- Reduces villain's AKs from 4 to 3 combos.
- Total reduction in villain's strongest continuing hands: ~25%.

Holding K5s:

- Does not reduce villain's AA at all (6 combos unchanged).
- Reduces villain's KK from 6 to 3 combos.
- Reduces villain's AKo from 12 to 9.
- Reduces villain's AKs from 4 to 3.
- Total reduction in villain's strongest continuing hands: ~15%.

The 10-percentage-point difference in blocking villain's *continuing* range translates to approximately 3-5% more fold equity for A5s over K5s. At a pot size of 10bb facing a 3-bet to 30bb, this fold equity difference is worth ~0.5-1.0bb per 3-bet bluff --- significant over volume.

**The anti-pattern:** "I block the nuts, so I should bluff." This inverts the logic. Blocking the nuts means villain is *less likely* to have the nuts, which is good for bluffing. But the relevant calculation is: how much does the blocker shift villain's *total continuing frequency*, not just their nut frequency? Holding A5s on a board of K-Q-J-T blocks some of villain's nut straights (A9), but also blocks villain's AA, which was going to fold anyway. The relevant blocker effect is against the *marginal* continuing hands --- the bluff-catchers that are close to indifferent between calling and folding. If holding A5s blocks more of villain's marginal callers than K5s does, A5s is the better bluff. On K-Q-J-T, A5s blocks AQ/AJ/AT (all of which are calling), making it a better bluff than K5s which blocks KQ/KJ (already strong and calling regardless).

### Population-Calibrated Ranges vs. GTO Ranges

GTO ranges are the equilibrium baseline. Real opponents deviate. The deviations are systematic by position, situation, and player pool.

**Reliable population deviations (online 100bb 6-max, 2024-2025 data):**

1. **Blind defense frequency.** GTO BB defense vs. BTN open: ~55-60% of hands. Population average at NL50-NL200: ~42-48%. The under-defense is consistent and has been stable for years despite training material availability. Implication: when modeling villain's BB defense range in `runMonteCarlo`, using the GTO "BB def vs BTN" preset (line 61) overstates villain's range width by ~15-20%. This inflates villain's equity (more garbage hands in their range, but also more nutted combos from wider defense) and distorts the equity distribution shape.

2. **EP 3-bet frequency.** GTO 3-bet frequency from BB vs. UTG open: ~10-12% of defending range. Population average: ~6-8%. Under-3-betting from the blinds vs. EP is the most consistently exploitable population tendency. For trace generation, using GTO 3-bet ranges as villain's range overstates the frequency of premium hands in villain's continuing range.

3. **BTN flatting range.** GTO BTN flat vs. CO open: a condensed range of suited connectors, pocket pairs, and suited broadways (~15-18% of hands). Population includes dominated hands (KTo, QTo, J9o) at ~22-25%. This matters for postflop equity calculations: the population BTN range has lower equity realization because dominated hands hit boards poorly, and the equity distribution has a larger "dead money" tail of hands with <30% equity.

4. **Postflop aggression.** Population c-bet frequency on the flop: ~55-60% (down from ~70%+ in 2018-2020 as training materials have shifted toward more checking). GTO flop c-bet frequency is highly board-dependent (30-90%), but averaged across boards is ~50-55%. The population and GTO are close here --- the deviation is in the *distribution*, not the mean. Population c-bets too much on boards where GTO checks frequently (low connected boards like 7-6-5, where GTO c-bets ~35% but population c-bets ~55%) and about right on boards where GTO bets high frequency (A-K-x rainbow).

**The failure mode for trace generation:** Using GTO ranges as villain input to `runMonteCarlo` when the trace is supposed to represent optimal play against a *real* opponent. If the trace says "villain's range here is [GTO construction]" but real opponents have a systematically different range, the equity calculations, range advantage assessments, and EV tree outputs are all calibrated to a phantom opponent. The fine-tuned model learns to play optimally against GTO opponents, which is guaranteed break-even by definition --- the model cannot learn to extract value from population deviations if the training data assumes population plays GTO.

**The operational fix:** Module 1's preset system could include "Population BTN" alongside "BTN RFI" --- same position, different range construction reflecting pool tendencies. The trace context (`buildContext`) should include a `range_source: "gto" | "population" | "custom"` field so downstream consumers know whether the equity calculations assume GTO or population play.

---

## Failure Modes and Anti-Patterns

### 1. Polarity-Sizing Mismatch (Severity: Critical)

**Trigger:** Selecting a large bet size (66-100% pot) when the hero's range on the current board is merged (>50% of combos are marginal hands by the `classifyHand` proxy).

**What it looks like:** The EV tree shows a positive EV for the large bet because the GTO-seeded fold frequencies assume villain defends at MDF. But the range-wide EV is negative because when villain calls, they call with hands that beat most of hero's range. The individual hand (which may be the nuts) profits, but the range loses money because the non-nut hands in the betting range are overcommitting.

**Detection:** Run `classifyHand` across all combos in the hero range on the current board. If the marginal bucket is >50%, flag large sizings as structurally suspect. The `metrics.pi` field (currently null, not yet computed) would automate this check. Until implemented, the `classifyHand` distribution across the range can serve as the proxy. Note that the polarity proxy buckets (value/marginal/air) describe range composition for sizing decisions — they are an approximation tool, not a prescription for deterministic mixing. Implementing these buckets as betting rules ("always bet value bucket, always check air bucket") creates the exploitable capped-checking-range anti-pattern documented in solver-theory-gto.md Failure Mode 3.

### 2. Preflop Nut Advantage Used as Postflop Nut Advantage (Severity: Critical)

**Trigger:** The `NutAdvantageGauge` displays nut advantage based on preflop premiums (AA/KK/QQ/AKs/AKo). This metric does not update when a board is dealt. On a board of 7-6-5 two-tone, the EP range's preflop nut advantage (mostly premiums) becomes a nut *disadvantage* postflop (the BB defender has more sets, straights, and two-pair combos).

**What it looks like:** The header displays "Hero Nut Advantage: 68%" on a board where hero's actual postflop nut advantage is ~35%. Traces generated from this state include a misleading nut advantage metric in `computed_metrics.nut_advantage_score`.

**Detection:** Compare the preflop nut advantage metric against a postflop proxy. If the board is connected (connectivity >= 2 in `boardTexture`) and the average board rank is below 9 (i.e., low-mid board), the preflop nut advantage is unreliable and should be flagged or suppressed in trace context.

### 3. Aggregate Equity Masking Bimodal Distribution (Severity: High)

**Trigger:** `runMonteCarlo` returns 51% hero equity. The user or trace generator interprets this as "approximately even, marginal spot." But the range is bimodal: 40% of combos have >80% equity (overpairs, sets), 60% of combos have <30% equity (missed suited connectors, air). The "even" equity is an artifact of averaging extremes.

**What it looks like:** Traces that recommend mixed strategies (bet small at medium frequency) on boards where the correct strategy is polarized (bet large with the value cluster, give up with the air cluster). The aggregate equity suggests a marginal situation; the distribution demands a polar approach.

**Detection:** The `histogram: null` field in the Monte Carlo output (line 390) is the gap. Until implemented, check whether the hero range contains both overpairs/sets AND suited connectors/air on the current board. If both categories exceed 25% of combos, the aggregate equity is likely misleading.

### 4. Blocker Logic Inversion (Severity: High)

**Trigger:** The trace generator (or a human interpreting RangeIQ output) reasons "I hold Ax, which blocks the nuts, so I should bluff" on a board where Ax blocks villain's *folding* range rather than their *calling* range.

**What it looks like:** On a board of K-Q-J, holding A5: the Ace blocks AK/AQ/AJ (villain's value hands that are *continuing*), making this a good bluff. But on a board of T-7-3, holding A5: the Ace blocks AT/A7/A3 (villain's weak top pair and medium pairs that might *fold*). Blocking the folding range makes the bluff worse, not better. The heuristic "Ace = good blocker for bluffing" inverts on boards where Ax hands are part of villain's folding range rather than calling range.

**Detection:** Board-dependent. On high-card boards (top card K+), Ace blockers primarily block calling range (good for bluffing). On low-card boards (top card T or below), Ace blockers primarily block folding range (bad for bluffing). This board-card-rank threshold is a heuristic, not a rule, but it catches the most common inversion.

### 5. Population Range Used as GTO Input (Severity: Medium)

**Trigger:** User loads a population-calibrated villain range (wider, more dominated hands) into the villain range input, then generates traces framed as GTO analysis. The equity calculations are correct for the population range, but the traces claim GTO optimality.

**What it looks like:** Traces that say "the GTO-optimal play is to bet 75% pot" when the calculation used a population range that is wider than GTO. The bet sizing might be correct *against this population*, but it is not GTO --- it is exploitative. The trace conflates the two frameworks.

**Detection:** Compare the loaded villain range against the closest GTO preset. If the combo count differs by >15%, or if the range includes hands not in the GTO preset (e.g., K9o in a range supposedly representing CO RFI), flag the trace as exploitative rather than GTO.

---

## Implementation Notes

### Equity Distribution Recovery

**Current state:** `runMonteCarlo` (lines 324-400) returns aggregate equity only. The `histogram: null` placeholder (line 390) was designed for per-combo equity buckets but is unimplemented.

**Implementation path:** During the Monte Carlo loop, maintain a per-hero-combo win counter. After completion, compute equity per combo: `comboEquity[i] = (comboWins[i] + comboTies[i] * 0.5) / comboTrials[i]`. Bucket into 10% bands (0-10%, 10-20%, ..., 90-100%). This produces the equity distribution histogram. From the histogram, compute:

- **Polarity index:** `(count_below_25pct + count_above_75pct) / total_combos`. Store in `metrics.pi.hero`.
- **Distribution variance:** Standard deviation of per-combo equity. High variance (>0.25) = polar range. Low variance (<0.15) = merged range.
- **Nut density:** `count_above_80pct / total_combos`. This is the postflop nut advantage metric that should replace or supplement the preflop `countPremiums` proxy.

**Performance concern:** Tracking per-combo equity requires maintaining a hashmap of combo -> {wins, ties, trials}. For ~100 combos, this is negligible. The `CHUNK = 5000` pattern is unaffected. The equity figures fed into the EV tree carry an approximation risk on non-flop streets — the `equity_is_approximated` flag (documented in solver-theory-gto reference, Failure Mode 2) marks nodes where flop equity is propagated unchanged to turn and river, and the distribution histogram, once implemented, should carry the same flag to prevent its use as precise turn/river equity.

### Postflop Nut Advantage

**Current state:** `countPremiums` (line 81) counts AA/KK/QQ/AKs/AKo combos in the range. This is preflop-only.

**Implementation path:** After `runMonteCarlo` completes with the histogram, compute `nutDensityHero = combos_above_80pct_equity / total_hero_combos` and `nutDensityVillain` similarly. Postflop nut advantage = `nutDensityHero / (nutDensityHero + nutDensityVillain)`. Dispatch to `metrics.na` to replace the preflop proxy.

**State field:** `metrics.na` (line 445) is already declared. Currently null. The `NutAdvantageGauge` component (line 715) reads from `countPremiums` directly rather than `metrics.na`. Rewiring it to use `metrics.na` when available (postflop, after MC completes) and falling back to `countPremiums` (preflop, before MC) would provide board-aware nut advantage.

### Range Advantage Computation

**Current state:** `metrics.ra` (line 445) is declared but never computed.

**Implementation path:** After Monte Carlo, `metrics.ra = heroEquity - 50`. A positive value means hero has range advantage. This is trivial to compute from existing MC output and should be dispatched alongside equity in `SET_METRICS`.

### `classifyHand` Distribution for Polarity Proxy

**Current state:** `classifyHand` is called per-combo in Module 2's range breakdown chart. The distribution data exists visually but is not stored in state or passed to Module 4.

**Implementation path:** After board is set, run `classifyHand` across all hero combos (using `expandHand` to get specific combos, then classifying each). Aggregate into the three polarity buckets (value/marginal/air). Store as `metrics.pi.hero = { value_pct, marginal_pct, air_pct, polarity_proxy }`. This is computationally cheap (~100-200 combo classifications) and does not require Monte Carlo.

### Trace Context Enrichment

**Current state:** `buildContext` (line 1614) serializes `computed_metrics` including `polarity_index_hero: metrics.pi?.hero ?? null`.

**Gap:** The `pi` field is always null. When the polarity proxy is implemented (above), it flows directly into trace context. Additionally, `buildContext` should include:

- `range_source: "gto" | "population" | "custom"` --- detectable by comparing the loaded range against PRESETS.
- `postflop_nut_advantage` --- from the MC-derived nut density, separate from preflop nut advantage.
- `equity_distribution_shape: "polar" | "merged" | "continuous"` --- derived from polarity index thresholds (>0.70 polar, <0.50 merged, between = continuous).

### Preset Range Extension

**Current state:** 14 presets (lines 55-69), all GTO-derived.

**Implementation path for population ranges:** Add population-calibrated presets that reflect pool deviations:

- `"Pop BB def vs BTN"`: Remove the bottom ~15% of the GTO BB defense range (hands like Q3s, J5s, T6s, 75o, 43s).
- `"Pop CO RFI"`: Add dominated broadway offsuit hands (KTo, QTo, JTo) that population includes.
- `"Pop BTN RFI"`: Widen by ~5% with hands like Q6o, J8o, T8o.

These enable trace generation against realistic opponent ranges. The `range_source` field in trace context distinguishes which range type was used.

---

## "Looks Right But Isn't" Traps

### Trap 1: Two Pair Classified as Value When It Behaves as Marginal

`classifyHand` returns `category: "Two Pair"` with a strength score derived from `(handRank / 8) * 0.85 + (tiebreak / 14) * 0.15` (line 318). For Two Pair, `handRank = 2`, producing `strength ~= 0.23-0.28`. This places Two Pair below pairs in the strength score, which is mathematically correct for the hand ranking but strategically wrong for the polarity classification.

The real trap: Two Pair's *strategic* behavior is position-dependent in the equity distribution. On static boards (K-7-2 rainbow), Two Pair (K7) is a nutted hand --- top of the distribution, pure value bet. On dynamic boards (T-9-7 two-tone), Two Pair (T9) is a marginal hand --- vulnerable to straights, flushes, and higher two-pairs on later streets. The same `classifyHand` category maps to different polarity buckets depending on board texture.

**Why it looks right:** Two Pair is always categorized as "Two Pair." The category is correct. The strength score is consistent. But any polarity proxy that assigns Two Pair to a fixed bucket (value or marginal) will be wrong on ~40% of boards.

**Impact:** If the polarity proxy classifies Two Pair as "value" (reasonable --- it beats one pair), the polarity index is inflated on wet boards where Two Pair plays as a bluff-catcher. If classified as "marginal" (also reasonable --- it can be outdrawn), the polarity index is deflated on dry boards where Two Pair is effectively nutted. The fix requires conditioning the bucket assignment on `boardTexture.wetness`: Two Pair is value when wetness < 3, marginal when wetness >= 3.

### Trap 2: Combo Count Symmetry Hiding Strategic Asymmetry

The `totalCombos` function and the "Delta" display (line 792: `totalCombos(heroRange) - totalCombos(villainRange)`) present combo count differences as a proxy for range width. A delta of 0 (equal combos) is displayed as even. But equal combo count does not mean equal range composition.

**Specific example:** Hero (UTG RFI, 194 combos) vs. Villain (BB def vs BTN, 480 combos) on a flop. After removing combos blocked by the board, suppose both ranges have 165 live combos. The delta is 0. But Hero's 165 combos are concentrated: 30 overpairs, 20 top pair, 115 air/missed. Villain's 165 combos are dispersed: 8 sets, 12 two-pair, 45 top pair, 35 middle pair, 25 draws, 40 air. The "equal combo count" masks that Hero's range is bimodal (polar) while Villain's is continuous (merged). This directly affects correct bet sizing, but the combo delta suggests an even matchup.

**Why it looks right:** Combo count is a real and relevant metric. More combos = wider range, generally. But on any specific board, the *structural composition* of remaining combos matters more than the count. Two ranges with identical combo counts can have entirely different polarity profiles.

**Impact on traces:** The `computed_metrics` passed to the trace generator does not include post-board combo distributions. The trace model receives combo counts (from `totalCombos`) and aggregate equity (from `runMonteCarlo`) but not the distribution shape. It must infer polarity from board texture and range composition, which it can only do if the training data taught it to. Traces generated with combo-count-as-proxy will teach the model that equal combos = equal strategic position, which is false.

### Trap 3: GTO-Seeded Raise Frequency Masking Board-Dependent Raise Incentive

The `buildTree` function (line 1132) hardcodes `raisePct = 10` for all nodes. The `adjustedCallPct = callPct - raisePct` (line 1133) deducts this from calling frequency. This produces EV trees where villain's raise frequency is constant across all board textures and bet sizings.

On boards where villain's range contains many semi-bluff raise candidates (e.g., flush draws + pair on a two-tone board), the actual raise frequency from solver outputs is 15-25%. On boards where villain's range is condensed and passive (e.g., A-A-7 where villain's range is capped at one-pair), the actual raise frequency is 2-5%.

**Why it looks right:** 10% is the median. The EV tree "accounts for" raises. The hero-fold-to-raise calculation is correct given the assumed raise size. Each node has a plausible-looking raise child with a plausible fold/call decision for hero.

**Impact:** On boards where raises should be frequent (wet, connected), the tree underestimates villain's aggression. The EV of hero's bet is overstated because it assumes villain passively calls or folds 90% of the time. Traces citing this EV to justify thin value bets will overestimate profitability. On boards where raises should be rare (dry, disconnected, paired), the tree overestimates villain's aggression, understating hero's bet EV and potentially discouraging profitable bets. The bias is *directionally opposite* on the two board types, making it hard to detect from aggregate statistics --- the average raise frequency across all boards may be approximately correct, masking the per-board errors.

### Trap 4: Preflop Preset Ranges Treating Position as the Only Construction Variable

The 14 presets in `PRESETS` (lines 55-69) are indexed by position (UTG, HJ, CO, BTN, SB) and situation (3-bet, call 3-bet, 4-bet). This treats range construction as a function of position alone. In practice, range construction depends on:

- **Effective stack depth.** The UTG RFI preset is calibrated for 100bb effective stacks. At 40bb, the opening range tightens significantly (remove suited connectors, small pairs); at 200bb, it widens (add more suited gappers and small suited Ax). The presets do not vary with the `effStack` field in `evTreeConfig`.
- **Number of players left to act.** UTG with 5 players behind is tighter than UTG with 3 players behind (short-handed). The presets assume 6-max.
- **Ante structure.** With antes (tournament play), all opening ranges widen by ~5-10%. The presets assume no antes.

**Why it looks right:** Position-based presets are standard in every poker tool. The ranges are correct for 100bb 6-max cash games without antes. The specific hands are solver-verified for these conditions.

**Impact:** When the user sets `effStack: 40` (short-stacked) and loads the UTG RFI preset, the range includes hands (87s, 76s, 98s) that should not be opened at 40bb because they rely on implied odds that short stacks cannot deliver. The Monte Carlo equity, EV tree, and traces are all computed against a range that is wrong for the stack depth. The error propagates silently through the entire pipeline.

---

## Connections to Adjacent Domains

### Solver Theory and GTO Equilibrium (bidirectional)

**From Range Construction to Solver Theory:** The quality of solver outputs depends on the accuracy of input ranges. Solvers compute equilibrium strategies *given* a range for each player at each decision point. If the input range is wrong (e.g., using a GTO preflop range when the actual opponent has a population-deviated range), the solver's equilibrium is correct for the wrong game. Range construction is upstream of solver computation, and errors in range construction produce systematically biased solver outputs. Specifically, the A5s-vs-A8s EP construction decision affects solver outputs on every board --- including A5s but excluding A8s means the solver never produces strategies for A8s, creating a blind spot in the strategy profile for that hand. The solver's strategy for A5s must account for the absence of A8s in the range, which changes how the range interacts with specific board textures.

**From Solver Theory to Range Construction:** CFR convergence artifacts (identified in the solver-theory-gto reference) directly affect range construction recommendations. A solver that recommends "open A5s 92% from UTG" at 5,000 iterations might converge to "open A5s 99.5% from UTG" at 200,000 iterations --- the first suggests mixing, the second suggests pure opening. Premature stopping in solver runs produces misleading range construction advice for marginal hands. The hands most affected are exactly the ones at the boundary of the opening range: A9s-A6s, small suited connectors (54s, 43s), and small pocket pairs (22-44). These are the hands where solver convergence is slowest because they are near the indifference boundary.

The `raisePct = 10` hardcode in `buildTree` connects to solver abstraction distortions: solver bet-size bucketing affects the computed raise frequency, and the fixed 10% mirrors the median of bucketed solver outputs rather than the actual optimal raise frequency for any specific board.

### Board Texture and Equity Analysis (bidirectional)

**From Range Construction to Board Texture:** The equity distribution shape (polar vs. merged) is jointly determined by the *range* and the *board*. The same board can produce a polar distribution for one range and a merged distribution for another. `boardTexture` computes properties of the board in isolation (wetness, connectivity, flush texture), but these properties only become strategically meaningful when combined with the range's composition on that board. The operational connection: `boardTexture.wetness` should be an input to the polarity proxy's bucket assignment (as described in Trap 1: Two Pair classification depends on wetness), and the polarity proxy should be an input to the recommended bet sizing in the EV tree.

**From Board Texture to Range Construction:** Board texture determines which preflop range construction decisions pay off. The A5s-over-A8s decision has no impact on A-K-Q rainbow (neither hand makes a relevant straight; both are effectively air). The decision matters enormously on 5-4-3 boards (A5s has the nut straight; A8s has nothing) and on A-5-x boards (A5s has two-pair; A8s has top pair weak kicker). The `boardTexture` output's connectivity score predicts which boards reward structured range construction (high connectivity = straight-making boards = A5s inclusion pays off) versus which boards are dominated by high-card strength (low connectivity, high-card-heavy = A8s's raw equity advantage matters more). This connection is not currently exploited in RangeIQ but would improve trace quality by explaining *why* certain range construction decisions exist.

### LLM Fine-Tuning and Trace Quality (unidirectional: Range Construction -> Trace Quality)

Range construction knowledge is a prerequisite for trace quality assessment. A trace that explains a betting decision without referencing the range's equity distribution shape is reasoning at the wrong level of abstraction. The trace says "bet because we have good equity" when it should say "bet large because our range is polar on this board, with 35% value hands above 80% equity and 40% air below 25% equity, enabling a geometric sizing that maximizes EV across the full range." The polarity proxy (from `classifyHand`) and the equity histogram (from the Monte Carlo extension) provide the data needed to ground traces in range-level reasoning rather than hand-level reasoning. Traces grounded in range-level reasoning produce fine-tuned models that generalize to new boards; traces grounded in hand-level reasoning produce models that memorize board-specific patterns.
