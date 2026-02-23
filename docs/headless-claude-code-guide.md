---
title: "Headless Claude Code: Non-Interactive Automation for Sports Betting"
created: 2026-02-20
modified: 2026-02-20
type: guide
status: active
tags:
  - automation/ci-cd
  - ai/claude-code
  - workflow/headless
---

# Headless Claude Code: Non-Interactive Automation for Sports Betting

> [!abstract] Summary
> Complete reference for running Claude Code non-interactively from PowerShell scripts,
> scheduled tasks, and CI/CD pipelines. Covers print mode (`-p`), permission strategies,
> output parsing, the Claude Agent SDK, GitHub Actions, hooks, and project-specific
> automation recipes for the `sports-betting` daily pipeline.

## Core Concept: Print Mode (`-p`)

Print mode is Claude Code's headless execution mode. It accepts a prompt, runs to
completion without interactive input, and returns output to stdout. This is the
foundation for all non-interactive automation.

```powershell
# Basic headless invocation
claude -p "your prompt here"

# With JSON output for programmatic parsing
claude -p --output-format json "your prompt here"

# With streaming JSON for real-time progress
claude -p --output-format stream-json "your prompt here"

# Pipe input from a file or other command
Get-Content prompt.txt | claude -p

# Combine with system prompt customization
claude -p --append-system-prompt "You are a data pipeline assistant" "Run the daily predictions"
```

## Permission Strategies for Headless Runs

Three approaches, from most to least permissive:

### Strategy 1: Full Autonomy (Development/Trusted Scripts)

```powershell
claude -p --dangerously-skip-permissions "Run pytest and fix failures"
```

Use when: Local development, trusted automation scripts, sandboxed environments.
Risk: Claude can execute any shell command, write any file.

### Strategy 2: Scoped Tool Whitelist (Recommended for Production)

```powershell
claude -p `
  --allowedTools "Bash(python:*)" "Bash(pytest:*)" "Read" "Glob" "Grep" `
  "Run the test suite and report failures"
```

Common tool patterns for sports-betting:

| Pattern | Allows |
|---------|--------|
| `Bash(python:*)` | Any python command |
| `Bash(pytest:*)` | Test execution |
| `Bash(git log:*)` | Git history reads |
| `Bash(git diff:*)` | Git diff reads |
| `Bash(sqlite3:*)` | Database queries |
| `Read` | File reading |
| `Write` | File writing |
| `Edit` | File editing |
| `Glob` | File pattern matching |
| `Grep` | Content search |
| `WebSearch` | Web lookups |
| `WebFetch` | URL fetching |

### Strategy 3: MCP Permission Tool (Enterprise/CI)

```powershell
claude -p `
  --permission-prompt-tool mcp__auth__check_permission `
  "Deploy the model update"
```

Use when: CI/CD where an external system manages approvals.

## Turn Limiting

Prevent runaway sessions with `--max-turns`:

```powershell
# Limit to 5 agentic turns (good for focused tasks)
claude -p --max-turns 5 "Generate today's predictions"

# Longer limit for complex multi-step work
claude -p --max-turns 20 "Run full backtest and validation pipeline"
```

## Output Formats and Parsing

### JSON Output (Best for Scripts)

```powershell
$result = claude -p --output-format json "What is 2+2?" | ConvertFrom-Json
$answer = $result.result
$cost = $result.cost_usd
```

### Stream-JSON (Real-Time Progress)

```powershell
claude -p --output-format stream-json "Run the daily pipeline" | ForEach-Object {
    $event = $_ | ConvertFrom-Json
    if ($event.type -eq "assistant") {
        Write-Host $event.message.content -ForegroundColor Cyan
    }
}
```

### Plain Text (Simple Capture)

```powershell
$output = claude -p "Summarize today's prediction results" 2>$null
```

## Environment Variables for Headless Mode

```powershell
# Required
$env:ANTHROPIC_API_KEY = "sk-ant-..."  # pragma: allowlist secret

# Optional: Force headless behavior in scripts
$env:CLAUDE_CODE_HEADLESS = "true"

# Optional: For Claude Flow V3 integration
$env:CLAUDE_FLOW_HEADLESS = "true"

# Optional: Custom config directory
$env:CLAUDE_CONFIG_DIR = "C:\Users\msenf\.claude"

# Optional: Disable interleaved thinking (faster for simple tasks)
$env:DISABLE_INTERLEAVED_THINKING = "1"
```

## Sports-Betting Automation Recipes

### Recipe 1: Daily Paper Betting Pipeline

The primary automation target. Runs the full predict → record → settle → report cycle.

