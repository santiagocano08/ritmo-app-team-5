# Guards: impossible position and future-dated event

Three protections, one per layer. None changes a JSON Schema. Rationale and measurements: [../research.md](../research.md)
R9, R10, R11.

## G1. Ingestion range check (US5, FR-050, FR-051)

| Item | Rule |
|---|---|
| Applies to | event type `bus_position` after the envelope validated |
| Bound | `max(distance_along_m)` of `config.ref_stops` (5,119.4 m today); lower bound 0 is already enforced by the model |
| Outcome above the bound | rejected with reason `value_out_of_range`; one row in `bronze.rejections` with the original message; nothing in `bronze.events` |
| Exactly 0 or exactly the bound | accepted |
| Where the bound is read | the ingestion connection, `ingestion/route_bounds.py`; cached after the first non-empty read for the process |
| Bound unreadable (table empty, schema missing) | the event is **accepted**; the next read is tried no earlier than 5 s later; a log line `route_bound_unavailable` (fixed reason vocabulary, no connection data) is written once per outage |
| Database unreachable | not swallowed: the existing retry layer stores the same line after reconnecting (feature 003) |
| New dependency, new variable | none |

Test matrix (Phase 4): 99,999 m rejected with the reason and the original message kept (SC-012); 5,119.4 and 0 accepted;
5,119.5 rejected; empty `config.ref_stops` accepts and logs once; an `UndefinedTable` error accepts; an `OperationalError`
propagates; second event after a successful read does not query again; a 5 s injected clock allows the retry; the JSON
Schemas of `contracts/` are byte-identical to the commit before the story (FR-053).

## G2. Silver rule for a position that cannot be placed (US5, FR-052)

Applies to rows already in bronze (inserted straight, or from before G1 existed).

| Situation | Silver result | Gold result |
|---|---|---|
| Newest `bus_position` of a bus is out of range (`< 0` or `> route_end`) | `data_quality = estimated`; position, trip and stop lookup from the newest in-range position; the out-of-range row is absent from `silver.position_history` | the cycle completes and writes a snapshot; the bus keeps its last valid position, state `regular`, listed in `sources_down` (`since` = its last report time) |
| The bus has no in-range position at all | position columns NULL, `estimated` | not in `corridor_now.buses`; listed in `sources_down` |
| The same bus later sends an in-range position | that row is the newest valid; `live` again on the next cycle (US5.4) | normal |
| Other buses | unaffected | unaffected (SC-012: the 4 other in-service buses keep their state) |

The measured failure this removes: `CorridorNowV100` rejects `distance_along_m = 99999` (maximum 5,119.4), `run_cycle` rolls back
and raises `CycleError`, so no bus gets a snapshot. No `try/except` around the snapshot builder is added.

## G3. Clock guard (US6, FR-060 to FR-064)

Applies only to `REFRESH_CLOCK=data`. With `wall` nothing changes. The `compute` CLI has an explicit `--as-of` and is not affected.

**Input**: for each bus with at least one report (`bus_position`, `stop_arrival`, `stop_departure`; `source <> 'backend'`),
the `event_ts` of its newest report **by arrival** (largest bronze `id`).

**Rule** (`rules/clock.py`, pure, no wall clock, no `arrival_ts`):

1. `others(b)` = the values of all buses except `b`; `ref(b)` = `median_low(others(b))` (the lower of the two middle values
   for an even count; always an actual report time).
2. `b` is **untrusted** when `latest[b] > ref(b) + ESTIMATED_AFTER_S` (120 s; exactly 120 s is trusted).
3. `as_of` = the largest `latest[b]` among trusted buses.

| Buses reporting | Result |
|---|---|
| 0 | no data clock; the existing wall-clock fallback applies |
| 1 | newest report, nobody untrusted (limit documented, US6.5) |
| 2 | the one ahead by more than 120 s is untrusted; the other sets the clock |
| 3 or more | as above; one outlier cannot move `median_low` |
| a majority of buses far in the future | no trustworthy reference; documented limit |

**What reaches the data layers**

- `resolve_clock(conn, mode, now_fn)` returns `ClockDecision(as_of, untrusted)`; `resolve_as_of` returns only `as_of`.
- `run_cycle(..., untrusted_buses)` → `rebuild_silver(..., untrusted_buses)`: those buses are `estimated` in
  `silver.bus_current_state`; gold lists them in `sources_down`; classification makes them and the bus behind them `regular`
  (no alert, no recommendation target).
- Log: the existing `refresh_cycle` JSON line gains `untrusted_buses` (sorted list, `[]` normally). A WARNING line
  `{"event": "clock_guard", "untrusted_buses": [...]}` is written when the set changes. No payloads, no secrets.
- The 2030 event stays in bronze; silver ignores it (`event_ts > as_of`); when the bus sends a later valid report its newest
  report by arrival is valid and it is trusted again (US6.4).

**New config**: none. `MIN_BUSES_FOR_CLOCK_GUARD = 2` is a named constant in `rules/clock.py`; the 120 s is
`ESTIMATED_AFTER_S` (FR-062).

Test matrix (Phase 4), unit, no database: 0, 1, 2, 3 and 5 buses; a bus exactly 120 s and 121 s ahead; two buses far apart;
all buses within 5 s (nobody untrusted, `as_of` = the old `max(event_ts)`, FR-064); even count of others uses the lower middle.
Integration: C1 stream plus one `bus_position` of B-101 dated 2030-01-01 gives `as_of` on or after 2026-11-24T22:00Z and not in
2030, the other buses `live` in 100 % of the cycles after the injection, B-101 `estimated` and in `sources_down` (SC-013);
a later valid B-101 report returns it to `live`; the simulator at its normal pace has no untrusted bus in any cycle
(golden hashes unaffected, US6.6); the `FakeConn` unit tests of `test_refresh_loop.py` are updated for the per-bus query.
