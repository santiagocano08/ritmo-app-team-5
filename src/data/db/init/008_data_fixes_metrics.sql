-- 008_data_fixes_metrics.sql — feature 005 (data fixes and boarding-probability metrics), Phase 2: stop-based EWT.
-- Owner: data layer (CODEOWNERS). Idempotent: ADD COLUMN IF NOT EXISTS, CREATE ... IF NOT EXISTS.
-- Bronze is not touched. Every new gold row carries rules_version and max_bronze_id (ADR-0001).
-- An existing database volume does not re-run init scripts: apply this file by hand (quickstart.md).

-- E2: minimum number of stop headways for the corridor EWT to be computable (same default as min_sample_count).
ALTER TABLE config.corridor_settings
    ADD COLUMN IF NOT EXISTS min_stop_headways INT NOT NULL DEFAULT 5;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'config.corridor_settings'::regclass
                     AND conname = 'corridor_settings_min_stop_headways_check') THEN
        ALTER TABLE config.corridor_settings
            ADD CONSTRAINT corridor_settings_min_stop_headways_check CHECK (min_stop_headways >= 1);
    END IF;
END
$$;

-- E3: silver.stop_visits flags a departure reported after a gap of more than ESTIMATED_AFTER_S (rebuilt every cycle).
ALTER TABLE silver.stop_visits
    ADD COLUMN IF NOT EXISTS estimated_at_departure BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS silver_stop_visits_stop_dep_idx ON silver.stop_visits (stop_id, departure_ts);

-- E5: trailing 15-minute sums per stop, one row per stop and snapshot (append-only with the snapshot).
CREATE TABLE IF NOT EXISTS gold.service_metric_stop (
    snapshot_id       UUID    NOT NULL REFERENCES gold.snapshots (snapshot_id),
    stop_id           TEXT    NOT NULL,
    n_headways        INT     NOT NULL CHECK (n_headways >= 0),
    sum_headway_s     NUMERIC NOT NULL CHECK (sum_headway_s >= 0),
    sum_headway_sq_s  NUMERIC NOT NULL CHECK (sum_headway_sq_s >= 0),
    sum_planned_s     NUMERIC NOT NULL CHECK (sum_planned_s >= 0),
    sum_planned_sq_s  NUMERIC NOT NULL CHECK (sum_planned_sq_s >= 0),
    n_excluded        INT     NOT NULL CHECK (n_excluded >= 0),
    computable        BOOLEAN NOT NULL,
    rules_version     TEXT    NOT NULL,
    max_bronze_id     BIGINT  NOT NULL,
    PRIMARY KEY (snapshot_id, stop_id)
);

-- E6: additive sums per closed clock-aligned 15-minute local band and stop; replaced every cycle (sparse).
CREATE TABLE IF NOT EXISTS gold.stop_ewt_band (
    local_date        DATE     NOT NULL,
    band              SMALLINT NOT NULL CHECK (band BETWEEN 0 AND 95),
    stop_id           TEXT     NOT NULL,
    n_headways        INT      NOT NULL CHECK (n_headways >= 0),
    sum_headway_s     NUMERIC  NOT NULL CHECK (sum_headway_s >= 0),
    sum_headway_sq_s  NUMERIC  NOT NULL CHECK (sum_headway_sq_s >= 0),
    sum_planned_s     NUMERIC  NOT NULL CHECK (sum_planned_s >= 0),
    sum_planned_sq_s  NUMERIC  NOT NULL CHECK (sum_planned_sq_s >= 0),
    n_excluded        INT      NOT NULL CHECK (n_excluded >= 0),
    rules_version     TEXT     NOT NULL,
    max_bronze_id     BIGINT   NOT NULL,
    PRIMARY KEY (local_date, band, stop_id)
);

-- Phase 3 (US4): P(board <= t) counts per stop and band of the rider's arrival (simple method, FR-040 to FR-045).
-- E7: additive counts; the open band is included (its counts can still rise); replaced every cycle (sparse).
CREATE TABLE IF NOT EXISTS gold.stop_boarding_band (
    local_date     DATE     NOT NULL,
    band           SMALLINT NOT NULL CHECK (band BETWEEN 0 AND 95),
    stop_id        TEXT     NOT NULL,
    n_riders       INT      NOT NULL CHECK (n_riders >= 0),
    n_board_le_5   INT      NOT NULL CHECK (n_board_le_5 >= 0),
    n_board_le_10  INT      NOT NULL CHECK (n_board_le_10 >= 0),
    n_board_le_15  INT      NOT NULL CHECK (n_board_le_15 >= 0),
    rules_version  TEXT     NOT NULL,
    max_bronze_id  BIGINT   NOT NULL,
    PRIMARY KEY (local_date, band, stop_id),
    CHECK (n_board_le_5 <= n_board_le_10 AND n_board_le_10 <= n_board_le_15 AND n_board_le_15 <= n_riders)
);

-- E8: the band's UTC instants and its state against the newest snapshot. `closed`: the band has ended.
-- `final`: every rider of the band has had the 15 minutes the largest threshold needs. No snapshot: both false.
-- Local time = UTC - 5 h (same fixed offset as src/data/rules/timebands.py).
CREATE OR REPLACE VIEW gold.stop_boarding_band_v AS
SELECT x.local_date, x.band, x.stop_id, x.n_riders, x.n_board_le_5, x.n_board_le_10, x.n_board_le_15,
       x.rules_version, x.max_bronze_id, x.band_start_ts, x.band_end_ts,
       coalesce(x.band_end_ts <= n.as_of_ts, false) AS closed,
       coalesce(x.band_end_ts + interval '15 minutes' <= n.as_of_ts, false) AS final
FROM (
    SELECT b.*,
           (b.local_date::timestamp + b.band * interval '15 minutes' + interval '5 hours') AT TIME ZONE 'UTC'
               AS band_start_ts,
           (b.local_date::timestamp + (b.band + 1) * interval '15 minutes' + interval '5 hours') AT TIME ZONE 'UTC'
               AS band_end_ts
    FROM gold.stop_boarding_band b
) x
CROSS JOIN (SELECT max(as_of_ts) AS as_of_ts FROM gold.snapshots) n;
