<#
.SYNOPSIS
    Nightly data refresh pipeline for sports betting model.

.DESCRIPTION
    Runs the following steps in sequence:
    1. Health check (pre-flight validation)
    2. Fetch latest scores (ESPN API, incremental)
    3. Retrain Elo model with new data
    4. Scrape Barttorvik daily snapshot
    5. Generate dashboard data bundle
    6. Deploy dashboard to Vercel

    Supports checkpointing, retry, and notification on failure.
    Designed to run via Windows Task Scheduler at 11:00 PM ET nightly.

.PARAMETER Force
    Skip checkpoint resume -- run all steps from scratch.

.PARAMETER DryRun
    Preview all steps without executing any Python scripts.

.PARAMETER SkipHealthCheck
    Skip the pre-flight health check step.

.PARAMETER NoClaude
    Skip AI-assisted diagnosis on failure (not yet implemented).

.PARAMETER MaxRetries
    Maximum retry attempts per step (default: 1).

.EXAMPLE
    .\scripts\nightly-refresh.ps1
    .\scripts\nightly-refresh.ps1 -DryRun
    .\scripts\nightly-refresh.ps1 -Force -MaxRetries 2
#>

[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$DryRun,
    [switch]$SkipHealthCheck,
    [switch]$NoClaude,
    [int]$MaxRetries = 1
)

$ErrorActionPreference = "Stop"

# Load shared functions
. "$PSScriptRoot\pipeline-common.ps1"

# Load environment variables
Import-DotEnv

# Initialize logging
$logFile = Initialize-PipelineLog -PipelineType "nightly"
Write-Log "INFO" "Nightly refresh starting (DryRun=$DryRun, Force=$Force, MaxRetries=$MaxRetries)"

# Define pipeline steps
$steps = [ordered]@{
    health_check = @{
        script    = "pipeline_health_check.py"
        args      = @("--json")
        critical  = $true
        timeout   = 30
    }
    fetch_scores = @{
        script    = "fetch_season_data.py"
        args      = @("--season", "2026", "--incremental", "--no-odds")
        critical  = $true
        timeout   = 300
    }
    train_elo = @{
        script    = "train_ncaab_elo.py"
        args      = @("--end", "2026")
        critical  = $true
        timeout   = 180
    }
    scrape_barttorvik = @{
        script    = "fetch_barttorvik_data.py"
        args      = @("--seasons", "2026", "--scrape")
        critical  = $false
        timeout   = 120
    }
    fetch_opening_odds = @{
        script    = "fetch_opening_odds.py"
        args      = @()
        critical  = $false
        timeout   = 180
    }
    generate_dashboard = @{
        script    = "generate_dashboard_data.py"
        args      = @()
        critical  = $false
        timeout   = 60
    }
    deploy_dashboard = @{
        script    = "deploy_dashboard.py"
        args      = @()
        critical  = $false
        timeout   = 90
    }
}

# Skip health check if requested
if ($SkipHealthCheck) {
    $steps.Remove("health_check")
    Write-Log "INFO" "Health check skipped (-SkipHealthCheck)"

    # When health check is skipped, acquire lock upfront
    if (-not $DryRun) {
        $locked = Acquire-PipelineLock
        if (-not $locked) {
            Write-Log "ERROR" "Cannot acquire pipeline lock -- exiting"
            exit 2
        }
    }
}

# NOTE: When health_check IS enabled, lock is acquired AFTER it passes (see main loop).
# Acquiring before health_check caused a self-deadlock: health_check's stale_lock
# detector saw the lock this pipeline created and returned critical, aborting everything.

# Check for checkpoint to resume
$checkpoint = $null
if (-not $Force -and -not $DryRun) {
    $checkpoint = Load-Checkpoint -PipelineType "nightly"
    if ($checkpoint) {
        Write-Log "INFO" "Resuming from checkpoint (started at $($checkpoint.started_at))"
    }
}

# Initialize state
$today = Get-Date -Format "yyyy-MM-dd"
$state = @{
    date           = $today
    pipeline       = "nightly"
    started_at     = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
    steps          = @{}
    overall_status = "running"
}

# Merge checkpoint steps if resuming
if ($checkpoint) {
    foreach ($prop in $checkpoint.steps.PSObject.Properties) {
        $state.steps[$prop.Name] = @{
            status    = $prop.Value.status
            exit_code = $prop.Value.exit_code
            attempt   = $prop.Value.attempt
            error     = $prop.Value.error
        }
    }
}

