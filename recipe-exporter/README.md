# JVM Recipe Exporter

Forge-based recipe export for Minecraft versions without JSON recipes in `client.jar`
(currently **1.7.10**).

## How it works

1. A Forge coremod (`rtvrecipeexporter`) runs inside a **headless Forge server** (`runServer`).
2. On `FMLLoadCompleteEvent` it dumps:
   - `CraftingManager` shaped/shapeless recipes (including `ShapedOreRecipe` / `ShapelessOreRecipe`)
   - `FurnaceRecipes` smelting recipes
   - Forge `OreDictionary` → `MinecraftVersions/{version}/ore_dict.json`
3. Recipe JSON files are written to `MinecraftVersions/{version}/recipe/`.
4. The backend loads recipes and ore dict automatically for JVM-layout versions (`1.7.*`).

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

Ore inputs use `forge:ore_dict` entries resolved via `MinecraftVersions/{version}/ore_dict.json`
(generated on export) with fallback to `backend/data/ore_dict/{version}.json`.

## Build exporter mod

Requirements: **JDK 17+** to run Gradle (toolchain auto-downloads **JDK 8** for Minecraft via Foojay)

RetroFuturaGradle **1.4.9** is vendored under `versions/1.7.10/vendor-maven/` (no GTNH Nexus
needed for the Gradle plugin). Run `.\install-vendor-rfg.ps1` only if that jar is missing.

Optional: copy `gradle.local.properties.example` → `gradle.local.properties` to pin a local JDK 8
path on Windows; CI uses the Foojay toolchain resolver instead.

```powershell
cd recipe-exporter/versions/1.7.10
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

Build the mod jar once (host or GitHub Actions):

```powershell
cd recipe-exporter/versions/1.7.10
.\gradlew.bat build
```

This produces `recipe-exporter/dist/recipe-exporter-1.7.10.jar`, which is baked into the image.

CI workflow **Build recipe-exporter mod** runs the same Gradle build on push (first run still
downloads Minecraft 1.7.10 + Forge). Artifact: `recipe-exporter-1.7.10.jar` → place in
`recipe-exporter/dist/` if you build via Actions instead of locally.

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
