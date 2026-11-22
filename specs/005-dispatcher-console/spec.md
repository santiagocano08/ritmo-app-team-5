# Feature Specification: Dispatcher Console — Fleet State and Headway

**Feature Branch**: `feature/US-06-frontend-console`

**Created**: 2026-11-22

**Status**: Draft

**Input**: User description: "US-06 Turn 1 dispatcher web console. A dispatcher needs to see the live state of corridor C6-008's fleet — each bus, its headway vs. plan, and its data quality — so they can detect bunching and gaps. Turn 1 is read-only, polling-based (no map, no recommendations, no auth). The console also provides the role-and-data-state navigation shell (sidebar sections, header corridor selector, data-state badge and alert banner) described in the US-03 desktop styling spec."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See live fleet state and headway (Priority: P1)

A dispatcher opens the console and sees the current state of corridor C6-008's fleet: every bus in service, ordered leader-first, with where it is along the corridor, its headway to the bus ahead compared against the planned headway, and whether its position is based on live or estimated data. The view refreshes on its own at a steady cadence so the dispatcher always works from a recent snapshot without reloading.

**Why this priority**: This is the core value of the story and the minimum viable product. Without a live fleet view the dispatcher has no way to observe the corridor, so every other capability depends on it. It delivers value on its own even if nothing else ships.

**Independent Test**: With the backend serving a corridor snapshot, open the console and confirm each bus appears leader-first with its state, position, and actual-vs-planned headway, and that the list updates automatically at the expected cadence without manual action.

**Acceptance Scenarios**:

1. **Given** the backend serves a corridor snapshot, **When** the console loads, **Then** it shows each bus leader-first with its state, position along the corridor, and headway ahead compared to the planned headway, and the view refreshes automatically at a fixed cadence.
2. **Given** a bus has estimated rather than live position data, **When** the snapshot is displayed, **Then** that bus is labeled as estimated and no alert is raised for it.
3. **Given** the fleet snapshot changes between refreshes, **When** the next refresh completes, **Then** the displayed bus states and positions reflect the newest snapshot.

---

### User Story 2 - Spot bunching and gaps at a glance (Priority: P2)

While watching the fleet, the dispatcher needs to immediately pick out buses that are bunched (too close together) or leaving a gap (too far apart), and see a running count of how many buses are in service, how many are bunched, and how many gaps exist across the corridor.

**Why this priority**: Detecting bunching and gaps is the operational point of watching the fleet, but it builds on the live view (P1). The raw per-bus state is already visible under P1; this story makes irregularity obvious and summarizes it so the dispatcher does not have to scan the whole list.

**Independent Test**: Feed a snapshot that contains at least one bunched bus and one gap, then confirm those buses are visually distinguished from regular buses and that the corridor summary counts of buses in service, bunched buses, and gaps match the snapshot.

**Acceptance Scenarios**:

1. **Given** a bus is in a bunched or gap state, **When** the snapshot is displayed, **Then** that bus is visually distinguished from regular buses.
2. **Given** the snapshot updates the number of bunched buses or gaps, **When** the next refresh completes, **Then** the corridor summary counts of buses in service, bunched buses, and gaps update to match.

---

### User Story 3 - Understand overall data trustworthiness (Priority: P3)

The dispatcher needs an at-a-glance signal of how trustworthy the data behind the view is right now: whether the corridor feed is fully live, partly estimated because an operator source is down, or showing no recent data at all. When data is estimated or absent, a banner explains the situation in plain language so the dispatcher knows how much to rely on the view.

**Why this priority**: Data-trust context shapes how the dispatcher interprets everything else, but the console is still usable for the primary task (P1/P2) without the banner. It is a safety and clarity enhancement layered on top of the fleet view, so it ranks below the core observation stories.

**Independent Test**: Switch the source status among live, estimated, and no-data conditions and confirm the console shows the matching overall status indicator, that the explanatory banner appears only for estimated and no-data states, and that estimated data alone never triggers an alert banner.

**Acceptance Scenarios**:

1. **Given** the source status is live, **When** the console renders, **Then** it shows a live status indicator and no explanatory banner is displayed.
2. **Given** the source status is estimated because an operator source is down, **When** the console renders, **Then** it shows an estimated status indicator with an explanatory banner, and estimated buses are labeled estimated without raising an alert.
3. **Given** no corridor events have arrived for longer than the no-data threshold, **When** the console renders, **Then** it shows a no-data status indicator with an explanatory banner telling the dispatcher to rely on the day's plan.
4. **Given** the dispatcher opens the console, **When** the navigation shell renders, **Then** it shows the sidebar sections, the corridor selector, the current time, the data-state badge, and the user identity, with the active section marked.

---

### Edge Cases

