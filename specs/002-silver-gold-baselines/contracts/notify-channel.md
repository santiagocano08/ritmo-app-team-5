# Notification channel `gold_snapshot` (push door, data side)

| Item | Value |
|---|---|
| Transport | PostgreSQL `LISTEN/NOTIFY` (ADR-0001, ADR-0003). No broker. |
| Channel | `gold_snapshot` |
| Emitter | the `refresh` service (and the `compute` CLI, see below), inside the cycle transaction via `pg_notify` |
| Payload | JSON text matching [gold_snapshot_notify.schema.json](gold_snapshot_notify.schema.json): `{"snapshot_id": "<uuid>"}` |
| Version | 1.0.0 (feature-local; see README for promotion) |

## Semantics

- **Exactly once per new snapshot.** PostgreSQL delivers the notification at `COMMIT`, so it always
  refers to a snapshot that is already readable (FR-038, SC-009).
- **Never for a failed cycle.** A rollback discards the notification (FR-040).
- **Never for a no-op recompute.** If the snapshot already exists (same `as_of_ts`,
  `rules_version` and `max_bronze_id`, research R5), nothing is inserted and nothing is notified.
- **At-most-once delivery to a listener.** A listener that is disconnected misses notifications. On
  reconnect it should read the latest snapshot with the query in
  [gold-read-access.md](gold-read-access.md). This is standard PostgreSQL behaviour, stated here so
  the backend does not assume a durable queue.
- The `compute` CLI notifies too, so a manual or replayed snapshot looks the same to listeners.
  `--no-notify` is available for bulk replays.
