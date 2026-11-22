"""Seed recommendations (004 FR-018, FR-019): demo and test data until the recommendation door exists.

`recommendations.json` is a JSON array of objects shaped as `contracts/read/recommendation.schema.json`
v1.0.0. The simulator reads it to know what an approved `rec_id` means; data loads the same file into
`config.seed_recommendation`, so both sides use one source. It is not a contract (spec, open integration
items). Each entry is validated with the generated model. The generated model does not bound a hold's
`duration_s` (the 0 to 90 s limit sits in the schema's `if/then/else`); the hold executor and the
callers of this loader enforce `MAX_HOLD_S`, so an entry above 90 s loads.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from src.pulsoflota.config import get_seed_recommendations_path
from src.pulsoflota.models.read.recommendation import RecommendationV100

DEFAULT_PATH = Path(__file__).resolve().parent / "recommendations.json"


class SeedError(ValueError):
    """The seed file cannot be read or an entry is invalid. The message carries no payload detail."""


def seed_path(path: str | Path | None = None) -> Path:
    return Path(path or get_seed_recommendations_path() or DEFAULT_PATH)


def load_recommendations(path: str | Path | None = None) -> list[RecommendationV100]:
    """Read and validate the seed file (`path`, else SEED_RECOMMENDATIONS_PATH, else the built-in file)."""
    target = seed_path(path)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SeedError(f"cannot read the seed recommendations file {target.name}") from None
    if not isinstance(raw, list):
        raise SeedError("the seed recommendations file must be a JSON array")
    entries: list[RecommendationV100] = []
    for i, item in enumerate(raw):
        try:
            entries.append(RecommendationV100.model_validate(item))
        except ValidationError as exc:
            fields = ".".join(str(p) for p in exc.errors()[0]["loc"])
            raise SeedError(f"seed recommendation #{i} is invalid at {fields}") from None
    ids = [str(e.rec_id) for e in entries]
    if len(set(ids)) != len(ids):
        raise SeedError("seed recommendations have a duplicate rec_id")
    return entries