```powershell
# daily-betting-pipeline.ps1
# Schedule via Windows Task Scheduler at 10:00 AM ET daily

$ProjectRoot = "C:\Users\msenf\sports-betting"
Set-Location $ProjectRoot

# Activate venv context for Claude
$prompt = @"
Run the daily paper betting pipeline:

1. Activate the venv: venv/Scripts/python.exe
2. Fetch daily Barttorvik + KenPom snapshots
3. Run: venv/Scripts/python.exe scripts/daily_run.py --fetch-snapshots
4. If any errors, diagnose and report them
5. Output a JSON summary with: date, games_found, bets_placed, settlements, errors

Use the project's venv Python at venv/Scripts/python.exe for all commands.
Working directory: $ProjectRoot
"@

$result = claude -p `
    --output-format json `
    --max-turns 10 `
    --allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" "Glob" `
    --append-system-prompt "You are the sports-betting daily automation agent. Never use system Python. Always use venv/Scripts/python.exe. Working dir: $ProjectRoot" `
    $prompt

# Parse and log
$result | Out-File "$ProjectRoot\logs\daily-run-$(Get-Date -Format 'yyyy-MM-dd').json"
```

### Recipe 2: Nightly Data Refresh

```powershell
# nightly-refresh.ps1
# Schedule at 11:00 PM ET

$ProjectRoot = "C:\Users\msenf\sports-betting"
Set-Location $ProjectRoot

claude -p `
    --output-format json `
    --max-turns 8 `
    --allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" `
    --append-system-prompt "Sports-betting nightly refresh agent. Use venv/Scripts/python.exe." `
    @"
Execute the nightly data refresh sequence:

1. Fetch incremental 2026 season data:
   venv/Scripts/python.exe scripts/fetch_season_data.py --season 2026 --incremental --no-odds

2. Retrain Elo model with latest data:
   venv/Scripts/python.exe scripts/train_ncaab_elo.py --end 2026

3. Regenerate dashboard data:
   venv/Scripts/python.exe scripts/generate_dashboard_data.py

Report any failures with the specific error message.
"@ | Out-File "$ProjectRoot\logs\nightly-refresh-$(Get-Date -Format 'yyyy-MM-dd').json"
```

### Recipe 3: Test Suite with Auto-Fix

```powershell
# run-tests-and-fix.ps1

$ProjectRoot = "C:\Users\msenf\sports-betting"
Set-Location $ProjectRoot

claude -p `
    --output-format json `
    --max-turns 15 `
    --dangerously-skip-permissions `
    @"
Run the full test suite and fix any failures:

1. Run: venv/Scripts/python.exe -m pytest tests/ -v --tb=short
2. If all 533+ tests pass, output {"status": "pass", "tests": <count>}
3. If tests fail:
   a. Analyze the failure
   b. Fix the code (not the test, unless the test itself is wrong)
   c. Re-run only the failing tests to confirm
   d. Output {"status": "fixed", "failures_fixed": <count>, "remaining": <count>}
"@
```

### Recipe 4: Model Validation Gate

```powershell
# validate-model.ps1

$ProjectRoot = "C:\Users\msenf\sports-betting"
Set-Location $ProjectRoot

$result = claude -p `
    --output-format json `
    --max-turns 5 `
    --allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" `
    @"
Run the 5-dimension Gatekeeper validation:

1. Execute: venv/Scripts/python.exe scripts/run_gatekeeper_validation.py
2. Parse the output for the gate decision
3. Return JSON: {
     "decision": "PASS|QUARANTINE|NEEDS_REVIEW",
     "blocking_failures": [...],
     "warnings": [...]
   }
"@

$parsed = $result | ConvertFrom-Json
if ($parsed.result -match "QUARANTINE") {
    Write-Host "MODEL QUARANTINED — Do not deploy" -ForegroundColor Red
    exit 1
}
```

### Recipe 5: Settlement-Only (Evening Run)

```powershell
# evening-settle.ps1
# Schedule at 11:30 PM ET

$ProjectRoot = "C:\Users\msenf\sports-betting"
Set-Location $ProjectRoot

claude -p `
    --output-format text `
    --max-turns 3 `
    --allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" `
    "Run venv/Scripts/python.exe scripts/daily_run.py --settle-only and report the settlement results"
```

## Claude Agent SDK (Programmatic Python Integration)

For deeper integration, the Claude Agent SDK (formerly Claude Code SDK) lets you
call Claude programmatically from Python scripts:

```python
# agent_daily_pipeline.py
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def run_daily_pipeline():
    """Run the daily betting pipeline via Claude Agent SDK."""
    async for message in query(
        prompt="Run scripts/daily_run.py --fetch-snapshots and report results as JSON",
        options=ClaudeAgentOptions(
            allowed_tools=["Bash", "Read", "Glob"],
            max_turns=10,
        ),
    ):
        if hasattr(message, "result"):
            return message.result

if __name__ == "__main__":
    result = asyncio.run(run_daily_pipeline())
    print(result)
```

Install: `pip install @anthropic-ai/claude-agent-sdk` (TypeScript) or
`pip install claude-agent-sdk` (Python).

## GitHub Actions Integration

For CI/CD on push or schedule:

```yaml
# .github/workflows/daily-betting.yml
name: Daily Betting Pipeline

