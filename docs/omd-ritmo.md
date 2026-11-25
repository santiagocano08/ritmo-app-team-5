# OMD — Object Model, Architecture Definition & Engineering Constitution: RITMO / PulsoFlota

## Constitution and Architecture Control
* **PROJECT_NAME**: RITMO (Riesgo, Incrementos y Trazabilidad para la Movilidad Operativa — Risk, Increments and Traceability for Operational Mobility)
* **CONSTITUTION_VERSION**: 1.0.0
* **RATIFICATION_DATE**: 2026-11-06
* **LAST_AMENDED_DATE**: 2026-11-14
* **TARGET APPLICATION**: Web Control Center for Supervisory Dispatch and Operational Mobility (PulsoFlota)

---

## 1. Core Engineering Principles

### Principle 1: Risk-First Order — [NON-NEGOTIABLE]
* **Rule**: The development backlog and the sequence of spiral turns **MUST** be ordered strictly by technical and architectural risk level (ASRs), not by static business priority. No new feature in the adaptive lane **MUST** start while a level-1 risk (security or data integrity) remains unmitigated in the active turn.
* **Rationale**: In firm real-time systems with supervisory control, ignoring concurrency or data-corruption risks at the start leads to a catastrophic collapse of operations during demand peaks.

### Principle 2: Data Has an Owner and Contract First (Contract-First & Data Ownership) — [NON-NEGOTIABLE]
* **Rule**: Every data exchange between modules or services **MUST** define and validate an explicit message contract (Pydantic / OpenAPI) before any implementation code is written. No data model **MUST** be persisted or processed in the pipeline if it lacks an assigned module owner and a schema validated at the boundary.
* **Rationale**: It removes implicit coupling and prevents malformed or non-standardized data from multiple operators from contaminating the indicators used to compute pay-for-quality.

### Principle 3: Isolated Ingestion and Deterministic Real Time — [NON-NEGOTIABLE]
* **Rule**: The telemetry and road-infrastructure ingestion pipeline **MUST** run in a process container isolated from the web interface. The critical real-time execution path ($\le 10\text{ s}$) **MUST** be deterministic and **MUST NEVER** depend on synchronous calls to Generative AI agents or external third-party services.
* **Rationale**: It guarantees that ingestion and fleet observability survive in the control center even if the supervisory frontend or auxiliary services degrade or go down.

### Principle 4: Unbreakable Human Gate (Human-in-the-Loop Supervision) — [NON-NEGOTIABLE]
* **Rule**: Every AI agent, optimization algorithm or automatic rule **MUST** operate exclusively in suggestion mode. No on-road regulation action (changing frequencies, sending messages to drivers or rerouting) **MUST** run autonomously without the explicit authorization of a human dispatcher through the web interface.
* **Rationale**: Operational and contractual responsibility toward the city and its riders lies with the supervisory control center; technology assists the decision, but the human keeps supervisory control.

### Principle 5: Mandatory Tests and Automated Gates (Test-First & Automated Gates) — [NON-NEGOTIABLE]
* **Rule**: Every Pull Request (PR) **MUST** include unit and integration tests that guarantee coverage above $80\%$, and must automatically pass the contract gates (DataOps) and continuous integration (CI) before it is merged into the main branch. No developer or agent **MUST** skip the gates.
* **Rationale**: It prevents regressions in the computation of the $P(\text{abordar} \le t)$ (boarding within $t$) metric and keeps the separate backend and frontend services stable in production.

---

## 2. Architecture Definition, Object Model and Technology Stack

### 2.1 Technology Stack and Containers

The system separates **frontend** and **backend** into independent services and folders
inside `src/`. The backend holds all business logic, ingestion and authorization
evaluation (Principle IV and A01); the frontend is a web client that consumes the
REST/WebSocket API and never makes access-control decisions on its own.

* **Programming language (backend)**: Python 3.12+
* **Web & API framework (backend)**: FastAPI with Pydantic V2 for REST and WebSocket API
  services. Database access uses psycopg 3 with parameterized SQL only (no ORM, no
  SQLAlchemy, no Alembic).
