# Drill baseline, 2026-11-18

Evidence of the incident drill run on 2026-11-18 on a copy of story 001, before feature 003. It is the
"before" column of `docs/ops/drill-rerun.md`.

## What the drill did

Three faults, same windows in the rerun: start, 45 s, **F1** `stop api` for 30 s, 25 s, **F2** `stop db`
for 30 s, 90 s, **F3** `kill -9` of the ingestion process, 90 s, end (about 329 s in total). One sample
every 2 s. Seed 42.

## Files

| File | Content |
|---|---|
| `metrics.csv` | One sample every 2 s: `t_s,events,max_event_ts,ingestion_lag_s,duplicates,other_rejections,ingestion,api,db` |
| `events.log` | The eight marks of the run (START, F1 and F2 injected and end, F3 injected, END observation, CLEANED) |
| `rejections.txt` | `bronze.rejections` grouped by reason at the end: `duplicate_event,971` |
| `restarts.txt` | Restart count per container: api 0, db 0, ingestion 3 |

## Translation

The original files are in Spanish and stay in `.drill-input/` (local only, never committed). **Only the
header line of `metrics.csv` and the labels of `events.log` and `restarts.txt` were translated** in these
repository copies. Timestamps, seconds and values are unchanged, and the data rows of `metrics.csv` are
byte for byte as captured (a test compares them with the original when it is present locally).

Header mapping (old to new): `lag_ingesta_s` to `ingestion_lag_s`, `dup` to `duplicates`,
`otros_rech` to `other_rejections`. The original Spanish script ran on a copy of the repository.

## Lag-reading rule (the same for baseline and rerun)

- *Lag after F2* = `ingestion_lag_s` of the last sample strictly before the F3 mark (228 s): t = 227 s,
  **120 s**.
- *F3 lag* = `ingestion_lag_s` of the last sample of the observation window: t = 316 s, **209 s**.

The 2026-11-18 report quoted 125 s and 204 s, read a few seconds off (t=232 and t=312); the fixed rule is
used for both columns.
