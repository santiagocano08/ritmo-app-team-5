# Tasks: Active Recommendations in the Dispatcher Console

**Input**: `/specs/012-console-recommendations/` (plan.md, spec.md, research.md, data-model.md, contracts/recommendations-response.md, quickstart.md)

**Tests**: ON by default. Neither spec nor constitution opts out. Tests MUST be written and MUST FAIL before implementation.

**Organization**: One user story (US1, P1, MVP). Backend in `src/api/`, console in `src/frontend/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: different files, no dependencies on incomplete tasks.

## Phase 1: Setup

- [X] T001 Confirm no data-contract impact: check that Q13 in `docs/data-contract.md` and `contracts/read/fixtures/c1_bunching/recommendation.json` still validate against `contracts/read/recommendation.schema.json` v1.1.0; change nothing under `docs/` or `contracts/`.

## Phase 2: Foundational (blocking)

**Purpose**: contract types both sides depend on (Contract-First, Principle II).

- [X] T002 Add Pydantic V2 envelope models in `src/api/routers/corridor_read.py`: `status` a `Literal["ok","stale","no_data"]`, `corridor_id`, `recommendations` list of `RecommendationV110` (from `src/pulsoflota/models/read/recommendation.py`) with `extra="forbid"`; ok variant `max_length=3`; stale and no_data variants `max_length=0` (mirror `NoDataSourceStatus`).
- [X] T003 [P] Add TypeScript envelope types (`RecommendationsResponse`, status union, recommendation item from the published contract) in `src/frontend/src/api/types.ts`, strict, no `any`.

**Checkpoint**: contract defined; story work can begin.

## Phase 3: User Story 1 - See active recommendations next to the live corridor (P1) 🎯 MVP

**Goal**: «Recomendaciones» panel in *Central en vivo* backed by a read-only endpoint.

**Independent Test**: with proposed recommendations, one card per item (max 3, by rank) shows all FR-007 fields; no button applies or discards; stale, empty and no-data messages render.

### Tests (write first, must FAIL)

- [X] T004 [P] [US1] Unit tests for the Q0 read with `age_s` and the Q13 read (only `proposed`, ordered by `rank`, `LIMIT 3`, parameterized SQL, no write statements) in `src/api/tests/unit/test_recommendation_reads.py`.
- [X] T005 [P] [US1] Integration tests for `GET /api/v1/corridor/{corridor_id}/recommendations` in `src/api/tests/integration/test_recommendations_endpoint.py`: `ok` (≤3 items, rank order, more than 3 stored returns 3, non-proposed excluded), `stale` when `age_s > 15` with `[]`, `no_data` with no snapshot, `no_data` for a corridor other than C6-008, 200 for all states, non-GET rejected.
- [X] T006 [P] [US1] Contract test that the envelope and the c1_bunching fixture validate against the models in `src/api/tests/contract/test_recommendations_contract.py`.
- [X] T007 [P] [US1] Unit tests for the five action labels (Retener, Despachar reserva, Ajustar salida, Saltar parada, Reducir velocidad), saving text («−55 s de espera») and the expiry format «Vence HH:MM» with no host-TZ dependency in `src/frontend/tests/recommendations/labels.test.ts`.
- [X] T008 [P] [US1] Component tests for `RecommendationCard` (all FR-007 fields, duration omitted when null, «En conflicto» marker, markup reason shown literally as text, no button) in `src/frontend/tests/recommendations/RecommendationCard.test.tsx`.
- [X] T009 [P] [US1] Component tests for `RecommendationsPanel` states (list of ≤3 cards, «Sin recomendaciones activas», «Datos desactualizados: no se muestran recomendaciones», shared no-data message, no apply/discard control) and 5 s `refetchInterval` in `src/frontend/tests/recommendations/RecommendationsPanel.test.tsx`.

### Implementation: backend

- [X] T010 [US1] Add a Q0 read returning the latest snapshot id and `age_s = clock_timestamp() - committed_at` (wall time, never `as_of_ts`) in `src/api/reads/gold_reads.py`; leave `latest_snapshot_id` untouched. Parameterized SQL, `dict_row`.
- [X] T011 [US1] Add the Q13 read in `src/api/reads/gold_reads.py`: stored `recommendation` docs where status is `proposed`, ordered by `rank`, `LIMIT 3`; no recomputation, no writes.
- [X] T012 [US1] Implement the route `GET /api/v1/corridor/{corridor_id}/recommendations` in `src/api/routers/corridor_read.py`: `no_data` + `[]` if no snapshot or corridor ≠ C6-008; `stale` + `[]` if `age_s > 15`; else `ok` with Q13 run after Q0 and each doc validated with `RecommendationV110`; invalid stored docs follow the existing generic 500 with `correlation_id`. GET only (depends on T002, T010, T011).

### Implementation: console

- [X] T013 [P] [US1] Create `src/frontend/src/components/recommendations/labels.ts`: action label map, saving formatter, and «Vence HH:MM» reusing the header clock formatter style (`es-CO`, `hour12: false`; TZ pinned by vite test env, no `toLocaleTimeString` host dependency).
- [X] T014 [P] [US1] Add `getRecommendations(corridorId)` in `src/frontend/src/api/client.ts` using the existing client pattern (depends on T003).
- [X] T015 [US1] Create `src/frontend/src/hooks/useRecommendations.ts`: TanStack Query `useQuery` with `refetchInterval: 5000`, like `useSourceStatus.ts`; no `useEffect` fetching (depends on T014).
- [X] T016 [P] [US1] Create `src/frontend/src/components/recommendations/RecommendationCard.tsx`: action, bus, stop, optional duration, reason as a React text child (never `dangerouslySetInnerHTML`), saving, existing `QualityTag` from `src/frontend/src/components/fleet/QualityTag.tsx`, expiry, «En conflicto» when `conflicts_with` is not empty; no buttons (depends on T013).
- [X] T017 [US1] Create `src/frontend/src/components/recommendations/RecommendationsPanel.tsx`: heading «Recomendaciones», cards by rank, empty/stale/no-data messages (reuse `src/frontend/src/components/status/EmptyState.tsx` for no-data) (depends on T015, T016).
- [X] T018 [US1] Place the panel right of the fleet list (about 400 px wide on desktop) in *Central en vivo* in `src/frontend/src/App.tsx` (depends on T017).
- [X] T019 [P] [US1] Add the mock fixture from `contracts/read/fixtures/c1_bunching/recommendation.json` to `src/frontend/src/mocks/fixtures.ts` and an MSW handler for the endpoint in `src/frontend/src/mocks/handlers.ts` so mock mode shows the card.

### Verification

- [X] T020 [US1] Run only the new backend tests with uv per `quickstart.md` (T004–T006 files) and confirm they pass.
- [X] T021 [US1] Run the frontend checks in the Node container without `-e TZ` (`vitest run tests/recommendations`, `eslint src tests --ext .ts,.tsx --max-warnings 0`, `tsc --noEmit`) and confirm they pass.

**Checkpoint**: US1 complete and independently testable.

## Phase 4: Polish

- [X] T022 Confirm `docs/data-contract.md` and `contracts/` are unmodified (git diff) and that no write path or apply/discard control was added.

## Dependencies & Execution Order

- Setup → Foundational (T002, T003) → US1 → Polish.
- Tests T004–T009 first and failing; then T010, T011 → T012 (backend); T013 → T016; T014 → T015 → T017 → T018 (console); T019 any time after T003.
- Backend and console tracks are independent until manual mock-mode check.

## Parallel Example

```text
T004, T005, T006, T007, T008, T009   (different test files)
T010 + T013 + T014 + T019            (backend reads, labels, client, mocks)
```

## Implementation Strategy

MVP is US1 (the only story). Do Setup and Foundational, write failing tests, build backend then console (or in parallel), run the scoped test commands, stop and validate in mock mode.
