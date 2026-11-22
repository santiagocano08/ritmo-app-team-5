# Feature Specification: US-05 — Backend Read API for Live Corridor State

**Feature Branch**: `feature/US-05-backend-read-api`

**Created**: 2026-11-21

**Status**: Draft

**Input**: User description: "Expose the existing gold-layer corridor snapshots and data-source status for corridor C6-008 as a small read-only HTTP API, so the dispatcher console and other read clients can see reliable live fleet state. Two endpoints: latest `corridor_now` snapshot and latest `source_status`, both serving the approved read contracts v1.0.0. Read-only against gold; polling-only (no real-time push); no auth/RBAC, recommendations, pagination, or history in this story." (Ticket US-05-backend-read-api)

## User Scenarios & Testing *(mandatory)*

### User Story 1 (US-05.1) - See current corridor state (Priority: P1)

A read client (primarily the dispatcher console) requests the latest consolidated state of corridor C6-008 and receives a single, current snapshot describing where the fleet stands right now, so the dispatcher can judge service regularity without hand-assembling raw data.

**Why this priority**: This is the core value of the ticket. Without a served corridor snapshot the dispatcher console cannot be built and the dispatcher stays operationally blind, which is the structural problem the product exists to solve. It is the minimum viable slice: it delivers visible value on its own.

**Independent Test**: With a current snapshot present in the gold layer, request the corridor-state endpoint and confirm the returned body matches the approved `corridor_now` contract v1.0.0 and reflects the most recent snapshot. No other story is required for this to be useful.

**Acceptance Scenarios**:

1. **Given** the gold layer holds a current corridor snapshot, **When** a client requests the latest corridor state, **Then** the response conforms to the `corridor_now` contract v1.0.0 and reflects the latest available snapshot.
2. **Given** a client requests the latest corridor state, **When** the response is returned, **Then** it contains only fields defined by the approved contract (no invented or extra fields).

---

### User Story 2 (US-05.2) - Know whether the data can be trusted (Priority: P2)

A read client requests the current data-source status for corridor C6-008 and learns which buses are reporting on time and which have gone quiet, so the dispatcher can tell whether the displayed corridor state is live or estimated before acting on it.

**Why this priority**: Freshness and trust in the data are essential to safe regulation decisions, but the corridor snapshot (P1) already delivers standalone value. Source status strengthens the trust signal on top of it.

**Independent Test**: With gold data where at least one bus has not reported for more than two minutes, request the source-status endpoint and confirm the status is reported as `estimated`, the stale bus appears in the down-sources list, and no alert is implied by the response.

**Acceptance Scenarios**:

1. **Given** the gold layer holds current source information, **When** a client requests source status, **Then** the response conforms to the `source_status` contract v1.0.0 and reflects the latest available data.
2. **Given** a bus has not reported for more than 2 minutes, **When** a client requests source status, **Then** the overall status is `estimated`, that bus appears in the set of down sources, and the response implies no alert.

---

### Edge Cases

