import { useRecommendations } from "../../hooks/useRecommendations";
import { EmptyState } from "../status/EmptyState";
import { RecommendationCard } from "./RecommendationCard";

function PanelMessage({ children }: { children: string }) {
  return <p className="text-sm text-text-secondary">{children}</p>;
}

export function RecommendationsPanel({ corridorId }: { corridorId: string }) {
  const { data } = useRecommendations(corridorId);

  let body = null;
  if (data?.status === "no_data") {
    body = <EmptyState />;
  } else if (data?.status === "stale") {
    body = <PanelMessage>Datos desactualizados: no se muestran recomendaciones</PanelMessage>;
  } else if (data?.status === "ok" && data.recommendations.length === 0) {
    body = <PanelMessage>Sin recomendaciones activas</PanelMessage>;
  } else if (data?.status === "ok") {
    body = (
      <ul className="flex flex-col gap-3">
        {data.recommendations.map((recommendation) => (
          <RecommendationCard key={recommendation.rec_id} recommendation={recommendation} />
        ))}
      </ul>
    );
  }

  return (
    <aside aria-label="Recomendaciones" className="flex w-full flex-col gap-3 lg:w-[400px]">
      <h2 className="font-brand text-lg font-bold">Recomendaciones</h2>
      {body}
    </aside>
  );
}
