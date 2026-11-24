# feat(frontend): SVG icons in the sidebar per the style spec (US-11)

> RITMO Turn 1 — "Data and minimal loop". Lane: Adaptive. Risk level: 1.
> Governed by `docs/turns-ritmo.md` §3 and the constitution.
> Tracked as GitHub issue #53 (label `demo`).

## Context and problem

The sidebar uses text glyphs as icons (`⬳`, `◉`, `✚`, `▦`, `⇥`), which render
differently on each machine. The style spec (§4.1, §4.2, §4.3) defines stroke
icons.

## User story

As a dispatcher, I want clear, consistent sidebar icons, so the menu looks the
same on every computer and matches the design.

## Scope (Turn 1)

- [ ] Logo: pulse icon, path `M2 12h4l3-8 4 16 3-8h6`, 26 × 26 px, color
      `#FBBF24`, stroke 2, round caps and joins.
- [ ] Menu items: 20 × 20 px inline SVG, stroke 2, `stroke: currentColor`:
      *Central en vivo* (pulse), *Alertas* (bell), *Plan del día* (calendar).
- [ ] *Cerrar sesión*: exit icon, 18 × 18 px.
- [ ] All icons `aria-hidden="true"`. Inline SVG components; no new icon
      dependency.

## Out of scope (deferred / evolution)

- Icons in the fleet list or the header chevron.

## Acceptance criteria

- **Given** the sidebar renders, **when** inspected, **then** each menu item and
  the logout link contain one `<svg aria-hidden="true">` and no text glyph icons
  remain.
- **Given** the existing accessibility test (`tests/a11y`), **when** it runs,
  **then** it still passes and the item labels are unchanged.

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

- Branch: `feature/US-11-frontend-sidebar-svg-icons`.
- Flow: Plan → Specify → Build → Verify → Review. One story on its own branch.
