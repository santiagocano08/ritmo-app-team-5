import { useEffect } from "react";
import { STATUS_LABELS } from "../components/shell/StatusBadge";
import type { SourceStatusValue } from "../api/types";

export function tabTitle(status: SourceStatusValue): string {
  const label = Object.hasOwn(STATUS_LABELS, status)
    ? STATUS_LABELS[status]
    : STATUS_LABELS.no_data;
  return `PulsoFlota · ${label}`;
}

export function useTabTitle(status: SourceStatusValue): void {
  useEffect(() => {
    document.title = tabTitle(status);
  }, [status]);
}
