import type { SourceStatusValue } from "../../api/types";
import { CorridorSelector } from "./CorridorSelector";
import { StatusBadge } from "./StatusBadge";
import { Clock } from "./Clock";

interface HeaderProps {
  status: SourceStatusValue;
  statusDetail?: string;
  stale?: boolean;
  corridorId: string;
  direction?: number;
}

export function Header({ status, statusDetail, stale, corridorId, direction }: HeaderProps) {
  return (
    <header className="flex h-[68px] items-center gap-5 border-b border-border bg-surface px-7">
      <CorridorSelector corridorId={corridorId} direction={direction} />
      <div className="ml-auto flex items-center gap-4">
        <StatusBadge status={status} detail={statusDetail} stale={stale} />
        <Clock />
      </div>
    </header>
  );
}
