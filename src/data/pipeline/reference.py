"""Load the static reference tables of `config` (006 adds the Metro train arrivals) from data/reference/*.csv (FR-001, R11).

DELETE + INSERT in the caller's transaction; parameterized statements only. Loading twice
leaves the tables unchanged. `stop_seq` is the file order of stops.csv.
"""
from __future__ import annotations

import csv
from pathlib import Path

import psycopg

REFERENCE_DIR = Path(__file__).resolve().parents[3] / "data" / "reference"


def _rows(directory: Path, name: str) -> list[dict]:
    with (directory / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _train_arrivals(rows: list[dict]) -> list[tuple[int, str]]:
    """(second of day, train trip) of the rows the simulator uses: a later second than a day is ignored (006 M2)."""
    out = []
    for r in rows:
        h, m, s = (int(x) for x in r["arrival_time"].split(":"))
        sec = h * 3600 + m * 60 + s
        if sec < 86400:
            out.append((sec, r["train_trip_id"]))
    return sorted(out)


def load_reference(conn: psycopg.Connection, directory: Path = REFERENCE_DIR) -> None:
    """Replace the six `config.ref_*` tables with the CSV contents, in one transaction."""
    stops = _rows(directory, "stops.csv")
    segments = _rows(directory, "segments.csv")
    congestion = _rows(directory, "congestion_factor.csv")
    shape = _rows(directory, "demand_params.csv")
    volume = _rows(directory, "demand_volume.csv")
    trains = _train_arrivals(_rows(directory, "train_arrivals.csv"))

    with conn.transaction():
        with conn.cursor() as cur:
            for table in ("ref_stops", "ref_segments", "ref_congestion_factor",
                          "ref_demand_shape", "ref_demand_volume", "ref_train_arrival"):
                cur.execute(f"DELETE FROM config.{table}")  # noqa: S608 - fixed table names
            cur.executemany(
                "INSERT INTO config.ref_stops (stop_seq, stop_id, distance_along_m, segment_id) "
                "VALUES (%s, %s, %s, %s)",
                [(n, r["stop_id"], r["distance_along_m"], int(r["segment_id"]))
                 for n, r in enumerate(stops, start=1)])
            cur.executemany(
                "INSERT INTO config.ref_segments (segment_id, length_m, free_flow_kmh) VALUES (%s, %s, %s)",
                [(int(r["segment_id"]), r["length_m"], r["free_flow_kmh"]) for r in segments])
            cur.executemany(
                "INSERT INTO config.ref_congestion_factor (hour, congestion_factor) VALUES (%s, %s)",
                [(int(r["hour"]), r["congestion_factor"]) for r in congestion])
            cur.executemany(
                "INSERT INTO config.ref_demand_shape (hour, metro_line_a_shape) VALUES (%s, %s)",
                [(int(r["hour"]), r["metro_line_a_shape"]) for r in shape])
            cur.executemany(
                "INSERT INTO config.ref_demand_volume (daily_riders_dir1) VALUES (%s)",
                [(r["daily_riders_dir1"],) for r in volume])
            cur.executemany(
                "INSERT INTO config.ref_train_arrival (arrival_sec, train_trip_id) VALUES (%s, %s) "
                "ON CONFLICT DO NOTHING", trains)
