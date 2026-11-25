# Quickstart & Validation: Sidebar SVG Icons

Feature: `008-frontend-sidebar-svg-icons` · Branch `feature/US-11-frontend-sidebar-svg-icons`

This guide validates the feature end to end. It is a run/validation guide, not
implementation code — the icon markup belongs in the implementation phase
(`tasks.md`).

## Prerequisites

- Node toolchain for the frontend service (`src/frontend/`), dependencies
  installed with `npm ci` (no new dependency is added by this feature).
- Working directory: `src/frontend/`.

## Scope under validation

- Single source file changed: `src/frontend/src/components/shell/Sidebar.tsx`.
- Test files with added assertions: `src/frontend/tests/shell/Sidebar.test.tsx`,
  `src/frontend/tests/a11y/TextNotColor.test.tsx` (the latter must simply stay
  green). See [data-model.md](./data-model.md) and [research.md](./research.md).

## Automated checks (frontend-ci gate — must all pass)

Run from `src/frontend/`:

```bash
npm run lint      # eslint . --ext .ts,.tsx --max-warnings 0 (no-explicit-any = error)
npm run build     # tsc --noEmit (strict) && vite build
npm run test:coverage   # vitest run --coverage; thresholds >80% lines/functions/branches/statements
```

Expected: lint 0 warnings/errors, type check clean, all tests pass, coverage
stays above 80 % on every metric, Vite build succeeds (SC-005).

## Test assertions to add (acceptance mapping)

In `tests/shell/Sidebar.test.tsx`, for `activeSection="live_central"`:

1. Each of the three nav links (*Central en vivo*, *Alertas*, *Plan del día*)
   and the *Cerrar sesión* link contains exactly one `<svg>` with
   `aria-hidden="true"`. → FR-002, FR-003, FR-005; SC-001, SC-004.
2. The sidebar contains no residual glyph from `⬳ ◉ ✚ ▦ ⇥`
   (assert `container.textContent` excludes each). → FR-006; SC-001.
3. The logo renders an `<svg>` (pulse) marked `aria-hidden="true"`. → FR-001.
4. Existing assertions (labels present, active entry has `aria-current="page"`)
   still pass. → FR-007, FR-008.

`tests/a11y/TextNotColor.test.tsx` is left unchanged and must stay green
(`aria-current="page"` on the active section). → SC-003.

## Manual validation scenarios

| # | Scenario | Steps | Expected | Spec ref |
|---|---|---|---|---|
| 1 | Consistent icons | Run `npm run dev`, open the console, inspect the sidebar | Logo + 3 menu icons + logout icon render as crisp SVG; no glyph placeholders | US1 AS-1,2; SC-001 |
| 2 | Cross-machine consistency | Open the built app on two environments with different fonts | Sidebar icons look identical on both | US1 AS-3; SC-002 |
| 3 | Active state intact | Observe the active entry (*Central en vivo*) | Active background/contrast correct; icon legible via `currentColor` | Edge case; FR-004, FR-008 |
| 4 | Decorative to AT | Inspect each icon node | Every `<svg>` has `aria-hidden="true"`; labels read unchanged | US2 AS-1,2,3; SC-003, SC-004 |
| 5 | Labels unchanged | Read all sidebar labels | *Central en vivo*, *Alertas*, *Plan del día*, *Cerrar sesión* exactly as before | FR-007 |

## Design reference

Icon shapes, sizes and the logo colour: §4.1–4.3 of
`tickets/US-06-frontend-home/US-06-escritorio-estilos.md` (pulse logo 26×26
`#FBBF24`; menu items 20×20 `currentColor`: pulse/bell/calendar; exit 18×18;
stroke width 2, round caps/joins). Do not invent new tokens.

## Done when

- All automated checks above pass (SC-005).
- New assertions prove one decorative `<svg>` per entry/logout and no residual
  glyph (SC-001, SC-004, SC-006/FR-006).
- Manual scenarios 1–5 confirmed.
