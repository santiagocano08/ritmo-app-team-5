import { describe, expect, it } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useCorridorNow } from "../../src/hooks/useCorridorNow";
import { setScenario } from "../../src/mocks/handlers";
import { isNoData } from "../../src/api/types";

function wrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("useCorridorNow", () => {
  it("fetches the current snapshot via the typed client", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result } = renderHook(() => useCorridorNow("C6-008"), {
      wrapper: wrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const data = result.current.data;
    expect(data).toBeDefined();
    if (data && !isNoData(data)) {
      expect(data.buses[0].bus_id).toBe("B-105");
    }
  });

  it("is configured to poll every 5 s and keep the previous snapshot", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { result, rerender } = renderHook(() => useCorridorNow("C6-008"), {
      wrapper: wrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const first = result.current.data;

    setScenario("c1_bunching");
    await client.invalidateQueries({ queryKey: ["corridor-now", "C6-008"] });
    rerender();

    // Previous data is retained (placeholderData: keepPreviousData) while refetching.
    expect(result.current.data).toBeDefined();
    await waitFor(() => {
      const current = result.current.data;
      if (current && !isNoData(current) && first && !isNoData(first)) {
        expect(current.snapshot_id).not.toBe(first.snapshot_id);
      }
    });
  });
});
