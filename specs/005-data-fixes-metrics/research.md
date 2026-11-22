# Research: Data Fixes and Boarding-Probability Metrics

**Feature**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md) | **Date**: 2026-11-21

Nothing is left open. The three questions of substance (lost departures, oracle numbers after US1, open riders in the
last band) were DECIDED by the data owner on 2026-11-21; the answers are in
[plan.md](plan.md#decisions-at-the-human-gate) and are applied below (R2, R4, R8).

## How the numbers were obtained

- **Mock**: the data owner's `mock_calculos.py` (2026-11-21), which uses the repo simulator without a database. The
  oracles of this plan are its **post-US1** results (`mock-005/resultados-post-us1.md`): the mock re-run on a copy of the
  repository whose `data/reference/congestion_factor.csv` is the old file rotated, new hour `h` = old hour
  `(h + 5) mod 24`. Numbers marked "(mock)" below come from that file.
- **Reproduction** (this plan, throwaway scripts in `/tmp/plan005`, not committed): the same C1 runs (seed 42,
  2,700 s, with and without the seeded hold applied at second 1,415) on a reference built from the raw SIMM file with
  the local-hour rule, and the stop EWT recomputed with the mock's method. They reproduce the mock exactly:
  **+25.8 s with 27 intervals** and **+10.6 s with 28** on P-888..P-900, departures in (22:28:55, 22:44:55]Z. Numbers
  marked "(recomputed)" below come from these scripts, which apply the spec definitions (live 15-minute window,
  per-band split, open riders counted). The scripts also ran the full test suite on a scratch copy with and without
  the new file (R1).
- **Measurement**: a throwaway database on the local compose PostgreSQL 16 server, the C1 stream ingested through
  `ingest()`, cycles run through `run_cycle()`, prototype SQL for the new steps timed 20 times each.
- **Dates and times**: simulated start 2026-11-24 22:00:00Z = 17:00:00 local (UTC−5). Local bands: 17:00 = band 68,
  17:15 = 69, 17:30 = 70.

## R1 — US1: local hour of the SIMM congestion factor, regeneration and new hashes

**Decision**

- `build_congestion_factor` parses `FECHAHORA` as a UTC instant and takes the hour with `timebands.local_hour_band`.
  The offset therefore lives in one place (`LOCAL_OFFSET`), as FR-010 asks. A row that cannot be parsed is skipped,
  as today. The "no data for this hour: overall mean with a warning" fallback stays.
- `src/data/reference/sources.py` (which generates `SOURCES.md`) changes its sentence "Grouped FECHAHORA by UTC hour"
  to say that `FECHAHORA` is UTC and is converted to local hour (UTC−5). `SOURCES.md` is regenerated, never hand-edited.
- The CSV is regenerated with `python -m src.data.reference.build` from `data/raw/` and committed. `data/raw/` is not
  in git, and CI skips the build tests that need it, so a **CI-safe test on the committed CSV** is added: 24 rows,
  17 h = 0.4816, slowest hour 18, highest speed factor at 03 h. The build test that needs `data/raw/` compares the 24
  factors with an independent recomputation (group raw rows by `UTC hour − 5`).

**Numbers**

| Fact | Value | Source |
|---|---|---|
| SIMM rows; rows whose `FECHAHORA` does not end in `Z` | 109,085; 0 | scan of `data/raw/plata/simm_corredor_c6008.csv` |
| Rebuild with the current code vs the committed files | all 7 files byte-identical | rebuild into a scratch directory |
| New factor `h` vs old factor `(h + 5) mod 24` | maximum difference 0 at 4 decimals | analysis script |
| 17 h local | 0.5011 → **0.4816** | CSV |
| Slowest hour (lowest factor) | 23 h (0.4575) → **18 h (0.4575)** | CSV |
| Highest factor | 08 h (0.5656) → **03 h (0.5656)** | CSV |
| Hours with no SIMM data | 0 before and after (the mapping is a bijection of the 24 hours) | CSV |

Because the new file is the old file rotated, SC-001's independent recomputation is exact, not approximate.

**Golden hashes** (`test_simulator_golden_hash.py`). Measured with the regenerated factors loaded into the simulator
(seed, 3,600 s). The implementer re-measures them from the committed CSV and records old and new in `verification.md`;
the values below are the dry run and must agree.

| Seed | Old SHA-256 (lines, bytes) | New SHA-256 (lines, bytes) |
|---|---|---|
| 42 | `51a5e9b3063667320a6e66cab6293f84197822378783724dd664b6f6865d39e1` (3,851; 1,439,431) | `8bae0e5229b2e547fac181f0f87176809d71be7a80600a4b066832b6274690bc` (3,831; 1,433,630) |
| 7 | `6bd20707cf9aaccc852b6f8431e1129b759321b69f5cd06e5697c1638e0ab132` (3,840; 1,436,048) | `27a8206e4bcf896b54f847521ae80d65db9db260c2ba1431422e04b244d4df7e` (3,844; 1,437,557) |

The old values were reproduced by the same harness, which confirms the harness. `test_seed_42_shape` pins the line
and byte counts and moves with the hash.

**What else moves** (scratch copy, full suite without the `slow` and `live` markers, new CSV vs old CSV): 18 tests
fail only after the change. Nine are golden-hash tests. Nine pin second values of the C1 hold run:
`test_scenario_injectors.py` (`test_c1_waits_for_the_first_arrival_at_or_after_start_s` pins an arrival at 725 s,
`test_decision_must_precede_the_arrival_strictly`, `test_hold_extends_the_total_dwell_to_the_requested_seconds`,
`test_hold_keeps_reporting_with_doors_open_and_the_bus_does_not_move`,
`test_second_order_for_the_same_visit_is_a_conflict_and_never_runs`), `test_hold_loop.py`
(`test_forced_compliance_gives_executed`, `test_same_decision_delivered_twice_runs_once`,
`test_two_orders_for_the_same_visit_run_the_first_only`) and `test_hold_poller.py`
(`test_pre_written_decision_is_on_the_board_before_the_first_event`). Phase 1 re-pins those nine to the new stream.
(Other failures in the scratch run come from files the scratch copy lacked, such as `.github/` and `.env.example`,
and are identical with the old CSV. One bronze-ingest test failed only in the baseline copy and is treated as flaky.)

**Alternatives considered**

- Freeze the nine 004 tests on the old CSV. Rejected: they would stop testing the shipping reference; re-pinning is
  seven constants and keeps them honest.
- Fix the conversion in the simulator/M1 (read factor by UTC hour). Rejected: FR-013 keeps both readers by local hour.

## R2 — Oracle policy: the post-US1 numbers are the only oracles

**Decision (data owner, 2026-11-21).** Every oracle in this plan is computed on the stream the shipping reference
produces, that is, after US1. There is no frozen copy of the old congestion file, no `reference_pre005/` fixture and no
`frozen_reference.py` helper. Every gold test compares gold with the independent oracle on the current stream.

| Oracle, C1 seed 42, P-888..P-900, departures in (22:28:55, 22:44:55]Z | Without hold | With the 90 s hold | Source |
|---|---|---|---|
| Stop EWT | **+25.8 s**, 27 intervals (Σh 13,290 s, Σh² 8,660,350) | **+10.6 s**, 28 intervals (Σh 14,505 s, Σh² 9,011,425) | mock; recomputed (sums) |
| Hold saving | 15.2 s | | mock |
| Hold execution | B-103 arrives at P-887 17:27:45 local, leaves 17:29:15 (90 s) | | mock |

The hold lowers EWT, so SC-006's second sentence ("lower with the hold") holds. Historical note: the review's +40.6 s and
+23.6 s (27 / 28 intervals) came from the pre-US1 stream, whose congestion factors were shifted five hours; US1 changes
the travel times, so the same window now gives +25.8 s and +10.6 s.

**Phase 1 exit gate.** After the CSV is regenerated by the reference build, the data owner's verifier re-runs the mock
on the regenerated file and must get exactly +25.8 s (27) and +10.6 s (28). The mock also prints the congestion table
(the committed factor and the factor recomputed from the raw file must agree for every hour, differences printing as
0.0 %), the slowest hour (18 h) and the hold at P-887. This needs no database, so Phase 1 can end with it.

**Consequence for the spec.** `spec.md` (SC-006, US3 scenarios 1 and 2, A-2) and `checklists/requirements.md` quote
the pre-US1 review numbers. They are outside this update; the data owner amends them to the numbers above (plan, Risks).

## R3 — US2: pass time at 0 m (H-10)

**Cause.** `pass_time` returns the first sample at or past the distance. A leader waiting at P-883 reports 0 m every
5 s with the same `trip_id`, so for a follower at 0 m the first sample at 0 m is when the leader *started waiting*.
On C1 seed 42 (post-US1 stream) the headways come out as 1,240 s, 1,835 s and 2,440 s (mock). This is an existing behavior of the rule, not of
the data.

**Decision.** `rules/headway.py` (pure):

- `pass_time(history, distance_m, origin_m=0.0, departure_ts=None)`. When `distance_m <= origin_m` it returns
  `departure_ts` if given; otherwise the time of the **last** sample at or below `origin_m` (the leader left the
  origin after it); otherwise `None`. For `distance_m > origin_m` it behaves exactly as today (the immediately
  preceding sample is the last waiting sample, so interpolation already starts at the departure).
- `BusObs` gains an optional `departure_ts` (first-stop departure on the position trip). `headway_s` and
  `compute_headways` pass it through. Existing unit tests build `BusObs` without it and are unaffected.
- `pipeline/gold.py` reads the departures with one query on `silver.stop_visits` joined to `silver.bus_current_state`
  on `position_trip_id`, for the first stop of `config.ref_stops` (`stop_seq = 1`, 0 m today), and passes
  `origin_m` from the same table. No literal 0 or `P-883` in code.

**Why `silver.stop_visits` first, with a fallback.** The departure event is exact. A visit row needs both arrival and
departure, so when the arrival was lost (D1 silence) there is no row; the fallback (last sample at the origin) is
exact in the simulator and within one report interval in general. Without a fallback the headway would fall back to
the leader's own latest position time, about 0 s, and report a false `bunched`.

**Waiting leader (US2.4).** A bus waiting at the first stop is `on_corridor = false` in silver (`waiting = true`), so it
never reaches the headway rule as a leader. The pure rule still returns `None` (no `departure_ts`, no sample past
the origin yet) and `headway_s` treats `None` as "no evidence", never raising and never returning a negative value.

**Numbers (mock, post-US1 stream).** The buses B-103, B-104 and B-105 leave the terminal at 17:20:40, 17:30:35 and
17:40:40 local (22:20:40Z, 22:30:35Z, 22:40:40Z; recomputed). At those instants the unfixed code gives 1,240 / 1,835 /
2,440 s and the fix gives **615 / 595 / 605 s**, inside the 300–900 s criterion (SC-003). The snapshot EWT jumps
(+259, +536, +732 s in the spatial definition, mock) disappear with US3 anyway; SC-004 is asserted on the new definition.

## R4 — US3: stop-based EWT from departures, and "estimated at departure"

**Decision.**

1. **Source.** Departures per stop from `silver.stop_visits.departure_ts`, restricted to stops of `config.ref_stops`
   (A-6). Ordered by `(departure_ts, bus_id, trip_id)` so ties are deterministic; a headway of 0 s is allowed.
2. **Interval and band.** The headway between consecutive departures `a < b` at one stop belongs to the **closing**
   departure `b`: it is in a window or band when `b` is. `a` may lie before the window. This is exactly the mock's
   rule (`t_from < b <= t_to`) and is how the oracle numbers were produced.
3. **Formulas.** Per stop and per band the additive sums `n`, `Σh`, `Σh²`, and the planned `Σhp = n · planned`,
   `Σhp² = n · planned²` with `planned = config.corridor_settings.headway_planned_s` (600, A-3). EWT is derived:
   `Σh²/(2Σh) − Σhp²/(2Σhp)`; the corridor sums the stop sums first (FR-031). Arithmetic uses integer microseconds
   converted to `Decimal`, so rebuilds are byte-identical.
4. **Estimated at departure.** New column `silver.stop_visits.estimated_at_departure`. FR-032 says to use "the same
   rule as the existing freshness classification (no report within 120 s of the departure)". Taken literally the rule
   is always false at that instant, because the departure event is itself a report at that time. The workable reading,
   consistent with `segment_traversals.travelled_while_estimated`, is: the bus's **previous report** (any of
   `bus_position`, `stop_arrival`, `stop_departure`, non-backend, strictly earlier `event_ts`) is **more than**
   `ESTIMATED_AFTER_S` = 120 s before the departure. Strictly greater, as in `silver_bus_current_state.sql`. A bus with
   no earlier report is not estimated. Implemented in `silver_stop_visits.sql` with the same "distinct timestamps per
   bus, `lag`" pattern as `silver_segment_traversals.sql`; the threshold is the existing `estimated_after_s` parameter.
