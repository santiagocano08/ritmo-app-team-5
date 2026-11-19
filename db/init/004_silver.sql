-- 004_silver.sql — silver tables (feature 002, data-model S1–S5).
-- Derived only from bronze + config. Deleted and rebuilt every cycle (research R2),
-- so no foreign keys to bronze. Idempotent: IF NOT EXISTS.

-- S1: one row per bus_position bronze row (input of the headway rule, FR-020).
CREATE TABLE IF NOT EXISTS silver.position_history (
    bronze_id        BIGINT      PRIMARY KEY,
    bus_id           TEXT        NOT NULL,
    trip_id          TEXT        NOT NULL,
    event_ts         TIMESTAMPTZ NOT NULL,
    distance_along_m NUMERIC     NOT NULL
);
CREATE INDEX IF NOT EXISTS silver_position_history_bus_trip_ts_idx
    ON silver.position_history (bus_id, trip_id, event_ts, bronze_id);

-- S2: incidents, active on [start_ts, end_ts) (FR-015, R7).
CREATE TABLE IF NOT EXISTS silver.incidents (
    inc_id        UUID        PRIMARY KEY,
    incident_type TEXT        NOT NULL,
    target_id     TEXT        NOT NULL,
    start_ts      TIMESTAMPTZ NOT NULL,
    end_ts        TIMESTAMPTZ NOT NULL,
    reported_by   TEXT        NOT NULL,
    source        TEXT        NOT NULL,
    bronze_id     BIGINT      NOT NULL,
    CHECK (end_ts >= start_ts)
);

-- S3: current state per bus (FR-008–FR-011).
CREATE TABLE IF NOT EXISTS silver.bus_current_state (
    bus_id             TEXT        PRIMARY KEY,
    trip_id            TEXT,
    distance_along_m   NUMERIC,
    position_ts        TIMESTAMPTZ,
    position_trip_id   TEXT,
    prev_stop_id       TEXT,
    next_stop_id       TEXT,
    last_report_ts     TIMESTAMPTZ NOT NULL,
    data_quality       TEXT        NOT NULL CHECK (data_quality IN ('live', 'estimated')),
    on_corridor        BOOLEAN     NOT NULL,
    operational_status TEXT        NOT NULL
        CHECK (operational_status IN ('in_service', 'reserve', 'broken_down', 'off_corridor')),
    as_of_ts           TIMESTAMPTZ NOT NULL
);

-- S4: paired arrival and departure at a stop (FR-012).
CREATE TABLE IF NOT EXISTS silver.stop_visits (
    bus_id       TEXT        NOT NULL,
    trip_id      TEXT        NOT NULL,
    stop_id      TEXT        NOT NULL,
    arrival_ts   TIMESTAMPTZ NOT NULL,
    departure_ts TIMESTAMPTZ NOT NULL,
    dwell_s      NUMERIC     NOT NULL,
    boarded      INT         NOT NULL CHECK (boarded >= 0),
    alighted     INT         NOT NULL CHECK (alighted >= 0),
    rejected     INT         NOT NULL CHECK (rejected >= 0),
    PRIMARY KEY (bus_id, trip_id, stop_id)
);

-- S5: segment traversals with exclusion flags (FR-013, FR-014, FR-026).
CREATE TABLE IF NOT EXISTS silver.segment_traversals (
    bus_id                    TEXT        NOT NULL,
    trip_id                   TEXT        NOT NULL,
    segment_id                SMALLINT    NOT NULL CHECK (segment_id BETWEEN 1 AND 17),
    departure_ts              TIMESTAMPTZ NOT NULL,
    arrival_ts                TIMESTAMPTZ NOT NULL,
    travel_s                  NUMERIC     NOT NULL,
    hour_band                 SMALLINT    NOT NULL CHECK (hour_band BETWEEN 0 AND 23),
    travelled_while_estimated BOOLEAN     NOT NULL,
    broken_down               BOOLEAN     NOT NULL,
    PRIMARY KEY (bus_id, trip_id, segment_id)
);
