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
      const serialized = serializeState(next, defaults);
      const qs = new URLSearchParams(serialized).toString();
      router.replace(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
    },
    [state, defaults, pathname, router],
  );

  return [state, setState] as const;
}
