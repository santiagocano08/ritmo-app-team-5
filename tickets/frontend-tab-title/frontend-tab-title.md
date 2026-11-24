# feat(frontend): browser tab title shows the data state

> RITMO Turn 1 — "Data and minimal loop". Lane: Adaptive. Risk level: 1.
> Governed by `docs/turns-ritmo.md` §3 and the constitution.
> Tracked as GitHub issue #56 (label `demo`). In review — PR #58.

## Context and problem

The browser tab always reads `PulsoFlota · Central en vivo`, whatever the data
state. A dispatcher with several tabs open cannot tell from the tab whether the
corridor data is live, estimated or missing.

## User story

As a dispatcher, I want the browser tab title to show the data state, so I can
notice a source outage even when the console is not the active tab.

## Scope (Turn 1)

- [ ] The tab title follows the header badge state: `PulsoFlota · En vivo`,
      `PulsoFlota · Estimado` or `PulsoFlota · Sin datos`.
- [ ] A small pure helper (e.g. `src/lib/tabTitle.ts`) maps the status to the
      title, with unit tests; `App.tsx` applies it with `document.title`.
- [ ] `index.html` keeps its current static title as the initial value.

## Out of scope (deferred / evolution)

- Favicon changes, notifications, sounds.

## Acceptance criteria

- **Given** `source_status.status = live`, **when** the console renders, **then**
  `document.title` is `PulsoFlota · En vivo`.
- **Given** `status = estimated`, **when** the snapshot updates, **then** the
  title becomes `PulsoFlota · Estimado`.
- **Given** no data (`no_data` or no response yet), **when** the console renders,
  **then** the title is `PulsoFlota · Sin datos`.

## Constraints

- Frontend only (`src/frontend/`). No backend, contract or generated-type changes.
- Timebox: the smallest demo story; built to test the full chain end to end
  (chain → verification → PR → CI → merge).

## Gates to pass

- `frontend-ci` stays green: ESLint, `tsc --noEmit`, Vitest with coverage
  **> 80 %**, Vite build.

## Origin

Created on 2026-11-24 as the minimal story to exercise the whole Kiro chain with
PR. Label `demo`.
