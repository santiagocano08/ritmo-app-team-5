import { describe, expect, it } from "vitest";
import { formatCorridorLabel } from "../../src/components/shell/corridorLabel";

describe("formatCorridorLabel", () => {
  it("formats the id with the Turn-1 direction text when direction is 1", () => {
    expect(formatCorridorLabel("C6-008", 1)).toBe("C6-008 · Estación → barrio");
  });

  it("returns the id alone when direction is undefined", () => {
    expect(formatCorridorLabel("C6-008", undefined)).toBe("C6-008");
  });

  it("returns the id alone for any direction other than 1", () => {
    expect(formatCorridorLabel("C6-008", 2)).toBe("C6-008");
  });
});
