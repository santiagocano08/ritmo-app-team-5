import { describe, expect, it } from "vitest";
import { renderHook } from "@testing-library/react";
import { useDocumentTitle } from "../../src/hooks/useDocumentTitle";
import { STATUS_LABELS } from "../../src/components/shell/StatusBadge";
import type { SourceStatusValue } from "../../src/api/types";

describe("useDocumentTitle", () => {
  it.each(["live", "estimated", "no_data"] as const)(
    "sets the title from the %s badge label",
    (status) => {
      renderHook(() => useDocumentTitle(status));
      expect(document.title).toBe(`PulsoFlota · ${STATUS_LABELS[status]}`);
    },
  );

  it("updates the title when the status changes without remounting", () => {
    const { rerender } = renderHook(
      ({ status }: { status: SourceStatusValue }) => useDocumentTitle(status),
      { initialProps: { status: "live" } },
    );
    expect(document.title).toBe("PulsoFlota · En vivo");

    rerender({ status: "estimated" });
    expect(document.title).toBe("PulsoFlota · Estimado");
  });
});
