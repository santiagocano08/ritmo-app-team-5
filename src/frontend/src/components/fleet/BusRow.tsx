import type { Bus } from "../../api/types";
import { StateTag } from "./StateTag";
import { QualityTag } from "./QualityTag";
import { HeadwayCompare } from "./HeadwayCompare";

function positionLabel(bus: Bus): string {
  return `Entre ${bus.prev_stop_id} y ${bus.next_stop_id} · ${Math.round(bus.distance_along_m)} m`;
}

export function BusRow({ bus }: { bus: Bus }) {
  return (
    <li
      data-testid="bus-row"
      data-bus-id={bus.bus_id}
      className="flex flex-col gap-2 rounded-card border border-border bg-surface p-4"
    >
      <div className="flex items-center justify-between gap-3">
        <span data-testid="bus-id" className="font-brand text-base font-bold text-text-primary">
          {bus.bus_id}
        </span>
        <div className="flex items-center gap-2">
          <StateTag state={bus.bus_state} />
          <QualityTag quality={bus.data_quality} />
        </div>
      </div>
      <p data-testid="bus-position" className="text-sm text-text-secondary">
        {positionLabel(bus)}
      </p>
      <HeadwayCompare
        headwayAheadS={bus.headway_ahead_s}
        headwayPlannedS={bus.headway_planned_s}
      />
    </li>
  );
}
