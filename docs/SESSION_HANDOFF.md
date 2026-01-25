# Session Handoff Log

## Purpose

This document maintains continuity between Claude Code and Claude Flow sessions. Update after each significant work session.

---

## Latest Session: [DATE]

### Work Completed

- [ ] Item 1
- [ ] Item 2
- [ ] Item 3

### Current State

**Branch:** `main` / `feature/xxx`
**Last Commit:** [hash] - [message]

### Claude Flow State

**Swarm Active:** Yes/No
**Active Agents:** [list or "none"]
**Memory Items Stored This Session:**

- `betting/[namespace]`: [key] — [brief description]

### Files Modified

| File | Changes | Status |
|------|---------|--------|
| `path/to/file.py` | Description | ✅ Complete / 🔄 In Progress |

### Active Bugs/Issues

| Issue | Description | Priority |
|-------|-------------|----------|
| None currently | | |

### Next Session Priorities

1. Priority 1
2. Priority 2
3. Priority 3

### Blockers

- None currently

### Notes for Next Session

- Any context needed
- Memory queries to run: `npx claude-flow@alpha memory query "[topic]" --namespace betting/[ns]`

---

## Session History

### Session [DATE] - [TOPIC]

**Duration:** X hours
**Focus:** Description

**Completed:**

- Item 1
- Item 2

**Decisions Made:**

- Decision 1: [Rationale]

**Carried Forward:**

- Item for next session

---

### Session [DATE] - [TOPIC]

[Template repeats]

---

## Quick Context Restore

### To Resume Work

```bash
# Navigate to project
cd ~/sports_betting

# Activate environment
conda activate sports_betting

# Check git status
git status

# Run tests to verify state
pytest tests/ -v

# Start Jupyter (if needed)
jupyter notebook
```

### Key Files to Review

1. `CLAUDE.md` - Project context
2. `docs/DATA_DICTIONARY.md` - Data definitions
3. `docs/DECISIONS.md` - Architecture decisions
4. This file - Recent session context

### Current Model Performance

| Model | Sport | Last Backtest | CLV | Status |
|-------|-------|---------------|-----|--------|
| Elo v1 | NCAAB | [date] | X% | 🔄 Dev |
| F5 v1 | MLB | [date] | X% | ⏳ Pending |

---

## Update Template

Copy this for new sessions:

```markdown
### Session [DATE] - [TOPIC]
**Duration:** X hours
**Focus:**

**Claude Flow Usage:**
- Swarm: Yes/No, [agents] agents
- Memory Stored: [list keys]
- Memory Queried: [list queries]

**Completed:**
-

**Decisions Made:**
-

**Carried Forward:**
-

**Files Modified:**
-

**Tests Added/Updated:**
-

**Next Steps:**
1.
2.
3.
```

---

## Claude Flow Quick Reference

### Before Starting Session

```bash
# Check for relevant stored patterns
npx claude-flow@alpha memory query "[today's topic]" --namespace betting/patterns
npx claude-flow@alpha memory query "[today's topic]" --namespace betting/bugs

# Check model status
npx claude-flow@alpha memory list --namespace betting/models
```

### After Completing Session

```bash
# Store any new patterns discovered
npx claude-flow@alpha memory store "[pattern-key]" "[description]" --namespace betting/patterns

# Store bug fixes
npx claude-flow@alpha memory store "[bug-key]" "[issue and fix]" --namespace betting/bugs

# Update model status if applicable
npx claude-flow@alpha memory store "[model-version]" "[current status and metrics]" --namespace betting/models
```
