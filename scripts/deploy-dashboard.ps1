<#
.SYNOPSIS
    Deploy NCAAB dashboard to Vercel.

.DESCRIPTION
    Stages the dashboard HTML (as index.html) and JSON data bundle into a
    temporary build directory, then deploys to Vercel via the CLI.

    First run requires interactive `npx vercel` to link the project.
    Subsequent runs (including nightly pipeline) use `npx vercel --prod --yes`.

    Set VERCEL_TOKEN env var for unattended/CI deploys.

.PARAMETER DryRun
    Preview what would be deployed without actually deploying.

.EXAMPLE
    .\scripts\deploy-dashboard.ps1
    .\scripts\deploy-dashboard.ps1 -DryRun
#>

[CmdletBinding()]
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$DashboardSrc = Join-Path $ProjectRoot "dashboards\ncaab_dashboard.html"
$DataSrc = Join-Path $ProjectRoot "data\processed\ncaab_dashboard_bundle.json"
$BuildDir = Join-Path $ProjectRoot ".vercel-build"

# Validate source files exist
if (-not (Test-Path $DashboardSrc)) {
    Write-Error "Dashboard not found: $DashboardSrc"
    exit 1
}
if (-not (Test-Path $DataSrc)) {
    Write-Error "Data bundle not found: $DataSrc"
    exit 1
}

$htmlSize = (Get-Item $DashboardSrc).Length
$jsonSize = (Get-Item $DataSrc).Length
Write-Host "[deploy] Dashboard: $([math]::Round($htmlSize/1KB, 1)) KB"
Write-Host "[deploy] Data bundle: $([math]::Round($jsonSize/1KB, 1)) KB"

if ($DryRun) {
    Write-Host "[deploy] DRY RUN -- would deploy to Vercel:"
    Write-Host "  $DashboardSrc -> index.html"
    Write-Host "  $DataSrc -> ncaab_dashboard_bundle.json"
    exit 0
}

# Stage build directory
if (Test-Path $BuildDir) {
    Remove-Item -Recurse -Force $BuildDir
}
New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
Copy-Item $DashboardSrc (Join-Path $BuildDir "index.html")
Copy-Item $DataSrc (Join-Path $BuildDir "ncaab_dashboard_bundle.json")

Write-Host "[deploy] Build directory staged at $BuildDir"

# Build Vercel CLI args
$vercelArgs = @("vercel", "--prod", "--yes", $BuildDir)
if ($env:VERCEL_TOKEN) {
    $vercelArgs += @("--token", $env:VERCEL_TOKEN)
    Write-Host "[deploy] Using VERCEL_TOKEN for authentication"
}

try {
    Write-Host "[deploy] Deploying to Vercel..."

    # Temporarily allow stderr (npx/vercel write progress to stderr)
    $prevPref = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & cmd /c npx @vercelArgs 2>&1
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $prevPref

    # Print output (filter out ErrorRecord wrappers)
    $lines = @()
    $output | ForEach-Object {
        $line = if ($_ -is [System.Management.Automation.ErrorRecord]) { $_.ToString() } else { $_ }
        $lines += $line
        Write-Host "  $line"
    }

    if ($exitCode -ne 0) {
        Write-Error "[deploy] Vercel deploy failed (exit $exitCode)"
        exit 1
    }

    # Extract URL from output (Vercel prints the production URL)
    $url = $lines | Where-Object { $_ -match "https://" } | Select-Object -Last 1
    if ($url) {
        Write-Host "[deploy] Live at: $($url.Trim())"
    }
    Write-Host "[deploy] Deployed successfully."
} finally {
    # Clean up build directory
    if (Test-Path $BuildDir) {
        Remove-Item -Recurse -Force $BuildDir
    }
}
