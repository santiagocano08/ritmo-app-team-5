# ---------------------------------------------------------------------------
# PulsoFlota — one Python image for all services (api, ingestion), two targets:
#   prod (default): runtime dependencies only, installed from uv.lock
#   dev:            prod + dev extras (pytest, ...) for the `tests` service
# Dependencies come from uv.lock (uv sync --frozen), so local runs, CI and every
# environment get exactly the same versions. No compiler in the image:
# psycopg[binary] ships wheels. Non-root UID 10001 (turn-1 baseline).
# ---------------------------------------------------------------------------

# Base pinned to an exact patch version so builds are reproducible (feature 003, R17).
FROM python:3.12.16-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

# curl is only for the api healthcheck probe.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid appgroup --no-create-home --shell /sbin/nologin appuser

WORKDIR /app
COPY pyproject.toml uv.lock ./

# --- dev: runtime + dev extras, used by `docker compose --profile tools run tests`
FROM base AS dev
RUN uv sync --frozen --no-install-project --extra dev
COPY src/ ./src/
COPY data/reference/ ./data/reference/
RUN chown -R appuser:appgroup /app
USER appuser
ARG REVISION=unknown
ARG SOURCE_URL=https://github.com/santiagocano08/ritmo-app-team-5
LABEL org.opencontainers.image.source=$SOURCE_URL \
      org.opencontainers.image.revision=$REVISION \
      org.opencontainers.image.title="pulsoflota"

# --- prod (default, last stage): runtime dependencies only
FROM base AS prod
RUN uv sync --frozen --no-install-project --no-dev
COPY src/ ./src/
COPY data/reference/ ./data/reference/
RUN chown -R appuser:appgroup /app
USER appuser
ARG REVISION=unknown
ARG SOURCE_URL=https://github.com/santiagocano08/ritmo-app-team-5
LABEL org.opencontainers.image.source=$SOURCE_URL \
      org.opencontainers.image.revision=$REVISION \
      org.opencontainers.image.title="pulsoflota"
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