- **Backend briefly unreachable**: When a refresh fails to reach the backend, the console shows a non-blocking "stale data" indicator, keeps the last known snapshot visible, and retries on the next cadence without crashing or losing the view.
- **Empty corridor**: When the snapshot reports no buses in service, the console shows a clear empty state and zero counts rather than a blank or broken list.
- **Broken-down bus**: A bus reported as broken down is shown in that state and is distinguishable from active buses; it is handled consistently in the summary counts.
- **Prolonged no-data**: When no events arrive for longer than the no-data threshold, the status moves to no-data and the explanatory banner persists until fresh data resumes.
- **Transition between states**: When the source status changes between refreshes (for example live to estimated), the indicator and banner update on the next refresh without requiring a reload.
- **Single bus / leader only**: When only one bus is in service there is no bus ahead; the view presents that bus without a misleading headway comparison.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The console MUST display the fleet of the active corridor as a list of buses ordered leader-first.
- **FR-002**: For each bus, the console MUST show its operational state (leader, regular, bunched, gap, or broken down), its position along the corridor, its headway to the bus ahead, and the planned headway for comparison.
- **FR-003**: For each bus, the console MUST indicate whether its data is live or estimated.
- **FR-004**: The console MUST visually distinguish bunched buses and gap buses from regular buses.
- **FR-005**: The console MUST display a corridor summary showing the number of buses in service, the number of bunched buses, and the number of gaps.
- **FR-006**: The console MUST display an overall source-status indicator with one of three states: live, estimated, or no data.
- **FR-007**: The console MUST display an explanatory banner for the estimated and no-data states, and MUST NOT display that banner in the live state.
- **FR-008**: When data is estimated, the console MUST label affected buses as estimated and MUST NOT raise an alert solely because data is estimated.
- **FR-009**: The console MUST refresh the fleet view and status automatically at a fixed cadence of approximately 5 seconds without requiring a manual reload.
- **FR-010**: When a refresh fails to reach the backend, the console MUST show a non-blocking stale-data indicator, retain the last known snapshot, and retry on the next cadence without crashing.
- **FR-011**: The console MUST present a navigation shell containing the sidebar sections for the dispatcher role (live central, alerts, day plan), a corridor selector, the current time, the data-state badge, and the signed-in user identity, with the active section clearly marked.
- **FR-012**: The console MUST communicate every operational state and data-quality condition through text and not through color alone.
- **FR-013**: The console MUST present an informative empty state when the corridor has no buses in service, showing zero counts rather than a blank view.
- **FR-014**: The console MUST reflect the newest available snapshot after each successful refresh, replacing prior displayed values.

### Key Entities *(include if feature involves data)*

- **Corridor snapshot**: The current state of one corridor at a point in time. Contains the ordered list of buses and the summary counts (buses in service, bunched, gaps).
- **Bus**: A single vehicle in the corridor. Key attributes the dispatcher sees: operational state (leader / regular / bunched / gap / broken down), position along the corridor, headway to the bus ahead, planned headway, and data quality (live / estimated).
- **Source status**: The overall trustworthiness of the corridor feed at a point in time: live, estimated (with the operator source(s) currently down), or no data (no recent events). Drives the status indicator and the explanatory banner.
- **Navigation context**: The shell state the dispatcher works within: active corridor, active section, current time, data-state badge, and signed-in user identity.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A dispatcher opening the console sees the current corridor fleet, ordered leader-first with each bus's state and headway, within 5 seconds of the view loading.
- **SC-002**: The displayed fleet reflects a new snapshot within one refresh cadence (about 5 seconds) of that snapshot becoming available, with no manual reload.
- **SC-003**: In a snapshot containing bunched buses and gaps, a dispatcher can identify every bunched bus and every gap, and the summary counts match the snapshot exactly (100% agreement).
- **SC-004**: For every source-status condition (live, estimated, no data), the console shows the correct indicator, and the explanatory banner appears only for estimated and no-data states.
- **SC-005**: Estimated data is labeled on affected buses and never raises an alert, verified across estimated-state snapshots.
- **SC-006**: When the backend is unreachable, the console keeps showing the last snapshot with a stale-data indicator and recovers automatically once the backend responds, without any crash or blank view.
- **SC-007**: Every operational state and data-quality condition is conveyed in text as well as visually, so the information is available without relying on color.

## Assumptions

- This story covers Turn 1 scope only: a read-only fleet view driven by periodic polling at roughly 5-second cadence (matching the simulator step). Live push/streaming updates and a sub-2-second refresh are deferred to a later turn.
- The single active corridor for this story is the pilot corridor C6-008, direction 1. Multiple corridors, the second direction, and short-turning are out of scope.
- There is no geographic or interactive map in this story; the fleet is presented as an ordered list with position and headway values.
- Recommendations and any approve/discard actions are out of scope (a separate story); the console is observation-only here.
- Authentication, login, role-based access control, and any auth UI are out of scope for this story. The displayed user identity and role are presentational context only; the console never decides access control. The sidebar shows the dispatcher role's sections.
- The no-data threshold is assumed to be "no corridor events for more than 2 minutes," consistent with the styling reference banner text.
- The console depends on the backend read API (the corridor snapshot and source-status feeds) being available; this story is blocked by that backend work.
- The US-03 desktop styling specification (sidebar, header, badge, banner, roles, data states) is the authoritative visual/interaction design reference for the shell; this specification captures the user-facing behavior, not the visual implementation.
- Historical charts and quality-indicator (manager-role) views are out of scope for this story.
