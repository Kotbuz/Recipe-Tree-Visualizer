param(
    [string]$Source = "..\..\..\LocalFiles\retrofuturagradle-1.4.9.jar"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$destDir = Join-Path $root "vendor-maven\com\gtnewhorizons\retrofuturagradle\1.4.9"
$destJar = Join-Path $destDir "retrofuturagradle-1.4.9.jar"

if (Test-Path $destJar) {
    Write-Host "Vendor RFG already present: $destJar"
    exit 0
}

if (-not (Test-Path $Source)) {
    Write-Host "Vendor RFG jar is missing: $destJar"
    Write-Host ""
    Write-Host "The repo normally includes this file. If you cloned without it, either:"
    Write-Host "  1. Restore from git: git checkout -- vendor-maven"
    Write-Host "  2. Copy LocalFiles\retrofuturagradle-1.4.9.jar and rerun this script"
    Write-Host "  3. Download:"
    Write-Host "https://nexus.gtnewhorizons.com/repository/public/com/gtnewhorizons/retrofuturagradle/1.4.9/retrofuturagradle-1.4.9.jar"
    exit 1
}

New-Item -ItemType Directory -Force -Path $destDir | Out-Null
Copy-Item $Source $destJar -Force
Write-Host "Installed $destJar"
