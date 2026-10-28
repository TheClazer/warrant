# Public demo image: the Warrant app plus the fictional course portal in one container.
# Requests are enforced by the built-in enforcer here; NVIDIA OpenShell needs a Docker host (see deploy/README.md).
FROM node:20-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY eval ./eval
COPY --from=web /web/dist ./web/dist
ENV WARRANT_DATA_DIR=/data \
    WARRANT_PORTAL_URL=http://127.0.0.1:8201 \
    WARRANT_ENFORCER=proxy \
    PYTHONUNBUFFERED=1
RUN useradd -r -m warrant && mkdir -p /data && chown warrant /data
USER warrant
EXPOSE 8090
CMD ["sh", "-c", "warrant portal --host 127.0.0.1 --port 8201 & exec warrant serve --host 0.0.0.0 --port ${PORT:-8090}"]
