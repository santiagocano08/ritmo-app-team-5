"""Base images pinned to exact versions and OCI labels (feature 003, FR-030, SC-013)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "Dockerfile"
COMPOSE = ROOT / "docker-compose.yml"


def _dockerfile() -> str:
    assert DOCKERFILE.is_file(), f"Dockerfile not found: {DOCKERFILE}"
    return DOCKERFILE.read_text(encoding="utf-8")


def _stages(text: str) -> dict[str, str]:
    parts = re.split(r"(?m)^FROM .* AS (\w+)\s*$", text)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


def test_base_image_is_pinned_to_patch_version():
    froms = re.findall(r"(?m)^FROM\s+(\S+)", _dockerfile())
    external = [f for f in froms if f not in ("base", "dev", "prod")]
    assert external, "no external FROM found"
    for image in external:
        assert re.fullmatch(r"python:\d+\.\d+\.\d+-slim", image), image


def test_uv_copy_stays_exact():
    assert "COPY --from=ghcr.io/astral-sh/uv:0.9.5 " in _dockerfile()


def test_db_image_is_pinned():
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    assert re.fullmatch(r"postgres:\d+\.\d+", compose["services"]["db"]["image"])


def test_revision_arg_has_default():
    assert re.search(r"(?m)^ARG REVISION=\S+", _dockerfile())


def test_oci_labels_in_dev_and_prod_after_uv_sync():
    stages = _stages(_dockerfile())
    for name in ("dev", "prod"):
        body = stages[name]
        assert "uv sync" in body
        label_pos = body.index("org.opencontainers.image.source")
        assert label_pos > body.index("uv sync"), name
        assert "org.opencontainers.image.revision=$REVISION" in body, name
        assert "org.opencontainers.image.title" in body, name
        assert "ARG REVISION" in body, name
        assert "USER appuser" in body, name


def test_stages_users_and_prod_cmd_unchanged():
    text = _dockerfile()
    stages = _stages(text)
    assert {"dev", "prod"} <= set(stages)
    assert "--uid 10001" in text
    assert 'CMD ["python", "-m", "uvicorn", "src.api.main:app"' in stages["prod"]