5. **Exclusion.** A headway is excluded when **either** of its two departures has the flag (US3.6). The count goes to
   `n_excluded` of the same row, so coverage is visible.
6. **Old spatial function.** `rules/service_metric.py` is rewritten over sums (FR-036); the old function of
   `headways: Sequence[float]` is removed because `gold.py` was its only caller. `compute_headways` stays: it still
   feeds `corridor_now.headway_ahead_s` and the bus states.
7. **Where it runs.** Python, in `rules/stop_metrics.py` (pure) and `pipeline/stop_metrics.py` (reads
   `silver.stop_visits` once per cycle, writes the rows). Python rather than SQL windows because the rule is
   unit-testable without a database and uses the single `timebands` offset for bands (a SQL version needs a second copy
   of UTC−5 and a test like `test_timebands_sql.py`). The prototype SQL is also fast (R12) if the data owner prefers it.

**Known limitation (DECIDED, data owner 2026-11-21: accepted as a turn-1 limit; no silence-bracket rule).** A departure
that was never reported (the bus was silent) leaves no row. The interval between its neighbours is then longer than
reality. Arithmetic: 25 intervals of 600 s give EWT 0; replacing two of them by one 1,200 s interval gives Σh = 15,000,
Σh² = 9,720,000, mean wait 324 s, EWT +24 s. The D1 fixture of 004 (`d1_silence.json`, B-101 silent from 250 s for 300 s)
loses only 2 departures. Because they are the first departures at those stops, they remove intervals instead of
lengthening them (recomputed on the post-US1 stream): the trailing 15-minute EWT of the silenced stream differs from the
unsilenced stream by about +10 s at 17:16:40 local (n = 3 vs 4, +0.1 vs −10.3 s) and at 17:20:00 (n = 4 vs 6, −7.9 vs
−18.8 s), and is identical before. The risk is larger for a silence in mid-run.

