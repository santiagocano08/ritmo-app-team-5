# Feature Specification: Functional Integration (Turn-1 Whole)

**Feature Branch**: `feature/US-07-functional-integration`
**Created**: 2026-11-22
**Status**: Draft
**Input**: User description: "US-07 — package the frontend and validate the Turn-1 project as one functional whole: all services running together under docker-compose, dispatcher console reaching the real backend over HTTP and showing live corridor C6-008 state, validated end to end. Integration only — no new product behavior, contracts or business logic."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run the whole Turn-1 system together and see live corridor state (Priority: P1)

As the operations team, I start the complete Turn-1 system with a single command and open the dispatcher console in a browser against the real backend, so I can watch corridor C6-008 update live instead of relying on parts tested in isolation.

**Why this priority**: This is the core value of the story — proving the project is a deployable, functional whole. Without it, ingestion, backend, database and console remain validated only separately and no one can confirm they work together. Every other story supports or documents this one.

**Independent Test**: Bring up the full stack (database, ingestion, refresh, backend read API, dispatcher console) with one command against gold data for C6-008, open the console in a browser, and confirm it loads from the real backend (no mock fixtures in the path), shows the fleet leader-first with state, headway and quality, and auto-refreshes about every 5 seconds. Delivers the functional-whole outcome on its own.

**Acceptance Scenarios**:

1. **Given** the full stack started with gold data for corridor C6-008, **When** all services finish starting, **Then** every service (database, ingestion, refresh, backend read API, dispatcher console) reports healthy.
2. **Given** the stack is up and healthy, **When** a dispatcher opens the console in a browser, **Then** it loads against the real backend with no mock fixtures, shows the fleet ordered leader-first with per-bus state, headway and quality, and refreshes about every 5 seconds.
3. **Given** the live data reports a bus with an estimated data source, **When** that bus is rendered, **Then** it is shown as "Estimated" and no alert is raised.
4. **Given** the corridor has no current snapshot, **When** the console polls the backend, **Then** it shows the no-data state rather than an error.
5. **Given** the backend is interrupted and then restored, **When** polls first fail and later succeed, **Then** the console shows a non-blocking stale indicator and recovers without a page reload or crash.

---

### User Story 2 - Package the dispatcher console as a hardened, same-origin service (Priority: P2)

As the operations team, I want the dispatcher console delivered as a packaged, security-hardened service that is served alongside the backend under one origin, so the console reaches the backend without cross-origin friction and the shipped image exposes no unnecessary runtime, source or stack details.

**Why this priority**: Packaging and same-origin serving are what let Story 1 run as a real deployable stack rather than a dev server. It is second because the end-to-end validation (P1) is the outcome that matters; packaging is the means. Hardening (non-root, security headers, no stack-revealing headers) is a Turn-1 security obligation that must ship with the package.

**Independent Test**: Build and inspect the shipped console image and run it behind its reverse proxy: confirm it runs as a non-root user, contains only the built static assets (no build runtime, source or dependency tree), serves requests under one origin that also forwards backend calls, and returns the required security headers while omitting stack-revealing ones.

**Acceptance Scenarios**:

1. **Given** the shipped console image, **When** it is inspected, **Then** it runs as the designated non-root user (UID 10001) and contains only the built static assets — no build runtime, application source or dependency tree.
2. **Given** the console is served behind its reverse proxy, **When** the console requests backend data using its default relative API path, **Then** the request is served under one origin and forwarded to the backend, so no cross-origin configuration is required.
3. **Given** a response served by the console, **When** its headers are examined, **Then** the mandatory security headers are present (content-security-policy, strict-transport-security, no-sniff, deny-framing) and headers revealing the technology stack or versions are absent.

---

### User Story 3 - Trustworthy run instructions and reconciled documentation (Priority: P3)

As a new contributor, I want project documentation — the README first — to accurately describe the full integrated setup, so I can configure the required settings, start the whole stack, and reach the console against the real backend without being misled by stale claims.

**Why this priority**: Documentation makes the functional whole repeatable by someone who did not build it. It is third because the system can be validated by the original team without it, but the story is not complete until the delivered setup is documented and contradictory statements (for example, claims that no frontend exists) are corrected.

**Independent Test**: Hand the updated README to someone unfamiliar with the project and have them follow it end to end: they should be able to configure the required environment settings, start the whole stack with one command, and open the console against the real backend, and they should find no documentation claiming the console does not exist.

**Acceptance Scenarios**:

