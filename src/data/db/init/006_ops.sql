-- 006_ops.sql — operational read-only views (feature 003, data-model E1).
-- Schema `ops` holds views only: no table, no write. Idempotent (IF NOT EXISTS / OR REPLACE).
-- Applying it to an existing volume: see the runbook (R14).
CREATE SCHEMA IF NOT EXISTS ops;

-- One row, always. Time comes from the database clock, evaluated once per read.
-- NULL means "not computable": empty bronze (age) or an empty denominator (rate).
-- Duplicates (reason duplicate_event) are reported on their own and never count as rejections.
CREATE OR REPLACE VIEW ops.ingestion_health AS
WITH clock AS (
    SELECT clock_timestamp() AS observed_at
),
last_event AS (
    SELECT arrival_ts FROM bronze.events ORDER BY id DESC LIMIT 1
),
ev AS (
    SELECT count(*) AS n
    FROM bronze.events e, clock c
    WHERE e.arrival_ts > c.observed_at - interval '60 seconds'
),
rej AS (
    SELECT count(*) FILTER (WHERE r.reason <> 'duplicate_event') AS rejections,
           count(*) FILTER (WHERE r.reason =  'duplicate_event') AS duplicates
    FROM bronze.rejections r, clock c
    WHERE r.received_ts > c.observed_at - interval '60 seconds'
)
SELECT
    c.observed_at                                                         AS observed_at,
    (SELECT extract(epoch FROM c.observed_at - l.arrival_ts)::double precision
       FROM last_event l)                                                 AS last_insert_age_s,
    ev.n::bigint                                                          AS events_60s,
    rej.rejections::bigint                                                AS rejections_60s,
    rej.duplicates::bigint                                                AS duplicates_60s,
    CASE WHEN ev.n + rej.rejections = 0 THEN NULL
         ELSE rej.rejections::numeric / (ev.n + rej.rejections) END       AS rejection_rate_60s
FROM clock c, ev, rej;
