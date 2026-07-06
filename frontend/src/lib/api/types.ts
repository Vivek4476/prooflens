// Domain types mirroring the ProofLens backend. `npm run gen:api` regenerates
// src/lib/api/schema.ts from the live /openapi.json; these hand types give the
// app ergonomic access (and document checks[].data, which is loosely typed).

export type Band = "Clear" | "Doubtful" | "Suspect";

export type CheckName = "exif" | "sharpness" | "uniqueness" | "recapture" | "content";

export interface CheckOutcome {
  name: string;
  available: boolean;
  score: number | null;
  summary: string;
  metric: number | null;
  data: Record<string, unknown>;
  latency_ms: number | null;
}

export interface Verdict {
  band: Band;
  score: number;
  reason: string; // verbatim from backend vocabulary — never rewrite
  reason_code: string;
  checks: CheckOutcome[];
  rubric_version: string;
}

export interface ScoreResponse extends Verdict {
  result_id: string;
  processing_ms: number;
  backend: string;
  backend_is_real: boolean;
}

export interface ResultItem {
  id: string;
  created_at: string;
  band: Band;
  score: number;
  reason: string;
  reason_code: string;
  rubric_version: string;
  processing_ms: number;
  source: "webhook" | "direct";
  opportunity_id: string | null;
  rep_id: string | null;
  checks: CheckOutcome[];
}

export interface ResultsPage {
  items: ResultItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface TopReason {
  reason_code: string;
  reason: string;
  count: number;
}

export interface DaySeries {
  date: string;
  count: number;
  clear: number;
  doubtful: number;
  suspect: number;
  avg_score: number;
}

export interface AnalyticsSummary {
  total: number;
  images_today: number;
  band_distribution: Record<Band, number>;
  suspect_pct: number;
  avg_score: number;
  avg_processing_ms: number;
  duplicates_caught: number;
  top_reasons: TopReason[];
  series: DaySeries[];
}

export interface Tenant {
  id: string;
  slug: string;
  name: string;
  active: boolean;
  vision_backend: string;
  field_map: Record<string, string>;
  has_lsq_credentials: boolean;
}

export type HealthState = "ok" | "degraded" | "down" | "loading";