* **Frontend (dispatcher control center)**: React 19 + TypeScript + Vite + Tailwind CSS,
  compiled to static files and served behind the reverse proxy (Nginx/Traefik). It consumes
  the backend API over REST/WebSocket.
* **Persistent database**: PostgreSQL (with the PostGIS extension for geospatial data) or
  SQLite for packaged development/testing environments.
* **Real-time & caching layer**: Redis (Pub/Sub for live telemetry events and in-memory
  state management).
* **Containerization**: Docker Engine and `docker-compose`. Repository structure:

  ```
  src/
  ├── backend/          # FastAPI + Pydantic V2, psycopg 3 / parameterized SQL (API, ingestion, metrics)
  ├── frontend/         # Vite + React 19 + TypeScript + Tailwind CSS
  └── docker-compose.yml
  ```

  Minimum services defined in `docker-compose`:
  1. `ingestion-service`: Container for synchronous ingestion of IoT telemetry and mocked
     traffic sources (Python). Isolated from everything else (Principle III).
  2. `pulsoflota-backend`: FastAPI API, metric computation and supervisory logic.
  3. `pulsoflota-frontend`: Static React build served by Nginx (in development, the Vite dev
     server with a proxy to the backend).
  4. `database-redis`: Persistence infrastructure (PostgreSQL) and cache/pub-sub (Redis).

### 2.2 Domain Object Model

Domain identifiers are kept as originally defined (see `AGENTS.md`, "Universal conventions").

```
+-------------------------------------------------------------------+
|                            Vehiculo                               |
+-------------------------------------------------------------------+
| - id_vehiculo: str (UUID)                                         |
| - placa: str                                                      |
| - id_operador: str                                                |
| - capacidad_pasajeros: int                                        |
| - estado_operativo: Enum (EN_RUTA, EN_ESTACION, EN_DESVIO, FUERA) |
+-------------------------------------------------------------------+
                                 | 1
                                 | 1..*
+-------------------------------------------------------------------+
|                        EventoTelemetria                           |
+-------------------------------------------------------------------+
| - timestamp: datetime (UTC)                                       |
| - latitud: float                                                  |
| - longitud: float                                                 |
| - velocidad_kmh: float                                            |
| - nivel_ocupacion: float (0.0 - 1.0)                              |
+-------------------------------------------------------------------+

+-------------------------------------------------------------------+
|                           RutaEstandar                            |
+-------------------------------------------------------------------+
| - id_ruta: str                                                    |
| - nombre_corredor: str                                            |
| - estaciones_ordenadas: List[Estacion]                            |
| - headway_objetivo_segundos: int                                  |
+-------------------------------------------------------------------+
                                 | 1
                                 | 1..*
+-------------------------------------------------------------------+
|                            TramoVial                              |
+-------------------------------------------------------------------+
| - id_tramo: str                                                   |
| - coordenada_inicio: GeoPoint                                     |
| - coordenada_fin: GeoPoint                                        |
| - nivel_congestion: Enum (VERDE, AMARILLO, ROJO)                  |
| - velocidad_promedio_actual: float                               |
+-------------------------------------------------------------------+

+-------------------------------------------------------------------+
|                         MetricaServicio                           |
+-------------------------------------------------------------------+
| - ventana_tiempo: TimeWindow                                      |
| - id_estacion: str                                                |
| - p_abordar_t: float (Probability <= t min)                       |
| - ewt_segundos: float (Excess Wait Time)                          |
| - percentil_evaluado: int (85, 95)                                |
+-------------------------------------------------------------------+

+-------------------------------------------------------------------+
|                       PropuestaRegulacion                         |
+-------------------------------------------------------------------+
| - id_propuesta: str                                               |
| - tipo_accion: Enum (DESPACHO_ANTICIPADO, RETENCION, DESVIO_RUTA) |
| - vehiculo_objetivo: Vehiculo                                     |
| - ruta_sugerida: List[TramoVial]                                  |
| - tiempo_respuesta_calculado: float                               |
| - estado_aprobacion: Enum (PENDIENTE, APROBADA, RECHAZADA)        |
| - autorisado_por: Optional[UsuarioDespachador]                    |
+-------------------------------------------------------------------+
```

