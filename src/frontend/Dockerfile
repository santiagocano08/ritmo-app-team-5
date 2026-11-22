# ---------------------------------------------------------------------------
# PulsoFlota — dispatcher console (frontend) image.
#
# Multi-stage build (ADR-0004, research R3):
#   build : Node stage runs `npm ci` + `npm run build` to produce dist/.
#   runtime: Nginx serves only the built dist/ assets and forwards /api/v1 to
#            the api service. No Node runtime, source or node_modules ship.
#
# Base images pinned to exact patch tags for reproducible builds (research R3,
# matching the backend Dockerfile's python:3.12.16-slim pin). Loose tags like
# `nginx:latest` are rejected. Pins: node:22.11.0-alpine (build),
# alpine:3.21.3 runtime with Alpine's own nginx + headers-more (ABI-matched).
# ---------------------------------------------------------------------------

# --- build stage: compile the SPA to static assets -------------------------
# Build context is the repository root (see docker-compose.yml) so the runtime
# stage can also copy deploy/frontend/. Frontend paths are under src/frontend/.
FROM node:22.11.0-alpine AS build

WORKDIR /app

# Build-time inputs: full frontend source + config (node_modules/dist excluded
# via .dockerignore so the host's platform-specific deps never leak in).
COPY src/frontend/ ./

# Install dependencies from the committed lockfile for reproducibility, resolving
# the platform-native binaries for this build image. Done after the source COPY
# so nothing overwrites the freshly installed node_modules.
RUN npm ci

# The dev-only mocks and tests type-check against the committed read-contract
# fixtures via a repo-root-relative import (../../../../contracts/read/fixtures).
# tsc --noEmit (the build's type-check step) needs them present. They are NOT
# bundled into the SPA and never reach the runtime stage (only dist/ is copied),
# so no mock fixture is in the shipped request path (FR-003).
COPY contracts/read/fixtures /contracts/read/fixtures

# `npm run build` = tsc --noEmit && vite build. Emits dist/ (hashed assets).
RUN npm run build

# --- runtime stage: Nginx serving static assets as non-root UID 10001 ------
# Base on Alpine and install nginx + the headers-more module from the SAME Alpine
# repo so they are ABI-compatible (the docker-official nginx image and Alpine's
# distro module are not). headers-more supplies `more_clear_headers`, which stock
# Nginx lacks, to strip the `Server`/`X-Powered-By` banners (FR-012, SC-005).
# Alpine pinned to an exact patch for reproducibility (research R3 exact pin).
FROM alpine:3.21.3 AS runtime

RUN apk add --no-cache nginx nginx-mod-http-headers-more

# Reverse-proxy config: serve dist/ + forward /api/v1, security headers (T010/T019/T020).
COPY deploy/frontend/nginx.conf /etc/nginx/nginx.conf

# Only the built static assets enter the final image (FR-009): no Node runtime,
# no source, no node_modules.
COPY --from=build /app/dist /usr/share/nginx/html

# Run as non-root UID 10001 (FR-010, security.md A02). Create UID/GID 10001 to
# match the project baseline and own the writable paths (temp dirs, served assets).
RUN set -eux; \
    addgroup -g 10001 -S appgroup; \
    adduser -u 10001 -G appgroup -S -H -s /sbin/nologin appuser; \
    mkdir -p /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi \
             /tmp/nginx/uwsgi /tmp/nginx/scgi; \
    chown -R 10001:10001 /tmp/nginx /usr/share/nginx/html /var/lib/nginx /var/log/nginx

USER 10001

EXPOSE 8080

# nginx -t is validated in CI/build via `docker build`; the default CMD runs the proxy.
CMD ["nginx", "-g", "daemon off;"]