How a reader sees it: during the silence the bus is `estimated` and appears in `sources_down`; headways that touch a
departure reported after a gap of more than 120 s are excluded and counted in `n_excluded`. The lost departure itself
leaves no row, so it is not in `n_excluded`. The limit is recorded, not solved, in this story and listed as Evolution.

**Alternatives considered**

- Make the flag part of gold, computed from bronze. Rejected (see Complexity Tracking in the plan).
- Treat a missing departure as "estimated" by comparing visit counts per bus. Rejected: needs a notion of expected
  stops per bus, which the data does not have in turn 1.

## R5 — US3: live trailing window, per-snapshot rows, closed bands, and the 16-minute oracle

**Decision**

- **Live value.** The `gold.service_metric` row of each snapshot sums the per-stop sums of closing departures in
  `(as_of − 15 min, as_of]`; the length is `timebands.WINDOW`. Same columns, new meaning. `n_headways` = Σ n.
- **Per-snapshot rows.** `gold.service_metric_stop` gets one row per stop of `config.ref_stops` (18) per snapshot, so a
  stop with fewer than two departures has a row with `n_headways = 0` and `computable = false` (US3.5).
- **Closed bands.** `gold.stop_ewt_band` holds one row per (`local_date`, `band`, `stop_id`) for each band whose end
  is at or before `as_of`, for stops that have at least one closing departure in the band. Rows are replaced every cycle
  (delete and insert) with the cycle's lineage, exactly as `m1_baseline` / `m2_baseline` are; the same bronze gives
  the same rows. A stop with no closing departure has no row, which is the same as zeros and "not computable".
