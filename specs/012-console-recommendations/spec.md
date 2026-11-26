# Feature Specification: Active Recommendations in the Dispatcher Console

**Feature Branch**: `012-console-recommendations`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "Show active recommendations in the dispatcher console (UXUI-05, read-only): new read endpoint for the corridor's proposed recommendations and a «Recomendaciones» panel in Central en vivo."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See active recommendations next to the live corridor (Priority: P1)

As a dispatcher, I want to see the active regularity recommendations next to the live fleet list, with their action, reason and expected effect, so I can decide what to do before bunching or a gap takes hold. The panel is read-only: the system recommends, the person decides, and deciding is a separate story.

**Why this priority**: It is the only story in this feature. Without it, recommendations are visible only in the data team's simulation lab.

**Independent Test**: Load the console against a corridor with proposed recommendations and check that one card per recommendation appears with all its fields, and that no control applies or discards anything.

**Acceptance Scenarios**:

1. **Given** the corridor has proposed recommendations, **When** the dispatcher opens *Central en vivo*, **Then** the «Recomendaciones» panel lists up to 3 cards ordered by rank, each with action (in Spanish), bus, stop, duration when the action has one, reason, expected saving (e.g. «−55 s de espera»), data quality («En vivo» / «Estimado») and expiry («Vence HH:MM»).
2. **Given** a recommendation conflicts with another, **When** its card is shown, **Then** it displays «En conflicto».
3. **Given** a reason containing markup, **When** the card is shown, **Then** the reason appears as literal text and is never interpreted as HTML.
4. **Given** the panel is open, **When** 5 s pass, **Then** the list refreshes without user action.
5. **Given** any state of the panel, **When** the dispatcher inspects it, **Then** no button applies or discards a recommendation.
6. **Given** no recommendations are proposed, **When** the panel is shown, **Then** it says «Sin recomendaciones activas».
7. **Given** the latest data snapshot is older than 15 s, **When** the panel is shown, **Then** it says «Datos desactualizados: no se muestran recomendaciones» and lists none.
8. **Given** there is no snapshot, **When** the panel is shown, **Then** it shows the same no-data message as the rest of the console.

---

### Edge Cases

- Requested corridor is not C6-008: the response is no-data with an empty list.
- More than 3 proposed recommendations exist: only the 3 best ranked are returned.
- Recommendations whose status is not `proposed` are never returned.
- A recommendation action without duration omits the duration.
- Stored recommendation that fails contract validation: handled as for the existing read endpoints (assumption below).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a read-only endpoint `GET /api/v1/corridor/{corridor_id}/recommendations` returning `{"status": "ok" | "stale" | "no_data", "corridor_id": "C6-008", "recommendations": [...]}`.
- **FR-002**: The endpoint MUST return only recommendations with status `proposed`, ordered by rank, at most 3, each valid against the published recommendation contract (v1.1.0), reading data contract query Q13 without recomputing any business rule.
- **FR-003**: The status MUST be `no_data` with an empty list when there is no snapshot or the corridor is not C6-008.
- **FR-004**: The status MUST be `stale` with an empty list when the latest snapshot was committed more than 15 s ago in wall time (freshness rule §2.1); otherwise `ok`.
- **FR-005**: The system MUST NOT write or change any recommendation status (Principle IV).
- **FR-006**: The console MUST show a «Recomendaciones» panel in *Central en vivo*, to the right of the fleet list on desktop (about 400 px wide), refreshed every 5 s.
- **FR-007**: Each card MUST show, in Spanish: the action (`hold` «Retener», `reserve_dispatch` «Despachar reserva», `adjust_departure` «Ajustar salida», `skip_stop` «Saltar parada», `slow_down` «Reducir velocidad»), bus, stop, duration when present (e.g. «90 s»), the reason as plain text, the expected saving from `ewt_saving_s` (e.g. «−55 s de espera»), the data quality using the existing quality tag, and «Vence HH:MM» from `expires_ts` in simulated time, same format as the header clock, with no countdown against wall clock.
- **FR-008**: A card MUST show «En conflicto» when `conflicts_with` is not empty.
- **FR-009**: The panel MUST show the empty, stale and no-data messages defined in the scenarios above.
- **FR-010**: The console MUST NOT offer any control to approve, apply or discard a recommendation.
- **FR-011**: The feature MUST ship with automated tests for the three envelope states, rank ordering, the limit of 3, an unsupported corridor, each action label, the conflict marker, the expiry format and the three panel states; the console MUST also work in mock mode with a fixture taken from the published contract fixtures.

### Key Entities

- **Recommendation**: A proposed regularity action for one bus at one stop, with action, optional duration, reason, expected waiting-time saving, data quality, expiry time, rank and conflicts. Owned by the data layer; this feature only reads it.
- **Recommendations response**: Backend-to-frontend envelope with status, corridor id and the list of recommendations. Documented here; no change to the data contract.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A dispatcher sees every active recommendation (up to 3) on the live corridor screen without leaving it or using the simulation lab.
- **SC-002**: A new or changed recommendation appears within 10 s of being published (5 s refresh plus delivery).
- **SC-003**: In 100 % of stale-data cases no recommendation is displayed.
- **SC-004**: In 100 % of tested cases reasons render as text; no markup is interpreted.
- **SC-005**: Every state (list, empty, stale, no data) shows its Spanish message, and existing backend and frontend tests still pass.

## Assumptions

- **Data contract impact**: none. Q13, `docs/data-contract.md`, `contracts/` and the gold tables do not change; the response envelope above is the only new contract.
- Story 5b (approve/discard via command door §4.2 and discard reason §4.6), the alerts inbox (UXUI-07), decision history and mobile layout are out of scope.
- Only corridor C6-008 is supported; other ids give no-data.
- Wall-time freshness uses the latest snapshot commit time; the 15 s threshold matches the existing read endpoints.
- A stored recommendation that fails validation is treated like invalid data in the existing read endpoints.
- Expiry time is shown in simulated time, formatted like the header clock, independent of the host time zone.
- Design reference: UXUI-05 in `docs/designs/resumen-historias.md`.
