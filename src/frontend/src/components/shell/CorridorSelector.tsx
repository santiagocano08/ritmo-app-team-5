export function CorridorSelector() {
  return (
    <div className="flex flex-col">
      <span className="text-xs font-semibold uppercase tracking-[0.05em] text-text-secondary">
        CORREDOR
      </span>
      <button
        type="button"
        className="flex items-center gap-1.5 border-none bg-transparent p-0 text-base font-bold text-text-primary"
      >
        [Corredor piloto] · Estación → casa
        <span aria-hidden="true">▾</span>
      </button>
    </div>
  );
}
