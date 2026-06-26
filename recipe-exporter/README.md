# JVM Recipe Exporter

Forge-based recipe export for Minecraft versions without JSON recipes in `client.jar`
(currently **1.7.10**).

## How it works

1. A Forge coremod (`rtvrecipeexporter`) runs inside a **headless Forge server** (`runServer`).
2. On `FMLLoadCompleteEvent` it dumps:
   - `CraftingManager` shaped/shapeless recipes (including `ShapedOreRecipe` / `ShapelessOreRecipe`)
   - `FurnaceRecipes` smelting recipes
3. JSON files are written to `MinecraftVersions/{version}/recipe/`.
4. The backend loads them automatically for JVM-layout versions (`1.7.*`).

Machine-only recipes (IC2 compressor, Mekanism enrichment, etc.) are **not** exported yet.

## Output format

```json
{
  "id": "minecraft:export/crafting/12",
  "type": "crafting_shaped",
  "pattern": ["##", "##"],
  "key": {
    "#": { "item": "minecraft:planks", "metadata": 0 }
  },
  "result": { "item": "minecraft:crafting_table", "count": 1 }
}
```

Ore inputs use `forge:ore_dict` entries compatible with `backend/data/ore_dict/1.7.10.json`.

## Build exporter mod

Requirements: **JDK 17+** to run Gradle (toolchain auto-downloads **JDK 8** for Minecraft via Foojay)

```powershell
cd recipe-exporter/versions/1.7.10
.\install-vendor-rfg.ps1   # if retrofuturagradle-1.4.9.jar is in LocalFiles/
.\gradlew.bat build
```

The mod jar is copied to `recipe-exporter/dist/recipe-exporter-1.7.10.jar`.

First build downloads Minecraft 1.7.10 + Forge (~5–15 minutes).

## Run export manually

```powershell
cd recipe-exporter/versions/1.7.10
.\run-export.ps1
```

Or with quoted absolute paths (required in PowerShell — unquoted `\1` in `1.7.10` breaks Gradle args):

```powershell
.\gradlew.bat runExport `
  "-PoutputDir=P:\Practice\Recipe-Tree-Visualizer\MinecraftVersions\1.7.10\recipe" `
  "-PmodsDir=P:\Practice\Recipe-Tree-Visualizer\MinecraftVersions\1.7.10\mods"
```

The server starts, exports recipes, and exits automatically.

## Backend integration

`JvmRecipeExportService.ensure_exported("1.7.10")` runs export when
`MinecraftVersions/1.7.10/recipe/` is empty.

Resolution order (`RECIPE_EXPORTER_MODE=auto`, default):

1. **HTTP** — `POST http://recipe-exporter:8090/export` (Docker service)
2. **Gradle** — `gradlew runExport` on the host (dev fallback)
3. **Skip** — warning if neither is available

After export, restart backend or switch to version `1.7.10` in the UI.

## Docker image (recommended for Docker Compose)

The `recipe-exporter` service runs a headless Forge 1.7.10 server with our export mod.
It mirrors the `renderer` pattern: shared `MinecraftVersions` volume + small HTTP API.

### Prerequisites

Build the mod jar once (host or CI with GTNH Maven access):

```powershell
cd recipe-exporter/versions/1.7.10
.\gradlew.bat build
```

This produces `recipe-exporter/dist/recipe-exporter-1.7.10.jar`, which is baked into the image.

If GTNH Nexus times out locally (`Read timed out` on `retrofuturagradle-2.0.2.jar`), use CI:

1. GitHub → Actions → **Build recipe-exporter mod** → Run workflow
2. Download artifact `recipe-exporter-1.7.10.jar`
3. Place it at `recipe-exporter/dist/recipe-exporter-1.7.10.jar`
4. Run `docker compose --profile legacy-recipes build recipe-exporter`

### Build and run

```powershell
docker compose --profile legacy-recipes build recipe-exporter
docker compose --profile legacy-recipes up -d
```

Backend is preconfigured with `RECIPE_EXPORTER_URL=http://recipe-exporter:8090`.

### Manual export

```powershell
curl -X POST http://localhost:8090/export `
  -H "Content-Type: application/json" `
  -d '{"version":"1.7.10"}'
```

Force re-export:

```json
{"version":"1.7.10","force":true}
```

### Image contents

| Layer | Purpose |
|-------|---------|
| `eclipse-temurin:8-jre` | Minecraft 1.7.10 / Forge require Java 8 |
| Forge universal server | Installed at image build via official installer |
| `rtv-recipe-exporter.jar` | Copied from `dist/` at build time |
| `export-server.py` | `GET /health`, `POST /export` |
| `run-export.sh` | Syncs mods from volume, starts Forge once, exits |

### Resource notes

- First Forge start: ~2–4 GB RAM (`FORGE_JAVA_XMX`, default `2G`)
- Export timeout: 30 min (`EXPORT_TIMEOUT_SECONDS`)
- Only one export at a time (HTTP 409 if busy)

### CI suggestion

Build the mod jar in GitHub Actions (GTNH Nexus is usually reachable from CI), upload artifact,
then `docker build` with the jar in `dist/`. Avoid Gradle inside the runtime image.

## Limitations

| Source | Exported |
|--------|----------|
| Vanilla crafting table | Yes |
| Vanilla furnace | Yes |
| Forge ore-shaped recipes | Yes (as `forge:ore_*`) |
| IC2 / AE2 / Mekanism machines | No (runtime-only handlers) |
