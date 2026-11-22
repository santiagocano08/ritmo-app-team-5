# Quickstart & Validation: Dispatcher Console — Fleet State and Headway

How to run and validate the US-06 console. This is a run/validation guide; implementation code, component bodies and full test suites belong to `/speckit.tasks` and the Build stage. Paths are repository-relative.

## Prerequisites

- Node 20 LTS and npm.
- Dependencies installed reproducibly: `cd src/frontend && npm ci` (uses the committed `package-lock.json`).
- For live validation: the US-05 backend (feature 004) running and reachable, serving `GET /api/v1/corridor/C6-008/now` and `.../source-status`. For mock validation: none — the fixtures drive everything.

References: data shapes in [data-model.md](./data-model.md); consumer interface and fixtures in [contracts/README.md](./contracts/README.md); authoritative visual design in `tickets/US-06-frontend-home/US-06-escritorio-estilos.md` and `mockup-base-escritorio.png`.

## 0 — Generate types from the read contracts (Contract-First)

```bash
cd src/frontend
npm run gen:types   # generates src/api/generated/ from contracts/read/*.schema.json v1.0.0
```

Expected: typed `CorridorNow` and `SourceStatus` under `src/frontend/src/api/generated/`, committed. `tsc --noEmit` passes.

## 1 — Run in mock mode (no backend)

```bash
cd src/frontend
npm run dev:mock    # serves contracts/read/fixtures/* via msw
```

Open the printed URL and step through the scenarios (switch the active fixture in the mock controls):

| Scenario | Expected console behavior | Covers |
|---|---|---|
| `normal` | 5 buses leader-first (B-105 first), each with state/position/headway vs planned; all "Live"; live status indicator, **no banner**; summary 5 / 0 / 0. | US1, FR-001/002/003/006/007, SC-001 |
| `c1_bunching` | Bunched buses visually **and textually** distinguished; summary `n_bunched` matches. | US2, FR-004/005, SC-003 |
| `c2_gap` | Gap buses distinguished; `n_gaps` matches. | US2, FR-004/005, SC-003 |
| `c5_breakdown` | Broken-down bus shown in that state, distinguishable; no headway comparison for it (`headway_ahead_s` null); counts consistent. | Edge cases |
| `d1_source_outage` | Status indicator `estimated` with explanatory banner; the stale bus labeled "Estimated"; **no alert raised**. | US3, FR-008, SC-004/005 |

## 2 — No-data and empty states

Point the mock at the no-data envelope (or empty gold on the live backend):

```bash
# live backend, fresh DB:
curl -s http://localhost:8000/api/v1/corridor/C6-008/now   # → 200 {"status":"no_data","corridor_id":"C6-008"}
```

Expected: no-data status indicator, banner telling the dispatcher to rely on the day's plan, informative empty state with zero counts (not a blank/broken list). Covers FR-013, US3 scenario 3, SC-004.

## 3 — Auto-refresh cadence (~5 s)

With mock or live data, change the served snapshot (edit the mock fixture / advance the simulator) and wait one cadence without reloading.

Expected: within ~5 s the fleet, counts and status reflect the new snapshot; prior values are replaced (FR-009/FR-014, SC-002). No manual reload, no `useEffect` fetching (all polling via TanStack Query `refetchInterval`).

## 4 — Stale data / backend unreachable (non-blocking)

With the console running against the live backend, stop the backend (or block the port) for one or two cadences, then restore it.

Expected while down: a non-blocking **stale-data** indicator appears, the **last known snapshot stays visible**, no crash, no blank view; the console keeps retrying each cadence. On restore: the view updates on the next successful poll and the stale indicator clears. Covers FR-010, SC-006. Note the stale indicator is distinct from the `estimated`/`no_data` data-trust banner (they can appear independently).

## 5 — Navigation shell (match the styling reference)

Compare against `tickets/US-06-frontend-home/US-06-escritorio-estilos.md` and `mockup-base-escritorio.png`.

Expected on load: 248 px dark-navy (`#14213D`) sidebar with the PulsoFlota logo (amber pulse icon), the dispatcher nav items (Central en vivo / Alertas / Plan del día) with the active one marked white-on-navy (`aria-current="page"`), and the bottom user footer (avatar "UD", "Usuario demo" / "Despachador", "Cerrar sesión"). A 68 px white header shows, left, the corridor selector ("CORREDOR" label + "[Corredor piloto] · Estación → casa" + chevron) and, right, the status badge (`role="status"` pill, colored per source status) and the clock (right-most). Identity/role and the logout link are display only — no access-control behavior. Spacing, radii (8/12/999 px), fonts (Inter + Space Grotesk) and the status palette match the reference. Covers FR-011, US3 scenario 4.

Also confirm the three data-state variants from the reference §8:
- **live**: green badge "En vivo" + "Último evento …", no banner.
- **estimated**: amber badge "Estimado" + "Una fuente no responde desde …", banner shown.
- **no_data**: red badge "Sin datos" + "Sin eventos desde …", banner shown.

## 6 — Accessibility: text, not color alone

For every state and quality condition, confirm a text label (and ARIA label) is present alongside any color. Validate at least one bunched, one gap, one broken-down and one estimated case, plus each source status. Covers FR-012, SC-007.

## 7 — Quality gates (frontend-ci, Gate 1 & Gate 2)

```bash
cd src/frontend
npm run lint          # ESLint — Gate 1 (0 Critical/High)
npx tsc --noEmit      # strict types, no any
npm run test:coverage # Vitest + Testing Library, coverage > 80 %
npm run build         # Vite production build
npm audit             # JS SCA — Gate 2
```

Pass criteria: ESLint clean, `tsc --noEmit` clean, Vitest green with coverage > 80 % on console code, Vite build succeeds, no High/Critical dependency advisory. The component tests reuse the `contracts/read/fixtures/*` scenarios above.

## Acceptance mapping

| Success criterion | Validated in |
|---|---|
| SC-001 fleet visible within 5 s, leader-first with state/headway | §1 `normal` |
| SC-002 new snapshot reflected within one cadence, no reload | §3 |
| SC-003 bunched/gap identified; summary counts exact | §1 `c1_bunching`, `c2_gap` |
| SC-004 correct indicator per status; banner only for estimated/no-data | §1 `d1_source_outage`, §2 |
| SC-005 estimated labeled, never alerts | §1 `d1_source_outage` |
| SC-006 backend unreachable keeps last snapshot, auto-recovers | §4 |
| SC-007 state/quality conveyed in text, not color alone | §6 |

## Out of scope for this validation (deferred — evolution)

Real-time push / sub-2 s refresh; geographic map; login/RBAC/auth; recommendations and approve/discard; multi-corridor and second direction; historical/manager views. See `docs/turns-ritmo.md` §3.3.
