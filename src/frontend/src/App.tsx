import { useCorridorNow } from "./hooks/useCorridorNow";
import { useSourceStatus } from "./hooks/useSourceStatus";
import { deriveFleetViewState } from "./hooks/useFleetViewState";
import { FleetList } from "./components/fleet/FleetList";
import { CorridorSummary } from "./components/summary/CorridorSummary";
import { Sidebar } from "./components/shell/Sidebar";
import { Header } from "./components/shell/Header";
import { DataStateBanner } from "./components/shell/DataStateBanner";
import { EmptyState } from "./components/status/EmptyState";
import { StaleIndicator } from "./components/status/StaleIndicator";
import { isNoData, type SourceDown, type SourceStatusValue } from "./api/types";
import { corridorId } from "./mocks/fixtures";

function resolveSourceStatus(
  lastSourceStatus: ReturnType<typeof deriveFleetViewState>["lastSourceStatus"],
): { status: SourceStatusValue; sourcesDown: SourceDown[]; detail?: string } {
  if (!lastSourceStatus) {
    return { status: "no_data", sourcesDown: [] };
  }
  if (isNoData(lastSourceStatus)) {
    return { status: "no_data", sourcesDown: [], detail: "Sin eventos del corredor" };
  }
  return {
    status: lastSourceStatus.status,
    sourcesDown: lastSourceStatus.sources_down,
    detail: `Último evento ${lastSourceStatus.as_of_ts}`,
  };
}

export default function App() {
  const corridorQuery = useCorridorNow(corridorId);
  const sourceStatusQuery = useSourceStatus(corridorId);

  const fleet = deriveFleetViewState(corridorQuery, sourceStatusQuery);
  const snapshot = fleet.lastSnapshot;
  const buses = snapshot?.buses ?? [];
  const { status, sourcesDown, detail } = resolveSourceStatus(fleet.lastSourceStatus);
  const stale = fleet.connection === "stale";

  return (
    <div className="flex h-full min-h-screen bg-app text-text-primary">
      <Sidebar activeSection="live_central" />
      <div className="flex flex-1 flex-col">
        <Header status={status} statusDetail={detail} stale={stale} />
        <DataStateBanner status={status} sourcesDown={sourcesDown} />
        <main className="flex flex-1 flex-col gap-4 p-7">
          <h1 className="font-brand text-[26px] font-bold">Central en vivo</h1>
          <StaleIndicator stale={stale} />
          {fleet.isEmpty ? (
            <EmptyState />
          ) : (
            <>
              {snapshot ? <CorridorSummary summary={snapshot.summary} /> : null}
              <FleetList buses={buses} />
            </>
          )}
        </main>
      </div>
    </div>
  );
}
