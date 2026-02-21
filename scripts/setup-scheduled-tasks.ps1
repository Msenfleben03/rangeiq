<#
.SYNOPSIS
    Register, unregister, or check status of Windows Task Scheduler tasks
    for the sports betting pipeline.

.DESCRIPTION
    Manages three scheduled tasks:
    - SportsBetting-Nightly   (11:00 PM ET) -- data refresh + model retrain
    - SportsBetting-Morning   (10:00 AM ET) -- predictions + record bets
    - SportsBetting-Settlement (11:30 PM ET) -- settle today's bets

.PARAMETER Action
    One of: register, unregister, status

.EXAMPLE
    .\scripts\setup-scheduled-tasks.ps1 -Action status
    .\scripts\setup-scheduled-tasks.ps1 -Action register
    .\scripts\setup-scheduled-tasks.ps1 -Action unregister
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateSet("register", "unregister", "status")]
    [string]$Action
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$ScriptsDir = Join-Path $ProjectRoot "scripts"

# Task definitions
$Tasks = @(
    @{
        Name        = "SportsBetting-Nightly"
        Description = "Nightly data refresh: fetch scores, retrain Elo, scrape Barttorvik, generate dashboard"
        Script      = Join-Path $ScriptsDir "nightly-refresh.ps1"
        TriggerTime = "23:00"  # 11:00 PM
        Arguments   = "-ExecutionPolicy Bypass -File `"$(Join-Path $ScriptsDir 'nightly-refresh.ps1')`""
    },
    @{
        Name        = "SportsBetting-Morning"
        Description = "Morning betting: settle yesterday's bets, generate today's predictions"
        Script      = Join-Path $ScriptsDir "morning-betting.ps1"
        TriggerTime = "10:00"  # 10:00 AM
        Arguments   = "-ExecutionPolicy Bypass -File `"$(Join-Path $ScriptsDir 'morning-betting.ps1')`""
    },
    @{
        Name        = "SportsBetting-Settlement"
        Description = "Late-night settlement: settle today's completed bets"
        Script      = Join-Path $ScriptsDir "morning-betting.ps1"
        TriggerTime = "23:30"  # 11:30 PM
        Arguments   = "-ExecutionPolicy Bypass -File `"$(Join-Path $ScriptsDir 'morning-betting.ps1')`" -SettleOnly"
    }
)

function Register-Tasks {
    Write-Host "`nRegistering scheduled tasks..." -ForegroundColor Cyan
    Write-Host "NOTE: This requires Administrator privileges.`n" -ForegroundColor Yellow

    foreach ($task in $Tasks) {
        $taskName = $task.Name

        # Check if task already exists
        $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
        if ($existing) {
            Write-Host "  Task '$taskName' already exists -- unregistering first" -ForegroundColor Yellow
            Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        }

        # Parse trigger time
        $timeParts = $task.TriggerTime -split ":"
        $triggerTime = New-ScheduledTaskTrigger `
            -Daily `
            -At "$($task.TriggerTime)"

        # Action: run PowerShell with the script
        $action = New-ScheduledTaskAction `
            -Execute "pwsh.exe" `
            -Argument $task.Arguments `
            -WorkingDirectory $ProjectRoot

        # Settings
        $settings = New-ScheduledTaskSettingsSet `
            -StartWhenAvailable `
            -RestartCount 1 `
            -RestartInterval (New-TimeSpan -Minutes 5) `
            -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -MultipleInstances IgnoreNew

        try {
            Register-ScheduledTask `
                -TaskName $taskName `
                -Description $task.Description `
                -Trigger $triggerTime `
                -Action $action `
                -Settings $settings `
                -RunLevel Highest | Out-Null

            Write-Host "  [OK] $taskName -- daily at $($task.TriggerTime)" -ForegroundColor Green
        } catch {
            Write-Host "  [FAIL] $taskName -- $($_.Exception.Message)" -ForegroundColor Red
            Write-Host "         Try running as Administrator" -ForegroundColor Yellow
        }
    }

    Write-Host "`nDone. Use '-Action status' to verify." -ForegroundColor Cyan
}

function Unregister-Tasks {
    Write-Host "`nUnregistering scheduled tasks..." -ForegroundColor Cyan

    foreach ($task in $Tasks) {
        $taskName = $task.Name
        $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

        if ($existing) {
            try {
                Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
                Write-Host "  [OK] Removed $taskName" -ForegroundColor Green
            } catch {
                Write-Host "  [FAIL] $taskName -- $($_.Exception.Message)" -ForegroundColor Red
            }
        } else {
            Write-Host "  [SKIP] $taskName not found" -ForegroundColor Yellow
        }
    }
}

function Show-TaskStatus {
    Write-Host "`nScheduled Task Status" -ForegroundColor Cyan
    Write-Host ("=" * 70)
    Write-Host ("{0,-28} {1,-12} {2,-20} {3}" -f "Task", "Status", "Next Run", "Last Result")
    Write-Host ("-" * 70)

    foreach ($task in $Tasks) {
        $taskName = $task.Name
        $existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

        if ($existing) {
            $info = Get-ScheduledTaskInfo -TaskName $taskName -ErrorAction SilentlyContinue
            $status = $existing.State
            $nextRun = if ($info.NextRunTime) { $info.NextRunTime.ToString("MM/dd HH:mm") } else { "N/A" }
            $lastResult = if ($info.LastTaskResult -eq 0) { "Success" }
                          elseif ($info.LastTaskResult -eq 267011) { "Never run" }
                          else { "Code: $($info.LastTaskResult)" }

            $color = switch ($status) {
                "Ready"    { "Green" }
                "Running"  { "Yellow" }
                "Disabled" { "DarkGray" }
                default    { "White" }
            }

            Write-Host ("{0,-28} " -f $taskName) -NoNewline
            Write-Host ("{0,-12} " -f $status) -ForegroundColor $color -NoNewline
            Write-Host ("{0,-20} {1}" -f $nextRun, $lastResult)
        } else {
            Write-Host ("{0,-28} " -f $taskName) -NoNewline
            Write-Host "NOT REGISTERED" -ForegroundColor Red
        }
    }

    # Show recent log files
    $logDir = Join-Path $ProjectRoot "logs"
    if (Test-Path $logDir) {
        $logs = Get-ChildItem -Path $logDir -Filter "pipeline-*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 5
        if ($logs) {
            Write-Host "`nRecent Pipeline Logs:" -ForegroundColor Cyan
            foreach ($log in $logs) {
                $size = [math]::Round($log.Length / 1024, 1)
                Write-Host "  $($log.Name) ($($size)KB, $($log.LastWriteTime.ToString('MM/dd HH:mm')))"
            }
        }
    }

    # Show checkpoint state
    $stateFile = Join-Path $logDir "pipeline-state.json"
    if (Test-Path $stateFile) {
        try {
            $state = Get-Content $stateFile -Raw | ConvertFrom-Json
            Write-Host "`nLast Checkpoint:" -ForegroundColor Cyan
            Write-Host "  Pipeline: $($state.pipeline) | Date: $($state.date) | Status: $($state.overall_status)"
        } catch {
            Write-Host "`nCheckpoint file exists but is unreadable" -ForegroundColor Yellow
        }
    }
}

# Execute the requested action
switch ($Action) {
    "register"   { Register-Tasks }
    "unregister" { Unregister-Tasks }
    "status"     { Show-TaskStatus }
}
