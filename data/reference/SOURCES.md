# Reference Data Sources

One entry per output file.  Each records source URL, license, download date and the transformation applied (FR-007).

## congestion_factor.csv

- **Raw source**: `plata/simm_corredor_c6008.csv`
- **Source URL / origin**: Sistema Inteligente de Movilidad de Medellín (SIMM) — provided by Área Metropolitana del Valle de Aburrá
- **License**: Uso interno / Internal use
- **Download date**: 2026-11-17
- **Transformation**: Grouped FECHAHORA by UTC hour; computed mean(VELOCIDAD) per hour. Corridor free-flow speed = length-weighted mean of v_libre_kmh across 17 segments from tramos_c6008_s1_osm.csv. congestion_factor[h] = mean(VELOCIDAD[h]) / free_flow_speed. Values outside the 0.43–0.56 sanity band emit a warning and are kept as computed.

## demand_params.csv

- **Raw source**: `metro/Afluencia_Metro_2025.xlsx + medata/pasajeros_movilizados_mensual_metro_de_medellin.csv`
- **Source URL / origin**: Afluencia_Metro_2025.xlsx — Metro de Medellín; pasajeros_movilizados_mensual_metro_de_medellin.csv — MeData (Alcaldía de Medellín)
- **License**: Uso interno / Internal use
- **Download date**: 2026-11-17
- **Transformation**: Metro Line A hourly shape: sum of LÍNEA A ridership per hour across all 2025 days from Afluencia_Metro_2025.xlsx, normalized to sum = 1.0. Basin-6 feeder share: sum(METRO_CUENCA_6) / sum(METRO_LINEA_A) for calendar year 2019 (12 months 201901–201912) from MeData monthly series. 2019 chosen as the last pre-pandemic year with 12 complete months of data (data-owner decision: not the last 12 months, which are pandemic-affected).

## segments.csv

- **Raw source**: `plata/tramos_c6008_s1_osm.csv`
- **Source URL / origin**: OpenStreetMap + PLATA (Proyecto de Levantamiento de Atributos de Transporte Alimentador) — provided by Área Metropolitana del Valle de Aburrá
- **License**: ODbL (OSM) / Uso interno (PLATA)
- **Download date**: 2026-11-17
- **Transformation**: All 17 direction-1 segments from tramos_c6008_s1_osm.csv. Columns retained: tramo→segment_id, desde→from_name, largo_m→length_m, v_libre_kmh→free_flow_kmh, pendiente_pct→slope_pct. Sorted by segment_id.

## stops.csv

- **Raw source**: `metro_capas/paradas_alimentadoras.geojson + metro_capas/rutas_alimentadoras.geojson`
- **Source URL / origin**: Metro de Medellín GIS layers — provided by Área Metropolitana del Valle de Aburrá
- **License**: Uso interno / Internal use
- **Download date**: 2026-11-17
- **Transformation**: Filtered paradas_alimentadoras.geojson for ruta='C6-008' and itinerario='C6-008 La Libertad' (direction 1, 18 stops). stop_id = 'P-<objectid>' (real objectid from the GeoJSON feature). distance_along_m = projected distance of stop point onto the direction-1 route line from rutas_alimentadoras.geojson (sentido=1). segment_id assigned from segments.csv by distance. Sorted by distance_along_m.

## train_arrivals.csv

- **Raw source**: `metro/GTFS-Metro_de_Medellin_2025.zip`
- **Source URL / origin**: GTFS-Metro de Medellín 2025 — Metro de Medellín
- **License**: Uso interno / Internal use
- **Download date**: 2026-11-17
- **Transformation**: Filtered trips.txt for route_id='LA' and service_id='Laboral'. Joined with stop_times.txt where stop_id='PRA' (Prado station). Output columns: train_trip_id (GTFS trip_id), arrival_time, service_id. Sorted by arrival_time.
