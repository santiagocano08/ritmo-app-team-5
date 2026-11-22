# Quickstart: validating feature 005

A run and validation guide. No implementation code here; the tests and rules are built from [plan.md](plan.md),
[data-model.md](data-model.md) and [contracts/](contracts/README.md). Commands run from the repository root.

## Prerequisites

- Python 3.12 and `uv`; Docker (for the CI-ready command and the local PostgreSQL 16 server the tests use).
- `.env` copied from `.env.example` (placeholders only). `DATABASE_URL` for tests run on the host points at
  `localhost`, not at the compose host `db`.
- For Phase 1 only: `data/raw/` (git-ignored) to regenerate the congestion CSV. Without it the build tests skip, as in CI.
- Branch `feature/005-data-fixes-metrics`, stacked on `feature/004-scenario-injectors`. No commit or push is made by the agent.

## Commands

| Purpose | Command |
|---|---|
| One test file, no coverage gate | `uv run pytest src/data/tests/unit/test_headway.py -p no:cacheprovider --no-cov` |
| Whole suite, host (slow and live excluded) | `uv run pytest -m "not slow and not live" --no-cov -p no:cacheprovider` |
| CI-ready command (the gate: coverage above 80 %) | `docker compose --profile tools build tests && docker compose --profile tools run --rm tests` |
| Regenerate the reference (Phase 1) | `python -m src.data.reference.build` |
| Data owner's verifier on the regenerated CSV (Phase 1 exit; no database) | `PYTHONPATH=. uv run python ~/Documents/contexto/mock-005/mock_calculos.py` (from the repository root; the script overwrites `resultados.md` next to itself, so copy the pre-005 file first if you want to keep it) |
| Apply the new init script to an existing volume | `docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < src/data/db/init/008_data_fixes_metrics.sql` |

A database volume created before this story does not run `008` again; apply it by hand (the file is idempotent). New volumes
get it from `docker-entrypoint-initdb.d`.

## Baseline before any change (record in `verification.md`)

1. The suite is green on `feature/004-scenario-injectors` head `8351274` (004's own figure: 434 passed, 4 skipped at the end of
   003; run it again, the number grows with 004).
2. Coverage figure of the CI-ready command (must stay above 80 %).
3. The two old golden hashes (research R1) and the old CSV (`17 h = 0.5011`).

## Phase 1: reference hour and terminal headway (US1 + US2)

Write first, watch fail:

1. Committed CSV: 24 rows, 17 h = 0.4816, slowest hour 18, highest speed factor at 03 h.
2. Build test: the 24 factors equal the raw file grouped by `UTC hour − 5` (skips without `data/raw/`).
3. `pass_time` with a waiting leader at 0 m returns the departure, not the first waiting sample; follower at 0 m gets
   `follower_ts − departure`; leader that has not left yields no evidence and no error; with no `departure_ts` the last sample
   at the origin is used.
4. Integration on C1 seed 42 (current reference): headway of the bus leaving the terminal at 22:20:40Z, 22:30:35Z and
   22:40:40Z is between 300 s and 900 s and equals the mock's 615 / 595 / 605 s to the nearest second (the unfixed code gives
   1,240 / 1,835 / 2,440 s); no `gap` caused by the terminal wait.

Then implement, regenerate, re-pin, and expect:

| Check | Expected |
|---|---|
| `git diff --stat data/reference/` | only `congestion_factor.csv` and `SOURCES.md` |
| new golden hashes | seed 42 `8bae0e52…690bc` (3,831 lines, 1,433,630 B); seed 7 `27a8206e…d4df7e` |
| nine re-pinned 004 tests | green on the new stream |
| `RULES_VERSION` | `1.2.0`; `test_rules_version.py` updated |
| full suite | green; coverage above 80 % |
| 24 factors vs the file before the change (`git show HEAD:data/reference/congestion_factor.csv`, one-off, result in `verification.md`; no frozen copy is committed) | new `h` = old `(h + 5) mod 24`, maximum difference 0 |

**Phase 1 exit gate: the data owner's verifier.** With the regenerated CSV in the working tree, the data owner runs the
mock (command in the table above) and compares:

| Mock output | Must be exactly |
|---|---|
| section 1, committed factor vs factor recomputed from the raw file | every hour prints as ±0.0 %; slowest hour 18 h in both columns |
| section 3, stop EWT P-888..P-900, departures 17:28:55 to 17:44:55 local | **+25.8 s (27 intervals)** without the hold, **+10.6 s (28 intervals)** with it; hold saving 15.2 s |
| section 3, hold check | B-103 at P-887 from 17:27:45 to 17:29:15 local (90 s) |
| section 2, terminal headways with the H-10 fix | 615 / 595 / 605 s at 17:20:40, 17:30:35 and 17:40:40 |

Any other value means the CSV was not regenerated as the rule says; Phase 1 stays open and Phase 2 does not start.

## Phase 2: stop-based EWT (US3)

Write first (all fail: the tables and rules do not exist): pure `stop_metrics` tests (closing-departure attribution, one departure
means no row, tie order, estimated endpoints excluded and counted, band boundaries at 17:14:59 / 17:15:00 local), `service_metric`
over sums (300 s and 900 s give +75 s, four times 600 give 0, fewer than 5 not computable), the
oracle module, and the gold integration tests.

Expected on the **current (post-US1) reference**, C1 seed 42, 2,700 s, cycle at 22:44:55Z and 22:45:00Z. Sources: the first
row is the mock; the others are the plan's recomputation from raw events:

