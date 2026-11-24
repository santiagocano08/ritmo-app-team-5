---
inclusion: auto
name: testing-quality-gates
description: When writing tests, configuring CI/CD, or checking a quality gate (SAST, SCA, DataOps, coverage >80 %, Human-in-the-Loop).
---

# Testing and Quality Gates — PulsoFlota

> Each gate applies from the turn in which `docs/turns-ritmo.md` adopts it. In
> turn 1: Gate 1 (schema validation only), Gate 2 (tests and coverage) and the
> human approval of Gate 4.

## Test-First (Principle V, NON-NEGOTIABLE)

- Every PR includes unit and integration tests with coverage > 80 %.
- No developer or agent skips the gates.

## Gate 1 — Contract and Static Analysis (every PR)

- SAST: `Bandit` (Python) and `ESLint` (JavaScript).
- Pydantic schema validation.
- Pass: 0 Critical/High SAST findings and a validated contract schema.

## Gate 2 — Integration and Supply Chain (CI)

- SCA: `pip-audit` / `Trivy` (and `Safety`/`Snyk` for Python); `npm audit`
  for the React console.
- Unit/integration test suites (pytest for Python; Vitest for the React
  console, which counts towards the same > 80 % threshold).
- Pass: coverage > 80 % and 0 known dependency vulnerabilities (a CVE with
  CVSS ≥ 7.0 blocks the merge).
- **DevSecOps publish block:** the SAST + SCA + image scan gates also block
  publishing a vulnerable container image to the registry (GHCR). An image with
  a High/Critical finding (CVSS ≥ 7.0) must not be promoted or published. The
  pipeline runs two GitHub Actions workflows, `backend-ci` and `frontend-ci`
  (both must pass to merge). See ADR-0005.

## Gate 3 — Data Gate (DataOps, ingestion runtime)

- Message contract tests, HMAC validation and anomaly detection.
- Pass: packet rejection rate < 0.1 % and ingestion latency ≤ 200 ms.

## Gate 4 — Value and Operational Safety (turn closing)

- Human-in-the-Loop validation, diversion audit and fallback test.
- Pass: explicit dispatcher approval and verification that AI does not interfere
  with the real-time path.

## Immediate failure

- A principle violation (e.g. untested code merged into the main branch, or
  recommendations issued without the human gate) immediately marks the CI build
  as failed.

## Integration test focus

- New service contracts, contract changes, inter-service communication and
  shared schemas.

## Scoped test selection in workflow steps (implement-code, review-code)

To avoid paying for the full DB-backed suite on every iteration, the
`implement-code` and `review-code` workflow steps run **only the tests for the
area directly changed, plus the critical zones that depend on it** — not the
whole tree, while iterating.

- **Skip `src/data/` tests when nothing under `src/data/` changed.** The
  bronze/gold ETL suite is slow and needs the git-ignored `data/raw/`; it adds
  no signal for a change outside `src/data/`. Only run it when `src/data/` is
  touched.
- **Run the affected area + its critical dependents.** For a backend change,
  that is typically `make test-backend` (= `pytest src/api/tests`, and add
  `src/pulsoflota` tests if shared code changed), not `--cov=src` over
  everything.
- **Lint/type checks run from the project `.venv`** via `make lint`
  (`.venv/bin/ruff check src` + `.venv/bin/mypy`). `ruff` and `mypy` are dev
  dependencies in `pyproject.toml` — do **not** invoke them via `uvx`/`uv run`,
  which pay a cold-start / env-revalidation cost each call.
- **Coverage gate vs iteration — they differ.** The repo's `--cov-fail-under=80`
  is measured over the **whole `src` tree**, and most of `src/pulsoflota` is
  exercised by the `src/data` suite. So **excluding `src/data` makes the global
  gate fail** (≈56%) even for a pure-backend change — `-m "not data"` is an
  *iteration* tool, not the final gate.
  - **While iterating:** use `make test-backend` (fast, no coverage gate) and
    `make test-cov` (`-m "not data"`) to exercise the changed area quickly.
  - **Final coverage gate:** run the whole suite **once**, in the foreground
    (`make test` / `uv run pytest`). Do **not** run it twice and do **not** poll
    a background run with `sleep` / `while kill -0` loops — that polling, not the
    single data run, was the ~20-min waste in US-08. Running the `src/data` suite
    once is unavoidable while coverage is measured over all of `src`.
  - The `data` marker (applied by path in `src/data/tests/conftest.py`) lets you
    deselect the ETL suite with `-m "not data"` for fast iteration without naming
    its path.

> Rationale: in US-08 the `implement-code` step spent ~38 of ~53 min waiting on
> the full suite (including untouched `src/data` tests with a pre-existing,
> unrelated failure) and ~6 min on `uvx` cold starts. See
> `specs/007-backend-version-info/audit-workflow-US-08.md`.

## References

- OWASP Top 10 (2025) matrix and SAST/SCA criteria: `security.md`.
- RITMO cycle, `feature/US-XX` branches and lanes: `ritmo-workflow.md`.
- Unified CI/CD pipelines, GHCR publish policy and future K8s target: ADR-0005.
- MVP `docker-compose` deployment vs GHCR/K8s evolution: `deployment-containers.md`.
