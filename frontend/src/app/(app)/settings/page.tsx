import { Settings as SettingsIcon } from "lucide-react";

import { EmptyState } from "@/components/ui/EmptyState";

export default function SettingsPage() {
  return (
    <EmptyState
      icon={SettingsIcon}
      title="Settings"
      what="Tenant configuration, scoring thresholds, vision backend, and live backend health."
      why="Built in a later phase."
    />
  );
}
