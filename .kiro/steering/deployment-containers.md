---
inclusion: fileMatch
fileMatchPattern: ["**/Dockerfile", "**/Dockerfile.*", "**/docker-compose*.yml", "**/docker-compose*.yaml", "**/.dockerignore"]
---

# Deployment and Containers — PulsoFlota

> Target system. Check `docs/turns-ritmo.md` for what the active turn requires.

## `docker-compose` services

At least three services:

1. **`ingestion-service`** — synchronous ingestion of IoT telemetry and mocked
   traffic sources.
2. **`pulsoflota-web`** — modular monolith: supervisory console, metric
   calculation and interactive map.
3. **`database-redis`** — persistence and event cache/pub-sub infrastructure.

## Isolation

- `ingestion-service` runs in a container **fully isolated** from the
  `pulsoflota-web` monolith, so interface failures do not affect data capture.

## Hardening (A02)

- **Non-root** execution: `USER appuser` with UID `10001` in every Python
  container (Ingestion and Console). Least privilege.
- Hardened reverse proxy (Nginx/Traefik) under least privilege.
- Mandatory HTTP security headers (exact values in `security.md`): CSP, HSTS,
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`.
- Remove headers that reveal the stack (`Server`, `X-Powered-By`, versions).
- `DEBUG=False` enforced in staging/production; Swagger/ReDoc not exposed in
  production without authentication.

## Data

- Persistence: PostgreSQL with the PostGIS extension (SQLite for packaged
  development/testing environments).
- Real time/cache: Redis (Pub/Sub for live telemetry + in-memory state).

## Secrets (A04)

- Injected at runtime through Docker Secrets or HashiCorp Vault.
- Never in images, source code or repository `.env` files (`.env` is
  git-ignored).

## Image dependencies (A03)

- Pin exact version + SHA-256 hash.
- SCA scan (`Trivy` for images) in CI; block CVEs with CVSS ≥ 7.0.
- React console (ADR-0004): multi-stage build. A Node stage runs `npm ci` and
  `vite build`; the final stage serves only the static `dist/` output from a
  non-root web server image (UID 10001) with the security headers. No Node
  runtime, source or `node_modules` in the final image.

## References

- OWASP Top 10 (2025) matrix: `security.md`.
- SCA/CI gates: `testing-quality-gates.md`.
