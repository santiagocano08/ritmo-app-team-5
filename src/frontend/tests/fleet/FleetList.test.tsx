import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { FleetList } from "../../src/components/fleet/FleetList";
import normalFixture from "../../../../contracts/read/fixtures/normal/corridor_now.json";
import type { CorridorNow } from "../../src/api/types";

const normal = normalFixture as CorridorNow;

describe("FleetList", () => {
  it("renders every bus in the received order (leader-first, no client re-sort)", () => {
    render(<FleetList buses={normal.buses} />);

    const rows = screen.getAllByTestId("bus-row");
    expect(rows).toHaveLength(normal.buses.length);

    const renderedIds = rows.map((row) => within(row).getByTestId("bus-id").textContent);
    expect(renderedIds).toEqual(normal.buses.map((bus) => bus.bus_id));
    expect(renderedIds[0]).toBe("B-105");
  });
});
