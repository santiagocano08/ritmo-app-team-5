# Post-mortem: incident drill of 2026-11-18

Blameless. It describes what the system did, not who built or ran it.

## Summary

On 2026-11-18 a drill injected three faults into the stack of story 001: F1 stopped the API, F2 stopped
the database for 30 s, F3 killed the ingestion process. F1 had no effect on capture. F2 and F3 made
ingestion exit and restart, replay the whole simulator stream from the start, and count the replay as
rejections. Bronze stayed intact (525 of 525 rows), but the data was late and the rejection metric was
wrong. Nothing in the stack signalled that data had stopped.

## Timeline

Times are seconds from the start of the drill (source: `docs/ops/drill-baseline/events.log`).

| t | Event |
|---|---|
| 0 s | Stack started (seed 42, 5x real time) |
| 51 s | F1: `docker compose stop api` |
| 82 s | F1 ends: API started again (30 s window) |
| 107 s | F2: `docker compose stop db` |
| 138 s | F2 ends: database started again (31 s outage) |
| 227 s | Last sample before F3: ingestion lag 120 s |
| 228 s | F3: `kill -9` of the ingestion process |
| 316 s | Last sample of the observation window: ingestion lag 209 s |
| 318 s | End of observation |

## Impact

- F2 lasted 31 s. Ingestion exited when the database went away and restarted three times in total
  (`restarts=3`); every restart replayed the simulator stream from the start.
- Ingestion lag after F2 was 120 s and the F3 lag was 209 s, read with one fixed rule for the baseline and
  the rerun (last sample strictly before the F3 mark, and last sample of the observation window). The
  2026-11-18 report quoted 125 s and 204 s, read a few seconds off; the fixed rule gives 120 s and 209 s.
- The replay produced 971 `duplicate_event` rows in `bronze.rejections`. They were counted as rejections,
  which showed a rejection rate of 65 % while no event had failed the contract.
- Bronze integrity held: 525 of 525 rows, no duplicate stored, no row lost.
- No alert, health status change or log line told an operator that data had stopped.

## Root causes

1. **No reconnect and restart-and-replay.** Ingestion treated a lost database connection as fatal. Docker
   restarted the container, and the simulator started its stream again from the first event.
2. **Duplicates counted as rejections.** The replayed events were rightly discarded, but the tally put
   them in the same count as events that failed the contract.
3. **No freshness signal.** Nothing measured the age of the newest bronze insert, so a stopped feed looked
   the same as a quiet one.

## What went well

- F1 isolation: stopping the API did not touch ingestion (Principle III).
- Bronze stayed immutable and idempotent: the replay was discarded by the deduplication key, not stored.
- The drill itself was scripted and sampled every 2 s, which made the numbers above possible.

## Actions

| Action | Story |
|---|---|
| CI that runs the tests, the contract fixtures and the compose build on every pull request, so a red build stops the line | US1 |
| Retry the current line through a database outage with a bounded, logged policy; no exit, no replay | US2 |
| Report duplicates apart from rejections; real rejection rate = rejections / (accepted + rejections) | US2 |
| Read-only view `ops.ingestion_health` and an `ingestion` healthcheck that turns `unhealthy` when inserts stop | US3 |
| Runbook, SLI/SLO proposal and a rerun of the same drill with a before/after table | Documentation |

## Lessons

- A fault in one dependency should pause a stage, not restart the whole pipeline.
- A counter is only useful if each number means one thing. Duplicates and contract rejections are different.
- "Is data still arriving?" needs its own signal. Container state says nothing about it.
- Compare drills with the same windows, columns and reading rule, or the comparison proves nothing.
