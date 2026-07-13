// Domain types mirroring the ProofLens backend. `npm run gen:api` regenerates
// src/lib/api/schema.ts from the live /openapi.json; these hand types give the
// app ergonomic access (and document checks[].data, which is loosely typed).

// "Unassessed" is NOT a graded risk band — it means the vision check was
// unavailable so the image was never assessed (always routes to review).
export type Band = "Clear" | "Doubtful" | "Suspect" | "Unassessed";

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
  // Set when the requested vision backend was unavailable and scoring fell back
  // to the stub (fail-open). Null on the normal path.
  backend_note?: string | null;
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
  // Present once a moderator has actioned this result; null/absent while pending.
  review?: ReviewBlock | null;
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
  short_label: string; // NEW — always present now
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

export interface AnalyticsBucket {
  bucket_label: string;
  start: string; // YYYY-MM-DD
  end: string; // YYYY-MM-DD
  clear: number;
  doubtful: number;
  suspect: number;
  unassessed: number;
  total: number;
  avg_score: number;
  incomplete: boolean;
}

export interface PeriodAggregate {
  clear: number;
  doubtful: number;
  suspect: number;
  unassessed: number;
  total: number;
  avg_score: number;
}

export interface PeriodBounds {
  from: string; // YYYY-MM-DD
  to: string; // YYYY-MM-DD
}

export interface AnalyticsGroup {
  node: string;
  total: number;
  clear: number;
  doubtful: number;
  suspect: number;
  unassessed: number;
  avg_score: number;
  suspect_rate: number;
  share: number;
  // Present only for group_by=agent: the real agent_id (node is the display
  // name). Used to link a DSE row to /dse?agent=<id> — the name won't resolve.
  agent_id?: string;
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
  series: DaySeries[]; // legacy, unchanged — still used by Dashboard if applicable
  buckets: AnalyticsBucket[]; // NEW
  incomplete: boolean; // NEW
  previous: PeriodAggregate; // NEW
  period: PeriodBounds; // NEW
  previous_period: PeriodBounds; // NEW
  groups: AnalyticsGroup[]; // NEW — unused by Phase A UI, present for type completeness
  flag_precision?: FlagPrecision; // Gate 3 — optional so older API responses still type-check
  system_health?: SystemHealth; // Pain 9 — optional for backward-compat
}

/**
 * System-health signals (Pain 9), so a vision-backend outage can't masquerade as a fraud
 * trend. scored_without_content_pct = fail-open degradation rate; median_processing_ms =
 * time-to-score. Both null when the period has no results.
 */
export interface SystemHealth {
  scored_without_content_pct: number | null;
  median_processing_ms: number | null;
}

/**
 * How often a Doubtful/Suspect flag was confirmed on review (Gate 3).
 * confirmed = reject; overturned = approve + false_positive; reviewed = confirmed + overturned
 * (escalate and pending excluded). precision_pct = confirmed/reviewed*100, null when reviewed 0.
 */
export interface FlagPrecision {
  reviewed: number;
  confirmed: number;
  overturned: number;
  precision_pct: number | null;
}

export type Bucket = "daily" | "weekly" | "monthly";
export type GroupBy = "none" | "zone" | "srsm" | "rsm" | "sm" | "branch" | "city" | "agent";

export interface AnalyticsParams {
  start_date?: string; // YYYY-MM-DD
  end_date?: string; // YYYY-MM-DD
  bucket?: Bucket;
  group_by?: GroupBy;
}

export interface ScoringConfig {
  weights: { content: number; sharpness: number; uniqueness: number; metadata: number };
  thresholds: {
    blur_floor: number;
    sharp_ok: number;
    dup_exact: number;
    dup_near: number;
    unique_distance: number;
    plausibility_gate: number;
  };
  bands: { clear: number; doubtful: number };
  caps: Record<string, number>;
}

export interface Tenant {
  id: string;
  slug: string;
  name: string;
  active: boolean;
  vision_backend: string;
  field_map: Record<string, string>;
  has_lsq_credentials: boolean;
  scoring: ScoringConfig;
}

export type ReviewDecision = "approve" | "reject" | "false_positive" | "escalate";

export interface ReviewBlock {
  status: ReviewDecision;
  note: string | null;
  reviewed_at: string | null;
  reviewer: string | null;
}

export type HealthState = "ok" | "degraded" | "down" | "loading";

// --- Bulk upload (Phase 1) ---------------------------------------------

/** One row of the POST /v1/bulk-score request body — a mapped CSV row. */
export interface BulkScoreRow {
  image_url: string;
  rep_id: string | null;
  opportunity_id: string | null;
}

export interface BulkScoreResponse {
  job_id: string;
  total: number;
}

export type BulkJobStatus = "queued" | "running" | "done";

/** Per-photo outcome inside a bulk job. `band`/`score`/`reason_code`/`result_id`
 *  are null until scored; `error` is set (and the rest stay null) on a
 *  fail-open per-row failure — the batch continues regardless. */
export interface BulkResultItem {
  image_url: string;
  rep_id: string | null;
  opportunity_id: string | null;
  band: Band | null;
  score: number | null;
  reason_code: string | null;
  result_id: string | null;
  error: string | null;
}

export interface BulkJob {
  status: BulkJobStatus;
  processed: number;
  total: number;
  results: BulkResultItem[];
}

// --- DSE (agent) scorecard + search ---

export interface DseSearchResult {
  agent_id: string;
  name: string;
  branch: string | null;
  sm: string | null;
}

export interface DseSearchResponse {
  results: DseSearchResult[];
}

export interface DseChain {
  sm: string | null;
  rsm: string | null;
  srsm: string | null;
  zone: string | null;
  branch: string | null;
  city: string | null;
}

export interface DseTrendPoint {
  bucket_label: string;
  start: string; // YYYY-MM-DD
  end: string; // YYYY-MM-DD
  suspect: number;
  total: number;
  suspect_rate: number;
  incomplete: boolean;
}

export interface DseTopReason {
  reason_code: string;
  short_label: string;
  count: number;
}

export interface DseScorecard {
  agent_id: string;
  name: string;
  chain: DseChain;
  total: number;
  band_distribution: Record<Band, number>;
  suspect_rate: number;
  avg_score: number;
  top_reasons: DseTopReason[];
  trend: DseTrendPoint[];
  recent: ResultItem[];
  truncated: boolean; // true when total exceeded the scorecard's 5000 cap
}
