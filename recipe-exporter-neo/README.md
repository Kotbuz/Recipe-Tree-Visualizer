# NeoForge in-game recipe export (1.21.1+)

Экспортирует **все зарегистрированные рецепты** из полного инстанса лаунчера (Prism/MultiMC) в `profiles/{id}/bake/recipes.baked.json`.

## Требования

- **JDK 21** для сборки мода
- **RAM 8G** на один экспорт (`NEOFORGE_JAVA_XMX=8G`)
- Инстанс с `libraries/`, `mmc-pack.json` и папкой `minecraft/` (или `mods/` в корне)
- Docker: смонтированы `MinecraftVersions` и папка instances (`INSTANCES_HOST_PATH`)

## Сборка мода

```powershell
cd recipe-exporter-neo/versions/1.21.1
.\gradlew.bat build
```

JAR: `recipe-exporter-neo/dist/recipe-exporter-neo-1.21.1.jar`

## Docker

```powershell
docker compose --profile neo-recipes build recipe-exporter-neo
docker compose --profile neo-recipes up -d
```

В `.env` backend:

```env
NEO_RECIPE_EXPORTER_URL=http://recipe-exporter-neo:8091
```

## API

`POST http://localhost:8091/export`

```json
{
  "minecraft_version": "1.21.1",
  "loader_version": "21.1.89",
  "instance_path": "/host/instances/Technopolis",
  "output_dir": "/data/minecraft/1.21.1/profiles/technopolis/bake",
  "storage_version": "1.21.1",
  "profile_id": "technopolis",
  "force": true
}
```

Backend: `POST /versions/{version}/profiles/{profile_id}/bake-recipes`

## Поведение при ошибке

Старый снимок **не удаляется**. Лог пишется в `bake/bake.log` и `bake_meta.partial.json`.
