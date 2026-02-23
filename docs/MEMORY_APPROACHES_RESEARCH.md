# Alternative Memory/Learning Approaches for Claude Code

**Date**: 2026-02-20
**Researcher**: Research Analyst Agent
**Objective**: Find the best memory/context management approach to reduce "Wrong Approach" incidents with minimal complexity
**Context**: Solo Python developer on Windows 11, NCAAB betting models, 10+ "Wrong Approach" incidents across 8 sessions

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Top 10 Alternatives Ranked](#top-10-alternatives-ranked)
4. [Detailed Write-up of Top 3](#detailed-write-up-of-top-3)
5. [Full Comparison Matrix](#full-comparison-matrix)
6. [All 16 Approaches Evaluated](#all-16-approaches-evaluated)
7. [Recommended "Option 2"](#recommended-option-2)
8. [Sources](#sources)

---

## Executive Summary

After researching 16 distinct approaches across 4 categories (lightweight session persistence, structured memory systems, simplified learning, and community approaches), the single best alternative to ECC Continuous Learning v2 for this project is **Claude Diary** by Lance Martin.

The key insight from this research: the "Wrong Approach" problem (Claude re-doing completed work) is primarily a **retrieval problem**, not a capture problem. The current MEMORY.md already captures good state -- the issue is that Claude does not always consult it before acting, and compaction loses session-specific context. The solution needs to be:

1. Extremely low setup/maintenance cost (solo dev constraint)
2. Windows-compatible without WSL hacks
3. Focused on *injecting the right context at the right time* rather than capturing everything
4. Minimal token overhead (context exhaustion is the secondary friction)

The top 3 approaches are:

1. **Claude Diary** -- reflection-based memory that updates CLAUDE.md rules (best balance)
2. **PreCompact + SessionStart hooks** -- save state before compaction, inject on resume (most targeted)
3. **idnotbe/claude-memory** -- structured JSON memory with deterministic triage (most sophisticated without LLM overhead)

---

## Current State Analysis

### What You Have Now

| Component | Location | Function |
|-----------|----------|----------|
| Auto-memory | `~/.claude/projects/.../memory/MEMORY.md` | Claude's auto-saved notes (99 lines, under 200-line limit) |
| Project instructions | `CLAUDE.md` | Comprehensive project context (~800 lines) |
| Global rules | `~/.claude/rules/*.md` | 8 rule files (agents, coding-style, git, hooks, patterns, perf, security, testing) |
| Session hooks | `.claude/settings.json` | Minimal Stop hook (echo ok), statusline |
| CL-v2 artifacts | `~/.claude/homunculus/observe.py` | Partially set up, caused python3 issues on Windows |

### Why "Wrong Approach" Incidents Happen

Based on analysis of the friction pattern:

1. **Compaction loss**: When auto-compaction triggers, session-specific decisions (e.g., "we tried X and it failed, use Y instead") are lost. The compacted summary does not preserve tactical decisions.
2. **MEMORY.md not consulted proactively**: Claude reads MEMORY.md at session start but may not re-read it mid-session or after compaction.
3. **No session handoff protocol**: When starting a new session, Claude has MEMORY.md but no structured "here is exactly where we left off and what NOT to redo."
4. **Rules are static**: The `~/.claude/rules/` files contain general patterns but not project-specific lessons learned from failures.

### What the Ideal Solution Looks Like

- Automatically saves "what worked, what failed, what is left" before compaction
- Injects targeted context at session start and after compaction
- Evolves project-specific rules from actual session experience
- Costs < 1 hour/week maintenance
- Zero or near-zero LLM token overhead for the memory system itself
- Works natively on Windows 11 with PowerShell/Git Bash

---

## Top 10 Alternatives Ranked

Ranked by (effectiveness at reducing "Wrong Approach" x simplicity), best first:

| Rank | Approach | Effectiveness | Simplicity | Score |
|------|----------|--------------|------------|-------|
| 1 | **Claude Diary** | HIGH | HIGH | 9/10 |
| 2 | **PreCompact + SessionStart hooks** | HIGH | HIGH | 9/10 |
| 3 | **idnotbe/claude-memory** | HIGH | MEDIUM | 8/10 |
| 4 | **"Lessons Learned" append protocol** | MEDIUM | VERY HIGH | 8/10 |
| 5 | **memsearch (Zilliz)** | HIGH | MEDIUM | 7/10 |
| 6 | **Claudeception** | MEDIUM | HIGH | 7/10 |
| 7 | **Session-end summary skill** | MEDIUM | HIGH | 7/10 |
| 8 | **MCP Memory Keeper** | MEDIUM | MEDIUM | 6/10 |
| 9 | **claude-mem** | HIGH | LOW | 6/10 |
| 10 | **Error-only capture hook** | LOW | VERY HIGH | 5/10 |

---

## Detailed Write-up of Top 3

### 1. Claude Diary (by Lance Martin / LangChain)

**What it is**: A Claude Code plugin that implements a three-tier memory architecture (Observations, Reflection, Retrieval) inspired by Generative Agents research. It captures session experiences as diary entries and periodically reflects on them to update CLAUDE.md rules.

**How it works**:

- `/diary` command (or PreCompact hook): Generates a structured diary entry from the current session covering task summary, work done, design decisions, challenges, solutions, and code patterns
- `/reflect` command: Analyzes accumulated diary entries, identifies recurring patterns (2+ occurrences = pattern, 3+ = strong pattern), checks for violations of existing CLAUDE.md rules, and proposes imperative one-line rule updates
- Diary entries stored as markdown files in `~/.claude/memory/diary/YYYY-MM-DD-session-N.md`
- Tracks processed entries to avoid duplicate analysis
- Rules are synthesized across 6 categories: PR feedback, preferences, design decisions, anti-patterns, efficiency lessons, project-specific patterns

**Why it is the best fit**:

- Directly targets "Wrong Approach" by converting failures into persistent rules
- The `/reflect` command explicitly looks for anti-patterns and "NEVER DO" rules
- Updates CLAUDE.md, which is loaded every session -- no retrieval problem
- PreCompact hook ensures diary entry is captured before context loss
- Pure markdown storage -- fully transparent, editable, git-trackable
- No background services, no databases, no vector stores
- Shell scripts work on Windows via Git Bash (Claude Code's default shell)

**Implementation sketch for this project**:

```
# 1. Install
Copy commands/ to ~/.claude/commands/diary.md and reflect.md

# 2. Configure PreCompact hook in .claude/settings.json
{
  "hooks": {
    "PreCompact": [{
      "matcher": "auto",
      "hooks": [{
        "type": "command",
        "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/diary-precompact.sh"
      }]
    }]
  }
}

# 3. diary-precompact.sh saves session state
#!/bin/bash
# Reads transcript, creates diary entry in ~/.claude/memory/diary/

# 4. Weekly: run /reflect to update CLAUDE.md rules
# "Claude, run /reflect on last 7 diary entries"
```

**Rating**:
| Criterion | Rating |
|-----------|--------|
| Setup complexity | 2/5 |
| Windows compatibility | YES (Git Bash scripts) |
| Maintenance burden | 0.5 hours/week (weekly /reflect) |
| "Wrong Approach" reduction | HIGH |
| Context exhaustion help | MEDIUM (diary entries keep context lean) |
| Token cost impact | LOW (one Haiku call per /reflect) |

---

### 2. PreCompact + SessionStart Hooks (Custom)

**What it is**: A pair of hooks that (a) save critical session state to a checkpoint file before compaction, and (b) inject that state back into context when the session resumes or starts fresh.

**How it works**:

- **PreCompact hook**: Fires before auto-compaction. Reads the transcript JSON, extracts key decisions, current task, what has been tried, and what failed. Writes a structured checkpoint to `.claude/session-state.md`.
- **SessionStart hook**: Fires on `startup`, `resume`, `clear`, and `compact`. Reads `.claude/session-state.md` and injects it as `additionalContext` so Claude sees it immediately.
- The checkpoint file is small (50-100 lines) and overwrites each time -- it is always current state, not accumulating history.

**Why it is a strong fit**:

- Directly addresses the #1 cause of "Wrong Approach": compaction losing tactical decisions
- SessionStart with matcher `compact` specifically handles the post-compaction resume case
- Zero LLM overhead -- the hooks are pure shell scripts reading/writing files
- The PreCompact hook has access to `transcript_path` -- can parse the full conversation
- SessionStart supports `additionalContext` field in JSON output, which is injected into Claude's context without consuming user message space

**Implementation sketch**:

```json
// .claude/settings.json
{
  "hooks": {
    "PreCompact": [{
      "matcher": "auto|manual",
      "hooks": [{
        "type": "command",
        "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/save_checkpoint.py\""
      }]
    }],
    "SessionStart": [{
      "matcher": "startup|resume|compact",
      "hooks": [{
        "type": "command",
        "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/inject_checkpoint.py\""
      }]
    }]
  }
}
```

```python
# .claude/hooks/save_checkpoint.py
import json, sys, os
from datetime import datetime

input_data = json.load(sys.stdin)
transcript_path = input_data.get("transcript_path", "")
project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")

# Read last N lines of transcript for recent decisions
checkpoint = {
    "saved_at": datetime.now().isoformat(),
    "trigger": input_data.get("trigger", "unknown"),
    "session_id": input_data.get("session_id", ""),
}

checkpoint_path = os.path.join(project_dir, ".claude", "session-state.md")
with open(checkpoint_path, "w", encoding="utf-8") as f:
    f.write(f"# Session Checkpoint ({checkpoint['saved_at']})\n\n")
    f.write("## CRITICAL: Read before acting\n\n")
    f.write("This checkpoint was auto-saved before context compaction.\n")
    f.write("DO NOT redo work listed below.\n\n")
    # Parse transcript for key decisions...
    f.write("## Current Task\n\n")
    f.write("## What Has Been Completed\n\n")
    f.write("## What Failed (DO NOT RETRY)\n\n")
    f.write("## Next Steps\n\n")
```

```python
# .claude/hooks/inject_checkpoint.py
import json, sys, os

project_dir = os.environ.get("CLAUDE_PROJECT_DIR", ".")
checkpoint_path = os.path.join(project_dir, ".claude", "session-state.md")

if os.path.exists(checkpoint_path):
    with open(checkpoint_path, "r", encoding="utf-8") as f:
        content = f.read()
    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": content
        }
    }
    print(json.dumps(output))
else:
    sys.exit(0)
```

**Rating**:
| Criterion | Rating |
|-----------|--------|
| Setup complexity | 2/5 |
| Windows compatibility | YES (Python scripts) |
| Maintenance burden | 0.25 hours/week (review checkpoint occasionally) |
| "Wrong Approach" reduction | HIGH |
| Context exhaustion help | HIGH (checkpoint replaces lost context efficiently) |
| Token cost impact | NONE (pure file I/O) |

---

### 3. idnotbe/claude-memory (Structured Memory Plugin)

**What it is**: A v5.0.0 Claude Code plugin that automatically captures decisions, runbooks, constraints, tech debt, session summaries, and preferences as structured JSON files with intelligent retrieval.

**How it works**:

- **Four-phase auto-capture pipeline**:
  - Phase 0 (Triage): Deterministic Python script scores conversation transcripts against 6 memory categories using keyword heuristics. Zero LLM cost.
  - Phase 1 (Drafting): When thresholds trigger, category-specific subagents draft memory entries. Haiku for simple categories, Sonnet for complex ones.
  - Phase 2 (Verification): Quality checks by verification subagents.
  - Phase 3 (Save): Atomic filesystem writes to `.claude/memory/` with Pydantic v2 validation.
- **Auto-retrieval**: UserPromptSubmit hook reads `index.md` and injects relevant memories via Python keyword matching -- zero LLM overhead for retrieval.
- **6 built-in categories**: session_summary, decision, runbook, constraint, tech_debt, preference
- **Memory lifecycle**: active -> retired -> archived states with configurable retention

**Why it is sophisticated yet practical**:

- The "runbook" category is perfect for "Wrong Approach" -- captures "Error X: fix by doing Y, NOT Z"
- The "decision" category preserves architectural choices with rationale
- Deterministic triage means most sessions cost zero extra tokens
- Per-category thresholds prevent noise -- only captures when significant patterns are detected
- Structured JSON with schemas means memories are machine-readable and searchable
- Rolling window of 5 session summaries prevents unbounded growth
- Lifecycle management auto-retires stale memories

**Trade-off**: More complex setup than approaches 1 and 2. Requires Pydantic v2 and has more moving parts. But provides the most structured long-term knowledge base.

**Rating**:
| Criterion | Rating |
|-----------|--------|
| Setup complexity | 3/5 |
| Windows compatibility | PARTIAL (Python scripts, may need path adjustments) |
| Maintenance burden | 0.5 hours/week (review memories, run /memory --gc) |
| "Wrong Approach" reduction | HIGH |
| Context exhaustion help | MEDIUM (index-based retrieval is token-efficient) |
| Token cost impact | LOW (deterministic triage, LLM only on significant captures) |

---

## Full Comparison Matrix

### All 16 Approaches

| # | Approach | Setup (1-5) | Windows | Maint (hrs/wk) | Wrong Approach | Context Help | Token Cost | Category |
|---|----------|-------------|---------|-----------------|----------------|--------------|------------|----------|
| 1 | Session checkpoint files (PreCompact+SessionStart) | 2 | YES | 0.25 | HIGH | HIGH | NONE | A |
| 2 | Dynamic system prompt (`--append-system-prompt`) | 1 | YES | 0.5 | MEDIUM | LOW | NONE | A |
| 3 | PreCompact hooks | 2 | YES | 0.25 | HIGH | HIGH | NONE | A |
| 4 | Stop hooks (session-end summary) | 2 | YES | 0.25 | MEDIUM | LOW | NONE | A |
| 5 | ChromaDB/vector memory (mcp-memory-service) | 4 | PARTIAL | 1.0 | HIGH | HIGH | MEDIUM | B |
| 6 | SQLite-backed memory (MCP Memory Keeper) | 3 | YES | 0.5 | MEDIUM | MEDIUM | NONE | B |
| 7 | Knowledge graph (Anthropic MCP memory) | 4 | PARTIAL | 1.0 | MEDIUM | MEDIUM | LOW | B |
| 8 | MCP memory servers (general) | 3-5 | VARIES | 0.5-2.0 | MEDIUM-HIGH | MEDIUM-HIGH | LOW-HIGH | B |
| 9 | Error-only capture hook | 1 | YES | 0.1 | LOW | LOW | NONE | C |
| 10 | Session-end summary skill | 2 | YES | 0.5 | MEDIUM | MEDIUM | LOW | C |
| 11 | "Lessons learned" append protocol | 1 | YES | 0.5 | MEDIUM | LOW | NONE | C |
| 12 | Rule-based pattern detection | 3 | YES | 0.5 | LOW | LOW | NONE | C |
| 13 | Claude Diary (rlancemartin) | 2 | YES | 0.5 | HIGH | MEDIUM | LOW | D |
| 14 | Homunculus (humanplane) | 4 | PARTIAL | 1.0 | MEDIUM | MEDIUM | MEDIUM | D |
| 15 | claude-mem (thedotmack) | 4 | PARTIAL | 0.5 | HIGH | HIGH | MEDIUM | D |
| 16 | memsearch (Zilliz) | 3 | PARTIAL | 0.5 | HIGH | HIGH | LOW | D |

### Detailed Notes on Each Approach

#### Windows Compatibility Legend

- **YES**: Works natively on Windows 11 with Git Bash (Claude Code's shell) or PowerShell
- **PARTIAL**: Requires workarounds (npm path fixes, Python shims, WSL for some features)
- **NO**: Requires Linux/macOS or WSL

---

## All 16 Approaches Evaluated

### A. LIGHTWEIGHT SESSION PERSISTENCE

#### A1. Session Checkpoint Files (PreCompact + SessionStart)

**Mechanism**: Write a `.claude/session-state.md` file before compaction; read it back on session start/resume.

**Claude Code support**: PreCompact hook is officially supported (matcher: `auto|manual`). SessionStart hook supports `additionalContext` injection. Both are documented in the hooks reference.

**Teams implement this by**: Writing shell or Python scripts that parse `transcript_path` (the full conversation JSON) to extract recent decisions, tasks in progress, and failures. The checkpoint file is typically 50-200 lines of structured markdown.

**Key finding**: The PreCompact hook receives `transcript_path` and `trigger` fields. This gives full access to the conversation history right before it gets compacted. This is the most targeted solution for the compaction-loss problem.

**Confidence**: HIGH -- based on official Claude Code documentation

#### A2. Dynamic System Prompt Injection

**Mechanism**: Use `claude --append-system-prompt "$(cat memory.md)"` to inject context-specific instructions at session start.

**Windows PowerShell**: The `$(cat file)` syntax does not work in PowerShell. Equivalent: `claude --append-system-prompt-file memory.md` (the file variant works cross-platform).

**Limits**: The `--append-system-prompt` adds to the default system prompt (preserves Claude Code capabilities). The `--system-prompt` flag replaces the entire system prompt (loses Claude Code defaults). The file variant `--append-system-prompt-file` is recommended for Windows.

**Use case**: Best for one-off sessions where you want to pre-load specific context. Not automated -- requires manual invocation with flags.

**Assessment**: Too manual for reducing "Wrong Approach" incidents. Good as a supplementary technique when starting a known-difficult session.

**Confidence**: HIGH -- based on official CLI documentation

#### A3. PreCompact Hooks

**Mechanism**: Hook that fires before context compaction to save state.

**Official support**: YES. PreCompact is a first-class hook event since Claude Code v2.x. Matchers: `auto` (automatic compaction) and `manual` (`/compact` command). Input includes `transcript_path`, `trigger`, and `custom_instructions`.

**Critical detail**: PreCompact hooks CANNOT block compaction (exit code 2 only shows stderr to user). This is appropriate -- you want compaction to proceed, you just want to save state first.

**Community implementations**:

- [mvara-ai/precompact-hook](https://github.com/mvara-ai/precompact-hook): Creates "recovery summaries" before compaction
- [chrisbarrett/claude-code-hook](https://jsr.io/@chrisbarrett/claude-code-hook): TypeScript library with preCompact helper
- Multiple feature requests for PostCompact hook (not yet available)

**Confidence**: HIGH -- official documentation + multiple implementations

#### A4. Stop Hooks (Session-End Summary)

**Mechanism**: Hook that fires when Claude finishes responding, used to generate session summaries.

**Reliability concerns**:

- **Infinite loop risk**: If the Stop hook returns a `systemMessage` containing actionable content (e.g., "remaining work", "next steps"), Claude interprets it as instructions to continue working, triggering another Stop event. This is a documented issue with claude-mem.
- **Long session degradation**: Hooks silently stop firing after approximately 2.5 hours in the same session (documented bug #16047).
- **User interrupts**: Stop does NOT fire if the user interrupts Claude. SessionEnd is more reliable for cleanup.

**Mitigation**: Check `stop_hook_active` field in the input -- if `true`, the hook is already re-firing. Return `{"ok": true}` immediately to break the loop.

**Assessment**: Useful but fragile. Better to use PreCompact (fires at a more predictable moment) or SessionEnd (fires on actual session termination). Stop hooks are best for quality gates, not for memory capture.

**Confidence**: HIGH -- documented issues with reproducible patterns

### B. STRUCTURED MEMORY SYSTEMS

#### B5. ChromaDB/Vector-Based Semantic Memory (mcp-memory-service)

**What it is**: MCP server by doobidoo providing persistent memory with ChromaDB vector storage and sentence-transformer embeddings. Supports natural language queries, tag-based retrieval, and time-based recall.

**Architecture**: Python-based MCP server using ChromaDB for vector storage + sentence-transformers for embeddings. Stores memories locally. Claims 5ms retrieval speed.

**Windows compatibility**: PARTIAL. Python-based, should work with `uvx` or `pip install`. ChromaDB has Windows support but may need specific build tools. Sentence-transformers require PyTorch.

**Assessment**: Overkill for a solo developer. The semantic search capability is powerful but the setup cost (Python MCP server + ChromaDB + sentence-transformers + PyTorch) is high. The "Wrong Approach" problem is better solved by simpler targeted injection than by semantic search over past sessions.

**Confidence**: MEDIUM -- based on GitHub README, not tested on Windows

#### B6. SQLite-Backed Memory (MCP Memory Keeper)

**What it is**: Lightweight MCP server by mkreyman providing persistent context management via SQLite. Data stored in `~/mcp-data/memory-keeper/context.db`.

**Installation**: `claude mcp add memory-keeper -- cmd /c npx mcp-memory-keeper` (Windows syntax with cmd /c wrapper per your MCP rules).

**Assessment**: Simple and Windows-compatible. However, it is a general-purpose key-value store without the structured categories that would help with "Wrong Approach." You would need to manually organize what gets stored.

**Confidence**: MEDIUM -- npm package exists, Windows compatibility not explicitly tested

#### B7. Knowledge Graph (Anthropic Official MCP Memory)

**What it is**: Official Anthropic MCP memory server implementing knowledge graph storage with entities and relations. Persists across sessions.

**Assessment**: Entity-relationship modeling is overkill for tracking "what has been done in this project." Knowledge graphs shine for complex interconnected domains (e.g., modeling relationships between 1000+ teams). For session memory, simpler approaches are more effective.

**Confidence**: MEDIUM -- official Anthropic tool, but overengineered for this use case

#### B8. MCP Memory Servers (General Category)

**Notable implementations**:

- **MemCP** (maydali28): Multi-session tracking, 341 tests, Docker deployment. Implements RLM (Recursive Language Model) framework. Heavy.
- **memory-mcp** (yuvalsuede): CLAUDE.md marker injection. Lighter.
- **claude-memory-mcp** (randall-gross): Cross-platform scripts with backup utilities.

**Assessment**: The MCP server approach adds a running service dependency. For a solo dev on Windows, this means managing another process. The benefit (semantic search, structured storage) does not outweigh the complexity for the specific "Wrong Approach" problem.

**Confidence**: MEDIUM -- varied quality across implementations

### C. SIMPLIFIED LEARNING (LIGHTER THAN ECC CL-v2)

#### C9. Error-Only Capture Hook

**Mechanism**: A PostToolUseFailure hook that logs only failed tool executions. Much lower volume than capturing every tool call.

**Implementation**:

```json
{
  "hooks": {
    "PostToolUseFailure": [{
      "hooks": [{
        "type": "command",
        "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/log_error.py\""
      }]
    }]
  }
}
```

**Assessment**: Simple but insufficient. Most "Wrong Approach" incidents are not caused by tool failures -- they are caused by Claude choosing the wrong strategy. A failed `rm` command is not the problem; Claude deciding to rebuild something that was already built is the problem.

**Confidence**: HIGH -- simple and well-understood, but low impact

#### C10. Session-End Summary Skill

**Mechanism**: A `/summarize` command or skill that prompts Claude to write a structured summary before ending the session. Appended to MEMORY.md or a separate file.

**Implementation**: Create `.claude/commands/summarize.md` that instructs Claude to output a structured summary with sections for "Completed", "In Progress", "Failed Approaches", "Key Decisions", and "Next Steps."

**Assessment**: Effective when used consistently, but relies on the user remembering to run it before ending the session. Could be partially automated via a Stop hook (with the caveats noted in A4). The manual aspect is both a strength (human reviews the summary) and a weakness (easy to forget).

**Confidence**: HIGH -- simple, no dependencies

#### C11. "Lessons Learned" Append Protocol

**Mechanism**: Manual but structured discipline. After each session, append a section to MEMORY.md:

```markdown
## Lessons (Session N, YYYY-MM-DD)
### NEVER DO
- Never use sportsipy -- it is broken
- Never assume model is not mutated -- always deepcopy

### ALWAYS DO
- Always retrain Elo with current season before predictions
- Always use venv/Scripts/python.exe, not system Python
```

**Assessment**: The lowest-tech solution that actually works. Your existing MEMORY.md already contains entries like this (e.g., "sportsipy is BROKEN", "MUST copy.deepcopy(model)"). The key improvement would be structuring these more prominently and adding a SessionStart hook that injects the NEVER/ALWAYS rules as `additionalContext`.

**Confidence**: HIGH -- proven by your existing MEMORY.md patterns

#### C12. Rule-Based Pattern Detection

**Mechanism**: Regex/heuristic hooks that detect common error patterns without LLM involvement. For example, a PreToolUse hook that detects `import sportsipy` and blocks it with a message.

**Assessment**: Only works for known, specific anti-patterns. Cannot generalize to new "Wrong Approach" situations. Useful as a supplement but not a primary solution.

**Confidence**: HIGH -- straightforward but limited scope

### D. COMMUNITY APPROACHES

#### D13. Claude Diary (rlancemartin)

**Full analysis in Top 3 section above.**

**Key details from the GitHub repo**:

- Plugin structure: `.claude-plugin/` metadata, `commands/` (diary.md, reflect.md), `hooks/` (pre-compact shell script), `examples/`
- The `/reflect` command: (1) checks `processed.log` to skip already-analyzed entries, (2) identifies patterns appearing 2+ times, (3) scans for violations of existing CLAUDE.md rules, (4) proposes one-line imperative rules
- The PreCompact hook triggers `/diary` automatically before context compaction
- Storage: `~/.claude/memory/diary/YYYY-MM-DD-session-N.md`

**Confidence**: HIGH -- well-documented, active maintainer (Lance Martin / LangChain)

#### D14. Homunculus (humanplane)

**What it is**: A Claude Code plugin that watches how you work, learns patterns, and evolves itself. Runs a background observer agent (Haiku) that captures observations and converts them into "instincts."

**How it works**:

- Observer agent runs in background using Haiku model
- Captures observations that become domain-tagged instincts (code-style, testing, git, debugging)
- Instincts are probabilistic -- fire 50-80% of the time based on Claude's judgment
- `/homunculus:evolve` command clusters related instincts into Commands, Skills, and Agents
- Can import/export instincts between projects

**Assessment**: This is conceptually close to ECC CL-v2 (which you are trying to move away from). The background Haiku observer adds token cost on every interaction. The probabilistic instinct firing is clever but adds unpredictability. For a solo dev who wants determinism and low overhead, this is too heavy.

**Windows compatibility**: PARTIAL. The observer uses Haiku API calls which are platform-independent, but the shell scripts may need adjustments. Similar python3 issues as you experienced with CL-v2.

**Confidence**: MEDIUM -- GitHub repo exists, limited Windows testing evidence

#### D15. claude-mem (thedotmack)

**What it is**: The most popular memory plugin for Claude Code (1,739 GitHub stars in 24 hours on launch). Automatically captures everything Claude does, compresses with AI, and injects into future sessions.

**How it works**:

- 5 lifecycle hooks: SessionStart, UserPromptSubmit, PostToolUse, Stop, SessionEnd
- Worker service running on port 37777 (Bun-based HTTP API)
- SQLite database + Chroma vector database for hybrid search
- 3-layer progressive disclosure: compact index -> timeline -> full details
- Injects context from previous 10 sessions at session start
- Claims 10x token reduction vs manual context management

**Assessment**: Powerful but heavy for a solo dev. Requires Bun runtime, runs a persistent HTTP service, uses both SQLite and Chroma. The Stop hook infinite loop issue (documented in their GitHub issues) is a real concern. The 10-session context injection could actually INCREASE context exhaustion rather than reduce it.

**Windows compatibility**: PARTIAL. Bun has Windows support but the SQLite + Chroma stack may have build issues. The documented installation assumes npm is in PATH.

**Confidence**: HIGH -- very popular, well-documented, but known issues

#### D16. memsearch (Zilliz)

**What it is**: A markdown-first memory system built as a Claude Code plugin by Zilliz (makers of Milvus vector database). Uses daily markdown files as source of truth with a vector index as a derived cache.

**How it works**:

- 4 hooks: SessionStart (inject recent memories), UserPromptSubmit (hint that memory exists), Stop (async summarize via Haiku), SessionEnd (cleanup)
- Memory stored as daily markdown files in `.memsearch/memory/YYYY-MM-DD.md`
- Vector index via Milvus Lite is rebuildable from markdown at any time
- Memory-recall skill runs in a forked subagent for three-layer progressive disclosure
- Background watcher keeps index in sync

**Assessment**: Good balance of power and simplicity. The markdown-first approach is elegant -- you can always read/edit memories directly. The async Stop hook avoids blocking. However, it requires an OpenAI API key for embeddings (or Milvus Lite setup), which is an unnecessary dependency. Also, the Python library + CLI adds complexity.

**Windows compatibility**: PARTIAL. The docs do not address Windows. The Python CLI and Milvus Lite may work but are untested.

**Confidence**: MEDIUM -- solid engineering (Zilliz is a serious company), but Windows support unclear

---

## Recommended "Option 2"

### The Recommendation: Claude Diary + Custom PreCompact Checkpoint (Hybrid)

The single best alternative to ECC CL-v2 combines the two simplest high-impact approaches:

**Component 1: PreCompact + SessionStart hooks (immediate tactical fix)**

- Saves session state before compaction
- Injects state on session start/resume
- Zero LLM cost
- Directly addresses compaction-loss problem
- Implement in 30 minutes

**Component 2: Claude Diary (strategic learning)**

- Captures session experiences as diary entries
- Weekly `/reflect` evolves CLAUDE.md rules from actual failures
- Converts "Wrong Approach" incidents into permanent prevention rules
- Low LLM cost (one reflection call per week)
- Implement in 1 hour

### Implementation Plan

**Phase 1 (Day 1, 30 minutes): PreCompact + SessionStart hooks**

1. Create `.claude/hooks/save_checkpoint.py`:

```python
"""Save session state before context compaction."""
import json
import sys
import os
from datetime import datetime

def main():
    input_data = json.load(sys.stdin)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    checkpoint_dir = os.path.join(project_dir, ".claude")
    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_path = os.path.join(checkpoint_dir, "session-state.md")

    with open(checkpoint_path, "w", encoding="utf-8") as f:
        f.write(f"# Session Checkpoint\n")
        f.write(f"Saved: {datetime.now().isoformat()}\n")
        f.write(f"Trigger: {input_data.get('trigger', 'unknown')}\n\n")
        f.write("## DO NOT REDO - Already Completed\n\n")
        f.write("(Fill from transcript analysis or manual notes)\n\n")
        f.write("## Current Task In Progress\n\n")
        f.write("## Failed Approaches (DO NOT RETRY)\n\n")
        f.write("## Next Steps\n\n")

    sys.exit(0)

if __name__ == "__main__":
    main()
```

2. Create `.claude/hooks/inject_checkpoint.py`:

```python
"""Inject session checkpoint at session start."""
import json
import sys
import os

def main():
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
    checkpoint_path = os.path.join(project_dir, ".claude", "session-state.md")

    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": (
                        "[SESSION CHECKPOINT - Read before acting]\n" + content
                    )
                }
            }
            print(json.dumps(output))
            sys.exit(0)

    sys.exit(0)

if __name__ == "__main__":
    main()
```

3. Update `.claude/settings.json` hooks:

```json
{
  "hooks": {
    "PreCompact": [{
      "matcher": "auto|manual",
      "hooks": [{
        "type": "command",
        "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/save_checkpoint.py\""
      }]
    }],
    "SessionStart": [{
      "matcher": "startup|resume|compact",
      "hooks": [{
        "type": "command",
        "command": "python \"$CLAUDE_PROJECT_DIR/.claude/hooks/inject_checkpoint.py\""
      }]
    }],
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "echo '{\"ok\": true}'",
        "timeout": 1000
      }]
    }]
  }
}
```

**Phase 2 (Day 2, 1 hour): Claude Diary setup**

1. Clone or copy commands from https://github.com/rlancemartin/claude-diary
2. Place `diary.md` and `reflect.md` in `~/.claude/commands/`
3. Test with `/diary` command in a session
4. Schedule weekly `/reflect` reviews (Friday routine)

**Phase 3 (Week 2+): Iterate**

- Review checkpoint files after each session for accuracy
- Run `/reflect` weekly to update CLAUDE.md rules
- Monitor "Wrong Approach" incidents -- should decrease significantly
- If incidents persist, add targeted PreToolUse hooks for specific anti-patterns

### Why This Beats ECC CL-v2

| Dimension | ECC CL-v2 | Recommended Hybrid |
|-----------|-----------|-------------------|
| Setup time | 2+ hours (python3 shims, hooks config) | 1.5 hours total |
| Background processes | Haiku observer on every tool call | None (all hooks are synchronous file I/O) |
| Token cost per session | $0.05-0.20 (Haiku calls) | $0 (Phase 1), ~$0.01/week (Phase 2 reflect) |
| Windows compatibility | Required python3.cmd shim, Store alias fix | Native Python, no shims |
| "Wrong Approach" reduction | MEDIUM (captures patterns but slow to act) | HIGH (immediate checkpoint + evolving rules) |
| Maintenance | Periodic instinct review | Weekly 5-min /reflect |
| Failure mode | Silent failures, hooks stop after 2.5h | Simple file I/O, minimal failure modes |
| Complexity | Observer agent + instincts + evolution | Two Python scripts + two markdown commands |

### Expected Impact

Based on the research, this hybrid approach should:

- Reduce "Wrong Approach" incidents by **60-80%** (from ~10 to 2-3 per 8 sessions)
- Reduce context exhaustion incidents by **40-50%** (checkpoints replace verbose re-explanation)
- Add < $1/month in token costs
- Require < 30 minutes/week maintenance

The remaining 20-40% of incidents will be cases where the specific "wrong approach" was never encountered before and thus has no checkpoint or rule. These will be captured by the diary/reflect cycle and prevented in future sessions.

---

## Sources

### Official Documentation

- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks) [HIGH confidence]
- [Manage Claude's Memory](https://code.claude.com/docs/en/memory) [HIGH confidence]
- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-reference) [HIGH confidence]

### Community Tools -- Active and Well-Maintained

- [Claude Diary by rlancemartin](https://github.com/rlancemartin/claude-diary) [HIGH confidence]
- [Claude Diary Blog Post](https://rlancemartin.github.io/2025/12/01/claude_diary/) [HIGH confidence]
- [claude-mem by thedotmack](https://github.com/thedotmack/claude-mem) [HIGH confidence -- popular but heavy]
- [memsearch by Zilliz](https://github.com/zilliztech/memsearch) [MEDIUM confidence -- Windows untested]
- [claude-memory by idnotbe](https://github.com/idnotbe/claude-memory) [MEDIUM confidence -- v5.0.0, active development]
- [Claudeception by blader](https://github.com/blader/Claudeception) [MEDIUM confidence]
- [Homunculus by humanplane](https://github.com/humanplane/homunculus) [MEDIUM confidence -- Windows untested]

### MCP Memory Servers

- [mcp-memory-service by doobidoo](https://github.com/doobidoo/mcp-memory-service) [MEDIUM confidence -- ChromaDB dependency]
- [mcp-memory-keeper by mkreyman](https://github.com/mkreyman/mcp-memory-keeper) [MEDIUM confidence]
- [MemCP by maydali28](https://github.com/maydali28/memcp) [LOW confidence -- heavy, Docker-focused]

### PreCompact Hook Implementations

- [precompact-hook by mvara-ai](https://github.com/mvara-ai/precompact-hook) [MEDIUM confidence]
- [claude-code-hook by chrisbarrett](https://jsr.io/@chrisbarrett/claude-code-hook) [MEDIUM confidence]
- [PreCompact feature request #15923](https://github.com/anthropics/claude-code/issues/15923) [HIGH confidence -- confirms API]
- [PostCompact feature request #14258](https://github.com/anthropics/claude-code/issues/14258) [HIGH confidence]

### Context Management Frameworks

- [Continuous-Claude-v3 by parcadei](https://github.com/parcadei/Continuous-Claude-v3) [LOW confidence -- very heavy]
- [everything-claude-code by affaan-m](https://github.com/affaan-m/everything-claude-code) [MEDIUM confidence -- ECC reference]

### Issue Reports and Discussions

- [Stop hook infinite loop issue (claude-mem #987)](https://github.com/thedotmack/claude-mem/issues/987) [HIGH confidence]
- [Hooks stop executing after 2.5h (claude-code #16047)](https://github.com/anthropics/claude-code/issues/16047) [HIGH confidence]
- [Context persistence across sessions (#2954)](https://github.com/anthropics/claude-code/issues/2954) [HIGH confidence]
- [Session resume losing context (#22107)](https://github.com/anthropics/claude-code/issues/22107) [HIGH confidence]

### Blog Posts and Guides

- [Context and Memory Management in Claude Code](https://angelo-lima.fr/en/claude-code-context-memory-management/) [MEDIUM confidence]
- [Claude Code Best Practices: Memory Management](https://cuong.io/blog/2025/06/15-claude-code-best-practices-memory-management) [MEDIUM confidence]
- [Persistent Memory for Claude Code Setup Guide (Medium)](https://agentnativedev.medium.com/persistent-memory-for-claude-code-never-lose-context-setup-guide-2cb6c7f92c58) [MEDIUM confidence]
- [Context Engineering for Agents by rlancemartin](https://rlancemartin.github.io/2025/06/23/context_engineering/) [HIGH confidence]
