# Quickstart: Tab Title Data State

Node is not on the host; run in the project's Node container (bounded to 120 s, no `-e TZ`):

```sh
docker run --rm -v "$PWD":/repo -w /repo/src/frontend node:22.11.0-alpine sh -c './node_modules/.bin/vitest run && ./node_modules/.bin/eslint src tests --ext .ts,.tsx --max-warnings 0 && ./node_modules/.bin/tsc --noEmit'
```

## Validation scenarios

1. Render `App` with source status `live`: `document.title` is `PulsoFlota · En vivo` (FR-001).
2. Change the status to `estimated`: title becomes `PulsoFlota · Estimado` (FR-002, FR-005).
3. Status `no_data`, or no response yet: title is `PulsoFlota · Sin datos` (FR-003).
4. In each case the title label equals the text of the header `StatusBadge` (FR-004).
5. `src/frontend/index.html` still contains `PulsoFlota · Central en vivo` (FR-006).

Expected: Vitest, ESLint and `tsc --noEmit` all pass. Tests do not depend on the host zone.
