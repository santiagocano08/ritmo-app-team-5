-- S3 silver.bus_current_state (FR-008-FR-011, R7). Run after silver_incidents.sql.
-- Parameters: %(as_of_ts)s, %(max_bronze_id)s, %(estimated_after_s)s (the single 120 s
-- threshold, src.rules.ESTIMATED_AFTER_S).
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
latest_position AS (
    SELECT DISTINCT ON (bus_id) bus_id, trip_id, event_ts,
           (payload->>'distance_along_m')::numeric AS distance_along_m
    FROM reports
    WHERE event_type = 'bus_position'
    ORDER BY bus_id, event_ts DESC, id DESC
),
terminus AS (
    SELECT stop_id FROM config.ref_stops ORDER BY stop_seq DESC LIMIT 1
),
finished AS (
    SELECT DISTINCT r.bus_id, r.trip_id
    FROM reports r
    WHERE r.event_type = 'stop_arrival'
      AND r.payload->>'stop_id' = (SELECT stop_id FROM terminus)
)
INSERT INTO silver.bus_current_state
    (bus_id, trip_id, distance_along_m, position_ts, position_trip_id, prev_stop_id, next_stop_id,
     last_report_ts, data_quality, on_corridor, operational_status, as_of_ts)
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
            THEN 'estimated' ELSE 'live' END,
       NOT EXISTS (SELECT 1 FROM finished f WHERE f.bus_id = s.bus_id AND f.trip_id = l.trip_id),
       CASE
           WHEN EXISTS (SELECT 1 FROM silver.incidents i
                         WHERE i.incident_type = 'bus_breakdown' AND i.target_id = s.bus_id
                           AND i.start_ts <= %(as_of_ts)s AND %(as_of_ts)s < i.end_ts)
               THEN 'broken_down'
           WHEN NOT EXISTS (SELECT 1 FROM finished f WHERE f.bus_id = s.bus_id AND f.trip_id = l.trip_id)
               THEN 'in_service'
           WHEN EXISTS (SELECT 1 FROM config.fleet_roster fr WHERE fr.bus_id = s.bus_id AND fr.role = 'reserve')
               THEN 'reserve'
           ELSE 'off_corridor'
       END,
       %(as_of_ts)s
FROM last_seen s
JOIN latest_report l USING (bus_id)
LEFT JOIN latest_position p USING (bus_id)
