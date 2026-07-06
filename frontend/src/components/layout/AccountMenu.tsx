"use client";

import { LogOut, ShieldCheck, UserRound } from "lucide-react";
import { useState } from "react";

import { useToast } from "@/components/ui/Toast";

/**
 * Real account chrome in place of the old hardcoded "UA / Demo user" avatar.
 * Authentication (SSO + roles) is an M4 deliverable; until then this is honest
 * about being a demo session rather than pretending to be signed-in identity.
 */
export function AccountMenu() {
  const [open, setOpen] = useState(false);
  const toast = useToast();

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account"
        className="grid h-9 w-9 place-items-center rounded-full bg-surface-2 text-caption font-semibold text-text-secondary ring-1 ring-border transition-colors hover:text-text"
      >
        DO
      </button>

      {open && (
        <>
          <button
            className="fixed inset-0 z-40 cursor-default"
            aria-hidden
            tabIndex={-1}
            onClick={() => setOpen(false)}
          />
          <div
            role="menu"
            className="absolute right-0 top-full z-50 mt-1.5 w-60 rounded-md border border-border bg-surface p-1 shadow-2"
          >
            <div className="flex items-center gap-3 border-b border-border px-3 py-2.5">
              <span className="grid h-9 w-9 place-items-center rounded-full bg-surface-2 text-caption font-semibold text-text-secondary">
                DO
              </span>
              <div className="min-w-0">
                <p className="truncate text-body-sm font-medium text-text">Demo Operator</p>
                <p className="truncate text-caption text-text-muted">Reviewer · demo session</p>
              </div>
            </div>
            <MenuRow icon={UserRound} label="Profile" onClick={() => notify(toast)} />
            <MenuRow icon={ShieldCheck} label="Roles & access" onClick={() => notify(toast)} />
            <div className="my-1 h-px bg-border" />
            <MenuRow icon={LogOut} label="Sign out" onClick={() => notify(toast)} />
          </div>
        </>
      )}
    </div>
  );
}

function notify(toast: ReturnType<typeof useToast>) {
  toast({
    kind: "info",
    title: "Authentication not enabled",
    description: "SSO, roles, and sign-out arrive in the enterprise release.",
  });
}

function MenuRow({
  icon: Icon,
  label,
  onClick,
}: {
  icon: typeof UserRound;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      role="menuitem"
      onClick={onClick}
      className="flex w-full items-center gap-2.5 rounded-sm px-3 py-2 text-left text-body-sm text-text-secondary transition-colors hover:bg-surface-2 hover:text-text"
    >
      <Icon size={15} className="shrink-0" />
      <span>{label}</span>
    </button>
  );
}
