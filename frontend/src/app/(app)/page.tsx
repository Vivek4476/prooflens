import { LayoutDashboard } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <p className="text-body-sm text-text-secondary">
        Is the system healthy, and is risk elevated today?
      </p>
      <EmptyState
        icon={LayoutDashboard}
        title="Dashboard"
        what="Today's capture-integrity KPIs and the most recent verdicts will appear here."
        why="Built in a later phase — the health indicator in the top bar is already live."
        cta={{ label: "Analyze a Photo", href: "/analyze" }}
      />
    </div>
  );
}
