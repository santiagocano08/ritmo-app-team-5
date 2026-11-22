import type { Bus } from "../../api/types";
import { BusRow } from "./BusRow";

export function FleetList({ buses }: { buses: Bus[] }) {
  return (
    <ul data-testid="fleet-list" className="flex flex-col gap-3">
      {buses.map((bus) => (
        <BusRow key={bus.bus_id} bus={bus} />
      ))}
    </ul>
  );
}
