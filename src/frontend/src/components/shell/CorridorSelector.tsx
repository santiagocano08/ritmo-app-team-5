import { formatCorridorLabel } from "./corridorLabel";

interface CorridorSelectorProps {
  corridorId: string;
  direction?: number;
}

export function CorridorSelector({ corridorId, direction }: CorridorSelectorProps) {
  return (
    <div className="flex flex-col">
      <span className="text-xs font-semibold uppercase tracking-[0.05em] text-text-secondary">
        CORREDOR
      </span>
      <button
        type="button"
        className="flex items-center gap-1.5 border-none bg-transparent p-0 text-base font-bold text-text-primary"
      >
        {formatCorridorLabel(corridorId, direction)}
        <span aria-hidden="true">▾</span>
      </button>
    </div>
  );
}
