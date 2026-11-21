<!--
Sync Impact Report (temporary draft — remove before merge)
====================================================================
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
  language. Source documents in docs/ (OMD, PRD, SRD) remain in Spanish.
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
  and keeps the modular monolith stable in production.

## Technical and Security Constraints

> These norms describe the **target system**. The **Phased Adoption** section
> (under Governance) and `docs/turns-ritmo.md` define in which turn each one
> becomes mandatory. The 5 Core Principles always apply.

**Mandatory technology stack.**

- Language: Python 3.12+ for the API, ingestion and data pipeline. A React
  console (next item) is written in JavaScript/TypeScript; it is the only
  non-Python component.
- API: FastAPI or Flask.
- Dispatcher console: one of
  - Streamlit / Dash;
  - HTML5/Jinja2 with WebSockets;
  - a React + Vite + Tailwind CSS single-page application that consumes the
    backend only through its REST/WebSocket API (no direct database access)
    and is served as built static files. Authorization stays in the backend.
- Persistence: PostgreSQL with the PostGIS extension (or SQLite for packaged
  development/testing environments).
- Real time and cache: Redis (Pub/Sub for live telemetry events and in-memory
  state management).
- Containers: Docker Engine and `docker-compose` with at least three services:
  `ingestion-service`, `pulsoflota-web` and `database-redis`.

**Performance and firm real time.**

- The system is classified as firm real time: a late recommendation causes no
  catastrophic physical failure, but has no operational value.
- The ingestion pipeline MUST process up to 1,000 events/second with a peak
  P99 latency ≤ 500 ms.
- The total time from detecting an on-road anomaly to showing the
  recommendation on the dispatcher console MUST be ≤ 10 s.
- Automatic route recalculation after a road blockage MUST happen in ≤ 5 s.
- The interactive map MUST refresh fleet positions with latency ≤ 2 s.

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
- **Injection and validation:** queries MUST be parameterized (ORM / SQLAlchemy
  / asyncpg / Pydantic V2). Every ingestion event MUST be validated against a
  strict Pydantic V2 schema; invalid packets MUST be rejected immediately with
  `422 Unprocessable Entity`.
- **Generative-AI isolation:** the deterministic real-time path MUST fully
  isolate predictive AI models; no model or autonomous agent MAY have direct
  write access to the production database or to the dispatch APIs of on-board
  units. Every new disciplined-lane feature MUST have a documented STRIDE threat
  model prioritized by risk.
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
- **Gate 2 — Integration and Supply Chain** (CI): SCA scan (`pip-audit`,
  `npm audit` for the React console, `Trivy`) and unit/integration test suites.
  The coverage threshold applies to the console code as well. Pass: coverage > 80 % and 0 known
  dependency vulnerabilities.
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

**Version**: 1.2.0 | **Ratified**: 2026-11-17 | **Last Amended**: 2026-11-21
