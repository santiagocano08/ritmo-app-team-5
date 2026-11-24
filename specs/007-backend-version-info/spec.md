# Feature Specification: Backend Version/Build Info Endpoint

**Feature Branch**: `feature/US-08-backend-version-info`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: US-08 — expose a tiny, read-only version/build-info endpoint so operators and contributors validating the Turn-1 stack can confirm which backend build is live and which read-contract version it serves, without inspecting the container.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Confirm the running backend build and contract version (Priority: P1)

An operator or contributor validating the Turn-1 stack queries a single endpoint and immediately sees the running backend's application version, the read-contract version it targets, and the build's source revision. They use this to confirm which build is live and to detect drift between the console's generated types and the live responses, without having to open a shell into the container.

**Why this priority**: This is the entire feature. Without it there is no way, during integration and end-to-end validation, to tell which backend version is running or which read-contract version it serves. It is a small, low-risk slice that exercises the full RITMO loop end to end and delivers standalone diagnostic value.

**Independent Test**: With the backend running, request the version endpoint and confirm the response reports a backend application version, the read-contract version, and a source-revision identifier, each in a predictable, machine-readable shape. Delivers value on its own because it answers "which build is live?" with no other feature present.

**Acceptance Scenarios**:

1. **Given** the backend is running, **When** a client requests the version info, **Then** the response is successful and reports the backend application version, the read-contract version value `1.0.0`, and a source-revision identifier, all conforming to a fixed, documented shape.
2. **Given** the build produced no source-revision identifier, **When** a client requests the version info, **Then** the source-revision field is reported as `unknown` and the request still succeeds.
3. **Given** the endpoint is called, **When** it produces its response, **Then** it performs no database or cache query and reads nothing from any stored table.

### Edge Cases

- When no source-revision identifier is available at build time, the response reports `unknown` for that field rather than failing or omitting it.
- When an unexpected internal error occurs, the response is a generic error body carrying a correlation identifier, with no stack trace, file paths, or internal structure exposed.
- When the data source for version values is missing or empty, the reported values fall back to a safe default (e.g. `unknown`) rather than causing the request to fail.
- The reported values always come from a single source of truth established at build/packaging time, so repeated requests to the same running build report identical values.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a single, read-only endpoint that reports version/build information about the running backend.
- **FR-002**: The response MUST include the backend application version, the read-contract version the backend targets, and a source-revision identifier for the running build.
- **FR-003**: The read-contract version reported MUST be the version of the existing `corridor_now` / `source_status` read contracts the backend already targets, with the value `1.0.0`; this field only reports an existing version and MUST NOT define, alter, or imply a change to any data contract.
- **FR-004**: When no source-revision identifier is available at build time, the system MUST report the value `unknown` for that field and still return a successful response.
- **FR-005**: The response body MUST conform to a fixed, documented shape with only the defined fields; the system MUST NOT return invented or free-form fields.
- **FR-006**: The endpoint MUST be read-only: it MUST NOT query or read from the database, the cache, or any stored table, and MUST NOT perform writes anywhere.
- **FR-007**: The reported values MUST originate from a single source of truth captured at build/packaging time, not hard-coded inline in the request-handling logic.
- **FR-008**: On any unhandled error, the response MUST be a generic error body that includes a correlation identifier and MUST NOT expose stack traces, file paths, or internal system structure.
- **FR-009**: The endpoint MUST be described in the backend's published interface documentation so that client code can be generated from it if ever needed.
- **FR-010**: The endpoint is unauthenticated read-only build metadata in this turn; authentication and role-based access control for it are out of scope here.

### Key Entities *(include if feature involves data)*

- **Version Info**: The read-only build description returned by the endpoint. Attributes: the backend application version, the read-contract version it targets (`1.0.0`), and a source-revision identifier (a short build-time revision string, or `unknown` when unavailable). It is derived from build/packaging metadata, not from any persisted record.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An operator or contributor can determine the running backend's application version and targeted read-contract version in a single request, with no container access, in under 30 seconds.
- **SC-002**: 100% of successful responses include all three defined fields (application version, read-contract version, source-revision identifier) and no additional fields.
- **SC-003**: When no source-revision identifier is available, 100% of requests still succeed and report `unknown` for that field.
- **SC-004**: 0 database or cache interactions occur while serving the endpoint, verifiable by observing that no data-store access takes place during a request.
- **SC-005**: 0 error responses expose a stack trace, file path, or internal system detail; every error response carries a correlation identifier.

## Assumptions

- The intended consumers are operators and contributors validating the Turn-1 stack (not end riders or the dispatcher UI); surfacing the version in the dispatcher console is a separate, out-of-scope story.
- Liveness checking stays as the existing dedicated liveness endpoint; this feature adds build metadata only and does not add readiness or dependency-health logic.
- The existing generic error handler (generic body with correlation identifier, no stack trace) is reused unchanged for this endpoint.
- The read-contract version `1.0.0` is a fixed value for this turn and tracks the version the backend already targets; it changes only when the underlying read contracts change, which is out of scope here.
- The source-revision identifier is captured at build/packaging time (e.g. via build metadata or an environment value) and is treated as `unknown` when absent, so local or metadata-less builds still return successfully.
- The endpoint introduces no business logic and no new data contract; if delivery appears to require a change under `contracts/`, work stops and an architecture decision record is requested from the data-design owner.
- No new external dependencies are introduced; the existing backend application and error handler are already in place.
