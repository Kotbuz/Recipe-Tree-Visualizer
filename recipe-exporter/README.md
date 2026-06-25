# JVM Recipe Exporter

Offline recipe export for Minecraft eras that do not ship JSON recipes in `client.jar`
(primarily **1.7.10** and mod recipes registered only at runtime).

## Output format

The exporter writes one JSON file per recipe into:

```
MinecraftVersions/{version}/recipe/{recipe_id_with_slashes_as_underscores}.json
```

Each file matches the backend `JsonRecipeParser` schema:

```json
{
  "type": "crafting_shaped",
  "pattern": ["##", "##"],
  "key": {
    "#": { "item": "minecraft:planks", "metadata": 0 }
  },
  "result": { "item": "minecraft:crafting_table", "count": 1 }
}
```

A manifest is written to `recipe/_export_manifest.json`.

## Build (1.7.10)

Requirements:

- JDK 8
- Gradle 7.x

```bash
cd recipe-exporter/versions/1.7.10
gradle build
cp build/libs/recipe-exporter-1.7.10.jar ../../dist/
```

The backend looks for:

- `recipe-exporter/dist/recipe-exporter-1.7.10.jar`
- `recipe-exporter/dist/recipe-exporter-all.jar`

## Run manually

```bash
java -jar recipe-exporter/dist/recipe-exporter-1.7.10.jar \
  --minecraft-version 1.7.10 \
  --client-jar MinecraftVersions/1.7.10/client.jar \
  --mods-dir MinecraftVersions/1.7.10/mods \
  --output-dir MinecraftVersions/1.7.10/recipe
```

## Backend integration

`JvmRecipeExportService.ensure_exported(version)` is called automatically when
loading vanilla recipes for JVM-layout versions (`1.7.*`).

If the exporter jar is missing, the backend logs a warning and continues with
an empty recipe set for that version.

## Implementation notes

- **1.7.10 / early Forge**: export `CraftingManager` shaped/shapeless recipes and
  mod-registered handlers via Forge events after registry init.
- **1.12.2+**: prefer JSON discovery from JARs; JVM export is only needed for
  mods without JSON (IC2, Mekanism 1.7.10, etc.).

JEI source branches per era are useful references for how recipe categories are
registered at runtime, but this exporter must run inside Forge to access live
registries.
