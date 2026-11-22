import type { BusState } from "../../api/types";

const LABELS: Record<BusState, string> = {
  leader: "Leader",
  regular: "Regular",
  bunched: "Bunched",
  gap: "Gap",
  broken_down: "Broken down",
};

const ICONS: Record<BusState, string> = {
  leader: "▲",
  regular: "●",
  bunched: "⇄",
  gap: "↔",
  broken_down: "■",
};

const STYLES: Record<BusState, string> = {
  leader: "bg-status-live-bg text-status-live-fg",
  regular: "bg-app text-text-secondary border border-border",
  bunched: "bg-status-nodata-bg text-status-nodata-fg",
  gap: "bg-status-estimated-bg text-status-estimated-fg",
  broken_down: "bg-status-nodata-bg text-status-nodata-fg",
};

export function StateTag({ state }: { state: BusState }) {
  return (
    <span
      data-testid="state-tag"
      data-state={state}
      className={`inline-flex items-center gap-1.5 rounded-pill px-2.5 py-0.5 text-xs font-semibold ${STYLES[state]}`}
    >
      <span aria-hidden="true">{ICONS[state]}</span>
      {LABELS[state]}
    </span>
  );
}
