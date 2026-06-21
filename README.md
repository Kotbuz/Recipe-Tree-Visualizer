# Recipe Tree Visualizer

Интерактивный граф производства для Minecraft (vanilla + моды): импорт `.jar`, индексация
предметов/рецептов/машин, ручное или автоматическое построение **двудольного графа**
`Предмет → Рецепт → Предмет` и расчёт производительности (items/min, количество машин).

## Команда

| Участник | Роль |
|----------|------|
| **Колупаев Ефим** | Тимлид / Frontend (React Flow canvas, поиск, recipe picker) |
| **Бердюгин Евгений** | Архитектор / Backend (parser, indexer, graph, calculator) / DevOps |

## Ключевая идея

- **Узел ресурса** — предмет на холсте (иконка, название, количество).
- **Узел рецепта** — машина в центре, входы слева, выходы справа.
- Рецепт — **отдельная нода**, не просто линия между предметами.
- Поддержка альтернативных рецептов, много входов/выходов, расчёт цепочки как в Factorio.

Архитектура и UML (PlantUML → PNG): [docs/architecture.md](docs/architecture.md) · [docs/uml/](docs/uml/)

## Backend — быстрый старт

```bash
cp .env.example .env
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Структура backend (целевая)

```
backend/app/
  api/routes/     # /mods, /items, /graph
  services/       # ModService, GraphService
  parser/         # .jar → raw data
  indexer/        # Item, Recipe, Machine registry
  graph/          # двудольный граф, auto-build
  calculator/     # производительность, нормализация
  schemas/        # Pydantic-модели
  core/           # config, logging
```

## API (черновик)

| Метод | Путь | Назначение |
|-------|------|------------|
| POST | `/mods/upload` | Загрузка `.jar` (один или несколько) |
| POST | `/mods/modpack` | Импорт модпака |
| GET | `/items/search` | Поиск предмета |
| GET | `/items/{id}/recipes` | Альтернативные рецепты |
| POST | `/graph/auto-build` | Автопостроение цепочки |
| POST | `/graph/calculate` | Расчёт items/min и машин |

## Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `API_HOST` | Хост Uvicorn | `0.0.0.0` |
| `API_PORT` | Порт API | `8000` |
| `LOG_LEVEL` | Уровень логов | `INFO` |
| `LOG_DIR` | Каталог лог-файлов | `logs` |
| `MODS_STORAGE_DIR` | Хранилище `.jar` | `data/mods` |
| `CORS_ORIGINS` | Origins для CORS | `http://localhost:5173` |

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
