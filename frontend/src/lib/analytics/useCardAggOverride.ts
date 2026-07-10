"use client";

import { useUrlState } from "@/lib/useUrlState";
import type { Bucket } from "@/lib/api/types";
import type { CardAggChoice } from "./cardOverride";

type AggUrlState = Record<string, string | undefined>;

function isBucket(v: string): v is Bucket {
  return v === "daily" || v === "weekly" || v === "monthly";
}

/**
 * Card-level aggregation override state, URL-synced under a caller-supplied
 * param name (e.g. `trend_agg`, `bandmix_agg`) so the two time-bucketed cards
 * stay independent in the querystring and a pasted URL reproduces the exact
 * per-card view. Value is omitted from the URL entirely when it's "page"
 * (the default) — same clean-URL convention as useAnalyticsFilters.
 */
export function useCardAggOverride(paramName: string) {
  const defaults: AggUrlState = { [paramName]: "page" };
  const [state, setState] = useUrlState(defaults, [paramName]);
  const raw = state[paramName];
  const choice: CardAggChoice = raw && isBucket(raw) ? raw : "page";

  function setChoice(next: CardAggChoice) {
    setState({ [paramName]: next });
  }

  return [choice, setChoice] as const;
}

// Re-export the namespaced param names used on the Analytics page so page.tsx
// and the two chart components share one source of truth.
export const TREND_AGG_PARAM = "trend_agg";
export const BANDMIX_AGG_PARAM = "bandmix_agg";
