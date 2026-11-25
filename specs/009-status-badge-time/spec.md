# Feature Specification: Status Badge Readable Time

**Feature Branch**: `009-status-badge-time`

**Created**: 2026-11-24

**Status**: Draft

**Input**: User description: "feat(frontend): readable time and 'since' detail in the status badge (US-09)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Judge data freshness at a glance (Priority: P1)

As a dispatcher, I want the status badge in the header to show a readable local time and, when a source is down, since when, so I can judge how fresh the data is without decoding a raw timestamp.

**Why this priority**: The raw ISO timestamp is hard to read under pressure, and a silent source outage hides how long the data has been stale. Both affect trust in the recommendations.

**Independent Test**: Render the badge for each of the three states with fixed timestamps and check the detail text.

**Acceptance Scenarios**:

1. **Given** status `live` and last event `2026-11-24T22:42:08Z` in a UTC-5 browser, **When** the badge renders, **Then** it reads `Último evento 17:42:08`.
2. **Given** status `estimated` with two buses down since 17:39 and 17:41 local, **When** the badge renders, **Then** it reads `Una fuente no responde desde 17:39` and no extra alert is raised (D1).
3. **Given** status `no_data`, **When** the badge renders, **Then** it reads `Sin eventos del corredor`.

---

### Edge Cases

- Several sources down: the earliest "since" time is shown.
- `estimated` with no usable "since" value: the badge falls back to a generic detail without a time and does not fail.
- Midnight and single-digit hours or minutes are zero-padded (`07:05:09`).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: For `live`, the badge detail MUST read `Último evento HH:MM:SS`, 24-hour format, in the browser's local time, from the last-event time of the source status.
- **FR-002**: For `estimated`, the badge detail MUST read `Una fuente no responde desde HH:MM`, in local time, using the earliest "since" among the sources that are down.
- **FR-003**: For `no_data`, the badge detail MUST remain `Sin eventos del corredor`.
- **FR-004**: The `estimated` state MUST NOT raise any additional alert.
- **FR-005**: The header clock and the alert banner text MUST remain unchanged.
- **FR-006**: The detail text formatting MUST be a separate, independently unit-tested unit, not inline in the app shell.
- **FR-007**: The change MUST NOT alter the backend, the data contracts or the generated API types.

### Key Entities

- **Source status**: state (`live`, `estimated`, `no_data`), time of the last event, and a list of sources down, each with a "since" time.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In all three states, the badge detail matches the acceptance scenarios exactly, with no raw ISO timestamp visible.
- **SC-002**: The displayed times are identical regardless of the reviewer's machine time zone or locale during automated checks.
- **SC-003**: Automated frontend checks (lint, type check, tests with coverage above 80 %, build) all pass.

## Assumptions

- Dispatchers use a browser whose local time zone is the one they expect to read (Medellín, UTC-5).
- The existing source status already provides the last-event time and per-source "since" times; no new data is needed.
- `no_data` has no "since" because no events were ever received.
- If `estimated` carries no usable "since", a generic detail without a time is acceptable.
- Scope is the frontend only.
