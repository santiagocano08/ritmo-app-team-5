export type SectionId = "live_central" | "alerts" | "day_plan";

export interface SectionDef {
  readonly id: SectionId;
  readonly label: string;
  readonly icon: string;
  readonly href: string;
  readonly hasContent: boolean;
}

export const SECTIONS: readonly SectionDef[] = [
  { id: "live_central", label: "Central en vivo", icon: "◉", href: "#live", hasContent: true },
  { id: "alerts", label: "Alertas", icon: "✚", href: "#alerts", hasContent: false },
  { id: "day_plan", label: "Plan del día", icon: "▦", href: "#plan", hasContent: false },
];
