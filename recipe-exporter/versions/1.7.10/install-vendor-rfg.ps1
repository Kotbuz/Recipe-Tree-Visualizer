param(
    [string]$Source = "..\..\..\LocalFiles\retrofuturagradle-1.4.9.jar"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$destDir = Join-Path $root "vendor-maven\com\gtnewhorizons\retrofuturagradle\1.4.9"
$destJar = Join-Path $destDir "retrofuturagradle-1.4.9.jar"

if (-not (Test-Path $Source)) {
    Write-Host "JAR not found: $Source"
    Write-Host ""
    Write-Host "Download (browser):"
    Write-Host "https://nexus.gtnewhorizons.com/repository/public/com/gtnewhorizons/retrofuturagradle/1.4.9/retrofuturagradle-1.4.9.jar"
    Write-Host ""
    Write-Host "Save as LocalFiles\retrofuturagradle-1.4.9.jar and rerun this script."
    exit 1
}

New-Item -ItemType Directory -Force -Path $destDir | Out-Null
Copy-Item $Source $destJar -Force
Write-Host "Installed $destJar"
