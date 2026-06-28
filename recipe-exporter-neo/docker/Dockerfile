# syntax=docker/dockerfile:1

FROM eclipse-temurin:21-jre-jammy

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 ca-certificates bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/rtv-recipe-exporter-neo

RUN mkdir -p baked-mods dist

# Build on host first; image still starts without jar (bake will fail with clear log).
COPY docker/run-neo-export.sh docker/neoforge_launcher.py docker/export-server.py docker/entrypoint.sh ./
COPY dist/ dist/
RUN sed -i 's/\r$//' run-neo-export.sh entrypoint.sh export-server.py \
    && chmod +x run-neo-export.sh entrypoint.sh export-server.py \
    && if [ -f dist/recipe-exporter-neo-1.21.1.jar ]; then \
         cp -f dist/recipe-exporter-neo-1.21.1.jar baked-mods/rtv-recipe-exporter-neo.jar; \
       fi

ENV HOST=0.0.0.0 \
    PORT=8091 \
    EXPORT_SCRIPT=/opt/rtv-recipe-exporter-neo/run-neo-export.sh \
    SUPPORTED_MINECRAFT_VERSIONS=1.21.1 \
    EXPORT_TIMEOUT_SECONDS=3600 \
    NEOFORGE_JAVA_XMX=8G \
    EXPORTER_MOD_JAR=/opt/rtv-recipe-exporter-neo/baked-mods/rtv-recipe-exporter-neo.jar

EXPOSE 8091

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8091/health')" || exit 1

ENTRYPOINT ["/opt/rtv-recipe-exporter-neo/entrypoint.sh"]
