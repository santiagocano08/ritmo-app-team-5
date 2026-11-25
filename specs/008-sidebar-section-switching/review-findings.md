# Review Findings: US-10 Sidebar Section Switching

**Run**: 2026-11-24 16:54 -05 · branch `feature/US-10-frontend-sidebar-sections`
**Converge outcome**: `converged` (0 iterations needed; `tasks.md` unchanged)
**Coverage minimum**: 80 %, from the constitution Principle V / `testing-quality-gates.md`
(Vitest thresholds in `src/frontend/vite.config.ts`, `--cov-fail-under=80` in `pyproject.toml`).

## Validation results

| Check | Command | Result |
|-------|---------|--------|
| Frontend lint (ESLint) | `npm run lint` | PASS (0 warnings) |
| Frontend typecheck | `npx tsc --noEmit` | PASS |
| Frontend tests + coverage | `npm run test:coverage` | PASS: 17 files, 46 tests; stmts 98.41 %, branches 93.1 %, funcs 100 %, lines 98.36 % |
| Frontend build | `npm run build` | PASS |
| Frontend SCA | `npm audit --audit-level=high` | PASS: 0 vulnerabilities |
| Frontend formatter | none configured (no Prettier config) | N/A |
| Backend tests + global coverage gate | `make test` (run once) | PASS: 830 passed, 438 skipped; total 80.75 % |
| Backend lint + typecheck | `make lint` | NOT RUN: `.venv/bin/ruff` missing (see F2) |
| Backend formatter | `.venv/bin/ruff format --check src` | NOT RUN: same cause (see F2) |

Scope check (FR-009, FR-010): changes are limited to `src/frontend/` (App, Sidebar,
sections.ts, SectionPlaceholder and their tests). No router dependency, no backend,
contract or generated-type edits.

## Findings

### MEDIUM

**F1 · converge · Manual validation tasks still open**
- Area: `tasks.md` T015 (quickstart manual checks 1–7) and T016 (SC-004 visual review
  against `UXUI03-escritorio.png` and style spec §7).
- Evidence: both tasks are `[ ]`. They need a human with `npm run dev:mock` and the mockup.
  The automated tests already assert the §7 classes, which resolve to the spec tokens
  (`border-placeholder` = `#A3ACB9`, `rounded-card` = 12 px, `text-secondary` = `#4A5361`).
- Remediation: run quickstart steps 1–7 and the visual comparison, then mark T015/T016 `[X]`.

### LOW

**F2 · lint/format · ruff and mypy not installed in the project `.venv`**
- Area: local environment (not this feature; no Python file changed).
- Command: `make lint` → `make: .venv/bin/ruff: No such file or directory`.
- Cause: the `dev` optional extras in `pyproject.toml` (ruff, mypy) were not synced into `.venv`.
- Remediation: `uv sync --extra dev`, then `make lint` and `.venv/bin/ruff format --check src`.
  `backend-ci` still runs both in CI.
