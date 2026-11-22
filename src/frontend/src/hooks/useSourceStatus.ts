import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getSourceStatus } from "../api/client";
import type { SourceStatusResponse } from "../api/types";

export const sourceStatusQueryKey = (corridorId: string) =>
  ["source-status", corridorId] as const;

export function useSourceStatus(corridorId: string) {
  return useQuery<SourceStatusResponse>({
    queryKey: sourceStatusQueryKey(corridorId),
    queryFn: () => getSourceStatus(corridorId),
    refetchInterval: 5000,
    refetchIntervalInBackground: false,
    placeholderData: keepPreviousData,
    retry: false,
  });
}
