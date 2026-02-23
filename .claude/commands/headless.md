---
argument-hint: "<task: daily|nightly|settle|test|validate|backtest|custom> [options]"
---

# /headless — Launch Non-Interactive Claude Code Execution

Generate and execute optimized headless (`-p` mode) commands for the sports-betting project.
Routes to the correct agents, skills, tools, and permission modes based on the task.

## Usage

```
/headless daily              # Daily paper betting pipeline
/headless nightly            # Nightly data refresh + retrain
/headless settle             # Evening bet settlement
/headless test               # Run test suite with auto-fix
/headless validate           # Gatekeeper model validation
/headless backtest           # Walk-forward backtest
/headless custom "<prompt>"  # Custom headless task
```

## Instructions

When the user invokes `/headless <task>`, build and execute the appropriate command.

### Task Routing Table

| Task | Agent | Skills | Plugins | Permission Mode | Max Turns |
|------|-------|--------|---------|-----------------|-----------|
| `daily` | `quant-analyst` | `odds-retrieval`, `statistical-analysis` | `data-validation-suite`, `python-development` | allowedTools whitelist | 10 |
| `nightly` | `data-scientist` | `senior-data-engineer`, `matplotlib` | `data-engineering`, `python-development` | allowedTools whitelist | 8 |
| `settle` | `data-analyst` | `statistical-analysis` | `data-validation-suite` | allowedTools whitelist | 3 |
| `test` | `senior-qa` | `test-driven-development`, `systematic-debugging`, `find-bugs` | `python-development` | dangerously-skip-permissions | 15 |
| `validate` | `quant-analyst` | `statistical-analysis`, `verification-before-completion` | `data-validation-suite` | allowedTools whitelist | 5 |
| `backtest` | `data-scientist` | `senior-data-scientist`, `statistical-analysis`, `matplotlib` | `data-engineering`, `python-development` | allowedTools whitelist | 12 |

### MCP Servers Available

| Server | Config | Use Case |
|--------|--------|----------|
| `zai-mcp-server` | `.mcp.json` | Z.AI image generation (dashboards) |

### Common Tool Whitelists

**Read-Only (reports, validation):**
```
--allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" "Glob" "Grep"
```

**Read-Write (fixes, retrain):**
```
--allowedTools "Bash(venv/Scripts/python.exe:*)" "Bash(pytest:*)" "Read" "Write" "Edit" "Glob" "Grep"
```

**Full Pipeline (daily/nightly):**
```
--allowedTools "Bash(venv/Scripts/python.exe:*)" "Bash(sqlite3:*)" "Read" "Write" "Glob" "Grep"
```

### Build the Command

For each task, construct the PowerShell command following this template:

```powershell
$ProjectRoot = "C:\Users\msenf\sports-betting"
Set-Location $ProjectRoot

claude -p `
    --output-format json `
    --max-turns <TURNS> `
    <PERMISSION_FLAGS> `
    --append-system-prompt "<AGENT_PERSONA + SKILL_CONTEXT>" `
    "<TASK_PROMPT>"
```

### Agent Persona Injection

Read the relevant `.claude/agents/<agent>.md` file and inject key instructions
into `--append-system-prompt`. Keep it under 500 tokens. Format:

```
You are the <agent-name> agent for the sports-betting project.
Key skills: <skill-list>.
Active plugins: <plugin-list>.
CRITICAL: Always use venv/Scripts/python.exe, never system Python.
Working directory: C:\Users\msenf\sports-betting
```

### Task: `daily`

```powershell
claude -p `
    --output-format json `
    --max-turns 10 `
    --allowedTools "Bash(venv/Scripts/python.exe:*)" "Bash(sqlite3:*)" "Read" "Write" "Glob" "Grep" `
    --append-system-prompt "You are the quant-analyst agent. Skills: odds-retrieval, statistical-analysis. Plugins: data-validation-suite, python-development. CRITICAL: Use venv/Scripts/python.exe only. Working dir: C:\Users\msenf\sports-betting" `
    @"
Execute the daily paper betting pipeline:

1. Fetch daily snapshots: venv/Scripts/python.exe scripts/daily_run.py --fetch-snapshots
2. If errors occur, diagnose from logs/ and report
3. Return JSON: {"date": "YYYY-MM-DD", "games_found": N, "bets_placed": N, "settlements": N, "errors": []}
"@
```

