---
inclusion: fileMatch
fileMatchPattern: ["contracts/**", "ingestion/**", "rules/**", "simulator/**", "**/*ingest*.py", "**/*contract*.py"]
---

# Data profile — Development (ingestion, contract and quality rules)

Used by `implement-code` when it writes data code. Owner: data owner (see CODEOWNERS).

## Turn 1 scope (takes precedence over `data-contracts.md` and `realtime-ingestion.md`)

According to `docs/turns-ritmo.md`, turn 1 builds the minimum that closes the loop:

| Topic | Turn 1 | Deferred (evolution) |
|---|---|---|
| Containers | `docker-compose`: PostgreSQL, simulator/ingestion and API as separate services (Principle III) | `database-redis` service, production hardening |
| Transport | The simulator writes to the PostgreSQL bronze table; notifications with `LISTEN/NOTIFY` | Redis Pub/Sub or a broker |
| Database | PostgreSQL only, `bronze`, `silver`, `gold` schemas | PostGIS, TimescaleDB |
| Position | Distance along the corridor in meters, no geometry | Coordinates and geometry |
| Volume | The exercise fleet (5 + 2 buses, 5 s step) | 1,000 events/s, P99 ≤ 500 ms |
| Data faults | Duplicates and source outage | Out of order, impossible position, bursts |

Do not implement deferred items "just in case". If a task asks for one, flag it as outside the turn.

## Implementation rules

- **Contract first.** Pydantic V2 models are derived from the approved JSON Schema in `contracts/`.
  Do not invent fields. If a new one is needed, stop and ask `data-design` for an ADR.
- **Boundary validation.** Every event is validated on entry. If invalid, it is rejected (`422` in
  the API) and stored in the rejections table with its **reason** and the original message.
- **Bronze is immutable.** Insert only, never update or delete. Silver and gold are recomputed from
  bronze.
- **Idempotency.** Every event has a deduplication key (source + event id). Inserting the same event
  twice does not change the result.
- **Two timestamps:** event time and arrival time. Calculations use event time.
- **Source outage.** If a bus does not report for more than 2 min, it becomes "Estimated" and
  **does not trigger alerts** on its own.
- **Quality rules = deterministic code** in `rules/`, with tests. An LLM never judges data.
- **Lineage.** Every gold row records the rules version and the range of bronze events it came from.
- **No agents on the real-time path** (Principle III).
- Always parameterized queries. No secrets in code or in versioned `.env` files.
