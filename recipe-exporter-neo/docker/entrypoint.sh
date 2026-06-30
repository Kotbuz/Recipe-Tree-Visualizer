#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/rtv-recipe-exporter-neo"
mkdir -p "${APP_DIR}/baked-mods"

if [[ -f "${APP_DIR}/dist/recipe-exporter-neo-1.21.1.jar" ]]; then
  cp -f "${APP_DIR}/dist/recipe-exporter-neo-1.21.1.jar" \
    "${APP_DIR}/baked-mods/rtv-recipe-exporter-neo.jar"
fi

chmod +x "${APP_DIR}/run-neo-export.sh" || true

exec "${APP_DIR}/export-server.py"
