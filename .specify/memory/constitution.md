<!--
Sync Impact Report (temporary draft — remove before merge)
====================================================================
- Proposed amendment 1.3.0 → 1.4.0 (MINOR, additive reliability norms), 2026-11-21,
  PR `constitutional-amendment`, ADR-0005 (unified CI/CD; and ADR-0004 pinned as
  Accepted). Adds two new, compatible normative items without touching the 5
  NON-NEGOTIABLE principles or the 5-stage spiral: (1) a data-freshness SLO and
  error-budget policy under *Performance and firm real time* — freshness SLI
  < 15 s, 99 % availability over a rolling 28-day window (≈ 403 min error budget),
  with budget exhaustion freezing new feature work until margin is recovered via
  the Run → Change loop; (2) a low-autonomy generative-AI lane under Principle IV /
  Security — GenAI agents operate in suggestion mode only and MUST NOT issue
  on-road or on-board commands without explicit human-dispatcher authorization
  (reinforces, does not redefine, Principle IV). Gate 2 references the DevSecOps
  image publish-block to GHCR (CVSS ≥ 7.0). Deployment framing: Docker +
  `docker-compose` is the MVP; GHCR image publishing is an intermediate target and
  Kubernetes + Helm + GitOps/Argo CD is a future production target — all adopted
  turn by turn per `docs/turns-ritmo.md`. NOT included (surfaced as open team
  decisions, deliberately not applied here): whether the 10-stage E2E Run → Change
  lifecycle redefines the 5-stage spiral (that would be MAJOR → 2.0.0 via the
  amendment process), and turn-map reconciliation of the Turn-3 observability/SLO
  deferral plus new GHCR and K8s turns (a Plan-stage turn-map PR, not an
  amendment). Updated: .specify/memory/constitution.md only. Sources of truth:
  docs/prd-ritmo.md (RNF-3.4.5/6/7), docs/omd-ritmo.md §3, docs/srd-ritmo.md §2.9/A09,
  docs/adr/0004, docs/adr/0005, .kiro/steering/*. Templates and agents: no changes
  required.
- Proposed amendment 1.2.0 → 1.3.0 (MINOR, compatible stack change), 2026-11-21,
  PR `constitutional-amendment`. Splits the dispatcher console into **separate**
  frontend and backend services and folders under `src/` (`src/backend/`,
  `src/frontend/`), superseding the single `pulsoflota-web` console. Backend is
  FastAPI + Pydantic V2 holding all business logic and authorization; database
  access is psycopg 3 with parameterized SQL only (no ORM, no SQLAlchemy, no
  Alembic — this replaces the earlier "ORM / SQLAlchemy / asyncpg" wording in the
  injection norm). Frontend is React 19 + TypeScript + Vite + Tailwind served as
  static assets behind a reverse proxy, never deciding access control. The
  `docker-compose` service list grows from three to four (`ingestion-service`,
  `pulsoflota-backend`, `pulsoflota-frontend`, `database-redis`), and Gate 2 names
  the two CI pipelines `backend-ci` and `frontend-ci`. Core Principles are
  unchanged (Principle V rationale reworded from "modular monolith" to the
  backend/frontend services). Sources of truth: AGENTS.md, docs/turns-ritmo.md
  v0.1.3, src/pulsoflota/db.py. The psycopg/no-ORM decision is reconciled across
  the source documents: PRD RNF-3.2.1, SRD §2.1/§2.11 and OMD §2.1 no longer name
  SQLAlchemy or Alembic. Updated: AGENTS.md, .kiro/steering/deployment-containers.md,
  backend-api.md, frontend-web.md, docs/turns-ritmo.md, docs/prd-ritmo.md,
  docs/srd-ritmo.md, docs/omd-ritmo.md. Templates and agents: no changes required.
- Proposed amendment 1.1.0 → 1.2.0 (MINOR, compatible stack change), 2026-11-21,
  PR `constitutional-amendment`, ADR-0004 (status: Proposed; pending the unanimous
  sign-off of the Turn Owner, the Architect and the Dispatcher Representative).
  Adds a React + Vite + Tailwind CSS single-page application as an allowed option
  for the dispatcher console, next to Streamlit / Dash and HTML5/Jinja2. Python
  3.12+ stays the language of the backend, ingestion and data pipeline; the SPA
  is the only JavaScript/TypeScript component. Supply-chain and Gate 2 norms name
  the JavaScript equivalents (`npm audit`, lockfile integrity hashes, `npm ci`),
  and the coverage threshold of Gate 2 explicitly covers the console code.
  Core Principles are unchanged. Updated: AGENTS.md, .kiro/steering/frontend-web.md,
  security.md, testing-quality-gates.md, deployment-containers.md, docs/turns-ritmo.md.
  Templates and agents: no changes required.
- Proposed amendment 1.0.0 → 1.1.0 (MINOR), 2026-11-17, PR `constitutional-amendment`:
  adds "Phased Adoption" under Governance and a note at the top of "Technical and
  Security Constraints". Core Principles are unchanged. New referenced document:
  docs/turns-ritmo.md (spiral turn map). Rationale: v1.0.0 requires the complete
  target system from turn 1, which is incompatible with a risk-driven spiral and
  with the scope of turn 1 (workshop on 2026-11-24).
  Templates: no changes required. Agents: create-spec, create-plan, create-tasks,
  validate-plan, implement-code and review-code load docs/turns-ritmo.md.
- Initial version: (no previously ratified version) → 1.0.0
  The pre-existing .specify/memory/constitution.md was unresolved template
  scaffolding (all [...] placeholders intact, no concrete version); there was no
  previously ratified constitution. Initial version 1.0.0 is adopted, aligned
  with version 1.0.0 declared in the source documents (OMD/PRD/SRD).
- Modified principles: N/A (initial ratification). The 5 NON-NEGOTIABLE Core
  Principles are taken from the OMD.
- Added sections:
  * Core Principles (5 NON-NEGOTIABLE principles)
  * Technical and Security Constraints (stack, firm real time, OWASP Top 10 2025)
  * RITMO Development Workflow and Quality Gates (5 stages, 2 lanes, 4 gates)
  * Governance (amendments, SemVer, compliance, phased adoption)
- Removed sections: N/A
- Deferred TODOs: none. Ratified = 2026-11-17 (date provided by the operator);
  Last Amended = 2026-11-17.
- Language: translated to English on 2026-11-17 so the whole repository uses one
  language. Source documents in docs/ (OMD, PRD, SRD) translated to English on
  2026-11-25; the app's user-facing text stays in Spanish.
-->

# RITMO / PulsoFlota Constitution

## Core Principles

### I. Risk-First Order — NON-NEGOTIABLE

- The development backlog and the sequence of spiral turns MUST be ordered
  strictly by technical and architectural risk level (ASRs), not by static
  business priority.
- NO new adaptive-lane feature MAY start while a Level 1 risk (security or data
  integrity) remains unmitigated in the active turn.
- **Rationale:** in firm real-time systems with supervisory control, ignoring
  concurrency or data-corruption risks early leads to operational collapse
  during demand peaks.

### II. Contract-First and Data Ownership — NON-NEGOTIABLE

- Every data exchange between modules or services MUST define and validate an
  explicit message contract (Pydantic V2 / OpenAPI) before implementation code
  is written.
- NO data model MAY be persisted or processed in the pipeline without an
  assigned owning module and a schema validated at the boundary.
- **Rationale:** removes implicit coupling and prevents malformed or
  non-standardized data from multiple operators from contaminating the
  indicators used for quality-based payment.

### III. Isolated Ingestion and Deterministic Real Time — NON-NEGOTIABLE

- The telemetry and road-infrastructure ingestion pipeline MUST run in a
  process container isolated from the web interface.
- The real-time critical path (≤ 10 s end to end) MUST be deterministic and
  MUST NEVER depend on synchronous calls to generative-AI agents or external
  third-party services.
- **Rationale:** guarantees that ingestion and fleet observability survive at
  the control center even if the supervisory frontend or auxiliary services
  degrade or fail.

### IV. Unbreakable Human Gate (Human-in-the-Loop Supervision) — NON-NEGOTIABLE

- Every AI agent, optimization algorithm or automated rule MUST operate
  exclusively in suggestion mode.
- NO on-road regulation action (frequency changes, messages to drivers or route
  diversions) MAY run autonomously without explicit authorization from a human
  dispatcher through the web interface.
- **Rationale:** operational and contractual responsibility towards the city
  and its riders lies with the supervisory control center; technology assists
  the decision, but the human keeps supervisory control.

### V. Test-First and Automated Gates — NON-NEGOTIABLE

- Every Pull Request MUST include unit and integration tests that guarantee
  coverage above 80 %, and MUST automatically pass the contract gate (DataOps)
  and the continuous-integration gate (CI) before being merged into the main
  branch.
- NO developer or agent MAY skip the gates.
- **Rationale:** prevents regressions in the P(board ≤ t) metric calculations
  and keeps the backend and frontend services stable in production.

## Technical and Security Constraints

> These norms describe the **target system**. The **Phased Adoption** section
> (under Governance) and `docs/turns-ritmo.md` define in which turn each one
> becomes mandatory. The 5 Core Principles always apply.

**Mandatory technology stack.** Frontend and backend are **separate** services
and folders under `src/` (`src/backend/`, `src/frontend/`). The split is adopted
turn by turn; `docs/turns-ritmo.md` records the current `src/` tree.

- Language (backend): Python 3.12+ for the API, ingestion and data pipeline. The
  React frontend is written in TypeScript; it is the only non-Python component.
- Backend: FastAPI (or Flask) + Pydantic V2 in `src/backend/` (REST + WebSocket
  API, ingestion, metrics). Holds all business logic and authorization. Database
  access MUST use psycopg 3 with parameterized SQL only — no ORM, no SQLAlchemy,
  no Alembic (parameterized queries are the A05 injection baseline).
- Frontend: a React + Vite + Tailwind CSS single-page application in
  `src/frontend/` that consumes the backend only through its REST/WebSocket API
  (no direct database access), is served as built static files behind a reverse
  proxy (Nginx/Traefik), and MUST NEVER decide access control. Earlier console
  options (Streamlit / Dash, HTML5/Jinja2 with WebSockets) are superseded by this
  SPA under ADR-0004.
- Persistence: PostgreSQL with the PostGIS extension (or SQLite for packaged
  development/testing environments).
- Real time and cache: Redis (Pub/Sub for live telemetry events and in-memory
  state management).
- Containers: Docker Engine and `docker-compose` with at least four services:
  `ingestion-service`, `pulsoflota-backend`, `pulsoflota-frontend` and
  `database-redis`.

**Performance and firm real time.**

- The system is classified as firm real time: a late recommendation causes no
  catastrophic physical failure, but has no operational value.
- The ingestion pipeline MUST process up to 1,000 events/second with a peak
  P99 latency ≤ 500 ms.
- The total time from detecting an on-road anomaly to showing the
  recommendation on the dispatcher console MUST be ≤ 10 s.
- Automatic route recalculation after a road blockage MUST happen in ≤ 5 s.
- The interactive map MUST refresh fleet positions with latency ≤ 2 s.
- **Data-freshness SLO and error budget:** the system MUST track a data-freshness
  SLI (newest ingested data no older than 15 s) and meet a 99 % availability
  target over a rolling 28-day window, i.e. an error budget of ≈ 403 minutes per
  window. When the budget is exhausted, new feature work MUST freeze and
  reliability work takes priority until margin is recovered; freshness-SLI
  breaches and budget-burn alerts enter the next turn's Plan stage as reliability
  stories (the Run → Change loop). This norm is adopted turn by turn per
  `docs/turns-ritmo.md`; the operational detail lives in
  `.kiro/steering/realtime-ingestion.md`.

**Security (aligned with OWASP Top 10 — 2025).** The operational detail of each
acceptance criterion lives in `.kiro/steering/security.md`; what follows is the
governing norm.

- **Access control:** every REST/WebSocket endpoint MUST authenticate the
  caller and check permissions through RBAC in the backend middleware. Insecure
  direct object references (IDOR) are forbidden: access to someone else's
  resource MUST return `403 Forbidden` and log an alert. Authorization MUST be
  evaluated only in the backend; the frontend MUST NOT be the only control
  mechanism. Telemetry from private consortia MUST be logically isolated
  (multi-tenant).
- **Infrastructure:** containers MUST run as a non-root user (UID 10001). The
  server MUST send the mandatory security headers (`Content-Security-Policy`,
  `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`) and remove headers that reveal the technology stack.
  `DEBUG=False` MUST be enforced in staging and production; Swagger/ReDoc MUST
  NOT be exposed in production without authentication.
- **Supply chain:** CI/CD MUST run software composition analysis (SCA) on every
  PR, block merges on High or Critical vulnerabilities (CVSS ≥ 7.0) and pin
  dependencies to exact versions with SHA-256 hashes. For JavaScript
  dependencies, the committed `package-lock.json` (exact versions with npm
  `integrity` hashes) installed with `npm ci` satisfies this norm.
- **Cryptography and secrets:** external communication MUST use TLS 1.3
  (minimum TLS 1.2 with PFS cipher suites); the IoT fleet MUST authenticate with
  mTLS and one x509 certificate per unit. Passwords MUST be hashed with Argon2id
  (or bcrypt with cost ≥ 12). Secrets MUST come from an external manager (Docker
  Secrets or HashiCorp Vault); they MUST NEVER be included in source code or in
  `.env` files in the repository.
- **Injection and validation:** all database access MUST use psycopg 3 with
  parameterized SQL only (no ORM, no SQLAlchemy, no Alembic); string-built SQL is
  forbidden. Every ingestion event MUST be validated against a strict Pydantic V2
  schema; invalid packets MUST be rejected immediately with `422 Unprocessable
  Entity`.
- **Generative-AI isolation and low-autonomy lane:** the deterministic real-time
  path MUST fully isolate predictive AI models; no model or autonomous agent MAY
  have direct write access to the production database or to the dispatch APIs of
  on-board units. Generative-AI agents MUST operate in a low-autonomy lane in
  suggestion mode only: they MAY propose regulation actions or route diversions
  but MUST NOT issue any on-road or on-board command without explicit
  human-dispatcher authorization (this reinforces Principle IV; it does not
  redefine it). Every new disciplined-lane feature MUST have a documented STRIDE
  threat model prioritized by risk.
- **Authentication and sessions:** JWTs MUST be signed with `RS256`, expire in
  ≤ 15 min and travel only in `HttpOnly`, `Secure`, `SameSite=Strict` cookies.
  Administrators and basin supervisors MUST use MFA (TOTP). The system MUST lock
  for 15 minutes any account or IP with 5 consecutive failed attempts.
- **Fare-collection integrity and anti-fraud:** the ingestion pipeline MUST
  record provenance, an immutable timestamp and a checksum per message, and MUST
  detect and discard tampered data (GPS jumps > 120 km/h, duplicate fare
  validations, inconsistency between road sensors and bus coordinates).
  Fare-collection packets MUST include an HMAC signature based on the secret of
  the on-board validator's secure module.
- **SRE observability:** logs MUST be emitted as structured JSON compatible with
  OpenTelemetry and record, with a UTC timestamp and user identifier,
  authentication attempts, permission changes, authorized or rejected diversions
  and changes to ingestion sources. Logs MUST NEVER include passwords, private
  keys, full JWTs or PII of drivers or riders. An IoT message rejection rate
  > 5 % within 1 min MUST trigger alerts to the SRE/DevSecOps team.
- **Exceptions and resilience:** no HTTP/WebSocket response MAY expose stack
  traces, local file paths or internal PostgreSQL structures; on a 500 error a
  generic message MUST be returned with a `correlation_id` recorded internally in
  the logs. If the control center or the web app fails, the isolated IoT
  ingestion MUST keep recording events in the persistent buffer and the
  dispatcher console MUST switch to a local contingency mode based on predefined
  static dispatch plans.

## RITMO Development Workflow and Quality Gates

**RITMO lifecycle — 5 stages per spiral turn.** Every turn goes through these
stages in order:

1. **Plan** — select the priority risk to mitigate, the turn's closing date and
   the operational hypotheses (owner: Turn Owner).
2. **Specify** — write the user story as a measurable SDD
   (*Specification-Driven Development*) specification, plus a contract gate if
   schemas change.
3. **Build** — develop one story at a time on an isolated `feature/US-XX`
   branch, including production code, tests and data rules.
4. **Verify** — run the CI pipeline (linting, unit tests, coverage > 80 %),
   DataOps contract tests and human reviewer inspection.
5. **Review (Value Gate)** — validate the value hypothesis by measuring the
   impact on P(board ≤ t) with the dispatcher in the test/simulation
   environment.

**Two development lanes.**

- **Disciplined Lane** (Ingestion, Message Contracts, Quality-Based Payment):
  strict Contract-First / SDD specification; low agent autonomy (only proposals
  validated in code and gates); maximum criticality; strict CI and DataOps
  contract tests.
- **Adaptive Lane** (Web Console, Visualization, Alert and Diversion Rules):
  iterations driven by value hypotheses validated with the dispatcher; medium
  agent autonomy (automated development on isolated branches with mandatory
  review by the module owner).

**Quality gates (automated and human).** No increment may be promoted to the
next stage or deployed to production without passing:

- **Gate 1 — Contract and Static Analysis** (every PR): SAST (`Bandit`,
  `ESLint`) and Pydantic schema validation. Pass: 0 Critical/High SAST findings
  and a validated contract schema.
- **Gate 2 — Integration and Supply Chain** (CI): two GitHub Actions pipelines,
  `backend-ci` (ruff, mypy, Bandit, pytest + coverage > 80 %, pip-audit, Trivy
  image scan) and `frontend-ci` (ESLint, `tsc --noEmit`, Vitest, Vite build, JS
  SCA); both MUST pass to merge. SCA scan (`pip-audit`, JS SCA, `Trivy`) and
  unit/integration test suites. The coverage threshold applies to the frontend
  code as well. Images are published to GHCR only after the scan passes; the
  pipeline MUST block publishing any image with a High or Critical vulnerability
  (CVSS ≥ 7.0) — see ADR-0005. Pass: coverage > 80 % and 0 known dependency
  vulnerabilities.
- **Gate 3 — Data Gate (DataOps)** (at ingestion runtime): message contract
  tests, HMAC validation and anomaly detection. Pass: packet rejection rate
  < 0.1 % and ingestion latency ≤ 200 ms.
- **Gate 4 — Value and Operational Safety** (turn closing): Human-in-the-Loop
  validation, diversion audit and fallback test. Pass: explicit dispatcher
  approval and verification that AI does not interfere with the real-time path.

## Governance

- This constitution is the supreme governing document of the RITMO / PulsoFlota
  project; it prevails over any other practice in case of conflict.
- **Amendments:** any change to the core principles or to this document MUST be
  proposed through a Pull Request labeled `constitutional-amendment`, with a
  justification based on field evidence or new constraints of the Medellín
  transport domain. Changes to normative requirements (MUST / SHOULD norms) also
  require an architecture decision record (ADR), validation at the spiral's risk
  gate and the unanimous sign-off of the Turn Owner, the Architect (Software /
  Security) and the Dispatcher Representative.
- **Versioning (SemVer):** MAJOR (X.0.0) for changes to the NON-NEGOTIABLE core
  principles or restructuring of the container/lane architecture; MINOR (1.X.0)
  for new domain-model objects, new user stories in the matrix or compatible
  stack changes; PATCH (1.0.X) for wording fixes, rule clarifications or
  adjustments to secondary metrics.
- **Compliance:** at the end of each spiral turn the team MUST review compliance
  with the core principles. A detected violation (e.g. untested code merged into
  the main branch, or recommendations issued without the human gate) MUST
  immediately mark the CI build as failed.
- **Phased Adoption:**
  - The **5 NON-NEGOTIABLE Core Principles** are mandatory from the first turn
    and in every turn.
  - The norms in *Technical and Security Constraints* and *Quality gates* are
    adopted **incrementally, turn by turn**. The order is set by Principle I:
    Level 1 risks first.
  - The **turn map** (`docs/turns-ritmo.md`) is the single source that
    declares, for each turn, which norms are mandatory and which are deferred as
    evolution. It is updated in the Plan stage of each turn through a PR reviewed
    by the team. That update does **NOT** require a constitutional amendment, as
    long as it does not contradict this constitution.
  - A norm adopted in a turn remains mandatory in all later turns. A deferred
    norm MUST NOT be treated as a blocking finding in the active turn; agents
    SHOULD record it as evolution.
  - The compliance review at the close of each turn checks the Core Principles
    and the norms adopted **up to that turn** according to the map.
- **Operational guidance:** the constitution governs; `AGENTS.md` and the
  `.kiro/steering/*.md` files operationalize it by context. For security detail,
  see `.kiro/steering/security.md`.

**Version**: 1.4.0 | **Ratified**: 2026-11-17 | **Last Amended**: 2026-11-21
