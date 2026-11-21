# Drill rerun: before and after feature 003

Same drill as 2026-11-18, same faults (F1 `stop api`, F2 `stop db`, F3 `kill -9` of ingestion), same
windows: start, 45 s, F1 30 s, 25 s, F2 30 s, 90 s, F3, 90 s, end. One sample every 2 s. Same columns:
`t_s,events,max_event_ts,ingestion_lag_s,duplicates,other_rejections,ingestion,api,db`.

## Lag-reading rule (the same for both columns)

- *Lag after F2* = `ingestion_lag_s` of the last sample strictly before the F3 mark.
- *F3 lag* = `ingestion_lag_s` of the last sample of the observation window.

The 2026-11-18 report quoted 125 s and 204 s, read a few seconds off (t=232 and t=312); the fixed rule is
used for both columns and gives 120 s and 209 s for the baseline.

## Before and after

| Metric | Before (2026-11-18) | After (rerun) |
|---|---|---|
| Ingestion survives F2 (no exit, no restart) | No: exited, restarted | Yes: `RestartCount` 0 and the same `StartedAt` before and after F2; 8 `db_retry` lines and one `db_recovered` (outage 32.1 s) |
| Lag after F2 | 120 s (t = 227 s, F3 mark at 228 s) | 1 s (t = 228 s, F3 mark at 229 s) |
| F3 lag | 209 s (t = 316 s) | 90 s (t = 320 s). Not fixed: F3 still restarts ingestion and replays the stream (458 duplicates by t = 320 s); the 90 s are the observation window, as in the baseline (209 - 120 = 89 s) |
| Duplicates counted as rejections | 971 (65 %) | 0. The 468 replay duplicates of F3 are reported on their own (`duplicates`) and `other_rejections` is 0 |
| Real rejection rate | not available | 0 % (0 rejections / (1154 accepted + 0)) |
| `unhealthy` transitions | none | 2: ingestion `unhealthy` at 12:20:43.6Z (F2, `healthy` again at 12:21:15.9Z) and at 12:22:55.9Z (F3, still `unhealthy` at the end of observation, 12:24:09Z) |
| Bronze integrity | 525 of 525 | 1154 of 1154 (`count(*)` = `count(distinct event_id)`) |

Baseline files: `docs/ops/drill-baseline/`. Rerun raw files: `drill-out/` (local, not committed).

## Reading the rerun

- Windows, columns (the same English header), sampling (every 2 s, about 2.4 s apart in practice) and the
  lag-reading rule are the same as the baseline; the F3 mark was at 229 s instead of 228 s.
- What improved: F2 no longer kills ingestion (no restart, no replay, no loss); the lag after F2 fell from
  120 s to 1 s; duplicates are no longer rejections; the healthcheck changed state in both F2 and F3.
- What did not improve: F3 (a crash of the ingestion process) still restarts the container and replays the
  stream from the start. The data is stale for the rest of the window and the service is `unhealthy`. The F3
  lag fell from 209 s to 90 s only because F2 no longer leaves a 120 s lag before F3 starts.
- The ingestion `unhealthy` during F2 starts 5 s after the database stopped because the probe cannot read
  the view (`unhealthy: check failed`), not because the data was already 15 s old.
- Bronze rows grew from 518 at t = 109 s to 1154 at t = 228 s: after F2 ingestion stored the backlog held in
  the pipe and kept the event order (the live outage test checks the order).