### 2.3 Two Operational Development Lanes
1. **Disciplined Lane (Ingestion, Message Contracts, Pay-for-Quality)**:
   - *Rigor*: Strict specification first (Contract-First / SDD).
   - *Agent autonomy*: Low (the agent only produces proposals that must be validated in code and gates).
   - *Criticality*: Maximum. Strict continuous integration and DataOps contract tests apply.
2. **Adaptive Lane (React Frontend, Visualization, Alert and Rerouting Rules)**:
   - *Rigor*: Iterations driven by value hypotheses validated with the dispatcher.
   - *Agent autonomy*: Medium (automated development on isolated branches with mandatory review by the module owner).
   - *Scope*: The React 19 + TypeScript + Vite + Tailwind frontend lives in `src/frontend/`
     and is the dispatcher control-center client; it consumes the backend API and makes no
     authorization decisions (A01).

**Low-autonomy lane for Generative AI agents**: Regardless of the lane, no Generative AI
agent operates in a high-autonomy mode. Agents only **propose** (text, code or regulation
recommendations) and **never** send direct commands to vehicles without the **explicit
signature/authorization of the human controller** (Principle IV). This includes the dynamic
rerouting of **US-03**: the AI proposes the detour and the **human dispatcher authorizes it**
before it reaches the on-board units. The deterministic real-time path ($\le 10\text{ s}$)
never depends on a synchronous call to a generative agent (Principle III).

**Lane assignment criteria (with evidence)**: Assigning a story to a lane (Disciplined vs.
Adaptive) is justified with **executed evidence from the repository** (tests, pipelines and
reproducible results), not with a subjective estimate: the Disciplined lane requires a
validated contract and green DataOps tests before building; the Adaptive lane requires a
measurable value hypothesis against $P(\text{abordar} \le t)$ validated with the dispatcher.

---

## 3. Development Flow, Review Process and Quality Gates

### 3.1 RITMO Lifecycle (The 5 Stages per Spiral Turn)
Every spiral turn goes through five structured stages in sequence:
1. **Stage 1 — Plan**: Select the priority risk to mitigate, the turn's closing date and the operating hypotheses. (Owner: Turn Owner).
2. **Stage 2 — Specify**: Write the user story as a measurable SDD (*Specification-Driven Development*) specification, plus a contract gate if schemas change.
3. **Stage 3 — Build**: Develop one story at a time on an isolated branch (`feature/US-XX`), including production code, tests and data rules.
4. **Stage 4 — Verify**: Run the CI pipeline (linting, unit tests, coverage $>80\%$), DataOps contract tests and human reviewer inspection.
5. **Stage 5 — Review (Value Gate)**: Final validation of the value hypothesis by measuring the impact on $P(\text{abordar} \le t)$ with the dispatcher in the test/simulation environment.

### 3.1.1 End-to-End (E2E) Lifecycle — 10 Stages
The 5 RITMO stages describe the engineering turn; the end-to-end (E2E) lifecycle frames
them in a 10-stage operating flow that combines **Agile + DevOps + SRE** and connects
development (*change*) with operations (*run*):

1. **Plan** — risk-based prioritization (ASRs) and selection of the turn's story.
2. **Specify** — measurable SDD story and contract gate (Contract-First).
3. **Build** — implementation on an isolated `feature/US-XX` branch with tests and rules.
4. **Verify** — CI (`backend-ci` / `frontend-ci`), DataOps contract tests and human review.
5. **Review** — value gate with the dispatcher on $P(\text{abordar} \le t)$.
6. **Package and publish** — build versioned images; the DevSecOps gates (SAST + SCA) block
   vulnerable images before they are published to the container registry (GHCR).
