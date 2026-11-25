import type { ReactNode } from "react";
import { BellIcon, CalendarIcon, PulseIcon } from "./icons";

export type SectionId = "live_central" | "alerts" | "day_plan";

export interface SectionDef {
  readonly id: SectionId;
  readonly label: string;
  readonly icon: ReactNode;
  readonly href: string;
  readonly hasContent: boolean;
}

export const SECTIONS: readonly SectionDef[] = [
  { id: "live_central", label: "Central en vivo", icon: PulseIcon, href: "#live", hasContent: true },
  { id: "alerts", label: "Alertas", icon: BellIcon, href: "#alerts", hasContent: false },
  { id: "day_plan", label: "Plan del día", icon: CalendarIcon, href: "#plan", hasContent: false },
];
