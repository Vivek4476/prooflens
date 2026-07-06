import { ScanSearch } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";

export default function AnalyzePage() {
  return (
    <EmptyState
      icon={ScanSearch}
      title="Analyze Photo"
      what="Drop in a photo to score it against the live pipeline and see the full explainability breakdown."
      why="The scoring experience is built in the next phase."
    />
  );
}