7. **Deploy** — deploy to the target environment (MVP: `docker-compose`; evolution: K8s/GitOps).
8. **Operate** — firm real-time operation ($\le 10\text{ s}$) with the isolated ingestion running.
9. **Observe** — the three observability signals (logs, metrics, traces) and the SLIs/SLOs with an error budget.
10. **Learn (Run → Change)** — production incidents and data-freshness degradation alerts
    become **reliability stories** that re-enter Stage 1.

**Run → Change loop (Agile-DevOps-SRE):** a production incident or a data-freshness
degradation alert enters **Stage 1 — Plan** as a reliability story, prioritized by risk
(Principle I). If the SLO **error budget** is exhausted, development of new *features* is
**frozen** until reliability margin is recovered (see §3.4). The CI/CD pipeline acts as an
**Andon**: a red gate stops the line and nobody moves forward until the root cause is fixed,
under a **Shift-Left** culture (quality and security moved as early as possible in the
cycle) and **blameless post-mortems**.

### 3.2 The Three Automated and Human Quality Gates
* **Gate 1: Contract Gate (DataOps)**: Checks that there are no breaks in the JSON/Pydantic schemas and that the data simulators follow the contract specification.
* **Gate 2: Data and CI Gate (DevOps/SRE)**: Validates that ingestion latency is $\le 500$ ms, with no time gaps and with approved test coverage.
* **Gate 3: Value and Human Gate (Dispatcher)**: Formal close of each spiral turn through the approval of the dispatcher and the system manager.

### 3.3 DevOps and SRE Practices

The quality gates define *what* is required; this section defines *how* they are
operated across the lifecycle. They are adopted incrementally, turn by turn, according to
`docs/turns-ritmo.md`.

* **CI/CD pipeline (GitHub Actions)**: The repository uses GitHub Actions
  (`.github/workflows/`). There are two pipelines because of the frontend/backend split:
  - `backend-ci`: lint (`ruff`), types (`mypy`), SAST (`Bandit`), tests and coverage
    (`pytest` > 80 %), SCA (`pip-audit`), image build and image scan (`Trivy`).
  - `frontend-ci`: lint (`ESLint`), types (`tsc --noEmit`), tests (`Vitest`), Vite build
    and SCA of JS dependencies (`npm audit` / `Trivy`).
  Both pipelines run on every *Pull Request* and block the merge if any gate fails
  (Principle V). The `docker-compose` file is validated in CI. The **DevSecOps** gates
  (SAST + SCA) block publishing vulnerable images to the container registry (GHCR) before
  promotion (see ADR-0005).
* **Environments and deployment**: Three logical environments — `development` (local with
  `docker-compose`), `staging` (pre-production) and `production`. `DEBUG=False` is enforced
  in staging and production. Releases ship as versioned images (immutable tag + SHA);
  rollback redeploys the previous image. Database schema changes are applied with
  versioned, idempotent SQL scripts (no Alembic), in a controlled way and with a prior
  backup.
* **MVP target deployment and evolution**: The **first MVP deployment** is
  **Docker + `docker-compose`** with the 4 services (`ingestion-service`, `pulsoflota-backend`,
  `pulsoflota-frontend`, `database-redis`); this is the current/near-term goal. **Publishing
  versioned images to GHCR** through the unified CI/CD pipeline is an **intermediate goal**
  (it may come before a full orchestrator and does not block the MVP). **Kubernetes + Helm +
  GitOps/Argo CD** is documented as the **evolution / future goal** for production in a
  later spiral turn; it is neither built nor required in the MVP (turn-by-turn adoption,
  `docs/turns-ritmo.md`).
* **SLIs and SLOs**: Indicators derived from the NFRs — ingestion latency P99 ≤ 500 ms, map
  refresh latency ≤ 2 s, detection→recommendation latency ≤ 10 s, packet rejection rate
  < 0.1 % and availability of the isolated ingestion. Each SLO has an error budget; once it
  is exhausted, feature deployments are frozen until margin is recovered.
