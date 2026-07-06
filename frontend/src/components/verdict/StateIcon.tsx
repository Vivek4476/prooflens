import { AlertTriangle, CheckCircle2, Info, MinusCircle, ShieldAlert } from "lucide-react";

import type { CheckState } from "@/lib/verdict";

const MAP = {
  pass: { Icon: CheckCircle2, cls: "text-ok" },
  warn: { Icon: AlertTriangle, cls: "text-warn" },
  fail: { Icon: ShieldAlert, cls: "text-danger" },
  skip: { Icon: MinusCircle, cls: "text-text-muted" },
  info: { Icon: Info, cls: "text-text-muted" },
} as const;

export function StateIcon({ state, size = 18 }: { state: CheckState; size?: number }) {
  const { Icon, cls } = MAP[state];
  return <Icon size={size} className={cls} aria-hidden />;
}

export function stateClass(state: CheckState): string {
  return MAP[state].cls;
}