on:
  schedule:
    - cron: "0 15 * * *"  # 10 AM ET daily
  workflow_dispatch:       # Manual trigger

jobs:
  daily-run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run daily pipeline via Claude
        uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: |
            Run the daily paper betting pipeline:
            1. python scripts/daily_run.py --fetch-snapshots --dry-run
            2. Report results as a PR comment
          claude_args: "--max-turns 10 --model claude-sonnet-4-6"

      - name: Run tests
        uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: "/review"  # Uses CLAUDE.md context
```

For the `@claude` mention workflow (PR reviews, issue triage):

```yaml
# .github/workflows/claude-pr.yml
name: Claude PR Assistant

on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  claude:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Hooks for Headless Safety

Your project already has a `Stop` hook. Extend it for headless-specific guards:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "echo '{\"ok\": true}'",
            "timeout": 1000
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "pwsh -NoProfile -Command \"$input = $Input | ConvertFrom-Json; if ($input.tool_input.command -match 'rm -rf|DROP TABLE|DELETE FROM') { Write-Error 'BLOCKED: Destructive command'; exit 2 } else { exit 0 }\"",
            "timeout": 3000
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "pwsh -NoProfile -Command \"if ($env:CLAUDE_ENV_FILE) { Add-Content $env:CLAUDE_ENV_FILE 'export PAPER_BETTING_MODE=true' }; exit 0\"",
            "timeout": 2000
          }
        ]
      }
    ]
  }
}
```

## Windows Task Scheduler Setup

Create scheduled tasks for the daily cadence:

```powershell
# setup-scheduled-tasks.ps1

# Morning: Daily predictions (10:00 AM ET)
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -File C:\Users\msenf\sports-betting\scripts\daily-betting-pipeline.ps1" `
    -WorkingDirectory "C:\Users\msenf\sports-betting"

$trigger = New-ScheduledTaskTrigger -Daily -At "10:00AM"

Register-ScheduledTask `
    -TaskName "SportsBetting-DailyPipeline" `
    -Action $action `
    -Trigger $trigger `
    -Description "Claude Code headless daily betting pipeline"

# Evening: Settlement (11:30 PM ET)
$settleAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -File C:\Users\msenf\sports-betting\scripts\evening-settle.ps1" `
    -WorkingDirectory "C:\Users\msenf\sports-betting"

$settleTrigger = New-ScheduledTaskTrigger -Daily -At "11:30PM"

Register-ScheduledTask `
    -TaskName "SportsBetting-EveningSettle" `
    -Action $settleAction `
    -Trigger $settleTrigger `
    -Description "Claude Code headless bet settlement"

# Nightly: Data refresh (11:00 PM ET)
$nightAction = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -File C:\Users\msenf\sports-betting\scripts\nightly-refresh.ps1" `
    -WorkingDirectory "C:\Users\msenf\sports-betting"

$nightTrigger = New-ScheduledTaskTrigger -Daily -At "11:00PM"

Register-ScheduledTask `
    -TaskName "SportsBetting-NightlyRefresh" `
    -Action $nightAction `
    -Trigger $nightTrigger `
    -Description "Claude Code headless nightly data refresh"
```

## Quick Reference: Flag Cheat Sheet

| Flag | Purpose | Example |
|------|---------|---------|
| `-p` / `--print` | Headless mode (no interactive UI) | `claude -p "query"` |
| `--output-format` | `text`, `json`, `stream-json` | `claude -p --output-format json` |
| `--input-format` | `text`, `stream-json` | `claude -p --input-format stream-json` |
| `--max-turns` | Limit agentic turns | `claude -p --max-turns 5` |
| `--model` | Select model | `claude -p --model opus` |
| `--allowedTools` | Whitelist tools | `claude -p --allowedTools "Read" "Bash(python:*)"` |
| `--disallowedTools` | Blacklist tools | `claude -p --disallowedTools "Write"` |
| `--dangerously-skip-permissions` | Skip all prompts | `claude -p --dangerously-skip-permissions` |
| `--permission-prompt-tool` | MCP auth tool | `claude -p --permission-prompt-tool mcp_tool` |
| `--append-system-prompt` | Add to system prompt | `claude -p --append-system-prompt "..."` |
| `--system-prompt-file` | Override system prompt from file | `claude -p --system-prompt-file prompt.md` |
| `--verbose` | Debug logging | `claude -p --verbose` |
| `--continue` | Resume last session | `claude --continue` |
| `--resume` | Resume specific session | `claude --resume <id>` |
| `--add-dir` | Add working directories | `claude --add-dir ../lib` |
| `--mcp-config` | MCP config path | `claude -p --mcp-config .mcp.json` |

## Related Notes

- [[Claude_Code_via_MCP]]
- [[Claude_Tools]]
- [[Command-Line_Reference]]
- [[hooks-reference]]
- [[claude-flow-readme]]
