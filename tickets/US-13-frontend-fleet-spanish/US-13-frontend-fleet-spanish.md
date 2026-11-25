# feat(frontend): fleet list and summary in Spanish (US-13)

> RITMO Turn 1 — "Data and minimal loop". Lane: Adaptive. Risk level: 1.
> Governed by `docs/turns-ritmo.md` §3 and the constitution.
> Tracked as GitHub issue #55 (label `demo`).

## Context and problem

The rest of the console is in Spanish, but the fleet list and the corridor
summary are in English: *Leader*, *Bunched*, *Gap*, *Broken down*,
*Live / Estimated*, *In service*, `Between P03 and P04 · 820 m`,
`420 s vs 420 s planned (+0 s on plan)`. The empty state already uses Spanish
terms (*En servicio*, *Agrupados*, *Rezagados*).

## User story

As a dispatcher, I want the fleet list and summary in Spanish, so the whole
console reads in one language.

## Scope (Turn 1)

- [ ] `StateTag`: Líder, Regular, Agrupado, Rezagado, Varado.
- [ ] `QualityTag`: En vivo, Estimado.
- [ ] `CorridorSummary`: En servicio, Agrupados, Rezagados (same words as
      `EmptyState`); `aria-label` *Resumen del corredor*.
- [ ] `BusRow` position: `Entre P03 y P04 · 820 m`.
- [ ] `HeadwayCompare`: `420 s vs 420 s del plan` plus `(+60 s sobre el plan)`,
      `(−60 s bajo el plan)` or `(en el plan)`.
- [ ] Update the affected tests; keep the `data-*` attributes and test ids
      unchanged.

## Out of scope (deferred / evolution)

- Units or number formats (seconds and metres stay as they are).

## Note for the frontend owner

US-06's acceptance criteria said an estimated bus shows "Estimated". This story
changes it to "Estimado", to match the badge and banner that already use
Spanish.

## Acceptance criteria

- **Given** a bunched bus with estimated data, **when** its row renders, **then**
  it shows *Agrupado* and *Estimado*, and no English UI text remains in the fleet
  list or summary.
- **Given** a bus 60 s over plan, **when** its headway renders, **then** it reads
  `… del plan (+60 s sobre el plan)`.

## Constraints

- Frontend only (`src/frontend/`). No backend, contract (`contracts/`) or
  generated-type changes.
- Timebox: small enough to run in Kiro in about 5 minutes (one or two components
  plus their tests).

## Gates to pass

- `frontend-ci` stays green: ESLint, `tsc --noEmit`, Vitest with coverage
  **> 80 %**, Vite build.

## Design connection

- **UXUI-04 — Ver el corredor en vivo:** reference for the live corridor
  summary, fleet list, and bus-status labels this ticket translates. See the
  [story summary](../../docs/designs/resumen-historias.md),
  [desktop mockup](../../docs/designs/mockups/escritorio/UXUI04-escritorio.png),
  [mobile mockup](../../docs/designs/mockups/celular/UXUI04-celular.png), and
  [global design styles](../../docs/designs/global-desing-styles.md).

## Origin

Gap found by comparing the shipped console (US-06, PR #35) with the style spec
`tickets/US-06-frontend-home/US-06-escritorio-estilos.md`. Part of the Kiro demo
set (label `demo`).

## RITMO workflow

- Branch: `feature/US-13-frontend-fleet-spanish`.
- Flow: Plan → Specify → Build → Verify → Review. One story on its own branch.
