-- S4 silver.stop_visits: a row only when both arrival and departure exist (FR-012, R7).
-- Counts come from the stop_departure payload. `estimated_at_departure` (005 R4) is true when the bus's previous
-- report (bus_position, stop_arrival or stop_departure, strictly earlier distinct event_ts) is more than
-- `estimated_after_s` before the departure; the departure is itself a report, so the gap before it is what counts.
-- No earlier report: false. Parameters: %(as_of_ts)s, %(max_bronze_id)s, %(estimated_after_s)s.
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
bus_report_times AS (
    SELECT bus_id, event_ts, lag(event_ts) OVER (PARTITION BY bus_id ORDER BY event_ts) AS prev_ts
    FROM (
        SELECT DISTINCT e.payload->>'bus_id' AS bus_id, e.event_ts
        FROM bronze.events e
        WHERE e.event_type IN ('bus_position', 'stop_arrival', 'stop_departure')
          AND e.source <> 'backend'
          AND e.id <= %(max_bronze_id)s
          AND e.event_ts <= %(as_of_ts)s
    ) distinct_reports
),
arrivals AS (
    SELECT DISTINCT ON (bus_id, trip_id, stop_id) bus_id, trip_id, stop_id, event_ts
    FROM reports WHERE event_type = 'stop_arrival'
    ORDER BY bus_id, trip_id, stop_id, event_ts, id
)
INSERT INTO silver.stop_visits
    (bus_id, trip_id, stop_id, arrival_ts, departure_ts, dwell_s, boarded, alighted, rejected,
     estimated_at_departure)
SELECT DISTINCT ON (a.bus_id, a.trip_id, a.stop_id)
       a.bus_id, a.trip_id, a.stop_id, a.event_ts, d.event_ts,
       extract(epoch FROM d.event_ts - a.event_ts),
       (d.payload->>'boarded')::int, (d.payload->>'alighted')::int, (d.payload->>'rejected')::int,
       coalesce(extract(epoch FROM d.event_ts - t.prev_ts) > %(estimated_after_s)s, false)
FROM arrivals a
JOIN reports d
  ON d.event_type = 'stop_departure'
 AND d.bus_id = a.bus_id AND d.trip_id = a.trip_id AND d.stop_id = a.stop_id
 AND d.event_ts >= a.event_ts
LEFT JOIN bus_report_times t ON t.bus_id = d.bus_id AND t.event_ts = d.event_ts
ORDER BY a.bus_id, a.trip_id, a.stop_id, d.event_ts, d.id
