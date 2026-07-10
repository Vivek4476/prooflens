"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "./client";
import type { AnalyticsParams, Bucket, HealthState } from "./types";
import { useDebouncedValue } from "./useDebouncedValue";

export function useHealth() {
  const query = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const [live, ready] = await Promise.allSettled([api.health(), api.ready()]);
      return {
        live: live.status === "fulfilled",
        ready: ready.status === "fulfilled" && ready.value.status === "ready",
      };
    },
    refetchInterval: 15_000,
    retry: false,
  });

  let state: HealthState = "loading";
  if (query.data) {
    if (query.data.live && query.data.ready) state = "ok";
    else if (query.data.live) state = "degraded";
    else state = "down";
  } else if (query.isError) {
    state = "down";
  }
  return { state, ...query };
}

export function useResults(params?: {
  limit?: number;
  offset?: number;
  band?: string;
  review?: string;
  reason?: string;
  rep_id?: string;
  from?: string;
  to?: string;
}) {
  return useQuery({
    queryKey: ["results", params],
    queryFn: () => api.results(params),
    refetchInterval: 20_000,
  });
}

export function useResult(id: string | undefined) {
  return useQuery({
    queryKey: ["result", id],
    queryFn: () => api.result(id as string),
    enabled: !!id,
    retry: false,
  });
}

export function useAnalytics(params: AnalyticsParams = {}, enabled: boolean = true) {
  const debounced = useDebouncedValue(params, 300);
  return useQuery({
    queryKey: ["analytics", debounced],
    queryFn: () => api.analytics(debounced),
    // Keep the previous page's data visible while the debounced params refetch,
    // so widgets show a subtle in-place update rather than a full unmount —
    // pairs with Task 8's "skeleton only on first load" rule.
    placeholderData: (prev) => prev,
    refetchInterval: 30_000,
    // No retry: like every other query in this file, a failed request should
    // surface the honest error state promptly (BRAND.md "honest states
    // only") instead of holding the loading skeleton through react-query's
    // default multi-second retry/backoff sequence.
    retry: false,
    enabled,
  });
}

export function useTenants() {
  return useQuery({ queryKey: ["tenants"], queryFn: () => api.tenants(), retry: false });
}

/** Below this length a non-empty query doesn't fire — a single character matches
 *  a huge swath of DSEs, so we wait for a more selective query. */
const MIN_QUERY_LEN = 2;

/** Debounced DSE search-as-you-type. An empty q intentionally hits the backend
 *  (the recent/most-active default roster shown when the box opens); a 1-char q
 *  is suppressed so we don't fire an unselective request on every keystroke. */
export function useDseSearch(q: string, enabled: boolean = true) {
  const debounced = useDebouncedValue(q, 300);
  const trimmed = debounced.trim();
  const queryable = trimmed.length === 0 || trimmed.length >= MIN_QUERY_LEN;
  return useQuery({
    queryKey: ["dse-search", trimmed],
    queryFn: () => api.dseSearch(trimmed),
    enabled: enabled && queryable,
    retry: false,
  });
}

export function useDseScorecard(
  agentId: string | undefined,
  params?: { from?: string; to?: string; bucket?: Bucket },
) {
  const debounced = useDebouncedValue(params, 300);
  return useQuery({
    queryKey: ["dse-scorecard", agentId, debounced],
    queryFn: () => api.dseScorecard(agentId as string, debounced),
    enabled: !!agentId,
    placeholderData: (prev) => prev,
    retry: false,
  });
}
