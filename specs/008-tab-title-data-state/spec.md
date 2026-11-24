# Feature Specification: Tab Title Data State

**Feature Branch**: `008-tab-title-data-state`

**Created**: 2026-11-24

**Status**: Draft

**Input**: User description: "feat(frontend): browser tab title shows the data state. The browser tab always reads `PulsoFlota · Central en vivo`. A dispatcher with several tabs open cannot tell whether the corridor data is live, estimated or missing. The tab title must follow the header badge state."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the data state from the browser tab (Priority: P1)

As a dispatcher with several browser tabs open, I want the console's tab title to show the data state (live, estimated or no data), so I can notice a source outage even when the console is not the active tab.

**Why this priority**: It is the only story of this feature. Without it, a data outage is visible only when the console tab is in front.

**Independent Test**: Open the console, feed it each data state in turn, and read the tab title. It must match the header badge each time.

**Acceptance Scenarios**:

1. **Given** the source status is live, **When** the console renders, **Then** the tab title is `PulsoFlota · En vivo`.
2. **Given** the source status is estimated, **When** the snapshot updates, **Then** the tab title becomes `PulsoFlota · Estimado`.
3. **Given** the source status is no data, or no response has arrived yet, **When** the console renders, **Then** the tab title is `PulsoFlota · Sin datos`.

---

### Edge Cases

- The status changes while the tab is in the background: the title still updates.
- The first response has not arrived: the title is `PulsoFlota · Sin datos` once the console renders. Before the console loads, the static initial title (`PulsoFlota · Central en vivo`) shows.
- The data request fails after a successful one: the title follows the header badge, whatever state the badge shows.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tab title MUST be `PulsoFlota · En vivo` when the data state is live.
- **FR-002**: The tab title MUST be `PulsoFlota · Estimado` when the data state is estimated.
- **FR-003**: The tab title MUST be `PulsoFlota · Sin datos` when the data state is no data or no response has been received yet.
- **FR-004**: The tab title MUST always agree with the state shown by the header badge.
- **FR-005**: The tab title MUST update whenever the data state changes, without a page reload.
- **FR-006**: The initial title shown before the console loads MUST stay `PulsoFlota · Central en vivo`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100 % of the three data states, the tab title matches the header badge.
- **SC-002**: A dispatcher reading only the tab strip can tell live from estimated from no data.
- **SC-003**: A change in data state shows in the tab title on the same update that changes the header badge.

## Assumptions

- The header badge already derives its state from the source status; the tab title reuses that state and defines no rule of its own.
- Out of scope: favicon changes, notifications, sounds.
- Frontend only. No backend, data contract or generated type changes; no contract impact.
- Titles are in Spanish, as in the existing console.
- Labels are taken verbatim from the issue; no localization is needed.
