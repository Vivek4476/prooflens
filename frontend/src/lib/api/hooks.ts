"use client";

import { useQuery } from "@tanstack/react-query";

import { api } from "./client";
import type { HealthState } from "./types";

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

export function useAnalytics() {
  return useQuery({
    queryKey: ["analytics"],
    queryFn: () => api.analytics(),
    refetchInterval: 30_000,
  });
}

export function useTenants() {
  return useQuery({ queryKey: ["tenants"], queryFn: () => api.tenants(), retry: false });
}
