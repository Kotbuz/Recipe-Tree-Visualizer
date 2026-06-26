param(
    [string]$Version = "1.7.10",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
)

$ErrorActionPreference = "Stop"
$outputDir = Join-Path $RepoRoot "MinecraftVersions\$Version\recipe"
$modsDir = Join-Path $RepoRoot "MinecraftVersions\$Version\mods"
$backendDir = Join-Path $RepoRoot "backend"

Push-Location $backendDir
try {
    uv run python -c @"
from app.services.jvm_recipe_export_service import jvm_recipe_export_service

count = jvm_recipe_export_service.ensure_exported('$Version', force=True)
print(f'Exported {count} recipe file(s)')
"@
} finally {
    Pop-Location
}
