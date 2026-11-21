-- S2 silver.incidents: active on [start_ts, end_ts) (FR-015, R7).
-- Incidents of every source count, including backend (dispatcher reports, ADR-0003).
-- Parameters: %(as_of_ts)s, %(max_bronze_id)s.
INSERT INTO silver.incidents (inc_id, incident_type, target_id, start_ts, end_ts, reported_by, source, bronze_id)
SELECT e.event_id,
       e.payload->>'incident_type',
       e.payload->>'target_id',
       e.event_ts,
       e.event_ts + (e.payload->>'duration_min')::numeric * interval '1 minute',
       e.payload->>'reported_by',
       e.source,
       e.id
FROM bronze.events e
WHERE e.event_type = 'incident_report'
  AND e.id <= %(max_bronze_id)s
  AND e.event_ts <= %(as_of_ts)s
