-- S6 silver.stop_queue (006 FR-004, data-model M3, research R3). Run last in the silver build order.
-- queue(stop) = `rejected` of the newest stop_arrival at the stop (any bus) + rider_arrival events at the stop
-- after that arrival. Exact for the simulator: riders are released before buses act in a step and `rejected` is
-- the queue left after boarding, so a rider stamped after the arrival second is still queued and one stamped at
-- or before it is already counted. Both look-backs stop at config.decision_model.rate_window_s (30 minutes), so
-- a stop with no arrival in the window counts the riders of the window and has no basis_ts.
-- basis_bronze_id is the largest bronze id used (traceability). Bounded by id <= M and event_ts <= as_of.
-- Parameters: %(as_of_ts)s, %(max_bronze_id)s.
WITH cfg AS (
    SELECT %(as_of_ts)s::timestamptz - rate_window_s * interval '1 second' AS lo
    FROM config.decision_model
    ORDER BY corridor_id
    LIMIT 1
),
arrivals AS (
    SELECT DISTINCT ON (e.payload->>'stop_id')
           e.payload->>'stop_id' AS stop_id, e.event_ts, e.id,
           (e.payload->>'rejected')::int AS rejected
    FROM bronze.events e, cfg
    WHERE e.event_type = 'stop_arrival'
      AND e.source <> 'backend'
      AND e.id <= %(max_bronze_id)s
      AND e.event_ts <= %(as_of_ts)s
      AND e.event_ts > cfg.lo
    ORDER BY e.payload->>'stop_id', e.event_ts DESC, e.id DESC
),
riders AS (
    SELECT s.stop_id, count(r.id) AS n, max(r.id) AS max_id
    FROM config.ref_stops s
    LEFT JOIN arrivals a ON a.stop_id = s.stop_id
    LEFT JOIN bronze.events r
           ON r.event_type = 'rider_arrival'
          AND r.source <> 'backend'
          AND r.payload->>'stop_id' = s.stop_id
          AND r.id <= %(max_bronze_id)s
          AND r.event_ts <= %(as_of_ts)s
          AND r.event_ts > coalesce(a.event_ts, (SELECT lo FROM cfg))
    GROUP BY s.stop_id
)
INSERT INTO silver.stop_queue (stop_id, queue_riders, basis_ts, basis_bronze_id, as_of_ts)
SELECT s.stop_id,
       coalesce(a.rejected, 0) + coalesce(r.n, 0),
       a.event_ts,
       greatest(coalesce(a.id, 0), coalesce(r.max_id, 0)),
       %(as_of_ts)s
FROM config.ref_stops s
LEFT JOIN arrivals a ON a.stop_id = s.stop_id
LEFT JOIN riders r ON r.stop_id = s.stop_id
ORDER BY s.stop_seq
