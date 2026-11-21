-- G5 gold.m1_baseline: 17 segments x 24 local hour bands (FR-026..FR-029, R13).
-- Observed: percentile_cont(0.5) of the eligible traversals (neither flag set) when there are at
-- least config.corridor_settings.min_sample_count of them; otherwise the reference formula
-- length_m / (free_flow_kmh / 3.6) / congestion_factor(hour), unrounded. n_samples is always kept.
-- Run after the silver rebuild. The caller deletes the table first (replaced each cycle).
-- Parameters: %(rules_version)s, %(max_bronze_id)s.
INSERT INTO gold.m1_baseline
    (segment_id, hour_band, forecast_travel_s, source, n_samples, rules_version, max_bronze_id)
WITH grid AS (
    SELECT s.segment_id, h.hour_band, s.length_m, s.free_flow_kmh, c.congestion_factor
    FROM config.ref_segments s
    CROSS JOIN generate_series(0, 23) AS h(hour_band)
    JOIN config.ref_congestion_factor c ON c.hour = h.hour_band
),
observed AS (
    SELECT t.segment_id, t.hour_band,
           count(*) AS n_samples,
           (percentile_cont(0.5) WITHIN GROUP (ORDER BY t.travel_s))::numeric AS median_s
    FROM silver.segment_traversals t
    WHERE NOT t.travelled_while_estimated AND NOT t.broken_down
    GROUP BY t.segment_id, t.hour_band
)
SELECT g.segment_id::smallint, g.hour_band::smallint,
       CASE WHEN coalesce(o.n_samples, 0) >= cfg.min_sample_count
            THEN o.median_s
            ELSE g.length_m / (g.free_flow_kmh / 3.6) / g.congestion_factor END,
       CASE WHEN coalesce(o.n_samples, 0) >= cfg.min_sample_count THEN 'observed' ELSE 'reference' END,
       coalesce(o.n_samples, 0)::int,
       %(rules_version)s,
       %(max_bronze_id)s
FROM grid g
CROSS JOIN config.corridor_settings cfg
LEFT JOIN observed o ON o.segment_id = g.segment_id AND o.hour_band = g.hour_band
ORDER BY g.segment_id, g.hour_band
