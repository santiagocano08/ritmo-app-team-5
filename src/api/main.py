"""
API entry point — Turn-1, US-2.

Exposes a single endpoint:
    GET /healthz → 200 {"status": "healthy"}

Design decisions:
- DB-free health check: the API reports healthy even when the DB is briefly
  unreachable at startup, so a container restart of db does not cascade into
  a failed health probe on api.
- DEBUG=False enforced: uvicorn is run with --no-access-log in production;
  FastAPI itself never exposes stack traces (exception handlers return a
  generic message + correlation_id).
- /api/v1 base reserved but unused in turn 1; no routes hang off it yet.
- No secrets, no RBAC, no JWT — all deferred to turn 2 per the turn map.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.routers.corridor_read import router as corridor_read_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="PulsoFlota API",
    version="0.1.0",
    # Swagger/ReDoc disabled in production via the DISABLE_DOCS env var;
    # for turn 1 we leave them enabled for the workshop (no prod deployment yet).
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    debug=False,
)


# ---------------------------------------------------------------------------
# Exception handler — never expose stack traces (turn-1 no-cost security baseline)
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a generic 500 with a correlation_id; log the real error server-side."""
    correlation_id = str(uuid.uuid4())
    logger.exception(
        "Unhandled exception",
        extra={"correlation_id": correlation_id, "path": str(request.url)},
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "correlation_id": correlation_id,
        },
    )


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@app.get("/healthz", response_model=dict)
async def healthz() -> dict:
    """Liveness / readiness probe.

    DB-free: returns healthy regardless of database reachability.
    Stopping the DB does not make this endpoint unhealthy.
    """
    return {"status": "healthy"}


# ---------------------------------------------------------------------------
# /api/v1 corridor read router (US-05)
# ---------------------------------------------------------------------------
app.include_router(corridor_read_router)
