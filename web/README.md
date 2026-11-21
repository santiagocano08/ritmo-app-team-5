# pulsoflota-web — dispatcher console

React + Vite + Tailwind CSS single-page application (ADR-0004). It talks to the backend only
through its REST/WebSocket API; authorization stays in the backend.

Use npm 11 (`packageManager` in `package.json`); npm 10.9 crashes resolving this dependency tree.

| Command | What it does |
|---|---|
| `npm ci` | Install exactly what `package-lock.json` pins |
| `npm run dev` | Dev server on http://localhost:5173 |
| `npm run lint` | ESLint (Gate 1) |
| `npm run typecheck` | TypeScript check |
| `npm run coverage` | Vitest with the > 80 % threshold (Gate 2) |
| `npm run build` | Static build into `dist/` |

Container: `docker compose up -d --build web`, then http://localhost:8080 (`WEB_PORT`).
