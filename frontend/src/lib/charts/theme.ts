/** Shared Recharts styling — reads CSS vars so charts track light/dark (Noir) automatically.
 *  Generic data series use the Focus-Indigo accent family, NOT verdict hues (verdict color = meaning). */
export const CHART_THEME = {
  grid: "var(--border)",
  axis: "var(--text-muted)",
  series: ["var(--accent)", "var(--accent-hover)", "var(--text-secondary)"],
  areaFill: (color: string) => `color-mix(in srgb, ${color} 14%, transparent)`,
};
