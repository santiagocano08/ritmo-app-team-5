import { describe, expect, it } from "vitest";
import { formatStatusDetail } from "../../src/components/shell/statusDetail";
import type { SourceDown } from "../../src/api/types";

const down = (since: string): SourceDown => ({ bus_id: "B-101", since });

describe("formatStatusDetail", () => {
  it("formats live as local HH:MM:SS", () => {
    expect(formatStatusDetail("live", "2026-11-24T22:42:08Z", [])).toBe("Último evento 17:42:08");
  });

  it("uses the earliest since for estimated", () => {
    const sources = [down("2026-11-24T22:41:00Z"), down("2026-11-24T22:39:00Z")];
    expect(formatStatusDetail("estimated", "2026-11-24T22:42:08Z", sources)).toBe(
      "Una fuente no responde desde 17:39",
    );
  });

  it("returns fixed text for no_data", () => {
    expect(formatStatusDetail("no_data", "", [])).toBe("Sin eventos del corredor");
  });

  it("zero-pads and handles midnight", () => {
    expect(formatStatusDetail("live", "2026-11-24T12:05:09Z", [])).toBe("Último evento 07:05:09");
    expect(formatStatusDetail("live", "2026-11-24T05:00:00Z", [])).toBe("Último evento 00:00:00");
  });

  it("degrades gracefully on unparsable input", () => {
    expect(formatStatusDetail("estimated", "x", [])).toBe("Una fuente no responde");
    expect(formatStatusDetail("estimated", "x", [down("nope")])).toBe("Una fuente no responde");
    expect(formatStatusDetail("live", "nope", [])).toBe("Último evento");
  });

  it("never emits a raw ISO string", () => {
    expect(formatStatusDetail("live", "2026-11-24T22:42:08Z", [])).not.toMatch(/\d{4}-\d{2}-\d{2}|Z$/);
  });
});
