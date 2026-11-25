# AGENTS.md — RITMO / PulsoFlota

> Shared context for **ALL** agents. Concise and stable; always loaded.
> Situational guidance lives in `.kiro/steering/` (loaded by context);
> the supreme governing document is `.specify/memory/constitution.md`.

## Purpose

**PulsoFlota** is the real-time supervisory web console for bus dispatchers and
traffic controllers in Medellín. It enables timely, reliable regulation decisions
from integrated telemetry, regularity algorithms and predictive road alerts. It
tackles two structural problems: operational blindness caused by late or
non-standardized data, and distorted incentives (the "guerra del centavo" — the
penny war — and *bus bunching*) that degrade service regularity. **RITMO**
(Riesgo, Incrementos y Trazabilidad para la Movilidad Operativa — Risk,
Increments and Traceability for Operational Mobility) is the spiral methodology
that governs development.

## Key metric

Service quality is measured as the probability of boarding within *t* minutes or
less, **P(board ≤ t)**, complemented by **EWT** (*Excess Wait Time*), read at the
P85 / P95 percentiles from the rider's real perspective (including bus
occupancy). This metric feeds quality-based payment to operators, so its
integrity is critical (fare-collection anti-fraud).

## Technology stack (hard constraints of the target system)

Frontend and backend are **separate** services and folders under `src/`.

- **Language (backend):** Python 3.12+.
- **Backend:** FastAPI + Pydantic V2 in `src/backend/` (REST + WebSocket API,
  ingestion, metrics). Holds all business logic and authorization. Database
  access is **psycopg 3 with parameterized SQL only — no ORM, no Alembic**
  (parameterized queries are the A05 injection baseline).
- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS in `src/frontend/`,
  built to static assets and served behind a reverse proxy (Nginx/Traefik). It
  consumes the backend API and never decides access control.
- **Persistence:** PostgreSQL + PostGIS (SQLite for packaged dev/test).
- **Real time / cache:** Redis (Pub/Sub for live telemetry + in-memory state).
- **Containers:** Docker + `docker-compose`, at least 4 services:
  `ingestion-service`, `pulsoflota-backend`, `pulsoflota-frontend`,
  `database-redis`.
- **Data validation:** Pydantic V2 / JSON Schema at the ingestion gate.
- **CI/CD:** two GitHub Actions pipelines — `backend-ci` (ruff, mypy, Bandit,
  pytest + coverage > 80 %, pip-audit, Trivy image scan) and `frontend-ci`
  (ESLint, `tsc --noEmit`, Vitest, Vite build, JS SCA). Both must pass to merge.
  DevSecOps gates (SAST + SCA + image scan) block publishing vulnerable images
  to GHCR (ADR-0005).
- **Deployment:** MVP is Docker + `docker-compose` (the 4 services). GHCR image
  publishing is an intermediate target; Kubernetes + Helm + GitOps/Argo CD is a
  future/evolution production target, never required for the MVP.

These are adopted **turn by turn**: check `docs/turns-ritmo.md` for what the
active turn requires and what is deferred.

Application code lives under `src/`. The target layout above (`src/backend/`,
`src/frontend/`) is the destination; the current Turn-1 tree is not yet
reorganized into it — backend code sits in `src/api/` (FastAPI app),
`src/data/` (ingestion, pipeline, rules, simulator) and `src/pulsoflota/`
(shared DB/config/models), and the dispatcher console lives in `src/frontend/`
(React 19 + TypeScript + Vite SPA, packaged as the `frontend` Nginx service).
Build tooling (Node / Python) is already covered in `.gitignore`.

## Repository layout

| Path | What it is |
|------|------------|
| `src/` | Application code. Target: `src/backend/` + `src/frontend/`; current Turn-1 tree: `src/api/`, `src/data/`, `src/pulsoflota/` (backend) + `src/frontend/` (dispatcher console SPA). |
| `docs/` | Source-of-truth documentation (OMD, PRD, SRD). |
| `docs/turns-ritmo.md` | **Turn map:** which norms are mandatory in the active turn and which are deferred. |
| `docs/designs/` | UX/UI reference: `global-desing-styles.md` (design tokens, components, a11y), `resumen-historias.md` and mockups `mockups/{escritorio,celular,historias}/UXUI-NN-*.png`. |
| `tickets/` | Per-story tickets wired to GitHub issues, one folder `US-NN-slug/` with its `.md`. |
| `specs/` | Generated per-feature artifacts (spec, plan, tasks, checklists). |
| `.specify/memory/constitution.md` | **Constitution — supreme governing document.** |
| `.kiro/steering/` | Situational guidance (loaded by context, not always). |
| `.kiro/agents/` | Kiro agents (one per Spec Kit workflow phase). |
| `.kiro/prompts/speckit.*.md` | Spec Kit command prompts the agents follow. |
| `.specify/scripts/`, `.specify/templates/` | Spec Kit machinery (bash + templates). |
| `.specify/feature.json`, `.specify/integrations/` | Per-checkout local state (git-ignored). |

## Universal conventions

- **Language:** the repository is written in **English** (agents, steering,
  constitution, specs, docs, code comments, commits and PRs), including the source
  documents in `docs/` (OMD, PRD, SRD), translated on 2026-11-25. Domain identifiers
  defined there (e.g. `id_vehiculo`, `p_abordar_t`) are kept as defined until the
  team decides otherwise. The app's user-facing text (UI copy, messages shown to
  the dispatcher) stays in Spanish.
- **RITMO workflow (spiral):** every turn goes Plan → Specify → Build → Verify →
  Review. One story at a time, on an isolated `feature/US-XX` branch.
- **Contract-First:** every data exchange between modules defines and validates a
  contract (Pydantic V2 / OpenAPI) **before** the implementation is written.
- **Isolated ingestion and deterministic real time:** ingestion runs in a
  container isolated from the web; the critical path (≤ 10 s end to end) never
  depends on synchronous calls to generative AI or third parties.
- **Human-in-the-Loop:** every AI recommendation / rule / optimization is only a
  suggestion; no on-road regulation action runs without explicit approval from
  the human dispatcher.
- **Tests and gates:** coverage > 80 % is mandatory; every PR passes the gates
  adopted in the active turn before merging; CI marks the build as failed on any
  principle violation.
- **Security:** RBAC only in the backend (never only in the frontend), no IDOR,
  multi-tenant isolation, secrets from an external manager (never in code or
  `.env`). Detail in `.kiro/steering/security.md`.
- **Commits:** agents never commit/push (blocked in their permissions); review
  and commit yourself. *The source documents do not set a commit-message
  convention; **Conventional Commits** is inferred (`type(scope): description`,
  e.g. `feat(ingestion): validate GPS schema with Pydantic V2`). If the team
  adopts another one, document it here and update the constitution.*
- **Story numbering (two schemes, not interchangeable):** `tickets/US-NN` are
  implementation stories tied to GitHub issues (the build sequence); `docs/designs/`
  uses **`UXUI-NN`** for design stories. They do not map one-to-one — a ticket
  may cite a `UXUI-NN` mockup as its visual reference.

## Governing document

The **constitution** (`.specify/memory/constitution.md`, v1.4.0) is the supreme
governing document: its 5 core principles are NON-NEGOTIABLE and prevail over
any other practice. For situational detail, load the matching steering file
(`.kiro/steering/*.md`).
