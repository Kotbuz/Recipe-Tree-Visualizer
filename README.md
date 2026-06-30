# Recipe Tree Visualizer

Интерактивный граф производства для Minecraft (vanilla + моды): импорт `.jar`, индексация
предметов/рецептов/машин, **ручное** построение двудольного графа
`Предмет → Рецепт → Предмет` на холсте и расчёт производительности (items/min, количество машин).

## Команда

| Участник | Роль |
|----------|------|
| **Колупаев Ефим** | Тимлид / Frontend (React Flow canvas, поиск, recipe picker) |
| **Бердюгин Евгений** | Архитектор / Backend (parser, indexer, graph, calculator) / DevOps |

## Ключевая идея

- Импорт мода **не строит граф** — только наполняет каталог; холст пуст, ноды добавляет пользователь.
- **Узел ресурса** — предмет на холсте (иконка, название, количество).
- **Узел рецепта** — машина в центре, входы слева, выходы справа.
- Рецепт — **отдельная нода**, не просто линия между предметами.
- Альтернативные рецепты, много входов/выходов, расчёт цепочки (референс: Satisfactory Modeler).

Архитектура и UML (PlantUML → PNG): [docs/architecture.md](docs/architecture.md) · [docs/uml/](docs/uml/)



## Docker — запуск одной командой

Полный стек (backend + frontend + renderer иконок) поднимается одной командой.
Требуется только установленный **Docker Desktop** с поддержкой `docker compose`.

```bash
# 1. Скопировать пример переменных окружения (значений по умолчанию достаточно)
cp .env.example .env

# 2. Собрать образы и запустить все сервисы
docker compose up --build
```

После старта доступны:

| Сервис | URL |
|--------|-----|
| **Swagger UI** (интерактивная документация API) | http://localhost:8000/docs |
| **ReDoc** (альтернативная документация) | http://localhost:8000/redoc |
| **Health-check** бэкенда | http://localhost:8000/health |
| **Frontend** (визуализация графа) | http://localhost:5173 |

Остановка: `Ctrl+C`, затем `docker compose down`.

Каталог `./MinecraftVersions` монтируется в контейнеры backend и renderer (read-write —
туда складываются отрендеренные иконки). Логи бэкенда пишутся в `backend/logs/` (в консоль
контейнера **и** в ротируемые файлы). Сервис `recipe-exporter` (JVM-экспорт рецептов для
legacy-версий Forge) вынесен в профиль `legacy-recipes` и по умолчанию не стартует.

## Backend — локальный запуск

```bash
cp .env.example .env
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Frontend — быстрый старт

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

- Сайт: http://localhost:5173/#preview

## Структура backend

```
backend/app/
  api/routes/     # маршруты FastAPI: mods, items, recipes, graph, versions, modpack, profiles, health
  services/       # бизнес-логика (ModService, GraphService, RecipeService, …)
  parser/         # .jar (ZIP) → сырые данные модов
  recipes/        # извлечение/нормализация рецептов, реестр, провайдеры (jar/vanilla/kubejs)
  indexer/        # реестр предметов и модов
  graph/          # двудольный граф «Предмет → Рецепт → Предмет» (networkx)
  calculator/     # расчёт производительности и нормализация
  mod_deps/       # резолв зависимостей модов (CurseForge + Modrinth)
  schemas/        # Pydantic v2 модели запросов/ответов
  core/           # config (env), logging (Loguru)
```

Слои: **routes (api) → services (бизнес-логика) → parser / recipes / graph (доступ к данным и алгоритмы)**.

## API

Полный список и схемы запросов/ответов — в Swagger UI (`/docs`). Основные группы маршрутов:

| Префикс | Назначение |
|---------|------------|
| `GET /health` | Проверка живости сервиса |
| `/mods` | Загрузка `.jar`, список и удаление модов |
| `/items` | Поиск предметов и их рецептов в каталоге |
| `/recipes` | Поиск рецептов (по выходу/входу/фокусу, фильтры) |
| `/graph` | Расчёт производительности по графу (items/min, машины, сырьё) |
| `/versions` | Версии Minecraft, установка, проверка зависимостей |
| `/versions/{version}/profiles` | Профили модпаков, проверка целостности и синхронизация |
| `/modpack` | Инспекция архива/папки модпака |

`GET /recipes` и `CanvasRecipeNode` поддерживают `duration_ticks` (override на ноде; иначе из рецепта, иначе 100 тиков).

## Переменные окружения

Полная карта — в [`.env.example`](.env.example). Значений по умолчанию достаточно для запуска;
секреты (`CURSEFORGE_API_KEY`) опциональны и хранятся только в `.env` (в репозитории — лишь пример).

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `API_HOST` | Хост Uvicorn | `0.0.0.0` |
| `API_PORT` | Порт API | `8000` |
| `LOG_LEVEL` | Уровень логов (Loguru) | `INFO` |
| `LOG_DIR` | Каталог ротируемых лог-файлов | `logs` |
| `MODS_AUTO_LOAD_ON_STARTUP` | Загружать сохранённые моды при старте | `true` |
| `MOD_UPLOAD_MAX_BYTES` | Лимит размера загружаемого `.jar` | `268435456` (256 МБ) |
| `MINECRAFT_VERSIONS_DIR` | Каталог версий Minecraft | `../MinecraftVersions` |
| `MINECRAFT_DEFAULT_VERSION` | Версия по умолчанию | `26.2` |
| `RENDERER_URL` | URL сервиса рендера иконок | `http://localhost:3001` |
| `RECIPE_EXPORTER_URL` | URL JVM-экспортёра рецептов (опц.) | пусто |
| `CURSEFORGE_API_KEY` | Ключ CurseForge для резолва зависимостей (секрет) | пусто |
| `CORS_ORIGINS` | Разрешённые origins (через запятую) | `http://localhost:5173,http://127.0.0.1:5173,http://localhost` |

## Разработка

```bash
cd backend
uv run pytest
uv run ruff check app tests
uv run ruff format --check app tests
uv run mypy app
```

Пересборка UML:

```bash
cd docs/uml
java -jar plantuml.jar -tpng *.puml
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
