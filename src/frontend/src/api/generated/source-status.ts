// AUTO-GENERATED from contracts/read/*.schema.json v1.0.0 — do not hand-edit.
// Regenerate with: npm run gen:types

/**
 * Data-quality status of the telemetry sources for the active corridor. Produced by the data layer (gold view). Screen US-03. See ADR-0003.
 */
export interface SourceStatusV100 {
  /**
   * Read contract version (SemVer). Turn 1 produces only 1.0.0.
   */
  schema_version: "1.0.0";
  /**
   * UUID v4 identifying this gold snapshot. Referenced by recommendation.lineage.snapshot_id.
   */
  snapshot_id: string;
  /**
   * UTC timestamp when the gold view was computed.
   */
  as_of_ts: string;
  /**
   * Overall corridor status. 'live' = all active buses reporting within 2 min. 'estimated' = at least one bus not reporting > 2 min (no alert raised). 'no_data' = no events ever received.
   */
  status: "live" | "estimated" | "no_data";
  /**
   * List of buses that have not reported for more than 2 minutes. Empty when status is 'live'.
   */
  sources_down: {
    /**
     * Bus identifier.
     */
    bus_id: "B-101" | "B-102" | "B-103" | "B-104" | "B-105" | "B-106" | "B-107" | "B-108" | "B-109" | "B-110" | "B-111";
    /**
     * UTC timestamp of the last received event from this bus.
     */
    since: string;
  }[];
}
