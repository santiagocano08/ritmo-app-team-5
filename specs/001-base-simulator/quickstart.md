# Quickstart — Turn-1 Run Environment and Base Simulator

**Feature**: 001-base-simulator | **Turn**: 1 (active) | **Date**: 2026-11-17

A validation/run guide — not an implementation. It proves the feature works
end-to-end against the spec's success criteria, with prerequisites, commands
and expected outcomes. Implementation detail belongs in `tasks.md` and the
implementation phase.

## Prerequisites

- Docker Engine + `docker-compose` (for the three-service run environment).
- `uv` (Astral) for the Python environment.
- Raw sources present in `data/raw/` (git-ignored locally). If a required source
  is missing, `make reference` fails with a clear message naming it.
- Python 3.12+.

## Setup (one time)

```bash
uv sync                       # install deps from pyproject.toml + uv.lock
make generate                 # regenerate Pydantic V2 models from contracts/turn1-events
make reference                # build data/reference/ from data/raw/ (<1 MB, reproducible)
```

`make generate` runs `datamodel-codegen` over `contracts/turn1-events/*.schema.json`
into `src/pulsoflota/models/`. CI asserts the committed file matches a fresh
generation (drift fails the gate).

## Build order (matches the plan)

1. **Reference data** → `make reference` (US-1).
2. **Run environment** → `make up` (US-2).
3. **Ingestion into bronze** → exercised via the integration tests (US-3).
4. **Base simulator** → `make test` covers it; run it directly below (US-4).

## Validation scenarios

### V1 — Reference data is reproducible and complete (SC-007, FR-001..FR-008)

```bash
make reference
cp -r data/reference /tmp/ref_a
make reference
diff -r /tmp/ref_a data/reference && echo "byte-identical OK"
du -sh data/reference            # expect < 1 MB
```

Expected: the two builds are byte-identical; total size under 1 MB; `segments.csv`
has 17 rows; `congestion_factor.csv` has 24 rows (mean SIMM speed ÷ length-weighted
corridor free-flow speed; the 0.43–0.56 band is an expected sanity check, not a
hard gate — values outside it emit a warning and are kept); `SOURCES.md` has one
line per file.

Automated: `pytest tests/unit/test_reference_build.py`.

### V2 — Run environment is isolated (SC-005, SC-008, FR-009..FR-011)

```bash
make up                                      # db + ingestion + api start
curl -sf http://localhost:8000/healthz       # expect {"status":"healthy"}
docker compose stop api
# wait ~20 s, then:
docker compose exec -T db psql -U pulsoflota -d pulsoflota \
  -c "SELECT count(*) FROM bronze.events;"   # still growing
docker compose start api
make down
```

Expected: three separate services start with one command; the health endpoint
reports healthy; stopping `api` does not stop `ingestion` and `bronze.events`
keeps growing (Principle III).

Automated: `pytest tests/integration/test_health.py tests/integration/test_isolation.py`.

### V3 — Ingestion validates, rejects and dedupes (SC-002..SC-004, FR-012..FR-016)

Feed crafted valid, invalid and duplicate envelopes through
`src.ingestion.bronze.ingest(conn, envelope)` (no live simulator):

- A valid envelope lands in `bronze.events` exactly once, with `arrival_ts`
  stamped by ingestion.
- Each invalid envelope in `contracts/turn1-events/examples/invalid/` lands in
  `bronze.rejections` with the matching reason.
- The same `source` + `event_id` twice → first accepted, second discarded to
  `bronze.rejections` with reason `duplicate_event`; `bronze.events` unchanged.
- No `UPDATE`/`DELETE` on bronze (insert-only).

Automated:
- Contract: `pytest tests/contract/test_contract_examples.py` (every valid
  example passes, every invalid example is rejected with the expected reason).
- Integration: `pytest tests/integration/test_bronze_ingest.py
  tests/integration/test_bronze_immutable.py`.

### V4 — Simulator is deterministic, realistic and capacity-safe (SC-001, SC-006, FR-017..FR-026)

```bash
python -m src.simulator.main --seed 42 --duration 1800 > /tmp/run_a.jsonl
python -m src.simulator.main --seed 42 --duration 1800 > /tmp/run_b.jsonl
diff /tmp/run_a.jsonl /tmp/run_b.jsonl && echo "deterministic OK"
sha256sum /tmp/run_a.jsonl
```

Expected: byte-identical output for the same seed (identical hash); every line
validates against the contract; a peak-hour trip completes in ~25 min within
±20 %; occupancy never exceeds 40; surplus riders are `rejected`.

Automated:
- `pytest tests/unit/test_simulator_determinism.py` (same seed → identical hash).
- `pytest tests/unit/test_simulator_capacity.py` (occupancy ≤ 40; rejected = surplus).
- `pytest tests/unit/test_simulator_travel_time.py` (peak trip ≈ 25 min ±20 %).

## Test suite and coverage (Gate 2, turn 1)

```bash
make test      # pytest + coverage
```

Expected: all tests pass, coverage > 80 %. Turn-1 gates only: Pydantic schema
validation (Gate 1) and tests + coverage (Gate 2). SAST/SCA, RBAC/JWT, HMAC and
the secret manager are turn-2 evolution and are **not** asserted here.

## Constitution alignment (quick check)

- Principle II (Contract-First): models generated from the contract; contract
  examples are the test fixtures.
- Principle III (Isolated ingestion): `api` down does not stop `ingestion` (V2).
- Principle V (Test-First): the scenarios above are the acceptance evidence.

## Evolution (not validated here)

Redis/PostGIS, 1,000 events/s, security turn-2 norms, silver/gold metrics,
scenario injectors, decision engine and the web console — deferred per
`docs/turns-ritmo.md`; see `research.md` §Evolution.
