# ADR-XXX: [Title - Use Verb Phrase, e.g., "Use Elo Ratings for Initial Model"]

**Date**: YYYY-MM-DD

**Status**: Proposed | Accepted | Deprecated | Superseded by [ADR-YYY]

**Deciders**: [Who was involved in the decision - can be "Development Team", specific names, or AI agents]

**Tags**: `#architecture` `#modeling` `#data` `#betting` `#infrastructure`

---

## Context

### Problem Statement

What is the issue we're facing? Frame it clearly with:

- What needs to be decided
- Why it needs to be decided now
- What constraints exist

### Background

Relevant context for understanding the decision:

- Current system state
- Prior attempts or approaches
- Business/technical constraints
- Timeline pressures

### Requirements

What must the solution satisfy?

- **Functional**: What it must do
- **Non-functional**: Performance, scalability, maintainability
- **Domain-specific**: Sports betting constraints (e.g., CLV tracking, bankroll limits)

---

## Decision

### What We're Going to Do

Clear statement of the chosen approach. Use active voice:

> We will [implement/use/adopt] [solution] because [primary reason].

### Implementation Details

**Technical Approach**:

- Component A: How it works
- Component B: Integration points
- Data flow: Input → Processing → Output

**Configuration**:

```python
# Example configuration or code structure
CONFIG = {
    'parameter1': value1,
    'parameter2': value2,
}
```

**Integration Points**:

- Module X: How this decision affects it
- API Y: New interfaces or changes

---

## Consequences

### Positive Outcomes

What we gain from this decision:

- ✅ Benefit 1: Specific advantage with measurable impact
- ✅ Benefit 2: How it improves the system
- ✅ Benefit 3: Long-term value

**Example**:

- ✅ Elo ratings provide baseline predictions within 2 weeks vs 2+ months for ML
- ✅ Interpretable model helps identify data issues early
- ✅ Lower computational cost enables faster iteration

### Negative Tradeoffs

What we sacrifice or accept:

- ⚠️ Tradeoff 1: What we give up and why it's acceptable
- ⚠️ Tradeoff 2: Limitation and mitigation plan
- ⚠️ Tradeoff 3: Technical debt introduced

**Example**:

- ⚠️ Elo may underperform complex ML models by 1-2% accuracy
- ⚠️ Requires manual K-factor tuning vs learned parameters
- ⚠️ Doesn't capture player-level injuries without extensions

### Neutral Changes

Things that change but aren't clearly positive or negative:

- ↔️ Complexity added: [Description]
- ↔️ Dependencies introduced: [List with versions]
- ↔️ Learning curve: Team needs to understand [concept]

**Example**:

- ↔️ Adds dependency on `scipy` for Elo calculations
- ↔️ Requires understanding of Elo rating mathematics
- ↔️ Team must track separate ratings per sport

---

## Alternatives Considered

### Option 1: [Name of Alternative]

**Description**: What this alternative would entail

**Pros**:

- Advantage 1
- Advantage 2

**Cons**:

- Disadvantage 1
- Disadvantage 2

**Why Rejected**: Specific reason(s) this wasn't chosen

---

### Option 2: [Another Alternative]

**Description**: What this alternative would entail

**Pros**:

- Advantage 1

**Cons**:

- Disadvantage 1
- Disadvantage 2

**Why Rejected**: Specific reason(s)

---

### Option 3: Do Nothing

**Description**: What happens if we don't make a decision

**Impact**: Consequences of inaction

**Why Rejected**: Why status quo is unacceptable

---

## Implementation Plan

### Phase 1: [Short-term]

**Timeline**: Week 1-2

Tasks:

1. Task 1: Specific action
2. Task 2: Specific action
3. Task 3: Validation step

**Success Criteria**: How we know Phase 1 is complete

---

### Phase 2: [Medium-term]

**Timeline**: Week 3-4

Tasks:

1. Task 1
2. Task 2

**Success Criteria**: Metrics or outcomes

---

### Migration Path

If replacing existing functionality:

1. **Parallel Running**: Run old and new side-by-side
2. **Validation**: Compare outputs for N games/bets
3. **Cutover**: When to switch completely
4. **Rollback Plan**: How to revert if issues arise

---

## Validation & Testing

### How We'll Know This Works

**Success Metrics**:

- Metric 1: Target value (e.g., CLV > 1%)
- Metric 2: Target value (e.g., ROI > 3%)
- Metric 3: Operational metric (e.g., backtest runtime < 5 min)

**Testing Strategy**:

```python
# Test cases that validate the decision
def test_decision_works():
    """Test that new approach meets requirements"""
    assert new_approach.metric() > threshold
```

**Monitoring**:

- What to track post-implementation
- Alerts/thresholds for degradation

---

## References

### Related ADRs

- [ADR-001: Prior Related Decision](link) — How they relate
- [ADR-005: Dependency](link) — What this builds on

### External Resources

- [Research Paper/Blog](https://url) — Supporting evidence
- [Documentation](https://url) — Technical reference
- [Similar Implementation](https://github.com) — Prior art

### Internal Documentation

- Code location: `module/submodule/file.py:123`
- Tests: `tests/test_module.py`
- Configuration: `config/settings.py`

### Domain Knowledge

Relevant formulas or concepts from `CLAUDE.md`:

- [Section: Elo Rating System](../../CLAUDE.md#elo-rating-system)
- [Section: Kelly Criterion](../../CLAUDE.md#kelly-criterion)

---

## Notes

### Open Questions

- Question 1: What we still need to figure out
- Question 2: Pending research or decisions

### Future Considerations

- Idea 1: How this decision might evolve
- Idea 2: Planned enhancements

### Lessons Learned

(Update after implementation)

- What worked well
- What didn't work
- What we'd do differently

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| YYYY-MM-DD | Initial proposal | [Name/Agent] |
| YYYY-MM-DD | Accepted after review | [Name/Agent] |
| YYYY-MM-DD | Updated with implementation learnings | [Name/Agent] |

---

**Review Cycle**: Every [3 months / major version / season]

**Next Review**: YYYY-MM-DD

**Owner**: [Team/Person responsible for maintenance]

---

## Template Usage Notes

When creating a new ADR:

1. **Copy this template** to `docs/DECISIONS.md` or create a new file
2. **Assign sequential number** (check existing ADRs)
3. **Fill all sections** — Don't leave placeholders
4. **Use specific examples** — Generic text isn't helpful
5. **Link to code** — Make it traceable
6. **Update STATUS** as decision evolves
7. **Store in memory**:

   ```bash
   npx claude-flow@alpha memory store "adr_XXX_summary" "One-line summary" --namespace betting/decisions
   ```

**Good ADR characteristics**:

- ✅ Specific and actionable
- ✅ Explains "why" not just "what"
- ✅ Documents alternatives considered
- ✅ Measurable success criteria
- ✅ Clear consequences (good and bad)

**Bad ADR characteristics**:

- ❌ Vague or generic
- ❌ No alternatives discussed
- ❌ No measurable outcomes
- ❌ Missing context or rationale
- ❌ Not maintained after implementation
