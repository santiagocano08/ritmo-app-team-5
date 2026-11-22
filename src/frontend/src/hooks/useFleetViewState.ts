import type { UseQueryResult } from "@tanstack/react-query";
import type {
  CorridorNow,
  CorridorNowResponse,
  NoDataEnvelope,
  SourceStatus,
  SourceStatusResponse,
} from "../api/types";
import { isNoData } from "../api/types";

export interface FleetViewState {
  connection: "ok" | "stale";
  lastSnapshot: CorridorNow | null;
  lastSourceStatus: SourceStatus | NoDataEnvelope | null;
  isEmpty: boolean;
  lastUpdated: string | null;
}

function toSnapshot(data: CorridorNowResponse | undefined): CorridorNow | null {
  if (!data || isNoData(data)) {
    return null;
  }
  return data;
}

function toSourceStatus(
  data: SourceStatusResponse | undefined,
): SourceStatus | NoDataEnvelope | null {
  return data ?? null;
}

export function deriveFleetViewState(
  corridorQuery: Pick<UseQueryResult<CorridorNowResponse>, "data" | "isError">,
  sourceStatusQuery: Pick<UseQueryResult<SourceStatusResponse>, "data">,
): FleetViewState {
  const snapshot = toSnapshot(corridorQuery.data);
  const corridorIsNoData = corridorQuery.data !== undefined && isNoData(corridorQuery.data);

  const isEmpty =
    corridorIsNoData || (snapshot !== null && snapshot.summary.buses_in_service === 0);

  return {
    connection: corridorQuery.isError && snapshot !== null ? "stale" : "ok",
    lastSnapshot: snapshot,
    lastSourceStatus: toSourceStatus(sourceStatusQuery.data),
    isEmpty,
    lastUpdated: snapshot?.as_of_ts ?? null,
  };
}
