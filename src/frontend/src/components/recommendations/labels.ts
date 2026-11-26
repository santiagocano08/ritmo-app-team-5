import type { RecommendationActionType } from "../../api/types";

const ACTION_LABELS: Record<RecommendationActionType, string> = {
  hold: "Retener",
  reserve_dispatch: "Despachar reserva",
  adjust_departure: "Ajustar salida",
  skip_stop: "Saltar parada",
  slow_down: "Reducir velocidad",
};

export function actionLabel(type: RecommendationActionType): string {
  return ACTION_LABELS[type];
}

export function formatSaving(ewtSavingS: number): string {
  return `−${Math.round(ewtSavingS)} s de espera`;
}

// Same es-CO, 24 h style as the header clock, in the corridor's simulated-time zone rather than the host's.
export function formatExpiry(expiresTs: string): string {
  const time = new Date(expiresTs).toLocaleTimeString("es-CO", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "America/Bogota",
  });
  return `Vence ${time}`;
}
