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
