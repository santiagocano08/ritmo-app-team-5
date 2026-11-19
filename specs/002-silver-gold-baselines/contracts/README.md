# Contracts — 002-silver-gold-baselines

This feature does **not** change any repository contract. `contracts/turn1-events/` and
`contracts/read/` v1.0.0 stay as they are (FR-025). Changing them needs a new ADR (ADR-0003
versioning rule).

The files here describe the interfaces this feature *adds* around those contracts:

| File | Interface | Consumer |
|---|---|---|
| [gold-read-access.md](gold-read-access.md) | How a reader finds the latest complete snapshot and its read objects in gold | Backend (query door) |
| [notify-channel.md](notify-channel.md) + [gold_snapshot_notify.schema.json](gold_snapshot_notify.schema.json) | `NOTIFY gold_snapshot` payload | Backend (push door) |
| [compute-and-refresh.md](compute-and-refresh.md) | `compute` CLI (one snapshot or a replay) and the `refresh` compose service | Operators, tests, the workshop |

Promoting the notification schema into `contracts/read/` is a data-owner decision. ADR-0003 names
"the gold channel" but defines no payload, so an ADR addendum would be needed. Until then, this
feature's tests validate every emitted payload against the schema in this directory.
