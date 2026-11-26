import type { Recommendation } from "../../api/types";
import { QualityTag } from "../fleet/QualityTag";
import { actionLabel, formatExpiry, formatSaving } from "./labels";

export function RecommendationCard({ recommendation }: { recommendation: Recommendation }) {
  const { action } = recommendation;
  const inConflict = recommendation.conflicts_with.length > 0;

  return (
    <li
      data-testid="recommendation-card"
      className="flex flex-col gap-2 rounded-card border border-border-default bg-surface p-4"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-brand text-base font-bold">{actionLabel(action.type)}</span>
        <QualityTag quality={recommendation.data_quality} />
      </div>
      <p className="text-sm text-text-secondary">
        {action.bus_id} · Parada {action.stop_id}
        {action.duration_s != null ? (
          <span data-testid="rec-duration"> · {action.duration_s} s</span>
        ) : null}
      </p>
      <p className="text-sm">{recommendation.reason}</p>
      <div className="flex items-center justify-between gap-2 text-sm">
        <span className="font-semibold">{formatSaving(recommendation.ewt_saving_s)}</span>
        <span className="text-text-secondary">{formatExpiry(recommendation.expires_ts)}</span>
      </div>
      {inConflict ? (
        <span className="text-xs font-semibold text-status-estimated-fg">En conflicto</span>
      ) : null}
    </li>
  );
}
