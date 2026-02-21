# pipeline-common.ps1 -- Shared functions for pipeline orchestrators.
# Dot-source this file: . "$PSScriptRoot\pipeline-common.ps1"

$Script:ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$Script:VenvPython = Join-Path $Script:ProjectRoot "venv\Scripts\python.exe"
$Script:LogDir = Join-Path $Script:ProjectRoot "logs"
$Script:StateFile = Join-Path $Script:LogDir "pipeline-state.json"
$Script:LockFile = Join-Path $Script:LogDir "pipeline.lock"

# Ensure logs directory exists
if (-not (Test-Path $Script:LogDir)) {
    New-Item -ItemType Directory -Path $Script:LogDir -Force | Out-Null
}

function Import-DotEnv {
    <#
    .SYNOPSIS
        Load .env file variables into the current process scope.
    #>
    param(
        [string]$Path = (Join-Path $Script:ProjectRoot ".env")
    )

    if (-not (Test-Path $Path)) {
        Write-Log "WARN" ".env file not found: $Path"
        return
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line -split "=", 2
            $key = $parts[0].Trim()
            $value = $parts[1].Trim().Trim('"').Trim("'")
            if ($key -and -not [System.Environment]::GetEnvironmentVariable($key)) {
                [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
            }
        }
    }
}

function Write-Log {
    <#
    .SYNOPSIS
        Timestamped log to console + file.
    #>
    param(
        [Parameter(Mandatory)][string]$Level,
        [Parameter(Mandatory)][string]$Message,
        [string]$LogFile = $Script:CurrentLogFile
    )

    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $entry = "[$ts] [$Level] $Message"

    switch ($Level.ToUpper()) {
        "ERROR" { Write-Host $entry -ForegroundColor Red }
        "WARN"  { Write-Host $entry -ForegroundColor Yellow }
        "OK"    { Write-Host $entry -ForegroundColor Green }
        default { Write-Host $entry }
    }

    if ($LogFile) {
        $entry | Out-File -FilePath $LogFile -Append -Encoding utf8
    }
}

function Initialize-PipelineLog {
    <#
    .SYNOPSIS
        Set up the log file for this run.
    #>
    param(
        [Parameter(Mandatory)][string]$PipelineType
    )

    $date = Get-Date -Format "yyyy-MM-dd"
    $Script:CurrentLogFile = Join-Path $Script:LogDir "pipeline-${PipelineType}-${date}.log"

    # Write header
    $header = @"
========================================
Pipeline: $PipelineType
Date: $date
Started: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
========================================
"@
    $header | Out-File -FilePath $Script:CurrentLogFile -Append -Encoding utf8
    return $Script:CurrentLogFile
}

function Load-Checkpoint {
    <#
    .SYNOPSIS
        Load pipeline checkpoint state from JSON file.
    #>
    param(
        [string]$PipelineType = "nightly"
    )

    if (-not (Test-Path $Script:StateFile)) {
        return $null
    }

    try {
        $state = Get-Content $Script:StateFile -Raw | ConvertFrom-Json
        $today = Get-Date -Format "yyyy-MM-dd"

        # Only resume checkpoints from today and same pipeline type
        if ($state.date -eq $today -and $state.pipeline -eq $PipelineType -and $state.overall_status -ne "completed") {
            return $state
        }
        return $null
    } catch {
        Write-Log "WARN" "Failed to load checkpoint: $_"
        return $null
    }
}

function Save-Checkpoint {
    <#
    .SYNOPSIS
        Atomically save pipeline checkpoint state.
    #>
    param(
        [Parameter(Mandatory)][hashtable]$State
    )

    $json = $State | ConvertTo-Json -Depth 5
    $tmpFile = "$($Script:StateFile).tmp"

    try {
        $json | Out-File -FilePath $tmpFile -Encoding utf8 -NoNewline
        Move-Item -Path $tmpFile -Destination $Script:StateFile -Force
    } catch {
        Write-Log "ERROR" "Failed to save checkpoint: $_"
        # Clean up temp file
        if (Test-Path $tmpFile) { Remove-Item $tmpFile -Force }
    }
}

function Send-PipelineNotification {
    <#
    .SYNOPSIS
        Send notification via Slack webhook (optional).
    #>
    param(
        [Parameter(Mandatory)][string]$Title,
        [Parameter(Mandatory)][string]$Message,
        [string]$Level = "info"
    )

    $webhookUrl = [System.Environment]::GetEnvironmentVariable("SLACK_WEBHOOK_URL")
    if (-not $webhookUrl) {
        Write-Log "INFO" "Notification (no Slack configured): $Title - $Message"
        return
    }

    $emoji = switch ($Level) {
        "error"   { ":red_circle:" }
        "warning" { ":warning:" }
        "success" { ":white_check_mark:" }
        default   { ":information_source:" }
    }

    $payload = @{
        text = "$emoji *$Title*`n$Message"
    } | ConvertTo-Json

    try {
        Invoke-RestMethod -Uri $webhookUrl -Method Post -Body $payload -ContentType "application/json" | Out-Null
        Write-Log "INFO" "Slack notification sent: $Title"
    } catch {
        Write-Log "WARN" "Slack notification failed: $_"
    }
}

