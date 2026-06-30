# Сборка Windows desktop (.exe installer + portable) через Tauri.
# Использование:
#   .\scripts\build-desktop.ps1
#   .\scripts\build-desktop.ps1 -Version 0.2.0
#   .\scripts\build-desktop.ps1 -SkipFrontend   # если frontend/dist уже собран

param(
    [string] $Version = "",
    [switch] $SkipFrontend,
    [switch] $SkipIcons,
    [switch] $VersionOnly
)

$ErrorActionPreference = "Stop"

function Write-Utf8NoBom([string] $Path, [string] $Content) {
    $utf8 = New-Object System.Text.UTF8Encoding $false
    $normalized = $Content -replace "`r`n", "`n" -replace "`r", "`n"
    if (-not $normalized.EndsWith("`n")) {
        $normalized += "`n"
    }
    [System.IO.File]::WriteAllText($Path, $normalized.Replace("`n", [Environment]::NewLine), $utf8)
}

function Set-CargoTomlVersion([string] $Path, [string] $NewVersion) {
    $lines = Get-Content $Path -Encoding UTF8
    $updated = $lines | ForEach-Object {
        if ($_ -match '^\s*version\s*=') { "version = `"$NewVersion`"" } else { $_ }
    }
    Write-Utf8NoBom $Path (($updated -join "`n"))
}

function Require-Command([string] $Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Команда '$Name' не найдена в PATH. См. desktop/README.md"
    }
}

$Root = Split-Path -Parent $PSScriptRoot
$FrontendDir = Join-Path $Root "frontend"
$DesktopDir = Join-Path $Root "desktop"
$TauriDir = Join-Path $DesktopDir "src-tauri"
$TauriConf = Join-Path $TauriDir "tauri.conf.json"
$OutDir = Join-Path $Root "release\desktop"

Require-Command node
Require-Command npm
if (-not $VersionOnly) {
    Require-Command cargo
}

if (-not $SkipIcons) {
    & (Join-Path $Root "scripts\ensure-tauri-icons.ps1")
}

if ($Version) {
    Write-Host "Setting desktop version to $Version"
    $conf = Get-Content $TauriConf -Raw | ConvertFrom-Json
    $conf.version = $Version
    Write-Utf8NoBom $TauriConf (($conf | ConvertTo-Json -Depth 20))

    $pkgPath = Join-Path $DesktopDir "package.json"
    $pkg = Get-Content $pkgPath -Raw | ConvertFrom-Json
    $pkg.version = $Version
    Write-Utf8NoBom $pkgPath (($pkg | ConvertTo-Json -Depth 20))

    Set-CargoTomlVersion (Join-Path $TauriDir "Cargo.toml") $Version
}

if ($VersionOnly) {
    Write-Host "Version synced to $Version (no build)."
    exit 0
}

$resolvedVersion = (Get-Content $TauriConf -Raw | ConvertFrom-Json).version
Write-Host "Building Recipe Tree Visualizer desktop v$resolvedVersion"

if (-not $SkipFrontend) {
    Push-Location $FrontendDir
    try {
        if (Test-Path "package-lock.json") {
            npm ci --no-audit --no-fund
        } else {
            npm install --no-audit --no-fund
        }
        npm run build
    } finally {
        Pop-Location
    }
}

Push-Location $DesktopDir
try {
    if (Test-Path "package-lock.json") {
        npm ci --no-audit --no-fund
    } else {
        npm install --no-audit --no-fund
    }
    npm run build
} finally {
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$BundleRoot = Join-Path $TauriDir "target\release\bundle"
$artifacts = @()

if (Test-Path $BundleRoot) {
    Get-ChildItem $BundleRoot -Recurse -Include *.exe, *.msi | ForEach-Object {
        $dest = Join-Path $OutDir $_.Name
        Copy-Item $_.FullName $dest -Force
        $artifacts += $dest
    }
}

$portable = Join-Path $TauriDir "target\release\recipe-tree-visualizer-desktop.exe"
if (Test-Path $portable) {
    $portableDest = Join-Path $OutDir "Recipe-Tree-Visualizer_$resolvedVersion-portable.exe"
    Copy-Item $portable $portableDest -Force
    $artifacts += $portableDest
}

$manifest = @{
    version     = $resolvedVersion
    built_at    = (Get-Date).ToUniversalTime().ToString("o")
    artifacts   = $artifacts | ForEach-Object { $_.ToString() }
    bundle_root = $BundleRoot
}
$manifestPath = Join-Path $OutDir "manifest.json"
Write-Utf8NoBom $manifestPath (($manifest | ConvertTo-Json -Depth 5))

Write-Host ""
Write-Host "=== Desktop build complete ===" -ForegroundColor Green
Write-Host "Version: $resolvedVersion"
Write-Host "Output:  $OutDir"
foreach ($file in $artifacts) {
    Write-Host "  - $file"
}
Write-Host ""
Write-Host "GitHub release: git tag v$resolvedVersion && git push origin v$resolvedVersion"
Write-Host "Or local upload: .\scripts\publish-github-release.ps1 -Version $resolvedVersion"
