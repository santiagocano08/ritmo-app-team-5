# feat(frontend): sidebar items switch sections with a placeholder (US-10)

> RITMO Turn 1 — "Data and minimal loop". Lane: Adaptive. Risk level: 1.
> Governed by `docs/turns-ritmo.md` §3 and the constitution.
> Tracked as GitHub issue #52 (label `demo`).

## Context and problem

The sidebar items *Alertas* and *Plan del día* are links that do nothing: the
active item and the page title are fixed to *Central en vivo*. The style spec
(§4.2, §7) defines the active state and a placeholder for sections that are not
built yet.

## User story

As a dispatcher, I want the sidebar items to switch sections, so the navigation
behaves like the design even before the sections have content.

## Scope (Turn 1)

- [ ] Clicking a sidebar item makes it active (`aria-current="page"`, active
      styles) and sets the `h1` to its label.
- [ ] *Central en vivo* shows the current fleet view.
- [ ] *Alertas* and *Plan del día* show the placeholder from spec §7: dashed
      border `2px #A3ACB9`, radius 12 px, centered text
      `Contenido de la sección: se define en las próximas historias.`
- [ ] Local UI state (or the existing hash links); no router library.

## Out of scope (deferred / evolution)

- Any real content for *Alertas* or *Plan del día*.
- The *Gestor* role variant (role-based menus belong to Turn 2, RBAC).

## Acceptance criteria

- **Given** the console is open, **when** the dispatcher clicks *Alertas*,
  **then** *Alertas* is the only item with `aria-current="page"`, the `h1` reads
  *Alertas* and the placeholder is shown instead of the fleet.
- **Given** the dispatcher is on *Plan del día*, **when** they click
  *Central en vivo*, **then** the fleet view and summary are back and polling
  continues.

## Constraints

- Frontend only (`src/frontend/`). No backend, contract (`contracts/`) or
  generated-type changes.
- Timebox: small enough to run in Kiro in about 5 minutes (one or two components
  plus their tests).

## Gates to pass

- `frontend-ci` stays green: ESLint, `tsc --noEmit`, Vitest with coverage
  **> 80 %**, Vite build.

## Origin

Gap found by comparing the shipped console (US-06, PR #35) with the style spec
`tickets/US-06-frontend-home/US-06-escritorio-estilos.md`. Part of the Kiro demo
set (label `demo`).

## RITMO workflow

- Branch: `feature/US-10-frontend-sidebar-sections`.
- Flow: Plan → Specify → Build → Verify → Review. One story on its own branch.
