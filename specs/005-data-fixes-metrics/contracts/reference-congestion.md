# Reference build: local hour of the congestion factor

## Rule (US1, FR-010 to FR-013)

- Input: `data/raw/plata/simm_corredor_c6008.csv`. `FECHAHORA` is **UTC** (ISO 8601 with a trailing `Z`; all 109,085 rows).
- Each row goes to local hour `timebands.local_hour_band(FECHAHORA)` (UTC−5, `LOCAL_OFFSET`). A row that cannot be parsed is
  skipped, as before. An hour with no data uses the overall mean with a warning, as before (none occurs).
- `congestion_factor[h] = round(mean(VELOCIDAD at local hour h) / free_flow_kmh, 4)`, free flow unchanged.
- The simulator (`ref.congestion[hour_of(t)]`) and M1 (`hour_band`) keep reading by local hour.

## Result

The new `congestion_factor.csv` is the old file with its rows rotated by five: `new[h] = old[(h + 5) mod 24]`
(maximum difference 0). 17 h local 0.5011 → 0.4816; slowest hour 23 h → 18 h (0.4575); highest factor 08 h → 03 h (0.5656).

## Regeneration and recording procedure (Phase 1)

1. Write the tests first (they fail on the unfixed code): the committed-CSV test (CI-safe) and the build test that groups the
   raw file by `UTC hour − 5` (skips without `data/raw/`).
2. Change `src/data/reference/build.py` and the sentence in `src/data/reference/sources.py`.
3. `python -m src.data.reference.build` (needs `data/raw/`). Check `git diff --stat data/reference/`: only
   `congestion_factor.csv` and `SOURCES.md` change. A rebuild with the unfixed code on 2026-11-21 reproduced all seven files
   byte for byte, so any other difference is a defect.
4. Measure the new golden hashes (seeds 42 and 7, 3,600 s, no scenario, no holds) and update `test_simulator_golden_hash.py`
   (hashes, 3,831 lines and 1,433,630 bytes for seed 42). Dry-run values: seed 42 `8bae0e52…690bc`, seed 7 `27a8206e…d4df7e`.
5. Re-pin the nine tests that pin seconds of the C1 hold run (research R1).
6. Record in `specs/005-data-fixes-metrics/verification.md`: old and new hashes, the 24 factors, the one-off comparison with
   `git show HEAD:data/reference/congestion_factor.csv` (new `h` = old `(h + 5) mod 24`, maximum difference 0), the data owner's
   verifier output and the commit of the CSV.
7. `data/raw/` is not in git and CI skips the build tests; the committed CSV is enough to run every other test.

## Oracles: post-US1 only (data owner, 2026-11-21)

No frozen copy of the old CSV is kept and no test substitutes the simulator's reference. Every oracle (stop EWT, rider
counts) is computed on the stream the committed CSV produces. The old file is compared once, from git, in Phase 1 (step 6).

## Data owner's verifier (Phase 1 exit)

After step 3 the data owner re-runs the mock (`mock_calculos.py`, command in [../quickstart.md](../quickstart.md)) on the
regenerated file. Required: P-888..P-900, departures 17:28:55 to 17:44:55 local, **+25.8 s (27 intervals) without the hold and
+10.6 s (28 intervals) with it**; slowest hour 18 h; every hour of the congestion table printing ±0.0 %. The phase is not
closed otherwise.
