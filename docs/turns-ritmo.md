# Turn Map — RITMO / PulsoFlota

## Document Control
* **PROJECT_NAME**: RITMO (Riesgo, Incrementos y Trazabilidad para la Movilidad Operativa) / PulsoFlota
* **MAP VERSION**: 0.1.3 (draft for team review)
* **DATE**: 2026-11-21
* **STATUS**: Proposal. Requires team approval
* **GOVERNED BY**: Constitution v1.2.0, "Phased Adoption" section

---

## 1. Purpose and How to Use It

This document states **in which spiral turn (vuelta) each norm** of the
constitution, the PRD and the SRD is adopted. The technical norms describe the
finished system; this map says which ones are required in each turn.

Planning is **rolling-wave**:
* The **active turn** is detailed.
* **Future turns** are high level: risk, scope and the norms they adopt.
* In **Stage 1 — Plan** of each turn, the Turn Owner details the next turn and
  updates this map. That update does not require a constitutional amendment.

**Rules that do not change between turns:**
* The **5 NON-NEGOTIABLE Core Principles** apply in **every** turn, from the
  first one.
* A norm adopted in a turn **remains mandatory** in every later turn.
* A **deferred** norm is not required in the active turn. Agents (`create-plan`,
  `validate-plan`, `review-code`) **MUST NOT** report it as a blocking finding;
  they may record it as "evolution".

---

## 2. Order of the Turns

The order is set by **Principle I (Risk-First Order)**: no adaptive-lane feature
starts while a Level 1 risk (security or data integrity) remains unmitigated.
That is why the two Level 1 turns come first.

| Turn | Name | Risk it mitigates | Level | Lane | Status |
|---|---|---|---|---|---|
| **1** | Data and minimal loop | Data integrity: malformed, duplicated or missing data contaminates the metric and the recommendations | **1** | Disciplined | **Active**: built for the workshop (2026-11-24) |
| **2** | Operational security | Unauthorized access, impersonation of units and fare-collection fraud | **1** | Disciplined | Design |
| **3** | Real time and isolation | Concurrency and latency at peak hours; a web failure dragging ingestion down | 2 | Disciplined | Design |
| **4** | Adaptive lane | Value: recommendations that actually improve P(board ≤ t) | 2 | Adaptive | Design |

---

## 3. Turn 1 — Data and Minimal Loop (active)

**Operational hypothesis:** with a message contract validated at the boundary and
a minimal closed loop (detect → recommend → approve → execute → measure), the
dispatcher receives reliable recommendations. Missing or duplicated data does not
trigger false alerts.

**Corridor:** Prado station (Metro line A), feeder route C6-008, station →
neighborhood direction only. Base fleet of 5 buses + 2 in reserve.

### 3.1 Scope
* **Containers from day one** (Principle III is never deferred): `docker-compose` with
  separate services for PostgreSQL, the simulator/ingestion, the FastAPI backend
  (`src/backend/`) and the React frontend (`src/frontend/`). The ingestion container keeps
  writing to bronze even if the backend or the web console is down.
* **Frontend/backend split from turn 1:** the dispatcher console is a React 19 +
  TypeScript + Vite + Tailwind app in `src/frontend/`, consuming the FastAPI backend in
  `src/backend/` over REST/WebSocket. In turn 1 the console shows fleet state and headway
  (no geographic map yet).
* **Message contract** with Pydantic V2. Invalid events are rejected with `422`
  and recorded with their reason.
* **Simulator** with a simple Python loop and a 5 s step. It publishes 5 events:
  bus position, stop arrival and departure, rider arrival, driver confirmation
  and incident report.
* **PostgreSQL persistence** with bronze, silver and gold schemas. Position is
  stored as distance along the corridor in meters, without geometry.
* **Data faults (D1):** duplicates and source outage. A bus without data becomes
  "Estimated" and does not trigger alerts.
* **Metrics:** headway, mean wait and EWT.
* **Scenarios:** bunching, gap, transfer surge, segment accident, broken-down bus
  and data fault.
* **Models:** baselines for travel time per segment and for demand at Prado. ML
  predicts, rules decide and a person approves.
* **Recommendations:** hold, adjust departure and reserve dispatch, **always with
  dispatcher approval** (RF-2.3).
* **PRD stories covered:** US-01 partially (headway and fleet state, without a
  geographic map) and US-02.

### 3.2 Norms adopted
* The 5 Core Principles, including Principle III (ingestion in its own container).
* RNF-3.2.1 and RNF-3.2.2: Python packaged with Docker and `docker-compose`; ingestion
  isolated from the web.
