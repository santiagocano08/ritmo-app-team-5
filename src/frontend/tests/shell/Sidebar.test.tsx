import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Sidebar } from "../../src/components/shell/Sidebar";

const RESIDUAL_GLYPHS = ["⬳", "◉", "✚", "▦", "⇥"];

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

  it("renders exactly one decorative svg icon for each nav link and the logout link", () => {
    render(<Sidebar activeSection="live_central" />);

    for (const label of ["Central en vivo", "Alertas", "Plan del día", "Cerrar sesión"]) {
      const link = screen.getByText(label).closest("a");
      expect(link).not.toBeNull();
      const svgs = link?.querySelectorAll("svg") ?? [];
      expect(svgs).toHaveLength(1);
      expect(svgs[0]).toHaveAttribute("aria-hidden", "true");
    }
  });

  it("renders the logo as a single decorative svg", () => {
    render(<Sidebar activeSection="live_central" />);

    const brand = screen.getByText("PulsoFlota").closest("div");
    expect(brand).not.toBeNull();
    const svgs = brand?.querySelectorAll("svg") ?? [];
    expect(svgs).toHaveLength(1);
    expect(svgs[0]).toHaveAttribute("aria-hidden", "true");
  });

  it("leaves no residual text glyph in the sidebar", () => {
    const { container } = render(<Sidebar activeSection="live_central" />);
    const text = container.textContent ?? "";
    for (const glyph of RESIDUAL_GLYPHS) {
      expect(text).not.toContain(glyph);
    }
  });
});
