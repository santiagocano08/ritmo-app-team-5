# Feature Specification: Real Corridor Name in Header

**Feature Branch**: `feature/US-12-frontend-corridor-name`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "Show the real corridor name in the header's corridor selector instead of the mockup sample text `[Corredor piloto] · Estación → casa`. When a snapshot is present with corridor_id = C6-008 and direction = 1, the header must read `C6-008 · Estación → barrio`. Before the first snapshot arrives, show the configured corridor id `C6-008` without the direction. Keep the existing label, button and chevron layout. The text `[Corredor piloto]` must no longer appear anywhere in the app. Switching corridors is out of scope. Frontend only (src/frontend/); no backend, contract or generated-type changes. (US-12, Turn 1, Adaptive lane.)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the real corridor named in the header (Priority: P1)

As a dispatcher watching the pilot corridor, I want the header's corridor selector to name the corridor from the live data, so I never mistake sample placeholder text for real operational information.

**Why this priority**: This is the entire feature. The header currently shows placeholder text (`[Corredor piloto] · Estación → casa`) that looks like real data but is not. Reading sample text as real information undermines trust in the console and risks a dispatcher acting on fiction. Replacing it with the corridor from the snapshot is the single piece of value this story delivers.

**Independent Test**: Render the header with a snapshot whose `corridor_id` is `C6-008` and `direction` is `1`, and confirm the selector reads `C6-008 · Estación → barrio` and that `[Corredor piloto]` appears nowhere in the rendered application.

**Acceptance Scenarios**:

1. **Given** a snapshot with `corridor_id = C6-008` and `direction = 1`, **When** the header renders, **Then** the corridor selector reads `C6-008 · Estación → barrio` and the text `[Corredor piloto]` no longer appears anywhere in the app.
2. **Given** a snapshot is present, **When** the header renders, **Then** the `CORREDOR` label, the selector button and the chevron keep their existing position and layout.

---

### User Story 2 - Show a sensible corridor name before data arrives (Priority: P2)

As a dispatcher who has just opened the console, I want the header to show the corridor being watched even before the first live snapshot has loaded, so the header is never blank or placeholder text during startup.

**Why this priority**: The console polls for the snapshot and there is a window before the first response arrives. Without this behaviour the header would either fall back to placeholder text or show nothing. It depends on the configured corridor id already available to the console, so it is lower effort and lower risk than Story 1, hence P2.

**Independent Test**: Render the header with no snapshot available yet and confirm the selector reads `C6-008` with no direction suffix.

**Acceptance Scenarios**:

1. **Given** no snapshot has arrived yet, **When** the header renders, **Then** the corridor selector reads `C6-008` without a direction suffix.

---

### Edge Cases

- **No snapshot (first load / outage / no data):** the selector shows the configured corridor id (`C6-008`) alone, with no direction suffix and no placeholder text.
- **Snapshot then no data:** once a snapshot has been seen, if the connection later reports no data, the header continues to present the corridor name based on the configured corridor id; it never reverts to `[Corredor piloto]`.
- **Inert selector:** the selector button remains non-interactive (switching corridors is out of scope for Turn 1); clicking it changes nothing.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The corridor selector MUST display the corridor identifier from the latest available snapshot when a snapshot is present.
- **FR-002**: When a snapshot is present with direction 1 (station to neighbourhood), the corridor selector MUST read `C6-008 · Estación → barrio`, combining the corridor identifier and the human-readable direction.
- **FR-003**: When no snapshot has yet arrived, the corridor selector MUST display the configured corridor identifier (`C6-008`) with no direction suffix.
- **FR-004**: The placeholder text `[Corredor piloto]` MUST NOT appear anywhere in the application.
- **FR-005**: The corridor selector MUST keep its existing `CORREDOR` label, button and chevron layout unchanged.
- **FR-006**: The corridor selector button MUST remain inert; this feature MUST NOT add corridor-switching behaviour.
- **FR-007**: The direction label MUST be derived from the snapshot's direction value, where direction 1 maps to `Estación → barrio` per the live-data contract.

### Key Entities *(include if feature involves data)*

- **Corridor snapshot**: the latest live reading of the corridor the dispatcher is watching. Relevant attributes for this feature are the corridor identifier and the travel direction. Turn 1 carries a single corridor (`C6-008`) and a single direction (1 = station to neighbourhood). May be absent before the first reading arrives.
- **Configured corridor identifier**: the corridor the console is set to watch (`C6-008`), available to the header even when no snapshot has arrived yet.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With a live snapshot present, the header corridor selector reads exactly `C6-008 · Estación → barrio`.
- **SC-002**: Before any snapshot has arrived, the header corridor selector reads exactly `C6-008`.
- **SC-003**: The string `[Corredor piloto]` occurs zero times in the running application's rendered output.
- **SC-004**: The corridor selector keeps its existing label, button and chevron layout (no visual regression in that region of the header).
- **SC-005**: The frontend quality gate stays green: linting, type checking, the component test suite with coverage above 80 %, and the production build all pass.

## Assumptions

- The direction-to-text mapping needed for Turn 1 is only direction 1 → `Estación → barrio`, because the contract supports direction 1 only; other directions are out of scope.
- The configured corridor identifier (`C6-008`) is already available to the header without a snapshot, so the pre-snapshot state can show it directly.
- "No longer appears anywhere in the app" is satisfied by removing the placeholder from the single component that renders it; the string is assumed not to be duplicated elsewhere.
- The corridor selector remains a single inert control; no dropdown, menu, or corridor list is introduced.
- This is a frontend-only change under `src/frontend/`. No backend, data contract (`contracts/`), or generated-type changes are in scope, consistent with Turn 1 (Adaptive lane) in the turn map.
- The existing header test that asserts the old placeholder text (`Estación → casa`) will be updated to assert the new behaviour; changing that test is expected, not a regression.
