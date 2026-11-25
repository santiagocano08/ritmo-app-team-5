import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getRecommendations } from "../api/client";
import type { RecommendationsResponse } from "../api/types";

export const recommendationsQueryKey = (corridorId: string) =>
  ["recommendations", corridorId] as const;

export function useRecommendations(corridorId: string) {
  return useQuery<RecommendationsResponse>({
    queryKey: recommendationsQueryKey(corridorId),
    queryFn: () => getRecommendations(corridorId),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
    placeholderData: keepPreviousData,
    retry: false,
  });
}
