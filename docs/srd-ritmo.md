# Security Requirements Document (SRD) - RITMO / PulsoFlota

**Project:** PulsoFlota — Real-Time Operational Control and Dispatch Center (RITMO Methodology)  
**SRD Version:** 1.0.0  
**Reference Standard:** OWASP Top 10 (2025) & RITMO Criticality Model (SWEBOK v4 / ISO/IEC/IEEE 24765)  
**Software Classification:** Application, Data-Dominant and Supervisory Control  
**Adoption Date:** 2026-11-14  

---

## 1. Overview and Domain Security Scope

This **Security Requirements Document (SRD)** sets the mandatory normative, technical and architectural guidelines for the development, deployment and operation of the **PulsoFlota** system, under the hybrid **RITMO** methodology (Riesgo, Incrementos y Trazabilidad para la Movilidad Operativa — Risk, Increments and Traceability for Operational Mobility) in the city of Medellín.

### 1.1 Operating Context and Domain Risks
PulsoFlota manages real-time bus fleet telemetry (GPS, fare validations, vehicle status) and integrates readings from the road network (flow speed, congestion and accident events). Given its **firm real-time nature (latency $\le 10\text{ s}$)** and its direct impact on the computation of economic incentives ($P(\text{abordar} \le t)$ and *Excess Wait Time* - EWT), system security covers three critical fronts:
1. **Data integrity and fare-collection anti-fraud:** Prevent the malicious injection or alteration of GPS and fare data aimed at artificially inflating the pay-for-quality indicators.
2. **Operational safety and human supervision:** Ensure that automatic or Generative-AI recommendations (frequency adjustments and rerouting for road closures) do not change on-road operations without the explicit authorization (*Human-in-the-Loop*) of the dispatcher.
3. **Availability and system resilience:** Protect the isolated IoT telemetry ingestion so it keeps recording events even when the central web interface fails or under denial-of-service (DDoS) attacks.

### 1.2 Dual Lanes and Criticality
* **Disciplined Lane (High Criticality - Level 1):** IoT data ingestion, contract engine, computation of $P(\text{abordar})$ and contractual settlement indicators. Strict cryptographic verification, message contracts and automated CI tests apply.
* **Adaptive Lane (Medium/Low Criticality - Levels 2 and 3):** Dispatcher web control center, graphical visualization panels and predictive alert rules. It works through validated hypothesis iterations with no direct access to the deterministic real-time path.

---

## 2. Technical Security Requirements (Adapted OWASP Top 10 - 2025 Matrix)

### 2.1 Access Control (A01:2025 - Broken Access Control)
* **Technical requirement:** Every REST or WebSocket API endpoint in the FastAPI backend MUST authenticate the caller's identity and explicitly verify the assigned permissions through Role-Based Access Control (RBAC) in the middleware layer before running any business logic.
* **Acceptance criteria:**
  * **No IDOR:** Insecure Direct Object References are strictly prohibited. If a user tries to access or modify a resource belonging to a different operator (e.g. querying `/api/v1/buses/{bus_id}` or changing routes of another transport basin), the middleware MUST return `403 Forbidden` and log a security alert.
  * **Centralized evaluation in the backend:** Authorization MUST be evaluated exclusively in the FastAPI backend. The React web client (*frontend*, `src/frontend/`) MUST NOT make access decisions or hide buttons as its only control mechanism.
  * **Multi-tenant isolation:** Telemetry data from private consortia MUST be logically isolated, so that no operator can access its competitors' raw telemetry.

