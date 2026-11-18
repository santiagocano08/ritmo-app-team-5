"""
Reference data build: data/raw/ → data/reference/ (or $REFERENCE_OUTPUT_DIR).

Invoked by `make reference` or directly:
    python -m src.reference.build

The build is deterministic: fixed sort orders, fixed rounding, no wall-clock
dependence (FR-001).  Running it twice from the same raw inputs produces
byte-identical output.

The raw sources directory can be overridden with the RAW_DIR env var (used by
tests to inject a fake empty directory to test the missing-source error path).

Data-owner decisions encoded here:
  * Direction 1 stops = paradas_alimentadoras with ruta='C6-008' and
    itinerario='C6-008 La Libertad' (18 stops, objectids 883-900), projected on
    the rutas_alimentadoras C6-008 sentido=1 route line.
  * Prado train arrivals = GTFS stop_id 'PRA', service_id 'Laboral' (weekday).
  * Basin-6 feeder share = sum(METRO_CUENCA_6) / sum(METRO_LINEA_A) over
    calendar year 2019 (12 months 201901-201912), NOT the last 12 months
    (pandemic); recorded in SOURCES.md.
  * Peak hour = FIXED at 17:00 (line A PM peak, Afluencia 2025); recorded in
    research.md R14 and spec.md Assumptions.
  * 0.43-0.56 is a SANITY BAND: values outside it emit a warning and are kept
    as computed (never clamped).
"""
from __future__ import annotations

import csv
import io
import json
import math
import os
import sys
import warnings
import zipfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]

def _get_raw_dir() -> Path:
    env = os.environ.get("RAW_DIR")
    if env:
        return Path(env)
    return _REPO_ROOT / "data" / "raw"

def _get_output_dir() -> Path:
    env = os.environ.get("REFERENCE_OUTPUT_DIR")
    if env:
        return Path(env)
    return _REPO_ROOT / "data" / "reference"


# ---------------------------------------------------------------------------
# Missing-source guard
# ---------------------------------------------------------------------------

def _require_file(path: Path) -> None:
    """Raise a clear RuntimeError if a required raw source is missing."""
    if not path.exists():
        raise RuntimeError(
            f"Required raw source not found: {path}\n"
            f"Run the data download script or restore the raw sources to data/raw/."
        )


# ---------------------------------------------------------------------------
# 1. segments.csv — 17 direction-1 segments (FR-002)
# ---------------------------------------------------------------------------

def build_segments(raw_dir: Path, output_dir: Path) -> None:
    src = raw_dir / "plata" / "tramos_c6008_s1_osm.csv"
    _require_file(src)

    with open(src, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if len(rows) != 17:
        warnings.warn(
            f"tramos_c6008_s1_osm.csv has {len(rows)} rows; expected 17.",
            stacklevel=2,
        )

    output_rows = []
    for row in rows:
        output_rows.append({
            "segment_id": int(row["tramo"]),
            "from_name": row["desde"],
            "length_m": float(row["largo_m"]),
            "free_flow_kmh": float(row["v_libre_kmh"]),
            "slope_pct": float(row["pendiente_pct"]),
        })

    # Sort by segment_id for determinism
    output_rows.sort(key=lambda r: r["segment_id"])

    out = output_dir / "segments.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["segment_id", "from_name", "length_m", "free_flow_kmh", "slope_pct"]
        )
        writer.writeheader()
        for row in output_rows:
            writer.writerow({
                "segment_id": row["segment_id"],
                "from_name": row["from_name"],
                "length_m": f"{row['length_m']:.1f}",
                "free_flow_kmh": f"{row['free_flow_kmh']:.1f}",
                "slope_pct": f"{row['slope_pct']:.1f}",
            })


# ---------------------------------------------------------------------------
# 2. stops.csv — real C6-008 direction-1 stops with P-<objectid> ids (FR-003)
# ---------------------------------------------------------------------------

def _point_to_xy(coords: list) -> tuple[float, float]:
    """Extract (x, y) from a GeoJSON Point coordinate."""
    return float(coords[0]), float(coords[1])


