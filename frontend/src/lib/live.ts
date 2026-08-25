import { useEffect, useRef, useState } from "react";
import { useResults } from "./api/hooks";
import type { ResultItem } from "./api/types";

/** Ids in `next` not seen in `prevIds`. Empty on first load (prevIds empty) to avoid a flash. */
export function pickNewIds(prevIds: string[], next: ResultItem[]): Set<string> {
  if (prevIds.length === 0) return new Set();
  const prev = new Set(prevIds);
  return new Set(next.filter((x) => !prev.has(x.id)).map((x) => x.id));
}

/** Newest decisions on a short poll, tracking which arrived since the last tick (for animation). */
export function useLiveDecisions(limit = 25) {
  const q = useResults({ limit }, 4_000);
  const prevIds = useRef<string[]>([]);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());
  const items = q.data?.items ?? [];

  useEffect(() => {
    if (!q.data) return;
    setNewIds(pickNewIds(prevIds.current, items));
    prevIds.current = items.map((x) => x.id);
  }, [q.dataUpdatedAt]); // fires each successful poll

  return { items, newIds, isLoading: q.isLoading };
}
