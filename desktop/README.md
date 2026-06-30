# Recipe Tree Visualizer — Desktop (Tauri)

Нативная оболочка `.exe` для Windows: веб-UI + локальный backend без Docker.

## Требования

1. [Rust](https://rustup.rs/) (`rustup default stable`)
2. [Node.js](https://nodejs.org/) 20+
3. [uv](https://docs.astral.sh/uv/) — для Python backend
4. JDK 8 / 17 / 21 на компьютере (выбор в UI → **Модпак → Java (JVM)**)

## Сборка frontend

```powershell
cd ..\frontend
npm ci
npm run build
```

## Сборка .exe

```powershell
cd desktop
npm install
npm run build
```

Артефакт: `desktop\src-tauri\target\release\recipe-tree-visualizer-desktop.exe`

## Режим разработки

Запустите backend и Vite отдельно, затем:

```powershell
cd desktop
npm run dev
```

Или быстрый лаунчер без Rust (открывает браузер):

```powershell
.\scripts\launch-rtv-desktop.ps1
```

## Что делает desktop

- Поднимает `uvicorn` (backend) как дочерний процесс
- Открывает WebView на `http://127.0.0.1:8000` (production) или Vite dev URL
- Передаёт `JAVA_HOME` из настроек пользователя в дочерние JVM-процессы (через backend `data/java_settings.json`)

Docker-сервисы `recipe-exporter-neo` и `renderer` для полного экспорта по-прежнему можно запускать через `docker compose` или подключать локально через `.env`.
