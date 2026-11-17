---
inclusion: auto
name: security
description: When implementing security, authentication, cryptography, secret management, container hardening, HTTP headers, supply chain (SCA) or STRIDE threat modeling. OWASP Top 10 (2025) matrix.
---

# Security — OWASP Top 10 (2025) — PulsoFlota

Full matrix of acceptance criteria. The constitution ("Technical and Security
Constraints" section) sets the governing MUSTs; this file operationalizes the
criteria. These norms are adopted in the turn that `docs/turns-ritmo.md` assigns
(mostly turn 2, "Operational security").

## A01 — Broken Access Control

- RBAC in the backend middleware; authenticate the caller and check permissions
  before business logic.
- IDOR is forbidden: access to someone else's resource → `403 Forbidden` +
  security alert.
- Authorization only in the backend; the frontend never decides access and does
  not just hide buttons.
- Multi-tenant isolation: telemetry from private consortia is logically
  isolated.

## A02 — Security Misconfiguration

- Python containers (Ingestion and Console) run as a non-root user:
  `USER appuser` with UID `10001`.
- Mandatory HTTP headers on every response:
  - `Content-Security-Policy: default-src 'self'; script-src 'self'; object-src 'none';`
  - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
- Remove `Server`, `X-Powered-By` and Python/FastAPI versions.
- `DEBUG=False` enforced in staging and production; Swagger/ReDoc not exposed in
  production without authentication.

## A03 — Software Supply Chain Failures

- SCA on every PR: `pip-audit`, `Safety` or `Snyk` (Python), `Trivy` (base
  Docker images and JS libraries).
- Block merges on High or Critical CVEs (CVSS ≥ 7.0).
- Pin dependencies to exact versions with SHA-256 hashes (`poetry.lock` or
  `requirements.txt` with hashes).

## A04 — Cryptographic Failures

- Encryption in transit: TLS 1.3 (minimum TLS 1.2 with PFS cipher suites); IoT
  fleet with mTLS and one x509 certificate per unit.
- Passwords with Argon2id (or `bcrypt` with cost factor ≥ 12).
- Secrets (passwords, JWT, DB keys, API keys) through Docker Secrets or
  HashiCorp Vault, injected at runtime. Forbidden in source code or repository
  `.env` files.

## A05 — Injection

- Parameterized queries (SQLAlchemy / asyncpg / Pydantic V2); SQL string
  concatenation is forbidden.
- Strict Pydantic V2 validation at ingestion: wrong types, values outside the
  geographic range or undeclared fields → `422 Unprocessable Entity`.

## A06 — Insecure Design

- Isolate the deterministic real-time path from predictive AI modules.
- Human-in-the-Loop: AI recommendations are non-binding suggestions; any change
  to on-road operation requires explicit manual approval from the dispatcher.
- No model/agent with direct write access to the production DB or the dispatch
  APIs.
- Documented STRIDE, prioritized by risk, for every new feature or change in the
  disciplined lane.

## A07 — Authentication Failures

- JWT signed with `RS256`, expiry ≤ 15 min, `HttpOnly` + `Secure` +
  `SameSite=Strict` cookies.
- MFA (TOTP) mandatory for administrators and basin supervisors.
- 15-min lock of an account or IP after 5 consecutive failed attempts.

## A08 — Data & Software Integrity Failures

- Data lineage (DataOps): provenance, immutable timestamp and checksum per
  message.
- Anomaly detection: GPS jumps > 120 km/h, duplicated fares, inconsistency
  between road sensors and bus coordinates.
- HMAC signature on fare-collection packets (secret of the validator's secure
  module).

## A09 — Security Logging and Alerting Failures

- Structured JSON logs compatible with OpenTelemetry.
- Auditable events with UTC timestamp and user identifier: authentication
  attempts (success/failure), permission/user changes, authorized/rejected
  diversions or dispatch adjustments, changes or outages in ingestion sources.
- Never log plain-text passwords, private keys, full JWTs or PII of drivers or
  riders.
- Real-time alerts to the SRE/DevSecOps team (PagerDuty/Slack) on security
  anomalies or IoT message rejection > 5 % in 1 min.

## A10 — Exceptional Conditions Handling

- Sanitize traces: no HTTP/WebSocket response exposes stack traces, local paths
  (`/workspace/...`) or internal PostgreSQL structures.
- HTTP 500 → generic message + `correlation_id` recorded in the logs.
- Operational fallback: isolated IoT ingestion keeps buffering persistently; the
  console switches to predefined static dispatch plans.

## References

- API/auth flow and error handling: `backend-api.md`.
- SAST/SCA gates in CI: `testing-quality-gates.md`.
- Image and `docker-compose` hardening: `deployment-containers.md`.
