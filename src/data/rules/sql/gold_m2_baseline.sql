-- G6 gold.m2_baseline: 96 local 15-minute bands at the M2 stop (FR-030, FR-031, R12, R13).
-- A sample is a (local date, band) pair whose band has ended (band_end <= as_of_ts) and holds at
-- least one non-backend bus_position (the simulator was running). Its value is the count of
-- rider_arrival events at the M2 stop in that band (possibly 0). Observed = median of the samples,
-- rounded half away from zero (percentile_cont is cast to numeric BEFORE round: round(double
-- precision) would round half to even). Fallback = round(daily_riders_dir1 * shape(hour) / 4) on numeric.
-- Local time = UTC - 5 h (same fixed offset as src/data/rules/timebands.py).
-- Run after the silver rebuild; the caller deletes the table first.
-- Parameters: %(as_of_ts)s, %(max_bronze_id)s, %(rules_version)s.
INSERT INTO gold.m2_baseline
    (band, stop_id, arrivals_forecast, source, n_samples, rules_version, max_bronze_id)
WITH cfg AS (
    SELECT m2_stop_id, min_sample_count FROM config.corridor_settings
),
running AS (
    SELECT DISTINCT
           ((e.event_ts AT TIME ZONE 'UTC') - interval '5 hours')::date AS local_date,
           (extract(hour FROM (e.event_ts AT TIME ZONE 'UTC') - interval '5 hours')::int * 4
            + extract(minute FROM (e.event_ts AT TIME ZONE 'UTC') - interval '5 hours')::int / 15) AS band
    FROM bronze.events e
    WHERE e.event_type = 'bus_position'
      AND e.source <> 'backend'
      AND e.id <= %(max_bronze_id)s
      AND e.event_ts <= %(as_of_ts)s
),
ended AS (
    SELECT r.local_date, r.band
    FROM running r
    WHERE ((r.local_date::timestamp + (r.band + 1) * interval '15 minutes' + interval '5 hours')
           AT TIME ZONE 'UTC') <= %(as_of_ts)s
),
riders AS (
    SELECT ((e.event_ts AT TIME ZONE 'UTC') - interval '5 hours')::date AS local_date,
           (extract(hour FROM (e.event_ts AT TIME ZONE 'UTC') - interval '5 hours')::int * 4
            + extract(minute FROM (e.event_ts AT TIME ZONE 'UTC') - interval '5 hours')::int / 15) AS band,
           count(*) AS n
    FROM bronze.events e, cfg
    WHERE e.event_type = 'rider_arrival'
      AND e.payload->>'stop_id' = cfg.m2_stop_id
      AND e.id <= %(max_bronze_id)s
      AND e.event_ts <= %(as_of_ts)s
    GROUP BY 1, 2
),
samples AS (
    SELECT n.band, coalesce(r.n, 0) AS n
    FROM ended n
    LEFT JOIN riders r ON r.local_date = n.local_date AND r.band = n.band
),
observed AS (
    SELECT band, count(*) AS n_samples,
           (percentile_cont(0.5) WITHIN GROUP (ORDER BY n))::numeric AS median_n
    FROM samples
    GROUP BY band
)
SELECT b.band::smallint,
       cfg.m2_stop_id,
       CASE WHEN coalesce(o.n_samples, 0) >= cfg.min_sample_count
            THEN round(o.median_n)::int
            ELSE round(v.daily_riders_dir1 * s.metro_line_a_shape / 4)::int END,
       CASE WHEN coalesce(o.n_samples, 0) >= cfg.min_sample_count THEN 'observed' ELSE 'reference' END,
       coalesce(o.n_samples, 0)::int,
       %(rules_version)s,
       %(max_bronze_id)s
FROM generate_series(0, 95) AS b(band)
CROSS JOIN cfg
CROSS JOIN (SELECT daily_riders_dir1 FROM config.ref_demand_volume LIMIT 1) v
JOIN config.ref_demand_shape s ON s.hour = b.band / 4
LEFT JOIN observed o ON o.band = b.band
ORDER BY b.band
