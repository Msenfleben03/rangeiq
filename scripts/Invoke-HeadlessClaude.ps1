<#
.SYNOPSIS
    Headless Claude Code launcher for sports-betting project.
    Routes tasks to correct agents, skills, tools, and permission modes.

.DESCRIPTION
    Unified entry point for all non-interactive Claude Code automation.
    Maps tasks to the optimal agent persona, tool whitelist, and turn limits.

.PARAMETER Task
    Task to run: daily, nightly, settle, test, validate, backtest, custom

.PARAMETER CustomPrompt
    Custom prompt text (required when Task = 'custom')

.PARAMETER DryRun
    Show the command without executing it

.PARAMETER Model
    Override model (default: sonnet)

.PARAMETER Verbose
    Enable verbose Claude Code logging

.EXAMPLE
    .\Invoke-HeadlessClaude.ps1 -Task daily
    .\Invoke-HeadlessClaude.ps1 -Task test -Verbose
    .\Invoke-HeadlessClaude.ps1 -Task custom -CustomPrompt "Analyze last week's CLV trends"
    .\Invoke-HeadlessClaude.ps1 -Task daily -DryRun
#>
param(
    [Parameter(Mandatory)]
    [ValidateSet('daily', 'nightly', 'settle', 'test', 'validate', 'backtest', 'custom')]
    [string]$Task,

    [string]$CustomPrompt = "",
    [switch]$DryRun,
    [string]$Model = "",
    [switch]$Verbose
)

$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\msenf\sports-betting"
Set-Location $ProjectRoot

# Ensure API key is available
if (-not $env:ANTHROPIC_API_KEY) {
    $envFile = Join-Path $ProjectRoot ".env"
    if (Test-Path $envFile) {
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^ANTHROPIC_API_KEY=(.+)$') {
                $env:ANTHROPIC_API_KEY = $Matches[1]
            }
        }
    }
    if (-not $env:ANTHROPIC_API_KEY) {
        Write-Error "ANTHROPIC_API_KEY not set. Add to .env or set environment variable."
        exit 1
    }
}

# ── Task Configuration Map ──────────────────────────────────────────
$TaskConfig = @{
    daily = @{
        Agent       = "quant-analyst"
        Skills      = "odds-retrieval, statistical-analysis"
        Plugins     = "data-validation-suite, python-development"
        MaxTurns    = 10
        OutputFmt   = "json"
        Permission  = '--allowedTools "Bash(venv/Scripts/python.exe:*)" "Bash(sqlite3:*)" "Read" "Write" "Glob" "Grep"'
        Prompt      = @"
Execute the daily paper betting pipeline:

1. Fetch daily snapshots: venv/Scripts/python.exe scripts/daily_run.py --fetch-snapshots
2. If errors occur, diagnose from logs/ and report
3. Return JSON: {"date": "$(Get-Date -Format 'yyyy-MM-dd')", "games_found": N, "bets_placed": N, "settlements": N, "errors": []}
"@
    }
    nightly = @{
        Agent       = "data-scientist"
        Skills      = "senior-data-engineer, matplotlib"
        Plugins     = "data-engineering, python-development"
        MaxTurns    = 8
        OutputFmt   = "json"
        Permission  = '--allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" "Glob"'
        Prompt      = @"
Execute nightly data refresh:

1. Fetch incremental 2026 data: venv/Scripts/python.exe scripts/fetch_season_data.py --season 2026 --incremental --no-odds
2. Retrain Elo: venv/Scripts/python.exe scripts/train_ncaab_elo.py --end 2026
3. Regenerate dashboard: venv/Scripts/python.exe scripts/generate_dashboard_data.py
4. Return JSON summary with step results and any failures.
"@
    }
    settle = @{
        Agent       = "data-analyst"
        Skills      = "statistical-analysis"
        Plugins     = "data-validation-suite"
        MaxTurns    = 3
        OutputFmt   = "text"
        Permission  = '--allowedTools "Bash(venv/Scripts/python.exe:*)" "Read"'
        Prompt      = "Run venv/Scripts/python.exe scripts/daily_run.py --settle-only and report settlement results."
    }
    test = @{
        Agent       = "senior-qa"
        Skills      = "test-driven-development, systematic-debugging, find-bugs"
        Plugins     = "python-development"
        MaxTurns    = 15
        OutputFmt   = "json"
        Permission  = "--dangerously-skip-permissions"
        Prompt      = @"
Run full test suite and fix failures:

1. Run: venv/Scripts/python.exe -m pytest tests/ -v --tb=short
2. If all pass: {"status": "pass", "tests": N}
3. If failures: analyze, fix code (not the test unless the test is wrong), re-run failing tests
4. Report: {"status": "fixed", "failures_fixed": N, "remaining": N}
"@
    }
    validate = @{
        Agent       = "quant-analyst"
        Skills      = "statistical-analysis, verification-before-completion"
        Plugins     = "data-validation-suite"
        MaxTurns    = 5
        OutputFmt   = "json"
        Permission  = '--allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" "Glob"'
        Prompt      = @"
Run 5-dimension Gatekeeper validation:

1. Execute: venv/Scripts/python.exe scripts/run_gatekeeper_validation.py
2. Return JSON: {"decision": "PASS|QUARANTINE|NEEDS_REVIEW", "blocking_failures": [...], "warnings": [...]}
"@
    }
    backtest = @{
        Agent       = "data-scientist"
        Skills      = "senior-data-scientist, statistical-analysis, matplotlib"
        Plugins     = "data-engineering, python-development"
        MaxTurns    = 12
        OutputFmt   = "json"
        Permission  = '--allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" "Write" "Glob" "Grep"'
        Prompt      = @"
Run incremental walk-forward backtest:

1. Execute: venv/Scripts/python.exe scripts/incremental_backtest.py --barttorvik
2. Analyze results for ROI, Sharpe, CLV, p-value
3. Return JSON: {"pooled_roi": N, "sharpe": N, "avg_clv": N, "p_value": N, "seasons": {...}}
"@
    }
    custom = @{
        Agent       = "task-planner"
        Skills      = "planning-with-files"
        Plugins     = "python-development"
        MaxTurns    = 10
        OutputFmt   = "json"
        Permission  = '--allowedTools "Bash(venv/Scripts/python.exe:*)" "Read" "Glob" "Grep"'
        Prompt      = ""
    }
}

