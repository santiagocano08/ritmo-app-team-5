# PRD — Product Requirement Definition: RITMO / PulsoFlota

## Document Control
* **PROJECT_NAME**: RITMO (Riesgo, Incrementos y Trazabilidad para la Movilidad Operativa — Risk, Increments and Traceability for Operational Mobility) / PulsoFlota
* **CONSTITUTION_VERSION**: 1.0.0
* **RATIFICATION_DATE**: 2026-11-06
* **LAST_AMENDED_DATE**: 2026-11-14
* **STATUS**: Ratified / In Initial Production

---

## 1. Product Overview and Domain Problem

### 1.1 Operating Context (Medellín)
The city of Medellín faces high levels of traffic congestion caused by the inefficiency and unreliability of its public bus system. Current operations suffer from two main structural causes:
1. **Lack of information and road visibility**: Fleet dispatch relies on late, manual or missing data. Operators capture GPS positions and fare validations without a unified data standard, which leaves operations blind to the real-time congestion status of the segments of the standard road network.
2. **Distorted operating incentives**: The pay-per-passenger model encourages the "guerra del centavo" (the "penny war"), which leads to unfair competition, *bus bunching* and the systematic degradation of service regularity.

### 1.2 Purpose of PulsoFlota
PulsoFlota is the real-time supervisory web control center designed for bus dispatchers and traffic controllers. It enables timely and reliable regulation decisions based on integrated telemetry, regularity algorithms and predictive road alerts.

### 1.3 System Scope
* **Test corridor**: A mass-transit bus corridor with closed stations, predefined standard routes and a multimodal transfer point with the Metro de Medellín.
* **Data environment**: Telemetry and ingestion fed by a synthetic data generator calibrated with the Metro de Medellín open microdata and mocked road sensors.
* **Core quality metric**: The probability of boarding within $t$ minutes or less after arriving at the station, $P(\text{abordar} \le t)$, complemented by the Excess Wait Time ($EWT$). It measures the service from the rider's real perspective (including bus occupancy), processed as time series read at percentiles ($P_{85}$, $P_{95}$).

---

## 2. Functional Requirements (FR)

### US-01: Real-Time Fleet Status Viewer and Road Monitoring
* **RF-1.1 (MUST)**: The system **MUST** display a real-time interactive map showing the updated geospatial position of every active bus in the corridor with a refresh latency of $\le 2$ seconds.
* **RF-1.2 (MUST)**: The system **MUST** compute and display the current headway between consecutive vehicles on each standard route, highlighting deviations greater than $\pm 15\%$ from the running plan.
* **RF-1.3 (MUST)**: The system **MUST** ingest traffic flow speed per segment and classify congestion levels on the road network using a color-coded visual scheme (Green: Free-flowing, Yellow: Moderate, Red: Congested).
* **RF-1.4 (SHOULD)**: The system **SHOULD** integrate passenger ridership data from the Metro stations linked to the transfer point to anticipate demand peaks.

### US-02: Alert Engine and Dynamic Dispatch Recommendations
* **RF-2.1 (MUST)**: The system **MUST** issue early fleet desynchronization alerts at least $\ge 3$ minutes before a *bunching* event or a frequency *gap* takes hold.
* **RF-2.2 (MUST)**: The system **MUST** generate regulation recommendations (e.g. holding at a station, early departure, injecting a reserve bus) with a computation and response time of $\le 10$ seconds.
* **RF-2.3 (MUST)**: The system **MUST** require the manual approval of the human dispatcher before sending any regulation order to the on-board units.
* **RF-2.4 (SHOULD)**: The system **SHOULD** prioritize the recommendations that maximize the $P(\text{abordar} \le t)$ indicator in the active time band.

### US-03: Dynamic Rerouting for Road Contingencies
* **RF-3.1 (MUST)**: The system **MUST** detect road blockages or accidents on standard routes by ingesting events from the mocked traffic data stream.
* **RF-3.2 (MUST)**: The system **MUST** automatically compute alternative routes for the affected fleet, evaluating the estimated impact on travel time and corridor frequency.
* **RF-3.3 (MUST)**: The system **MUST** present the detour recommendation to the dispatcher on the map viewer with the suggested route, the extra distance and the projected change in the service indicator. The AI **proposes** the dynamic rerouting; no detour order reaches the on-board units without the **explicit authorization of the human dispatcher** (*Human-in-the-Loop*). Generative AI agents operate in **low-autonomy** mode and never send direct commands to the vehicle without the human controller's signature.
* **RF-3.4 (SHOULD)**: The system **SHOULD** keep an audit log of the detours authorized by the dispatcher, used to compute compensations and contract compliance with operators.

---

## 3. Non-Functional Requirements (NFR)

### 3.1 Performance and Firm Real Time
* **RNF-3.1.1 (MUST)**: The system **MUST** be classified as *Firm Real Time*. A late recommendation does not cause catastrophic physical failures, but it has no operational value.
* **RNF-3.1.2 (MUST)**: The ingestion event processing pipeline **MUST** process up to 1,000 telemetry events per second with a peak latency of $P_{99} \le 500$ ms.
* **RNF-3.1.3 (MUST)**: The total time from detecting an on-road anomaly to presenting the recommendation on the dispatcher console **MUST** be $\le 10$ seconds.

