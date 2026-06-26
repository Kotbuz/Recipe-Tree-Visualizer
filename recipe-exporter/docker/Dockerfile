# syntax=docker/dockerfile:1

ARG FORGE_VERSION=1.7.10-10.13.4.1448-1.7.10

FROM eclipse-temurin:8-jre-jammy
ARG FORGE_VERSION

RUN apt-get update \
    && apt-get install -y --no-install-recommends wget python3 ca-certificates bash \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/forge

RUN wget -q \
      "https://maven.minecraftforge.net/net/minecraftforge/forge/${FORGE_VERSION}/forge-${FORGE_VERSION}-installer.jar" \
      -O forge-installer.jar \
    && java -jar forge-installer.jar --installServer \
    && echo "eula=true" > eula.txt \
    && rm forge-installer.jar

RUN mkdir -p baked-mods mods

# Requires a pre-built mod jar (see README: gradlew build on host or in CI).
COPY dist/recipe-exporter-1.7.10.jar baked-mods/rtv-recipe-exporter.jar

COPY docker/run-export.sh /opt/forge/run-export.sh
COPY docker/export-server.py /opt/forge/export-server.py
RUN chmod +x /opt/forge/run-export.sh

ENV HOST=0.0.0.0 \
    PORT=8090 \
    MINECRAFT_ROOT=/data/minecraft \
    FORGE_DIR=/opt/forge \
    EXPORT_SCRIPT=/opt/forge/run-export.sh \
    SUPPORTED_VERSIONS=1.7.10 \
    EXPORT_TIMEOUT_SECONDS=1800 \
    FORGE_JAVA_XMX=2G

EXPOSE 8090

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8090/health')" || exit 1

CMD ["python3", "/opt/forge/export-server.py"]
