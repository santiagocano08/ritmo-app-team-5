import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import App from "../../src/App";
import { renderWithQuery } from "../test-utils";
import { server } from "../setup";
import { setScenario } from "../../src/mocks/handlers";

describe("App document title", () => {
  it("shows the no-data title before any response", () => {
    renderWithQuery(<App />);
    expect(document.title).toBe("PulsoFlota · Sin datos");
  });

  it.each([
    ["normal", "En vivo"],
    ["d1_source_outage", "Estimado"],
  ] as const)("matches the header badge for scenario %s", async (scenario, label) => {
    setScenario(scenario);
    renderWithQuery(<App />);

    await waitFor(() => {
      expect(screen.getByRole("status", { name: "" })).toHaveTextContent(label);
    });
    expect(document.title).toBe(`PulsoFlota · ${label}`);
  });

  it("matches the badge when the corridor has no data", async () => {
    server.use(
      http.get("/api/v1/corridor/:id/now", () =>
        HttpResponse.json({ status: "no_data", corridor_id: "C6-008" }),
      ),
      http.get("/api/v1/corridor/:id/source-status", () =>
        HttpResponse.json({ status: "no_data", corridor_id: "C6-008", sources_down: [] }),
      ),
    );
    renderWithQuery(<App />);

    await waitFor(() => {
      expect(screen.getByRole("status", { name: "" })).toHaveTextContent("Sin datos");
    });
    expect(document.title).toBe("PulsoFlota · Sin datos");
  });
});
