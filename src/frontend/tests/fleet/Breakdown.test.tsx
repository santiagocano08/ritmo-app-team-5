import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { FleetList } from "../../src/components/fleet/FleetList";
import breakdownFixture from "../../../../contracts/read/fixtures/c5_breakdown/corridor_now.json";
import type { CorridorNow } from "../../src/api/types";

const breakdown = breakdownFixture as CorridorNow;

describe("Breakdown scenario", () => {
  it("renders a broken_down bus distinguishably with no headway comparison", () => {
    render(<FleetList buses={breakdown.buses} />);

    const brokenRow = screen
      .getAllByTestId("bus-row")
      .find((row) => row.getAttribute("data-bus-id") === "B-104");
    expect(brokenRow).toBeDefined();
    if (!brokenRow) return;

    const stateTag = within(brokenRow).getByTestId("state-tag");
    expect(stateTag).toHaveTextContent(/varado/i);
    expect(stateTag).toHaveAttribute("data-state", "broken_down");
    expect(within(brokenRow).queryByTestId("headway-compare")).not.toBeInTheDocument();
  });

  it("keeps counts consistent with the fixture summary", () => {
    expect(breakdown.summary.buses_in_service).toBe(4);
    expect(breakdown.summary.n_gaps).toBe(1);
  });
});
