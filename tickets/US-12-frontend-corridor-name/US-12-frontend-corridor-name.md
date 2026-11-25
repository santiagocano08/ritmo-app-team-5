# feat(frontend): show the real corridor name in the header (US-12)

> RITMO Turn 1 — "Data and minimal loop". Lane: Adaptive. Risk level: 1.
> Governed by `docs/turns-ritmo.md` §3 and the constitution.
> Tracked as GitHub issue #54 (label `demo`).

## Context and problem

Under *CORREDOR*, the header shows the mockup's sample text
`[Corredor piloto] · Estación → casa`. The real corridor data already arrives in
`corridor_now` (`corridor_id`, `direction`), but it is not displayed.

## User story

As a dispatcher, I want the header to name the corridor I am watching, taken
from the live data, so I never read sample text as real information.

## Scope (Turn 1)

- [ ] `CorridorSelector` receives the corridor from the latest snapshot and
      shows `C6-008 · Estación → barrio` (direction 1 = station to neighbourhood,
      per the contract).
- [ ] Before the first snapshot arrives, show the configured corridor id
      (`C6-008`) without the direction.
- [ ] Keep the existing label, button and chevron layout.

## Out of scope (deferred / evolution)

- Actually switching corridors (Turn 1 has one corridor; the button stays inert).

## Acceptance criteria

- **Given** a snapshot with `corridor_id = C6-008` and `direction = 1`, **when**
  the header renders, **then** it reads `C6-008 · Estación → barrio` and the text
  `[Corredor piloto]` no longer appears anywhere in the app.
- **Given** no snapshot yet, **when** the header renders, **then** it reads
  `C6-008`.

## Constraints

- Frontend only (`src/frontend/`). No backend, contract (`contracts/`) or
  generated-type changes.
- Timebox: small enough to run in Kiro in about 5 minutes (one or two components
  plus their tests).

## Gates to pass

- `frontend-ci` stays green: ESLint, `tsc --noEmit`, Vitest with coverage
  **> 80 %**, Vite build.

## Design connection

- **UXUI-03 — Navegación principal por rol y estado del dato:** reference for
  the corridor selector in the shared header and its label/button/chevron
  layout. See the [story summary](../../docs/designs/resumen-historias.md),
  [desktop mockup](../../docs/designs/mockups/escritorio/UXUI03-escritorio.png),
  and section 5 of
  [`US-06-escritorio-estilos.md`](../US-06-frontend-home/US-06-escritorio-estilos.md).

## Origin

Gap found by comparing the shipped console (US-06, PR #35) with the style spec
`tickets/US-06-frontend-home/US-06-escritorio-estilos.md`. Part of the Kiro demo
set (label `demo`).

## RITMO workflow

- Branch: `feature/US-12-frontend-corridor-name`.
- Flow: Plan → Specify → Build → Verify → Review. One story on its own branch.