### 2.2 Security Configuration and Container Infrastructure (A02:2025 - Security Misconfiguration)
* **Technical requirement:** Docker container images and reverse proxy servers (Nginx/Traefik) MUST be configured under the principle of least privilege and infrastructure *hardening*.
* **Acceptance criteria:**
  * **Non-root execution in Docker:** All Python containers (Ingestion and Control Center) MUST run as a non-root user (`USER appuser` with UID `10001`).
  * **HTTP security headers:** The web server MUST include the following headers in every HTTP response:
    * `Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none';`
    * `Strict-Transport-Security: max-age=31536000; includeSubDomains`
    * `X-Content-Type-Options: nosniff`
    * `X-Frame-Options: DENY`
  * **Infrastructure concealment:** The server MUST remove headers that describe the technology stack, such as `Server`, `X-Powered-By` and Python/FastAPI versions.
  * **Debug modes disabled:** `DEBUG=False` MUST be enforced in every staging and production environment. Exposing Swagger/ReDoc in production without prior authentication is prohibited.

### 2.3 Software Supply Chain and Agent Factory (A03:2025 - Software Supply Chain Failures)
* **Technical requirement:** Third-party dependencies (Python libraries, Docker base images and JavaScript libraries) MUST be strictly controlled in the repository and the CI/CD pipeline.
* **Acceptance criteria:**
  * **Automated vulnerability scanning (SCA):** The CI/CD pipeline MUST run software composition analysis tools (`pip-audit`, `Safety` or `Snyk`) on every *Pull Request*.
  * **Blocking by CVE severity:** If High or Critical vulnerabilities (CVSS $\ge 7.0$) are found in any Python package or Docker base image, the CI pipeline MUST fail automatically and prevent the merge.
  * **Version pinning:** Every dependency MUST be declared with its exact version and integrity hash (`poetry.lock` or a `requirements.txt` compiled with SHA-256 hashes).

### 2.4 Cryptography and Data Protection (A04:2025 - Cryptographic Failures)
* **Technical requirement:** All data in transit between the buses' on-board units, the road sensors and the ingestion center, as well as data at rest, MUST be protected with strong encryption.
* **Acceptance criteria:**
  * **Encryption in transit:** External communications MUST use TLS 1.3 exclusively (or TLS 1.2 as the lower bound with PFS *ciphersuites*). IoT vehicle fleet connections MUST authenticate through mTLS (*Mutual TLS*) with per-unit x509 certificates.
  * **Credential storage:** Dispatcher and administrator passwords MUST be hashed with **Argon2id** (or `bcrypt` with a cost factor $\ge 12$).
  * **Secrets management:** Including passwords, JWT tokens, database keys or API keys in the source code or in `.env` files in the repository is strictly prohibited. An external secrets manager (*Docker Secrets* or *HashiCorp Vault*) injected at runtime MUST be used.

### 2.5 Injection and IoT Schema Validation (A05:2025 - Injection)
* **Technical requirement:** Every incoming data flow (REST requests, IoT telemetry MQTT/WebSocket messages or query parameters) MUST be sanitized and formally validated before it touches the database or the rules engine.
* **Acceptance criteria:**
  * **Parameterized queries:** Direct string concatenation in SQL statements is prohibited. The system MUST use psycopg 3 with parameterized SQL only (no ORM, no SQLAlchemy, no Alembic); Pydantic V2 validates data at the boundary.
  * **Strict schema validation with Pydantic:** Every GPS telemetry or fare-collection ingestion event MUST be validated against a strict Pydantic V2 schema at the ingestion gate. If a packet contains wrong types, values outside the geographic range or undeclared extra fields, it MUST be rejected immediately with HTTP `422 Unprocessable Entity`.

### 2.6 Secure Design and Generative AI Isolation (A06:2025 - Insecure Design)
* **Technical requirement:** The system architecture MUST fully isolate the deterministic real-time computation path from artificial intelligence modules or adaptive predictive algorithms.
* **Acceptance criteria:**
  * **Human gate (*Human-in-the-Loop*):** Frequency regulation or road detour recommendations produced by Generative AI models MUST be shown on the console as non-binding suggestions. Applying any change to on-road operations MUST require the explicit, manual approval of the human dispatcher.
  * **Real-time path isolation:** No AI model or autonomous agent MUST have direct write permissions on the production database or on the dispatch APIs of the on-board units.
  * **STRIDE threat analysis:** Every new feature or architectural change in the disciplined lane MUST have a documented, risk-prioritized STRIDE threat model review.

