# Gold stop metrics: tables, view and read queries

Columns and rules are defined in [../data-model.md](../data-model.md) (E4–E8). This file fixes how they are **read** and
what a reader may rely on. The backend filters and sums; it never computes headways, waits or counts (ADR-0003, ADR-0006).
The queries are the contract; they are run by the integration tests against an oracle.

## Guarantees

1. **Determinism.** The same bronze events (same `max_bronze_id`) and the same `rules_version` give identical rows in all
   four tables (SC-005, SC-011).
2. **Lineage.** Every row has `rules_version` and `max_bronze_id`, both NOT NULL.
3. **Additivity.** Every numeric column of E5–E7 is a count or a sum, so any aggregation over stops, bands or days is a
   `sum`. Ratios and EWT are computed in the query, never stored.
4. **Absent means zero.** `stop_ewt_band` and `stop_boarding_band` are sparse. A missing (`local_date`, `band`, `stop_id`)
   row means no headway or no rider.
5. **Null, not zero.** A ratio over an empty set is NULL (`nullif`), and `computable = false` shows "—", never 0.
6. **Open data is marked.** `stop_ewt_band` holds closed bands only. `stop_boarding_band` also holds the open band, and
   the view says which bands are `closed` and `final`. Reports use `final` bands.
7. **Reports use band rows, the dashboard uses the snapshot row.** `gold.service_metric` and `service_metric_stop` are the
   trailing 15-minute live value; payment and reports read `stop_ewt_band` and `stop_boarding_band` (FR-034).

## Q-S1. Live EWT of one snapshot (replaces data-contract Q4)

```sql
SELECT s.as_of_ts, m.n_headways, m.mean_wait_s, m.scheduled_wait_s, m.ewt_s, m.computable
FROM gold.service_metric m JOIN gold.snapshots s USING (snapshot_id)
WHERE m.snapshot_id = %(snapshot_id)s;
```

Same columns as before. `computable = false` when fewer than `config.corridor_settings.min_stop_headways` (5) headways
are in the window; then `mean_wait_s`, `scheduled_wait_s` and `ewt_s` are NULL and `n_headways` still shows the count.

## Q-S2. Live EWT per stop of one snapshot

```sql
SELECT stop_id, n_headways, n_excluded, computable,
       sum_headway_sq_s / nullif(2 * sum_headway_s, 0)
     - sum_planned_sq_s / nullif(2 * sum_planned_s, 0) AS ewt_s
FROM gold.service_metric_stop
WHERE snapshot_id = %(snapshot_id)s
ORDER BY stop_id;
```

18 rows. A stop with `computable = false` has `ewt_s` NULL (the sums are 0).

## Q-E1. EWT over a range of closed bands, corridor and per stop (reports, payment)

```sql
-- corridor
SELECT sum(n_headways) AS n_headways, sum(n_excluded) AS n_excluded,
       sum(sum_headway_sq_s) / nullif(2 * sum(sum_headway_s), 0)
     - sum(sum_planned_sq_s) / nullif(2 * sum(sum_planned_s), 0) AS ewt_s,
       sum(n_headways) >= (SELECT min_stop_headways FROM config.corridor_settings) AS computable,
       max(rules_version) AS rules_version, max(max_bronze_id) AS max_bronze_id
FROM gold.stop_ewt_band
WHERE local_date = %(day)s AND band BETWEEN %(from_band)s AND %(to_band)s;
-- per stop: the same select list plus stop_id, GROUP BY stop_id ORDER BY stop_id
```

The caller treats `ewt_s` as valid only when `computable` is true. Coverage is `n_headways / (n_headways + n_excluded)`.

## Q-P1. P(board ≤ t) for a range of bands, corridor and per stop

```sql
-- corridor, final bands only
SELECT sum(n_riders) AS n_riders,
       sum(n_board_le_5)::numeric  / nullif(sum(n_riders), 0) AS p_board_le_5,
       sum(n_board_le_10)::numeric / nullif(sum(n_riders), 0) AS p_board_le_10,
       sum(n_board_le_15)::numeric / nullif(sum(n_riders), 0) AS p_board_le_15
FROM gold.stop_boarding_band_v
WHERE local_date = %(day)s AND band BETWEEN %(from_band)s AND %(to_band)s AND final;
-- per stop: add stop_id to the select list and GROUP BY stop_id ORDER BY stop_id
```

`final` is dropped to see the provisional value of a band that is still filling (the dashboard may do this; reports must not).

## Known limitations (stated for every consumer)

- **Low demand, one dominant stop (finding O-1).** On C1 seed 42 (post-US1 stream) 37 of 46 riders (80.4 %) arrive at
  P-883, where departures are regular, so the corridor P(board ≤ 10 min) is 100 % in bands 68 and 69 even while the
  corridor has a gap downstream. Use the per-stop query as well. The demand model is not changed by this story.
- **Simple method.** The wait is measured to the next departure of any bus; full buses are ignored, and a rider who
  arrives while a bus dwells counts that bus. The FIFO method with capacity is Evolution.
- **Lost departures** during a silence of a bus shorten the number of headways and lengthen their neighbours. Accepted as a
  turn-1 limit (data owner, 2026-11-21; research R4). The silence shows as the bus being `estimated` (`sources_down`) and
  headways touching a departure reported after a gap of more than 120 s are in `n_excluded`; the lost departure itself leaves
  no row and is not counted.
- **Planned headway** is the single 600 s of `config.corridor_settings` for every stop and hour (A-3, A-10).

## Test matrix (integration, throwaway database)

| Check | Source of truth | Phase |
|---|---|---|
| live row and per-stop rows equal the oracle from raw events at several snapshots, with and without the hold | oracle module | 2 |
| band rows equal the oracle grouped by band; bands 69 + 70 sums on P-888..P-900 = 31 intervals (Σh 16,950, Σh² 12,010,450) without the hold, 32 (18,165; 12,361,525) with it | oracle module | 2 |
| `window_sums` over the 16-minute window gives +25.8 / +10.6 s, 27 / 28 intervals (current reference) | data owner mock | 2 |
| stop with one departure: row, `computable = false`, no effect on the corridor sums | unit | 2 |
| estimated departure: both headways excluded, `n_excluded` counted | unit and D1 stream | 2 |
| corridor row not computable below 5 headways; computable at 5 | unit and integration | 2 |
| rerun and rebuild give identical rows | SC-011 | 2, 3 |
| counts equal the oracle: bands 68 / 69 / 70 = 9 / 16 / 21 riders; ≤ 5: 3 / 10 / 9; ≤ 10: 9 / 16 / 14; ≤ 15: 9 / 16 / 15 | oracle module | 3 |
| rider with no departure is in `n_riders` only; arrival exactly at a departure counts with wait 0 | unit | 3 |
| duplicate `rider_arrival` counted once; rider at an unknown stop counted nowhere | integration | 3 |
| `P = Σ ≤ t / Σ riders`, NULL when no rider; `final` filter excludes the open band | read-query test | 3 |
