# Собирает portable backend для Tauri: embedded Python 3.13 + pip deps + app/.
# Результат: desktop/src-tauri/bin/backend-bundle/
#
#   .\scripts\build-backend-bundle.ps1
#   .\scripts\build-backend-bundle.ps1 -PythonVersion 3.13.2

param(
    [string] $PythonVersion = "3.13.2"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$BundleRoot = Join-Path $Root "desktop\src-tauri\bin\backend-bundle"
$PythonDir = Join-Path $BundleRoot "python"
$BackendDir = Join-Path $BundleRoot "backend"
$CacheDir = Join-Path $Root ".cache\python-embed"
$Requirements = Join-Path $Root "backend\requirements-bundle.txt"

$majorMinor = ($PythonVersion -split '\.')[0] + ($PythonVersion -split '\.')[1]
$embedName = "python-$PythonVersion-embed-amd64.zip"
$embedUrl = "https://www.python.org/ftp/python/$PythonVersion/$embedName"
$embedZip = Join-Path $CacheDir $embedName
$getPipUrl = "https://bootstrap.pypa.io/get-pip.py"
$getPipPath = Join-Path $CacheDir "get-pip.py"

function Ensure-Dir([string] $Path) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

Write-Host "Building backend bundle (Python $PythonVersion embeddable)..."

Ensure-Dir $CacheDir
Ensure-Dir $BundleRoot

if (-not (Test-Path $embedZip)) {
    Write-Host "Downloading $embedUrl"
    Invoke-WebRequest -Uri $embedUrl -OutFile $embedZip -UseBasicParsing
}

if (-not (Test-Path $getPipPath)) {
    Write-Host "Downloading get-pip.py"
    Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipPath -UseBasicParsing
}

if (Test-Path $PythonDir) {
    Remove-Item -Recurse -Force $PythonDir
}
Ensure-Dir $PythonDir
Expand-Archive -Path $embedZip -DestinationPath $PythonDir -Force

$pthName = "python$majorMinor._pth"
$pthPath = Join-Path $PythonDir $pthName
if (-not (Test-Path $pthPath)) {
    throw "Expected $pthPath after extracting embeddable Python"
}

$pthLines = @(
    "python$majorMinor.zip",
    ".",
    "Lib\site-packages",
    "import site"
)
[System.IO.File]::WriteAllLines($pthPath, $pthLines)

Ensure-Dir (Join-Path $PythonDir "Lib\site-packages")

$PythonExe = Join-Path $PythonDir "python.exe"
if (-not (Test-Path $PythonExe)) {
    throw "python.exe not found in $PythonDir"
}

Write-Host "Installing pip..."
& $PythonExe $getPipPath --no-warn-script-location
if ($LASTEXITCODE -ne 0) {
    throw "get-pip.py failed"
}

Write-Host "Installing backend dependencies..."
& $PythonExe -m pip install --no-warn-script-location -r $Requirements
if ($LASTEXITCODE -ne 0) {
    throw "pip install failed"
}

if (Test-Path $BackendDir) {
    Remove-Item -Recurse -Force $BackendDir
}
Ensure-Dir $BackendDir
Copy-Item -Recurse -Force (Join-Path $Root "backend\app") (Join-Path $BackendDir "app")

$marker = Join-Path $BundleRoot "BUNDLE_VERSION.txt"
@(
    "python=$PythonVersion"
    "built_at=$(Get-Date).ToUniversalTime().ToString('o')"
) | Set-Content -Encoding UTF8 $marker

Write-Host ""
Write-Host "Backend bundle ready: $BundleRoot" -ForegroundColor Green
Write-Host "  python.exe  -> $PythonExe"
Write-Host "  backend app -> $(Join-Path $BackendDir 'app')"
