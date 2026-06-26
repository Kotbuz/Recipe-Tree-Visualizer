# syntax=docker/dockerfile:1

FROM eclipse-temurin:8-jre-jammy

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 ca-certificates bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/rtv-recipe-exporter

RUN mkdir -p baked-mods

# Requires a pre-built mod jar (see README: gradlew build on host or in CI).
COPY dist/recipe-exporter-1.7.10.jar baked-mods/rtv-recipe-exporter.jar

COPY docker/run-export.sh docker/export-server.py docker/entrypoint.sh ./
RUN chmod +x run-export.sh entrypoint.sh

ENV HOST=0.0.0.0 \
    PORT=8090 \
    MINECRAFT_ROOT=/data/minecraft \
    FORGE_DIR=/opt/forge \
    FORGE_RUNTIME_ROOT=/opt/forge-runtime \
    EXPORT_SCRIPT=/opt/rtv-recipe-exporter/run-export.sh \
    SUPPORTED_VERSIONS=1.7.10 \
    EXPORT_TIMEOUT_SECONDS=1800 \
    FORGE_JAVA_XMX=2G

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health')" || exit 1

ENTRYPOINT ["/opt/rtv-recipe-exporter/entrypoint.sh"]
