# Contract: Reference Data Files

**Authority**: this feature (FR-001..FR-008). Built reproducibly by
`src/reference/build.py` (`make reference`) from `data/raw/` (git-ignored) into
`data/reference/` (committed, total <1 MB). Two builds from the same raw sources
are byte-identical (FR-001).

## Files (under `data/reference/`)

### `segments.csv` — the 17 direction-1 segments (FR-002)

| Column | Type | Notes |
|---|---|---|
| `segment_id` | int 1..17 | Ordered along the corridor. |
| `from_name` | string | Real intersection name (source `desde`). |
| `length_m` | number >0 | Segment length, meters. |
| `free_flow_kmh` | number >0 | Free-flow speed. |
| `slope_pct` | number | Slope, percent (may be negative). |

Source: `data/raw/plata/tramos_c6008_s1_osm.csv`. Exactly 17 rows.

### `stops.csv` — real C6-008 stops (FR-003, FR-008)

| Column | Type | Notes |
|---|---|---|
| `stop_id` | string `P-<objectid>` | Real id derived from the stop's `objectid` in `paradas_alimentadoras.geojson` (R6). Used by fixtures and the contract examples. |
| `stop_name` | string | Real stop name (`parada`/`label`) from `paradas_alimentadoras.geojson`. |
| `distance_along_m` | number ≥0 | Distance from the corridor origin, computed by projecting the stop onto the direction-1 route line (meters). |
| `segment_id` | int | Corridor segment (1..17) the projected stop falls in. |

Built from the `ruta == "C6-008"` features of
`data/raw/metro_capas/paradas_alimentadoras.geojson`, filtered to direction 1
(Prado outbound) using `data/raw/metro_capas/rutas_alimentadoras.geojson`
(`sentido`). Fixtures MUST use these real `stop_id` values (FR-008). `stop_id` is
a string in the event schema, so adopting `P-<objectid>` needs no schema version
change.

### `train_arrivals.csv` — Prado weekday arrivals (FR-004)

| Column | Type | Notes |
|---|---|---|
| `train_trip_id` | string | GTFS `trip_id` (e.g. `METRO-A-0815`). Used by `rider_arrival` (`origin == "train"`). |
| `arrival_time` | `HH:MM:SS` | Arrival at Prado, line A, weekday service. |
| `service_id` | string | GTFS weekday calendar service id. |

Source: `data/raw/metro/GTFS-Metro_de_Medellin_2025.zip`.

### `congestion_factor.csv` — hourly factor (FR-005)

| Column | Type | Notes |
|---|---|---|
| `hour` | int 0..23 | Wall-clock hour. |
| `congestion_factor` | number | `mean(SIMM VELOCIDAD) / free_flow_speed`, where free-flow speed is the length-weighted mean of `v_libre_kmh` over the 17 corridor segments. |

Sources: `data/raw/plata/simm_corredor_c6008.csv` (hourly mean measured speed) +
`data/raw/plata/tramos_c6008_s1_osm.csv` (`v_libre_kmh`, length-weighted). 24
rows. No tuning constant is applied; the 0.43–0.56 band is only an expected
sanity check — values outside it emit a warning and are kept as computed (R7).

### `demand_params.csv` — demand shape + feeder share (FR-006)

| Column | Type | Notes |
|---|---|---|
| `hour` | int 0..23 | Wall-clock hour. |
| `metro_line_a_shape` | number | Hourly shape of Metro line A (relative). |
| `feeder_share_basin6` | number | Basin-6 feeder share (constant across hours), from the MeData basin-6 series over line A. |

Sources: `data/raw/metro/Afluencia_Metro_2025.xlsx` (hourly shape),
`data/raw/medata/pasajeros_movilizados_mensual_metro_de_medellin.csv`
(`METRO_CUENCA_6` over `METRO_LINEA_A`, per FR-006). The EOD
(`data/raw/plata/eod_macrozonas.csv`) is not used in this story (R9).

### `SOURCES.md` — provenance (FR-007)

One line per output file: `source URL | license | download date | transformation
applied`. The build writes it; the test asserts one line per file and
completeness.

## Reproducibility rules

- No wall-clock dependence; no unsorted iteration over floats/sets; fixed
  rounding.
- A missing required raw source fails the build with a clear message naming the
  missing source (spec edge case).
- Total size under 1 MB (FR-001).
