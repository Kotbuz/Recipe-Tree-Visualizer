# Запуск RTV без Docker и без Tauri (браузер + локальный backend).
# Требуется: uv, Node (опционально Vite), JDK в PATH или через UI «Java (JVM)».

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $Root "backend"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv не найден. Установите: https://docs.astral.sh/uv/"
}

# Предпочитаем JDK 21, если установлена
$JdkCandidates = @(
    "C:\Program Files\Java\jdk-21",
    "C:\Program Files\Eclipse Adoptium\jdk-21*",
    "C:\Program Files\Java\jdk-17",
    "C:\Program Files\Eclipse Adoptium\jdk-8*"
)
foreach ($pattern in $JdkCandidates) {
    $resolved = Get-Item $pattern -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($resolved) {
        $env:JAVA_HOME = $resolved.FullName
        $env:Path = "$($env:JAVA_HOME)\bin;$env:Path"
        break
    }
}

Write-Host "JAVA_HOME=$env:JAVA_HOME"
Write-Host "Запуск backend на http://127.0.0.1:8000 ..."

$backend = Start-Process -FilePath "uv" `
    -ArgumentList @("run", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $BackendDir `
    -PassThru `
    -WindowStyle Minimized

Start-Sleep -Seconds 3
Start-Process "http://127.0.0.1:8000"

Write-Host "Backend PID $($backend.Id). Закройте окно или Ctrl+C здесь для остановки."
try {
    Wait-Process -Id $backend.Id
} finally {
    if (-not $backend.HasExited) {
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    }
}
