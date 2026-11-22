-- Model input (006 FR-003, research R1): buses that are at a stop now, i.e. a stop_arrival with no completed
-- silver.stop_visits row (same arrival choice as silver and as pipeline/holds.py `_OPEN`). The remaining dwell is
-- arrival + dwell(boarded, alighted) - as_of, computed by the caller with the simulator's dwell rule.
-- Read-only on bronze, bounded by id <= M and event_ts in (as_of - lookback, as_of].
-- Parameters: %(as_of_ts)s, %(max_bronze_id)s, %(lookback_s)s.
SELECT a.bus_id, a.stop_id, a.event_ts, a.boarded, a.alighted
FROM (SELECT DISTINCT ON (e.payload->>'bus_id', e.payload->>'trip_id', e.payload->>'stop_id')
             e.payload->>'bus_id' AS bus_id, e.payload->>'trip_id' AS trip_id,
             e.payload->>'stop_id' AS stop_id, e.event_ts,
             (e.payload->>'boarded')::int AS boarded, (e.payload->>'alighted')::int AS alighted
      FROM bronze.events e
      WHERE e.event_type = 'stop_arrival' AND e.source <> 'backend'
        AND e.id <= %(max_bronze_id)s
        AND e.event_ts <= %(as_of_ts)s
        AND e.event_ts > %(as_of_ts)s - %(lookback_s)s::double precision * interval '1 second'
      ORDER BY e.payload->>'bus_id', e.payload->>'trip_id', e.payload->>'stop_id', e.event_ts, e.id) a
WHERE NOT EXISTS (SELECT 1 FROM silver.stop_visits v
                  WHERE v.bus_id = a.bus_id AND v.trip_id = a.trip_id AND v.stop_id = a.stop_id)
ORDER BY a.bus_id, a.event_ts
