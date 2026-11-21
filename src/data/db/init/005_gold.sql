-- 005_gold.sql — gold tables (feature 002, data-model G1–G6).
-- Every table carries rules_version and max_bronze_id (FR-017, SC-008).
-- gold.snapshots and the per-snapshot tables are append-only; m1/m2 baselines are replaced
-- each cycle. Idempotent: IF NOT EXISTS.

-- G1
CREATE TABLE IF NOT EXISTS gold.snapshots (
    snapshot_id    UUID        PRIMARY KEY,
    as_of_ts       TIMESTAMPTZ NOT NULL,
    rules_version  TEXT        NOT NULL,
    max_bronze_id  BIGINT      NOT NULL,
    CONSTRAINT gold_snapshots_key UNIQUE (as_of_ts, rules_version, max_bronze_id)
);

-- Commit log of snapshots (operational, not gold content): the wall-clock time each snapshot row
-- was written, inside its cycle transaction, so a rolled-back cycle leaves no row. Read by the
-- refresh healthcheck (freshness). Kept outside gold.snapshots so the gold content stays
-- deterministic for identical inputs (SC-005). No FK: it is a log, and it survives rebuilds.
CREATE TABLE IF NOT EXISTS gold.snapshot_commits (
    snapshot_id   UUID        PRIMARY KEY,
    committed_at  TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);
CREATE INDEX IF NOT EXISTS gold_snapshot_commits_ts_idx ON gold.snapshot_commits (committed_at);

CREATE OR REPLACE FUNCTION gold.log_snapshot_commit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO gold.snapshot_commits (snapshot_id, committed_at)
    VALUES (NEW.snapshot_id, clock_timestamp())
    ON CONFLICT (snapshot_id) DO UPDATE SET committed_at = EXCLUDED.committed_at;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER gold_snapshots_log_commit
    AFTER INSERT ON gold.snapshots
    FOR EACH ROW EXECUTE FUNCTION gold.log_snapshot_commit();

-- G2: read objects stored exactly as their JSON Schema defines them.
CREATE TABLE IF NOT EXISTS gold.source_status (
    snapshot_id    UUID   PRIMARY KEY REFERENCES gold.snapshots (snapshot_id),
    status         TEXT   NOT NULL,
    doc            JSONB  NOT NULL,
    rules_version  TEXT   NOT NULL,
    max_bronze_id  BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS gold.corridor_now (
    snapshot_id    UUID   PRIMARY KEY REFERENCES gold.snapshots (snapshot_id),
    doc            JSONB  NOT NULL,
    rules_version  TEXT   NOT NULL,
    max_bronze_id  BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS gold.decision_inputs (
    snapshot_id    UUID   PRIMARY KEY REFERENCES gold.snapshots (snapshot_id),
    doc            JSONB  NOT NULL,
    rules_version  TEXT   NOT NULL,
    max_bronze_id  BIGINT NOT NULL
);

-- G4
CREATE TABLE IF NOT EXISTS gold.service_metric (
    snapshot_id      UUID    PRIMARY KEY REFERENCES gold.snapshots (snapshot_id),
    n_headways       INT     NOT NULL CHECK (n_headways >= 0),
    mean_wait_s      NUMERIC,
    scheduled_wait_s NUMERIC,
    ewt_s            NUMERIC,
    computable       BOOLEAN NOT NULL,
    rules_version    TEXT    NOT NULL,
    max_bronze_id    BIGINT  NOT NULL
);

-- G5: 17 segments x 24 hour bands, replaced each cycle.
CREATE TABLE IF NOT EXISTS gold.m1_baseline (
    segment_id        SMALLINT NOT NULL CHECK (segment_id BETWEEN 1 AND 17),
    hour_band         SMALLINT NOT NULL CHECK (hour_band BETWEEN 0 AND 23),
    forecast_travel_s NUMERIC  NOT NULL CHECK (forecast_travel_s >= 0),
    source            TEXT     NOT NULL CHECK (source IN ('observed', 'reference')),
    n_samples         INT      NOT NULL CHECK (n_samples >= 0),
    rules_version     TEXT     NOT NULL,
    max_bronze_id     BIGINT   NOT NULL,
    PRIMARY KEY (segment_id, hour_band)
);

-- G6: 96 fifteen-minute bands at the M2 stop, replaced each cycle.
CREATE TABLE IF NOT EXISTS gold.m2_baseline (
    band              SMALLINT PRIMARY KEY CHECK (band BETWEEN 0 AND 95),
    stop_id           TEXT     NOT NULL,
    arrivals_forecast INT      NOT NULL CHECK (arrivals_forecast >= 0),
    source            TEXT     NOT NULL CHECK (source IN ('observed', 'reference')),
    n_samples         INT      NOT NULL CHECK (n_samples >= 0),
    rules_version     TEXT     NOT NULL,
    max_bronze_id     BIGINT   NOT NULL
);
