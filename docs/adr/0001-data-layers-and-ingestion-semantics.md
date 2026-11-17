# ADR-0001: Data Layers and Ingestion Semantics (Turn 1)

- Status: Accepted
- Decided by: data owner, 2026-11-17
- Date: 2026-11-17
- Turn: Turn 1 — Data and Minimal Loop (active)
- Addresses: Principle II (Contract-First and Data Ownership), Principle III (Isolated Ingestion and Deterministic Real Time), RNF-3.3.1 (boundary validation; reject 100 % of packets without a valid schema), turn-1 risk (data integrity: malformed, duplicated or missing data contaminates the metric and the recommendations)

## Context

Turn 1 closes the minimal loop (detect → recommend → approve → execute → measure) for corridor
C6-008 (Prado station, direction 1) with a 5 + 2 bus fleet and a 5 s simulation step. The turn-1
risk is Level 1 data integrity: a duplicated packet double-counts a bus, a silent source must not
fabricate a position, and a malformed packet must never reach the P(board ≤ t) / EWT metric or a
recommendation. Ingestion must also keep capturing if the API/web is down (Principle III). Volume is
tiny (the exercise fleet), so the design optimizes for correctness, auditability and idempotency,
not throughput.

## Options considered (max. 3)

1. **Layered PostgreSQL schemas (bronze / silver / gold + rejections), insert-only bronze, `(source, event_id)` dedup.**
   - Pros: clear separation of raw / derived / aggregated; bronze immutability is trivial to test; lineage lives as explicit columns on gold; one engine, no extra services.
   - Cons: four schemas to maintain; silver/gold must be recomputed when rules change.
2. **Bronze append-only + silver/gold as materialized views refreshed on demand.**
   - Pros: less code; derivation is declarative.
   - Cons: refresh semantics and concurrent-read consistency are fiddly at this stage; lineage is harder to assert explicitly; materialized views blur the "bronze is the only source of truth" rule.
3. **Single wide table with a `status` column and no layering.**
   - Pros: simplest to build.
   - Cons: no real immutability or lineage; hard to audit the payment metric; violates per-layer data ownership (Principle II); a bad row can be updated away silently.

## Decision

Adopt **option 1**. It mitigates the turn-1 integrity risk with the least moving parts while giving
replay, dedup, a clean rejection audit and explicit lineage. Everything runs in PostgreSQL only
(turn-1 stack); Redis/PostGIS are deferred. Rejections live as a table (`bronze.rejections`) inside
the bronze schema rather than as a fourth schema (see Gate decisions).

### Layers

- **bronze** — immutable, insert-only raw events that passed boundary validation. Never `UPDATE` or
  `DELETE`. The only source of truth for replay and payment audit.
- **silver** — validated/derived state recomputed from bronze: deduped positions, per-bus current
  state including the "Estimated" flag, stop dwell events.
- **gold** — aggregates that feed the metrics and the console: headway, mean wait and EWT per
  stop/window.
- **bronze.rejections** — a table inside the bronze schema for every event rejected at the boundary
  or discarded as a duplicate, stored with its **reason** and the **original message** (see
  `rejection.schema.json`). A rejected event never reaches the validated bronze events table.

### Ingestion semantics

- **At-least-once delivery.** The simulator may resend (e.g., on retry); ingestion tolerates it.
- **Idempotency key = `source` + `event_id`.** A unique constraint on bronze makes the second insert
  fail; the duplicate is discarded and recorded in `bronze.rejections` with reason `duplicate_event`.
  Re-ingesting the same batch leaves bronze, silver and gold unchanged.
- **Two timestamps.** `event_ts` (when the event occurred, from the message) and `arrival_ts` (stamped
  by ingestion on receipt). **All calculations use `event_ts`.** `arrival_ts` is for latency/audit
  only.
- **Duplicates:** same `source + event_id` → discard, record in `bronze.rejections` with reason
  `duplicate_event`.
- **Source outage:** if a bus does not report for more than **2 min**, its state becomes
  **"Estimated"** and it **does not trigger alerts** on its own. (Out-of-order, impossible position
  and bursts are turn 3.)

### Storage

- **PostgreSQL only.** Schemas: `bronze`, `silver`, `gold`. Rejections are a table (`bronze.rejections`)
  inside the bronze schema, not a fourth schema.
- **bronze is insert-only** (no `UPDATE`/`DELETE`). Silver and gold are recomputed from bronze.
- **No time partitioning or retention policy in turn 1.** The exercise fleet (7 buses, 5 s step) is
  trivial volume; partitioning adds complexity without mitigating the turn-1 risk. Bronze retention:
  none in turn 1 (deferred to turn 3).

### Lineage

- **Every gold row records `rules_version` and `max_bronze_id`** (the highest bronze row id it was
  derived from), not a full bronze range. A gold aggregate can thus be traced to its rules version
  and to the bronze events up to that point. Quality rules live as deterministic, tested code in
  `rules/` (never an LLM judgment).

### Container constraint (Principle III)

- `docker-compose` defines **separate services** for PostgreSQL, the simulator/ingestion, and the
  API.
- The ingestion container **writes directly to the bronze table** and **keeps writing if the API/web
  is down.** The API reads from silver/gold and uses `LISTEN/NOTIFY` for live updates; it is not on
  the capture path. (Redis Pub/Sub and a broker are turn 3.)

## Consequences

- **Easier:** bronze immutability gives replay and payment audit; the dedup key prevents
  double-counting; explicit lineage makes the metric reproducible; isolation keeps capture alive
  when the API is down.
- **Harder:** three schemas to keep coherent; silver/gold recomputation needed when rules change; no
  partitioning means bronze grows unbounded (acceptable for turn-1 volume; addressed in turn 3).

## Affected contract

`contracts/turn1-events/envelope.schema.json`, `bus_position.schema.json`,
`stop_arrival.schema.json`, `stop_departure.schema.json`, `rider_arrival.schema.json`,
`driver_confirmation.schema.json`, `incident_report.schema.json`, `rejection.schema.json` — all
**v1.0.0 (new)**. See ADR-0002 for the contract shape.

## Evolution

- Time partitioning and per-layer retention (turn 3, high volume).
- Redis Pub/Sub transport, PostGIS geometry, TimescaleDB (turn 3).
- Out-of-order, impossible-position and burst faults (turn 3).
- HMAC signature and per-message checksum; fare-collection events (turn 2).

## Gate decisions

Decided by the data owner at the contract and data architecture gate, 2026-11-17:

- **Rejections live in `bronze.rejections`** — a table inside the bronze schema, not a fourth schema.
- **Lineage on gold is `rules_version` + `max_bronze_id` only** (the highest bronze row id the
  aggregate was derived from), not a full bronze range.
- **Duplicates go to `bronze.rejections` with reason `duplicate_event`** (wording confirmed).
- **Bronze retention: none in turn 1** (no retention policy; deferred to turn 3).
