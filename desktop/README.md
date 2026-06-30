# Recipe Tree Visualizer — Desktop (Tauri)



Нативная оболочка `.exe` для Windows: WebView + локальный backend.



## Требования для сборки



1. [Rust](https://rustup.rs/) (`rustup default stable`)

2. [Node.js](https://nodejs.org/) 20+

3. [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) — C++ workload (для Tauri на Windows)



Для **запуска** у пользователя дополнительно:



- [uv](https://docs.astral.sh/uv/) в PATH

- JDK 8 / 17 / 21 (UI → **Модпак → Java (JVM)**)



---



## Сборка .exe локально (одной командой)



Из корня репозитория:



```powershell

.\scripts\build-desktop.ps1

```



С указанием версии:



```powershell

.\scripts\build-desktop.ps1 -Version 0.1.0

```



Результат: папка `release\desktop\`



- `Recipe Tree Visualizer_*_x64-setup.exe` — NSIS installer

- `Recipe-Tree-Visualizer_0.1.0-portable.exe` — portable (если собрался)

- `manifest.json` — список артефактов



Иконки генерируются автоматически (`scripts\ensure-tauri-icons.ps1`), если их ещё нет.



---



## Публикация в GitHub Releases



### Способ 1 — тег (рекомендуется, CI собирает сам)



1. Обновите версию (или передайте в скрипт):

   ```powershell

   .\scripts\build-desktop.ps1 -Version 0.1.0 -VersionOnly

   ```

2. Закоммитьте изменения версии в `desktop/src-tauri/tauri.conf.json`, `package.json`, `Cargo.toml`.

3. Создайте и запушьте тег:

   ```powershell

   git tag v0.1.0

   git push origin v0.1.0

   ```

4. GitHub Actions **Release Desktop (Windows)** соберёт installer и прикрепит к [Release](https://github.com/Kotbuz/Recipe-Tree-Visualizer/releases).



### Способ 2 — ручной запуск workflow



GitHub → **Actions** → **Release Desktop (Windows)** → **Run workflow**



- `version`: `0.1.0`

- `draft`: включить, чтобы сначала проверить черновик



### Способ 3 — локальная сборка + `gh`



```powershell

.\scripts\publish-github-release.ps1 -Version 0.1.0 -Build -Draft

```



Требуется `gh auth login`. Флаг `-Build` сначала вызывает `build-desktop.ps1`.



---



## Режим разработки



```powershell

# Терминал 1 — backend

cd backend

uv run uvicorn app.main:app --reload --port 8000



# Терминал 2 — frontend

cd frontend

npm run dev



# Терминал 3 — Tauri

cd desktop

npm run dev

```



Без Rust — быстрый запуск в браузере:



```powershell

.\scripts\launch-rtv-desktop.ps1

```



---



## Структура



| Путь | Назначение |

|------|------------|

| `scripts/build-desktop.ps1` | Полная сборка Windows |

| `scripts/publish-github-release.ps1` | Загрузка в GitHub Releases через `gh` |

| `scripts/ensure-tauri-icons.ps1` | Генерация иконок |

| `.github/workflows/release-desktop.yml` | CI: тег `v*` → Release |

| `desktop/src-tauri/` | Rust + Tauri конфиг |



Docker (`recipe-exporter-neo`, `renderer`) для полного NeoForge-экспорта — отдельно, см. корневой README.


