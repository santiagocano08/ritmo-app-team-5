# Research: Active Recommendations in the Console

No NEEDS CLARIFICATION remained. Decisions:

**R1 Source of items.** Decision: read Q13 as stored, limit 3 in SQL, validate each doc with `RecommendationV110`. Rationale: FR-002, no recomputation (same as R1 of US-05). Alternative: recompute ranking in the backend (rejected, duplicates data-layer rules).

**R2 Staleness.** Decision: a read returning the latest snapshot id and `age_s = clock_timestamp() - committed_at` (Q0 as written in data-contract §3); `stale` when `age_s > 15`. Rationale: §2.1 forbids using `as_of_ts` (simulated time). Alternative: reuse `latest_snapshot_id` plus a second query (rejected, two round trips and a race).

**R3 Q13 ordering of reads.** Decision: Q13 is not keyed by snapshot, so it runs after Q0, only when the snapshot exists and is fresh. Alternative: filter by `lineage.snapshot_id` (rejected, the contract does not say older proposals disappear).

**R4 Frontend data.** Decision: `useQuery` with `refetchInterval: 5000`, like `useSourceStatus`. Alternative: WebSocket (deferred to turn 3).

**R5 Text safety.** Decision: render the reason as a React text child; never `dangerouslySetInnerHTML`.

**R6 Expiry format.** Decision: reuse the header clock's formatter for «Vence HH:MM» and pin TZ in the vite test env. Alternative: `toLocaleTimeString` (rejected, host-dependent).
