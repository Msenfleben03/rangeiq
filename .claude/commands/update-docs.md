---
description: Comprehensively sync all documentation with the current codebase after a development session
argument-hint: [focus-area]
---

# Update Documentation

Sync all project documentation with the codebase source-of-truth
after a development session. Fix incorrect counts/references and
report discrepancies.

## What This Command Does

1. **Discover changes**: Identify what changed since last doc update
2. **Read source-of-truth**: Extract ground truth from code, config, and tests
3. **Audit documentation**: Cross-reference every doc against the codebase
4. **Fix discrepancies**: Update stale counts, references, and descriptions
5. **Check staleness**: Flag docs not modified in 90+ days
6. **Report**: Show diff summary of all changes made

## Usage

```bash
# Full documentation sync
/update-docs

# Focus on a specific area
/update-docs tests
/update-docs codemaps
/update-docs env-vars
```

## Implementation Steps

When this command is invoked:

### 1. Discover What Changed

Run these commands in parallel to understand the current state:

```bash
git status --short -u
git log --oneline -20
git diff --name-only HEAD~5
```

Check the argument: if a focus area is provided (e.g., `tests`,
`codemaps`, `env-vars`), limit the audit to that area.
Otherwise, run the full audit.

### 2. Read Source-of-Truth Files

Read all source-of-truth files in parallel. These are the authoritative sources:

| Source File | What It Defines |
|-------------|-----------------|
| `.env.example` | All environment variables, their defaults, and purposes |
| `requirements.txt` or `pyproject.toml` | All project dependencies |
| `config/constants.py` | Threshold values, dataclass configs, magic numbers |
| `config/settings.py` | Path configs, bankroll settings, risk limits |
| `tracking/database.py` | Database schema (all `CREATE TABLE` statements) |
| `tests/` directory | Test counts per file (grep for `def test_` across all test files) |
| `scripts/` directory | All entry-point scripts and their CLI arguments |

For test counts, run:

```bash
grep -r "def test_" tests/ --include="*.py" -c
```

This produces the ground-truth test count per file.

### 3. Audit Core Documentation

Read and cross-reference each documentation file against source-of-truth:

#### A. CONTRIB.md (Development Guide)

Check these sections against source files:

- **Environment variables table** matches `.env.example` — every variable present, correct defaults
- **Available scripts table** matches actual files in `scripts/` — no missing or removed scripts
- **Test counts** match grep results from step 2 — total count, per-category counts
- **Dependencies** match `requirements.txt` — no removed or added packages missing
- **Project structure** reflects current directory layout

#### B. RUNBOOK.md (Operations Guide)

Check these sections:

- **Threshold values** match `config/constants.py` — daily exposure, weekly loss, monthly loss, max bet
- **Script commands** reference existing scripts with correct arguments
- **Alert conditions** match actual code in `tracking/reports.py` or equivalent
- **Database tables** referenced actually exist in schema

#### C. Codemaps (docs/CODEMAPS/)

For each codemap file:

- **File counts** in module tables match actual file count in that directory
- **Test counts** match grep results
- **Export lists** match actual public functions/classes in source files
- **Dependency references** are still accurate
- **Architecture diagrams** reflect current module structure

#### D. DATA_DICTIONARY.md

- Every `CREATE TABLE` in `tracking/database.py` has a corresponding entry
- Column descriptions match actual schema
- No tables documented that no longer exist

#### E. Other docs (ARCHITECTURE.md, QUICKSTART.md, etc.)

- Numeric references (test counts, file counts, table counts) are accurate
- Script paths and command examples still work
- Referenced files still exist

### 4. Fix Discrepancies

For each discrepancy found:

1. Use the Edit tool to fix the specific value (prefer targeted edits over full rewrites)
2. Track what was changed for the diff summary

Common fixes:

- **Test counts**: Update total and per-file counts across all docs that reference them
- **Env vars**: Add missing variables to tables, remove deleted ones
- **Thresholds**: Sync numeric values with `config/constants.py`
- **Script references**: Update paths, arguments, and descriptions
- **Schema**: Add missing tables, update column lists

Use Grep to find all occurrences of a stale value before fixing:

```bash
# Example: find all docs referencing an old test count
grep -r "289" docs/ --include="*.md"
```

Fix ALL occurrences, not just the first one found.

### 5. Check Documentation Staleness

Get last-modified dates for all documentation files:

```bash
for file in docs/*.md docs/**/*.md; do
  echo "$(git log -1 --format='%ai' -- "$file" 2>/dev/null || echo 'untracked') $file"
done
```

Flag files in three categories:

- **STALE (90+ days)**: Not modified in 90+ days — recommend review or removal
- **AGING (30-89 days)**: May be drifting from codebase — check key facts
- **CURRENT (<30 days)**: Recently updated — spot-check only

For stale files, check if they reference code that has changed since their last update.

### 6. Lint Check

If markdownlint pre-commit hook exists, verify changes pass:

- Fenced code blocks have language specifiers
  (`text` for ASCII art, `bash` for commands, `python` for code)
- Lines do not exceed 120 characters (wrap long descriptions)
- No emphasis used as headings (use `##` instead of `**bold text**`)

### 7. Report Results

Output a structured summary:

```text
## Documentation Sync Report

### Files Modified
| File | Changes |
|------|---------|
| docs/CONTRIB.md | [specific changes] |
| ... | ... |

### Source-of-Truth Sync Status
| Source | Status |
|--------|--------|
| .env.example | In sync / X discrepancies |
| config/constants.py | In sync / X discrepancies |
| ... | ... |

### Staleness Report
| Status | Count | Files |
|--------|-------|-------|
| STALE (90+ days) | X | [list] |
| AGING (30-89 days) | X | [list] |
| CURRENT (<30 days) | X | [list] |

### Flagged for Manual Review
- [files that may need human attention]
```

## Important Notes

- **Read before editing**: Always read a file with the Read tool before making changes
- **Targeted edits only**: Use Edit tool for specific fixes, not full file rewrites
- **Grep for all occurrences**: A stale value (like a test count) may appear in 5+ files
- **Do NOT update CLAUDE.md**: That file has its own update process
- **Do NOT modify source code**: This command only updates documentation files
- **Preserve formatting**: Match the existing style of each doc (tables, headers, code blocks)
- **Parallel reads**: Read source-of-truth files in parallel for efficiency

## Error Handling

If a source-of-truth file does not exist:

- Skip that check and note it in the report
- Do NOT create missing source files

If a documentation file has conflicting information:

- Trust the source code over the documentation
- Fix the documentation to match the code
- Note the discrepancy in the report

## Success Criteria

**DONE** when:

- All documentation files checked against source-of-truth
- All numeric references (test counts, thresholds, file counts) verified or corrected
- Staleness report generated
- Diff summary presented to user
