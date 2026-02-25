<#
.SYNOPSIS
    Morning betting pipeline -- settle + predict.

.DESCRIPTION
    Runs the daily paper betting workflow:
    1. Settle yesterday's bets (using ESPN final scores)
    2. Generate today's predictions and record paper bets

    Includes idempotency: checks if bets already exist for today
    before generating predictions. Detects no-game days.

    Designed to run via Windows Task Scheduler at 10:00 AM ET.

.PARAMETER Force
    Force re-run even if today's bets already exist.

.PARAMETER DryRun
    Preview without executing Python scripts.

.PARAMETER SettleOnly
    Only settle yesterday's bets, skip predictions.

.PARAMETER SkipSettle
    Skip settlement, only generate predictions.

.PARAMETER Date
    Target date for predictions (default: today). Format: YYYY-MM-DD or "today".

.PARAMETER MaxRetries
    Maximum retry attempts per step (default: 1).

.EXAMPLE
    .\scripts\morning-betting.ps1
    .\scripts\morning-betting.ps1 -SettleOnly
    .\scripts\morning-betting.ps1 -DryRun
    .\scripts\morning-betting.ps1 -Force -Date "2026-02-21"
#>

[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$DryRun,
    [switch]$SettleOnly,
    [switch]$SkipSettle,
    [string]$Date = "today",
    [int]$MaxRetries = 1
)

$ErrorActionPreference = "Stop"

Write-Warning "DEPRECATED: Use daily-pipeline.ps1 instead. This script will be removed in a future version."

# Load shared functions
. "$PSScriptRoot\pipeline-common.ps1"

# Load environment variables
Import-DotEnv

# Initialize logging
$logFile = Initialize-PipelineLog -PipelineType "morning"
Write-Log "INFO" "Morning betting starting (DryRun=$DryRun, SettleOnly=$SettleOnly, Date=$Date)"

# Acquire lock
if (-not $DryRun) {
    $locked = Acquire-PipelineLock
    if (-not $locked) {
        Write-Log "ERROR" "Cannot acquire pipeline lock -- exiting"
        exit 2
    }
}

# Initialize state
$today = Get-Date -Format "yyyy-MM-dd"
$state = @{
    date           = $today
    pipeline       = "morning"
    started_at     = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
    steps          = @{}
    overall_status = "running"
}

$hasFailure = $false

# =========================================================================
# Step 1: Settle yesterday's bets
# =========================================================================
if (-not $SkipSettle) {
    Write-Log "INFO" "========== Step: settle_bets =========="

    $settleResult = Invoke-PipelineStep `
        -StepName "settle_bets" `
        -Script "daily_run.py" `
        -Arguments @("--settle-only") `
        -TimeoutSeconds 120 `
        -MaxRetries $MaxRetries `
        -DryRun:$DryRun

    if ($settleResult.exit_code -eq 0) {
        $state.steps["settle_bets"] = @{
            status    = "completed"
            exit_code = 0
            attempt   = $settleResult.attempt
            duration  = $settleResult.duration
        }
    } else {
        $state.steps["settle_bets"] = @{
            status    = "failed"
            exit_code = $settleResult.exit_code
            attempt   = $settleResult.attempt
            error     = "Settlement failed (non-critical)"
        }
        Write-Log "WARN" "Settlement failed -- continuing to predictions"
        # Settlement is non-critical: log but don't abort
    }

    if (-not $DryRun) {
        Save-Checkpoint -State $state
    }
}

# =========================================================================
# Step 2: Generate predictions (with idempotency check)
# =========================================================================
if (-not $SettleOnly) {
    Write-Log "INFO" "========== Step: predictions =========="

    # Idempotency check: do bets already exist for today?
    $skipPredictions = $false
    if (-not $Force -and -not $DryRun) {
        try {
            $dbPath = Join-Path (Join-Path $Script:ProjectRoot "data") "betting.db"
            $checkDate = if ($Date -eq "today") { $today } else { $Date }

            # Use Python to query since PowerShell SQLite support varies
            $checkCmd = "import sqlite3; conn = sqlite3.connect(r'$dbPath'); print(conn.execute('SELECT COUNT(*) FROM bets WHERE game_date = ?', ('$checkDate',)).fetchone()[0]); conn.close()"
            $countResult = & $Script:VenvPython -c $checkCmd 2>$null
            if ($null -eq $countResult) { $countResult = "0" }
            $existingBets = [int]($countResult.ToString().Trim())

            if ($existingBets -gt 0) {
                Write-Log "INFO" "Found $existingBets existing bets for $checkDate -- skipping predictions (use -Force to override)"
                $skipPredictions = $true
                $state.steps["predictions"] = @{
                    status    = "skipped"
                    exit_code = 0
                    attempt   = 0
                    error     = "Idempotency: $existingBets bets already exist"
                }
            }
        } catch {
            Write-Log "WARN" "Idempotency check failed: $_ -- proceeding with predictions"
        }
    }

    if (-not $skipPredictions) {
        $predArgs = @("--skip-settle")
        if ($Date -ne "today") {
            $predArgs += @("--date", $Date)
        }

        $predResult = Invoke-PipelineStep `
            -StepName "predictions" `
            -Script "daily_run.py" `
            -Arguments $predArgs `
            -TimeoutSeconds 300 `
            -MaxRetries $MaxRetries `
            -DryRun:$DryRun

        if ($predResult.exit_code -eq 0) {
            $state.steps["predictions"] = @{
                status    = "completed"
                exit_code = 0
                attempt   = $predResult.attempt
                duration  = $predResult.duration
            }
        } else {
            $errorMsg = if ($predResult.stderr) {
                $predResult.stderr.Substring(0, [Math]::Min(200, $predResult.stderr.Length))
            } else {
                "Exit code $($predResult.exit_code)"
            }

            $state.steps["predictions"] = @{
                status    = "failed"
                exit_code = $predResult.exit_code
                attempt   = $predResult.attempt
                error     = $errorMsg
            }

            $hasFailure = $true
            Write-Log "ERROR" "Predictions step FAILED"
            Send-PipelineNotification `
                -Title "Morning Pipeline FAILED" `
                -Message "Predictions step failed: $errorMsg" `
                -Level "error"
        }
    }

    if (-not $DryRun) {
        Save-Checkpoint -State $state
    }
}

# Determine overall status
if ($hasFailure) {
    $state.overall_status = "failed"
    $exitCode = 1
} else {
    $state.overall_status = "completed"
    $exitCode = 0
}

$state.completed_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")

# Save final state and release lock
if (-not $DryRun) {
    Save-Checkpoint -State $state
    Release-PipelineLock
}

# Summary
Write-Log "INFO" "========================================"
Write-Log "INFO" "Morning pipeline: $($state.overall_status.ToUpper())"
Write-Log "INFO" "========================================"

foreach ($stepName in $state.steps.Keys) {
    $s = $state.steps[$stepName]
    $icon = switch ($s.status) {
        "completed" { "OK" }
        "failed"    { "FAIL" }
        "skipped"   { "SKIP" }
        default     { "?" }
    }
    Write-Log "INFO" "  [$icon] $stepName (exit=$($s.exit_code))"
}

if ($exitCode -eq 0 -and -not $SettleOnly) {
    Send-PipelineNotification `
        -Title "Morning Pipeline Success" `
        -Message "Predictions generated for $today" `
        -Level "success"
}

Write-Log "INFO" "Log file: $logFile"
exit $exitCode
