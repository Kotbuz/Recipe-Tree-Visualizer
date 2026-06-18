# Recipe Tree Visualizer

Веб-сервис для извлечения рецептов крафта из модов Minecraft Java (`.jar`) и построения интерактивного нодового дерева зависимостей крафта.

## Команда

| Участник | Роль |
|----------|------|
| **Колупаев Ефим** | Тимлид / Frontend (React Flow, интеграция с API) |
| **Бердюгин Евгений** | Архитектор / Backend (парсер, граф, REST API) / DevOps |

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
  api/routes/     # HTTP-эндпоинты
  services/       # бизнес-логика
  parser/         # чтение .jar (заготовка)
  graph/          # networkx DAG (заготовка)
  schemas/        # Pydantic-модели
  core/           # config, logging
```

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

## Лицензия

MIT — см. [LICENSE](LICENSE).
