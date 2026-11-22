"""T016 — DDL, seed values and reference tables (FR-034, FR-028, FR-017, R11, SC-008)."""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

import psycopg
import pytest

from src.pulsoflota.config import get_sim_planned_headway_s

ROOT = Path(__file__).resolve().parents[4]
REF = ROOT / "data" / "reference"
INIT = ROOT / "src" / "data" / "db" / "init"

TABLES = {
    "config": ["corridor_settings", "fleet_roster", "enabled_stops", "ref_stops", "ref_segments",
               "ref_congestion_factor", "ref_demand_shape", "ref_demand_volume", "seed_recommendation"],
    "silver": ["position_history", "incidents", "bus_current_state", "stop_visits", "segment_traversals"],
    "gold": ["snapshots", "source_status", "corridor_now", "decision_inputs", "service_metric",
             "m1_baseline", "m2_baseline", "incident", "instruction_status"],
}
GOLD_TABLES = TABLES["gold"]


@pytest.fixture()
def conn(module_db_dsn):
    with psycopg.connect(module_db_dsn) as c:
        yield c


def _csv(name: str) -> list[dict]:
    with (REF / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_all_tables_exist(conn) -> None:
    for schema, names in TABLES.items():
        for name in names:
            assert conn.execute("SELECT to_regclass(%s)", (f"{schema}.{name}",)).fetchone()[0] is not None, \
                f"{schema}.{name} missing"


def test_incident_current_view_exists(conn) -> None:
    """004: the view over the newest snapshot of gold.incident (init script 007)."""
    assert conn.execute("SELECT to_regclass('gold.incident_current')").fetchone()[0] is not None
    assert conn.execute("SELECT relkind FROM pg_class WHERE oid = 'gold.incident_current'::regclass").fetchone()[0] == "v"


def test_corridor_settings_seed(conn) -> None:
    row = conn.execute(
        "SELECT corridor_id, direction, headway_planned_s, drivers_free, hold_penalty_s, "
        "early_departure_penalty_s, min_sample_count, m2_stop_id FROM config.corridor_settings").fetchall()
    assert row == [("C6-008", 1, Decimal(600), 2, Decimal(0), Decimal(0), 5, "P-883")]


def test_planned_headway_equals_simulator_default(conn, monkeypatch) -> None:
    """R14: the simulator and the gold rules read the same planned value from separate places."""
    monkeypatch.delenv("SIM_PLANNED_HEADWAY_S", raising=False)
    seeded = conn.execute("SELECT headway_planned_s FROM config.corridor_settings").fetchone()[0]
    assert seeded == get_sim_planned_headway_s()


def test_roster_and_enabled_stops_seed(conn) -> None:
    roster = conn.execute("SELECT bus_id, role FROM config.fleet_roster ORDER BY bus_id").fetchall()
    assert roster == [(f"B-10{i}", "in_service" if i <= 5 else "reserve") for i in range(1, 8)]
    stops = [r[0] for r in conn.execute("SELECT stop_id FROM config.enabled_stops ORDER BY stop_id")]
    assert stops == [f"P-{n}" for n in range(883, 901)]


def test_reference_tables_equal_the_csv_files(conn) -> None:
    stops = _csv("stops.csv")
    got = conn.execute("SELECT stop_seq, stop_id, distance_along_m FROM config.ref_stops ORDER BY stop_seq").fetchall()
    assert [(s, i, float(d)) for s, i, d in got] == [
        (n, r["stop_id"], float(r["distance_along_m"])) for n, r in enumerate(stops, start=1)]
    seg = _csv("segments.csv")
    got = conn.execute("SELECT segment_id, length_m, free_flow_kmh FROM config.ref_segments ORDER BY 1").fetchall()
    assert [(i, float(a), float(b)) for i, a, b in got] == [
        (int(r["segment_id"]), float(r["length_m"]), float(r["free_flow_kmh"])) for r in seg]
    cong = _csv("congestion_factor.csv")
    got = conn.execute("SELECT hour, congestion_factor FROM config.ref_congestion_factor ORDER BY 1").fetchall()
    assert [(h, float(f)) for h, f in got] == [(int(r["hour"]), float(r["congestion_factor"])) for r in cong]
    shape = _csv("demand_params.csv")
    got = conn.execute("SELECT hour, metro_line_a_shape FROM config.ref_demand_shape ORDER BY 1").fetchall()
    assert [(h, float(f)) for h, f in got] == [(int(r["hour"]), float(r["metro_line_a_shape"])) for r in shape]
    vol = _csv("demand_volume.csv")
    got = conn.execute("SELECT daily_riders_dir1 FROM config.ref_demand_volume").fetchall()
    assert [float(r[0]) for r in got] == [float(vol[0]["daily_riders_dir1"])]


def _dump_reference(conn) -> list:
    out = []
    for t in TABLES["config"][3:]:
        out.append(conn.execute(f"SELECT * FROM config.{t} ORDER BY 1").fetchall())  # noqa: S608 - fixed names
    return out


def test_loading_reference_twice_changes_nothing(conn) -> None:
    from src.data.pipeline.reference import load_reference

    before = _dump_reference(conn)
    load_reference(conn)
    conn.commit()
    load_reference(conn)
    conn.commit()
    assert _dump_reference(conn) == before


def test_snapshots_unique_key(conn) -> None:
    conn.execute(
        "INSERT INTO gold.snapshots (snapshot_id, as_of_ts, rules_version, max_bronze_id) "
        "VALUES ('aaaa0001-0000-4000-8000-000000000001', '2026-11-24T08:00:00Z', '1.0.0', 5)")
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(
            "INSERT INTO gold.snapshots (snapshot_id, as_of_ts, rules_version, max_bronze_id) "
            "VALUES ('aaaa0001-0000-4000-8000-000000000002', '2026-11-24T08:00:00Z', '1.0.0', 5)")
    conn.rollback()


@pytest.mark.parametrize("table", GOLD_TABLES)
def test_gold_tables_carry_non_null_lineage(conn, table: str) -> None:
    rows = conn.execute(
        "SELECT column_name, is_nullable FROM information_schema.columns "
        "WHERE table_schema = 'gold' AND table_name = %s", (table,)).fetchall()
    cols = dict(rows)
    assert cols.get("rules_version") == "NO", f"gold.{table}.rules_version must be NOT NULL"
    assert cols.get("max_bronze_id") == "NO", f"gold.{table}.max_bronze_id must be NOT NULL"


def test_check_constraints(conn) -> None:
    bad = [
        "INSERT INTO gold.m1_baseline (segment_id, hour_band, forecast_travel_s, source, n_samples, rules_version, max_bronze_id)"
        " VALUES (1, 0, -1, 'observed', 0, '1.0.0', 0)",
        "INSERT INTO gold.m1_baseline (segment_id, hour_band, forecast_travel_s, source, n_samples, rules_version, max_bronze_id)"
        " VALUES (1, 0, 10, 'guess', 0, '1.0.0', 0)",
        "INSERT INTO gold.m2_baseline (band, stop_id, arrivals_forecast, source, n_samples, rules_version, max_bronze_id)"
        " VALUES (96, 'P-883', 1, 'observed', 0, '1.0.0', 0)",
        "INSERT INTO silver.bus_current_state (bus_id, last_report_ts, data_quality, on_corridor, operational_status, as_of_ts)"
        " VALUES ('B-101', now(), 'bogus', true, 'in_service', now())",
    ]
    for stmt in bad:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(stmt)
        conn.rollback()


def test_init_scripts_are_idempotent(conn) -> None:
    for script in sorted(INIT.glob("*.sql")):
        conn.execute(script.read_text(encoding="utf-8"))
    conn.commit()
    assert conn.execute("SELECT count(*) FROM config.fleet_roster").fetchone()[0] == 7
    assert conn.execute("SELECT count(*) FROM config.enabled_stops").fetchone()[0] == 18
    assert conn.execute("SELECT count(*) FROM config.corridor_settings").fetchone()[0] == 1


def test_adr_0001_has_the_config_addendum() -> None:
    text = (ROOT / "docs" / "adr" / "0001-data-layers-and-ingestion-semantics.md").read_text(encoding="utf-8")
    assert ("Addendum 2026-11-18: a fourth schema, `config`, holds static configuration and "
            "reference tables. It holds no derived data and no secrets.") in text


def test_ops_view_exists_after_init(conn) -> None:
    assert conn.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'ops'").fetchone()
    assert conn.execute("SELECT to_regclass('ops.ingestion_health')").fetchone()[0] is not None


def test_adr_0001_has_the_ops_addendum_after_the_config_one() -> None:
    text = (ROOT / "docs" / "adr" / "0001-data-layers-and-ingestion-semantics.md").read_text(encoding="utf-8")
    ops = ("Addendum 2026-11-21: a fifth schema, `ops`, holds read-only views over bronze for operations "
           "(ingestion freshness). It holds no tables and no secrets.")
    assert ops in text
    assert text.index("a fourth schema, `config`") < text.index(ops)
