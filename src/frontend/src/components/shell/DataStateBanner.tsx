import type { SourceDown, SourceStatusValue } from "../../api/types";

interface DataStateBannerProps {
  status: SourceStatusValue;
  sourcesDown: SourceDown[];
}

const ESTIMATED_TEXT =
  "Parte de los datos son estimados porque la fuente de un operador no responde. " +
  "Las recomendaciones basadas en ellos se marcan como estimadas.";

const NO_DATA_TEXT =
  "No llegan eventos del corredor desde hace más de 2 min. " +
  "No hay recomendaciones nuevas; decide con el plan del día.";

const STYLES: Record<"estimated" | "no_data", string> = {
  estimated: "bg-status-estimated-bg text-status-estimated-fg",
  no_data: "bg-status-nodata-bg text-status-nodata-fg",
};

export function DataStateBanner({ status, sourcesDown }: DataStateBannerProps) {
  if (status === "live") {
    return null;
  }

  const text = status === "estimated" ? ESTIMATED_TEXT : NO_DATA_TEXT;
  const downList =
    status === "estimated" && sourcesDown.length > 0
      ? ` Fuentes sin reporte: ${sourcesDown.map((s) => s.bus_id).join(", ")}.`
      : "";

  return (
    <div
      role="alert"
      data-status={status}
      className={`w-full border-b border-border px-7 py-3 text-sm leading-[1.4] ${STYLES[status]}`}
    >
      {text}
      {downList}
    </div>
  );
}
