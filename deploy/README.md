# Deploying PulsoFlota on Kubernetes (kind + Helm + Argo CD)

ADR-0005. `docker-compose` stays the local development stack; this folder runs the same services
on Kubernetes. Host ports do not clash with compose, so both can run at the same time.

| Path | What it is |
|---|---|
| `kind/cluster.yaml` | Local cluster. NodePorts mapped to `127.0.0.1:8180` (web) and `127.0.0.1:8100` (api) |
| `helm/pulsoflota/` | The chart. `values.yaml` defaults, `values-kind.yaml` for kind (CI writes its image tags) |
| `helm/pulsoflota/files/db-init/` | Copy of `db/init/*.sql`. Refresh it with `make sync-db-init`; CI fails if it differs |
| `argocd/application.yaml` | The Argo CD Application that keeps the cluster equal to Git |

## How compose maps to Kubernetes

| Compose service | Kubernetes object | Note |
|---|---|---|
| `db` | StatefulSet + Service + PVC; init scripts from a ConfigMap | Init scripts run only on an empty volume, as in compose |
| `ingestion` | Job | The simulator ends. Name = image tag + settings hash, so a change creates a new Job. Re-running is safe (bronze dedup) |
| `refresh` | Deployment, 1 replica, `Recreate` | Single writer of gold snapshots. Freshness check is the **readiness** probe only |
| `api` | Deployment + Service | `/healthz` (DB-free) for readiness and liveness |
| `web` | Deployment + Service | Unprivileged nginx |
| `depends_on` | `wait-for-db` init container | `pg_isready` loop |
| `.env` | Pod env + Secret `pulsoflota-db` | Only `POSTGRES_PASSWORD` is secret |
| `tests` | not deployed | Runs in GitHub Actions |

All app pods run as UID 10001 with a read-only root filesystem, no privilege escalation and no
capabilities.

## 1. Local loop (no registry)

```bash
make kind-up
kubectl create namespace pulsoflota
# Letters and digits only: the password goes inside DATABASE_URL without URL-encoding.
kubectl -n pulsoflota create secret generic pulsoflota-db \
  --from-literal=POSTGRES_PASSWORD="$(openssl rand -hex 16)"
make kind-load kind-deploy
kubectl -n pulsoflota get pods
curl http://127.0.0.1:8100/healthz     # api
open http://127.0.0.1:8180             # console
```

`refresh` turns *not ready* when the simulator finishes and no new data arrives. That is the
freshness signal, not a failure. Run it again with `make kind-deploy` after changing
`ingestion.*` values, or delete the Job and let Helm/Argo recreate it.

## 2. CI/CD (`.github/workflows/ci.yaml`)

- Every PR and push: Python suite through compose (coverage > 80 %), web lint/types/tests/build,
  `helm lint`, and a smoke deploy of the chart in kind.
- Push to `main` or `feature/**`: publish `ghcr.io/santiagocano08/ritmo-app-team-5/pulsoflota-app`
  and `.../pulsoflota-web` tagged with the commit SHA and the branch name
  (`feature/004-devops` → `feature-004-devops`); `latest` only from `main`.
- Push to `main` only: commit the SHA into `values-kind.yaml` (Argo CD deploys it). Feature builds
  are never deployed automatically. To try one in kind:

  ```bash
  helm upgrade --install pf deploy/helm/pulsoflota -n pulsoflota \
    -f deploy/helm/pulsoflota/values-kind.yaml \
    --set image.app.tag=feature-004-devops --set image.web.tag=feature-004-devops \
    --set image.pullPolicy=Always --wait
  ```

Requirements in GitHub (repository settings, not in code):
- **Actions → General → Workflow permissions:** "Read and write" (the bump job pushes a commit).
- If `main` is protected against direct pushes, allow `github-actions[bot]` to bypass, or the bump
  job fails.

## 3. GitOps with Argo CD

The repo and its GHCR packages are private, so the cluster needs two credentials. Create them with
`kubectl`; never commit them.

```bash
make argocd-install

# a) Argo CD reads the repo: add a read-only deploy key in GitHub
#    (Settings → Deploy keys) and register the private key in Argo CD.
ssh-keygen -t ed25519 -N "" -f /tmp/argocd-deploy-key -C argocd-kind
kubectl -n argocd create secret generic repo-pulsoflota \
  --from-literal=type=git \
  --from-literal=url=git@github.com:santiagocano08/ritmo-app-team-5.git \
  --from-file=sshPrivateKey=/tmp/argocd-deploy-key
kubectl -n argocd label secret repo-pulsoflota argocd.argoproj.io/secret-type=repository

# b) kind pulls from GHCR: a classic personal access token with only `read:packages`.
kubectl -n pulsoflota create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io --docker-username=<github-user> --docker-password=<token>

# c) If the chart was installed by hand before, remove that release so Argo CD owns it.
helm uninstall pf -n pulsoflota    # keeps the namespace and its Secrets

kubectl apply -f deploy/argocd/application.yaml
kubectl -n argocd get application pulsoflota -w
```

Argo CD UI:

```bash
kubectl -n argocd port-forward svc/argocd-server 8443:443
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d
# https://localhost:8443  user: admin
```

The Application follows `main`. Until `deploy/` is merged into `main`, Argo CD finds no chart there;
to try it from a branch, set `spec.source.targetRevision` to that branch (then CI does not bump tags
there, so `values-kind.yaml` keeps `latest`).

The loop: merge to `main` → CI tests and publishes images → CI commits the new tag →
Argo CD sees the commit (polls every ~3 min) → syncs the cluster.
