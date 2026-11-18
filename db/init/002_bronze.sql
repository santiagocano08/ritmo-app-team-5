-- 002_bronze.sql — Immutable event landing tables.
-- Idempotent: IF NOT EXISTS guards.
-- Rules enforced here:
--   * INSERT-only (enforced in application code + guard test test_bronze_immutable)
--   * Idempotent on (source, event_id): UNIQUE constraint routes duplicates to rejections
--   * Two timestamps: event_ts (from message) and arrival_ts (stamped by ingestion)
--   * rejection reason constrained to the contract enum (rejection.schema.json)

-- bronze.events: authoritative raw event store (E3 in data-model.md)
CREATE TABLE IF NOT EXISTS bronze.events (
    id              BIGSERIAL    PRIMARY KEY,
    source          TEXT         NOT NULL,
    event_id        UUID         NOT NULL,
    schema_version  TEXT         NOT NULL,
    event_type      TEXT         NOT NULL,
    event_ts        TIMESTAMPTZ  NOT NULL,
    arrival_ts      TIMESTAMPTZ  NOT NULL,
    payload         JSONB        NOT NULL,
    ingested_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT bronze_events_unique UNIQUE (source, event_id)
);

-- Hot-path lookup indexes
CREATE INDEX IF NOT EXISTS bronze_events_type_ts_idx
    ON bronze.events (event_type, event_ts);

CREATE INDEX IF NOT EXISTS bronze_events_source_ts_idx
    ON bronze.events (source, event_ts);

-- bronze.rejections: rejected or duplicate events with reason (E4 in data-model.md)
CREATE TABLE IF NOT EXISTS bronze.rejections (
    id               BIGSERIAL    PRIMARY KEY,
    original_message JSONB,
    reason           TEXT         NOT NULL,
    received_ts      TIMESTAMPTZ  NOT NULL,
    CONSTRAINT bronze_rejections_reason_chk CHECK (
        reason IN (
            'missing_required_field',
            'wrong_type',
            'value_out_of_range',
            'unknown_event_type',
            'unsupported_schema_version',
            'undeclared_field',
            'invalid_uuid',
            'invalid_timestamp',
            'duplicate_event'
        )
    )
);

CREATE INDEX IF NOT EXISTS bronze_rejections_reason_ts_idx
    ON bronze.rejections (reason, received_ts);
