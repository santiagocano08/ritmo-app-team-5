"""Structure of the CI workflow (feature 003, US1, FR-001 to FR-007).

The workflow file is read as data; nothing here runs GitHub Actions. PyYAML
parses the bare key ``on`` as the boolean ``True`` (YAML 1.1), so the helper
accepts both spellings.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
COMPOSE = ROOT / "docker-compose.yml"

ANDON = (
    "docker compose --profile tools build tests "
    "&& docker compose --profile tools run --rm tests"
)
CONTRACT_CMD = (
    "uv run --frozen --extra dev pytest "
    "src/data/tests/contract/test_read_fixtures.py -p no:cacheprovider --no-cov"
)
BUILD_CMD = "docker compose --profile tools build"


@pytest.fixture(scope="module")
def raw() -> str:
    assert WORKFLOW.is_file(), f"workflow not found: {WORKFLOW}"
    return WORKFLOW.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def wf(raw: str) -> dict:
    return yaml.safe_load(raw)


def _on(wf: dict) -> dict:
    return wf["on"] if "on" in wf else wf[True]


def _runs(job: dict) -> str:
    return "\n".join(s["run"] for s in job["steps"] if "run" in s)


def test_workflow_name(wf):
    assert wf["name"] == "CI"


def test_triggers(wf):
    on = _on(wf)
    assert "pull_request" in on
    pr = on["pull_request"] or {}
    assert "branches" not in pr, "pull_request must not filter branches"
    assert on["push"]["branches"] == ["main"]


def test_permissions_read_only(wf):
    assert wf["permissions"] == {"contents": "read"}


def test_exact_jobs_independent_on_ubuntu(wf):
    assert set(wf["jobs"]) == {"test", "contract", "build"}
    for name, job in wf["jobs"].items():
        assert job["runs-on"] == "ubuntu-latest", name
        assert "needs" not in job, f"{name} must not depend on another job"


def test_test_job_runs_andon_unchanged(wf):
    job = wf["jobs"]["test"]
    runs = _runs(job)
    assert ANDON in runs
    assert "--cov-fail-under" not in runs
    assert "--cov" not in runs


def test_contract_job_command(wf):
    assert CONTRACT_CMD in _runs(wf["jobs"]["contract"])


def test_build_job_command(wf):
    lines = [ln.strip() for ln in _runs(wf["jobs"]["build"]).splitlines()]
    assert BUILD_CMD in lines


def test_no_secrets_and_env_from_example(raw, wf):
    assert "secrets." not in raw
    for name in ("test", "build"):
        assert "cp .env.example .env" in _runs(wf["jobs"][name]), name


def test_concurrency_cancels_pull_requests_only(wf):
    c = wf["concurrency"]
    assert c["group"] == "ci-${{ github.workflow }}-${{ github.ref }}"
    assert c["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"


def test_every_job_has_timeout(wf):
    for name, job in wf["jobs"].items():
        assert isinstance(job.get("timeout-minutes"), int), name


def test_tests_service_mounts_workflows_and_ops_docs_read_only():
    compose = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))
    volumes = compose["services"]["tests"]["volumes"]
    assert "./.github/workflows:/app/.github/workflows:ro" in volumes
    assert "./docs/ops:/app/docs/ops:ro" in volumes
