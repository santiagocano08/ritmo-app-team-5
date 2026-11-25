import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RecommendationCard } from "../../src/components/recommendations/RecommendationCard";
import type { Recommendation } from "../../src/api/types";
import { recommendationFixture } from "../../src/mocks/fixtures";

function build(overrides: Partial<Recommendation> = {}): Recommendation {
  return { ...recommendationFixture, ...overrides };
}

describe("RecommendationCard", () => {
  it("shows every dispatcher-facing field", () => {
    render(<RecommendationCard recommendation={build()} />);

    expect(screen.getByText("Retener")).toBeInTheDocument();
    expect(screen.getByText(/B-101 · Parada P-887/)).toBeInTheDocument();
    expect(screen.getByTestId("rec-duration")).toHaveTextContent("90 s");
    expect(screen.getByText(/B-101 and B-103 are bunching/)).toBeInTheDocument();
    expect(screen.getByText("−55 s de espera")).toBeInTheDocument();
    expect(screen.getByTestId("quality-tag")).toHaveTextContent("En vivo");
    expect(screen.getByText("Vence 03:12")).toBeInTheDocument();
    expect(screen.queryByText("En conflicto")).not.toBeInTheDocument();
  });

  it("omits the duration when it is null", () => {
    const action = { ...recommendationFixture.action, type: "reserve_dispatch" as const, duration_s: null };
    render(<RecommendationCard recommendation={build({ action })} />);

    expect(screen.getByText("Despachar reserva")).toBeInTheDocument();
    expect(screen.queryByTestId("rec-duration")).not.toBeInTheDocument();
  });

  it("marks recommendations in conflict", () => {
    render(
      <RecommendationCard
        recommendation={build({ conflicts_with: ["cccc0003-0000-4000-8000-000000000031"] })}
      />,
    );

    expect(screen.getByText("En conflicto")).toBeInTheDocument();
  });

  it("renders markup in the reason literally as text", () => {
    const reason = '<img src=x onerror="alert(1)"><b>bold</b>';
    const { container } = render(<RecommendationCard recommendation={build({ reason })} />);

    expect(screen.getByText(reason)).toBeInTheDocument();
    expect(container.querySelector("img, b")).toBeNull();
  });

  it("has no button", () => {
    render(<RecommendationCard recommendation={build()} />);

    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