### 3.2 Architecture and Container Deployment
* **RNF-3.2.1 (MUST)**: The **backend** (API, ingestion and metric computation) **MUST** be developed in Python (FastAPI + Pydantic V2) and packaged with Docker and `docker-compose`. Database access **MUST** use psycopg 3 with parameterized SQL only (no ORM, no SQLAlchemy, no Alembic; parameterized queries are the baseline for A05 injection prevention). The dispatcher control-center **frontend** **MUST** be developed as a separate web application in React 19 + TypeScript + Vite + Tailwind CSS, served behind a reverse proxy. Frontend and backend live in separate folders under `src/` (`src/frontend/`, `src/backend/`). The **first MVP** deployment is Docker + `docker-compose` with 4 services (`ingestion-service`, `pulsoflota-backend`, `pulsoflota-frontend`, `database-redis`); **Kubernetes + Helm + GitOps/Argo CD** is documented as the **evolution / future goal** for production and is not required for the MVP. Every exchange between modules follows **Contract-First** with versioned JSON schemas (Pydantic V2 / OpenAPI).
* **RNF-3.2.2 (MUST)**: The real-time telemetry ingestion service **MUST** run in a container fully isolated from the backend and the frontend, so that interface failures cannot affect data capture.
* **RNF-3.2.3 (MUST)**: The system **MUST** include a persistent database (PostgreSQL / SQLite) and an in-memory storage/pub-sub layer (Redis) to manage the mocked real-time data.

### 3.4 Operations, Observability and Continuous Delivery (DevOps / SRE)
* **RNF-3.4.1 (MUST)**: The project **MUST** have separate CI/CD pipelines (GitHub Actions) for backend and frontend, run on every *Pull Request*, that block the merge if any quality gate fails (lint, types, SAST, tests, coverage > 80 %, SCA and image build/scan).
* **RNF-3.4.2 (MUST)**: The system **MUST** expose the three observability signals: structured JSON logs (OpenTelemetry), Prometheus-format metrics and distributed traces correlated by `correlation_id`.
* **RNF-3.4.3 (SHOULD)**: The team **SHOULD** define SLIs/SLOs with an error budget for the critical latencies (ingestion P99 ≤ 500 ms, map ≤ 2 s, detection→recommendation ≤ 10 s) and alert the SRE/DevSecOps team when they are exhausted.
* **RNF-3.4.5 (MUST)**: The team **MUST** govern reliability through a **data freshness SLO** with an SLI threshold of **< 15 s** and a **99 %** target over a rolling **28-day** window (shared error budget of **403 minutes**). Once the budget is exhausted, development of new *features* **MUST** be frozen until margin is recovered; production incidents and freshness degradation alerts **MUST** re-enter the backlog as reliability stories (Run → Change loop).
* **RNF-3.4.6 (MUST)**: The team **MUST** track a three-part set of indicators: **technical (DORA)** — deployment frequency, *lead time*, change failure rate and MTTR; **operational** — data freshness, rejection rate, ingestion latency P99 and firm real time ≤ 10 s; and **business** — $P(\text{abordar} \le t)$ and EWT at the $P_{85}$ / $P_{95}$ percentiles.
* **RNF-3.4.7 (SHOULD)**: The **DevSecOps** gates (SAST + SCA) **SHOULD** block publishing vulnerable container images to the registry (GHCR) before promotion. The first MVP deployment is Docker + `docker-compose` (4 services); **Kubernetes + Helm + GitOps/Argo CD** is adopted as the **evolution / future goal** for production in a later turn, not in the MVP.
* **RNF-3.4.4 (SHOULD)**: The system **SHOULD** include per-service *healthchecks* (liveness/readiness) in `docker-compose`, periodic PostgreSQL backups with RPO/RTO targets and a *rollback* procedure that redeploys the previous image.

### 3.3 Data Quality, Security and Integrity
* **RNF-3.3.1 (MUST)**: All telemetry ingestion **MUST** be validated at the boundary through message contracts (Pydantic / JSON Schema). Corrupt or out-of-date data **MUST** be rejected and recorded in the DataOps log.
* **RNF-3.3.2 (MUST)**: The system **MUST** implement mechanisms to detect tampered data (e.g. inconsistent GPS jumps or duplicate validations) to protect the pay-for-quality computation.
* **RNF-3.3.3 (SHOULD)**: The system **SHOULD** provide fault tolerance through a synthetic data simulator that replaces failed telemetry sources without interrupting the dispatcher's operation.

---

## 4. Acceptance and Validation Criteria Matrix

| Requirement ID | Acceptance Criterion | Validation Method | Pass/Fail |
| :--- | :--- | :--- | :--- |
| **RF-1.1** | Map latency $\le 2\text{ s}$ on position refresh. | Frontend performance test with 100 simulated buses. | Required |
| **RF-2.2** | Recommendation computed in $\le 10\text{ s}$. | Load test of the algorithmic engine in CI/CD. | Required |
| **RF-2.3** | No command is sent to the fleet without a human confirmation click. | Code inspection and API integration tests. | Required |
| **RF-3.2** | Automatic route recomputation after a road-blockage event in $\le 5\text{ s}$. | Automated injection of synthetic accident events. | Required |
| **RNF-3.3.1** | $100\%$ of telemetry packets without a valid schema are rejected. | Automated data quality gate in DataOps. | Required |
| **RNF-3.4.1** | A PR with a failed gate (lint/types/SAST/tests/coverage/SCA) cannot be merged. | `backend-ci` and `frontend-ci` pipelines run on every PR. | Required |
| **RNF-3.4.2** | JSON logs, Prometheus metrics and traces available for the ingestion→recommendation path. | Inspection of the observability endpoints and trace review with `correlation_id`. | Required |
