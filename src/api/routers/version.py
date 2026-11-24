"""Read-only version/build-info endpoint (US-08), mounted under /api/v1.

Reports three build-time facts about the running backend: its application version,
the read-contract version it targets (fixed 1.0.0 this turn) and a source-revision
identifier (`unknown` when the build captured none). The response is built from the
single build-time values in config.py, never inline literals (FR-007). The endpoint
reads no data store (FR-006) and adds no error handling of its own: unhandled errors
bubble to the app's global exception handler (FR-008, research R4).
"""
from __future__ import annotations

from fastapi import APIRouter

from src.pulsoflota.config import (
    READ_CONTRACT_VERSION,
    get_app_version,
    get_source_revision,
)
from src.pulsoflota.models.read.version_info import VersionInfo

router = APIRouter(prefix="/api/v1")


@router.get(
    "/version",
    response_model=VersionInfo,
    summary="Report the running backend build and read-contract version",
)
def get_version() -> VersionInfo:
    return VersionInfo(
        app_version=get_app_version(),
        read_contract_version=READ_CONTRACT_VERSION,
        source_revision=get_source_revision(),
    )
