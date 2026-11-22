-- Backend hold decisions, in bronze id order (004 R4.1, R5; contracts/hold-loop.md).
-- Shared by the simulator's read-only poller and the pipeline's instruction-status step, so both
-- sides apply one definition. SELECT only: bronze is never written here.
-- decided_at_sim: event time of the newest non-backend bus report with a smaller id (NULL when the
-- decision precedes every report). The decision's own event_ts is a wall time and is not used.
-- Parameters: %(last_id)s (exclusive lower bound), %(max_id)s (inclusive upper bound).
SELECT e.id,
       e.payload->>'rec_id' AS rec_id,
       e.payload->>'action' AS action,
       (SELECT max(r.event_ts)
          FROM bronze.events r
         WHERE r.id < e.id
           AND r.source <> 'backend'
           AND r.event_type IN ('bus_position', 'stop_arrival', 'stop_departure')) AS decided_at_sim
FROM bronze.events e
WHERE e.source = 'backend'
  AND e.event_type = 'decision'
  AND e.id > %(last_id)s
  AND e.id <= %(max_id)s
ORDER BY e.id
