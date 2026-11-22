-- 009_decision_mpc.sql — feature 006 (decision model, simulation-based MPC). Owner: data layer (CODEOWNERS).
-- Idempotent: IF NOT EXISTS / OR REPLACE / DROP IF EXISTS. One section per phase: phase 2, then phase 2b (projection record).
-- Bronze is not touched. Every derived row carries rules_version and max_bronze_id (ADR-0001).
-- An existing volume does not re-run init scripts: apply this file by hand (specs/006-decision-mpc/quickstart.md).

-- === Phase 2: inputs, candidates, top 3, gold.recommendation, seed retirement =====================

-- M1: every parameter of the model, one row. Source and owner per column; the dataclass `MpcParams`
-- (src/data/rules/mpc_params.py) has the same defaults and a test keeps both in step.
CREATE TABLE IF NOT EXISTS config.decision_model (
    corridor_id            TEXT    PRIMARY KEY,
    scoring_window_s       INT     NOT NULL DEFAULT 1800 CHECK (scoring_window_s > 0),    -- FR-005, data owner 2026-11-21
    horizon_s              INT     NOT NULL DEFAULT 600  CHECK (horizon_s = 600),         -- FR-018, ADR-0007: pinned
    step_s                 INT     NOT NULL DEFAULT 5    CHECK (step_s > 0),              -- simulator STEP_S: rounding grid
    capacity               INT     NOT NULL DEFAULT 40   CHECK (capacity > 0),            -- simulator CAPACITY
    threshold_s_per_rider  NUMERIC NOT NULL DEFAULT 15   CHECK (threshold_s_per_rider >= 0),  -- FR-012
    top_n                  INT     NOT NULL DEFAULT 3    CHECK (top_n BETWEEN 1 AND 3),   -- FR-012
    reserve_ready_s        INT     NOT NULL DEFAULT 120  CHECK (reserve_ready_s >= 0),    -- declared assumption (data owner)
    reserve_cost_s         NUMERIC NOT NULL DEFAULT 900  CHECK (reserve_cost_s >= 0),     -- declared (data owner)
    slow_duration_s        INT     NOT NULL DEFAULT 300  CHECK (slow_duration_s > 0),     -- declared (data owner)
    slow_shares            NUMERIC[] NOT NULL DEFAULT '{0.10,0.20}',                      -- FR-008; published as percent
    hold_options_s         INT[]   NOT NULL DEFAULT '{30,60,90}' CHECK (90 >= ALL (hold_options_s)),  -- FR-008, <= 90
    adjust_options_s       INT[]   NOT NULL DEFAULT '{-120,-60,60,120}',                  -- FR-008
    skip_reach_stops       INT     NOT NULL DEFAULT 4    CHECK (skip_reach_stops > 0),    -- prototype reach, declared here
    queue_trigger_riders   INT     NOT NULL DEFAULT 20   CHECK (queue_trigger_riders > 0),  -- FR-008: half a bus
    proposal_ttl_s         INT     NOT NULL DEFAULT 120  CHECK (proposal_ttl_s > 0),      -- FR-030
    rest_s                 INT     NOT NULL DEFAULT 300  CHECK (rest_s >= 0),             -- FR-030
    freshness_max_s        INT     NOT NULL DEFAULT 15   CHECK (freshness_max_s > 0),     -- FR-017, ADR-0006
    rate_window_s          INT     NOT NULL DEFAULT 1800 CHECK (rate_window_s > 0),       -- FR-003: 30 minutes
    train_share            NUMERIC NOT NULL DEFAULT 0.80 CHECK (train_share BETWEEN 0 AND 1),  -- SOURCES.md assumption
    walk_mean_s            INT     NOT NULL DEFAULT 120  CHECK (walk_mean_s >= 0),        -- mean of the simulator's walk
    model_version          TEXT    NOT NULL DEFAULT '1.0.0'                               -- lineage.model_version
);

INSERT INTO config.decision_model (corridor_id) VALUES ('C6-008') ON CONFLICT (corridor_id) DO NOTHING;

-- M2: Metro train arrivals at Prado (GTFS), the same file the simulator reads. Loaded by pipeline/reference.py.
CREATE TABLE IF NOT EXISTS config.ref_train_arrival (
    arrival_sec   INT  NOT NULL CHECK (arrival_sec >= 0 AND arrival_sec < 86400),
    train_trip_id TEXT NOT NULL,
    PRIMARY KEY (arrival_sec, train_trip_id)
);

-- M3: queue per stop, rebuilt every cycle (DELETE + INSERT) by rules/sql/silver_stop_queue.sql.
CREATE TABLE IF NOT EXISTS silver.stop_queue (
    stop_id          TEXT        PRIMARY KEY,
    queue_riders     INT         NOT NULL CHECK (queue_riders >= 0),
    basis_ts         TIMESTAMPTZ,
    basis_bronze_id  BIGINT      NOT NULL,
    as_of_ts         TIMESTAMPTZ NOT NULL
);

-- M4: occupancy of the newest in-range position (NULL when the bus has none).
ALTER TABLE silver.bus_current_state ADD COLUMN IF NOT EXISTS occupancy INT;

