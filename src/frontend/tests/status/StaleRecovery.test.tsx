import { describe, expect, it } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import App from "../../src/App";
import { renderWithQuery } from "../test-utils";
import { server } from "../setup";
import normalFixture from "../../../../contracts/read/fixtures/normal/corridor_now.json";
import normalStatus from "../../../../contracts/read/fixtures/normal/source_status.json";

describe("Stale recovery", () => {
  it("keeps the last snapshot visible, shows the stale indicator, then recovers", async () => {
    renderWithQuery(<App />);
    // Two ~5 s poll cadences (fail then recover) exceed the default 5 s test timeout.

    await waitFor(() => expect(screen.getByText("B-105")).toBeInTheDocument());

    // Next refresh fails: backend returns 500.
    server.use(
      http.get("/api/v1/corridor/:id/now", () =>
        HttpResponse.json({ error: "internal_server_error", correlation_id: "x" }, { status: 500 }),
      ),
    );

    await waitFor(
      () => expect(screen.getByTestId("stale-indicator")).toBeInTheDocument(),
      { timeout: 7000 },
    );
    // Last snapshot is still visible while stale.
    expect(screen.getByText("B-105")).toBeInTheDocument();

    // Backend recovers.
    server.use(
      http.get("/api/v1/corridor/:id/now", () => HttpResponse.json(normalFixture)),
      http.get("/api/v1/corridor/:id/source-status", () => HttpResponse.json(normalStatus)),
    );

    await waitFor(
      () => expect(screen.queryByTestId("stale-indicator")).not.toBeInTheDocument(),
      { timeout: 7000 },
    );
  }, 20000);
});
