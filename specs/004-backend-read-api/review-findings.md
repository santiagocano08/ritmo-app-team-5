# Review Findings — US-05 Backend Read API (feature 004)

**Run timestamp**: 2026-11-21 (post-implementation review)
**Feature dir**: `specs/004-backend-read-api/`
**Converge outcome**: `converged` (no convergence tasks appended; `tasks.md` unchanged)
**Coverage minimum source**: `pyproject.toml` → `--cov-fail-under=80`, matching constitution Gate 2 ("coverage > 80 %").

## Validation summary

| Check | Result |
|---|---|
| Full test suite | **553 passed, 23 skipped** (23 skips are `live`/`slow`-marked and offline-reference tests, by design) |
| Total coverage | **94.72 %** vs 80 % minimum — PASS |
| Feature-004 API tests (`src/api/tests`) | 13 passed |
| Linter / formatter / typecheck (ruff, mypy, Bandit) | Not run — **deferred to Turn 2** per `docs/turns-ritmo.md` §3 (Gate 1 in Turn 1 is Pydantic schema validation only). `make lint` is a deliberate placeholder. Recorded as `evolution`, not blocking. |
| Gate 1 (Pydantic schema validation of served contracts) | PASS — contract tests validate both responses against the approved JSON Schemas. |
| Gate 2 (unit + integration tests, coverage > 80 %) | PASS |

No failing check requires a code fix. Nothing was auto-fixed (nothing was broken).

## Findings not auto-fixed

Grouped by severity. No CRITICAL / HIGH / MEDIUM items.

### LOW

#### F1 — `converge` / process — `api.md` requirements-quality checklist is fully unchecked
- **Category**: converge (checklist gate)
- **Severity**: LOW (non-blocking; reviewer-owned review artifact, not implementation state)
- **Area**: `specs/004-backend-read-api/checklists/api.md` (35 items, 0 checked)
- **Detail**: The `/speckit.implement` prompt treats unchecked checklists as a gate that normally prompts a STOP-and-ask. The orchestration for this run was explicitly "do not ask for approval between iterations" and "iterate automatically," so the loop was not halted. This `api.md` checklist is a **reviewer-owned requirements-quality** artifact ("unit tests for the English spec"); `[x]` means a reviewer confirmed the requirement is well-specified, it does **not** mean implementation is incomplete. The implementation itself is complete and verified (see validation summary). The built-in `requirements.md` spec-quality checklist is fully checked (16/16).
- **Failing command**: n/a (gate inspection, not a tool failure).
- **Recommended remediation**: A human reviewer walks `api.md` CHK001–CHK035 and marks each item once satisfied (or records a correction). This is a documentation/review step before merge; it does not block the code from functioning. It must not be auto-checked by an agent — the prompt forbids modifying checklist markers.

#### F2 — environment — three feature-002 health tests require a running `api` container
- **Category**: test (environment, out of scope for feature 004)
- **Severity**: LOW (environment artifact; resolved, no code change)
- **Area**: `src/data/tests/integration/test_health.py` (`test_healthz_returns_200`, `test_healthz_body`, `test_healthz_content_type`)
- **Detail**: On the first full run these three failed with `httpx.ConnectError: Connection refused` because they hit a **live** API over HTTP at `API_BASE_URL` (default `http://localhost:8000`) and no `api` container was running. They belong to feature 002 / US-2 (T008), not feature 004. After starting the `api` compose service they **pass** (3 passed). No code defect; no code was changed.
- **Failing command**: `uv run --extra dev pytest` (with no `api` service up).
- **Recommended remediation**: Run the suite with the `api` service running (or via the compose `tests` profile, which sets `API_BASE_URL=http://api:8000` and `depends_on: api healthy`). This is how CI already runs it. Optionally, these tests could `importorskip`/skip when the API base URL is unreachable, but that is a feature-002 concern and out of scope here.

## Deferred-by-turn items (evolution, informational — not findings)

Per the plan's "Evolution (deferred)" section and `docs/turns-ritmo.md`, the following are intentionally **not** built and do not block: RBAC/JWT, WebSocket/SSE push, history/filtering/pagination/rate-limiting/caching, connection pooling, `age_s` staleness gating, and full SAST/SCA (ruff/mypy/Bandit/pip-audit/Trivy). The 5 Core Principles are not deferred and all PASS.
