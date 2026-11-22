-- S1 silver.position_history: one row per in-range bus_position bronze row (FR-007, R4; 005 US5, FR-052).
-- In range = 0 <= distance_along_m <= route end, route end = max(config.ref_stops.distance_along_m).
-- Parameters: %(as_of_ts)s, %(max_bronze_id)s. Reads bronze only.
INSERT INTO silver.position_history (bronze_id, bus_id, trip_id, event_ts, distance_along_m)
SELECT e.id,
       e.payload->>'bus_id',
       e.payload->>'trip_id',
       e.event_ts,
       (e.payload->>'distance_along_m')::numeric
FROM bronze.events e
WHERE e.event_type = 'bus_position'
  AND e.source <> 'backend'
  AND e.id <= %(max_bronze_id)s
  AND e.event_ts <= %(as_of_ts)s
  AND (e.payload->>'distance_along_m')::numeric BETWEEN 0
      AND (SELECT max(distance_along_m) FROM config.ref_stops)
