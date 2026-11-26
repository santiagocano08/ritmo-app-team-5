// AUTO-GENERATED from contracts/read/*.schema.json v1.0.0 — do not hand-edit.
// Regenerate with: npm run gen:types

/**
 * A regulation recommendation produced by the data layer's decision model (MPC). Data persists it in the gold layer. The dispatcher must approve before any on-road action is taken (Principle IV). Screen US-05. See ADR-0003.
 */
export type RecommendationV110 = {
  [k: string]: unknown;
} & {
  /**
   * Read contract version (SemVer). Producers write 1.1.0; 1.0.0 is still read.
   */
  schema_version: "1.0.0" | "1.1.0";
  /**
   * UUID v4 uniquely identifying this recommendation.
   */
  rec_id: string;
  /**
   * Regulation case. C1: bunching → hold. C2: gap → adjust departure. C5: breakdown → reserve dispatch. D1: source outage → information only, no alert.
   */
  case: "C1" | "C2" | "C5" | "D1";
  /**
   * The specific action proposed.
   */
  action: {
    /**
     * Action type. hold: keep bus at stop for duration_s. adjust_departure: depart stop early by duration_s. reserve_dispatch: dispatch a reserve bus from the depot. slow_down: the bus travels slower for duration_s (speed_reduction_pct). skip_stop: the bus does not stop at stops with an empty queue from stop_id on.
     */
    type: "hold" | "adjust_departure" | "reserve_dispatch" | "slow_down" | "skip_stop";
    /**
     * Target bus for the action.
     */
    bus_id: "B-101" | "B-102" | "B-103" | "B-104" | "B-105" | "B-106" | "B-107" | "B-108" | "B-109" | "B-110" | "B-111";
    /**
     * Stop where the action should be executed.
     */
    stop_id: string;
    /**
     * Duration in seconds. hold: 0..90 s (positive delay at stop). adjust_departure: -600..600 s (negative = depart earlier, positive = depart later). reserve_dispatch: always null. slow_down: 1..1800 s. skip_stop: always null.
     */
    duration_s?: number | null;
    /**
     * Speed reduction in percent while a slow_down is active (10 means the bus travels at 90 % of its speed). Required when type is slow_down; absent for every other type.
     */
    speed_reduction_pct?: number;
  };
  /**
   * Human-readable explanation of why this recommendation was generated. Frontend displays this to the dispatcher.
   */
  reason: string;
  /**
   * Projected reduction in Excess Wait Time in seconds if the action is applied. Positive = improvement.
   */
  ewt_saving_s: number;
  /**
   * Time horizon in seconds over which the ewt_saving_s projection is computed.
   */
  horizon_s: number;
  /**
   * Data quality of the snapshot used to generate this recommendation.
   */
  data_quality: "live" | "estimated";
  /**
   * UTC timestamp after which this recommendation is no longer actionable. Status transitions to 'expired' automatically.
   */
  expires_ts: string;
  /**
   * List of rec_id values that are mutually exclusive with this recommendation. Backend detects conflicts.
   */
  conflicts_with: string[];
  /**
   * Priority rank among concurrent recommendations. 1 = highest priority.
   */
  rank: number;
  /**
   * Lifecycle status. proposed: awaiting dispatcher decision. applied: dispatcher approved (command_event written). discarded: dispatcher rejected. expired: past expires_ts with no decision.
   */
  status: "proposed" | "applied" | "discarded" | "expired";
  /**
   * Traceability fields linking this recommendation to the data and rules that produced it.
   */
  lineage: {
    /**
     * Version of the M1/M2 baseline models used (SemVer string).
     */
    model_version: string;
    /**
     * Version of the decision rules applied (SemVer string). Matches the rules_version on gold rows.
     */
    rule_version: string;
    /**
     * UUID v4 of the corridor_now snapshot that triggered this recommendation.
     */
    snapshot_id: string;
  };
};
