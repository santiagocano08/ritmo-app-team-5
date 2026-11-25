import type { SourceStatusValue } from "../../api/types";

interface StatusBadgeProps {
  status: SourceStatusValue;
  detail?: string;
  stale?: boolean;
}

export const STATUS_LABELS: Record<SourceStatusValue, string> = {
  live: "En vivo",
  estimated: "Estimado",
  no_data: "Sin datos",
};

const STYLES: Record<SourceStatusValue, string> = {
  live: "bg-status-live-bg text-status-live-fg",
  estimated: "bg-status-estimated-bg text-status-estimated-fg",
  no_data: "bg-status-nodata-bg text-status-nodata-fg",
};

export function StatusBadge({ status, detail, stale = false }: StatusBadgeProps) {
  return (
    <span
      role="status"
      data-status={status}
      className={`inline-flex items-center gap-2.5 rounded-pill px-3 py-1.5 ${STYLES[status]}`}
    >
      <span
        aria-hidden="true"
        className="h-2.5 w-2.5 rounded-pill bg-current"
      />
      <span className="text-sm font-bold">{STATUS_LABELS[status]}</span>
      {detail ? <span className="text-[13px] font-normal">{detail}</span> : null}
      {stale ? <span className="text-[13px] font-normal">· sin conexión</span> : null}
    </span>
  );
}
