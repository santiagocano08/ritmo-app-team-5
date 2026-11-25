# feat(frontend): readable time and 'since' detail in the status badge (US-09)

> RITMO Turn 1 — "Data and minimal loop". Lane: Adaptive. Risk level: 1.
> Governed by `docs/turns-ritmo.md` §3 and the constitution.
> Tracked as GitHub issue #51 (label `demo`).

## Context and problem

The status badge in the header shows the raw ISO timestamp
(`Último evento 2026-11-24T17:42:08Z`) and, when a bus stops reporting, it does
not say since when. The style spec (§8) asks for a readable time and a "since"
detail.

## User story

As a dispatcher, I want the status badge to show a readable time and, when a
source is down, since when, so I can judge how fresh the data is at a glance.

## Scope (Turn 1)

- [ ] `live`: detail reads `Último evento HH:MM:SS` (24 h, browser local time)
      from `source_status.as_of_ts`.
- [ ] `estimated`: detail reads `Una fuente no responde desde HH:MM`, using the
      earliest `sources_down[].since`.
- [ ] `no_data`: keep `Sin eventos del corredor` (the contract has no "since"
      for this state: no events were ever received).
- [ ] Move the formatting out of `App.tsx` into a small pure helper with unit
      tests.

## Out of scope (deferred / evolution)

- The header clock and the alert banner text (unchanged).

## Acceptance criteria

- **Given** `status = live` and `as_of_ts = 2026-11-24T22:42:08Z` in a UTC-5
  browser, **when** the badge renders, **then** it reads `Último evento 17:42:08`.
- **Given** `status = estimated` with two buses down since 17:39 and 17:41 local,
  **when** the badge renders, **then** it reads `Una fuente no responde desde 17:39`
  and **no** extra alert is raised (D1).
- **Given** `status = no_data`, **when** the badge renders, **then** it reads
  `Sin eventos del corredor`.

## Constraints

- Frontend only (`src/frontend/`). No backend, contract (`contracts/`) or
  generated-type changes.
- Timebox: small enough to run in Kiro in about 5 minutes (one or two components
  plus their tests).

## Gates to pass

- `frontend-ci` stays green: ESLint, `tsc --noEmit`, Vitest with coverage
  **> 80 %**, Vite build.

## Design connection

- **UXUI-03 — Navegación principal por rol y estado del dato:** the header's
  data-status badge and its `live`, `estimated`, and `no_data` details are the
  design reference for this ticket. See the [story summary](../../docs/designs/resumen-historias.md),
  [desktop mockup](../../docs/designs/mockups/escritorio/UXUI03-escritorio.png),
  and [global status-badge styles](../../docs/designs/global-desing-styles.md)
  (§5.3). The detailed text variants are in §8 of
  [`US-06-escritorio-estilos.md`](../US-06-frontend-home/US-06-escritorio-estilos.md).

## Origin

Gap found by comparing the shipped console (US-06, PR #35) with the style spec
`tickets/US-06-frontend-home/US-06-escritorio-estilos.md`. Part of the Kiro demo
set (label `demo`).

## RITMO workflow

- Branch: `feature/US-09-frontend-status-badge-time`.
- Flow: Plan → Specify → Build → Verify → Review. One story on its own branch.