def _project_point_onto_linestring(
    px: float, py: float, line_coords: list[list[float]]
) -> float:
    """Return the distance along a linestring where a point projects closest.

    Uses the minimum perpendicular distance from the point to each segment of
    the line, then accumulates length up to that segment.  Pure Python, no
    external geometry library (PostGIS is deferred to turn 3).
    """
    best_dist_sq = math.inf
    best_along = 0.0
    cumulative = 0.0

    for i in range(len(line_coords) - 1):
        ax, ay = float(line_coords[i][0]), float(line_coords[i][1])
        bx, by = float(line_coords[i + 1][0]), float(line_coords[i + 1][1])

        abx, aby = bx - ax, by - ay
        ab_len_sq = abx * abx + aby * aby

        if ab_len_sq < 1e-18:
            # Degenerate segment
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((px - ax) * abx + (py - ay) * aby) / ab_len_sq))

        cx, cy = ax + t * abx, ay + t * aby
        d_sq = (px - cx) ** 2 + (py - cy) ** 2

        if d_sq < best_dist_sq:
            best_dist_sq = d_sq
            # Distance along = cumulative length up to segment start + t * segment_length
            seg_len = math.sqrt(ab_len_sq)
            best_along = cumulative + t * seg_len

        # Convert degree distance to approximate meters (1 degree ≈ 111_320 m at equator)
        # This is good enough for a 5 km corridor; PostGIS is deferred.
        seg_len_deg = math.sqrt(ab_len_sq)
        cumulative += seg_len_deg

    # Convert degrees to approximate meters (Medellín latitude ~6.25°, cos(6.25°) ≈ 0.9940)
    LAT_RAD = 6.25 * math.pi / 180
    METERS_PER_DEG_LAT = 111_320.0
    METERS_PER_DEG_LON = 111_320.0 * math.cos(LAT_RAD)

    # Re-project properly: cumulative is in degrees; we need meters.
    # Recompute properly with meters.
    return _project_point_onto_linestring_m(px, py, line_coords)


def _deg_to_m(dx: float, dy: float) -> tuple[float, float]:
    """Convert degree deltas to approximate meters at Medellín latitude."""
    LAT_RAD = 6.25 * math.pi / 180
    mx = dx * 111_320.0 * math.cos(LAT_RAD)
    my = dy * 111_320.0
    return mx, my


def _project_point_onto_linestring_m(
    px: float, py: float, line_coords: list[list[float]]
) -> float:
    """Project point (lon, lat) onto a linestring; return distance along in meters."""
    best_dist_sq = math.inf
    best_along_m = 0.0
    cumulative_m = 0.0

    for i in range(len(line_coords) - 1):
        ax, ay = float(line_coords[i][0]), float(line_coords[i][1])
        bx, by = float(line_coords[i + 1][0]), float(line_coords[i + 1][1])

        # Convert to meters relative to 'a'
        abmx, abmy = _deg_to_m(bx - ax, by - ay)
        apmx, apmy = _deg_to_m(px - ax, py - ay)

        ab_len_sq = abmx * abmx + abmy * abmy
        if ab_len_sq < 1e-9:
            t = 0.0
        else:
            t = max(0.0, min(1.0, (apmx * abmx + apmy * abmy) / ab_len_sq))

        cx_m, cy_m = t * abmx, t * abmy
        d_sq = (apmx - cx_m) ** 2 + (apmy - cy_m) ** 2

        seg_len_m = math.sqrt(ab_len_sq)
        if d_sq < best_dist_sq:
            best_dist_sq = d_sq
            best_along_m = cumulative_m + t * seg_len_m

        cumulative_m += seg_len_m

    return best_along_m


