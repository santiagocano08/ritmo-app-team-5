import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useTabTitle } from "../../src/hooks/useTabTitle";
import type { SourceStatusValue } from "../../src/api/types";

describe("useTabTitle", () => {
  it.each([
    ["live", "PulsoFlota · En vivo"],
    ["estimated", "PulsoFlota · Estimado"],
    ["no_data", "PulsoFlota · Sin datos"],
  ] as const)("sets the title for %s", (status, expected) => {
    renderHook(() => useTabTitle(status));
    expect(document.title).toBe(expected);
  });

  it("falls back to no data for an unrecognized status", () => {
    renderHook(() => useTabTitle("bogus" as never));
    expect(document.title).toBe("PulsoFlota · Sin datos");
  });

  it("updates the title when the status changes", () => {
    const { rerender } = renderHook(
      ({ status }: { status: SourceStatusValue }) => useTabTitle(status),
      { initialProps: { status: "live" as SourceStatusValue } },
    );
    expect(document.title).toBe("PulsoFlota · En vivo");
    rerender({ status: "estimated" });
    expect(document.title).toBe("PulsoFlota · Estimado");
  });
});