- **Reports read the band rows**, never the trailing rows (FR-034).

**How the 16-minute oracle window maps to the tests.** The oracle window is 16 minutes and not clock aligned:
(22:28:55, 22:44:55]Z. The live window is 15 minutes, and a band is 15 minutes aligned to the clock. All three differ.
Measured on the post-US1 stream (recomputed; P-888..P-900 unless stated; the 16-minute rows agree with the mock):

| Slice | Intervals | Σh (s) | Σh² | EWT |
|---|---|---|---|---|
| Oracle window (22:28:55, 22:44:55], no hold | 27 | 13,290 | 8,660,350 | **+25.8 s** |
| Oracle window, with hold | 28 | 14,505 | 9,011,425 | **+10.6 s** |
| Live trailing window at 22:44:55 (22:29:55, 22:44:55], no hold | 25 | — | — | +21.0 s |
| Live trailing window at 22:44:55, with hold | 27 | — | — | +1.8 s |
| Live trailing window, all 18 stops, no hold / with hold | 33 / 35 | — | — | +17.6 s / +2.8 s |
| Band 68 (17:00–17:15 local), no hold or hold | 0 | 0 | 0 | not computable (no closing departure on these stops) |
| Band 69 (17:15–17:30 local), no hold | 6 | 4,770 | 4,190,600 | +139.3 s |
| Band 70 (17:30–17:45 local), no hold | 25 | 12,180 | 7,819,850 | +21.0 s |
| Band 69 / band 70, with hold | 5 / 27 | 4,550 / 13,615 | 4,142,200 / 8,219,325 | +155.2 s / +1.8 s |

Mapping to tests:

