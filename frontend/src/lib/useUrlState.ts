"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

/** Pure: encode a partial state object into a URLSearchParams-compatible record,
 *  dropping keys whose value equals the default (keeps URLs clean). */
export function serializeState<T extends Record<string, string | undefined>>(
  state: T,
  defaults: Partial<T>,
): Record<string, string> {
  const out: Record<string, string> = {};
  for (const key of Object.keys(state)) {
    const v = state[key];
    if (v === undefined || v === "") continue;
    if (defaults[key] !== undefined && v === defaults[key]) continue;
    out[key] = v;
  }
  return out;
}

/** Pure: apply this hook's OWNED keys onto a copy of the current querystring, preserving
 *  any foreign params. This is what lets several independent `useUrlState` instances share
 *  one URL (e.g. the global filters + two per-card aggregation overrides) without wiping
 *  each other's params. Owned keys equal to their default (or empty) are removed. */
export function mergeState<T extends Record<string, string | undefined>>(
  current: URLSearchParams,
  next: T,
  defaults: Partial<T>,
  allowedKeys: (keyof T)[],
): URLSearchParams {
  const params = new URLSearchParams(current.toString());
  for (const key of allowedKeys) {
    const k = String(key);
    const v = next[key];
    const isDefault = defaults[key] !== undefined && v === defaults[key];
    if (v === undefined || v === "" || isDefault) params.delete(k);
    else params.set(k, v as string);
  }
  return params;
}

/** Pure: parse a URLSearchParams into a typed state object, falling back to defaults
 *  and dropping keys not in `allowedKeys` (ignores unrelated query params). */
export function parseState<T extends Record<string, string | undefined>>(
  params: URLSearchParams,
  defaults: T,
  allowedKeys: (keyof T)[],
): T {
  const out = { ...defaults };
  for (const key of allowedKeys) {
    const raw = params.get(String(key));
    if (raw !== null && raw !== "") out[key] = raw as T[typeof key];
  }
  return out;
}

/** React binding: reads the given keys from the URL (typed via defaults), and
 *  returns [state, setState] where setState merges + replaces the URL (no history
 *  entry per keystroke — callers should debounce free-text inputs upstream). */
export function useUrlState<T extends Record<string, string | undefined>>(
  defaults: T,
  allowedKeys: (keyof T)[],
) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const state = useMemo(
    () => parseState(searchParams, defaults, allowedKeys),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [searchParams.toString()],
  );

  const setState = useCallback(
    (patch: Partial<T>) => {
      const next = { ...state, ...patch };
      // Merge onto the FULL current querystring — only this hook's owned keys change; any
      // params owned by other useUrlState instances (per-card overrides, etc.) are kept.
      const params = mergeState(new URLSearchParams(searchParams.toString()), next, defaults, allowedKeys);
      const qs = params.toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [state, defaults, allowedKeys, pathname, router, searchParams],
  );

  return [state, setState] as const;
}
