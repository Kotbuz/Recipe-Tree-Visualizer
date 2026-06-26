#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:?Minecraft version required (e.g. 1.7.10)}"
MINECRAFT_ROOT="${MINECRAFT_ROOT:-/data/minecraft}"
FORGE_DIR="${FORGE_DIR:-/opt/forge}"

MODS_DIR="${MINECRAFT_ROOT}/${VERSION}/mods"
OUTPUT_DIR="${MINECRAFT_ROOT}/${VERSION}/recipe"
ORE_DICT_FILE="${MINECRAFT_ROOT}/${VERSION}/ore_dict.json"
EXPORTER_JAR="${FORGE_DIR}/baked-mods/rtv-recipe-exporter.jar"

if [[ ! -f "${EXPORTER_JAR}" ]]; then
  echo "Exporter mod jar not found at ${EXPORTER_JAR}" >&2
  exit 1
fi

mkdir -p "${OUTPUT_DIR}" "${FORGE_DIR}/mods"
rm -f "${FORGE_DIR}/mods"/*.jar

cp "${EXPORTER_JAR}" "${FORGE_DIR}/mods/"

if [[ -d "${MODS_DIR}" ]]; then
  shopt -s nullglob
  for jar in "${MODS_DIR}"/*.jar; do
    base="$(basename "${jar}")"
    if [[ "${base}" == rtv-recipe-exporter*.jar ]]; then
      continue
    fi
    cp "${jar}" "${FORGE_DIR}/mods/"
  done
fi

FORGE_JAR="$(find "${FORGE_DIR}" -maxdepth 1 -name 'forge-*-universal.jar' -print -quit)"
if [[ -z "${FORGE_JAR}" ]]; then
  echo "Forge universal jar not found in ${FORGE_DIR}" >&2
  exit 1
fi

cd "${FORGE_DIR}"

echo "[recipe-exporter] Starting Forge export for ${VERSION}"
echo "[recipe-exporter] Mods: $(ls -1 mods | wc -l) jar(s), output: ${OUTPUT_DIR}"

exec java \
  -Xmx"${FORGE_JAVA_XMX:-2G}" \
  -Drtv.recipe.export=true \
  "-Drtv.recipe.export.dir=${OUTPUT_DIR}" \
  "-Drtv.ore.dict.export.file=${ORE_DICT_FILE}" \
  -jar "${FORGE_JAR}" \
  nogui
