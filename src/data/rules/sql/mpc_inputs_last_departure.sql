-- Model input (006 FR-003): the newest departure from the first stop (the terminal), from completed visits.
-- The caller adds an open visit at that stop (its planned departure) and then the planned headway per slot.
-- Parameters: none (silver is rebuilt in the same transaction).
SELECT max(v.departure_ts)
FROM silver.stop_visits v
WHERE v.stop_id = (SELECT stop_id FROM config.ref_stops ORDER BY stop_seq LIMIT 1)
