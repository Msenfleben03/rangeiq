# Headless Claude Code: Non-Interactive Automation for Sports Betting

> Complete reference for running Claude Code non-interactively from PowerShell scripts,
> scheduled tasks, and CI/CD pipelines.

See the full guide: `docs/HEADLESS_CLAUDE_CODE.md`

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

| Time | Script | Purpose |
|------|--------|---------|
| 10:00 AM | `daily-betting-pipeline.ps1` | Predict → Record → Report |
| 11:00 PM | `nightly-refresh.ps1` | Fetch data → Retrain → Dashboard |
| 11:30 PM | `evening-settle.ps1` | Settle yesterday's bets |