### 2.7 Authentication and Session Management (A07:2025 - Authentication Failures)
* **Technical requirement:** The control and dispatch center MUST have strong authentication mechanisms that resist brute-force attacks, impersonation and session hijacking.
* **Acceptance criteria:**
  * **Secure JWT session tokens:** JWT session tokens MUST be signed with the `RS256` algorithm (public/private key), expire after at most 15 minutes and be sent only in cookies with the `HttpOnly`, `Secure` and `SameSite=Strict` attributes.
  * **Multi-factor authentication (MFA):** Access for system administrators and basin supervisors MUST require MFA (TOTP).
  * **Brute-force protection:** The system MUST temporarily lock (for 15 minutes) any account or IP address that records 5 consecutive failed sign-in attempts.

### 2.8 Software and Data Integrity and Fare-Collection Anti-Fraud (A08:2025 - Data & Software Integrity Failures)
* **Technical requirement:** The tamper-proof integrity of the telemetry and fare-collection events that feed the computation of the $P(\text{abordar} \le t)$ service metrics and the later settlement of pay-for-quality to operators MUST be guaranteed.
* **Acceptance criteria:**
  * **Data lineage audit with DataOps:** Every ingestion data pipeline MUST record the origin, an immutable timestamp and the message checksum.
  * **Detection of anomalies and tampered data:** The system MUST have automated rules to detect and discard tampered data (e.g. GPS location jumps at speeds above $120\text{ km/h}$, duplicated fare sequences or inconsistencies between road sensors and bus coordinates).
  * **Digital event signature:** Data packets sent by the fare validators MUST include an HMAC signature based on a secret token stored in the vehicle validator's secure module.

### 2.9 Logging, Auditing and SRE Observability (A09:2025 - Security Logging and Alerting Failures)
* **Technical requirement:** The system MUST produce an immutable, structured audit log for every security-sensitive action and operational decision.
* **Acceptance criteria:**
  * **Structured JSON logs:** Every log event MUST be emitted in structured JSON compatible with OpenTelemetry standards.
  * **Mandatory auditable events:** The following MUST be recorded with a UTC timestamp and user identifier:
    1. Authentication attempts (success/failure).
    2. Permission changes or user modifications.
    3. Road detours or dispatch adjustments authorized or rejected by the dispatcher.
    4. Changes or outages in the ingestion data sources.
  * **Protection of PII and sensitive data:** Audit records and application logs MUST NEVER include plain-text passwords, private keys, full JWT tokens or personally identifiable data of drivers or passengers.
  * **Real-time alerts:** Security anomalies or spikes in IoT message rejection (>5% failures in 1 minute) MUST trigger immediate alerts to the SRE/DevSecOps team via PagerDuty/Slack.
  * **Freshness SLO and error budget:** The system MUST measure data freshness as an SLI (threshold `< 15 s`) with a `99 %` SLO over a `28-day` window (shared error budget of `403 minutes`). Freshness degradation MUST alert the SRE/DevSecOps team, and exhausting the error budget MUST freeze the deployment of new *features* until reliability margin is recovered (Run → Change loop).

### 2.10 Exception Handling and Real-Time Resilience (A10:2025 - Exceptional Conditions Handling)
* **Technical requirement:** The Python backend and the isolated ingestion MUST handle exceptions defensively, ensuring continuity of operations and avoiding leaks of infrastructure details.
* **Acceptance criteria:**
  * **Error trace sanitization:** No HTTP or WebSocket API response to the client MUST expose *stack traces*, local file paths such as `/workspace/...` or internal PostgreSQL database structures.
  * **Unified correlation ID:** On an unhandled error (HTTP 500), the application MUST return a standard generic message together with a unique tracking identifier (`correlation_id`) recorded internally in the logs.
  * **Operational fallback when the control center fails:** If the control center or the web interface collapses, the isolated IoT ingestion service MUST keep recording events in the persistent buffer, and the dispatcher console MUST switch automatically to a local contingency mode based on predefined static dispatch plans.

