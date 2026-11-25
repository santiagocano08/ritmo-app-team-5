# Implementation Plan: Active Recommendations in the Dispatcher Console

**Branch**: `012-console-recommendations` | **Date**: 2026-11-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/012-console-recommendations/spec.md`

## Summary

Add a read-only `GET /api/v1/corridor/{corridor_id}/recommendations` endpoint that serves Q13 (stored, pre-validated `recommendation` v1.1.0 docs, max 3, `proposed` only) with an `ok | stale | no_data` envelope, and a «Recomendaciones» panel in *Central en vivo* that polls it every 5 s. No business rule is recomputed and nothing is written (Principle IV). Staleness uses wall time (`age_s` of Q0, §2.1).

## Technical Context

**Language/Version**: Python 3.12 (backend, `src/api/`); TypeScript strict + React 19 (`src/frontend/`)

**Primary Dependencies**: FastAPI, Pydantic V2, psycopg 3; Vite, Tailwind, TanStack Query, Vitest + Testing Library, MSW (existing mock mode)

**Storage**: PostgreSQL, `gold.recommendation` and `gold.snapshot_commits` (read-only)

**Testing**: pytest (`src/api/tests`), Vitest (`src/frontend/tests`)

**Target Platform**: `docker-compose` services `pulsoflota-backend`, `pulsoflota-frontend`

**Project Type**: web application (backend + frontend)

**Performance Goals**: change visible within 10 s of publication (5 s poll + delivery, SC-002)

**Constraints**: parameterized SQL only; reasons rendered as text; simulated-time expiry independent of host time zone; no write path

**Scale/Scope**: one corridor (C6-008), at most 3 cards

**Assumptions** (no open clarifications): a new Q0 read with `age_s` is added next to the existing `latest_snapshot_id`, which stays untouched for the other endpoints; invalid stored docs follow the existing read endpoints (generic 500 with `correlation_id`); the lane is Adaptive (read-only console visualization).

**Data contract impact**: none. Q13, `docs/data-contract.md`, `contracts/` and gold tables are unchanged. The response envelope is new and documented in `contracts/recommendations-response.md`. Verification must check that Q13 and the v1.1.0 fixture still validate.

## Constitution Check

| Gate | Result |
|---|---|
| I Risk-first | Pass. Read-only adaptive story; no open Level 1 risk added. |
| II Contract-first | Pass. Envelope contract defined before code; items reuse `RecommendationV110`. |
| III Isolated ingestion | Pass. Reads gold only; ingestion untouched; no AI or third-party call. |
| IV Human gate | Pass. No apply/discard control, no writes (FR-005, FR-010). |
| V Tests/gates | Pass. Tests planned for every FR-011 item; coverage > 80 %. |
| Turn 1 norms | Pass. Parameterized SQL, no secrets, generic errors. |

Post-design re-check: Pass, no violations.

## Evolution (deferred per `docs/turns-ritmo.md`)

Approve/discard (story 5b), RBAC/JWT (turn 2), alerts inbox, mobile layout, WebSocket push (turn 3).

## Project Structure

### Documentation

```text
specs/012-console-recommendations/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/recommendations-response.md
```

### Source Code (current Turn-1 tree)

```text
src/api/
├── reads/gold_reads.py            # + snapshot with age_s (Q0), recommendation docs (Q13)
├── routers/corridor_read.py       # + GET /corridor/{id}/recommendations, envelope models
└── tests/{unit,integration}/      # envelope states, order, limit, corridor

src/frontend/
├── src/api/{client.ts,types.ts}   # getRecommendations, envelope types
├── src/hooks/useRecommendations.ts
├── src/components/recommendations/{RecommendationsPanel,RecommendationCard}.tsx
├── src/components/recommendations/labels.ts   # action labels, expiry format
├── src/mocks/{fixtures.ts,handlers.ts}        # fixture from contracts/read/fixtures/c1_bunching/recommendation.json
└── tests/recommendations/
```

**Structure Decision**: extend the existing read router and gold reads (router validates, reads run SQL) and add one feature folder in the console, following the `fleet/` and `summary/` pattern.

## Complexity Tracking

No violations.
