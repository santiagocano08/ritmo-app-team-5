# ADR-0005: Kubernetes (kind), Helm and Argo CD Next to docker-compose

- Status: Proposed
- Date: 2026-11-21
- Decided by: pending (Turn Owner, Architect; the team decides whether this needs a
  `constitutional-amendment` PR)
- Turn: Turn 1 — Data and Minimal Loop (active)
- Addresses: Principle III (ingestion isolated from the web), Principle V (automated gates in CI),
  Gate 2 (tests and coverage > 80 % on every PR)

## Context

The constitution's stack names Docker and `docker-compose` with at least three services. The
project has no CI pipeline yet, so Gate 2 is checked by hand. The team also wants a delivery path
that builds, tests and publishes images and deploys them declaratively, using Kubernetes, Helm
and Argo CD.

## Decision

1. **`docker-compose` stays** the local development stack and the test harness. Nothing is removed.
2. **GitHub Actions** runs on every PR and push: the Python suite through compose (the documented
   CI-ready command), the web lint/type/test/build, `helm lint`, and a smoke deploy in kind. On
   push to `main` it publishes both images to GHCR tagged with the commit SHA.
3. **Kubernetes target: kind**, packaged as one Helm chart (`deploy/helm/pulsoflota`). Mapping:
   `db` StatefulSet; `ingestion` Job (the simulator ends); `refresh` Deployment with exactly one
   replica; `api` and `web` Deployments; Services for db, api and web.
4. **GitOps with Argo CD**: an Application tracks `deploy/helm/pulsoflota` on `main` with
   `values-kind.yaml`. CI writes the new image tag into that file; Argo CD syncs with `prune` and
   `selfHeal`.
5. **Probes**: the `refresh` freshness check is a readiness probe only. As liveness it would
   restart the pod every time the data feed stops, which the design treats as a signal, not a
   process failure.

## Consequences

- No application code changes: configuration already comes from environment variables and the
  images already run as UID 10001.
- `db/init/*.sql` is duplicated inside the chart (Helm cannot read outside it; Argo CD rejects
  out-of-bounds symlinks). CI fails if the copies differ.
- The database password reaches pods through a Kubernetes Secret created by hand. External secret
  management (Docker Secrets / Vault) stays deferred to turn 2, as in `docs/turns-ritmo.md`.
- The repo is private: Argo CD needs a read-only deploy key and kind needs a `read:packages` token,
  both created out of band.
- The bump job pushes to `main`; branch protection must allow `github-actions[bot]`.
- Deferred to later turns: pinning actions and base images by SHA, SAST/SCA as blocking gates,
  Ingress/TLS, Prometheus/Grafana.
