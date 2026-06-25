FROM node:20-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        fontconfig \
        libfontconfig1 \
        libfreetype6 \
        libx11-6 \
        libxext6 \
        libxi6 \
        libxrandr2 \
        libgl1-mesa-glx \
        libglib2.0-0 \
        xvfb \
        xauth \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json ./
RUN npm install --omit=dev

COPY render-server.js ./
COPY start-renderer.sh ./
RUN sed -i 's/\r$//' /app/start-renderer.sh && chmod +x /app/start-renderer.sh

ENV PORT=3001
ENV DISPLAY=:99
ENV ALLOWED_ROOTS=/data/mods,/data/rendered,/data/minecraft
ENV RENDER_TIMEOUT_MS=600000
ENV MINECRAFT_VERSION=1.21.4

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:3001/health || exit 1

ENTRYPOINT ["/app/start-renderer.sh"]
