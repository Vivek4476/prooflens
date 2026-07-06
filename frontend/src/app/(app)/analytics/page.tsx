import { BarChart3 } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";

export default function AnalyticsPage() {
  return (
    <EmptyState
      icon={BarChart3}
      title="Analytics"
      what="Where is risk trending — band mix over time, score trend, top reasons, and duplicate attempts."
      why="Built in a later phase."
      cta={{ label: "Analyze a Photo", href: "/analyze" }}
    />
  );
}
