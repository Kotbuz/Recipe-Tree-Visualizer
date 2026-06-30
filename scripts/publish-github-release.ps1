# Создаёт GitHub Release и загружает артефакты из release/desktop/.
# Требуется: gh auth login, собранный .\scripts\build-desktop.ps1
#
#   .\scripts\publish-github-release.ps1 -Version 0.1.0
#   .\scripts\publish-github-release.ps1 -Version 0.1.0 -Draft
#   .\scripts\publish-github-release.ps1 -Version 0.1.0 -Build   # собрать перед публикацией

param(
    [Parameter(Mandatory = $true)]
    [string] $Version,
    [switch] $Draft,
    [switch] $Build,
    [string] $Notes = ""
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "GitHub CLI (gh) не найден: https://cli.github.com/"
}

$Root = Split-Path -Parent $PSScriptRoot
$OutDir = Join-Path $Root "release\desktop"
$Tag = if ($Version -match '^v') { $Version } else { "v$Version" }
$VersionNumber = $Tag.TrimStart('v')

if ($Build) {
    & (Join-Path $Root "scripts\build-desktop.ps1") -Version $VersionNumber
}

if (-not (Test-Path $OutDir)) {
    throw "Папка $OutDir не найдена. Сначала запустите .\scripts\build-desktop.ps1"
}

$files = Get-ChildItem $OutDir -File | Where-Object { $_.Extension -in '.exe', '.msi' }
if ($files.Count -eq 0) {
    throw "В $OutDir нет .exe/.msi. Сборка не удалась?"
}

$body = if ($Notes) {
    $Notes
} else {
@"

## Recipe Tree Visualizer $Tag — Desktop (Windows)

### Установка
1. Скачайте ``*-setup.exe`` (NSIS installer) или ``*-portable.exe``.
2. Для JVM-экспорта установите [Temurin JDK](https://adoptium.net/) 8/17/21.
3. Для backend внутри приложения нужен [uv](https://docs.astral.sh/uv/) в PATH.

### Полный экспорт NeoForge 1.21+
Docker-сервисы ``recipe-exporter-neo`` и ``renderer`` — отдельно через ``docker compose`` (см. README репозитория).

"@
}

$ghArgs = @(
    "release", "create", $Tag,
    "--title", "Recipe Tree Visualizer $Tag",
    "--notes", $body
)
if ($Draft) {
    $ghArgs += "--draft"
}

foreach ($file in $files) {
    $ghArgs += $file.FullName
}

Write-Host "Creating release $Tag with $($files.Count) file(s)..."
& gh @ghArgs
Write-Host "Done. Open: gh release view $Tag --web"
