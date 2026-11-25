# Quickstart: Validate Tab Title Shows Data State

Node is not on the host; run in the Node container (node_modules already installed). No `-e TZ` is needed.

```bash
docker run --rm -v "$PWD":/repo -w /repo/src/frontend node:22.11.0-alpine sh -c \
  './node_modules/.bin/vitest run && ./node_modules/.bin/eslint src tests --ext .ts,.tsx --max-warnings 0 && ./node_modules/.bin/tsc --noEmit'
```

## Expected outcomes

1. `tests/hooks/useTabTitle.test.tsx` passes: `live` gives `PulsoFlota · En vivo`, `estimated` gives `PulsoFlota · Estimado`, `no_data` gives `PulsoFlota · Sin datos`, and an unrecognized value gives `PulsoFlota · Sin datos`.
2. Rerendering with a new status changes `document.title` without reload (FR-002).
3. Existing `StatusBadge` tests still pass after the export.
4. ESLint and `tsc --noEmit` report no errors; coverage stays above 80 %.
5. `src/frontend/index.html` is unchanged (FR-005).
