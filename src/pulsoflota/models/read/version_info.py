from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class VersionInfo(BaseModel):
    """Build-time version/build info returned by GET /api/v1/version (US-08).

    Fixed shape: exactly three required string fields, no extras (FR-005, SC-002).
    All three are always present on output; an unknown source revision is emitted
    as the string ``unknown`` rather than ``null`` or an omitted key.
    """

    model_config = ConfigDict(extra="forbid")

    app_version: Annotated[str, Field(min_length=1)]
    read_contract_version: Literal["1.0.0"]
    source_revision: Annotated[str, Field(min_length=1)]
