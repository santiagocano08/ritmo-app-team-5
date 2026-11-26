import { describe, expect, it } from "vitest";
import {
  actionLabel,
  formatExpiry,
  formatSaving,
} from "../../src/components/recommendations/labels";

describe("recommendation labels", () => {
  it.each([
    ["hold", "Retener"],
    ["reserve_dispatch", "Despachar reserva"],
    ["adjust_departure", "Ajustar salida"],
    ["skip_stop", "Saltar parada"],
    ["slow_down", "Reducir velocidad"],
  ] as const)("labels %s as %s", (type, label) => {
    expect(actionLabel(type)).toBe(label);
  });

  it("formats the saving as a waiting-time reduction", () => {
    expect(formatSaving(55)).toBe("−55 s de espera");
    expect(formatSaving(54.6)).toBe("−55 s de espera");
  });

  it("formats the expiry as HH:MM in the pinned test zone", () => {
    expect(formatExpiry("2026-11-24T08:12:00Z")).toBe("Vence 03:12");
    expect(formatExpiry("2026-11-24T22:05:00Z")).toBe("Vence 17:05");
  });
});
