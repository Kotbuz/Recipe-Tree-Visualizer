#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/rtv-recipe-exporter"
FORGE_DIR="${FORGE_DIR:-/opt/forge}"
FORGE_RUNTIME_ROOT="${FORGE_RUNTIME_ROOT:-/opt/forge-runtime}"

if ! compgen -G "${FORGE_DIR}/forge-*-universal.jar" > /dev/null 2>&1; then
  if [[ -n "${FORGE_BUILD:-}" && -d "${FORGE_RUNTIME_ROOT}/${FORGE_BUILD}" ]]; then
    FORGE_DIR="${FORGE_RUNTIME_ROOT}/${FORGE_BUILD}"
  elif [[ -d "${FORGE_RUNTIME_ROOT}" ]]; then
    found="$(find "${FORGE_RUNTIME_ROOT}" -name 'forge-*-universal.jar' -print -quit 2>/dev/null || true)"
    if [[ -n "${found}" ]]; then
      FORGE_DIR="$(dirname "${found}")"
    fi
  fi
fi

export FORGE_DIR
mkdir -p "${FORGE_DIR}/baked-mods" "${FORGE_DIR}/mods"

if [[ -f "${APP_DIR}/baked-mods/rtv-recipe-exporter.jar" ]]; then
  cp -f "${APP_DIR}/baked-mods/rtv-recipe-exporter.jar" "${FORGE_DIR}/baked-mods/"
fi

if [[ -d "${FORGE_DIR}" && ! -f "${FORGE_DIR}/eula.txt" ]]; then
  echo "eula=true" > "${FORGE_DIR}/eula.txt"
fi

if ! compgen -G "${FORGE_DIR}/forge-*-universal.jar" > /dev/null 2>&1; then
  echo "[entrypoint] WARNING: Forge universal jar not found (FORGE_DIR=${FORGE_DIR})" >&2
  echo "[entrypoint] Install Forge via backend UI or Gradle; files go to recipe-exporter/forge-runtime/1.7.10/" >&2
  echo "[entrypoint] /health works; POST /export fails until Forge is on the mounted volume." >&2
fi

exec python3 "${APP_DIR}/export-server.py"
