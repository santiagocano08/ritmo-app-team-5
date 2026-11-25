import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import App from "../../src/App";
import { setScenario } from "../../src/mocks/handlers";
import { renderWithQuery } from "../test-utils";
import { server } from "../setup";
import outageCorridor from "../../../../contracts/read/fixtures/d1_source_outage/corridor_now.json";
import outageStatus from "../../../../contracts/read/fixtures/d1_source_outage/source_status.json";

function sectionLink(label: string): HTMLElement {
  return screen.getByRole("link", { name: new RegExp(label, "i") });
}

function currentLinks(): HTMLElement[] {
  const nav = screen.getByRole("navigation", { name: "Secciones" });
  return Array.from(nav.querySelectorAll<HTMLElement>('a[aria-current="page"]'));
}

function expectPlaceholderSection(label: string): void {
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(label);
  expect(currentLinks()).toEqual([sectionLink(label)]);
  expect(screen.getByTestId("section-placeholder")).toBeInTheDocument();
  expect(screen.queryByText("B-105")).not.toBeInTheDocument();
  expect(screen.queryByTestId("stale-indicator")).not.toBeInTheDocument();
  expect(screen.queryByTestId("empty-state")).not.toBeInTheDocument();
}

describe("Section switching", () => {
  it("shows the placeholder for sections without content and keeps header and banner", async () => {
    setScenario("d1_source_outage");
    const user = userEvent.setup();
    renderWithQuery(<App />);
    await waitFor(() => expect(screen.getByText("B-105")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());

    await user.click(sectionLink("Alertas"));
    expectPlaceholderSection("Alertas");
    expect(screen.getByRole("status")).toHaveTextContent("Estimado");
    expect(screen.getByRole("alert")).toBeInTheDocument();

    await user.click(sectionLink("Plan del día"));
    expectPlaceholderSection("Plan del día");
    expect(screen.getByRole("status")).toHaveTextContent("Estimado");
    expect(screen.getByRole("alert")).toBeInTheDocument();

    await user.click(sectionLink("Plan del día"));
    expectPlaceholderSection("Plan del día");
  });

  it("keeps exactly one highlighted item matching the title across switches", async () => {
    const user = userEvent.setup();
    renderWithQuery(<App />);
    await waitFor(() => expect(screen.getByText("B-105")).toBeInTheDocument());

    const sequence = ["Alertas", "Plan del día", "Central en vivo", "Plan del día", "Alertas"];
    for (const label of sequence) {
      await user.click(sectionLink(label));
      const current = currentLinks();
      expect(current).toHaveLength(1);
      expect(current[0]).toHaveTextContent(label);
      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(label);
    }
  });

  it("opens on the live section with the fleet view", async () => {
    renderWithQuery(<App />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Central en vivo");
    expect(currentLinks()).toEqual([sectionLink("Central en vivo")]);
    await waitFor(() => expect(screen.getByText("B-105")).toBeInTheDocument());
    expect(screen.queryByTestId("section-placeholder")).not.toBeInTheDocument();
  });

  it(
    "returns to the fleet view and keeps polling the corridor after switching back",
    async () => {
      let nowRequests = 0;
      const countNowRequests = ({ request }: { request: Request }) => {
        if (new URL(request.url).pathname.endsWith("/now")) {
          nowRequests += 1;
        }
      };
      server.events.on("request:start", countNowRequests);
      try {
        const user = userEvent.setup();
        renderWithQuery(<App />);
        await waitFor(() => expect(screen.getByText("B-105")).toBeInTheDocument());

        await user.click(sectionLink("Plan del día"));
        expectPlaceholderSection("Plan del día");

        await user.click(sectionLink("Central en vivo"));
        expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Central en vivo");
        expect(screen.getByText("B-105")).toBeInTheDocument();
        expect(screen.getByRole("region", { name: "Resumen del corredor" })).toBeInTheDocument();
        expect(screen.queryByTestId("section-placeholder")).not.toBeInTheDocument();

        const requestsOnReturn = nowRequests;
        await waitFor(() => expect(nowRequests).toBeGreaterThan(requestsOnReturn), {
          timeout: 7000,
        });
      } finally {
        server.events.removeListener("request:start", countNowRequests);
      }
    },
    20000,
  );

  it(
    "reflects a degraded feed while away and shows the current state on return",
    async () => {
      setScenario("d1_source_outage");
      const user = userEvent.setup();
      renderWithQuery(<App />);
      await waitFor(() => expect(screen.getByText("B-105")).toBeInTheDocument());

      await user.click(sectionLink("Alertas"));
      server.use(
        http.get("/api/v1/corridor/:id/now", () =>
          HttpResponse.json({ error: "internal_server_error", correlation_id: "x" }, { status: 500 }),
        ),
      );

      await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("sin conexión"), {
        timeout: 7000,
      });
      expectPlaceholderSection("Alertas");
      expect(screen.getByRole("alert")).toBeInTheDocument();

      server.use(
        http.get("/api/v1/corridor/:id/now", () => HttpResponse.json(outageCorridor)),
        http.get("/api/v1/corridor/:id/source-status", () => HttpResponse.json(outageStatus)),
      );
      await waitFor(
        () => expect(screen.getByRole("status")).not.toHaveTextContent("sin conexión"),
        { timeout: 7000 },
      );

      await user.click(sectionLink("Central en vivo"));
      expect(screen.getByText("B-105")).toBeInTheDocument();
      expect(screen.queryByTestId("stale-indicator")).not.toBeInTheDocument();
      expect(screen.getByRole("alert")).toBeInTheDocument();
    },
    20000,
  );
});
