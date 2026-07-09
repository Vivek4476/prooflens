// The single service layer. Every request goes through here.
import axios from "axios";

import type {
  AnalyticsParams,
  AnalyticsSummary,
  ResultItem,
  ResultsPage,
  ReviewDecision,
  ScoreResponse,
  Tenant,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

// Admin token is dev-only convenience for the demo; in real deployments the
// admin surface would sit behind SSO, not a public env var.
const ADMIN_TOKEN = process.env.NEXT_PUBLIC_ADMIN_TOKEN || "dev-admin-token";

export const http = axios.create({ baseURL: API_URL, timeout: 120_000 });

export const api = {
  async health(): Promise<{ status: string }> {
    const { data } = await http.get("/healthz");
    return data;
  },

  async ready(): Promise<{ status: string }> {
    const { data } = await http.get("/readyz");
    return data;
  },

  async score(file: File, opts?: { tenant?: string; backend?: string }): Promise<ScoreResponse> {
    const form = new FormData();
    form.append("image", file);
    if (opts?.tenant) form.append("tenant", opts.tenant);
    if (opts?.backend) form.append("backend", opts.backend);
    const { data } = await http.post("/v1/score", form);
    return data;
  },

  async results(params?: {
    limit?: number;
    offset?: number;
    band?: string;
    review?: string;
    reason?: string;
    rep_id?: string;
    from?: string;
    to?: string;
  }): Promise<ResultsPage> {
    const { data } = await http.get("/v1/results", { params });
    return data;
  },

  // A single stored verdict with its full evidence — powers the Verdict Detail page.
  async result(id: string): Promise<ResultItem> {
    const { data } = await http.get(`/v1/results/${encodeURIComponent(id)}`);
    return data;
  },

  async analytics(params?: AnalyticsParams): Promise<AnalyticsSummary> {
    const { data } = await http.get("/v1/analytics/summary", { params });
    return data;
  },

  async tenants(): Promise<Tenant[]> {
    const { data } = await http.get("/admin/tenants", {
      headers: { "X-Admin-Token": ADMIN_TOKEN },
    });
    return data;
  },

  // Record a moderator decision. Returns the updated result (with a `review` block).
  async reviewDecision(id: string, decision: ReviewDecision, note?: string): Promise<ResultItem> {
    const { data } = await http.post(`/v1/results/${encodeURIComponent(id)}/review`, {
      decision,
      note,
    });
    return data;
  },
};
