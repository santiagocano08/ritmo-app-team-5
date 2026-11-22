// AUTO-GENERATED from contracts/read/*.schema.json v1.0.0 — do not hand-edit.
// Regenerate with: npm run gen:types

/**
 * Live fleet state for corridor C6-008, direction 1. Produced by the data layer (gold view). Screen US-04. See ADR-0003.
 */
export interface CorridorNowV100 {
  /**
   * Read contract version (SemVer). Turn 1 produces only 1.0.0.
   */
  schema_version: "1.0.0";
  /**
   * UUID v4 identifying this gold snapshot. Same value as source_status.snapshot_id for the same computation cycle.
   */
  snapshot_id: string;
  /**
   * UTC timestamp when the gold view was computed.
   */
  as_of_ts: string;
  /**
   * Corridor identifier. Turn 1: 'C6-008'.
   */
  corridor_id: string;
  /**
   * Travel direction. Turn 1 supports direction 1 only (station to neighbourhood).
   */
  direction: 1;
  /**
   * One entry per active bus currently on the corridor, ordered by distance_along_m descending (leader first — the bus furthest along the route).
   *
   * @minItems 0
   */
  buses: {
    /**
     * Vehicle identifier.
     */
    bus_id: "B-101" | "B-102" | "B-103" | "B-104" | "B-105" | "B-106" | "B-107";
    /**
     * Direction of travel.
     */
    direction: 1;
    /**
     * Stop id the bus most recently departed. Uses real P-<objectid> ids from data/reference/stops.csv.
     */
    prev_stop_id: string;
    /**
     * Stop id the bus is heading towards.
     */
    next_stop_id: string;
    /**
     * Distance from origin (P-883, 0 m) to terminus (P-900, 5119.4 m) in meters. No geometry in turn 1.
     */
    distance_along_m: number;
    /**
     * Gap in seconds to the bus immediately ahead (higher distance_along_m, further along the route). Null for the leader bus (no bus ahead on the corridor) or for a broken_down bus. A broken_down bus is excluded from headway calculations: the bus behind it measures its gap to the next operational bus ahead, skipping the broken_down bus.
     */
    headway_ahead_s: number | null;
    /**
     * Planned headway in seconds for this time window. Turn 1 peak value: 600 s.
     */
    headway_planned_s: number;
    /**
     * Computed state. 'leader': furthest-ahead bus on the corridor (headway_ahead_s is null — no bus ahead). 'regular': within tolerance. 'bunched': headway_ahead_s < 0.5 * headway_planned_s. 'gap': headway_ahead_s > 1.5 * headway_planned_s. 'broken_down': incident of type bus_breakdown active for this bus.
     */
    bus_state: "leader" | "regular" | "bunched" | "gap" | "broken_down";
    /**
     * Per-bus data quality. 'live': last event within 2 min. 'estimated': no report > 2 min; position is extrapolated; no alert raised.
     */
    data_quality: "live" | "estimated";
    /**
     * UTC timestamp of the event_ts from the last bus_position event used for this entry.
     */
    ts: string;
  }[];
  /**
   * Corridor-level summary counts.
   */
  summary: {
    /**
     * Number of active buses on the corridor (not broken down, not in reserve).
     */
    buses_in_service: number;
    /**
     * Number of buses in 'bunched' state.
     */
    n_bunched: number;
    /**
     * Number of buses in 'gap' state.
     */
    n_gaps: number;
  };
}
