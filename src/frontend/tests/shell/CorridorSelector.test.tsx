import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CorridorSelector } from "../../src/components/shell/CorridorSelector";

describe("CorridorSelector", () => {
  it("renders the corridor id with the direction text when a snapshot is present", () => {
    render(<CorridorSelector corridorId="C6-008" direction={1} />);

    const button = screen.getByRole("button");
    expect(button).toHaveTextContent("C6-008 · Estación → barrio");

    expect(screen.getByText("CORREDOR")).toBeInTheDocument();
    expect(button).toHaveAttribute("type", "button");
    expect(screen.getByText("▾")).toHaveAttribute("aria-hidden", "true");

    expect(screen.queryByText(/\[Corredor piloto\]/)).not.toBeInTheDocument();
  });

  it("renders the corridor id alone before a snapshot arrives", () => {
    render(<CorridorSelector corridorId="C6-008" />);

    const button = screen.getByRole("button");
    expect(button).toHaveTextContent("C6-008");
    expect(button).not.toHaveTextContent("Estación → barrio");

    expect(screen.queryByText(/\[Corredor piloto\]/)).not.toBeInTheDocument();
  });
});
