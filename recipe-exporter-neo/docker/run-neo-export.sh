#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/rtv-recipe-exporter-neo"
PYTHON_BIN="${PYTHON_BIN:-python3}"

: "${INSTANCE_PATH:?INSTANCE_PATH is required}"
: "${OUTPUT_DIR:?OUTPUT_DIR is required}"
: "${LOADER_VERSION:?LOADER_VERSION is required}"

exec "${PYTHON_BIN}" "${APP_DIR}/neoforge_launcher.py"