# ── Build Command ────────────────────────────────────────────────────
$config = $TaskConfig[$Task]

if ($Task -eq "custom") {
    if (-not $CustomPrompt) {
        Write-Error "Custom task requires -CustomPrompt parameter."
        exit 1
    }
    $config.Prompt = $CustomPrompt
}

$systemPrompt = "You are the $($config.Agent) agent for the sports-betting project. " +
    "Key skills: $($config.Skills). " +
    "Active plugins: $($config.Plugins). " +
    "CRITICAL: Always use venv/Scripts/python.exe, never system Python. " +
    "Working directory: $ProjectRoot"

$modelFlag = if ($Model) { "--model $Model" } else { "" }
$verboseFlag = if ($Verbose) { "--verbose" } else { "" }

# Build the full command
$cmd = "claude -p " +
    "--output-format $($config.OutputFmt) " +
    "--max-turns $($config.MaxTurns) " +
    "$($config.Permission) " +
    "--append-system-prompt `"$systemPrompt`" " +
    "$modelFlag $verboseFlag " +
    "`"$($config.Prompt -replace '"', '\"')`""

# ── Execute or Preview ───────────────────────────────────────────────
$logDir = Join-Path $ProjectRoot "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "headless-$Task-$(Get-Date -Format 'yyyy-MM-dd-HHmmss').json"

if ($DryRun) {
    Write-Host "`n=== DRY RUN: /headless $Task ===" -ForegroundColor Yellow
    Write-Host "`nAgent:      $($config.Agent)" -ForegroundColor Cyan
    Write-Host "Skills:     $($config.Skills)" -ForegroundColor Cyan
    Write-Host "Plugins:    $($config.Plugins)" -ForegroundColor Cyan
    Write-Host "Max Turns:  $($config.MaxTurns)" -ForegroundColor Cyan
    Write-Host "Output:     $($config.OutputFmt)" -ForegroundColor Cyan
    Write-Host "Permission: $($config.Permission)" -ForegroundColor Cyan
    Write-Host "Log File:   $logFile" -ForegroundColor Cyan
    Write-Host "`nCommand:" -ForegroundColor Green
    Write-Host $cmd -ForegroundColor White
    exit 0
}

Write-Host "`n=== Headless: /headless $Task ===" -ForegroundColor Green
Write-Host "Agent: $($config.Agent) | Turns: $($config.MaxTurns) | Format: $($config.OutputFmt)" -ForegroundColor Cyan
Write-Host "Logging to: $logFile" -ForegroundColor DarkGray

$startTime = Get-Date
$result = Invoke-Expression $cmd
$duration = (Get-Date) - $startTime

# Log results
$logEntry = @{
    task       = $Task
    agent      = $config.Agent
    timestamp  = (Get-Date -Format "o")
    duration_s = [math]::Round($duration.TotalSeconds, 1)
    output     = $result
} | ConvertTo-Json -Depth 10

$logEntry | Out-File $logFile -Encoding utf8

Write-Host "`nCompleted in $([math]::Round($duration.TotalSeconds, 1))s" -ForegroundColor Green
Write-Host "Log: $logFile" -ForegroundColor DarkGray

# Return result for pipeline chaining
$result
