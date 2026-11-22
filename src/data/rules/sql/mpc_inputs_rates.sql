-- Model input (006 FR-003, research R1, R13): rider_arrival events per stop in the last `window_s` seconds
-- (the observed rate; the caller falls back to the reference rate below `min_sample_count`).
-- Read-only on bronze, bounded by id <= M and event_ts in (as_of - window, as_of].
-- Parameters: %(as_of_ts)s, %(max_bronze_id)s, %(window_s)s.
SELECT e.payload->>'stop_id' AS stop_id, count(*) AS n
FROM bronze.events e
WHERE e.event_type = 'rider_arrival'
  AND e.source <> 'backend'
  AND e.id <= %(max_bronze_id)s
  AND e.event_ts <= %(as_of_ts)s
  AND e.event_ts > %(as_of_ts)s - %(window_s)s::double precision * interval '1 second'
GROUP BY 1
ORDER BY 1
