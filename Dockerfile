# ---------------------------------------------------------------------------
# PulsoFlota — single Python image for all services (api, ingestion).
# Base: python:3.12-slim (already pulled locally).
# Non-root execution: UID 10001 (turn-1 no-cost security baseline; full
# container hardening deferred to turn 2 per docs/turns-ritmo.md §3.3).
# ---------------------------------------------------------------------------

FROM python:3.12-slim

# -- system deps --------------------------------------------------------------
# gcc is needed for psycopg[binary] wheel; removed after install to keep image
# lean.  Also install curl for the healthcheck probe.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# -- non-root user (UID 10001) ------------------------------------------------
RUN groupadd --gid 10001 appgroup \
    && useradd --uid 10001 --gid appgroup --no-create-home --shell /sbin/nologin appuser

# -- working directory --------------------------------------------------------
WORKDIR /app

# -- install Python deps first (cached layer) ---------------------------------
COPY pyproject.toml ./
# Install pip-based deps (no uv in container; uv is a dev tool).
# Install in a venv owned by appuser.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        "psycopg[binary]>=3.1,<4" \
        "pydantic>=2.5,<3" \
        "fastapi>=0.110,<1" \
        "uvicorn[standard]>=0.27,<1" \
        "openpyxl>=3.1,<4"

# -- copy application source --------------------------------------------------
COPY src/ ./src/
COPY data/reference/ ./data/reference/

# -- hand ownership to appuser ------------------------------------------------
RUN chown -R appuser:appgroup /app

USER appuser

# -- default: run the API (overridden by docker-compose for ingestion) --------
# The api service sets CMD in docker-compose.yml; the ingestion service
# overrides it with the simulator | ingestion pipe.
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
