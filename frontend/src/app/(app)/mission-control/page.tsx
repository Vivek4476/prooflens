"use client";

import { useState } from "react";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { MetricCard } from "@/components/ui/MetricCard";
import { DecisionStream } from "@/components/mission/DecisionStream";
import { AlertsPanel } from "@/components/mission/AlertsPanel";
import { DecisionMixBar } from "@/components/mission/DecisionMixBar";
import { ProvenanceGauge } from "@/components/mission/ProvenanceGauge";
import { DecisionDrawer } from "@/components/decision/DecisionDrawer";
import { useAnalytics } from "@/lib/api/hooks";
import { useLiveDecisions } from "@/lib/live";
import { formatMs } from "@/lib/utils";
import { formatPct } from "@/lib/format";
import { bandRate } from "@/lib/analytics/bandRates";
import type { ResultItem } from "@/lib/api/types";

export default function MissionControlPage() {
  const analytics = useAnalytics();
  const { items, newIds } = useLiveDecisions(25);
  const [selected, setSelected] = useState<ResultItem | null>(null);
  const a = analytics.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mission Control"
        description="Automated decisions, live — watch, trust, audit."
        actions={
          <span className="flex items-center gap-2 text-[12px] text-text-secondary">
            <span
              className="inline-block h-2 w-2 rounded-full bg-verdict-clear animate-pulse-dot"
              style={{ ["--pulse-color" as string]: "rgba(31,157,87,0.5)" }}
              aria-hidden
            />
            Live
          </span>
        }
      />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <MetricCard label="Decisions today" value={a?.images_today ?? "—"} />
        <MetricCard label="Suspect / fraud" value={a ? formatPct(a.suspect_pct) : "—"} />
        <MetricCard label="Unassessed" value={a ? formatPct(bandRate(a.band_distribution, a.total, "Unassessed")) : "—"} />
        <MetricCard label="Avg latency" value={a ? formatMs(a.avg_processing_ms) : "—"} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.55fr_1fr]">
        <Card glow>
          <CardHeader serif title="Live decision stream" subtitle="auto-scored & written to LSQ" />
          <DecisionStream items={items} newIds={newIds} onSelect={setSelected} />
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader serif title="Alerts" subtitle="system-level" />
            <AlertsPanel a={a} />
          </Card>
          <Card>
            <CardHeader serif title="Decision mix" subtitle="today" />
            <div className="p-4"><DecisionMixBar dist={a?.band_distribution} /></div>
          </Card>
          <Card>
            <CardHeader serif title="Provenance coverage" />
            <div className="p-4">
              {/* TODO(provenance-engine): replace with real coverage */}
              <ProvenanceGauge pct={64} />
            </div>
          </Card>
        </div>
      </div>

      <DecisionDrawer result={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
