# ---------------------------------------------------------------------------
# pulsoflota-web — React + Vite + Tailwind console (ADR-0004)
#   build: Node installs from package-lock.json (npm ci) and runs `vite build`
#   final: unprivileged nginx serves only the static dist/ output
# No Node runtime, source or node_modules in the final image. Non-root UID 10001.
# Image digests are not pinned yet (SCA/pinning of images is a turn-2 norm).
# ---------------------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app
# npm 10 crashes resolving this dependency tree; use the version declared in packageManager.
RUN npm install -g npm@11.21.3
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginxinc/nginx-unprivileged:1.29-alpine AS final
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
USER 10001:0
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD wget -q --spider http://127.0.0.1:8080/ || exit 1
