import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import App from "../../src/App";
import { renderWithQuery } from "../test-utils";
import { server } from "../setup";

const noDataCorridor = { status: "no_data", corridor_id: "C6-008" };
const noDataStatus = { status: "no_data", corridor_id: "C6-008", sources_down: [] };

describe("No-data envelope", () => {
  it("renders the no-data status, the day's-plan banner and a zero-count empty state", async () => {
    server.use(
      http.get("/api/v1/corridor/:id/now", () => HttpResponse.json(noDataCorridor)),
      http.get("/api/v1/corridor/:id/source-status", () =>
        HttpResponse.json(noDataStatus),
      ),
    );

    renderWithQuery(<App />);

    await waitFor(() => {
      expect(screen.getByRole("status", { name: "" })).toHaveTextContent("Sin datos");
    });
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/plan del día/i);
    expect(screen.getByTestId("empty-state")).toBeInTheDocument();
  });
});
