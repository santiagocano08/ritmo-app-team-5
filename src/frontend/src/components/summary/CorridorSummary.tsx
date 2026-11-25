import type { Summary } from "../../api/types";

interface SummaryStat {
  testId: string;
  label: string;
  value: number;
}

export function CorridorSummary({ summary }: { summary: Summary }) {
  const stats: SummaryStat[] = [
    { testId: "summary-in-service", label: "En servicio", value: summary.buses_in_service },
    { testId: "summary-bunched", label: "Agrupados", value: summary.n_bunched },
    { testId: "summary-gaps", label: "Rezagados", value: summary.n_gaps },
  ];

  return (
    <section
      aria-label="Resumen del corredor"
      className="flex gap-3 rounded-card border border-border bg-surface p-4"
    >
      {stats.map((stat) => (
        <div key={stat.testId} className="flex flex-1 flex-col">
          <span className="text-xs font-semibold uppercase tracking-wide text-text-secondary">
            {stat.label}
          </span>
          <span
            data-testid={stat.testId}
            className="font-brand text-2xl font-bold text-text-primary"
          >
            {stat.value}
          </span>
        </div>
      ))}
    </section>
  );
}