* RNF-3.3.1: boundary validation and rejection of 100 % of packets without a
  valid schema.
* RF-2.1, RF-2.2 and RF-2.3.
* Gate 1: Pydantic schema validation only.
* Gate 2: unit and integration tests with coverage > 80 %.
* Gate 4: explicit dispatcher approval.
* From security, only what costs nothing extra: parameterized queries, no
  secrets in the repository, error responses without stack traces.
* **DevOps/SRE (turn 1 baseline):** `backend-ci` and `frontend-ci` pipelines in
  GitHub Actions running lint, types, tests and coverage > 80 % on every PR; per-service
  `healthcheck` in `docker-compose`. Full SAST/SCA, metrics/traces, SLO error budgets,
  staging/production environments and DR are deferred (see below).

### 3.3 Deferred norms (evolution)
Redis (and the `database-redis` service), PostGIS, 1,000 events/s, geographic map
≤ 2 s, SAST/SCA, RBAC/JWT/MFA, mTLS, HMAC, secret manager and route diversion
(US-03). DevOps/SRE deferred: image build/scan (`Trivy`), Prometheus metrics and
OpenTelemetry traces, SLO error budgets with SRE alerting, staging/production
environments with rollback, and PostgreSQL backup/DR (RPO/RTO).

---

## 4. Turn 2 — Operational Security (design)

* **Scope:**
  * RBAC in the backend and multi-tenant isolation.
  * RS256 JWT in secure cookies, MFA for administrators and supervisors, lockout
    after 5 failed attempts.
  * mTLS with one x509 certificate per bus and HMAC signature on fare collection.
  * Docker Secrets or Vault.
  * Security headers and OpenTelemetry-compatible JSON logs, without PII.
  * STRIDE threat modeling.
  * Anti-fraud: GPS jumps > 120 km/h, duplicate fare validations and sensor
    inconsistency.
* **Norms adopted:** the full security section (OWASP Top 10 — 2025), the full
  Gate 1 (SAST: Bandit, ESLint) and the SCA part of Gate 2 (`pip-audit`, `npm audit`,
  Trivy image/dependency scan). DevOps/SRE: OpenTelemetry structured JSON logs without PII
  and SRE/DevSecOps alerting (A09), secret manager (Docker Secrets / Vault).

## 5. Turn 3 — Real Time and Isolation (design)

* **Scope:**
  * Redis Pub/Sub (or a Kafka-API broker) as the `database-redis` service in `docker-compose`.
  * Container hardening for production (non-root UID 10001, minimal images).
  * PostGIS and TimescaleDB.
  * Interactive map with refresh ≤ 2 s.
  * All 5 data faults: duplicates, out of order, impossible position, source
    outage and bursts.
  * Persistent buffer and local contingency mode.
* **Scope (DevOps/SRE):**
  * Prometheus metrics and OpenTelemetry distributed traces on the ingestion → compute →
    recommendation path.
  * SLIs/SLOs with error budgets for the real-time latencies; alerting on budget burn.
  * Staging and production environments with versioned image releases and rollback.
  * PostgreSQL backup and DR (explicit RPO/RTO), with a tested restore.
* **Norms adopted:** RNF-3.1.2 (1,000 events/s, P99 ≤ 500 ms), RNF-3.2.3, RNF-3.4.2,
  RNF-3.4.3, RNF-3.4.4, RF-1.1, RF-1.3 and Gate 3 (DataOps: rejection < 0.1 %, ingestion
  ≤ 200 ms).

## 6. Turn 4 — Adaptive Lane (design)

* **Scope:**
  * Full US-03: blockage detection, route recalculation ≤ 5 s, diversion
    recommendation and diversion audit.
  * Both directions of the corridor, with short-turning.
  * Discrete-event simulation.
  * Full travel-time and demand models, anomaly detection and experiment
    tracking.
  * Metro ridership (RF-1.4).
  * Prioritization by P(board ≤ t) (RF-2.4).
* **Norms adopted:** RF-3.1 to RF-3.4, RF-1.4, RF-2.4 and the full Gate 4
  (diversion audit and fallback test).

---

## 7. Maintaining the Map
* The map is updated in Stage 1 — Plan of each turn, through a PR reviewed by the
  team.
* Moving a norm to a turn **later** than the one it was assigned to requires a
  written justification in the PR.
* At the close of each turn (Stage 5), the compliance review checks the 5 Core
  Principles and the norms adopted **up to that turn**.