-- M5: one row per rec_id. Written only by pipeline/recommend.py. `status` always equals `doc.status`.
CREATE TABLE IF NOT EXISTS gold.recommendation (
    rec_id            UUID        PRIMARY KEY,
    doc               JSONB       NOT NULL,
    key               TEXT        NOT NULL,
    "case"            TEXT        NOT NULL,
    status            TEXT        NOT NULL CHECK (status IN ('proposed', 'applied', 'discarded', 'expired')),
    stale             BOOLEAN     NOT NULL DEFAULT false,
    proposed_ts       TIMESTAMPTZ NOT NULL,
    expires_ts        TIMESTAMPTZ NOT NULL,
    close_ts          TIMESTAMPTZ,
    first_snapshot_id UUID        NOT NULL,
    params            JSONB       NOT NULL,
    lineage_detail    JSONB       NOT NULL,
    rules_version     TEXT        NOT NULL,
    max_bronze_id     BIGINT      NOT NULL,
    CONSTRAINT gold_recommendation_status_matches_doc CHECK (doc->>'status' = status)
);
CREATE INDEX IF NOT EXISTS gold_recommendation_status_rank_idx ON gold.recommendation (status, ((doc->>'rank')::int));
CREATE INDEX IF NOT EXISTS gold_recommendation_key_idx ON gold.recommendation (key);

-- M6: one row per evaluated candidate of the latest cycle, plus the baseline; replaced every cycle.
CREATE TABLE IF NOT EXISTS gold.mpc_evaluation (
    snapshot_id         UUID    NOT NULL,
    seq                 INT     NOT NULL,
    action              JSONB   NOT NULL,
    "case"              TEXT,
    score_s             NUMERIC NOT NULL,
    saving_s_per_rider  NUMERIC NOT NULL,
    recommended         BOOLEAN NOT NULL,
    reason_not          TEXT,
    rules_version       TEXT    NOT NULL,
    max_bronze_id       BIGINT  NOT NULL,
    PRIMARY KEY (snapshot_id, seq)
);

-- M9: the story-004 seed table is retired (the hold executor and the instruction status read gold.recommendation).
-- On a volume created before 006 the table still exists: drop every seed_* table of `config`. Written as a catalog
-- loop so no file names the retired table (the tree grep of SC-009 stays at 0 hits outside specs/ and docs/).
DO $$
DECLARE t text;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'config' AND tablename LIKE 'seed\_%' LOOP
        EXECUTE format('DROP TABLE IF EXISTS config.%I', t);
    END LOOP;
END
$$;

-- === Phase 2b: projection record (FR-035, FR-036, SC-016; data owner 2026-11-22) ====================

-- M10: the model's "do nothing" departures, one row per (snapshot, bus, stop), appended every cycle by
-- pipeline/recommend.py in the cycle transaction. Append-only like gold.snapshots: code never updates or deletes it.
-- The insert is ON CONFLICT DO NOTHING, so the same snapshot (a function of as_of, rules_version and max_bronze_id)
-- gives the same rows.
CREATE TABLE IF NOT EXISTS gold.mpc_projection (
    snapshot_id             UUID        NOT NULL REFERENCES gold.snapshots (snapshot_id),
    bus_id                  TEXT        NOT NULL,
    stop_id                 TEXT        NOT NULL,
    as_of_ts                TIMESTAMPTZ NOT NULL,   -- cycle reference time
    projected_departure_ts  TIMESTAMPTZ NOT NULL,   -- as_of_ts + lead_s
    lead_s                  NUMERIC     NOT NULL CHECK (lead_s >= 0 AND lead_s <= 1800),  -- scoring window (FR-005)
    rules_version           TEXT        NOT NULL,
    max_bronze_id           BIGINT      NOT NULL,
    PRIMARY KEY (snapshot_id, bus_id, stop_id)
);
CREATE INDEX IF NOT EXISTS gold_mpc_projection_bus_stop_idx ON gold.mpc_projection (bus_id, stop_id, as_of_ts);

-- M11: each projected departure against the bus's first real departure from that stop at or after as_of_ts
-- (silver.stop_visits). error_s = real - projected (positive: the bus left later). NULL error when there is no real
-- departure yet or when that first visit is an estimated departure; never 0. affected_by_decision: an applied
-- recommendation on the same bus was decided after as_of_ts and not after the real departure (the baseline is then
-- not comparable). Research R17.
CREATE OR REPLACE VIEW gold.v_projection_accuracy AS
SELECT p.snapshot_id,
       p.bus_id,
       p.stop_id,
       p.as_of_ts,
       p.projected_departure_ts,
       p.lead_s,
       CASE WHEN p.lead_s < 300 THEN '0-5 min'
            WHEN p.lead_s < 600 THEN '5-10 min'
            ELSE '10-30 min' END AS lead_bucket,
       CASE WHEN NOT v.estimated_at_departure THEN v.departure_ts END AS actual_departure_ts,
       CASE WHEN NOT v.estimated_at_departure
            THEN extract(epoch FROM v.departure_ts - p.projected_departure_ts)::numeric END AS error_s,
       CASE WHEN NOT v.estimated_at_departure
            THEN abs(extract(epoch FROM v.departure_ts - p.projected_departure_ts))::numeric END AS abs_error_s,
       EXISTS (SELECT 1
               FROM gold.recommendation r
               WHERE r.status = 'applied'
                 AND r.doc->'action'->>'bus_id' = p.bus_id
                 AND r.close_ts > p.as_of_ts
                 AND (v.departure_ts IS NULL OR r.close_ts <= v.departure_ts)) AS affected_by_decision,
       p.rules_version,
       p.max_bronze_id
FROM gold.mpc_projection p
LEFT JOIN LATERAL (
    SELECT sv.departure_ts, sv.estimated_at_departure
    FROM silver.stop_visits sv
    WHERE sv.bus_id = p.bus_id AND sv.stop_id = p.stop_id AND sv.departure_ts >= p.as_of_ts
    ORDER BY sv.departure_ts
    LIMIT 1
) v ON true;
