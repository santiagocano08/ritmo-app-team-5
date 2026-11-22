-- S3 silver.bus_current_state (FR-008-FR-011, R7). Run after silver_incidents.sql.
-- Parameters: %(as_of_ts)s, %(max_bronze_id)s, %(estimated_after_s)s (the single 120 s
-- threshold, src.data.rules.ESTIMATED_AFTER_S), %(untrusted_buses)s (text[], buses the clock guard distrusts,
-- 005 US6; 006 adds `occupancy` from the same row). A position outside 0..route end is ignored (005 US5): the position columns and the waiting test come
-- from the newest in-range position, and a bus whose newest bus_position is out of range is Estimated.
WITH reports AS (
    SELECT e.id, e.event_ts, e.event_type,
           e.payload->>'bus_id' AS bus_id,
           e.payload->>'trip_id' AS trip_id,
           e.payload
    FROM bronze.events e
    WHERE e.event_type IN ('bus_position', 'stop_arrival', 'stop_departure')
      AND e.source <> 'backend'
      AND e.id <= %(max_bronze_id)s
      AND e.event_ts <= %(as_of_ts)s
),
latest_report AS (
    SELECT DISTINCT ON (bus_id) bus_id, trip_id
    FROM reports
    ORDER BY bus_id, event_ts DESC, id DESC
),
last_seen AS (
    SELECT bus_id, max(event_ts) AS last_report_ts FROM reports GROUP BY bus_id
),
route_end AS (
    SELECT max(distance_along_m) AS end_m FROM config.ref_stops
),
positions AS (  -- every bus_position with its range flag
    SELECT r.*, (r.payload->>'distance_along_m')::numeric AS dist_m,
           (r.payload->>'distance_along_m')::numeric BETWEEN 0 AND (SELECT end_m FROM route_end) AS in_range
    FROM reports r
    WHERE r.event_type = 'bus_position'
),
latest_position AS (  -- newest in-range position
    SELECT DISTINCT ON (bus_id) bus_id, trip_id, event_ts, dist_m AS distance_along_m,
           (payload->>'occupancy')::int AS occupancy
    FROM positions
    WHERE in_range
    ORDER BY bus_id, event_ts DESC, id DESC
),
newest_position_bad AS (  -- the newest bus_position by (event_ts, id) is out of range
    SELECT DISTINCT ON (bus_id) bus_id, NOT in_range AS bad
    FROM positions
    ORDER BY bus_id, event_ts DESC, id DESC
),
terminus AS (
    SELECT stop_id FROM config.ref_stops ORDER BY stop_seq DESC LIMIT 1
),
first_stop AS (
    SELECT stop_id, distance_along_m FROM config.ref_stops ORDER BY stop_seq ASC LIMIT 1
),
finished AS (
    SELECT DISTINCT r.bus_id, r.trip_id
    FROM reports r
    WHERE r.event_type = 'stop_arrival'
      AND r.payload->>'stop_id' = (SELECT stop_id FROM terminus)
),
departed AS (  -- left the first stop on that trip: on the corridor from here to the terminus
    SELECT DISTINCT r.bus_id, r.trip_id
    FROM reports r
    WHERE r.event_type = 'stop_departure'
      AND r.payload->>'stop_id' = (SELECT stop_id FROM first_stop)
),
trip_position AS (
    SELECT DISTINCT ON (bus_id, trip_id) bus_id, trip_id, dist_m AS distance_along_m
    FROM positions
    WHERE in_range
    ORDER BY bus_id, trip_id, event_ts DESC, id DESC
),
-- Waiting at the first stop for the scheduled departure (R7, decided 2026-11-20): the current
-- trip has not left the first stop, and its latest position is still at the first stop (or it
-- has no position yet and has arrived there). Its reports still count for freshness.
status AS (
    SELECT l.bus_id,
           EXISTS (SELECT 1 FROM finished f WHERE f.bus_id = l.bus_id AND f.trip_id = l.trip_id) AS is_finished,
           (NOT EXISTS (SELECT 1 FROM finished f WHERE f.bus_id = l.bus_id AND f.trip_id = l.trip_id)
            AND NOT EXISTS (SELECT 1 FROM departed d WHERE d.bus_id = l.bus_id AND d.trip_id = l.trip_id)
            AND COALESCE(
                  (SELECT tp.distance_along_m <= (SELECT distance_along_m FROM first_stop)
                     FROM trip_position tp WHERE tp.bus_id = l.bus_id AND tp.trip_id = l.trip_id),
                  EXISTS (SELECT 1 FROM reports r
                           WHERE r.bus_id = l.bus_id AND r.trip_id = l.trip_id
                             AND r.event_type = 'stop_arrival'
                             AND r.payload->>'stop_id' = (SELECT stop_id FROM first_stop)))
           ) AS is_waiting
    FROM latest_report l
)
INSERT INTO silver.bus_current_state
    (bus_id, trip_id, distance_along_m, position_ts, position_trip_id, prev_stop_id, next_stop_id,
     last_report_ts, data_quality, on_corridor, waiting, operational_status, as_of_ts, occupancy)
SELECT s.bus_id,
       l.trip_id,
       p.distance_along_m,
       p.event_ts,
       p.trip_id,
       (SELECT st.stop_id FROM config.ref_stops st
         WHERE st.distance_along_m <= p.distance_along_m ORDER BY st.stop_seq DESC LIMIT 1),
       (SELECT st.stop_id FROM config.ref_stops st
         WHERE st.distance_along_m > p.distance_along_m ORDER BY st.stop_seq ASC LIMIT 1),
       s.last_report_ts,
       CASE WHEN %(as_of_ts)s - s.last_report_ts > %(estimated_after_s)s::double precision * interval '1 second'
                 OR COALESCE(nb.bad, false)
                 OR s.bus_id = ANY(%(untrusted_buses)s::text[])
            THEN 'estimated' ELSE 'live' END,
       NOT st.is_finished AND NOT st.is_waiting,
       st.is_waiting,
       CASE
           WHEN EXISTS (SELECT 1 FROM silver.incidents i
                         WHERE i.incident_type = 'bus_breakdown' AND i.target_id = s.bus_id
                           AND i.start_ts <= %(as_of_ts)s AND %(as_of_ts)s < i.end_ts)
               THEN 'broken_down'
           WHEN NOT st.is_finished AND NOT st.is_waiting
               THEN 'in_service'
           WHEN EXISTS (SELECT 1 FROM config.fleet_roster fr WHERE fr.bus_id = s.bus_id AND fr.role = 'reserve')
               THEN 'reserve'
           ELSE 'off_corridor'
       END,
       %(as_of_ts)s,
       p.occupancy  -- 006 M4: from the same newest in-range position row as distance_along_m
FROM last_seen s
JOIN latest_report l USING (bus_id)
JOIN status st USING (bus_id)
LEFT JOIN latest_position p USING (bus_id)
LEFT JOIN newest_position_bad nb USING (bus_id)
