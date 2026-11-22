export function EmptyState() {
  return (
    <div
      data-testid="empty-state"
      className="flex flex-1 flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed border-border-placeholder p-6 text-center"
    >
      <p className="text-[15px] text-text-secondary">
        No hay buses en servicio en el corredor en este momento.
      </p>
      <dl className="flex gap-6 text-text-secondary">
        <div className="flex flex-col">
          <dt className="text-xs uppercase tracking-wide">En servicio</dt>
          <dd className="font-brand text-2xl font-bold">0</dd>
        </div>
        <div className="flex flex-col">
          <dt className="text-xs uppercase tracking-wide">Agrupados</dt>
          <dd className="font-brand text-2xl font-bold">0</dd>
        </div>
        <div className="flex flex-col">
          <dt className="text-xs uppercase tracking-wide">Rezagados</dt>
          <dd className="font-brand text-2xl font-bold">0</dd>
        </div>
      </dl>
    </div>
  );
}
