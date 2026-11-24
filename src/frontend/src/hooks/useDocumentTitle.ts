import { useEffect } from "react";
import type { SourceStatusValue } from "../api/types";
import { STATUS_LABELS } from "../components/shell/StatusBadge";

export function useDocumentTitle(status: SourceStatusValue): void {
  useEffect(() => {
    document.title = `PulsoFlota · ${STATUS_LABELS[status]}`;
  }, [status]);
}
