# Review Findings — 006-functional-integration (US-07 Functional Integration)

**Run timestamp:** 2026-11-22 (post-implementation review)
**Feature dir:** `specs/006-functional-integration/`
**Coverage minimum:** 80% — source: Constitution §V ("coverage above 80 %") and `--cov-fail-under=80` in `pyproject.toml` `[tool.pytest.ini_options]` addopts and the `docker-compose.yml` `tests` service.

## Summary

| Stage | Result |
|-------|--------|
| Stage 1 — Converge | `converged` — 0 actionable findings; `tasks.md` left unchanged (no phase appended) |
| Stage 2 — Implement | Skipped (nothing to implement) |
| Stage 3 — Validation | Backend pytest+coverage PASS, frontend ESLint PASS, Vitest+coverage PASS, `tsc --noEmit`+Vite build PASS |
| Stage 4 — Fix/file | Nothing auto-fixed (no failing check); one environment note filed below (LOW) |

## Validation results

| Check | Command | Result |
|-------|---------|--------|
| Backend tests + coverage | `docker compose --profile tools run --rm tests` | **543 passed, 23 skipped**; coverage **92.84%** (≥ 80%) |
| Frontend ESLint | `npm run lint` (`eslint . --ext .ts,.tsx --max-warnings 0`) | **PASS** (0 errors/warnings) |
| Frontend tests + coverage | `npm run test:coverage` (Node 22) | **33 passed / 15 files**; coverage **98.27% lines, 93.97% branch** (≥ 80%) |
| Frontend typecheck + build | `npm run build` (`tsc --noEmit && vite build`, Node 22) | **PASS** (308 modules, built in 8.62s) |

No linter/formatter is configured in-repo for the Python backend (ruff/mypy are named as CI-target norms in AGENTS.md/constitution but have no local config file); the frontend ESLint gate is the configured lint. No formatter-check step exists in either stack's config, so none was run.

## Findings

### LOW

**F1 — environment (not a code defect)**
- **Category:** environment / tooling
- **Severity:** LOW
- **Area:** local dev host Node runtime
- **Command:** `npm run test:coverage` on the host (Node v18.2.0)
- **Output:** `SyntaxError: The requested module 'node:fs/promises' does not provide an export named 'constants'` — Vite 6 / Vitest 4 startup error.
- **Analysis:** The project pins `node:22.11.0-alpine` (frontend `Dockerfile`, README, CI). The host's Node v18.2.0 predates the `node:fs/promises.constants` export (added in Node 18.3+/20+). Re-running the identical gate inside the pinned Node 22 image passes cleanly (33/33 tests, build OK). This is a host-environment mismatch, not an application-code issue.
- **Remediation:** Run the frontend gate on Node 22 (as CI and the Docker image do), e.g. `docker run --rm -v "$PWD":/repo -w /repo/src/frontend node:22.11.0-alpine sh -c 'npm ci && npm run lint && npm run test:coverage && npm run build'`, or upgrade the local Node to ≥ 20. No repository change required.

## Convergence detail (Stage 1)

Assessed present code state against spec.md (17 FR, 7 SC, 3 user stories), plan.md decisions, tasks.md (31 tasks, all `[X]`), and the constitution (5 Core Principles + Turn-1 adopted norms). Every requirement traces to delivered code:

- FR-001/002, SC-001 — five services (db, ingestion, refresh, api, frontend) in `docker-compose.yml`, each with a healthcheck; `frontend` gated on `api` `service_healthy`.
- FR-003/011, SC-002 — `src/frontend/src/api/client.ts` `resolveBaseUrl()` → relative `/api/v1`; `deploy/frontend/nginx.conf` forwards `/api/v1/` to `api`; no mock in the shipped path.
- FR-004–008 — leader-first render, ~5 s refresh, Estimated label, no-data state, stale indicator present in SPA components.
- FR-009/010/012, SC-005 — multi-stage `src/frontend/Dockerfile` ships only `dist/` as non-root UID 10001; nginx emits the four mandatory headers verbatim and clears `Server`/`X-Powered-By` (headers-more).
- FR-013 — only infrastructure/docs touched; no application source module changed.
- FR-014, SC-007 — both read schemas pin `enum: ["1.0.0"]`; client pins `EXPECTED_SCHEMA_VERSION` and throws on mismatch.
- FR-015, SC-004 — `quickstart.md` documents all five validation cases + contract-drift + ingestion-isolation + image-inspection checks.
- FR-016/017, SC-006 — `.env.example`, `README.md` (five services, ports, healthchecks), `AGENTS.md` reconciled; no surviving "no frontend yet" statement found in README/AGENTS/docs.
- Constitution III — `ingestion` depends only on `db`; nothing depends on it.

Findings by gap type: missing 0 / partial 0 / contradicts 0 / unrequested 0. By severity: CRITICAL 0 / HIGH 0 / MEDIUM 0 / LOW 0 (convergence). No constitution MUST violation. Deferred norms (TLS/HSTS termination, Trivy/GHCR gate, RBAC/JWT/Redis/PostGIS/≤2s map) are Turn-2/3 evolution per `docs/turns-ritmo.md` and are non-blocking.

## Note on checklists

`checklists/requirements.md`: all items checked (PASS). `checklists/integration.md`: 44 unchecked items — this is a reviewer-owned **requirements-quality** review checklist (produced by `/speckit.checklist`); unchecked means the reviewer has not signed off on requirements quality, NOT that implementation work is incomplete. It did not gate Stage 2 because convergence found no tasks to implement. Recommend a human reviewer walk this checklist before closing the feature's Review (Value Gate) stage.

## Verdict

**Ready to open a PR.** All automated gates pass (backend 92.84% + frontend 98.27% coverage, both > 80%; lint, typecheck, build green). The sole finding is a local-host Node-version note (LOW) that does not affect the code or CI. No blocking items.

Remaining non-blocking follow-ups for the human reviewer:
1. Have a reviewer complete `checklists/integration.md` (requirements-quality sign-off) as part of the Review stage.
2. Run the frontend gate on Node ≥ 20 / the pinned Node 22 image locally (CI already does).

Committing is left to the user (agents never commit/push).
