# 001-base-simulator — Verification results

Independent verification of story 001 (turn 1, "Data and minimal loop"), 2026-11-18.
Built by the Kiro agent factory (Spec Kit: spec → plan → tasks → implement), gated by the
data owner, and verified by Claude with real executions (not by reading the code).

## Status

| Item | Result |
|---|---|
| Tasks | 25/25 done (`tasks.md`) |
| Tests | 91 passed, coverage 89.7 % (host, stack up) · in image: all pass, 3 isolation tests skip by design (need the host docker CLI) |
| Event contract | `contracts/turn1-events` v1.0.0 (ADR-0001/0002) |
| Read contract | `contracts/read` v1.0.0 (ADR-0003), 8 schemas, 18/18 fixtures valid |

## Real data behind the simulator (`data/reference/`, 29 KB, rebuilt byte-for-byte identical)

| Data | Value | Source |
|---|---|---|
| Corridor | C6-008 direction 1, Prado → La Libertad, 17 segments, 5.12 km, slopes up to 16.8 % | OSM + SRTM |
| Stops | 18 real stops, `P-883` … `P-900` | ArcGIS feeder stops |
| Trains at Prado | 511 weekday line-A arrivals (40 at 17:00) | GTFS Metro 2025 |
| Congestion factor | real ÷ free speed 0.46–0.57 by hour; **0.50 at 17:00** | SIMM |
| Demand | **634 trips/day** in direction 1 (= basin-6 2019 monthly mean / 30 × 343/1191 × 35/343) | MEData monthly passengers |
| Fleet | B-101…B-105 in service, B-106/B-107 reserve, capacity 40 | Design (anchored on Metro 2015 report) |

## Simulator run: 1 hour from 17:00, seed 42

| Check | Result |
|---|---|
| Determinism | Two runs with the same seed → byte-identical output |
| Contract | 3,986 events, **0 invalid** against `contracts/turn1-events` |
| Demand | 59 rider arrivals (47 at Prado) — matches the agreed ~66/h peak |
| Load | Max occupancy 8 / 40, **0 riders left behind** (the base case must not fill buses; crowding comes from scenarios in story 003) |
| Peak trip | ≈ 25 min average (22.9–29.6) — target 25 min ± 20 % |
| Isolation (SC-005) | With the `api` container stopped, `bronze.events` keeps growing (134 → 198 → 264), 0 rejections |

## Defects found by verification (all fixed)

- Plan invented stop ids (`S-001`…); the GeoJSON does contain the 35 real C6-008 stops.
- Travel-time formula multiplied by the SIMM factor instead of dividing (peak would have been faster than off-peak).
- Simulator used invented demand (30,000/20,000 riders/day, ~4× real) → replaced by 634/day from data.
- `docker-compose` command broke the simulator → ingestion pipe (folded YAML scalar).
- Pydantic models accepted numbers as strings; DB password was written in `docker-compose.yml`; `.env.example` was hidden by the `.env.*` ignore rule.

## Who built what

| Piece | Built by |
|---|---|
| Constitution, specs, plan, tasks, reference data, containers, simulator, both contracts | Kiro agents |
| Phase 3 (`.env`, `uv.lock` image, `tests` service, ingestion into bronze) | Claude — Kiro was out of credits that night; pending a Kiro `review-code` pass |

## How to run it

```bash
cp .env.example .env            # set POSTGRES_PASSWORD
docker compose down -v          # fresh database (same seed replays the same event ids)
docker compose up -d --build    # db + ingestion (simulator | ingestion) + api
docker compose --profile tools run --rm tests
```
