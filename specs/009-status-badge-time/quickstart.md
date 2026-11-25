# Quickstart: Validation

Prerequisite: Docker; Node is not on the host. Do not run `npm install`/`npm ci`.

```sh
docker run --rm -v "$PWD":/repo -w /repo/src/frontend node:22.11.0-alpine sh -c \
 './node_modules/.bin/vitest run --coverage && ./node_modules/.bin/eslint src tests --ext .ts,.tsx --max-warnings 0 && ./node_modules/.bin/tsc --noEmit'
```

Run without `-e TZ`. Expected: all pass, coverage ≥ 80 %.

Scenarios (see [spec.md](spec.md)):
1. `live`, `2026-11-24T22:42:08Z` → `Último evento 17:42:08`.
2. `estimated`, two sources down (17:39, 17:41 local) → `Una fuente no responde desde 17:39`; no extra alert.
3. `no_data` → `Sin eventos del corredor`.
4. Edge: `estimated` with no usable `since` → generic text, no error; single-digit values padded.

Time-zone proof: tests pass on a host in any zone because the zone is pinned in `src/frontend/vite.config.ts` (research D2). Build check (`vite build`) can be added with the same container.
