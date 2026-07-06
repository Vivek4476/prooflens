"use client";

import { Activity, Building2, KeyRound, SlidersHorizontal } from "lucide-react";

import { Card, CardHeader } from "@/components/ui/Card";
import { Skeleton } from "@/components/ui/Skeleton";
import { useHealth, useTenants } from "@/lib/api/hooks";
import { API_URL } from "@/lib/api/client";
import type { HealthState } from "@/lib/api/types";
import { cn } from "@/lib/utils";

function Row({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4 px-5 py-3 text-body-sm">
      <span className="text-text-secondary">{label}</span>
      <span className={cn("text-right text-text", mono && "font-mono text-body-sm tabular-nums")}>{value}</span>
    </div>
  );
}

const DOT: Record<HealthState, string> = {
  ok: "bg-ok",
  degraded: "bg-warn",
  down: "bg-danger",
  loading: "bg-text-muted",
};

function StatusPill({ up, label }: { up: boolean | undefined; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("h-2 w-2 rounded-full", up == null ? DOT.loading : up ? DOT.ok : DOT.down)} />
      <span className="text-text">{up == null ? "…" : up ? label : `${label} unreachable`}</span>
    </span>
  );
}

export default function SettingsPage() {
  const health = useHealth();
  const tenants = useTenants();
  const tenant = tenants.data?.[0];

  return (
    <div className="space-y-6">
      <p className="text-body-sm text-text-secondary">
        Tenant configuration, scoring policy, and live backend status.
      </p>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Backend Health */}
        <Card>
          <CardHeader title="Backend health" subtitle="Live liveness and readiness probes." />
          <div className="divide-y divide-border">
            <Row label="API (/healthz)" value={<StatusPill up={health.data?.live} label="Healthy" />} />
            <Row label="Database (/readyz)" value={<StatusPill up={health.data?.ready} label="Ready" />} />
            <Row label="API base URL" value={API_URL} mono />
          </div>
        </Card>

        {/* Tenant */}
        <Card>
          <CardHeader title="Tenant" subtitle="From the admin API." />
          {tenants.isLoading ? (
            <div className="p-4"><Skeleton className="h-24 w-full" /></div>
          ) : tenants.isError ? (
            <p className="px-5 py-6 text-body-sm text-text-muted">
              Admin API unavailable (needs a valid admin token).
            </p>
          ) : !tenant ? (
            <p className="px-5 py-6 text-body-sm text-text-muted">No tenants configured.</p>
          ) : (
            <div className="divide-y divide-border">
              <Row label="Name" value={tenant.name} />
              <Row label="Slug" value={tenant.slug} mono />
              <Row
                label="Status"
                value={
                  <span className="inline-flex items-center gap-1.5">
                    <span className={cn("h-2 w-2 rounded-full", tenant.active ? "bg-ok" : "bg-text-muted")} />
                    {tenant.active ? "Active" : "Inactive"}
                  </span>
                }
              />
              <Row label="Vision backend" value={<code className="rounded bg-surface-2 px-1.5 py-0.5">{tenant.vision_backend}</code>} />
              <Row label="LSQ credentials" value={tenant.has_lsq_credentials ? "Configured (encrypted)" : "Not set"} />
            </div>
          )}
        </Card>

        {/* LSQ field mapping */}
        <Card>
          <CardHeader title="LSQ write-back fields" subtitle="Order: band → score → reason." />
          {tenant && Object.keys(tenant.field_map).length > 0 ? (
            <div className="divide-y divide-border">
              {(["band", "score", "reason"] as const).map((k) => (
                <Row key={k} label={k[0].toUpperCase() + k.slice(1)} value={tenant.field_map[k] ?? "—"} mono />
              ))}
            </div>
          ) : (
            <p className="flex items-center gap-2 px-5 py-6 text-body-sm text-text-muted">
              <KeyRound size={15} /> No custom-field mapping configured.
            </p>
          )}
        </Card>

        {/* Scoring policy */}
        <Card>
          <CardHeader title="Scoring policy" subtitle="Effective thresholds (defaults + tenant overrides)." />
          {tenant ? (
            <div className="divide-y divide-border">
              <Row label="Clear band" value={`≥ ${tenant.scoring.bands.clear}`} mono />
              <Row label="Doubtful band" value={`${tenant.scoring.bands.doubtful}–${tenant.scoring.bands.clear - 1}`} mono />
              <Row label="Blur floor" value={tenant.scoring.thresholds.blur_floor} mono />
              <Row label="Plausibility gate" value={tenant.scoring.thresholds.plausibility_gate} mono />
              <Row label="Duplicate ≤ (near)" value={tenant.scoring.thresholds.dup_near} mono />
            </div>
          ) : (
            <p className="flex items-center gap-2 px-5 py-6 text-body-sm text-text-muted">
              <SlidersHorizontal size={15} /> Load a tenant to view its scoring policy.
            </p>
          )}
        </Card>
      </div>

      <div className="flex items-center gap-3 text-caption text-text-muted">
        <Activity size={14} />
        <span>ProofLens · Capture Integrity — scores &amp; flags, never blocks. Images are never stored.</span>
        <Building2 size={14} className="ml-auto" />
        <span>ProofLens</span>
      </div>
    </div>
  );
}
