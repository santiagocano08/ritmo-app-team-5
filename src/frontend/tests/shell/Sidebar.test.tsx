import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "../../src/components/shell/Sidebar";

describe("Sidebar", () => {
  it("renders the dispatcher sections with the active one marked", () => {
    render(<Sidebar activeSection="live_central" />);

    const nav = screen.getByRole("navigation", { name: /secciones/i });
    expect(nav).toBeInTheDocument();

    expect(screen.getByText("Central en vivo")).toBeInTheDocument();
    expect(screen.getByText("Alertas")).toBeInTheDocument();
    expect(screen.getByText("Plan del día")).toBeInTheDocument();

    const active = screen.getByText("Central en vivo").closest("a");
    expect(active).toHaveAttribute("aria-current", "page");
  });

  it("renders the logo and user footer", () => {
    render(<Sidebar activeSection="live_central" />);
    expect(screen.getByText("PulsoFlota")).toBeInTheDocument();
    expect(screen.getByText("Usuario demo")).toBeInTheDocument();
    expect(screen.getByText("Despachador")).toBeInTheDocument();
  });
});
