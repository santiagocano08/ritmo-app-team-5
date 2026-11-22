"""Read-only corridor endpoints (US-05), mounted under /api/v1.

Both read endpoints resolve the latest gold snapshot once (Q0) and serve the stored,
pre-validated contract document as-is: no business rule is recomputed here (research
R1). When there is no snapshot, or the requested corridor is not the supported one,
a distinguishable HTTP 200 no-data sibling envelope is returned (FR-008/FR-011).
The router adds no error handling of its own: unhandled errors bubble to the app's
global exception handler, which returns a generic body with a correlation_id
(FR-007, research R3).
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

import psycopg
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from src.api.deps import get_db_connection
from src.api.reads.gold_reads import (
    corridor_now_doc,
    latest_snapshot_id,
    source_status_doc,
)
from src.pulsoflota.models.read.corridor_now import CorridorNowV100
from src.pulsoflota.models.read.source_status import SourceStatusV100

router = APIRouter(prefix="/api/v1")

# Turn 1 serves only this corridor; any other id yields the no-data envelope (FR-011).
SUPPORTED_CORRIDOR_ID = "C6-008"

DbConnection = Annotated[psycopg.Connection[dict[str, Any]], Depends(get_db_connection)]


class NoDataCorridor(BaseModel):
    """API-level sibling envelope for corridor_now when no snapshot exists (FR-008)."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["no_data"] = "no_data"
    corridor_id: Annotated[str, Field(min_length=1)]


class NoDataSourceStatus(BaseModel):
    """No-data variant for source-status, mirroring the contract's no_data state (FR-008)."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["no_data"] = "no_data"
    corridor_id: Annotated[str, Field(min_length=1)]
    sources_down: list = Field(default_factory=list, max_length=0)


@router.get(
    "/corridor/{corridor_id}/now",
    response_model=CorridorNowV100 | NoDataCorridor,
    summary="Latest corridor_now snapshot",
)
def get_corridor_now(corridor_id: str, conn: DbConnection) -> CorridorNowV100 | NoDataCorridor:
    snapshot_id = latest_snapshot_id(conn)
    if corridor_id != SUPPORTED_CORRIDOR_ID or snapshot_id is None:
        return NoDataCorridor(corridor_id=corridor_id)

    doc = corridor_now_doc(conn, snapshot_id)
    if doc is None:
        return NoDataCorridor(corridor_id=corridor_id)
    return CorridorNowV100.model_validate(doc)


@router.get(
    "/corridor/{corridor_id}/source-status",
    response_model=SourceStatusV100 | NoDataSourceStatus,
    summary="Latest source_status",
)
def get_source_status(corridor_id: str, conn: DbConnection) -> SourceStatusV100 | NoDataSourceStatus:
    snapshot_id = latest_snapshot_id(conn)
    if corridor_id != SUPPORTED_CORRIDOR_ID or snapshot_id is None:
        return NoDataSourceStatus(corridor_id=corridor_id)

    doc = source_status_doc(conn, snapshot_id)
    if doc is None:
        return NoDataSourceStatus(corridor_id=corridor_id)
    return SourceStatusV100.model_validate(doc)