def build_stops(raw_dir: Path, output_dir: Path, segments_path: Path) -> None:
    paradas_path = raw_dir / "metro_capas" / "paradas_alimentadoras.geojson"
    rutas_path = raw_dir / "metro_capas" / "rutas_alimentadoras.geojson"
    _require_file(paradas_path)
    _require_file(rutas_path)

    with open(paradas_path, encoding="utf-8") as f:
        paradas = json.load(f)
    with open(rutas_path, encoding="utf-8") as f:
        rutas = json.load(f)

    # Direction-1 route line: ruta='C6-008', sentido=1
    # (data-owner decision: itinerario 'C6-008 La Libertad')
    route_line = None
    for feat in rutas["features"]:
        p = feat["properties"]
        if p.get("ruta") == "C6-008" and p.get("sentido") == 1:
            route_line = feat
            break
    if route_line is None:
        raise RuntimeError(
            "Required raw source not found: rutas_alimentadoras.geojson — "
            "no feature with ruta='C6-008' and sentido=1"
        )

    # Extract route geometry coordinates
    geom = route_line["geometry"]
    if geom["type"] == "MultiLineString":
        # Flatten into one sequence
        coords = [c for segment in geom["coordinates"] for c in segment]
    else:
        coords = geom["coordinates"]  # LineString

    # Direction-1 stops: ruta='C6-008', itinerario='C6-008 La Libertad'
    # (data-owner decision per session context)
    dir1_stops = [
        feat for feat in paradas["features"]
        if feat["properties"].get("ruta") == "C6-008"
        and feat["properties"].get("itinerario") == "C6-008 La Libertad"
    ]

    # Load segments to assign segment_id
    with open(segments_path, newline="", encoding="utf-8") as f:
        seg_rows = list(csv.DictReader(f))
    # Build cumulative distance boundaries per segment
    # segments are ordered 1..17; boundary[i] = sum of length_m for segments 1..i
    cum = 0.0
    seg_boundaries: list[tuple[float, float, int]] = []  # (start_m, end_m, segment_id)
    for row in seg_rows:
        start = cum
        length = float(row["length_m"])
        cum += length
        seg_boundaries.append((start, cum, int(row["segment_id"])))

    def _assign_segment(dist_m: float) -> int:
        for start, end, seg_id in seg_boundaries:
            if dist_m <= end:
                return seg_id
        return seg_boundaries[-1][2]  # beyond last segment → last segment

    # Project each stop onto the route line and compute distance_along_m
    stop_rows = []
    for feat in dir1_stops:
        props = feat["properties"]
        stop_coords = feat["geometry"]["coordinates"]
        px, py = float(stop_coords[0]), float(stop_coords[1])
        dist_m = _project_point_onto_linestring_m(px, py, coords)
        seg_id = _assign_segment(dist_m)
        stop_rows.append({
            "stop_id": f"P-{props['objectid']}",
            "stop_name": props.get("parada") or props.get("label", ""),
            "distance_along_m": round(dist_m, 1),
            "segment_id": seg_id,
            "_objectid": int(props["objectid"]),  # for deterministic sort
        })

    # Sort by distance_along_m (then objectid for ties) for determinism
    stop_rows.sort(key=lambda r: (r["distance_along_m"], r["_objectid"]))

    out = output_dir / "stops.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["stop_id", "stop_name", "distance_along_m", "segment_id"]
        )
        writer.writeheader()
        for row in stop_rows:
            writer.writerow({
                "stop_id": row["stop_id"],
                "stop_name": row["stop_name"],
                "distance_along_m": f"{row['distance_along_m']:.1f}",
                "segment_id": row["segment_id"],
            })


# ---------------------------------------------------------------------------
# 3. train_arrivals.csv — Prado weekday arrivals from GTFS (FR-004)
#    Data-owner decision: stop_id='PRA', service_id='Laboral'
# ---------------------------------------------------------------------------

def build_train_arrivals(raw_dir: Path, output_dir: Path) -> None:
    gtfs_path = raw_dir / "metro" / "GTFS-Metro_de_Medellin_2025.zip"
    _require_file(gtfs_path)

    with zipfile.ZipFile(gtfs_path) as z:
        with z.open("GTFS-2025/trips.txt") as f:
            trips = list(csv.DictReader(io.TextIOWrapper(f)))
        with z.open("GTFS-2025/stop_times.txt") as f:
            stop_times = list(csv.DictReader(io.TextIOWrapper(f)))

    # Line A weekday trips (route_id='LA', service_id='Laboral')
    la_laboral: set[str] = {
        t["trip_id"]
        for t in trips
        if t["route_id"] == "LA" and t["service_id"] == "Laboral"
    }

    # PRA arrivals
    pra_arrivals = [
        st for st in stop_times
        if st.get("stop_id") == "PRA" and st["trip_id"] in la_laboral
    ]

    if not pra_arrivals:
        raise RuntimeError(
            "Required raw source not found: GTFS-Metro_de_Medellin_2025.zip — "
            "no Line A Laboral trips found at stop PRA"
        )

    output_rows = sorted(
        (
            {
                "train_trip_id": r["trip_id"],
                "arrival_time": r["arrival_time"],
                "service_id": "Laboral",
            }
            for r in pra_arrivals
        ),
        key=lambda r: r["arrival_time"],
    )

    out = output_dir / "train_arrivals.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["train_trip_id", "arrival_time", "service_id"]
        )
        writer.writeheader()
        writer.writerows(output_rows)


