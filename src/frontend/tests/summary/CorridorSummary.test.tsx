import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CorridorSummary } from "../../src/components/summary/CorridorSummary";
import bunchingFixture from "../../../../contracts/read/fixtures/c1_bunching/corridor_now.json";
import gapFixture from "../../../../contracts/read/fixtures/c2_gap/corridor_now.json";
import type { CorridorNow } from "../../src/api/types";

const bunching = bunchingFixture as CorridorNow;
const gap = gapFixture as CorridorNow;

describe("CorridorSummary", () => {
  it("shows buses_in_service, n_bunched and n_gaps matching the bunching fixture", () => {
    render(<CorridorSummary summary={bunching.summary} />);

    expect(screen.getByTestId("summary-in-service")).toHaveTextContent("5");
    expect(screen.getByTestId("summary-bunched")).toHaveTextContent("2");
    expect(screen.getByTestId("summary-gaps")).toHaveTextContent("1");
  });

  it("updates counts when the snapshot changes", () => {
    const { rerender } = render(<CorridorSummary summary={bunching.summary} />);
    rerender(<CorridorSummary summary={gap.summary} />);

    expect(screen.getByTestId("summary-in-service")).toHaveTextContent("5");
    expect(screen.getByTestId("summary-bunched")).toHaveTextContent("0");
    expect(screen.getByTestId("summary-gaps")).toHaveTextContent("2");
  });
});
