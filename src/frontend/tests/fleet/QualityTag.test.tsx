import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { QualityTag } from "../../src/components/fleet/QualityTag";

describe("QualityTag", () => {
  it("labels an estimated bus 'Estimado' without raising an alert", () => {
    render(<QualityTag quality="estimated" />);

    const tag = screen.getByTestId("quality-tag");
    expect(tag).toHaveTextContent(/estimado/i);
    expect(tag).not.toHaveAttribute("role", "alert");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("labels a live bus 'En vivo'", () => {
    render(<QualityTag quality="live" />);
    expect(screen.getByTestId("quality-tag")).toHaveTextContent(/en vivo/i);
  });
});
