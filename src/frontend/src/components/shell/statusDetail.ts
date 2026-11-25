import type { SourceDown, SourceStatusValue } from "../../api/types";

const pad = (value: number): string => String(value).padStart(2, "0");

function parseTime(iso: string): Date | null {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatStatusDetail(
  status: SourceStatusValue,
  asOfTs: string,
  sourcesDown: SourceDown[],
): string {
  if (status === "no_data") {
    return "Sin eventos del corredor";
  }
  if (status === "live") {
    const asOf = parseTime(asOfTs);
    return asOf
      ? `Último evento ${pad(asOf.getHours())}:${pad(asOf.getMinutes())}:${pad(asOf.getSeconds())}`
      : "Último evento";
  }
  const times = sourcesDown
    .map((source) => parseTime(source.since))
    .filter((date): date is Date => date !== null)
    .map((date) => date.getTime());
  if (times.length === 0) {
    return "Una fuente no responde";
  }
  const earliest = new Date(Math.min(...times));
  return `Una fuente no responde desde ${pad(earliest.getHours())}:${pad(earliest.getMinutes())}`;
}
