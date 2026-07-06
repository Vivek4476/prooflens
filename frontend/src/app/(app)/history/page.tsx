import { History } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";

export default function HistoryPage() {
  return (
    <EmptyState
      icon={History}
      title="Upload History"
      what="Every scored image, newest first — band, score, reason, and processing time."
      why="Built in a later phase."
      cta={{ label: "Analyze a Photo", href: "/analyze" }}
    />
  );
}
