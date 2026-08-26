import type { Band } from "@/lib/api/types";

export function bandRate(
  dist: Record<Band, number>,
  total: number,
  band: Band,
): number {
  if (!total) return 0;
  return (dist[band] / total) * 100;
}
