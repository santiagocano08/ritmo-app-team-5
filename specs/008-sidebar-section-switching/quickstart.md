# Quickstart / Validation: Sidebar Section Switching (US-10)

## Prerequisites

- Node version used by `frontend-ci`, dependencies installed with `npm ci` in `src/frontend/`.
- Branch `feature/US-10` checked out (US-06 console shell present).

## Automated checks (the `frontend-ci` gate)

Run from `src/frontend/`:

```bash
npm run lint            # ESLint, 0 warnings
npx tsc --noEmit        # strict types
npm run test:coverage   # Vitest; thresholds 80 % lines/functions/branches/statements
npm run build           # tsc + Vite build
```

Expected: all four pass. The new and updated tests are:

| Test file | Proves |
|-----------|--------|
| `tests/shell/Sidebar.test.tsx` | contract S1–S6 (`contracts/ui-sections.md`) |
| `tests/status/SectionPlaceholder.test.tsx` | P1–P2 |
| `tests/shell/SectionSwitching.test.tsx` | A1–A6, spec US1 scenarios 1–3, US2 scenarios 1–2, SC-001, SC-003 |

Existing suites (`StaleRecovery`, `NoData`, fleet and summary tests) must stay green
unchanged: they render `App` on the default section.

## Manual validation (mock mode, no backend needed)

```bash
npm run dev:mock        # Vite with MSW fixtures
```

Open the printed URL and check:

1. **First load**: *Central en vivo* highlighted (white background, dark text), `h1`
   «Central en vivo», fleet list and summary visible.
2. Click **Alertas**: only *Alertas* highlighted, `h1` «Alertas», dashed placeholder with
   «Contenido de la sección: se define en las próximas historias.» centered and filling the
   remaining height. Header badge, clock and banner still visible. URL has no new hash.
3. Click **Plan del día**: same checks with «Plan del día».
4. Click **Plan del día** again: nothing resets or blinks.
5. Click **Central en vivo**: fleet list and summary return; in DevTools → Network,
   `/api/v1/corridor/.../now` requests keep arriving every ~5 s with no page reload.
6. **Keyboard**: Tab to each sidebar item, press Enter; result matches the click.
7. **Screen reader / DevTools**: exactly one sidebar link has `aria-current="page"`.

## Visual review (SC-004)

Compare step 2 with mockup `docs/designs/mockups/escritorio/UXUI03-escritorio.png` and style spec
`tickets/US-06-frontend-home/US-06-escritorio-estilos.md` §7: border 2 px dashed `#A3ACB9`,
radius 12 px, padding 24 px, text `#4A5361` 15 px, centered on both axes.
