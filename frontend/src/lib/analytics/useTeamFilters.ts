"use client";

import { useMemo } from "react";
import type { AnalyticsParams, Bucket } from "@/lib/api/types";
import { useUrlState } from "@/lib/useUrlState";
import { DEFAULT_BUCKET, DEFAULT_PRESET, resolvePreset, type RangePreset } from "./dateRanges";

const DEFAULTS = {
  range: DEFAULT_PRESET as string,
  bucket: DEFAULT_BUCKET as string,
  from: undefined as string | undefined,
  to: undefined as string | undefined,
  dim: undefined as string | undefined,
  node: undefined as string | undefined,
};
const ALLOWED_KEYS = ["range", "bucket", "from", "to", "dim", "node"] as const;

/** Pure: assemble the analytics query for a team (node-scoped, per-agent breakdown). */
export function teamParams(
  resolved: { start_date: string; end_date: string; bucket: Bucket },
  dim: string | undefined,
  node: string | undefined,
): AnalyticsParams {
  return { ...resolved, group_by: "agent", dim, node };
}

export function useTeamFilters() {
  const [urlState, setUrlState] = useUrlState(DEFAULTS, [...ALLOWED_KEYS]);
  const preset = (urlState.range as RangePreset) || DEFAULT_PRESET;
  const bucket = (urlState.bucket as Bucket) || DEFAULT_BUCKET;
  const resolved = useMemo(
    () => resolvePreset(preset, new Date(), { start_date: urlState.from, end_date: urlState.to }),
    [preset, urlState.from, urlState.to],
  );
  const params = useMemo(
    () => teamParams({ ...resolved, bucket }, urlState.dim, urlState.node),
    [resolved, bucket, urlState.dim, urlState.node],
  );
  return {
    dim: urlState.dim, node: urlState.node, preset, bucket, from: urlState.from, to: urlState.to,
    params,
    setPreset: (n: RangePreset) => setUrlState({ range: n, from: undefined, to: undefined }),
    setCustomRange: (from: string, to: string) => setUrlState({ range: "custom", from, to }),
    setBucket: (n: Bucket) => setUrlState({ bucket: n }),
  };
}
