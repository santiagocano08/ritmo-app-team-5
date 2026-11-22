import type { CorridorNowV100 } from "./generated/corridor-now";
import type { SourceStatusV100 } from "./generated/source-status";

export type CorridorNow = CorridorNowV100;
export type Bus = CorridorNowV100["buses"][number];
export type Summary = CorridorNowV100["summary"];
export type BusState = Bus["bus_state"];
export type DataQuality = Bus["data_quality"];

export type SourceStatus = SourceStatusV100;
export type SourceStatusValue = SourceStatusV100["status"];
export type SourceDown = SourceStatusV100["sources_down"][number];

export interface NoDataEnvelope {
  status: "no_data";
  corridor_id: string;
  sources_down?: [];
}

export type CorridorNowResponse = CorridorNow | NoDataEnvelope;
export type SourceStatusResponse = SourceStatus | NoDataEnvelope;

export function isNoData(
  value: CorridorNowResponse | SourceStatusResponse,
): value is NoDataEnvelope {
  return "status" in value && value.status === "no_data" && !("as_of_ts" in value);
}
