-- 007_scenarios.sql — objects of feature 004 (scenario injectors, hold loop, effect table).
-- Idempotent: IF NOT EXISTS / OR REPLACE. Three sections, one per phase; an existing volume does not
-- run init scripts again, apply this file by hand (see specs/004-scenario-injectors/research.md R8).

-- === Phase 1: incident gold object (US-12; data-model E6) ===========================================
-- One row per incident per snapshot; `doc` is exactly contracts/read/incident.schema.json v1.0.0.
CREATE TABLE IF NOT EXISTS gold.incident (
    snapshot_id    UUID    NOT NULL REFERENCES gold.snapshots (snapshot_id),
    inc_id         UUID    NOT NULL,
    active         BOOLEAN NOT NULL,
    doc            JSONB   NOT NULL,
    rules_version  TEXT    NOT NULL,
    max_bronze_id  BIGINT  NOT NULL,
    PRIMARY KEY (snapshot_id, inc_id)
);

-- Rows of the newest snapshot of the rules version that is current (the newest snapshot's version).
CREATE OR REPLACE VIEW gold.incident_current AS
SELECT i.snapshot_id, i.inc_id, i.active, i.doc, i.rules_version, i.max_bronze_id
FROM gold.incident i
WHERE i.snapshot_id = (
    SELECT s.snapshot_id
    FROM gold.snapshots s
    WHERE s.rules_version = (SELECT s2.rules_version FROM gold.snapshots s2
                             ORDER BY s2.as_of_ts DESC, s2.max_bronze_id DESC LIMIT 1)
    ORDER BY s.as_of_ts DESC, s.max_bronze_id DESC
    LIMIT 1);

-- === Phase 2: hold loop (US2; data-model E3, E7) ====================================================
-- Seed recommendations: demo and test data, loaded from src/data/seeds/recommendations.json by
-- pipeline/seeds.py (DELETE + INSERT). Removed when the recommendation door exists.
CREATE TABLE IF NOT EXISTS config.seed_recommendation (
    rec_id  UUID  PRIMARY KEY,
    doc     JSONB NOT NULL
);

-- Instruction status per approved hold, rebuilt each cycle from bronze, silver and config (no row while
-- pending). `ts_by_status` has exactly one key, the status itself, with an RFC 3339 UTC time.
CREATE TABLE IF NOT EXISTS gold.instruction_status (
    rec_id            UUID    PRIMARY KEY,
    bus_id            TEXT    NOT NULL,
    stop_id           TEXT    NOT NULL,
    hold_s            NUMERIC NOT NULL,
    observed_dwell_s  NUMERIC,
    status            TEXT    NOT NULL CHECK (status IN ('executed', 'not_executed')),
    ts_by_status      JSONB   NOT NULL,
    rules_version     TEXT    NOT NULL,
    max_bronze_id     BIGINT  NOT NULL,
    CONSTRAINT instruction_status_one_key CHECK (
        COALESCE(jsonb_typeof(ts_by_status -> status) = 'string', false)
        AND ts_by_status = jsonb_build_object(status, ts_by_status -> status))
);
