# Feature Specification: Tab Title Shows Data State

**Feature Branch**: `feature/56-cadena`

**Created**: 2026-11-24

**Status**: Draft

**Input**: User description: "feat(frontend): browser tab title shows the data state. The browser tab always reads `PulsoFlota · Central en vivo`. A dispatcher with several tabs open cannot tell from the tab whether the corridor data is live, estimated or missing."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See the data state from the tab title (Priority: P1)

As a dispatcher, I want the browser tab title to show the data state, so I can notice a source outage even when the console is not the active tab.

**Why this priority**: It is the only story. It makes a source outage visible without switching tabs.

**Independent Test**: Open the console with live, estimated and missing data in turn and read the tab title each time.

**Acceptance Scenarios**:

1. **Given** the source status is live, **When** the console renders, **Then** the tab title is `PulsoFlota · En vivo`.
2. **Given** the source status is estimated, **When** the snapshot updates, **Then** the tab title becomes `PulsoFlota · Estimado`.
3. **Given** no data (status "no data" or no response yet), **When** the console renders, **Then** the tab title is `PulsoFlota · Sin datos`.

### Edge Cases

- Before the first response arrives, the title is `PulsoFlota · Sin datos`.
- The page's static initial title stays `PulsoFlota · Central en vivo` until the console applies a state.
- An unrecognized status value is treated as no data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The tab title MUST match the state shown in the header badge: `PulsoFlota · En vivo`, `PulsoFlota · Estimado` or `PulsoFlota · Sin datos`.
- **FR-002**: The tab title MUST update whenever the data state changes, without a page reload.
- **FR-003**: The title MUST be `PulsoFlota · Sin datos` when the status is "no data", unrecognized, or no response has arrived yet.
- **FR-004**: The mapping from status to title MUST be covered by automated tests, including the unrecognized-status case.
- **FR-005**: The page's static initial title MUST remain unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100 % of the three data states, the tab title matches the header badge.
- **SC-002**: A title change is visible within the same refresh in which the badge changes.
- **SC-003**: The frontend quality pipeline stays green, with test coverage above 80 %.

## Assumptions

- Scope is the dispatcher console only. No backend, data contract or generated-type changes.
- The three states and their labels are those the header badge already shows.
- Favicon changes, notifications and sounds are out of scope.
- An unrecognized status falls back to "no data" (the safe, non-reassuring state).