# ---------------------------------------------------------------------------
# 4. congestion_factor.csv — SIMM aggregated by hour (FR-005, R7)
#    0.43-0.56 is a SANITY BAND (warn, keep computed) — data-owner M2 fix.
# ---------------------------------------------------------------------------

def build_congestion_factor(raw_dir: Path, output_dir: Path, segments_path: Path) -> None:
    simm_path = raw_dir / "plata" / "simm_corredor_c6008.csv"
    segs_path = raw_dir / "plata" / "tramos_c6008_s1_osm.csv"
    _require_file(simm_path)
    _require_file(segs_path)

    # Corridor free-flow speed = length-weighted mean of v_libre_kmh (R7)
    with open(segs_path, newline="", encoding="utf-8") as f:
        seg_rows = list(csv.DictReader(f))
    total_len = sum(float(r["largo_m"]) for r in seg_rows)
    free_flow = sum(float(r["v_libre_kmh"]) * float(r["largo_m"]) for r in seg_rows) / total_len

    # Group SIMM VELOCIDAD by hour
    from collections import defaultdict
    hour_speeds: dict[int, list[float]] = defaultdict(list)
    with open(simm_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                hour = int(row["FECHAHORA"][11:13])
                v = float(row["VELOCIDAD"])
                hour_speeds[hour].append(v)
            except (ValueError, IndexError, KeyError):
                continue

    output_rows = []
    out_of_band: list[str] = []
    BAND_LOW, BAND_HIGH = 0.43, 0.56

    for h in range(24):
        speeds = hour_speeds[h]
        if speeds:
            mean_v = sum(speeds) / len(speeds)
        else:
            # No data for this hour: use overall mean
            all_speeds = [v for vs in hour_speeds.values() for v in vs]
            mean_v = sum(all_speeds) / len(all_speeds) if all_speeds else free_flow
            warnings.warn(f"No SIMM data for hour {h:02d}; using overall mean.", stacklevel=2)

        cf = round(mean_v / free_flow, 4)

        if not (BAND_LOW <= cf <= BAND_HIGH):
            out_of_band.append(f"  hour {h:02d}: {cf:.4f}")

        output_rows.append({"hour": h, "congestion_factor": cf})

    if out_of_band:
        band_msg = "\n".join(out_of_band)
        warnings.warn(
            f"Congestion factor sanity band [{BAND_LOW}–{BAND_HIGH}] exceeded for:\n"
            f"{band_msg}\n"
            f"Values kept as computed (the band is a sanity check, not a target).",
            stacklevel=2,
        )

    out = output_dir / "congestion_factor.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["hour", "congestion_factor"])
        writer.writeheader()
        for row in output_rows:
            writer.writerow({"hour": row["hour"], "congestion_factor": f"{row['congestion_factor']:.4f}"})


# ---------------------------------------------------------------------------
# 5. demand_params.csv — Metro line A hourly shape + basin-6 feeder share (FR-006, R9)
#    Data-owner decision: feeder share = sum(METRO_CUENCA_6)/sum(METRO_LINEA_A)
#    over calendar year 2019 (12 months), NOT the last 12 months (pandemic).
# ---------------------------------------------------------------------------

def build_demand_params(raw_dir: Path, output_dir: Path) -> None:
    afluencia_path = raw_dir / "metro" / "Afluencia_Metro_2025.xlsx"
    medata_path = raw_dir / "medata" / "pasajeros_movilizados_mensual_metro_de_medellin.csv"
    _require_file(afluencia_path)
    _require_file(medata_path)

    # --- Metro Line A hourly shape from Afluencia_Metro_2025.xlsx ---
    import openpyxl
    wb = openpyxl.load_workbook(str(afluencia_path), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    # Row 0: header "Día", "Línea de Servicio", "Hora de operación"
    # Row 1: None, None, hour columns (datetime.time objects), "Total general"
    # Rows 2+: data rows
    # Hours 4–23 are in columns index 2..21
    HOUR_COLS = list(range(2, 22))   # column indices 2..21 → hours 4..23
    HOURS = list(range(4, 24))       # 4, 5, ..., 23

    hour_total: dict[int, float] = {h: 0.0 for h in HOURS}
    linea_a_rows = [r for r in rows if r[1] == "LÍNEA A"]

    for row in linea_a_rows:
        for col_idx, hour in zip(HOUR_COLS, HOURS):
            v = row[col_idx]
            if isinstance(v, (int, float)) and v:
                hour_total[hour] += float(v)

    total = sum(hour_total.values())
    if total == 0:
        raise RuntimeError(
            "Required raw source not found: Afluencia_Metro_2025.xlsx — "
            "no LÍNEA A data found"
        )

    # Normalize shape; hours not in 4-23 get 0.0
    hourly_shape: dict[int, float] = {}
    for h in range(24):
        hourly_shape[h] = round(hour_total.get(h, 0.0) / total, 6)

    # --- Basin-6 feeder share from MeData 2019 (calendar year, pre-pandemic) ---
    with open(medata_path, newline="", encoding="utf-8") as f:
        medata_rows = list(csv.DictReader(f))

    c6_2019 = [
        int(r["pas_valor"])
        for r in medata_rows
        if r["pas_lineametro"] == "METRO_CUENCA_6" and r["pas_periodo"].startswith("2019")
    ]
    la_2019 = [
        int(r["pas_valor"])
        for r in medata_rows
        if r["pas_lineametro"] == "METRO_LINEA_A" and r["pas_periodo"].startswith("2019")
    ]

    if len(c6_2019) != 12 or len(la_2019) != 12:
        raise RuntimeError(
            f"Required raw source not found: MeData 2019 annual data — "
            f"expected 12 months each for METRO_CUENCA_6 and METRO_LINEA_A, "
            f"got {len(c6_2019)} and {len(la_2019)}"
        )

    feeder_share = round(sum(c6_2019) / sum(la_2019), 6)

    out = output_dir / "demand_params.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["hour", "metro_line_a_shape", "feeder_share_basin6"]
        )
        writer.writeheader()
        for h in range(24):
            writer.writerow({
                "hour": h,
                "metro_line_a_shape": f"{hourly_shape[h]:.6f}",
                # Same value every row (single constant; R9)
                "feeder_share_basin6": f"{feeder_share:.6f}",
            })


# ---------------------------------------------------------------------------
# 6. SOURCES.md (FR-007)
# ---------------------------------------------------------------------------

def build_sources_md(output_dir: Path) -> None:
    from src.reference.sources import generate_sources_md
    content = generate_sources_md(output_dir)
    (output_dir / "SOURCES.md").write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build(raw_dir: Path | None = None, output_dir: Path | None = None) -> None:
    """Run the full reference data build.

    Args:
        raw_dir: Override for the raw sources directory (default: data/raw/).
        output_dir: Override for the output directory (default: data/reference/).
    """
    if raw_dir is None:
        raw_dir = _get_raw_dir()
    if output_dir is None:
        output_dir = _get_output_dir()

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building reference data: {raw_dir} → {output_dir}", file=sys.stderr)

    # 1. Segments first (stops and congestion_factor depend on the segment list)
    print("  Building segments.csv ...", file=sys.stderr)
    build_segments(raw_dir, output_dir)

    # 2. Stops (depends on segments.csv for segment_id assignment)
    print("  Building stops.csv ...", file=sys.stderr)
    build_stops(raw_dir, output_dir, output_dir / "segments.csv")

    # 3. Train arrivals
    print("  Building train_arrivals.csv ...", file=sys.stderr)
    build_train_arrivals(raw_dir, output_dir)

    # 4. Congestion factor
    print("  Building congestion_factor.csv ...", file=sys.stderr)
    build_congestion_factor(raw_dir, output_dir, output_dir / "segments.csv")

    # 5. Demand params
    print("  Building demand_params.csv ...", file=sys.stderr)
    build_demand_params(raw_dir, output_dir)

    # 6. SOURCES.md
    print("  Writing SOURCES.md ...", file=sys.stderr)
    build_sources_md(output_dir)

    # Report total size
    total_bytes = sum(f.stat().st_size for f in output_dir.rglob("*") if f.is_file())
    print(
        f"Done. Total size: {total_bytes / 1024:.1f} KiB "
        f"({'OK' if total_bytes < 1_048_576 else 'WARNING: exceeds 1 MiB'}).",
        file=sys.stderr,
    )


if __name__ == "__main__":
    build()