* **Data freshness SLO and shared error budget**: The main reliability SLI is **data
  freshness**: the age of the last telemetry event ingested per active bus. The SLI
  threshold is **< 15 s**; a sample aged ≥ 15 s counts as a failure. The **SLO is 99 %**
  freshness over a rolling **28-day** window, which sets an **error budget of 403 minutes**
  (1 % × 28 days) shared by the whole team. Exhausting this budget **freezes development of
  new features** and prioritizes reliability stories until the margin is restored (Run →
  Change loop, §3.1.1).
* **Three-part set of indicators**: The tracking dashboard combines three families of metrics:
  - **Technical (DORA)**: deployment frequency, change *lead time*, change failure rate and
    time to restore service (MTTR).
  - **Operational**: data freshness, packet rejection rate, ingestion latency P99 and
    compliance with firm real time ($\le 10\text{ s}$).
  - **Business**: $P(\text{abordar} \le t)$ and *Excess Wait Time* (EWT), read at the
    $P_{85}$ / $P_{95}$ percentiles, which feed the pay-for-quality scheme for operators.
* **Observability (three signals)**:
  - **Logs**: structured JSON compatible with OpenTelemetry, with no PII (see SRD A09).
  - **Metrics**: exported in Prometheus format (event counters, latencies, rejection rate,
    bus status), visualized in Grafana.
  - **Traces**: distributed tracing with OpenTelemetry along the ingestion → computation →
    recommendation path, correlated by `correlation_id`.
* **Alerts and incidents**: Alerts to the SRE/DevSecOps team (PagerDuty/Slack) when IoT
  message rejection is > 5 % in 1 min, on **data-freshness degradation** (SLI < 15 s not
  met) or when the error budget is exhausted. Every high-severity incident requires a
  *runbook* and a **blameless post-mortem**. A production incident or a freshness
  degradation alert produces a **reliability story** that re-enters Stage 1 — Plan (Run →
  Change loop, §3.1.1). The CI/CD pipeline works as an **Andon**: a red gate stops
  integration until the root cause is resolved.
* **Healthchecks and resilience**: Every `docker-compose` service defines a `healthcheck`
  (liveness/readiness) and dependencies with `depends_on: condition: service_healthy`. The
  isolated ingestion survives a frontend/backend outage (Principle III) and keeps the
  persistent buffer (A10).
* **Backup and recovery (DR)**: Periodic PostgreSQL backups with explicit RPO and RTO
  targets; restore is tested. Bronze is immutable; silver and gold are recomputed from
  bronze, which limits the impact of a loss.
* **Immutable lineage and fare-collection anti-fraud (DataOps)**: The data pipeline keeps an
  immutable lineage that protects the pay-for-quality scheme for operators. Every *gold*
  aggregate records its `rules_version` and its origin in *bronze*, so every settlement
  metric ($P(\text{abordar} \le t)$, EWT) is reproducible and traceable to the rules version
  that produced it. Quality rules live as deterministic, tested code (never an LLM
  decision), which prevents retroactive changes to the payment indicators.

---

## 4. Document Governance and Amendments

### 4.1 Amendment Procedure
* Any change to this OMD document or its core principles **MUST** be proposed through a Pull Request labeled `constitutional-amendment`.
* The amendment PR **MUST** include a justification based on field evidence or new constraints of the Medellín transport domain.
* It requires the unanimous approval of the team members (Turn Owner, Software Architect and Dispatcher Representative).

### 4.2 Versioning Policy (SemVer)
* **MAJOR (X.0.0)**: Changes to the NON-NEGOTIABLE Core Principles or a restructuring of the container/lane architecture.
* **MINOR (1.X.0)**: New objects in the domain model, new user stories in the matrix or compatible changes to the technology stack.
* **PATCH (1.0.X)**: Minor wording fixes, rule clarifications or adjustments to secondary metrics.

### 4.3 Compliance Audit
* At the end of each spiral turn, the team **MUST** run a compliance review of the 5 Core Principles.
* If a violation of the principles is detected (e.g. untested code pushed to the main branch, or recommendations issued without the human gate), the CI build **MUST** be marked as failed immediately.
