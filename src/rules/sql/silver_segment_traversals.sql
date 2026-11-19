-- S5 silver.segment_traversals with the two exclusion flags (FR-013, FR-014, FR-026, R7).
-- Segment k runs from stop_seq k to k+1. Run after silver_incidents.sql.
-- hour_band: local hour with the fixed UTC-5 offset (same as Python), not a time-zone name.
-- Parameters: %(as_of_ts)s, %(max_bronze_id)s, %(estimated_after_s)s (src.rules.ESTIMATED_AFTER_S).
WITH reports AS (
    SELECT e.id, e.event_ts, e.event_type,
           e.payload->>'bus_id' AS bus_id,
           e.payload->>'trip_id' AS trip_id,
           e.payload->>'stop_id' AS stop_id
    FROM bronze.events e
    WHERE e.event_type IN ('bus_position', 'stop_arrival', 'stop_departure')
      AND e.source <> 'backend'
      AND e.id <= %(max_bronze_id)s
      AND e.event_ts <= %(as_of_ts)s
),
departures AS (
    SELECT DISTINCT ON (r.bus_id, r.trip_id, s.stop_seq)
           r.bus_id, r.trip_id, s.stop_seq AS segment_id, r.event_ts
    FROM reports r JOIN config.ref_stops s ON s.stop_id = r.stop_id
    WHERE r.event_type = 'stop_departure'
    ORDER BY r.bus_id, r.trip_id, s.stop_seq, r.event_ts, r.id
),
arrivals AS (
    SELECT DISTINCT ON (r.bus_id, r.trip_id, s.stop_seq)
           r.bus_id, r.trip_id, s.stop_seq, r.event_ts
    FROM reports r JOIN config.ref_stops s ON s.stop_id = r.stop_id
    WHERE r.event_type = 'stop_arrival'
    ORDER BY r.bus_id, r.trip_id, s.stop_seq, r.event_ts, r.id
),
paired AS (
    SELECT d.bus_id, d.trip_id, d.segment_id, d.event_ts AS departure_ts, a.event_ts AS arrival_ts
    FROM departures d
    JOIN arrivals a ON a.bus_id = d.bus_id AND a.trip_id = d.trip_id AND a.stop_seq = d.segment_id + 1
    WHERE a.event_ts >= d.event_ts
)
INSERT INTO silver.segment_traversals
    (bus_id, trip_id, segment_id, departure_ts, arrival_ts, travel_s, hour_band,
     travelled_while_estimated, broken_down)
SELECT p.bus_id, p.trip_id, p.segment_id, p.departure_ts, p.arrival_ts,
       extract(epoch FROM p.arrival_ts - p.departure_ts),
       extract(hour FROM (p.departure_ts AT TIME ZONE 'UTC' - interval '5 hours'))::smallint,
       EXISTS (
           SELECT 1
           FROM (SELECT r.event_ts,
                        lag(r.event_ts) OVER (ORDER BY r.event_ts, r.id) AS prev_ts
                 FROM reports r
                 WHERE r.bus_id = p.bus_id
                   AND r.event_ts BETWEEN p.departure_ts AND p.arrival_ts) g
           WHERE g.event_ts - g.prev_ts > %(estimated_after_s)s::double precision * interval '1 second'
       ),
       EXISTS (
           SELECT 1 FROM silver.incidents i
           WHERE i.incident_type = 'bus_breakdown' AND i.target_id = p.bus_id
             AND i.end_ts > i.start_ts
             AND i.start_ts <= p.arrival_ts AND i.end_ts > p.departure_ts
       )
FROM paired p
