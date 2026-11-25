import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BusRow } from "../../src/components/fleet/BusRow";
import type { Bus } from "../../src/api/types";

const leader: Bus = {
  bus_id: "B-105",
  direction: 1,
  prev_stop_id: "P-893",
  next_stop_id: "P-894",
  distance_along_m: 3860,
  headway_ahead_s: null,
  headway_planned_s: 600,
  bus_state: "leader",
  data_quality: "live",
  ts: "2026-11-24T07:59:55Z",
};

const follower: Bus = {
  ...leader,
  bus_id: "B-104",
  prev_stop_id: "P-889",
  next_stop_id: "P-890",
  distance_along_m: 2900,
  headway_ahead_s: 601,
  bus_state: "regular",
};

describe("BusRow", () => {
  it("shows state, position label and headway comparison for a following bus", () => {
    render(<BusRow bus={follower} />);

    expect(screen.getByTestId("bus-id")).toHaveTextContent("B-104");
    expect(screen.getByTestId("bus-position")).toHaveTextContent("P-889");
    expect(screen.getByTestId("bus-position")).toHaveTextContent("P-890");
    expect(screen.getByTestId("headway-compare")).toHaveTextContent("601");
    expect(screen.getByTestId("headway-compare")).toHaveTextContent("600");
  });

  it("shows no headway comparison when headway_ahead_s is null", () => {
    render(<BusRow bus={leader} />);

    expect(screen.queryByTestId("headway-compare")).not.toBeInTheDocument();
  });

  it("renders a bunched, estimated bus in Spanish", () => {
    const bunched: Bus = {
      ...follower,
      bus_state: "bunched",
      data_quality: "estimated",
      headway_ahead_s: 660,
      headway_planned_s: 600,
    };
    render(<BusRow bus={bunched} />);

    expect(screen.getByTestId("state-tag")).toHaveTextContent("Agrupado");
    expect(screen.getByTestId("quality-tag")).toHaveTextContent("Estimado");
    expect(screen.getByTestId("bus-position")).toHaveTextContent(/^Entre .+ y .+ · \d+ m$/);
    expect(screen.getByTestId("headway-compare")).toHaveTextContent("del plan");
    expect(screen.getByTestId("headway-compare")).toHaveTextContent("(+60 s sobre el plan)");
  });
});
