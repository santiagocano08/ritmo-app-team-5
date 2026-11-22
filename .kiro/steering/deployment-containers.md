---
inclusion: fileMatch
fileMatchPattern: ["**/Dockerfile", "**/Dockerfile.*", "**/docker-compose*.yml", "**/docker-compose*.yaml", "**/.dockerignore"]
---

# Deployment and Containers — PulsoFlota

> Target system. Check `docs/turns-ritmo.md` for what the active turn requires.

## `docker-compose` services

At least four services:

1. **`ingestion-service`** — synchronous ingestion of IoT telemetry and mocked
   traffic sources.
2. **`pulsoflota-backend`** — FastAPI + Pydantic V2 (`src/backend/`): REST +
   WebSocket API, metric calculation and all business logic/authorization.
   Database access is psycopg 3 with parameterized SQL only (no ORM).
3. **`pulsoflota-frontend`** — React 19 + TypeScript + Vite + Tailwind
   (`src/frontend/`), built to static assets and served behind the reverse
   proxy. Consumes the backend API; never decides access control.
4. **`database-redis`** — persistence and event cache/pub-sub infrastructure.

## Deployment target and evolution

- **MVP deployment is Docker + `docker-compose`** with the four services above;
  this is the current target. Releases are versioned, immutable image tags
  (semantic tag + commit SHA); rollback is a redeploy of the previous image.
- **GHCR image publishing** by the unified CI/CD pipeline is an **intermediate
  target**: it may precede any orchestrator and is not an MVP blocker. The
  DevSecOps gates (SAST + SCA + image scan) block publishing any image with a
  High/Critical finding (CVSS ≥ 7.0).
- **Kubernetes + Helm + GitOps/Argo CD** is documented as a **future / evolution
  production target** for a later spiral turn; it is never built or required for
  the MVP (adopt turn by turn, `docs/turns-ritmo.md`). See ADR-0005.

## Isolation

- `ingestion-service` runs in a container **fully isolated** from the
  `pulsoflota-backend`, so interface failures do not affect data capture.

## Hardening (A02)

- **Non-root** execution: `USER appuser` with UID `10001` in every Python
  container (ingestion and backend), and in the frontend's static-serving
  image. Least privilege.
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
- SCA/CI gates and GHCR publish policy: `testing-quality-gates.md`.
- Unified CI/CD, GHCR and future K8s target: ADR-0005.