1. **SC-006 (the data owner's numbers).** The pure rule `window_sums(departures, lo, hi)` is called by the test with
   the explicit 16-minute window over the rows of `silver.stop_visits` of a database loaded with the C1 stream of the
   current reference, and must give +25.8 / +10.6 (±0.1) and 27 / 28 intervals. The gold rows are not asked to equal this
   window, because they are not 16 minutes.
2. **SC-005 (gold equals an independent recomputation).** The oracle module recomputes from the raw simulator events
   (not from silver): (a) for the live trailing window at several snapshots, per stop and for the corridor; (b) per stop
   and per closed band. Equality is exact on `n_headways`, `Σh`, `Σh²`, `Σhp`, `Σhp²`.
3. **"Band sums add up to the oracle's totals."** Band rows (P-888..P-900) are summed over bands 69 and 70 and compared with
   the oracle grouped by the same two bands (6 + 25 = 31 intervals, Σh 16,950, Σh² 12,010,450 without the hold; 5 + 27 = 32
   intervals, Σh 18,165, Σh² 12,361,525 with it). All 18 stops are compared the same way. They are not
   compared with the 16-minute total (27 / 28), which covers part of band 69 and all of band 70.
4. Band 70 ends at 22:45:00Z but a 2,700 s run stops reporting at 22:44:55Z, so it is closed only for `as_of ≥ 22:45:00Z`.
   The test calls the cycle at 22:45:00Z; no departure falls between 22:44:55 and 22:45:00 (the live window at
   22:44:55 and band 70 then agree: 25 intervals, +21.0 s without the hold; 27 intervals, +1.8 s with it).

## R6 — US3: minimum sample for `computable` (observation 1)

**Decision.** `config.corridor_settings.min_stop_headways INT NOT NULL DEFAULT 5 CHECK (>= 1)`, next to
`min_sample_count` (also 5). The corridor row of `gold.service_metric` has `computable = true` only when
`n_headways >= min_stop_headways` and `Σh > 0`; otherwise `mean_wait_s`, `scheduled_wait_s` and `ewt_s` are NULL, as
the existing rule does for "not computable" (Q4: show "—", not 0), and `n_headways` keeps the real count. The value is
read from `config` in SQL or in the pipeline, never a literal in a rule (the rule takes it as an argument).
Per-stop rows have `computable = n_headways >= 1` (a stop can rarely reach 5 in 15 minutes: about 1.5 intervals at 600 s).

**Evidence for 5** (trailing 15-minute stop EWT over all stops, C1 seed 42 without hold, post-US1 stream; snapshots every
5 s; value at the first snapshot with that count. Rows marked * are also in the mock's table and agree with it):

| n intervals | 1* | 2 | 3* | 4* | 5* | 8* | 10* | 15* | 17* | 24 | 32* |
|---|---|---|---|---|---|---|---|---|---|---|---|
| EWT (s) | +7.5 | +124.9 | +151.6 | +124.0 | +104.8 | +109.5 | +123.2 | +116.6 | +104.2 | +91.3 | +46.2 |

Re-check after US1: the justification holds, with a nuance. From n = 4 to n = 17 the value stays between +99.8 s and
+127.8 s (a few counts have snapshots with up to +128.8 s) while the bunching lasts, and only then falls as the corridor
recovers (+91.3 s at n = 24, +46.2 s at n = 32). Below that band: n = 1 gives +7.5 s, a value that misses the bunching
entirely. Above it: n = 3 gives +151.6 s, 19 % over the top of the band. n = 2 (+124.9 s) happens to fall inside the band,
but it sits between two counts that do not, so it is not a reliable threshold. A threshold of 4 would also pass on this
stream (+124.0 s). Five stays: its value (+104.8 s) is inside the band, and it is also
M1's `min_sample_count`, so one hypothesis serves both. A column on the existing table avoids a new table; the cost is
that an existing volume needs `008` applied by hand (R14).

**Alternatives**: 3, rejected because +151.6 s at n = 3 is 19 % above the band's top (+127.8 s). 4, a defensible choice
(+124.0 s) that has no second use; the data owner can change the column value without a release.

## R7 — US3/US4: band tables, keys and names

**Decision.** Two tables keyed by (`local_date`, `band`, `stop_id`), `band` 0–95 from `timebands.m2_band`, the same
bands as M2 and the reports (spec Clarifications). Column names follow H4 of `docs/data-contract.md` (`sum_headway_s`,
`sum_headway_sq_s`, `sum_planned_s`, `sum_planned_sq_s`, `n_riders`, `n_board_le_5`, `n_board_le_10`, `n_board_le_15`), so
the later history layer only adds `operator`, coverage and `computed_at`. `local_date` is part of the key because
band 68 of two days must not merge. Both carry `rules_version` and `max_bronze_id` (NOT NULL), and are replaced every
cycle.

Full definitions: [data-model.md](data-model.md) and [contracts/gold-stop-metrics.md](contracts/gold-stop-metrics.md).

**Alternatives considered**

- Append-only band rows. Rejected: a late event inside a closed band (out-of-order, H-6) would need a correction row;
  replace-each-cycle gives the same bytes for the same bronze (SC-011) and matches the baseline tables.
- Dense rows for all 18 stops in every band. Rejected: 18 × 96 rows per day for mostly zeros; sums are additive, so
  absence equals zero.

## R8 — US4: boarding counts, method and read query

**Decision.**

- **Riders** come from `bronze.events` (`event_type = 'rider_arrival'`, `id <= max_bronze_id`, `event_ts <= as_of`),
  the same source `gold_m2_baseline.sql` already reads. No new silver table (it would have no other consumer).
  Duplicates are already rejected by `UNIQUE (source, event_id)`, so a repeated `rider_arrival` is one row (US4.7).
- **Wait.** For a rider at stop `s` arriving at `a`: the smallest `departure_ts` of `silver.stop_visits` at `s` with
  `a <= departure_ts <= as_of`. `wait = departure − a`. Equal timestamps count (wait 0, spec assumption).
  `n_board_le_t` counts `wait <= t` for t = 300, 600, 900 s. No departure yet: counted in `n_riders` only (US4.2, US4.8).
  A later cycle can move an open rider into the `≤ t` columns (A-7).
- **Band** is the band of the **arrival** (local time), including the current open band.
- **Rule**: `rules/boarding.py`, pure, `bisect` over the sorted departures of each stop. `pipeline/stop_metrics.py` reads
  the riders and the departures and writes `gold.stop_boarding_band`. Riders at a stop outside `config.ref_stops` are
  counted nowhere (A-6).
- **Index.** `silver.stop_visits (stop_id, departure_ts)` is added for the read.
- **Read.** Documented queries and one view, `gold.stop_boarding_band_v`, which adds `band_start_ts`, `band_end_ts`,
  `closed` (band end at or before the newest snapshot's `as_of_ts`) and `final` (band end + 15 min at or before it, so
  every rider of the band had the 15 minutes the largest `t` needs). `P = Σ n_board_le_t / nullif(Σ n_riders, 0)`: null,
  not 0.

**Oracle** (post-US1 stream, recomputed from raw events with the spec definition: open riders count in `n_riders`;
as_of 22:44:55Z and 22:45:00Z give the same rows):

| Band (local) | Riders | ≤ 5 min | ≤ 10 min | ≤ 15 min | P(≤5) | P(≤10) | P(≤15) |
|---|---|---|---|---|---|---|---|
| 68 (17:00–17:15) | 9 | 3 | 9 | 9 | 33.3 % | 100 % | 100 % |
| 69 (17:15–17:30) | 16 | 10 | 16 | 16 | 62.5 % | 100 % | 100 % |
| 70 (17:30–17:45) | 21 | 9 | 14 | 15 | 42.9 % | 66.7 % | 71.4 % |

The mock (departed riders only) prints 33 % (3/9), 62 % (10/16) and 60 % (9/15) at ≤ 5 min, and 100 %, 100 % and
93 % (14/15) at ≤ 10 min. Bands 68 and 69 agree with it. Band 70 has the same numerators (9, 14, 15) over 21 riders instead
of 15: the 6 riders still waiting at the end of the run are in `n_riders` (A-7). DECIDED (data owner, 2026-11-21): the spec
governs, and reports read only bands marked `final`; the mock's band-70 percentages are not oracles.
Riders by stop (46 in total, recomputed): P-883 37 (80.4 %), P-884 1, P-886 1, P-888 2, P-891 1, P-893 2, P-895 1, P-897 1.

**Limitation (observation 2, finding O-1).** The corridor value barely discriminates: with this demand almost everybody
waits at P-883, where departures are regular, and the C1 gap happens downstream where nobody waits, so P(≤ 10 min)
stays 100 % in bands 68 and 69 even during the gap. Per-stop values are therefore part of the read queries, and
the limitation is stated in the contract note. The demand model is not changed.

**Simple-method bias.** A rider who arrives while a bus is already dwelling counts that bus's departure, although the
simulator's boarding happens at arrival. The simple method is optimistic by construction; FIFO is Evolution.

## R9 — US5: ingestion range check

**Decision.** `ingest()` already has the database connection. After the envelope validates, for `bus_position` only,
it compares `distance_along_m` with `RouteBounds.max_distance_m(conn)`:

- The bound is `SELECT max(distance_along_m) FROM config.ref_stops`: no new dependency, no environment variable.
- Cached for the process after the first successful, non-empty read. After a failure or an empty table, the next read is
  at least 5 s later (a code constant with an injected clock for tests); in between, events are accepted (fail-open,
  FR-051). Only SQL-level errors that mean "reference data not there" are swallowed (`UndefinedTable`, an empty result);
  connection errors still propagate to the retry layer (`ingestion/retry.py`), which already stores the same line after
  reconnecting.
- Above the bound: `_reject(conn, message, "value_out_of_range")`; nothing is written to `bronze.events`; the original
  message is kept in `bronze.rejections` (FR-050). Exactly the bound (5,119.4) and 0 are accepted. A negative value is
  already rejected by the Pydantic model (`minimum: 0`).
- One log line `route_bound_unavailable` (fixed vocabulary, no connection data, no event content) is written once per outage.
- The pure comparison is in `ingestion/validate.py` so it is unit-tested without a database; `validate_envelope` stays
  database-free.

**Why a cache, and why no variable.** The route does not change within a run; the table is loaded by `refresh`/`compute`
at start-up, possibly after ingestion started (compose starts both), so a failed first read must be retried. A per-event
query would add a round trip per event at no gain. A restart picks up a changed route.

**Reuse of the reason.** `value_out_of_range` is already in the rejection enum and in the `bronze.rejections` CHECK, so no
schema or contract change is needed (FR-053).

**Test builders.** The five timeline builders peak at 4,320 m (measured), well below 5,119.4 m; the simulator's maximum
over the 2,700 s run is 5,119.4 m (mock: 0 of 2,700 positions outside the range).

## R10 — US5: pipeline guard against an impossible position

**Measured failure.** Reproduced on the throwaway database: a `bus_position` with `distance_along_m = 99999` as the
newest report of B-105 (on the corridor) makes `gold.build_snapshot` raise `ValidationError` in `CorridorNowV100`
(`buses.0.distance_along_m`: "Input should be less than or equal to 5119.4"). The cause is the read schema's maximum,
not a missing stop (the spec says "no previous or next stop"; silver gives `prev_stop_id = P-900` and no next stop,
which the builder already patches with `prev or next`). `run_cycle` rolls back and raises `CycleError`: no bus gets a
snapshot. The same event with B-103 (already finished its trip, not on the corridor) did not fail, which is why the first
reproduction attempt looked fine.

**Decision.** The route end is `max(distance_along_m)` of `config.ref_stops`, read in SQL. In silver:

- `silver.position_history` skips rows outside `[0, route_end]` (an impossible sample in a leader's history would also
  corrupt the interpolation for the follower).
- In `silver.bus_current_state`, `latest_position`, `trip_position` (the "waiting" test) and the stop lookup use only
  in-range positions. A bus whose **newest** position report is out of range gets `data_quality = 'estimated'` (it
  keeps its last valid position, as a silent bus does). When its next position is valid, that becomes the newest and the
  bus is `live` again (US5.4). A bus with no valid position has a NULL position; `gold.py` already skips buses without
  one, and it is listed in `sources_down` (`on_corridor` and `estimated`).
- `classify` already forces `estimated` buses and their followers to `regular`, so no alert follows (FR-052).
- A cycle-level safety net is not added: swallowing the `ValidationError` would hide other defects.

**Alternative**: only the ingestion check. Rejected: FR-052 requires the pipeline to survive a row inserted straight into
bronze (a route change, a bypass).

## R11 — US6: clock guard in `resolve_as_of`

**Reproduced.** One `bus_position` of B-101 dated 2030-01-01 makes `resolve_as_of(conn, "data")` return
`2030-01-01 00:00:00+00:00` on the throwaway database.

**Decision.** New pure module `rules/clock.py`:

- Input: for each bus that has reports, the event time of its **newest report by arrival** (largest bronze `id`, of
  `bus_position`, `stop_arrival`, `stop_departure`, non-backend). Output: `ClockDecision(as_of, untrusted)`.
- A bus `b` is untrusted when `latest[b] > median_low(latest of the other buses) + ESTIMATED_AFTER_S` (strictly more
  than 120 s ahead; exactly 120 s is trusted, FR-062). `median_low` returns an actual element, so no averaging of times
  and the rule is deterministic. `as_of` = the newest `latest` among trusted buses.
- **Fallback for few buses (observation 3).** With **0 buses reporting** the data clock falls back to the wall clock, as
  today. With **1 bus reporting** there is no "others": its newest report is used and nobody is untrusted (US6.5). With
  **2 buses** the "others" is one bus: the bus ahead by more than 120 s is untrusted, the other is trusted. The constant
  `MIN_BUSES_FOR_CLOCK_GUARD = 2` states the lower bound. At 2 buses a real desynchronization of more than 120 s (one bus
  silent for 130 s) also flags the live bus; the alternative of a bound of 3 would let one bad event hijack the clock
  at start-up and at night, which is the worse failure and permanent in bronze.
- **Why arrival order.** US6.4: after the bad event, the bus's next valid report must bring it back to `live`. By event
  time the 2030 report is its newest report forever. By arrival order the newest report is the valid one, and the 2030
  event is ignored by silver (`event_ts <= as_of`). For an in-order feed (the simulator) the two orders are the same.
  Out-of-order delivery is H-6 and out of scope.
- **How the excluded bus is reported.** `resolve_clock(conn, mode, now_fn)` returns the decision; `resolve_as_of` stays
  as a thin wrapper returning only the time (existing callers and tests). `run_cycle(..., untrusted_buses=frozenset())`
  passes the set to `rebuild_silver`, whose SQL marks those buses `estimated` (`bus_id = ANY(%(untrusted_buses)s)`).
  Gold then lists them in `sources_down` and classifies them `regular`. The `refresh_cycle` log line gains
  `untrusted_buses` (sorted list, empty normally), and a WARNING `clock_guard` event is logged when the set changes. The
  `compute` CLI passes none (its `--as-of` is explicit, so a future-dated event is already beyond `as_of`).
- **Query.** One per cycle: newest report per bus by `id` (`DISTINCT ON`). Measured 3.0 ms median at 2,877 rows and 13 ms
  at 15,410 rows. The existing `max(event_ts)` query is replaced; `test_refresh_loop.py`'s `FakeConn` returns one row,
  so those unit tests are updated in Phase 4.

**Oracle (mock, with C1 events, newest reports at 22:44:55Z for all five buses).** Inject B-101 at 2030-01-01: today's
clock gives 2030; the rule gives 22:44:55Z and excludes B-101. Without the injected event the rule excludes nobody.

**Limit.** If most buses carry a future date there is no trustworthy reference (documented, spec edge case). After the
2030 event is in bronze, its bus's newest report by event time stays in 2030; it is the *others'* median that matters,
and one contaminated bus does not move it (`median_low`).

## R12 — Cycle time (measured)

Throwaway database, C1 stream ingested, `run_cycle` timed, then the prototype SQL of each new step timed 20 times on the
final state. Prototype SQL is not the final code; the final code is Python plus small reads and is expected to be within
the same order.

| Dataset | Bronze rows | Baseline cycle (median / p95 / max) | Cycles at the end of the run | New steps (prototype medians) |
|---|---|---|---|---|
| Demo, C1 seed 42, 2,700 s | 2,877 | 48 / 68 / 81 ms (108 cycles) | 60–95 ms (two runs) | stop headways 4.3 ms, closed bands 6.3 ms, boarding 3.2 ms, clock query 3.0 ms: **17 ms** |
| Stress, base seed 42, 14,400 s (4 h) | 15,410 | 286 / 965 / 1,041 ms (24 cycles) | 1,271–1,311 ms | 18.0 + 18.7 + 56.1 + 13.1 = **106 ms** |

Both datasets were measured on the pre-US1 stream. The post-US1 C1 run has 2,881 events (2,884 with the hold) instead of
2,877 (2,879), so the figures stand; Phases 2 and 3 re-measure on the regenerated stream.

Budget decided: new steps ≤ 100 ms and cycle p95 ≤ 250 ms at demo length; ≤ 1.5 s at 4 h. At demo length the finished
cycle should be about 65–110 ms, about 2 % of the 5 s interval. The boarding prototype had no index; the index on
`silver.stop_visits (stop_id, departure_ts)` and a bisect in Python are expected to lower it. Phase 2 and 3 re-measure
and write the figures in `verification.md`. The baseline itself grows linearly with bronze (1.28 s at 15,410 rows, so
5 s at about 60,000 rows, about 16 simulated hours). That is finding H-8, out of scope; it is recorded so that story 006
does not assume a day-long run.

## R13 — Rules version

`RULES_VERSION` 1.1.0 → 1.2.0 in Phase 1 (the headway rule changes `corridor_now` content), 1.3.0 in Phase 2 (the
`service_metric` definition changes), 1.4.0 in Phase 3 (new boarding rows) and 1.5.0 in Phase 4 (silver state of
unplaceable and untrusted buses). 002's rule is "any change to a rule bumps it", and each phase can be committed alone.
Snapshot ids hash the version, so ids re-key; no stored gold content is altered for an unchanged version. Only
`test_rules_version.py` pins the literal. If the data owner prefers one bump for the whole story, the phases above
collapse to a single `1.2.0` at the first commit with no other change.

## R14 — Schema delivery and test helpers

- `008_data_fixes_metrics.sql`, idempotent (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`, `CREATE OR REPLACE
  VIEW`). New databases get it from `docker-entrypoint-initdb.d`. An existing volume applies it by hand (same procedure as
  007; written in the quickstart). The refresh service logs `cycle_failed` until it is applied.
- Test helpers that list tables and must learn the new ones: `tests/fixtures/gold_support.clear_all`,
  `tests/integration/conftest.py` (silver list unchanged; gold list gains `service_metric_stop` **before** `snapshots` because
  of the foreign key), `test_scenarios_gold.py` (two lists), `test_schema_init.py` (table inventory and the lineage test
  parameters), `test_gold_contract.py` (`n_headways == 4`, mean 300 s of the old spatial rule become the stop-based values
  of the same fixture).
- `test_no_bronze_writes.py` scans the SQL files for bronze writes; the new SQL reads only.

## Decisions NOT taken here

- Changing `contracts/` JSON Schemas, ADR text, `docs/data-contract.md` (FR-003, SC-014): listed in
  [contracts/README.md](contracts/README.md).
- A per-hour planned headway (A-10), weekend service (A-11), SIMM period bias (A-12): documented limits of the reference data.
- Per-operator split and coverage columns (H4): Evolution.
