import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../../src/components/shell/StatusBadge";

describe("StatusBadge", () => {
  it("renders the live state with role=status and text 'En vivo'", () => {
    render(<StatusBadge status="live" detail="Último evento 08:00:00" />);
    const badge = screen.getByRole("status");
    expect(badge).toHaveTextContent("En vivo");
    expect(badge).toHaveTextContent("Último evento 08:00:00");
  });

  it("renders the estimated state with text 'Estimado'", () => {
    render(<StatusBadge status="estimated" detail="Una fuente no responde" />);
    expect(screen.getByRole("status")).toHaveTextContent("Estimado");
  });

  it("renders the no_data state with text 'Sin datos'", () => {
    render(<StatusBadge status="no_data" detail="Sin eventos" />);
    expect(screen.getByRole("status")).toHaveTextContent("Sin datos");
  });

  it("renders the estimated detail without raising an alert", () => {
    render(<StatusBadge status="estimated" detail="Una fuente no responde desde 17:39" />);
    expect(screen.getByRole("status")).toHaveTextContent("Una fuente no responde desde 17:39");
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
