import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SectionPlaceholder } from "../../src/components/status/SectionPlaceholder";

describe("SectionPlaceholder", () => {
  it("renders the pending-section text", () => {
    render(<SectionPlaceholder />);
    expect(screen.getByTestId("section-placeholder")).toHaveTextContent(
      /^Contenido de la sección: se define en las próximas historias\.$/,
    );
  });

  it("uses the dashed placeholder frame from the style spec", () => {
    render(<SectionPlaceholder />);
    expect(screen.getByTestId("section-placeholder")).toHaveClass(
      "flex",
      "flex-1",
      "items-center",
      "justify-center",
      "rounded-card",
      "border-2",
      "border-dashed",
      "border-border-placeholder",
      "p-6",
      "text-center",
      "text-[15px]",
      "text-text-secondary",
    );
  });
});
