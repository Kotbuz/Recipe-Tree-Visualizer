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

## Frontend — быстрый старт

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

- Сайт: http://localhost:5173/#preview

## Backend — быстрый старт

```bash
cp .env.example .env
cd backend
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Структура backend

```
backend/app/
  api/routes/     # /mods, /items, /graph, /health
  services/       # ModService, GraphService
  parser/         # .jar → raw data
  indexer/        # Item, Recipe, Machine registry
  graph/          # двудольный граф (manual canvas state)
  calculator/     # производительность, нормализация
  schemas/        # Pydantic-модели
  core/           # config, logging
```

## API

| Метод | Путь | Статус |
|-------|------|--------|
| GET | `/health` | ✅ реализован |
| GET | `/mods` | ✅ список (пустой до импорта) |
| POST | `/mods/upload` | 🔜 заготовка (501) |
| POST | `/mods/modpack` | 🔜 заготовка (501) |
| GET | `/items/search` | ✅ поиск (пустой до индексации) |
| GET | `/items/{id}/recipes` | ✅ альтернативные рецепты |
| POST | `/graph/calculate` | 🔜 заготовка (501) |

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
# Recipe-Tree-Visualizer
веб-сервис для извлечения рецептов крафта из модов Minecraft Java (.jar) и построения интерактивного нодового дерева зависимостей крафта

