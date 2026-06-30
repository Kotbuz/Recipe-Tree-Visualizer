# Создаёт branding/app-icon.png и набор icons/* для Tauri, если icon.ico ещё нет.
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$DesktopDir = Join-Path $Root "desktop"
$BrandingDir = Join-Path $DesktopDir "branding"
$IconsDir = Join-Path $DesktopDir "src-tauri\icons"
$IconIco = Join-Path $IconsDir "icon.ico"

if (Test-Path $IconIco) {
    Write-Host "Tauri icons already present: $IconIco"
    exit 0
}

New-Item -ItemType Directory -Force -Path $BrandingDir | Out-Null
New-Item -ItemType Directory -Force -Path $IconsDir | Out-Null

$PngPath = Join-Path $BrandingDir "app-icon.png"

Add-Type -AssemblyName System.Drawing

$size = 512
$bmp = New-Object System.Drawing.Bitmap $size, $size
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.Clear([System.Drawing.Color]::FromArgb(255, 28, 36, 48))

$brush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 96, 178, 255))
$g.FillEllipse($brush, 96, 96, 320, 320)

$pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(255, 220, 235, 255)), 24
$g.DrawLine($pen, 256, 120, 180, 340)
$g.DrawLine($pen, 256, 120, 332, 340)
$g.DrawLine($pen, 180, 340, 332, 340)

$inner = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 40, 52, 70))
$g.FillEllipse($inner, 196, 196, 120, 120)

$bmp.Save($PngPath, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$bmp.Dispose()

Write-Host "Created $PngPath"

Push-Location $DesktopDir
try {
    if (-not (Test-Path "node_modules")) {
        npm install --no-audit --no-fund
    }
    npx tauri icon $PngPath
} finally {
    Pop-Location
}

Write-Host "Tauri icons generated in $IconsDir"
