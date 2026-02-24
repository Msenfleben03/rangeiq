# Headless Claude Code: Non-Interactive Automation for Sports Betting

> Quick reference for running Claude Code non-interactively from PowerShell scripts,
> scheduled tasks, and CI/CD pipelines.

See the full guide: `docs/headless-claude-code-guide.md`

## Quick Start: Your Daily Pipeline

```powershell
# One-liner: Run daily paper betting pipeline headlessly
claude -p --output-format json --max-turns 10 `
    --allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" "Glob" `
    "Run venv/Scripts/python.exe scripts/daily_run.py --fetch-snapshots"
```

## Three Permission Modes

| Mode | Flag | When |
|------|------|------|
| Full autonomy | `--dangerously-skip-permissions` | Local dev, sandboxed |
| Tool whitelist | `--allowedTools "Bash(python:*)" "Read"` | **Production recommended** |
| MCP auth | `--permission-prompt-tool mcp_tool` | Enterprise CI/CD |

## Daily Schedule (Windows Task Scheduler)

Two tasks registered via `scripts/setup-scheduled-tasks.ps1 -Action register`:

| Time | Task | Script | Purpose |
|------|------|--------|---------|
| 10:00 AM | SportsBetting-Morning | `morning-betting.ps1` | Settle yesterday + predict today |
| 11:00 PM | SportsBetting-Nightly | `nightly-refresh.ps1` | Fetch scores, retrain Elo, Barttorvik, dashboard |

## Manual Runs

```powershell
# Preview without executing
.\scripts\nightly-refresh.ps1 -DryRun
.\scripts\morning-betting.ps1 -DryRun

# Force re-run (skip idempotency check)
.\scripts\morning-betting.ps1 -Force

# Settle only (no predictions)
.\scripts\morning-betting.ps1 -SettleOnly

# Check task registration
.\scripts\setup-scheduled-tasks.ps1 -Action status
```

## Pipeline Health Check

```powershell
venv/Scripts/python.exe scripts/pipeline_health_check.py --json
```

Validates: venv, database (22 tables), API keys, data freshness, stale locks.