### Task: `nightly`

```powershell
claude -p `
    --output-format json `
    --max-turns 8 `
    --allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" "Glob" `
    --append-system-prompt "You are the data-scientist agent. Skills: senior-data-engineer, matplotlib. Plugins: data-engineering, python-development. Use venv/Scripts/python.exe only. Working dir: C:\Users\msenf\sports-betting" `
    @"
Execute nightly data refresh:

1. Fetch incremental 2026 data: venv/Scripts/python.exe scripts/fetch_season_data.py --season 2026 --incremental --no-odds
2. Retrain Elo: venv/Scripts/python.exe scripts/train_ncaab_elo.py --end 2026
3. Regenerate dashboard: venv/Scripts/python.exe scripts/generate_dashboard_data.py
4. Return JSON summary with step results and any failures.
"@
```

### Task: `settle`

```powershell
claude -p `
    --output-format text `
    --max-turns 3 `
    --allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" `
    --append-system-prompt "You are the data-analyst agent. Settle bets only. Use venv/Scripts/python.exe. Working dir: C:\Users\msenf\sports-betting" `
    "Run venv/Scripts/python.exe scripts/daily_run.py --settle-only and report settlement results."
```

### Task: `test`

```powershell
claude -p `
    --output-format json `
    --max-turns 15 `
    --dangerously-skip-permissions `
    --append-system-prompt "You are the senior-qa agent. Skills: test-driven-development, systematic-debugging, find-bugs. Fix code, not tests (unless the test is wrong). Use venv/Scripts/python.exe. Working dir: C:\Users\msenf\sports-betting" `
    @"
Run full test suite and fix failures:

1. Run: venv/Scripts/python.exe -m pytest tests/ -v --tb=short
2. If all pass: {"status": "pass", "tests": N}
3. If failures: analyze, fix code, re-run failing tests, report {"status": "fixed", "failures_fixed": N, "remaining": N}
"@
```

### Task: `validate`

```powershell
claude -p `
    --output-format json `
    --max-turns 5 `
    --allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" "Glob" `
    --append-system-prompt "You are the quant-analyst agent running Gatekeeper validation. Skills: statistical-analysis, verification-before-completion. Use venv/Scripts/python.exe. Working dir: C:\Users\msenf\sports-betting" `
    @"
Run 5-dimension Gatekeeper validation:

1. Execute: venv/Scripts/python.exe scripts/run_gatekeeper_validation.py
2. Return JSON: {"decision": "PASS|QUARANTINE|NEEDS_REVIEW", "blocking_failures": [...], "warnings": [...]}
"@
```

### Task: `backtest`

```powershell
claude -p `
    --output-format json `
    --max-turns 12 `
    --allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" "Write" "Glob" "Grep" `
    --append-system-prompt "You are the data-scientist agent running walk-forward backtests. Skills: senior-data-scientist, statistical-analysis, matplotlib. Use venv/Scripts/python.exe. Working dir: C:\Users\msenf\sports-betting" `
    @"
Run incremental walk-forward backtest:

1. Execute: venv/Scripts/python.exe scripts/incremental_backtest.py --barttorvik
2. Analyze results for ROI, Sharpe, CLV, p-value
3. Return JSON: {"pooled_roi": N, "sharpe": N, "avg_clv": N, "p_value": N, "seasons": {...}}
"@
```

### Task: `custom`

Pass the user's custom prompt through with sensible defaults:

```powershell
claude -p `
    --output-format json `
    --max-turns 10 `
    --allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" "Glob" "Grep" `
    --append-system-prompt "Sports-betting project assistant. Use venv/Scripts/python.exe. Working dir: C:\Users\msenf\sports-betting" `
    "<USER_CUSTOM_PROMPT>"
```

### Output Handling

After execution, always:
1. Log output to `logs/headless-<task>-<date>.json`
2. Parse exit status
3. Report summary to user

```powershell
$result | Out-File "$ProjectRoot\logs\headless-<task>-$(Get-Date -Format 'yyyy-MM-dd-HHmmss').json"
```
