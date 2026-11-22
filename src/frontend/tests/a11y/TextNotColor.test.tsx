import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StateTag } from "../../src/components/fleet/StateTag";
import { QualityTag } from "../../src/components/fleet/QualityTag";
import { StatusBadge } from "../../src/components/shell/StatusBadge";
import { Sidebar } from "../../src/components/shell/Sidebar";
import type { BusState, DataQuality, SourceStatusValue } from "../../src/api/types";

const states: BusState[] = ["leader", "regular", "bunched", "gap", "broken_down"];
const qualities: DataQuality[] = ["live", "estimated"];
const statuses: SourceStatusValue[] = ["live", "estimated", "no_data"];

describe("Text, not color alone", () => {
  it("every bus_state carries a non-empty text label", () => {
    for (const state of states) {
      const { unmount } = render(<StateTag state={state} />);
      expect(screen.getByTestId("state-tag").textContent?.trim().length ?? 0).toBeGreaterThan(0);
      unmount();
    }
  });

  it("every data_quality carries a non-empty text label", () => {
    for (const quality of qualities) {
      const { unmount } = render(<QualityTag quality={quality} />);
      expect(screen.getByTestId("quality-tag").textContent?.trim().length ?? 0).toBeGreaterThan(0);
      unmount();
    }
  });

  it("every source status renders role=status with text", () => {
    for (const status of statuses) {
      const { unmount } = render(<StatusBadge status={status} detail="detalle" />);
      const badge = screen.getByRole("status");
      expect(badge.textContent?.trim().length ?? 0).toBeGreaterThan(0);
      unmount();
    }
  });

  it("the active nav section is marked with aria-current=page", () => {
    render(<Sidebar activeSection="live_central" />);
    const active = screen.getByText("Central en vivo").closest("a");
    expect(active).toHaveAttribute("aria-current", "page");
  });
});