$hasCriticalFailure = $false
$hasAnyFailure = $false

foreach ($stepName in $steps.Keys) {
    $stepConfig = $steps[$stepName]

    # Skip completed steps (checkpoint resume)
    if ($state.steps.ContainsKey($stepName)) {
        $existing = $state.steps[$stepName]
        if ($existing.status -eq "completed") {
            Write-Log "INFO" "Step [$stepName] already completed (checkpoint) -- skipping"
            continue
        }
    }

    # Skip remaining steps if a critical step failed
    if ($hasCriticalFailure) {
        Write-Log "WARN" "Skipping [$stepName] -- critical failure in earlier step"
        $state.steps[$stepName] = @{
            status    = "skipped"
            exit_code = -1
            attempt   = 0
            error     = "Skipped due to earlier critical failure"
        }
        continue
    }

    Write-Log "INFO" "========== Step: $stepName =========="

    $result = Invoke-PipelineStep `
        -StepName $stepName `
        -Script $stepConfig.script `
        -Arguments $stepConfig.args `
        -TimeoutSeconds $stepConfig.timeout `
        -MaxRetries $MaxRetries `
        -DryRun:$DryRun

    if ($result.exit_code -eq 0) {
        $state.steps[$stepName] = @{
            status    = "completed"
            exit_code = 0
            attempt   = $result.attempt
            duration  = $result.duration
        }

        # Acquire lock AFTER health_check passes (avoids self-deadlock where
        # health_check's stale_lock detector sees the lock we created).
        if ($stepName -eq "health_check" -and -not $DryRun) {
            $locked = Acquire-PipelineLock
            if (-not $locked) {
                Write-Log "ERROR" "Cannot acquire pipeline lock -- exiting"
                Release-PipelineLock
                exit 2
            }
        }
    } else {
        $errorMsg = if ($result.stderr) {
            $result.stderr.Substring(0, [Math]::Min(200, $result.stderr.Length))
        } else {
            "Exit code $($result.exit_code)"
        }

        $state.steps[$stepName] = @{
            status    = "failed"
            exit_code = $result.exit_code
            attempt   = $result.attempt
            error     = $errorMsg
        }

        $hasAnyFailure = $true

        if ($stepConfig.critical) {
            $hasCriticalFailure = $true
            Write-Log "ERROR" "CRITICAL step [$stepName] failed -- aborting pipeline"
            Send-PipelineNotification `
                -Title "Nightly Pipeline FAILED" `
                -Message "Critical step '$stepName' failed: $errorMsg" `
                -Level "error"
        } else {
            Write-Log "WARN" "Non-critical step [$stepName] failed -- continuing"
        }
    }

    # Save checkpoint after each step
    if (-not $DryRun) {
        Save-Checkpoint -State $state
    }
}

# Determine overall status
if ($hasCriticalFailure) {
    $state.overall_status = "critical_failure"
    $exitCode = 2
} elseif ($hasAnyFailure) {
    $state.overall_status = "partial_failure"
    $exitCode = 1
} else {
    $state.overall_status = "completed"
    $exitCode = 0
}

$state.completed_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")

# Save final state
if (-not $DryRun) {
    Save-Checkpoint -State $state
    Release-PipelineLock
}

# Summary
Write-Log "INFO" "========================================"
Write-Log "INFO" "Nightly refresh: $($state.overall_status.ToUpper())"
Write-Log "INFO" "========================================"

foreach ($stepName in $steps.Keys) {
    if ($state.steps.ContainsKey($stepName)) {
        $s = $state.steps[$stepName]
        $icon = switch ($s.status) {
            "completed" { "OK" }
            "failed"    { "FAIL" }
            "skipped"   { "SKIP" }
            default     { "?" }
        }
        Write-Log "INFO" "  [$icon] $stepName (exit=$($s.exit_code), attempt=$($s.attempt))"
    }
}

if ($exitCode -eq 0) {
    Send-PipelineNotification `
        -Title "Nightly Pipeline Success" `
        -Message "All steps completed for $today" `
        -Level "success"
}

Write-Log "INFO" "Log file: $logFile"
exit $exitCode
