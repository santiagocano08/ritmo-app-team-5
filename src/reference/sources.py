"""
Source registry for the reference data build.

Each entry records source URL, license, download date and the transformation
applied, as required by FR-007.  The registry is used by build.py to generate
SOURCES.md alongside the output CSV files.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SourceEntry:
    output_file: str        # filename in data/reference/
    raw_file: str           # relative path from data/raw/
    source_url: str         # where the raw file was obtained
    license: str            # license of the raw data
    download_date: str      # ISO date string (approximate)
    transformation: str     # plain-English description of the transformation


# Registry: one entry per output file in data/reference/ (FR-007).
# Keep entries sorted by output_file for deterministic SOURCES.md output.
REGISTRY: list[SourceEntry] = [
    SourceEntry(
        output_file="congestion_factor.csv",
        raw_file="plata/simm_corredor_c6008.csv",
        source_url="Sistema Inteligente de Movilidad de Medellín (SIMM) — provided by Área Metropolitana del Valle de Aburrá",
        license="Uso interno / Internal use",
        download_date="2026-11-17",
        transformation=(
            "Grouped FECHAHORA by UTC hour; computed mean(VELOCIDAD) per hour. "
            "Corridor free-flow speed = length-weighted mean of v_libre_kmh across "
            "17 segments from tramos_c6008_s1_osm.csv. "
            "congestion_factor[h] = mean(VELOCIDAD[h]) / free_flow_speed. "
            "Values outside the 0.43–0.56 sanity band emit a warning and are kept as computed."
        ),
    ),
    SourceEntry(
        output_file="demand_params.csv",
        raw_file="metro/Afluencia_Metro_2025.xlsx + medata/pasajeros_movilizados_mensual_metro_de_medellin.csv",
        source_url=(
            "Afluencia_Metro_2025.xlsx — Metro de Medellín; "
            "pasajeros_movilizados_mensual_metro_de_medellin.csv — MeData (Alcaldía de Medellín)"
        ),
        license="Uso interno / Internal use",
        download_date="2026-11-17",
        transformation=(
            "Metro Line A hourly shape: sum of LÍNEA A ridership per hour across all 2025 days "
            "from Afluencia_Metro_2025.xlsx, normalized to sum = 1.0. "
            "Basin-6 feeder share: sum(METRO_CUENCA_6) / sum(METRO_LINEA_A) for calendar year 2019 "
            "(12 months 201901–201912) from MeData monthly series. "
            "2019 chosen as the last pre-pandemic year with 12 complete months of data "
            "(data-owner decision: not the last 12 months, which are pandemic-affected)."
        ),
    ),
    SourceEntry(
        output_file="demand_volume.csv",
        raw_file="medata/pasajeros_movilizados_mensual_metro_de_medellin.csv + metro_capas/paradas_alimentadoras.geojson",
        source_url="MeData (Alcaldía de Medellín); Metro de Medellín GIS layers",
        license="Uso interno / Internal use",
        download_date="2026-11-17",
        transformation=(
            "Direction-1 daily riders (data-owner decision, triangulation step A). "
            "daily_trips_both_dirs = mean_monthly(METRO_CUENCA_6 over 2019) / 30 "
            "x (stops of routes serving Prado / stops of basin 6) "
            "x (C6-008 stops / stops of routes serving Prado); daily_riders_dir1 = daily_trips_both_dirs / 2. "
            "Stop counts from paradas_alimentadoras.geojson: basin-6 = ruta starts with 'C6' (1191); "
            "Prado = linea or itinerario mentions 'Prado' (343); C6-008 = ruta == 'C6-008' (35). "
            "ASSUMPTION (simulator, not derived from data): of the direction-1 daily riders, 80 % arrive at "
            "Prado in Metro train batches (GTFS) and 20 % as street riders at the other stops; "
            "distributed over the day with the Metro Line A hourly shape of demand_params.csv. "
            "The basin-6 feeder share is already inside this volume and is not applied again."
        ),
    ),
    SourceEntry(
        output_file="segments.csv",
        raw_file="plata/tramos_c6008_s1_osm.csv",
        source_url="OpenStreetMap + PLATA (Proyecto de Levantamiento de Atributos de Transporte Alimentador) — provided by Área Metropolitana del Valle de Aburrá",
        license="ODbL (OSM) / Uso interno (PLATA)",
        download_date="2026-11-17",
        transformation=(
            "All 17 direction-1 segments from tramos_c6008_s1_osm.csv. "
            "Columns retained: tramo→segment_id, desde→from_name, largo_m→length_m, "
            "v_libre_kmh→free_flow_kmh, pendiente_pct→slope_pct. Sorted by segment_id."
        ),
    ),
    SourceEntry(
        output_file="stops.csv",
        raw_file="metro_capas/paradas_alimentadoras.geojson + metro_capas/rutas_alimentadoras.geojson",
        source_url="Metro de Medellín GIS layers — provided by Área Metropolitana del Valle de Aburrá",
        license="Uso interno / Internal use",
        download_date="2026-11-17",
        transformation=(
            "Filtered paradas_alimentadoras.geojson for ruta='C6-008' and "
            "itinerario='C6-008 La Libertad' (direction 1, 18 stops). "
            "stop_id = 'P-<objectid>' (real objectid from the GeoJSON feature). "
            "distance_along_m = projected distance of stop point onto the direction-1 "
            "route line from rutas_alimentadoras.geojson (sentido=1). "
            "segment_id assigned from segments.csv by distance. Sorted by distance_along_m."
        ),
    ),
    SourceEntry(
        output_file="train_arrivals.csv",
        raw_file="metro/GTFS-Metro_de_Medellin_2025.zip",
        source_url="GTFS-Metro de Medellín 2025 — Metro de Medellín",
        license="Uso interno / Internal use",
        download_date="2026-11-17",
        transformation=(
            "Filtered trips.txt for route_id='LA' and service_id='Laboral'. "
            "Joined with stop_times.txt where stop_id='PRA' (Prado station). "
            "Output columns: train_trip_id (GTFS trip_id), arrival_time, service_id. "
            "Sorted by arrival_time."
        ),
    ),
]


def generate_sources_md(output_dir: Path) -> str:
    """Generate the SOURCES.md content for the given output directory.

    Returns the Markdown string (without writing it).
    """
    lines = [
        "# Reference Data Sources",
        "",
        "One entry per output file.  Each records source URL, license, "
        "download date and the transformation applied (FR-007).",
        "",
    ]
    for entry in sorted(REGISTRY, key=lambda e: e.output_file):
        lines.append(f"## {entry.output_file}")
        lines.append("")
        lines.append(f"- **Raw source**: `{entry.raw_file}`")
        lines.append(f"- **Source URL / origin**: {entry.source_url}")
        lines.append(f"- **License**: {entry.license}")
        lines.append(f"- **Download date**: {entry.download_date}")
        lines.append(f"- **Transformation**: {entry.transformation}")
        lines.append("")
    return "\n".join(lines)
