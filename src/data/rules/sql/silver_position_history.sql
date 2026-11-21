-- S1 silver.position_history: one row per bus_position bronze row (FR-007, R4).
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
