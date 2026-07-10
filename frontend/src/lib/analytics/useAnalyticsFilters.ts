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
};
const ALLOWED_KEYS = ["range", "bucket", "from", "to"] as const;

export function useAnalyticsFilters() {
  const [urlState, setUrlState] = useUrlState(DEFAULTS, [...ALLOWED_KEYS]);

  const preset = (urlState.range as RangePreset) || DEFAULT_PRESET;
  const bucket = (urlState.bucket as Bucket) || DEFAULT_BUCKET;

  const resolved = useMemo(
    () => resolvePreset(preset, new Date(), { start_date: urlState.from, end_date: urlState.to }),
    [preset, urlState.from, urlState.to],
  );

  // CRITICAL: memoize params — useAnalytics debounces its params input by 300ms,
  // and a fresh object identity every render (e.g. `{ ...resolved, bucket, ... }`
  // inlined at the call site) would reset that debounce timer indefinitely,
  // so the query would never settle. Keep this reference stable across renders
  // that don't actually change the resolved range/bucket.
  const params: AnalyticsParams = useMemo(
    () => ({
      start_date: resolved.start_date,
      end_date: resolved.end_date,
      bucket,
      group_by: "none", // Phase A never sets this to anything else
    }),
    [resolved.start_date, resolved.end_date, bucket],
  );

  function setPreset(next: RangePreset) {
    setUrlState({ range: next, from: undefined, to: undefined });
  }
  function setCustomRange(from: string, to: string) {
    setUrlState({ range: "custom", from, to });
  }
  function setBucket(next: Bucket) {
    setUrlState({ bucket: next });
  }

  return {
    preset,
    bucket,
    from: urlState.from,
    to: urlState.to,
    resolved,
    params,
    setPreset,
    setCustomRange,
    setBucket,
  };
}
