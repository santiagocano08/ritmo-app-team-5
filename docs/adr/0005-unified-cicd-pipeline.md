# ADR-0005: Unified CI/CD Pipeline (backend-ci + frontend-ci, GHCR, future K8s)

- Status: Proposed
- Date: 2026-11-21
- Decided by: pending. Requires the unanimous sign-off of the Turn Owner, the Architect
  (Software / Security) and the Dispatcher Representative (Constitution, Governance, Amendments)
- Turn: Turn 1 — Data and Minimal Loop (active); staged adoption per `docs/turns-ritmo.md`
- Addresses: Principle V (Test-First and Automated Gates), Principle III (Isolated Ingestion and
  Deterministic Real Time), RNF-3.4.1, RNF-3.4.7 (CI/CD gates, image publishing), SRD A02/A03/A09
  (security misconfiguration, supply chain, observability)

## Context

The team's integrated update report names a unified CI/CD pipeline as the immediate evolution
priority. The system is a frontend/backend split (ADR-0004): a React 19 + TypeScript + Vite +
Tailwind frontend in `src/frontend/` and a FastAPI + Pydantic V2 backend in `src/backend/` that
accesses the database with psycopg 3 and parameterized SQL only (no ORM, no SQLAlchemy, no Alembic).
The MVP runs as four docker-compose services: `ingestion-service`, `pulsoflota-backend`,
`pulsoflota-frontend`, `database-redis`.

CI/CD has to enforce the automated gates (Principle V) on every Pull Request, build the service
images, and keep vulnerable images out of the registry — without over-building for a production
orchestrator the MVP does not need yet. The constitution and the turn map adopt norms turn by turn,
so anything beyond the MVP must be framed as a future target, not a current requirement.

## Options considered (max. 3)

1. **Two pipelines (`backend-ci`, `frontend-ci`) on GitHub Actions; docker-compose MVP now; GHCR
   image publish as an intermediate target; K8s/Helm/Argo CD documented as future.**
   - Pros: matches the split and the four-service compose; each pipeline owns its stack and gates;
     deployment complexity grows only when a turn needs it.
   - Cons: two workflow files to keep coherent; shared conventions (tags, SHA) must be agreed.
2. **One monolithic pipeline for both services.**
   - Pros: a single file.
   - Cons: couples unrelated toolchains (Python and Node), blurs ownership, and a frontend-only
     change reruns backend jobs; weaker gate isolation.
3. **Adopt Kubernetes + Helm + Argo CD (GitOps) now.**
   - Pros: a single production-grade target.
   - Cons: large operational surface the MVP does not need; contradicts the turn-by-turn adoption
     and the docker-compose MVP; premature (YAGNI).

## Decision

Adopt **option 1**. Two GitHub Actions pipelines, both required to merge:

- **`backend-ci`** (`src/backend/`, `ingestion-service`): `ruff` lint, `mypy` types, `Bandit` SAST,
  Pydantic V2 schema validation, `pytest` with coverage > 80 %, `pip-audit`/`Safety` SCA, image
  build and `Trivy` image scan.
- **`frontend-ci`** (`src/frontend/`): `ESLint`, `tsc --noEmit`, `Vitest` with coverage > 80 %,
  `npm audit`/`Trivy` JS SCA, and the Vite production build.

Cross-cutting rules:

1. **DevSecOps gate before publish.** SAST + SCA + image scan run before any image is published.
   A High/Critical finding (CVSS ≥ 7.0) fails the pipeline and blocks publishing to **GHCR**. The
   pipeline acts as an Andon: a red gate stops the line until the root cause is fixed (Shift-Left).
2. **docker-compose MVP is the current deployment.** Releases are versioned, immutable image tags
   (semantic tag + commit SHA); rollback is a redeploy of the previous image. `docker-compose` is
   validated in CI.
3. **GHCR image publish is an intermediate target.** Building and pushing signed, scanned images to
   GHCR may precede any orchestrator and is not an MVP blocker.
4. **Kubernetes + Helm + GitOps/Argo CD is the future production target.** It is documented as
   evolution for a later spiral turn, not built or required for the MVP.
5. **No ORM in the pipeline.** Schema changes ship as versioned idempotent SQL scripts applied in a
   controlled step with a prior backup — never Alembic migrations.
6. **Authorization stays in the backend.** The frontend pipeline never introduces access-control
   logic; it builds static assets only.

## Consequences

- Two workflow files share tag/SHA conventions and a published-image policy; the four-service
  compose is the deployment contract both target.
- Full SAST/SCA as blocking gates and image scanning follow their turns in `docs/turns-ritmo.md`
  (turn 2); turn 1 runs lint, types, tests and coverage > 80 % on every PR. This ADR names the
  tools and the GHCR policy they will enforce.
- Adopting GHCR publishing and, later, K8s/Helm/Argo CD will each need the turn map updated in the
  Plan stage of the turn that adopts them.
- Observability signals and the freshness SLO error budget (OMD §3.3) gate promotion decisions but
  are operated outside the pipeline.

## Evolution

- GHCR image publishing with signing and provenance (intermediate target).
- Kubernetes + Helm charts and GitOps/Argo CD for staging/production (future turn).
- Staging/production deploy stages with automated rollback and DR drills.

## Changed documents

`docs/prd-ritmo.md` (RNF-3.4.7), `docs/omd-ritmo.md` (§3.1.1 E2E lifecycle, §3.3 DevOps/SRE),
`docs/srd-ritmo.md` (§2.11 CI/CD orchestration).