1. **Given** the updated README, **When** a new contributor follows it, **Then** they can configure the required environment settings (including the console's API base / same-origin proxy default), start the full stack with one command, and reach the console against the real backend.
2. **Given** the delivered setup, **When** project documentation (README, docs, agent context) is reviewed, **Then** its description of the service list, the frontend layout and how to run the system matches what actually ships, with no stale "no frontend yet" statements.

---

### Edge Cases

- When the console starts before the backend is ready, startup ordering and health gating prevent a broken first load; the console surfaces a non-blocking state rather than a crash.
- When the backend becomes unavailable mid-session and later recovers, the console degrades to a non-blocking stale indicator and recovers on its own without a reload.
- When the corridor has no current snapshot, the console shows an explicit no-data state distinct from an error state.
- When a bus reports an estimated data source, the console labels it without raising an alert.
- When live backend responses do not match the committed contract version, work stops and a contract decision is requested rather than silently editing the contract or the generated types.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST start all Turn-1 services together with a single orchestration command: database, ingestion, periodic refresh, backend read API and dispatcher console.
- **FR-002**: Each started service MUST report a health status, and the console MUST start only after the backend is reported healthy.
- **FR-003**: The dispatcher console MUST obtain corridor data from the real backend with no mock fixtures in the request path.
- **FR-004**: The console MUST render the corridor fleet ordered leader-first, showing per-bus state, headway and quality.
- **FR-005**: The console MUST refresh the displayed corridor state automatically about every 5 seconds.
- **FR-006**: When a bus reports an estimated data source, the console MUST label it as "Estimated" and MUST NOT raise an alert.
- **FR-007**: When the corridor has no current snapshot, the console MUST display a no-data state distinct from an error state.
- **FR-008**: When backend polls fail and later succeed, the console MUST show a non-blocking stale indicator and MUST recover without a page reload or crash.
- **FR-009**: The dispatcher console MUST be packaged as a deployable service containing only its built static assets — no build runtime, application source or dependency tree in the shipped artifact.
- **FR-010**: The shipped console service MUST run as the designated non-root user (UID 10001).
- **FR-011**: The console MUST be served alongside the backend under a single origin that forwards backend requests, so the console's default relative API path works without cross-origin configuration.
- **FR-012**: Responses served by the console MUST include the mandatory security headers (content-security-policy, strict-transport-security, content-type no-sniff, deny-framing) and MUST omit headers that reveal the technology stack or component versions.
- **FR-013**: The system MUST introduce no new user-facing feature, data contract or business logic; it only wires, packages and validates what prior stories delivered.
- **FR-014**: The live backend responses MUST match the committed contract version (1.0.0) for corridor state and source status; on any mismatch, the team MUST stop and request a contract decision rather than edit the contract or the generated types.
- **FR-015**: A documented end-to-end validation walkthrough MUST exist that exercises live snapshot render, the ~5-second refresh, the estimated-source case (no alert), the no-data case, and backend interruption and recovery.
- **FR-016**: Project documentation — the README first — MUST describe the full integrated setup: how to configure required settings and run the whole stack, the required environment settings (including the console API base / same-origin proxy default), service ports and health checks, and how to open the console against the real backend.
- **FR-017**: Project documentation (README, docs, agent context) MUST be reconciled so its description of the service list, the frontend layout and how to run the system matches the delivered setup, with no stale statements that the frontend does not exist.

### Key Entities *(include if feature involves data)*

- **Corridor snapshot**: The current live state of corridor C6-008 that the console displays — the fleet ordered leader-first with per-bus state, headway and quality. Consumed by the console from the backend; unchanged by this story.
- **Source status**: An indicator of the data source for the corridor or a bus (for example, estimated), driving the "Estimated" label and the absence of an alert. Consumed by the console; unchanged by this story.
- **Service in the stack**: A running unit of the Turn-1 system (database, ingestion, refresh, backend read API, dispatcher console) with a health status and startup ordering relative to the others.
- **Shipped console artifact**: The packaged, deployable console containing only built static assets, run as a non-root user and served with the required security headers under a single origin.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Starting the system with a single command brings up all five Turn-1 services (database, ingestion, refresh, backend read API, dispatcher console) and 100% of them report healthy.
- **SC-002**: A dispatcher opening the console against the real backend sees the live corridor C6-008 fleet (leader-first, with state, headway and quality) within the first load, with no mock fixtures involved.
- **SC-003**: The displayed corridor state refreshes automatically about every 5 seconds without user action.
- **SC-004**: All five documented validation cases pass: live snapshot render, ~5-second refresh, estimated source without an alert, no-data state, and backend interruption followed by self-recovery.
- **SC-005**: Inspection of the shipped console artifact confirms it runs as a non-root user, carries only built static assets, serves all required security headers, and exposes no stack-revealing headers — zero exceptions.
- **SC-006**: A new contributor, following only the updated README, configures the required settings and reaches the live console against the real backend without needing undocumented steps, and finds no documentation claiming the frontend does not exist.
- **SC-007**: Live backend responses match the committed contract version with zero schema drift for the corridor-state and source-status data the console consumes.

## Assumptions

- The backend read API (US-05) and the dispatcher console (US-06) are both complete and merged; this story integrates and packages what they delivered and does not change their behavior.
- The corridor state and source-status contracts remain at version 1.0.0; this story consumes them unchanged, and any live mismatch triggers a contract decision rather than an edit here.
- Same-origin serving (console and backend reached through one origin via a reverse proxy) is the default deployment topology for Turn 1; a cross-origin topology and its access-control handling are out of scope unless explicitly chosen later.
- Gold/simulator data producing corridor C6-008 snapshots is available to drive the end-to-end validation.
- Authentication, authorization and any access-control UI are out of scope for Turn 1; the console never decides access control.
- Publishing images to an external registry and image vulnerability scanning as a release gate are not required to complete this Turn-1 story, though prior security gates on code and dependencies remain in force.
- Advanced delivery targets (orchestration platforms beyond local compose) are out of scope for this story.
- The "about every 5 seconds" refresh and the five documented validation cases are inherited from the prior console story and the ticket's acceptance criteria; they are treated as the target behavior for this integration.