function Invoke-PipelineStep {
    <#
    .SYNOPSIS
        Run a Python script with timeout, retry, and output capture.
    .OUTPUTS
        Hashtable with: exit_code, stdout, stderr, duration, attempt
    #>
    param(
        [Parameter(Mandatory)][string]$StepName,
        [Parameter(Mandatory)][string]$Script,
        [string[]]$Arguments = @(),
        [int]$TimeoutSeconds = 300,
        [int]$MaxRetries = 1,
        [switch]$DryRun
    )

    if ($DryRun) {
        $argStr = if ($Arguments.Count -gt 0) { " " + ($Arguments -join " ") } else { "" }
        Write-Log "INFO" "[DRY RUN] Would run: $Script$argStr (timeout: ${TimeoutSeconds}s)"
        return @{
            exit_code = 0
            stdout = "[dry run]"
            stderr = ""
            duration = 0
            attempt = 0
        }
    }

    $scriptPath = Join-Path $Script:ProjectRoot "scripts" $Script

    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        Write-Log "INFO" "Step [$StepName] attempt $attempt/$MaxRetries -- $Script"

        $startTime = Get-Date
        $stdoutFile = [System.IO.Path]::GetTempFileName()
        $stderrFile = [System.IO.Path]::GetTempFileName()

        try {
            $allArgs = @($scriptPath) + $Arguments
            $proc = Start-Process -FilePath $Script:VenvPython `
                -ArgumentList $allArgs `
                -WorkingDirectory $Script:ProjectRoot `
                -RedirectStandardOutput $stdoutFile `
                -RedirectStandardError $stderrFile `
                -NoNewWindow -PassThru

            $exited = $proc.WaitForExit($TimeoutSeconds * 1000)
            $duration = ((Get-Date) - $startTime).TotalSeconds

            if (-not $exited) {
                $proc.Kill()
                Write-Log "ERROR" "Step [$StepName] timed out after ${TimeoutSeconds}s"
                $stdout = if (Test-Path $stdoutFile) { Get-Content $stdoutFile -Raw } else { "" }
                $stderr = "TIMEOUT after ${TimeoutSeconds}s"
                $exitCode = 124  # timeout convention
            } else {
                $exitCode = $proc.ExitCode
                $stdout = if (Test-Path $stdoutFile) { Get-Content $stdoutFile -Raw } else { "" }
                $stderr = if (Test-Path $stderrFile) { Get-Content $stderrFile -Raw } else { "" }
            }

            # Log output to file
            if ($stdout) { Write-Log "INFO" "[$StepName stdout] $($stdout.Substring(0, [Math]::Min(500, $stdout.Length)))" }
            if ($stderr -and $exitCode -ne 0) { Write-Log "ERROR" "[$StepName stderr] $($stderr.Substring(0, [Math]::Min(500, $stderr.Length)))" }

            if ($exitCode -eq 0) {
                Write-Log "OK" "Step [$StepName] completed in ${duration}s (exit code 0)"
                return @{
                    exit_code = 0
                    stdout = $stdout
                    stderr = $stderr
                    duration = [math]::Round($duration, 1)
                    attempt = $attempt
                }
            }

            Write-Log "WARN" "Step [$StepName] failed (exit code $exitCode, attempt $attempt/$MaxRetries)"

            if ($attempt -lt $MaxRetries) {
                $backoff = $attempt * 5
                Write-Log "INFO" "Retrying in ${backoff}s..."
                Start-Sleep -Seconds $backoff
            }
        } finally {
            # Clean up temp files
            if (Test-Path $stdoutFile) { Remove-Item $stdoutFile -Force -ErrorAction SilentlyContinue }
            if (Test-Path $stderrFile) { Remove-Item $stderrFile -Force -ErrorAction SilentlyContinue }
        }
    }

    # All attempts failed
    Write-Log "ERROR" "Step [$StepName] FAILED after $MaxRetries attempts"
    return @{
        exit_code = $exitCode
        stdout = $stdout
        stderr = $stderr
        duration = [math]::Round(((Get-Date) - $startTime).TotalSeconds, 1)
        attempt = $MaxRetries
    }
}

function Acquire-PipelineLock {
    <#
    .SYNOPSIS
        Acquire pipeline lock file. Returns $true if acquired.
    #>
    if (Test-Path $Script:LockFile) {
        $age = ((Get-Date) - (Get-Item $Script:LockFile).LastWriteTime).TotalMinutes
        if ($age -gt 60) {
            Write-Log "WARN" "Removing stale lock file (${age}min old)"
            Remove-Item $Script:LockFile -Force
        } else {
            Write-Log "ERROR" "Pipeline lock active (${age}min old) -- another run in progress?"
            return $false
        }
    }

    "$PID $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -FilePath $Script:LockFile -Encoding utf8
    return $true
}

function Release-PipelineLock {
    <#
    .SYNOPSIS
        Release pipeline lock file.
    #>
    if (Test-Path $Script:LockFile) {
        Remove-Item $Script:LockFile -Force -ErrorAction SilentlyContinue
    }
}
