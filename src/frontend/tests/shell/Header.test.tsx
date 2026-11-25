import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Header } from "../../src/components/shell/Header";

describe("Header", () => {
  it("renders the corridor selector, status badge and clock", () => {
    render(
      <Header
        status="live"
        statusDetail="Último evento 08:00:00"
        corridorId="C6-008"
        direction={1}
      />,
    );

    expect(screen.getByText("CORREDOR")).toBeInTheDocument();
    expect(screen.getByText(/C6-008 · Estación → barrio/)).toBeInTheDocument();

    expect(screen.getByRole("status")).toHaveTextContent("En vivo");
    expect(screen.getByLabelText("Hora actual")).toBeInTheDocument();
  });
});
