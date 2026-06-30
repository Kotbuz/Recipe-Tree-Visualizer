# NeoForge in-game recipe export (1.21.1+)

Экспортирует **все зарегистрированные рецепты** из полного инстанса лаунчера (Prism/MultiMC) в `profiles/{id}/bake/recipes.baked.json`.

## Требования

- **JDK 21** для сборки мода
- **RAM 8G** на один экспорт (`NEOFORGE_JAVA_XMX=8G`)
- Инстанс с `libraries/`, `mmc-pack.json` и папкой `minecraft/` (или `mods/` в корне)
- Docker: смонтированы `MinecraftVersions` и папка instances (`INSTANCES_HOST_PATH`)

## Сборка мода

Нужен **JDK 21**. Wrapper (`gradlew` / `gradlew.bat`) уже в репозитории.

```powershell
cd recipe-exporter-neo/versions/1.21.1
$env:JAVA_HOME = "C:\Program Files\Java\jdk-21"   # или ваша JDK 21
.\gradlew.bat build
```

JAR: `recipe-exporter-neo/dist/recipe-exporter-neo-1.21.1.jar`

Без JAR `docker compose build` всё равно пройдёт (в репозитории есть `dist/.gitkeep`), но
экспорт рецептов из игры не заработает, пока не соберёте мод.

## Docker

```powershell
docker compose build recipe-exporter-neo
docker compose up -d
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