- **No current snapshot in gold**: When the corridor-state or source-status data is not yet available, the client receives a clear, well-formed response indicating the absence of data rather than a malformed body or an internal error. (See FR-008.)
- **Unknown or unsupported corridor**: When a client requests a corridor other than C6-008 (the only corridor served in this turn), the system returns the same "no data" response as the empty-gold case — HTTP 200 with the no-data envelope echoing the requested corridor id — rather than introducing a new error form. (See FR-008 and FR-011.)
- **All buses reporting normally**: Source status reports a healthy/live state with an empty set of down sources.
- **Unexpected internal failure**: Any unhandled error returns a generic error body carrying a correlation identifier, with no stack trace, file path, or internal data-store detail exposed.
- **Contract field missing from gold**: If the gold data cannot populate a contract-required field, the feature does not invent or guess a value; this condition is treated as a blocking data-contract issue to escalate, not as a silent default. (See Assumptions.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a read-only endpoint that returns the latest corridor-state snapshot for corridor C6-008.
- **FR-002**: The system MUST expose a read-only endpoint that returns the latest data-source status for corridor C6-008.
- **FR-003**: When corridor-state data is available, the corridor-state response MUST conform to the approved `corridor_now` read contract, version 1.0.0, exposing only fields defined by that contract. This "contract-fields-only" rule governs the data-bearing response; the "no data" response (FR-008) is a separate API-level envelope and is not subject to it.
- **FR-004**: When source-status data is available, the source-status response MUST conform to the approved `source_status` read contract, version 1.0.0, exposing only fields defined by that contract. As with FR-003, this rule governs the data-bearing response and does not apply to the "no data" response (FR-008).
- **FR-005**: Both endpoints MUST be read-only: they read from the gold layer and MUST NOT write to or modify any upstream (bronze) data.
- **FR-006**: Source status MUST classify the data as `estimated` and list any bus that has not reported for more than 2 minutes as a down source, without implying an alert.
- **FR-007**: Any request that fails with an unhandled error MUST return a generic error body that includes a correlation identifier and MUST NOT expose stack traces, file paths, or internal data-store structure.
- **FR-008**: When no current snapshot or source data is available, the system MUST return a well-formed, clearly distinguishable response for the "no data" condition rather than failing opaquely. This "no data" response is an API-level sibling envelope carrying a `status` of `no_data` and the requested corridor id; it is NOT a mutation of, or an extra field added to, the `corridor_now` contract document, so it does not violate the contract-fields-only rule of FR-003/FR-004. For `source_status`, `no_data` is already a first-class value of the contract's `status` field; for `corridor_now`, which has no such field, the envelope is returned alongside (not inside) the contract document.
- **FR-009**: Both endpoints MUST be documented so that a read client can discover the exact request and response shapes and generate a typed client from that documentation.
- **FR-010**: Both endpoints MUST reflect the single most recent snapshot only; the system is NOT required to provide history, filtering, or pagination for this feature.
- **FR-011**: A request for any corridor other than C6-008 (the only corridor served this turn) MUST return the "no data" response of FR-008 — HTTP 200 with the no-data envelope echoing the requested corridor id — and MUST NOT introduce a distinct error status or leak that the corridor is unsupported.

### Key Entities *(include if feature involves data)*

- **Corridor-now snapshot**: The latest consolidated live state of corridor C6-008 as defined by the `corridor_now` contract v1.0.0. Represents what the dispatcher sees as "the corridor right now".
- **Source status**: The current reporting health of the data sources feeding corridor C6-008 as defined by the `source_status` contract v1.0.0, including the overall freshness classification (e.g. live vs. estimated) and the set of sources currently considered down.
- **Correlation identifier**: An opaque reference attached to error responses that ties a failed request to internally recorded detail, without revealing internal state to the client.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A read client can retrieve the current corridor state and the current source status for corridor C6-008 through two distinct requests, with zero manual assembly of raw data.
- **SC-002**: 100% of corridor-state and source-status responses validate against the approved read contracts (v1.0.0) with no extra or missing fields.
- **SC-003**: When any bus is stale (no report for more than 2 minutes), the source status correctly reflects an `estimated` state and names the stale bus as down in 100% of such cases.
- **SC-004**: No error response exposes a stack trace, file path, or internal data-store detail; every error response carries a correlation identifier that can be matched to an internal record.
- **SC-005**: A client developer can generate a typed read client from the published endpoint documentation without needing to inspect server internals or guess field names.

## Assumptions

- The read contracts `corridor_now.schema.json` and `source_status.schema.json` (both v1.0.0) already exist, are approved, and are the single source of truth for response shapes; no contract changes are expected in this feature. If a required field cannot be populated from gold, the work stops and escalates for a data-contract decision rather than inventing a value (per the ticket's instruction to request an ADR from the contract owners).
- The gold layer already produces the corridor snapshots consumed here; producing or transforming that data is out of scope.
- This feature serves corridor C6-008 only, consistent with the current turn's scope.
- Access is polling-only. Real-time push (WebSocket / Server-Sent Events) is deferred to a later turn.
- Authentication, authorization (RBAC), and JWT are out of scope for this feature and are handled in a later turn; the endpoints are read-only and expose no sensitive per-user data.
- Recommendations and the approve/discard (Human-in-the-Loop) decision path are out of scope and handled in a separate story.
- Pagination, filtering, historical queries, rate limiting, and caching headers are out of scope; only the latest snapshot is required.
- Geographic data (map geometry, coordinates) and real-time cache concerns are out of scope for this feature.
- This feature has no dependencies on other unstarted stories.
