param(
    [string]$Version = "1.7.10",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
)

$ErrorActionPreference = "Stop"
$projectDir = Join-Path $PSScriptRoot "."
$outputDir = Join-Path $RepoRoot "MinecraftVersions\$Version\recipe"
$modsDir = Join-Path $RepoRoot "MinecraftVersions\$Version\mods"

Push-Location $projectDir
try {
    & .\gradlew.bat runExport `
        "-PoutputDir=$outputDir" `
        "-PmodsDir=$modsDir"
} finally {
    Pop-Location
}
