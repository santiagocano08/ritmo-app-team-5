-- S4 silver.stop_visits: a row only when both arrival and departure exist (FR-012, R7).
-- Counts come from the stop_departure payload. Parameters: %(as_of_ts)s, %(max_bronze_id)s.
WITH reports AS (
    SELECT e.id, e.event_ts, e.event_type,
           e.payload->>'bus_id' AS bus_id,
           e.payload->>'trip_id' AS trip_id,
           e.payload->>'stop_id' AS stop_id,
           e.payload
    FROM bronze.events e
    WHERE e.event_type IN ('stop_arrival', 'stop_departure')
      AND e.source <> 'backend'
      AND e.id <= %(max_bronze_id)s
      AND e.event_ts <= %(as_of_ts)s
),
arrivals AS (
    SELECT DISTINCT ON (bus_id, trip_id, stop_id) bus_id, trip_id, stop_id, event_ts
    FROM reports WHERE event_type = 'stop_arrival'
    ORDER BY bus_id, trip_id, stop_id, event_ts, id
)
INSERT INTO silver.stop_visits
    (bus_id, trip_id, stop_id, arrival_ts, departure_ts, dwell_s, boarded, alighted, rejected)
SELECT DISTINCT ON (a.bus_id, a.trip_id, a.stop_id)
       a.bus_id, a.trip_id, a.stop_id, a.event_ts, d.event_ts,
       extract(epoch FROM d.event_ts - a.event_ts),
       (d.payload->>'boarded')::int, (d.payload->>'alighted')::int, (d.payload->>'rejected')::int
FROM arrivals a
JOIN reports d
  ON d.event_type = 'stop_departure'
 AND d.bus_id = a.bus_id AND d.trip_id = a.trip_id AND d.stop_id = a.stop_id
 AND d.event_ts >= a.event_ts
ORDER BY a.bus_id, a.trip_id, a.stop_id, d.event_ts, d.id
