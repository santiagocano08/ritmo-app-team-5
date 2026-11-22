import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getCorridorNow } from "../api/client";
import type { CorridorNowResponse } from "../api/types";

export const corridorNowQueryKey = (corridorId: string) =>
  ["corridor-now", corridorId] as const;

export function useCorridorNow(corridorId: string) {
  return useQuery<CorridorNowResponse>({
    queryKey: corridorNowQueryKey(corridorId),
    queryFn: () => getCorridorNow(corridorId),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
    placeholderData: keepPreviousData,
    retry: false,
  });
}
