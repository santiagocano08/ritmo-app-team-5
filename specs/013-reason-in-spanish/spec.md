# Feature Specification: Recommendation Reason in Spanish

**Feature Branch**: `013-reason-in-spanish`

**Created**: 2026-11-26

**Status**: Draft

**Input**: User description: "Decision model writes the recommendation reason in Spanish (data, follow-up of #70)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read each recommendation's reason in Spanish (Priority: P1)

As a dispatcher, I want each recommendation's reason in Spanish, so the whole console reads in one language.

**Why this priority**: The recommendations panel shows an English sentence inside a Spanish screen. This is the only story of the feature.

**Independent Test**: Generate one recommendation of each action type and check that its reason is the Spanish sentence for that action, naming the action, the bus, the stop (when the action has one) and the saving per rider.

**Acceptance Scenarios**:

1. **Given** the model recommends holding a bus, **When** the reason is written, **Then** it reads like `retener B-103 60 s en P-888 ahorra 22 s por pasajero`.
2. **Given** the model recommends slowing down, dispatching a reserve, adjusting a departure (advance or delay) or skipping stops, **When** the reason is written, **Then** it follows the Spanish template for that action listed in the requirements.
3. **Given** the contract fixtures for `recommendation`, **When** they are validated against the recommendation schema, **Then** they pass and their reasons are in Spanish with the same templates.

### Edge Cases

- Numbers keep today's formatting (for example `18.2 s`, `60 s`).
- Reasons already stored or archived in English are not changed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The model MUST write every published recommendation `reason` in Spanish, built from the same fields as today and never parsed back from text.
- **FR-002**: The reason MUST use these templates:
  - hold: `retener {bus} {s} s en {stop} ahorra {n} s por pasajero`
  - slow down: `reducir la velocidad de {bus} un {pct} % durante {min} min en {stop} ahorra {n} s por pasajero`
  - reserve dispatch: `despachar la reserva {bus} ahorra {n} s por pasajero`
  - adjust departure: `adelantar {s} s la próxima salida desde {stop} ({bus}) ahorra {n} s por pasajero` or `retrasar {s} s la próxima salida desde {stop} ({bus}) ahorra {n} s por pasajero`
  - skip stop: `saltar las paradas sin cola para {bus} desde {stop} ahorra {n} s por pasajero`
- **FR-003**: The reason MUST name the action, the bus, the stop (when the action has one) and the saving per rider.
- **FR-004**: Number formatting MUST stay as it is today.
- **FR-005**: The `reason` of every contract fixture for `recommendation` MUST be in Spanish with the same template and still validate against the recommendation schema, which does not change.
- **FR-006**: The data contract (recommendation section) MUST state in one line that `reason` is plain Spanish text for the dispatcher, built from the same fields as the document.
- **FR-007**: Existing tests that assert a reason MUST expect the Spanish text, and the data unit tests MUST stay green.
- **FR-008**: The data lab's English-to-Spanish translation of reasons MUST be left as is, so it keeps translating reasons from runs archived before this change.

### Key Entities

- **Recommendation**: a suggestion for the dispatcher with an action, a target bus, an optional stop, a saving per rider and a free-text `reason`. Only the language of `reason` changes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % of recommendations published after this change have a Spanish reason.
- **SC-002**: 100 % of contract fixtures for `recommendation` validate against the unchanged schema.
- **SC-003**: The dispatcher sees no English sentence in the recommendations panel for new recommendations.

## Assumptions

- Contract impact: `reason` stays free text, so no schema version change. Only the data contract section on recommendations gains one line, and the fixture example text changes.
- Out of scope: translating reasons already stored in `gold.recommendation` or in archived runs, and any console change (the console renders `reason` as it comes).
- The Spanish wording is the one the data lab already uses.