| Check | Without hold | With 90 s hold (decision at second 1,415) |
|---|---|---|
| `window_sums` over (22:28:55, 22:44:55], P-888..P-900 | 27 intervals, **+25.8 s** (±0.1) | 28 intervals, **+10.6 s** (±0.1) |
| live corridor row at 22:44:55, all 18 stops | 33 headways, +17.6 s, computable | 35 headways, +2.8 s |
| live window, P-888..P-900 (from the per-stop rows) | 25 headways, +21.0 s | 27 headways, +1.8 s |
| band 69 / band 70 rows, P-888..P-900 | 6 / 25 headways | 5 / 27 headways |
| band 69 + 70 sums | 31 headways, Σh 16,950, Σh² 12,010,450 | 32, Σh 18,165, Σh² 12,361,525 |
| bunched snapshot (B-103 210 s behind B-102, 22:30:00Z) | corridor EWT +116.6 s with 15 headways (the spatial definition gave −195 s); mock | — |
| band 68 rows, P-888..P-900 | none (not computable) | none |
| a bus with no departure in the window enters or leaves | EWT changes by 0 s | — |

Also: rerun the cycle and rebuild gold twice, rows identical (SC-011 analogue); every row carries `rules_version` and
`max_bronze_id`; the D1 stream (`d1_silence.json`) excludes headways of an estimated departure and reports `n_excluded`.
Gold must equal the recomputation from raw events exactly (`n_headways`, `Σh`, `Σh²`, `Σhp`, `Σhp²`).

Cycle time: record `duration_ms` of the `refresh_cycle` log lines (or time `run_cycle`) over a C1 demo run; target p95 at most
250 ms; the baseline measured on 2026-11-21 is median 48 ms, p95 68 ms, max 81 ms.

`RULES_VERSION` `1.3.0`.

## Phase 3: P(board ≤ t) (US4)

Write first: pure `boarding` tests (arrival exactly at a departure counts with wait 0; a rider with no departure only in
`n_riders`; open rider moves into the columns after a later cycle; duplicate rider counted once through ingestion; unknown stop counted
nowhere), the oracle comparison, the view and the read queries (null when no rider, `final` filter).

Expected on the current (post-US1) reference, C1 seed 42 without hold, cycle at 22:45:00Z (recomputed from raw events with the
spec definition; the numerators agree with the mock):

| Band (local) | n_riders | ≤ 5 min | ≤ 10 min | ≤ 15 min |
|---|---|---|---|---|
| 68 (17:00–17:15) | 9 | 3 | 9 | 9 |
| 69 (17:15–17:30) | 16 | 10 | 16 | 16 |
| 70 (17:30–17:45), open riders 6 | 21 | 9 | 14 | 15 |

Per-stop counts equal the oracle (46 riders; 37 at P-883). Bands 68 and 69 reproduce the mock's 33 % and 62 % at ≤ 5 min (62.5 %
unrounded) and 100 % at ≤ 10 min. Band 70 gives 42.9 % at ≤ 5 min and 66.7 % at ≤ 10 min, not the mock's 60 % (9/15) and
93 % (14/15): the mock leaves the 6 open riders out of the denominator, the spec counts them (decision 3). The queries read only
`final` bands for reports; at 22:45:00Z only bands 68 and 69 are final.
`RULES_VERSION` `1.4.0`.

## Phase 4: guards (US5 + US6)

Write first:

1. Ingestion: `distance_along_m = 99999` rejected with `value_out_of_range` and the original message kept; 5,119.4 and 0
   accepted; unreadable bound accepts; connection error propagates; `contracts/` unchanged (`git diff feature/004-scenario-injectors -- contracts docs/adr` is empty).
2. Pipeline: the same row inserted straight into bronze as the newest report of an on-corridor bus (B-105 at the end of the
   C1 run) gives a cycle that completes and writes a snapshot; B-105 is `estimated` and in `sources_down`; the 4 other
   in-service buses keep their state; a later valid position returns it to `live`. On the unfixed code this fails with
   `ValidationError` in `CorridorNowV100` (reproduced 2026-11-21).
3. Clock: `trusted_clock` unit matrix (0, 1, 2, 3, 5 buses; 120 s and 121 s; lower-middle median); integration with a
   2030-01-01 `bus_position` of B-101: `as_of_ts` stays on or after 2026-11-24T22:00Z and not in 2030; the other buses stay `live`
   in 100 % of the cycles after the injection; B-101 `estimated` and listed down; recovery after a valid report. On the unfixed code
   `resolve_as_of(conn, "data")` returns 2030-01-01 (reproduced 2026-11-21).
4. The simulator at its normal pace has no untrusted bus in any cycle, and the golden hashes are unchanged by this phase.

`RULES_VERSION` `1.5.0`. Then run the CI-ready command; coverage above 80 %.

## Final gate (end of Phase 4)

| Gate | Check |
|---|---|
| Gate 1 (turn 1) | new gold tables typed and checked; read objects still built through the generated models |
| Gate 2 | CI-ready command green, coverage above 80 % |
| SC-014 | `git diff feature/004-scenario-injectors -- contracts docs/adr` is empty |
| Cycle time | p95 at most 250 ms at demo length; at 4 simulated hours at most 1.5 s |
| Notes | `verification.md` with old and new hashes, oracle table, cycle times, coverage, and the data owner's verifier output |

## Scratch measurement recipe (what the plan used)

On a throwaway database cloned from a template built with `src/data/tests/db_helpers.py`, ingest the simulator stream with
`ingest()`, run `run_cycle(conn, as_of, notify=False)` for as-of times every 25 s, and time each. The 2026-11-21 figures are
in research R12. Never write to the compose database from tests.
