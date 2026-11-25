import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sidebar } from "../../src/components/shell/Sidebar";

describe("Sidebar", () => {
  it("renders the dispatcher sections with the active one marked", () => {
    render(<Sidebar activeSection="live_central" onSelect={vi.fn()} />);

    const nav = screen.getByRole("navigation", { name: /secciones/i });
    expect(nav).toBeInTheDocument();

    expect(screen.getByText("Central en vivo")).toBeInTheDocument();
    expect(screen.getByText("Alertas")).toBeInTheDocument();
    expect(screen.getByText("Plan del día")).toBeInTheDocument();

    const active = screen.getByText("Central en vivo").closest("a");
    expect(active).toHaveAttribute("aria-current", "page");
  });

  it("renders the logo and user footer", () => {
    render(<Sidebar activeSection="live_central" onSelect={vi.fn()} />);
    expect(screen.getByText("PulsoFlota")).toBeInTheDocument();
    expect(screen.getByText("Usuario demo")).toBeInTheDocument();
    expect(screen.getByText("Despachador")).toBeInTheDocument();
  });

  it("renders one link per section, in order, inside the sections nav", () => {
    render(<Sidebar activeSection="live_central" onSelect={vi.fn()} />);
    const nav = screen.getByRole("navigation", { name: "Secciones" });
    const list = nav.querySelector("ul");
    const links = Array.from(list?.querySelectorAll("a[href]") ?? []);

    expect(links.map((link) => link.textContent?.trim())).toEqual([
      expect.stringContaining("Central en vivo"),
      expect.stringContaining("Alertas"),
      expect.stringContaining("Plan del día"),
    ]);
    expect(links.map((link) => link.getAttribute("href"))).toEqual(["#live", "#alerts", "#plan"]);
  });

  it("marks only the active section with aria-current and the active style", () => {
    render(<Sidebar activeSection="alerts" onSelect={vi.fn()} />);

    const alerts = screen.getByRole("link", { name: /alertas/i });
    expect(alerts).toHaveAttribute("aria-current", "page");
    expect(alerts).toHaveClass("bg-surface", "text-sidebar");

    for (const name of [/central en vivo/i, /plan del día/i]) {
      const link = screen.getByRole("link", { name });
      expect(link).not.toHaveAttribute("aria-current");
      expect(link).toHaveClass("text-sidebar-inactive");
    }
  });

  it("calls onSelect with the clicked section without changing the URL hash", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const hashBefore = window.location.hash;
    render(<Sidebar activeSection="live_central" onSelect={onSelect} />);

    await user.click(screen.getByRole("link", { name: /plan del día/i }));

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith("day_plan");
    expect(window.location.hash).toBe(hashBefore);
  });

  it("calls onSelect when an item is activated with the keyboard", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<Sidebar activeSection="live_central" onSelect={onSelect} />);

    const alerts = screen.getByRole("link", { name: /alertas/i });
    for (let presses = 0; presses < 5 && document.activeElement !== alerts; presses += 1) {
      await user.tab();
    }
    expect(alerts).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith("alerts");
  });

  it("calls onSelect with the same id when the active item is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<Sidebar activeSection="alerts" onSelect={onSelect} />);

    await user.click(screen.getByRole("link", { name: /alertas/i }));

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith("alerts");
  });

  it("never calls onSelect from the logout link", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<Sidebar activeSection="live_central" onSelect={onSelect} />);

    const logout = screen.getByRole("link", { name: /cerrar sesión/i });
    expect(logout).toHaveAttribute("href", "#logout");
    await user.click(logout);

    expect(onSelect).not.toHaveBeenCalled();
  });
});