---

## 3. Security Quality Gates Matrix

In line with the RITMO spiral turns, no software increment may move to the next stage or be deployed to production without passing the following security gates:

| Quality Gate | RITMO Stage | Frequency / Moment | Required Tests and Controls | Mandatory Approval Criterion | Owner |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Gate 1: Contract and Static Analysis** | 2. Specify / 3. Build | Every *Pull Request* | SAST analysis (`Bandit`, `ESLint`) and Pydantic schema validation. | 0 Critical/High SAST findings; contract schema validated. | Development Agent / Reviewer |
| **Gate 2: Integration and Supply Chain** | 4. Verify | In continuous integration (CI) | SCA scanning (`pip-audit`, `Trivy`) and unit/integration test suites. | Test coverage $>80\%$; 0 known vulnerabilities in dependencies. | Testing Agent / DevSecOps |
| **Gate 3: Data Gate (DataOps)** | 4. Verify | At runtime (Ingestion) | Message contract tests, HMAC validation and anomaly detection. | Packet rejection rate $<0.1\%$; ingestion latency $\le 200\text{ ms}$. | DataOps Lead / Ingestion |
| **Gate 4: Value and Operational Safety Gate** | 5. Review | Close of the Spiral Turn | *Human-in-the-Loop* validation, detour audit and fallback test. | Explicit dispatcher approval; verification that AI does not interfere with real time. | Dispatcher / Turn Owner |

### 2.11 CI/CD Orchestration per Pipeline (Frontend and Backend)

Given the split between frontend (`src/frontend/`, React 19 + TypeScript + Vite + Tailwind) and backend (`src/backend/`, FastAPI + Pydantic V2, with data access through psycopg 3 and parameterized SQL, no ORM), the gates above run in two independent GitHub Actions pipelines. Both MUST pass before merging:

* **`backend-ci`:** SAST with `Bandit`, Pydantic V2 schema validation, `pytest` tests and coverage > 80 %, SCA with `pip-audit`/`Safety`, and Docker image scanning with `Trivy` (blocking at CVSS ≥ 7.0).
* **`frontend-ci`:** SAST/lint with `ESLint`, type checking with `tsc --noEmit`, `Vitest` tests, SCA of JS dependencies (`npm audit`/`Trivy`) and the Vite production build. The frontend does not store secrets or make authorization decisions.

The **DevSecOps (SAST + SCA)** gates MUST block the **publication of vulnerable container images** to the registry (GHCR): no image with a High/Critical finding (CVSS ≥ 7.0) MUST be promoted or published. The first MVP deployment is Docker + `docker-compose` (4 services); **Kubernetes + Helm + GitOps/Argo CD** is adopted as the **evolution / future goal** for production, not in the MVP (turn-by-turn adoption). This orchestration is detailed in ADR-0005.

---

## 4. Governance and Amendment Procedure

1. **Versioning policy:** This SRD follows semantic versioning (`MAJOR.MINOR.PATCH`). A `MAJOR` increment represents changes to the security requirements due to regulatory updates or architectural restructuring; `MINOR` reflects new acceptance criteria; `PATCH` applies to wording fixes or technical clarifications.
2. **Amendment procedure:** Any change to the normative requirements (MUST / SHOULD rules) requires an architecture decision record (ADR), validation at the spiral's risk gate and the unanimous signature of the Turn Owner, the Security Architect and the Dispatcher Representative.
3. **Compliance audit:** An automated compliance review of this SRD will run at the end of each RITMO spiral turn by executing the security and DataOps audit pipeline.
