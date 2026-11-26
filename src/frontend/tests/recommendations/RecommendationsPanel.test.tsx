import { afterEach, describe, expect, it, vi } from "vitest";
import { formatExpiry } from "../../src/components/recommendations/labels";
import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse, type JsonBodyType } from "msw";
import { RecommendationsPanel } from "../../src/components/recommendations/RecommendationsPanel";
import { useRecommendations } from "../../src/hooks/useRecommendations";
import { recommendationFixture } from "../../src/mocks/fixtures";
import { renderWithQuery } from "../test-utils";
import { server } from "../setup";
import { renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

const URL = "/api/v1/corridor/:corridorId/recommendations";

function respond(body: JsonBodyType): void {
  server.use(http.get(URL, () => HttpResponse.json(body)));
}

const item = (n: number) => ({
  ...recommendationFixture,
  rec_id: `cccc0003-0000-4000-8000-00000000004${n}`,
  rank: n,
});

describe("RecommendationsPanel", () => {
  it("lists one card per recommendation in the given order", async () => {
    respond({
      status: "ok",
      corridor_id: "C6-008",
      recommendations: [item(1), item(2), item(3)],
    });
    renderWithQuery(<RecommendationsPanel corridorId="C6-008" />);

    expect(screen.getByRole("heading", { name: "Recomendaciones" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByTestId("recommendation-card")).toHaveLength(3));
  });

  it("shows the default mock card", async () => {
    renderWithQuery(<RecommendationsPanel corridorId="C6-008" />);

    expect(await screen.findAllByTestId("recommendation-card")).toHaveLength(1);
  });

  it("shows the empty message", async () => {
    respond({ status: "ok", corridor_id: "C6-008", recommendations: [] });
    renderWithQuery(<RecommendationsPanel corridorId="C6-008" />);

    expect(await screen.findByText("Sin recomendaciones activas")).toBeInTheDocument();
  });

  it("shows the stale message and no cards", async () => {
    respond({ status: "stale", corridor_id: "C6-008", recommendations: [] });
    renderWithQuery(<RecommendationsPanel corridorId="C6-008" />);

    expect(
      await screen.findByText("Datos desactualizados: no se muestran recomendaciones"),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("recommendation-card")).not.toBeInTheDocument();
  });

  it("shows the shared no-data message", async () => {
    respond({ status: "no_data", corridor_id: "C6-008", recommendations: [] });
    renderWithQuery(<RecommendationsPanel corridorId="C6-008" />);

    expect(await screen.findByTestId("empty-state")).toBeInTheDocument();
  });

  it("has no apply or discard control", async () => {
    renderWithQuery(<RecommendationsPanel corridorId="C6-008" />);

    await screen.findAllByTestId("recommendation-card");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("useRecommendations", () => {
  it("polls every 5 s", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useRecommendations("C6-008"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const query = client.getQueryCache().find({ queryKey: ["recommendations", "C6-008"] });
    expect(query?.observers[0].options.refetchInterval).toBe(5000);
  });
});

describe("formatExpiry", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("uses the corridor zone whatever the host zone is", () => {
    vi.stubEnv("TZ", "Asia/Tokyo");
    expect(formatExpiry("2026-11-24T08:12:00Z")).toBe("Vence 03:12");
    vi.stubEnv("TZ", "UTC");
    expect(formatExpiry("2026-11-24T08:12:00Z")).toBe("Vence 03:12");
  });
});

describe("useRecommendations refetch", () => {
  it("requests the list again after 5 s", async () => {
    let calls = 0;
    server.use(
      http.get(URL, () => {
        calls += 1;
        return HttpResponse.json({ status: "ok", corridor_id: "C6-008", recommendations: [] });
      }),
    );
    vi.useFakeTimers({ shouldAdvanceTime: true });
    try {
      renderWithQuery(<RecommendationsPanel corridorId="C6-008" />);
      await waitFor(() => expect(calls).toBe(1));
      await vi.advanceTimersByTimeAsync(5100);
      await waitFor(() => expect(calls).toBe(2));
    } finally {
      vi.useRealTimers();
    }
  });
});
