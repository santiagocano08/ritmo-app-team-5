-- 003_config.sql — static configuration and reference tables (feature 002, research R11).
-- A fourth schema, `config`, holds settings and reference data only: no derived data, no
-- secrets (ADR-0001 addendum). Idempotent: IF NOT EXISTS + ON CONFLICT DO NOTHING seeds.
-- Reference tables (ref_*) are created empty here and loaded from data/reference/*.csv by
-- src/data/pipeline/reference.py.

CREATE SCHEMA IF NOT EXISTS config;

-- C1: one row. Values are provisional and owned by the backend/decision-engine owner.
CREATE TABLE IF NOT EXISTS config.corridor_settings (
    corridor_id               TEXT     PRIMARY KEY,
    direction                 SMALLINT NOT NULL CHECK (direction = 1),
    headway_planned_s         NUMERIC  NOT NULL CHECK (headway_planned_s > 0),
    drivers_free              INT      NOT NULL CHECK (drivers_free >= 0),
    hold_penalty_s            NUMERIC  NOT NULL CHECK (hold_penalty_s >= 0),
    early_departure_penalty_s NUMERIC  NOT NULL CHECK (early_departure_penalty_s >= 0),
    min_sample_count          INT      NOT NULL CHECK (min_sample_count >= 1),
    m2_stop_id                TEXT     NOT NULL
);

INSERT INTO config.corridor_settings
    (corridor_id, direction, headway_planned_s, drivers_free, hold_penalty_s,
     early_departure_penalty_s, min_sample_count, m2_stop_id)
VALUES ('C6-008', 1, 420, 4, 0, 0, 5, 'P-883')
ON CONFLICT (corridor_id) DO NOTHING;

-- C2
CREATE TABLE IF NOT EXISTS config.fleet_roster (
    bus_id TEXT PRIMARY KEY,
    role   TEXT NOT NULL CHECK (role IN ('in_service', 'reserve'))
);

-- Issue #42 (contract v0.5): 7 in service, 4 in reserve. Planned headway 420 s and 4 free drivers above keep the
-- terminal cycle near the old 5 x 600 s while more buses run at once.
INSERT INTO config.fleet_roster (bus_id, role) VALUES
    ('B-101', 'in_service'), ('B-102', 'in_service'), ('B-103', 'in_service'),
    ('B-104', 'in_service'), ('B-105', 'in_service'), ('B-106', 'in_service'),
    ('B-107', 'in_service'),
    ('B-108', 'reserve'),    ('B-109', 'reserve'),    ('B-110', 'reserve'),
    ('B-111', 'reserve')
ON CONFLICT (bus_id) DO UPDATE SET role = EXCLUDED.role;

-- C3: stops where regulation actions are permitted (all 18 in turn 1).
CREATE TABLE IF NOT EXISTS config.enabled_stops (
    stop_id TEXT PRIMARY KEY
);

INSERT INTO config.enabled_stops (stop_id)
SELECT 'P-' || n FROM generate_series(883, 900) AS n
ON CONFLICT (stop_id) DO NOTHING;

-- C4: reference tables, loaded from data/reference/*.csv (DELETE + INSERT in one transaction).
CREATE TABLE IF NOT EXISTS config.ref_stops (
    stop_seq         SMALLINT PRIMARY KEY CHECK (stop_seq >= 1),
    stop_id          TEXT     NOT NULL UNIQUE,
    distance_along_m NUMERIC  NOT NULL CHECK (distance_along_m >= 0),
    segment_id       SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS config.ref_segments (
    segment_id     SMALLINT PRIMARY KEY CHECK (segment_id >= 1),
    length_m       NUMERIC  NOT NULL CHECK (length_m > 0),
    free_flow_kmh  NUMERIC  NOT NULL CHECK (free_flow_kmh > 0)
);

CREATE TABLE IF NOT EXISTS config.ref_congestion_factor (
    hour              SMALLINT PRIMARY KEY CHECK (hour BETWEEN 0 AND 23),
    congestion_factor NUMERIC  NOT NULL CHECK (congestion_factor > 0)
);

CREATE TABLE IF NOT EXISTS config.ref_demand_shape (
    hour               SMALLINT PRIMARY KEY CHECK (hour BETWEEN 0 AND 23),
    metro_line_a_shape NUMERIC  NOT NULL CHECK (metro_line_a_shape >= 0)
);

CREATE TABLE IF NOT EXISTS config.ref_demand_volume (
    daily_riders_dir1 NUMERIC NOT NULL CHECK (daily_riders_dir1 >= 0)
);
