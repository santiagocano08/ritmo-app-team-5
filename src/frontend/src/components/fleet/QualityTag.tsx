import type { DataQuality } from "../../api/types";

const LABELS: Record<DataQuality, string> = {
  live: "Live",
  estimated: "Estimated",
};

const STYLES: Record<DataQuality, string> = {
  live: "bg-status-live-bg text-status-live-fg",
  estimated: "bg-status-estimated-bg text-status-estimated-fg",
};

export function QualityTag({ quality }: { quality: DataQuality }) {
  return (
    <span
      data-testid="quality-tag"
      className={`inline-flex items-center rounded-pill px-2 py-0.5 text-xs font-semibold ${STYLES[quality]}`}
    >
      {LABELS[quality]}
    </span>
  );
}
