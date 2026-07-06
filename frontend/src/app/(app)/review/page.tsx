import { ClipboardCheck } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";

export default function ReviewPage() {
  return (
    <EmptyState
      icon={ClipboardCheck}
      title="Review Queue"
      what="Doubtful and Suspect verdicts queued for a human decision — approve, reject, or mark a false positive."
      why="Built in a later phase."
    />
  );
}
