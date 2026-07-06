"use client";

import { Check, ChevronsUpDown } from "lucide-react";
import { useState } from "react";

import { useTenants } from "@/lib/api/hooks";

/**
 * The active tenant this ProofLens workspace serves. Styled as a switcher to
 * establish "whose data am I looking at?" chrome; real multi-tenant switching
 * lands with workspace roles (M4). Falls back to the co-brand default when the
 * admin API isn't reachable.
 */
export function TenantSwitcher() {
  const [open, setOpen] = useState(false);
  const [imgOk, setImgOk] = useState(true);
  const tenants = useTenants();
  const active = tenants.data?.[0];
  const name = active?.name ?? "Aditya Birla Capital";

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="group flex w-full items-center gap-2.5 rounded-md border border-border bg-surface px-2.5 py-2 text-left transition-colors hover:bg-surface-2"
        title={`${name} — active tenant`}
      >
        <span className="grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded bg-white ring-1 ring-border">
          {imgOk ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src="/brand/abc-life-insurance.png"
              alt=""
              className="h-5 w-auto"
              onError={() => setImgOk(false)}
            />
          ) : (
            <span className="text-[10px] font-bold text-brand-crimson">ABC</span>
          )}
        </span>
        <span className="flex min-w-0 flex-1 flex-col leading-tight">
          <span className="truncate text-body-sm font-medium text-text">{name}</span>
          <span className="truncate text-caption text-text-muted">Life Insurance · tenant</span>
        </span>
        <ChevronsUpDown size={14} className="shrink-0 text-text-muted" />
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
            className="absolute left-0 right-0 top-full z-50 mt-1.5 rounded-md border border-border bg-surface p-1 shadow-2"
          >
            <div className="flex items-center gap-2 rounded-sm px-2 py-1.5">
              <Check size={14} className="text-brand-crimson" />
              <span className="flex-1 truncate text-body-sm text-text">{name}</span>
            </div>
            <p className="px-2 py-1.5 text-caption text-text-muted">
              Multi-tenant switching arrives with workspace roles.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
